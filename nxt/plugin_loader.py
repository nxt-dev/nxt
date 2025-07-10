# Built-in
import os
import importlib.util
import logging

# Internal
from .constants import PLUGIN_DIRS

_nxt_loaded_plugin_module_names = []
_nxt_loaded_plugin_modules = []

logger = logging.getLogger('nxt.plugins')


def load_plugins():
    global _nxt_loaded_plugin_module_names
    global _nxt_loaded_plugin_modules
    logger.info('Loading plugins.')
    for plugin_dir in PLUGIN_DIRS:
        if not os.path.isdir(plugin_dir):
            continue
        for file_name in os.listdir(plugin_dir):
            mod_name, _ = os.path.splitext(file_name)
            if mod_name in _nxt_loaded_plugin_module_names:
                continue
            mod_path = os.path.join(plugin_dir, file_name)
            spec = importlib.util.spec_from_file_location(mod_name, mod_path)
            if not spec:
                continue
            mod = importlib.util.module_from_spec(spec)
            _nxt_loaded_plugin_module_names += [mod_name]
            _nxt_loaded_plugin_modules += [mod]
            spec.loader.exec_module(mod)
