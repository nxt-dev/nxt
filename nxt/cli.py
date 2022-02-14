# Built-in
import argparse
import sys
import os
import json
import logging
import time

# Internal
from nxt.session import Session

from nxt import legacy
from nxt import nxt_log
from nxt.constants import (API_VERSION, GRAPH_VERSION, NXT_DCC_ENV_VAR,
                           STANDALONE)
from nxt.remote.contexts import iter_context_names
has_editor = False
try:
    import nxt_editor
    from nxt_editor.constants import EDITOR_VERSION
    has_editor = True
except ImportError:
    pass

logger = logging.getLogger('nxt')


class InvalidChoice(Exception):
    pass


class UnrecognizedArg(Exception):
    pass


class CustomParser(argparse.ArgumentParser):
    def error(self, message):
        if "invalid choice" in message:
            # If message doesn't look like a file path, raise the error
            if '.nxt' not in message:
                super(CustomParser, self).error(message)
            raise InvalidChoice(message)
        elif 'unrecognized arguments' in message:
            possible_args = ['-gui']
            args = [a for a in possible_args if a in message]
            if args:
                raise UnrecognizedArg(message)

        super(CustomParser, self).error(message)


def count_down(t=3):
    while t != 0:
        sys.stdout.write('\r' + str(t))
        sys.stdout.flush()
        time.sleep(.8)
        t -= 1
    sys.stdout.write('\r ')
    sys.stdout.flush()


def get_version():
    # Get API version
    api_v = API_VERSION.VERSION_STR
    # Get editor version
    try:
        editor_v = EDITOR_VERSION.VERSION_STR
    except NameError:
        editor_v = False
    # Get graph version
    graph_v = GRAPH_VERSION.VERSION_STR
    # Assemble version string
    if editor_v:
        version_str = 'API {av} | Editor {ev} |  Graph {gv}'
    else:
        version_str = 'API {av} | Graph {gv}'
    return version_str.format(av=api_v, ev=editor_v, gv=graph_v)


def editor(args):
    """Launches editor

    :param args: Namespace Object
    :return: None
    """
    if not has_editor:
        msg = 'Editor not found, you can install with "pip install nxt_editor"'
        print(msg)
        return
    if isinstance(args.path, list):
        paths = args.path
    else:
        paths = [args.path]
    os.environ[NXT_DCC_ENV_VAR] = STANDALONE
    sys.exit(nxt_editor.launch_editor(paths, start_rpc=not args.no_rpc))


def execute(args):
    """Executes graph

    :param args: Namespace Object
    :return: None"""
    if not hasattr(args, 'parameters'):
        parameter_list = []  # Legacy does not support parameters
    else:
        parameter_list = args.parameters
    if not hasattr(args, 'start'):
        start = None # Legacy does not support start points
    else:
        start = args.start

    param_arg_count = len(parameter_list)
    if param_arg_count == 1:
        # Read file for parameters
        param_path = parameter_list[0]
        if not os.path.isfile(param_path):
            msg = 'Single parameter passed, expected it to be valid parameters file. However, "{}" does not exist'.format(param_path)
            raise IOError(msg)
        with open(param_path, 'r') as fp:
            parameters = json.load(fp)
    elif param_arg_count % 2 != 0:
        raise Exception('Invalid parameters supplied, must be 1 file path or '
                        'pattern: "/node.attr value"')
    else:
        # Parse cli formatted input
        parameters = {}
        i = 0
        for _ in range(int(param_arg_count / 2)):
            key = parameter_list[i]
            if not key.startswith('/'):
                raise Exception('Invalid attr path key {}, must be '
                                'formatted as /node.attr'.format(key))
            val = parameter_list[i + 1]
            parameters[key] = val
            i += 2
    context = getattr(args, 'context', None)
    Session().execute_graph(args.path[0], start, parameters, context)
    logger.execinfo('Execution finished!')


def convert(args):
    """Convert save file

    :param args: Namespace Object
    :return: None"""
    legacy.cli_file_convert(args.path[0], args.replace)
    sys.exit()


def main():
    desc = 'execute nxt file or open an nxt session'
    parser = CustomParser(description=desc, prog='nxt')
    subs = parser.add_subparsers()
    parser.add_argument('-v', '--verbose', help='verbose execution '
                                                '(-vv for debugging)',
                        action='count')
    parser.add_argument('--version', action='version', version=get_version())
    # Legacy
    # TODO: Remove at 2.0
    leg_desc = ('Please convert your calls to the new system: '
                'edit, exec,or convert.')
    legacy_parser = subs.add_parser('legacy', help=leg_desc)
    legacy_parser.add_argument('-v', '--verbose', help='verbose execution',
                               action='store_true')
    if has_editor:
        gui_parser = subs.add_parser('ui', help='Launch visual editor.')
        gui_parser.set_defaults(which='ui')
        gui_parser.add_argument('path', type=str, nargs='?',
                                help='file(s) to open', default='')
        no_rpc_help = ('Start editor without setting up an rpc server during '
                       'startup.')
        gui_parser.add_argument('-no-rpc', help=no_rpc_help,
                                action='store_true')

    exec_parser = subs.add_parser('exec', help='Execute graph. See: exec -h')
    exec_parser.set_defaults(which='exec')

    exec_parser.add_argument('path', type=str, nargs=1, help='file to execute')
    exec_parser.add_argument('-s', '--start', nargs='?', default=None,
                             help='start node path')
    exec_parser.add_argument('-c', '--context', nargs='?', default=None,
                             help='optional remote context to call graph in',
                             choices=list(iter_context_names()))

    convert_parser = subs.add_parser('convert', help='upgrades old save file to'
                                                     ' current version.'
                                                     'See: convert -h')
    convert_parser.set_defaults(which='convert')

    convert_parser.add_argument('path', type=str, nargs=1,
                                help='file/dir to convert')

    convert_parser.add_argument('-r', '--replace', help='replace file with '
                                                        'converted.')

    parameters_help = '''Incompatible with -gui! Specify node attributes to
    overload before running the graph. Specify via several in-line arguments,
    or a single path to json file in the following format.
        /node.attr 5
        /node.third_attr "\\"\\"\\"Hello World!\\"\\"\\""
    Escape literal double quotes, try not to use them, if you
    have to, use the Python or file API.
    '''
    exec_parser.add_argument('-p', '--parameters', nargs="*",
                             help=parameters_help, default=())

    legacy_parser.add_argument('-gui', '--gui',
                               help='launch visual editor session '
                                    '(will be depreciated at 2.0)',
                               action='store_true')
    legacy_parser.add_argument('path', type=str, nargs='?', help='file to open',
                               default='')
    legacy_parser.add_argument('-c', '--convert',
                               help='converts old save version to '
                                    'current (will be depreciated at 2.0)',
                               action='store_true')
    legacy_parser.add_argument('-r', '--replace',
                               help='when used with -c the file on disc is '
                                    'replaced (will be depreciated at 2.0)',
                               action='store_true')
    legacy_parser.add_argument('path', type=str, help='file to open',
                               default='')
    test_parser = subs.add_parser('test', help='Runs unit tests')
    test_parser.set_defaults(which='test')
    if '--' in sys.argv:
        idx = sys.argv.index('--')
        sys.argv = sys.argv[idx:]
    try:
        args = parser.parse_args()
    except (InvalidChoice, UnrecognizedArg):
        # Supports legacy
        logger.exception('Invalid choice, falling back to legacy.')
        try:
            sys.argv.remove('legacy')
        except ValueError:
            pass
        args = legacy_parser.parse_args()
        setattr(args, 'which', 'legacy')
        if getattr(args, 'path'):
            if not isinstance(args.path, list):
                args.path = [args.path]
    if args.verbose:
        if os.environ.get(nxt_log.VERBOSE_ENV_VAR) is None:
            os.environ[nxt_log.VERBOSE_ENV_VAR] = str(args.verbose)
        nxt_log.set_verbosity(args.verbose)
    if not hasattr(args, 'which'):
        parser.parse_args(['-h'])
        return
    if args.which == 'legacy':
        if args.gui:
            logger.warning('The flag -gui will be depreciated at 2.0, please '
                           'see: ui -h')
            count_down()
            editor(args)
        if args.convert:
            logger.warning('The flag -c will be depreciated at 2.0, please '
                           'see: convert -h')
            count_down()
            convert(args)
        else:
            logger.warning('Executing without the "exec" keyword will be '
                           'depreciated at 2.0, please '
                           'see: exec -h')
            count_down()
            execute(args)

    elif args.which == 'convert':
        if not args.path:
            raise IOError('No file path to convert provided!')
        convert(args)
    elif args.which == 'test':
        d = os.path.dirname(__file__)
        path = os.path.join(d, 'test/unittests.nxt').replace(os.sep, '/')
        test_args = argparse.Namespace(path=[path], context=None)
        execute(test_args)
    elif args.which == 'ui':
        editor(args)
    elif args.path and args.which == 'exec':
        execute(args)
    else:
        logger.error('No file path provided!')


if __name__ == '__main__':
    main()
