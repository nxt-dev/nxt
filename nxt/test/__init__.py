# Builtin
import os
import inspect

# NOTE: the behavior of inspect.currentframe() likely requires cpython.
# https://docs.python.org/2.7/library/inspect.html#inspect.currentframe
_this_file = inspect.getframeinfo(inspect.currentframe()).filename
TEST_DIR = os.path.dirname(os.path.abspath(_this_file))


def get_test_graph(graph_name):
    """Shortcut to get full path to desired test graph.

    Only assembles path, no validation.

    :param graph_name: Filename of testing graph.
    :type graph_name: str
    :return: Full graph path for given graph name.
    :rtype: str
    """
    return os.path.join(TEST_DIR, graph_name)
