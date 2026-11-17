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
read before plugins load, so a plugin sees what they set. NXT_USER_DIR,
NXT_SITE_DIR and NXT_ENV_FILES decide which files are read, so a file that
sets one of them is logged and the variable is passed over.

A `$NAME` that is not set is left in the value as written, and logged with
the file and the variable it is in. Names are matched the way the
environment matches them: ignoring case on Windows, exactly elsewhere.
"""
# Builtin
import json
import logging
import os
import re
from collections import OrderedDict

# Internal
from .constants import (USER_CONFIG_DIR, SITE_CONFIG_DIR, USER_DIR_ENV_VAR,
                        SITE_DIR_ENV_VAR)

logger = logging.getLogger(__name__)

ENV_FILES_ENV_VAR = 'NXT_ENV_FILES'
FILE_DIR_VAR = 'NXT_ENV_FILE_DIR'
ENV_FILE_NAME = 'env.json'
FORMAT_VERSION = 1
USER_ENV_FILE = os.path.join(USER_CONFIG_DIR, ENV_FILE_NAME)
SITE_ENV_FILE = os.path.join(SITE_CONFIG_DIR, ENV_FILE_NAME)
#: Read before any env file is, to decide which files are read, so one set
#: from a file would come too late to mean anything.
NOT_FROM_A_FILE = (USER_DIR_ENV_VAR, SITE_DIR_ENV_VAR, ENV_FILES_ENV_VAR)

#: `${NAME}`, `$NAME` and `%NAME%`. A name ends at the first character that
#: cannot be in one, so `$NXT_ENV_FILE_DIRX` is a variable of its own.
_NAME = r'[A-Za-z_][A-Za-z0-9_]*'
_REFERENCE = re.compile(r'\$\{(?P<braced>' + _NAME + r')\}|'
                        r'\$(?P<bare>' + _NAME + r')|'
                        r'%(?P<percent>' + _NAME + r')%')


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


def _key(name):
    """One spelling for a variable name, compared the way the environment
    compares them: Windows ignores case in names, everywhere else does not.
    """
    return name.upper() if os.name == 'nt' else name


def applied():
    """What the env files have put in the environment.

    :return: a copy of {name: value}, names spelled as the environment
        compares them
    :rtype: dict
    """
    return dict(_applied)


def is_applied(name):
    """Whether a variable holds the value an env file gave it.

    False for one set outside nxt, which the files leave alone, and for one
    that something changed after nxt set it.

    :param name: the variable, spelled any way the environment accepts
    :type name: str
    :rtype: bool
    """
    key = _key(name)
    return key in _applied and os.environ.get(name) == _applied[key]


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

    def expand(self, text, unset=None):
        """Fill in the file's own folder, then the environment's variables.

        A variable that is not set is left as written, as a shell would.
        `%NAME%` is only a variable on Windows, where that is how one is
        written, apart from `%NXT_ENV_FILE_DIR%`, the file's folder
        everywhere.

        :param text: a value or an include path, as written in the file
        :param unset: a list that gets the name of each variable that is
            not set
        :type unset: list | None
        :rtype: str
        """
        file_dir = _key(FILE_DIR_VAR)

        def fill(match):
            name = (match.group('braced') or match.group('bare') or
                    match.group('percent'))
            if _key(name) == file_dir:
                return self.directory
            if match.group('percent') and os.name != 'nt':
                return match.group(0)
            if name in os.environ:
                return os.environ[name]
            if unset is not None and name not in unset:
                unset.append(name)
            return match.group(0)

        return _REFERENCE.sub(fill, text)

    def include_paths(self, unset=None):
        """The files this one includes, as absolute paths.

        :param unset: a list that gets the name of each variable that is
            not set
        :type unset: list | None
        :rtype: list
        """
        paths = []
        for written in self.include:
            path = self.expand(written, unset)
            if not os.path.isabs(path):
                path = os.path.join(self.directory, path)
            paths.append(os.path.normpath(path))
        return paths

    def resolve(self, name, unset=None):
        """The text one variable is set to, in the environment as it is.

        :param unset: a list that gets the name of each variable that is
            not set
        :type unset: list | None
        :rtype: str
        """
        value = self.variables[name]
        if isinstance(value, list):
            return os.pathsep.join(self.expand(item, unset)
                                   for item in value)
        return self.expand(value, unset)


def _warn_unset(env_file, unset, where):
    """Say which variables a file uses that are not set. Left as written,
    `$PROJECT/graphs` quietly becomes a folder nobody has."""
    for name in unset:
        logger.warning('{}: ${} in {} is not set, so it is left as written'
                       ''.format(env_file.path, name, where))


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
        unset = []
        includes = env_file.include_paths(unset)
        _warn_unset(env_file, unset, '"{}"'.format(KEYS.INCLUDE))
        for include in includes:
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
        set from files, names spelled as the environment compares them,
        and a list of (path, message) problems
    :rtype: (OrderedDict, list)
    """
    environ = os.environ
    applied = _applied
    problems = []
    result = OrderedDict()
    declared = set()
    refused = set(_key(name) for name in NOT_FROM_A_FILE)
    del _declared[:]
    for env_file in read_files(paths, problems):
        for name in env_file.variables:
            key = _key(name)
            if key in refused:
                logger.warning('{}: {} cannot be set from an env file, it '
                               'decides which env files are read. Set it '
                               'before nxt starts.'.format(env_file.path,
                                                           name))
                continue
            if key not in declared:
                declared.add(key)
                _declared.append(name)
            ours = key in applied and environ.get(name) == applied[key]
            if name in environ and not ours and key not in result:
                logger.debug('{} is already set, {} does not change it'
                             ''.format(name, env_file.path))
                continue
            unset = []
            value = env_file.resolve(name, unset)
            _warn_unset(env_file, unset, name)
            environ[name] = value
            applied[key] = value
            result.pop(key, None)
            result[key] = (value, env_file.path)
    for key in list(applied):
        if key in result:
            continue
        if environ.get(key) == applied[key]:
            del environ[key]
        del applied[key]
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
    from .nxt_io import relative_path_under
    best = ''
    best_depth = -1
    for name in _declared:
        folder = os.environ.get(name, '')
        if not folder or os.pathsep in folder or not os.path.isdir(folder):
            continue
        relative = relative_path_under(filepath, folder)
        if not relative:
            continue
        depth = len(os.path.realpath(folder))
        if depth > best_depth:
            best_depth = depth
            best = '${}/{}'.format(name, relative)
    return best
