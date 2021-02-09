# Builtin
import os

# External
from nxt.remote.contexts import RemoteContext, register_context

# Setup Context
_name = '{name}'
_exe = '{interpreter_exe}'
_graph = '{context_graph}'
_args = {args}
_context = RemoteContext(_name, _exe, _graph, _args)
register_context(_context)
