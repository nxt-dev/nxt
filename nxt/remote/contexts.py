# Builtin
import sys
import os
import logging
from collections import namedtuple

from nxt import nxt_io

logger = logging.getLogger('nxt')

REMOTE_CONTEXT_BUILTIN_NODE = '_remote_sub_graph'
SUB_GRAPH_BUILTIN_NODE = '_sub_graph'
REMOTE_CONTEXT_ATTR_NAME = '_context'


class RemoteContext(object):
    def __init__(self, name, exe, graph, args=()):
        """Create a cusom remote context for NXT, the return of this function
        should be fed to `register_context`.

        :param name: Desired context name (used to identify it to users)
        :param exe: Path to Python interpreter executable, if another executable
        is supplied a script to call with that executable is expected.
        :param graph: Filepath of context setup graph
        :param args: If the exe arg is not a Python interpreter additional args
        may need to passed.
        :type args: list | tuple
        """
        self.name = name
        self.exe = exe
        self.graph = graph
        self.args = args


_CONTEXTS = []
starter_contexts = {'maya':
                        os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                     'maya_context.nxt')),
                    'blender':
                        os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                     'blender_context.nxt'))}


def register_context(context):
    """Register context class with nxt

    >>> my_context = RemoteContext('Maya', 'path_to/bin/mayapy.exe', './maya_context.nxt')
    (RemoteContext)
    >>> register_context(my_context)
    (registered context: Maya)

    :param context: RemoteContext object
    :type context: RemoteContext
    """
    global _CONTEXTS
    _CONTEXTS += [context]
    logger.info('registered context: ' + context.name)


def find_context_by_name(name):
    for context in _CONTEXTS:
        if context.name == name:
            return context
    return None


def iter_context_names():
    for context in _CONTEXTS:
        yield context.name


_context_graph = '${var}/_context.nxt'.format(var=nxt_io.BUILTIN_GRAPHS_ENV_VAR)
PYTHON_CONTEXT = RemoteContext('python', sys.executable, _context_graph)
register_context(PYTHON_CONTEXT)


def get_current_context_exe_name():
    exe_name = os.path.basename(sys.executable)
    exe_name, _ = os.path.splitext(exe_name)
    return exe_name
