"""Methods for file input and output of nxt file data.
"""
# Builtin
import json
import logging
import os
import time
import sys
# Python 2/3 compatibility
if sys.version_info[0] == 2:
    import cPickle as pickle
    # Internal
    import nxt_path
    import clean_json
    import legacy
    from constants import FILE_FORMAT, GRAPH_VERSION
    from nxt_layer import SAVE_KEY
else:
    import pickle
    # Internal
    from . import nxt_path
    from . import clean_json
    from . import legacy
    from .constants import FILE_FORMAT, GRAPH_VERSION
    from .nxt_layer import SAVE_KEY

import gc
import tempfile

nxt_folder = os.path.dirname(os.path.abspath(__file__))
BUILTIN_GRAPHS_DIR = os.path.join(nxt_folder, 'builtin')
BUILTIN_GRAPHS_ENV_VAR = 'NXT_BUILTINS'
os.environ[BUILTIN_GRAPHS_ENV_VAR] = BUILTIN_GRAPHS_DIR
logger = logging.getLogger(__name__)

plugin_expanders = []


def register_reference_path_expander(expander):
    """Register a method to expand reference paths. An expander is a callable \
    that takes exactly 1 argument, a filepath.

    :param expander: A python callable that takes a single argument, and \
    returns an expanded filepath.
    :type expander: callable
    """
    global plugin_expanders
    msg = 'Registered reference path expander from ' + str(expander.__module__)
    logger.info(msg)
    plugin_expanders += [expander]


def expand_reference_path(filepath, layer_dir=None):
    """Where a reference points, resolved the way loading resolves it.

    A reference is stored as written, which is often partial, so anything
    that wants to show a person where it actually lands has to ask the
    same machinery that loading asks. A path that is absolute once
    variables and "~" are expanded is taken as it is. Anything else is
    tried against every registered expander, which is what walks
    NXT_FILE_ROOTS, and then against the referring layer's own directory,
    so a root wins over a file beside the layer, as it does on load.
    Without a layer directory the working directory stands in for it.

    :param filepath: the reference as stored on the layer
    :type filepath: str
    :param layer_dir: directory of the layer holding the reference, which
        is how a path relative to its own file resolves
    :type layer_dir: str | None
    :return: (resolved path, whether a file is there). The path is
        returned even when nothing is there, because where it looked is
        the useful thing to show.
    :rtype: tuple
    """
    if not filepath:
        return '', False
    real_path = nxt_path.full_file_expand(filepath, start=layer_dir)
    if is_absolute(filepath) and os.path.isfile(real_path):
        return real_path, True
    for expander in plugin_expanders:
        try:
            found = expander(filepath, layer_dir)
        except TypeError:
            # Expanders are registered as taking one argument; the one
            # that knows about roots can also take the layer's directory.
            found = expander(filepath)
        if found and os.path.isfile(found):
            return found, True
    if os.path.isfile(real_path):
        return real_path, True
    return real_path, False


def is_absolute(filepath):
    """Whether a path is absolute once its variables and "~" are expanded.

    :param filepath: path as written
    :type filepath: str
    :rtype: bool
    """
    expanded = os.path.expandvars(nxt_path.unify_env_vars(filepath))
    return os.path.isabs(os.path.expanduser(expanded))


def stored_reference_path(path, layer_dir):
    """How a file is written into a layer as a reference.

    Relative to the layer when it sits alongside it, which keeps a graph
    portable. Anything else is stored whole: making a path relative across
    drives or out of the layer's folder would be worse than being explicit,
    and would get in the way of NXT_FILE_ROOTS. Symlinks are resolved on
    both sides first, so a file reached by another name for the same folder
    still counts as beside it.

    :param path: the file to reference
    :type path: str
    :param layer_dir: folder of the layer that holds the reference, or None
        when it has never been saved
    :type layer_dir: str | None
    :return: forward slashed path, relative when the file is beside the layer
    :rtype: str
    """
    path = path.replace(os.path.sep, '/')
    if not layer_dir:
        return path
    try:
        relative = os.path.relpath(os.path.realpath(path),
                                   os.path.realpath(layer_dir))
    except ValueError:
        # Different drive on Windows.
        return path
    relative = relative.replace(os.path.sep, '/')
    if relative.startswith('..'):
        return path
    return relative


def load_file_data(filepath, layer_dir=None):
    """Given a file path this function determines if its a known nxt save
    format and attempts to open it. If the file is out of date it is passed
    to the legacy converter for conversion.

    A relative path is looked for under each registered expander first,
    which is what walks NXT_FILE_ROOTS, and then relative to `layer_dir`,
    or to the working directory when no `layer_dir` is given.

    :param filepath: string of save file filepath
    :type filepath: str
    :param layer_dir: directory of the layer referencing this file, which
        a relative path is resolved against
    :type layer_dir: str | None
    :return: dict of file data
    """
    real_path = nxt_path.full_file_expand(filepath, start=layer_dir)
    for expander in plugin_expanders:
        found_path = expander(filepath)
        if not os.path.isfile(found_path):
            continue
        real_path = found_path
        break
    _, ext = os.path.splitext(real_path)
    if ext not in FILE_FORMAT._ALL:
        raise IOError('Unknown filetype "{}"'.format(ext))
    file_type = FILE_FORMAT.ASCII
    if file_type == FILE_FORMAT.BINARY:
        with open(real_path, 'rb') as file_object:
                file_data = pickle.load(file_object)
    else:
        with open(real_path, 'r') as file_object:
            file_data = json.load(file_object, object_hook=clean_json._byteify)
    file_version = file_data.get(SAVE_KEY.VERSION)
    if not file_version:
        file_version = GRAPH_VERSION.VERSION_STR
        logger.warning('Assuming file version `{}` if trying to open a '
                       'file from before 1.0.0 please add '
                       'the following line to to top of your save file: '
                       '"version": "0.45.0"'.format(GRAPH_VERSION.VERSION_STR))
    if not file_version.count('.'):
        raise IOError('Invalid version number format! Please ensure your save '
                      'file has the following line: "version": "1.x" where '
                      'the x is replaced with an int.')
    # Strip off patch number as we don't support save converters for hot fixes
    major_version, minor_version = [int(n) for n in
                                    file_version.split('.')[0:2]]
    file_too_new = (major_version > GRAPH_VERSION.MAJOR or
                    (major_version == GRAPH_VERSION.MAJOR
                     and minor_version > GRAPH_VERSION.MINOR))
    if file_too_new:
        raise IOError('You are attempting to open a file saved with a newer '
                      'version of nxt ({}). '
                      'Please update nxt!'.format(file_version))
    if major_version == 0 or minor_version < GRAPH_VERSION.MINOR:
        # Calls a legacy check if the full version number doesn't match the
        # current version
        start = time.time()
        template = (file_data.get(SAVE_KEY.VERSION),
                    GRAPH_VERSION.VERSION_STR, str(round(time.time() - start, 3)))
        file_data = legacy.FileConverter.get_converted_data(file_data)
        logger.info("File converted from '{}' to '{}' in {}".format(*template))
    file_data[SAVE_KEY.FILEPATH] = filepath
    file_data[SAVE_KEY.REAL_PATH] = real_path
    name_from_file = os.path.splitext(os.path.basename(filepath))[0]
    file_data[SAVE_KEY.NAME] = file_data.get(SAVE_KEY.NAME, name_from_file)
    return file_data


def save_file_data(save_data, filepath=None, file_format=FILE_FORMAT.ASCII):
    """Saves the given file data to the given file path in the given file
    format. If no filepath is provided a temp file is generated.
    The default file format is ASCII.

    :param save_data: dict of save data
    :param filepath: string of desired output file path or None
    :param file_format: FILE_FORMAT constant
    :return: string of output file path.
    """
    start = time.time()
    ext = file_format
    _, filepath_ext = os.path.splitext(filepath)
    if filepath_ext not in FILE_FORMAT._ALL:
        raise TypeError('Unknown file extension "{}"'.format(filepath_ext))
    elif filepath_ext != ext:
        ext = filepath_ext
    filepath = filepath or tempfile.mkstemp(prefix='nxt_tmp_',
                                            suffix=ext)[1]
    filepath = filepath.replace(os.sep, '/')
    if not filepath.endswith(ext):
        filepath += ext
    if file_format == FILE_FORMAT.BINARY:
        gc.disable()
        with open(filepath, 'wb') as out_file:
            pickle.dump(save_data, out_file, protocol=-1)
        gc.enable()
    else:
        with open(filepath, 'w') as out_file:
            json.dump(save_data, out_file, indent=4, sort_keys=False,
                      separators=(',', ': '))
    logger.info('Successfully saved "' + filepath + '"')
    update_time = str(int(round((time.time() - start) * 1000)))
    logger.debug("Saved in: " + update_time + "ms")
    return filepath


def generate_temp_file(suffix='.nxt'):
    """Safely generates a temp file and returns a Windows safe path

    :param suffix: Optional suffix for the file, default is `.nxt`
    :return: String filepath
    """
    _, cache_filepath = tempfile.mkstemp(suffix=suffix)
    return cache_filepath.replace(os.sep, '/')


def generate_temp_dir(prefix='nxt_tmp_'):
    """Safely generates a temp dir and returns a Windows safe path

    :param prefix: Optional prefix to the dir name, default is `nxt_tmp_`
    :return: String dir path
    """
    return tempfile.mkdtemp(prefix=prefix)
