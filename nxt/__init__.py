# Builtin
import sys
import os
import logging

# Internal Logging setup
if sys.version_info[0] == 2:
    import nxt_log
else:
    from . import nxt_log
nxt_log.initial_setup()

# Internal
if sys.version_info[0] == 2:
    import plugin_loader
    from constants import (DATA_STATE, NODE_ERRORS, UNTITLED, IGNORE,
                           GRID_SIZE, USER_PLUGIN_DIR, USER_DIR_ENV_VAR)
    from session import Session
    import nxt_path
    import nxt_layer
    from remote import contexts
else:
    from . import plugin_loader
    from .constants import (DATA_STATE, NODE_ERRORS, UNTITLED, IGNORE,
                            GRID_SIZE, USER_PLUGIN_DIR, USER_DIR_ENV_VAR)
    from .session import Session
    from . import nxt_path, nxt_layer
    from .remote import contexts

# Load plugins
plugin_loader.load_plugins()

logger = logging.getLogger('nxt')


def execute_graph(filepath, start=None, parameters=None, context=None):
    """Shortest code path to executing a graph from the nxt package.
    Creates a 1 off session and executes the graph within that session.
    Arguments are a direct copy of Session.execute_graph, see there for full
    details.

    :param filepath: Path to the graph file.
    :type filepath: str
    :param start: Path to the node to begin execution from.
    :type start: str
    :param parameters: Dict where key is attr path and value is new attr\
    value.
    :type parameters: dict
    :param context: Optional name of remote context to execute graph in, \
    if none is passed the graph is executed in this interpreter.
    :type context: str
    """
    if context and context not in contexts.iter_context_names():
        logger.info('Valid contexts are: '
                    '{}'.format(list(contexts.iter_context_names())))
        raise NameError('Unknown context: "{}"'.format(context))
    one_shot_session = Session()
    one_shot_session.execute_graph(filepath,
                                   start=start, parameters=parameters,
                                   context=context)


def create_context(custom_name, interpreter_exe=sys.executable,
                   context_graph=None, exe_script_args=()):
    """Generate a remote context given the path to an interpreter executable,
    if none is provided the current sys.executable is used. You must provide a
    custom name for your context. If no errors are raised, the context should
    be available without restarting NXT.

    :param interpreter_exe: String path to Python executable.  If another\
    executable is supplied a script to call with that executable is expected.
    :param custom_name: String of context name. The name users will refer to\
    the context by
    :param context_graph: Optional path to an existing context startup graph
    :param exe_script_args: If the exe arg is not a Python interpreter \
    additional args may need to passed. For example in Blender its possible \
    to call the blender.exe with the arg `--python`. After the args the path \
    to the nxt cli module is inserted into the subprocess call.
    :type exe_script_args: list | tuple
    :raises: IOError, NameError
    :return: string of the new context name
    """
    _user_plugin_dir = USER_PLUGIN_DIR.replace(os.sep, '/')
    if not custom_name:
        raise NameError('Must provide a valid name for your context!')
    interpreter_exe = interpreter_exe.replace(os.sep, '/')
    default_context_graph = 'custom_{name}_context.nxt'.format(name=custom_name)
    default_c_path = os.path.abspath(os.path.join(_user_plugin_dir,
                                                  default_context_graph))
    default_c_path = default_c_path.replace(os.sep, '/')
    template_path = os.path.join(os.path.dirname(__file__),
                                 'remote/remote_context_template.py')
    with open(template_path, 'r') as fp:
        py_str = fp.read()

    context_py_file = 'custom_{name}_context.py'.format(name=custom_name)
    context_py_filepath = os.path.join(_user_plugin_dir, context_py_file)
    if os.path.exists(context_py_filepath):
        raise IOError('The context name you selected is already taken. '
                      '"{}"'.format(custom_name))
    if context_graph is None:
        context_graph = default_c_path
        file_name = 'custom_{name}_context.nxt'.format(name=custom_name)
        dest_path = os.path.join(_user_plugin_dir, file_name).replace(os.sep,
                                                                     '/')
        exe_name = contexts.get_current_context_exe_name()
        starter_context = contexts.starter_contexts.get(exe_name)
        if starter_context is None:
            fallback_exe_name = os.path.basename(interpreter_exe.lower())
            fallback_exe_name, _ = os.path.splitext(fallback_exe_name)
            starter_context = contexts.starter_contexts.get(fallback_exe_name)
        if starter_context:
            layer = nxt_layer.SpecLayer.load_from_filepath(starter_context)
        else:
            logger.warning('No prebuilt context was found for "{exe_name}", '
                           'if your interpreter needs special setup/teardown '
                           'please open "{dest_path}" and edit as needed.'
                           ''.format(exe_name=exe_name, dest_path=dest_path))
            layer = nxt_layer.SpecLayer()
            layer.add_reference(layer_path=contexts._context_graph)
        layer.set_alias('custom_{name}_context'.format(name=custom_name))
        layer.save(filepath=dest_path)
    else:
        expanded_context_graph = nxt_path.full_file_expand(context_graph)
        if not os.path.isfile(expanded_context_graph):
            raise IOError('The context graph you provided does not exist! '
                          '"{}"'.format(context_graph))
        root = os.path.commonprefix((context_graph, context_py_filepath))
        if root:
            context_graph = os.path.relpath(context_graph, root)
        context_graph.replace(os.sep, '/')

    py_str = py_str.format(name=custom_name, interpreter_exe=interpreter_exe,
                           context_graph=context_graph, args=exe_script_args)
    with open(context_py_filepath, 'w+') as fp:
        fp.write(py_str)
    exec(py_str)
    return custom_name
