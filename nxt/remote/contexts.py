# Builtin
import sys
import os
import logging
from collections import namedtuple

logger = logging.getLogger('nxt')

REMOTE_CONTEXT_BUILTIN_NODE = '_remote_sub_graph'
SUB_GRAPH_BUILTIN_NODE = '_sub_graph'
REMOTE_CONTEXT_ATTR_NAME = '_context'
RemoteContext = namedtuple('RemoteContext', ('name', 'exe', 'graph'))
_CONTEXTS = []
starter_contexts = {'maya':
                        os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                     'maya_context.nxt'))}


def register_context(context):
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


PYTHON_CONTEXT = RemoteContext('python', sys.executable,
                               '$NXT_BUILTINS/_context.nxt')
register_context(PYTHON_CONTEXT)


def get_current_context_exe_name():
    exe_name = os.path.basename(sys.executable)
    exe_name, _ = os.path.splitext(exe_name)
    return exe_name
