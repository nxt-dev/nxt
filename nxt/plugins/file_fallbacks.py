# Builtin
import logging
import os
import unittest
import time

# Internal
from nxt.session import Session
from nxt import nxt_path, nxt_io
from nxt.tokens import (register_token, get_token_content,
                        get_standalone_tokens, make_token_str, TOKENTYPE)
from nxt.nxt_layer import CompLayer, get_active_layers
from nxt.nxt_node import get_node_path


logger = logging.getLogger('nxt')

FILEPATH_PREFIX = TOKENTYPE.FILE.prefix
FILE_LIST_PREFIX = 'filelist::'

NXT_FILE_ROOTS = 'NXT_FILE_ROOTS'
ROOT_PATH_SEP = ';'

INVALID_PATH = '<invalid>'


def detect_filepath_token(value):
    return value.startswith(FILEPATH_PREFIX)


def detect_file_list_token(value):
    return value.startswith(FILE_LIST_PREFIX)


def resolve_filepath_token(stage, node, cleaned, layer, **kwargs):
    """Custom resolver for `file::` tokens. Can resolve multiple file tokens
    in a single attr value. The initial raw value is NOT retrieved from the
    node again as fallbacks happen.
        If on layer_0 the attr value is
            ${file::${attr}}
        and on layer_1 the attr value is
            ${file::${foo}}
        This plugin will only fallback and resolve for the value:
              ${file::${attr}}
    This is a fallback resolver for the contents of the token, not the entire
    attr value!
    :param stage: Stage instance
    :param node: Node object
    :param cleaned: String of cleaned attr value (the outer file
    token has been stripped off).
    :param layer: Layer object
    :param kwargs: Not used but may be passed by the Stage
    :return: string of resolved file path
    """
    token = make_token_str(FILEPATH_PREFIX+cleaned)
    out_value = resolve_file_token_with_fallbacks(stage=stage,
                                                  comp_node=node,
                                                  value=token,
                                                  comp_layer=layer)
    return out_value


def resolve_filelist_token(stage, node, cleaned, layer, **kwargs):
    as_string = kwargs.get('as_string', True)
    token = make_token_str(FILE_LIST_PREFIX+cleaned)
    genny = resolve_file_list_token(stage=stage, comp_node=node,
                                    value=token, comp_layer=layer)
    file_list = list(genny)
    if as_string:
        return str(file_list)
    return file_list


def resolve_file_list_token(stage, comp_node, value, comp_layer):
    if not isinstance(comp_layer, CompLayer):
        logger.error('File list resolve requires a comp layer or a '
                     'sub-class of a comp layer!')
        return stage.resolve_file_token(comp_node, value, comp_layer)
    first, last = comp_layer._layer_range
    paths = generate_historical_values(first, last, value, stage,
                                       comp_node, comp_layer, file_list_token)
    return paths


def resolve_file_token_with_fallbacks(stage, comp_node, value, comp_layer):
    """Given a node, who's attr_name has a value only containing a file
    token we will fall back through all possible historical comps until
    we bottom out or find a valid file path.
    :param stage: Stage instance to resolve against
    :param comp_node: CompNode object
    :param value: string of attribute value
    :param comp_layer: CompLayer object
    :raises: TypeError
    :return: string of file path or empty string if no file found
    """
    start = time.time()
    if not isinstance(comp_layer, CompLayer):
        raise TypeError('Resolve with fallbacks requires a comp layer or a '
                        'sub-class of a comp layer!')
    first, last = comp_layer._layer_range
    paths = generate_historical_values(first, last, value, stage,
                                       comp_node, comp_layer, file_fallback_token)
    try:
        valid_path = next(paths)
    except StopIteration:
        valid_path = ''
    # resolve_time = str(int(round((time.time() - start) * 1000)))  # debugging
    return valid_path


def generate_historical_values(first, last, value, stage, comp_node,
                               comp_layer, token):
    seen = []
    for depth in range(first, last):
        requested_layers = stage._sub_layers[depth:last]
        # Early exit if there are no active layers in the requested range
        active_layers = get_active_layers(requested_layers)
        if not active_layers:
            continue
        historical_node = stage.infer_lower_comp(comp_node, comp_layer,
                                                 active_layers=active_layers,
                                                 depth=depth)
        resolved = historical_resolve_file_ref(stage, historical_node,
                                               value, comp_layer,
                                               active_layers,
                                               historical_depth=depth,
                                               token=token)
        if resolved and resolved not in seen:
            yield resolved
            seen += [resolved]


def historical_resolve_file_ref(stage, comp_node, value, comp_layer,
                                active_layers, token, historical_depth=0):
    """Attempts to resolve a file token in the attribute
    specified at the historical depth given. See `Stage.infer_lower_comp` for
    more details on comping at a historical depth. This method is not
    recursive, it only checks the exact historical depth provided.
    :param stage: Stage instance to resolve against
    :param comp_node: CompNode object
    :param value: string of attribute value
    :param comp_layer: CompLayer object
    :param active_layers: List of at least 1 active layer
    :param token: tokens.Token object
    :param historical_depth: number of layers to step back, relative to the
    comp layer, that the historical comp should be built at.
    :return: string of the resolved attribute value
    """
    resolved = value
    display_layer = active_layers[0]
    layer_dir = display_layer.get_cwd()
    all_tokens = get_standalone_tokens(value, token_types=(token,))
    # If no tokens are found we test if the val is a valid a valid path
    if not all_tokens and value:
        resolved = file_root_fallback(resolved, layer_dir=layer_dir)
    for full_token in all_tokens:
        token_content = get_token_content(full_token)
        string = token_content
        _, sep, raw = string.partition(token.prefix)
        resolved_token = historical_resolve_attr_ref(stage, raw, comp_node,
                                                     comp_layer, active_layers,
                                                     historical_depth)
        if not resolved_token and raw:
            resolved_token = INVALID_PATH
        resolved_fp = file_root_fallback(resolved_token, layer_dir=layer_dir)
        resolved = resolved.replace(full_token, resolved_fp)
    return resolved


def historical_resolve_attr_ref(stage, string, comp_node, comp_layer,
                                active_layers, historical_depth=0):
    """Attempts to resolve an attr ref token at the historical depth given.
    See `Stage.infer_lower_comp` for more details on comping at a historical
    depth. This method IS recursive, BUT only checks the exact historical
    depth provided.
    :param stage: Stage instance
    :param string: Attr value string containing 1 or more attr ref tokens.
    :param comp_node: CompNode object
    :param comp_layer: CompLayer object
    :param active_layers: list of active layers
    :param historical_depth: number of layers to step back, relative to the
    comp layer, that the historical comp should be built at.
    :return: string of the resolved attribute token
    """
    tokens = stage.get_tokens_from(string, token_type=TOKENTYPE.ATTR)
    resolved_token = string
    for attr_token in tokens:
        attr_ref = get_token_content(attr_token)
        ref_path, ref_attr_name = nxt_path.path_attr_partition(attr_ref)
        if ref_path and ref_attr_name:
            attr_name = ref_attr_name
            source_path = ref_path
        else:
            attr_name = attr_ref
            source_path = get_node_path(comp_node)
        # If this attr ref is to another node, go there and get the value
        if source_path:
            node_path = get_node_path(comp_node)
            source_path = nxt_path.expand_relative_node_path(source_path,
                                                             node_path)
        source_node = comp_layer.lookup(source_path)
        historical_node = stage.infer_lower_comp(source_node, comp_layer,
                                                 active_layers,
                                                 historical_depth)

        value = getattr(historical_node, attr_name, None) or ''
        more = get_standalone_tokens(value, token_types=(TOKENTYPE.ATTR,
                                                         file_fallback_token))
        for token_content in more:
            token = stage.determine_token_type(get_token_content(token_content))
            if token == TOKENTYPE.ATTR:
                value = historical_resolve_attr_ref(stage, value, comp_node,
                                                    comp_layer,
                                                    active_layers,
                                                    historical_depth)
            elif token == file_fallback_token:
                value = historical_resolve_file_ref(stage, comp_node,
                                                    token_content, comp_layer,
                                                    active_layers,
                                                    token,
                                                    historical_depth)
        raw_token = make_token_str(attr_ref)
        resolved_token = resolved_token.replace(raw_token, value)
    return resolved_token


def iter_env_roots(only_exsiting=True):
    if NXT_FILE_ROOTS not in os.environ:
        return
    if NXT_FILE_ROOTS in os.environ:
        for root in os.environ.get(NXT_FILE_ROOTS).split(ROOT_PATH_SEP):
            if only_exsiting and not os.path.exists(root):
                continue
            yield root


def file_root_fallback(filepath, layer_dir=None):
    """Test a given filepath against the list of possible root paths
    specified in the env var NXT_FILE_ROOTS.
    :param filepath: string of file path
    :param layer_dir: optional layer dir to be tested after all possible
    roots fail.
    :return: string of valid filepath or empty string
    """
    for root in iter_env_roots():
        full_path = nxt_path.full_file_expand(filepath, start=root)
        if os.path.exists(full_path):
            return full_path
    if layer_dir and os.path.exists(layer_dir):
        full_path = nxt_path.full_file_expand(filepath, start=layer_dir)
        if os.path.exists(full_path):
            return full_path
    return ''


nxt_io.register_reference_path_expander(file_root_fallback)


file_fallback_token = register_token(FILEPATH_PREFIX, detect_filepath_token,
                                     resolve_filepath_token)

file_list_token = register_token(FILE_LIST_PREFIX, detect_file_list_token,
                                 resolve_filelist_token)


def detect_path_token(value):
    return value.startswith(TOKENTYPE.FILEPATH.prefix)


def resolve_path_token_in_roots(stage, node, cleaned, layer, **kwargs):
    value = stage.resolve(node, cleaned, layer)
    try:
        root = next(iter_env_roots())
    except StopIteration:
        layer_cwd = layer.get_cwd()
        if os.path.exists(layer_cwd):
            root = layer_cwd
        else:
            root = os.getcwd()
    return nxt_path.full_file_expand(value, start=root)


roots_path_token = register_token(TOKENTYPE.FILEPATH.prefix, detect_path_token,
                                  resolve_path_token_in_roots)


# UNITTESTS
# Fixme: putting these here until we can make plugins packages
