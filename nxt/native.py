"""Optional native speedups.

nxt ships a compiled module for each OS it supports, in nxt/_bin/<platform>/.
Built for Python's stable ABI, one build serves every Python from 3.10 up,
including the ones inside Maya, Blender and Unreal. Every function in it has
a Python twin in nxt that gives the same result, so when the module is
missing or won't load, nxt runs exactly the same, only slower.

Set NXT_NO_NATIVE=1 to use the Python code even where the module loads.

``lib`` is the loaded module, or None.
"""
import importlib.machinery
import importlib.util
import logging
import os
import platform
import sys

logger = logging.getLogger(__name__)

NO_NATIVE_ENV_VAR = 'NXT_NO_NATIVE'
MODULE_NAME = '_nxt_native'
BIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_bin')


def platform_tag():
    """The _bin folder for this OS and processor, or None if nxt has no
    build for it."""
    machine = platform.machine().lower()
    if machine in ('amd64', 'x86_64', 'x64'):
        machine = 'x86_64'
    elif machine in ('arm64', 'aarch64'):
        machine = 'arm64'
    else:
        return None
    if sys.platform == 'win32':
        return 'windows_' + machine
    if sys.platform == 'darwin':
        # One universal build covers Intel and Apple silicon.
        return 'macos_universal'
    if sys.platform.startswith('linux'):
        return 'linux_' + machine
    return None


def _load():
    if os.environ.get(NO_NATIVE_ENV_VAR, '').strip() not in ('', '0'):
        return None
    tag = platform_tag()
    if not tag:
        return None
    folder = os.path.join(BIN_DIR, tag)
    file_name = MODULE_NAME + ('.pyd' if sys.platform == 'win32' else '.so')
    path = os.path.join(folder, file_name)
    if not os.path.isfile(path):
        return None
    try:
        loader = importlib.machinery.ExtensionFileLoader(MODULE_NAME, path)
        spec = importlib.util.spec_from_file_location(MODULE_NAME, path,
                                                      loader=loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
    except Exception as err:
        # A build for another OS version or a damaged file. The Python
        # code does the same work.
        logger.debug('Not using native speedups: {}'.format(err))
        return None
    return module


lib = _load()

#: Not failures of the module, left to go where they were going.
PASS_THROUGH = (KeyboardInterrupt, SystemExit, GeneratorExit)


def disable(doing):
    """Use the Python code from now on, the native module having failed
    while doing what is named. Called from an except block; says why, once.

    A failure is any exception, a Rust panic among them, which reaches
    Python as a BaseException."""
    global lib
    if lib is None:
        return
    lib = None
    logger.warning('The native speedups failed %s, so nxt uses its Python '
                   'code from now on, which gives the same result.', doing,
                   exc_info=True)
