"""Code used while a graph is running.
"""
# Built-in
import code
import sys
import traceback
import logging

# Internal
from . import IGNORE

logger = logging.getLogger(__name__)

def w(string, quote_type=0):
    """Wraps given string in quotes.

    :param string: Input string to be wrapped
    :type string: str
    :param quote_type: Int 1: ', 2: ", 3: ''', 4: \"\"\" Default is 1, any \
        string can also be provided and we will wrap the string arg in that \
        string ie w('Hello World', '$') returns '$Hello World$'.
    :type quote_type: int or str
    :return: String wrapped in quote marks or custom string
    """
    raise NotImplementedError("Written here for documentation, real "
                              "implementation in stage.py")

def execute(paths=(), start=None, parameters=None):
    """While within node code, this method runs other parts of the graph, \
        allowing non-linear execution.

    :param paths: iterable of paths to execute, defaults to ()
    :type paths: iterable, optional
    :param start: node path to start from, defaults to None. \
        NOTE must give *either* paths or start, both is invalid input.
    :type start: str, optional
    :param parameters: parameters dictionary to apply before exectuion, \
        defaults to None
    :type parameters: dict, optional
    :raises GraphError: When there is a problem with execution.
    :raises ValueError: When not given either node paths or a start path.
    """
    raise NotImplementedError("Written here for documentation, real "
                              "implementation in stage.py")

class Console(code.InteractiveConsole):
    def __init__(self, _globals=None, _locals=None, filename=IGNORE,
                 node_path=None, layer_path=None):
        if locals is None:
            _locals = {}
        if globals is None:
            _globals = {}
        self.node_path = node_path
        self.running_lines = []
        self.layer_path = layer_path
        self.locals = _locals
        self.globals = _globals
        self.run_as_global = False
        self.lineno_offset = -1
        code.InteractiveConsole.__init__(self, self.locals, filename)

    def runcode(self, c):
        try:  # Convert to tuple for python3
            exec(c, self.globals)
        except (KeyboardInterrupt, ExitNode, ExitGraph):
            raise
        except (SystemExit, Exception) as err:
            lineno = get_traceback_lineno(err_depth=1)
            lineno -= 1
            try:
                bad_line = self.running_lines[lineno-1]
            except IndexError:
                bad_line = "LINE NOT FOUND"
            _, _, tb = sys.exc_info()
            raise GraphError(err, tb, self.layer_path, self.node_path, lineno,
                             bad_line, err_depth=1)


def get_traceback_lineno(err_depth=0):
    """Get the line number of one of the errors in the current traceback.

    :param err_depth: index of the error to get line number of. 0 is most
    recent, higher values are deeper errors. Defaults to 0
    :type err_depth: int, optional
    :return: line number of requested error
    :rtype: int
    """
    _, _, tb = sys.exc_info()
    _tblist = traceback.extract_tb(tb)
    return _tblist[err_depth][1]


class GraphError(Exception):
    def __init__(self, err, tb, layer_path, err_path, lineno, bad_line,
                 err_depth=0):
        tb_lines = traceback.extract_tb(tb)
        tb_lines = tb_lines[err_depth:]
        # Insert our custom graph traceback
        tb_lines[0] = (layer_path, lineno, err_path, bad_line)
        print_lines = traceback.format_list(tb_lines)
        print_lines[0] = print_lines[0].lstrip()
        print_lines += traceback.format_exception_only(type(err), err)
        print_tb = ''.join(print_lines)
        print_tb = print_tb.rstrip('\n')
        super(Exception, self).__init__(print_tb)


class GraphSyntaxError(GraphError):
    def __init__(self, error, layer_path, error_path, lineno):
        print_lines = traceback.format_exception_only(type(error), error)
        top_line_fmt = 'File "{}", line {}, in {}\n'
        print_lines[0] = top_line_fmt.format(layer_path, lineno, error_path)
        syntax_err_msg = ''.join(print_lines)
        syntax_err_msg = syntax_err_msg.rstrip('\n')
        super(Exception, self).__init__(syntax_err_msg)


class InvalidNodeError(GraphError):
    def __init__(self, node_path):
        super(Exception, self).__init__("Attempted to execute "
                                        "non-exsistant node! \n"
                                        "{}".format(node_path))


class ExitNode(Exception):
    def __init__(self, reason=''):
        super(ExitNode, self).__init__(reason)


class ExitGraph(Exception):
    def __init__(self, reason=''):
        self.runtime_layer = None
        super(ExitGraph, self).__init__(reason)
