"""Environment variables from files, set as nxt starts.

Graphs lean on environment variables: a `$PROJECT_GRAPHS/rig.nxt` reference,
the roots in NXT_FILE_ROOTS, whatever the code in a node reads. Somebody has
to set them before nxt starts, in every place nxt starts from: a shell, a
host's own startup scripts, a farm job. An env file says them once, in a
file that can sit beside the graphs under version control, and nxt sets them
itself wherever it is imported, the editor and a headless run alike.

An env file is json::

    {
        "version": 1,
        "include": ["$NXT_ENV_FILE_DIR/shared_env.json"],
        "variables": {
            "PROJECT_GRAPHS": "$NXT_ENV_FILE_DIR/graphs",
            "NXT_FILE_ROOTS": ["$PROJECT_GRAPHS", "//server/graphs"]
        }
    }

- A value is a string, or a list that is joined with the platform's path
  separator, so one file serves Windows and Linux.
- `$NXT_ENV_FILE_DIR` is the folder of the file it is written in, which is
  what lets a file travel with a project. Other variables are expanded from
  the environment as it is when the value is set, so a value can build on
  one set above it, or in a file read earlier.
- `include` names other env files. They are read first, so the file that
  includes them has the last word. A relative path is relative to the file.

Which files are read, in this order, later ones winning:

1. `env.json` in the site config dir (NXT_SITE_DIR)
2. `env.json` in the user config dir, `~/nxt/config/<major api version>`
3. the files listed in the environment variable NXT_ENV_FILES

A variable that is already set when nxt starts is left alone: whoever
launched the process has the last word, as with a .env file. The files are
read before plugins load, so a plugin sees what they set. NXT_USER_DIR and
NXT_SITE_DIR decide where the files are looked for, so they cannot be set
from one.
"""
# Builtin
import json
import logging
import os
from collections import OrderedDict

# Internal
from .constants import USER_CONFIG_DIR, SITE_CONFIG_DIR

logger = logging.getLogger(__name__)

ENV_FILES_ENV_VAR = 'NXT_ENV_FILES'
FILE_DIR_VAR = 'NXT_ENV_FILE_DIR'
ENV_FILE_NAME = 'env.json'
FORMAT_VERSION = 1
USER_ENV_FILE = os.path.join(USER_CONFIG_DIR, ENV_FILE_NAME)
SITE_ENV_FILE = os.path.join(SITE_CONFIG_DIR, ENV_FILE_NAME)


class KEYS(object):
    VERSION = 'version'
    INCLUDE = 'include'
    VARIABLES = 'variables'


#: What this module has put in the environment, {name: value}. Telling its
#: own values from ones set outside is what lets a file be edited and
#: applied again in a running session without ever replacing somebody
#: else's value.
_applied = {}

#: The names the env files declare, in the order read, whether or not nxt
#: was the one to set them.
_declared = []


class EnvFileError(ValueError):
    """An env file that cannot be used, and why."""


def _identity(path):
    """One spelling for a file, however it was reached."""
    return os.path.normcase(os.path.realpath(path))


class EnvFile(object):
    """One env file: the files it includes and the variables it sets.

    :param path: where the file is, or will be saved
    :type path: str
    """

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.include = []
        self.variables = OrderedDict()

    @property
    def directory(self):
        return os.path.dirname(self.path).replace(os.sep, '/')

    @classmethod
    def load(cls, path):
        """Read an env file.

        :raises EnvFileError: when it is not json, or not shaped like an
            env file
        :raises OSError: when it cannot be read
        :rtype: EnvFile
        """
        env_file = cls(path)
        with open(env_file.path, 'r') as file_object:
            try:
                data = json.load(file_object, object_pairs_hook=OrderedDict)
            except ValueError as error:
                raise EnvFileError('{} is not valid json: {}'
                                   ''.format(env_file.path, error))
        if not isinstance(data, dict):
            raise EnvFileError('{} must hold a json object'
                               ''.format(env_file.path))
        version = data.get(KEYS.VERSION, FORMAT_VERSION)
        if not isinstance(version, int) or version > FORMAT_VERSION:
            raise EnvFileError('{} is env file version {}, this nxt reads up '
                               'to {}'.format(env_file.path, version,
                                              FORMAT_VERSION))
        include = data.get(KEYS.INCLUDE, [])
        if isinstance(include, str):
            include = [include]
        if (not isinstance(include, list) or
                not all(isinstance(item, str) for item in include)):
            raise EnvFileError('"{}" in {} must be a list of file paths'
                               ''.format(KEYS.INCLUDE, env_file.path))
        variables = data.get(KEYS.VARIABLES, {})
        if not isinstance(variables, dict):
            raise EnvFileError('"{}" in {} must be an object of name: value'
                               ''.format(KEYS.VARIABLES, env_file.path))
        env_file.include = list(include)
        for name, value in variables.items():
            env_file.variables[name] = cls.clean_value(name, value,
                                                       env_file.path)
        return env_file

    @staticmethod
    def clean_value(name, value, path=''):
        """A value as an env file holds it: a string or a list of them.

        :raises EnvFileError: for anything that is not text, a number or a
            list of those
        """
        if not name or '=' in name:
            raise EnvFileError('"{}" in {} cannot name an environment '
                               'variable'.format(name, path))
        if isinstance(value, (list, tuple)):
            items = list(value)
        else:
            items = [value]
        cleaned = []
        for item in items:
            if isinstance(item, bool) or not isinstance(item,
                                                        (str, int, float)):
                raise EnvFileError('The value of "{}" in {} must be text or '
                                   'a list of text'.format(name, path))
            cleaned.append(str(item))
        if isinstance(value, (list, tuple)):
            return cleaned
        return cleaned[0]

    def as_data(self):
        """What is written to disk.

        :rtype: OrderedDict
        """
        data = OrderedDict()
        data[KEYS.VERSION] = FORMAT_VERSION
        if self.include:
            data[KEYS.INCLUDE] = list(self.include)
        data[KEYS.VARIABLES] = OrderedDict(self.variables)
        return data

    def save(self):
        """Write the file, making its folder if need be."""
        folder = os.path.dirname(self.path)
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)
        with open(self.path, 'w') as file_object:
            json.dump(self.as_data(), file_object, indent=4)
            file_object.write('\n')

    def expand(self, text):
        """Fill in the file's own folder, then the environment's variables.

        :param text: a value or an include path, as written in the file
        :rtype: str
        """
        for spelling in ('${%s}' % FILE_DIR_VAR, '$' + FILE_DIR_VAR,
                         '%' + FILE_DIR_VAR + '%'):
            text = text.replace(spelling, self.directory)
        return os.path.expandvars(text)

    def include_paths(self):
        """The files this one includes, as absolute paths.

        :rtype: list
        """
        paths = []
        for written in self.include:
            path = self.expand(written)
            if not os.path.isabs(path):
                path = os.path.join(self.directory, path)
            paths.append(os.path.normpath(path))
        return paths

    def resolve(self, name):
        """The text one variable is set to, in the environment as it is.

        :rtype: str
        """
        value = self.variables[name]
        if isinstance(value, list):
            return os.pathsep.join(self.expand(item) for item in value)
        return self.expand(value)


def start_files():
    """The env files nxt looks for when it starts, existing or not.

    :return: paths, the first to be read first
    :rtype: list
    """
    files = []
    if _identity(SITE_ENV_FILE) != _identity(USER_ENV_FILE):
        files.append(SITE_ENV_FILE)
    files.append(USER_ENV_FILE)
    for path in os.environ.get(ENV_FILES_ENV_VAR, '').split(os.pathsep):
        if path.strip():
            files.append(path.strip())
    return files


def read_files(paths=None, problems=None):
    """Load env files and everything they include, in the order they apply.

    A file that is missing or broken is skipped and noted, never raised:
    this runs when nxt is imported, and a typo in a file must not be what
    keeps a host from starting.

    :param paths: the files to start from, start_files() by default
    :param problems: a list that gets a (path, message) for each file that
        could not be used
    :return: EnvFile objects, an included file before the one including it,
        each file once
    :rtype: list
    """
    paths = start_files() if paths is None else paths
    problems = [] if problems is None else problems
    loaded = []
    seen = set()

    def visit(path, wanted_by):
        key = _identity(path)
        if key in seen:
            return
        seen.add(key)
        if not os.path.isfile(path):
            if wanted_by:
                problems.append((path, 'included by {} but does not exist'
                                       ''.format(wanted_by)))
            return
        try:
            env_file = EnvFile.load(path)
        except (EnvFileError, OSError) as error:
            problems.append((path, str(error)))
            return
        for include in env_file.include_paths():
            visit(include, env_file.path)
        loaded.append(env_file)

    for path in paths:
        visit(path, None)
    return loaded


def apply(paths=None):
    """Set the variables the env files hold.

    A variable set outside nxt is left as it is. One this function set
    before is updated, and removed when no file sets it any more, so
    calling it again after editing a file brings a running session in step.

    :param paths: the files to start from, start_files() by default
    :return: {name: (value, path of the file that set it)} for what is now
        set from files, and a list of (path, message) problems
    :rtype: (OrderedDict, list)
    """
    environ = os.environ
    applied = _applied
    problems = []
    result = OrderedDict()
    del _declared[:]
    for env_file in read_files(paths, problems):
        for name in env_file.variables:
            if name not in _declared:
                _declared.append(name)
            ours = name in applied and environ.get(name) == applied[name]
            if name in environ and not ours and name not in result:
                logger.debug('{} is already set, {} does not change it'
                             ''.format(name, env_file.path))
                continue
            value = env_file.resolve(name)
            environ[name] = value
            applied[name] = value
            result.pop(name, None)
            result[name] = (value, env_file.path)
    for name in list(applied):
        if name in result:
            continue
        if environ.get(name) == applied[name]:
            del environ[name]
        del applied[name]
    for path, message in problems:
        logger.warning('Env file skipped: {} ({})'.format(path, message))
    return result, problems


def variable_compact(filepath):
    """A file under a folder an env file variable names, written from it.

    A reference compactor, see nxt_io.register_reference_path_compactor.
    With PROJECT_GRAPHS declared in an env file, a file picked from that
    folder is stored as `$PROJECT_GRAPHS/rig.nxt`, the way it would have
    been typed, instead of the whole path it has on this machine.

    Only variables an env file declares are considered, whoever set their
    value: a project names those on purpose, which cannot be said of
    whatever else is in the environment. The deepest folder wins.

    :param filepath: path of an existing file
    :type filepath: str
    :return: forward slashed `$NAME/relative/path`, or an empty string
    :rtype: str
    """
    real_path = os.path.realpath(filepath)
    best = ''
    best_depth = -1
    for name in _declared:
        folder = os.environ.get(name, '')
        if not folder or os.pathsep in folder or not os.path.isdir(folder):
            continue
        real_folder = os.path.realpath(folder)
        try:
            relative = os.path.relpath(real_path, real_folder)
        except ValueError:
            # Different drive on Windows.
            continue
        if relative.startswith('..') or os.path.isabs(relative):
            continue
        depth = len(real_folder)
        if depth > best_depth:
            best_depth = depth
            best = '${}/{}'.format(name, relative.replace(os.sep, '/'))
    return best
