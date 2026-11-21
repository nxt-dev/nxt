"""Compositing worked out as data, then built in one go.

Stage.build_stage composites by building node classes and changing their
base classes as it goes, so every change has Python work out the method
resolution order again for the class and everything inheriting from it. On
a big graph that is most of the time a comp takes.

This does the same comp on plain data: a class here is a dict and a list of
bases, attribute lookups follow a C3 MRO worked out the way Python does, and
the comp layer's tables, child caches and dirty map are kept the way
CompLayer keeps them. Each step mirrors the Stage method it is named after,
in the same order, so the result is the same, down to the order nodes were
added and the order of every cache. Only at the end are the classes made,
each once, with the bases it ends up with, and handed to the comp layer.

Anything this does not expect -- a base class change Python would refuse,
say -- raises Fallback, and the caller composites the old way instead, so
even a comp that fails fails the same way.
"""
import copy
import logging

from nxt import nxt_path
from nxt.nxt_node import (INTERNAL_ATTRS, META_ATTRS, CompNode, SpecNode,
                          list_merger, has_opinion)
from nxt.nxt_layer import LayerReturnTypes

logger = logging.getLogger('nxt.stage')

OBJECT = -1
_MISSING = object()


class Fallback(Exception):
    """The comp needs something this does not do; composite the old way."""


def _arcs():
    from nxt.stage import CompArc
    return CompArc


class Plan(object):
    """One comp, worked out as data. See the module docstring."""

    def __init__(self, stage, comp_layer, strict=False):
        self.stage = stage
        self.comp_layer = comp_layer
        # Check every class inheriting from one whose bases change, the way
        # Python does when bases are set, rather than only those looked at.
        self.strict = strict
        # Classes. Python classes that already exist (spec nodes, Node) keep
        # their own MRO; the ones made here are worked out.
        self.dicts = []
        self.bases = []
        self.kind = []  # 'py', 'spec' (made here) or 'comp'
        self.pyclass = []
        self.initial = []  # attrs a class was made with
        self.subclasses = []
        self.fixed_mro = []
        self.mro_cache = {}
        self.py_ids = {}
        # Calls made on real layers, replayed once the comp is built.
        self.layer_calls = []
        self.logs = []
        # The comp layer, as CompLayer keeps it.
        self.path_key = {}
        self.node_key = {}
        self.node_table = []
        self.cached_children = {}
        self.cached_implied = {}
        self.bulk_valid = False
        self.implied_index = {}
        self.implied_valid = False
        self.implied_len = -1
        self.dirty_map = {}
        self.real_path = comp_layer.real_path

    # Classes ---------------------------------------------------------------

    def py(self, cls):
        """The id of an existing Python class."""
        key = id(cls)
        cid = self.py_ids.get(key)
        if cid is not None:
            return cid
        if cls is object:
            return OBJECT
        cid = len(self.dicts)
        self.py_ids[key] = cid
        self.dicts.append(cls.__dict__)
        self.bases.append(None)
        self.kind.append('py')
        self.pyclass.append(cls)
        self.initial.append(None)
        self.subclasses.append(set())
        self.fixed_mro.append(None)
        self.fixed_mro[cid] = tuple(self.py(c) for c in cls.__mro__)
        return cid

    def new_class(self, kind, bases, attrs):
        cid = len(self.dicts)
        self.dicts.append(dict(attrs))
        self.bases.append(list(bases))
        self.kind.append(kind)
        self.pyclass.append(None)
        self.initial.append(dict(attrs))
        self.subclasses.append(set())
        self.fixed_mro.append(None)
        for base in bases:
            if base != OBJECT:
                self.subclasses[base].add(cid)
        self.mro(cid)  # Python works it out as the class is made.
        return cid

    def mro(self, cid):
        if cid == OBJECT:
            return (OBJECT,)
        fixed = self.fixed_mro[cid]
        if fixed is not None:
            return fixed
        cached = self.mro_cache.get(cid)
        if cached is not None:
            return cached
        result = self._c3(cid)
        self.mro_cache[cid] = result
        return result

    def _c3(self, cid):
        bases = self.bases[cid]
        if len(set(bases)) != len(bases):
            raise Fallback('duplicate base class')
        seqs = [list(self.mro(b)) for b in bases] + [list(bases)]
        result = [cid]
        while True:
            seqs = [s for s in seqs if s]
            if not seqs:
                return tuple(result)
            for seq in seqs:
                head = seq[0]
                if not any(head in s[1:] for s in seqs):
                    break
            else:
                raise Fallback('inconsistent method resolution order')
            result.append(head)
            for s in seqs:
                if s[0] == head:
                    del s[0]

    def set_bases(self, cid, new_bases):
        """cls.__bases__ = new_bases, as Python checks and does it."""
        new_bases = list(new_bases)
        if not new_bases:
            raise Fallback('empty bases')
        for base in new_bases:
            if base != OBJECT and cid in self.mro(base):
                raise Fallback('inheritance cycle')
        old = self.bases[cid]
        for base in old:
            if base != OBJECT:
                self.subclasses[base].discard(cid)
        self.bases[cid] = new_bases
        for base in new_bases:
            if base != OBJECT:
                self.subclasses[base].add(cid)
        self._forget_mro(cid)
        try:
            self.mro(cid)
            if self.strict:
                self._check_subclasses(cid)
        except Fallback:
            raise

    def _forget_mro(self, cid):
        stack = [cid]
        seen = set()
        while stack:
            c = stack.pop()
            if c in seen:
                continue
            seen.add(c)
            self.mro_cache.pop(c, None)
            stack.extend(self.subclasses[c])

    def _check_subclasses(self, cid):
        for sub in self.subclasses[cid]:
            self.mro(sub)
            self._check_subclasses(sub)

    def getattr(self, cid, attr, default=_MISSING):
        if cid is None:
            if default is _MISSING:
                raise AttributeError(attr)
            return default
        for c in self.mro(cid):
            if c == OBJECT:
                continue
            d = self.dicts[c]
            if attr in d:
                return d[attr]
        if default is _MISSING:
            raise AttributeError(attr)
        return default

    def setattr(self, cid, attr, value):
        if self.kind[cid] == 'py':
            raise Fallback('setting an attr on an existing class')
        self.dicts[cid][attr] = value

    def opinion(self, cid, attr):
        value = self.getattr(cid, attr, None)
        return value, has_opinion(value)

    def name(self, cid):
        return self.getattr(cid, INTERNAL_ATTRS.NAME)

    def is_comp(self, cid):
        return self.kind[cid] == 'comp'

    # The comp layer, as CompLayer keeps it ---------------------------------

    def lookup(self, path):
        return self.path_key.get(path)

    def get_node_path(self, cid):
        return self.node_key.get(cid)

    def get_node_dirties(self, node_path):
        concerns = self.dirty_map.get(node_path, [])[:]
        new_concerns = [node_path] + concerns
        while new_concerns:
            tmp = []
            for concern in new_concerns:
                for item in self.dirty_map.get(concern, []):
                    if item not in concerns + tmp:
                        tmp += [item]
            new_concerns = tmp
            concerns += tmp
        return concerns

    def extend_dirty_map(self, node_path, concern):
        world = nxt_path.WORLD
        if node_path is world or concern is world:
            return
        node_concerns = self.dirty_map.get(node_path, [])
        if not node_concerns:
            self.dirty_map[node_path] = node_concerns
        if concern is not node_path and concern not in node_concerns:
            node_concerns += [concern]

    @staticmethod
    def _entry():
        return {'nodes': [], 'paths': [], 'table': [], 'names': {}}

    def clear_node_child_cache(self, parent_path):
        self.bulk_valid = False
        self.implied_valid = False
        self.cached_children.pop(parent_path, None)
        self.cached_implied.pop(parent_path, None)

    def add_child_to_child_cache(self, parent_path, child_path, child):
        if not parent_path or parent_path == nxt_path.WORLD:
            return
        cache = self.cached_children.get(parent_path)
        if cache is not None:
            entry = {'nodes': cache['nodes'][:], 'paths': cache['paths'][:],
                     'table': cache['table'][:],
                     'names': copy.copy(cache['names'])}
        else:
            entry = self._entry()
        entry['nodes'] += [child]
        entry['paths'] += [child_path]
        entry['table'] += [[child_path, child]]
        entry['names'][self.name(child)] = child
        self.cached_children[parent_path] = entry

    def remove_child_from_child_cache(self, parent_path, child_path, child):
        if parent_path is nxt_path.WORLD:
            return
        cache = self.cached_children.get(parent_path)
        if cache is None:
            return
        if child in cache['nodes']:
            cache['nodes'].remove(child)
        if child_path in cache['paths']:
            cache['paths'].remove(child_path)
        if [child_path, child] in cache['table']:
            cache['table'].remove([child_path, child])
        cache['names'].pop(self.name(child), None)

    def _build_child_cache(self):
        cache = {}
        for path in self.path_key:
            if path != nxt_path.WORLD:
                cache[path] = self._entry()
        for path, node in self.path_key.items():
            parent_path = self.getattr(node, INTERNAL_ATTRS.PARENT_PATH)
            if not parent_path or parent_path == nxt_path.WORLD:
                continue
            entry = cache.get(parent_path)
            if entry is None:
                entry = self._entry()
                cache[parent_path] = entry
            entry['nodes'] += [node]
            entry['paths'] += [path]
            entry['table'] += [[path, node]]
            entry['names'][self.name(node)] = node
        self.cached_children = cache
        self.bulk_valid = True

    def _build_implied_index(self):
        index = {}
        seen = {}
        sep = nxt_path.NODE_SEP
        for path in self.path_key:
            if path == nxt_path.WORLD:
                continue
            parts = path.split(sep)
            for depth in range(1, len(parts) - 1):
                ancestor = sep.join(parts[:depth + 1])
                trimmed = sep.join(parts[:depth + 2])
                bucket = index.get(ancestor)
                if bucket is None:
                    index[ancestor] = bucket = []
                    seen[ancestor] = set()
                if trimmed not in seen[ancestor]:
                    seen[ancestor].add(trimmed)
                    bucket += [trimmed]
        self.implied_index = index
        self.implied_len = len(self.path_key)
        self.implied_valid = True

    def _implied_children_for(self, node_path):
        if (not self.implied_valid
                or self.implied_len != len(self.path_key)):
            self._build_implied_index()
        return self.implied_index.get(node_path, [])[:]

    def children(self, node_path=nxt_path.WORLD, return_type='paths',
                 include_implied=False):
        """CompLayer.children, unordered, returning 'paths' or 'names'."""
        world = nxt_path.WORLD
        if not node_path:
            return {} if return_type == 'names' else []
        children_nodes = []
        children_paths = []
        node_table = []
        name_dict = {}
        implied_children = []
        cache = self.cached_children.get(node_path)
        if node_path == world:
            cache = None
        elif cache is None and not self.bulk_valid:
            self._build_child_cache()
            cache = self.cached_children.get(node_path)
        if cache is not None:
            children_nodes = cache['nodes'][:]
            children_paths = cache['paths'][:]
            node_table = cache['table'][:]
            name_dict = copy.copy(cache['names'])
            cache_real = False
        else:
            self.cached_children[node_path] = {
                'nodes': children_nodes, 'paths': children_paths,
                'table': node_table, 'names': name_dict}
            cache_real = True
        cache_implied = False
        if include_implied:
            if node_path is world:
                implied_cache = None
            else:
                implied_cache = self.cached_implied.get(node_path)
            if implied_cache is not None:
                implied_children = implied_cache['paths'][:]
            elif node_path is not world:
                implied_children = self._implied_children_for(node_path)
                self.cached_implied[node_path] = {'paths': implied_children}
            else:
                self.cached_implied[node_path] = {'paths': implied_children}
                cache_implied = True
        if cache_implied or cache_real:
            node_path_is_world = node_path is world
            ancestor_prefix = node_path + nxt_path.NODE_SEP
            trim_depth = nxt_path.get_path_depth(node_path) + 1
            seen_implied = set()
            trim = nxt_path.trim_to_depth
            for path, node in self.path_key.items():
                if cache_real:
                    parent_path = self.getattr(node,
                                               INTERNAL_ATTRS.PARENT_PATH)
                    if parent_path == node_path:
                        children_nodes += [node]
                        children_paths += [path]
                        node_table += [[path, node]]
                        name_dict[self.name(node)] = node
                if not include_implied or not cache_implied:
                    continue
                if not node_path_is_world:
                    if not path.startswith(ancestor_prefix):
                        continue
                trimmed = trim(path, trim_depth)
                if trimmed not in seen_implied:
                    seen_implied.add(trimmed)
                    implied_children += [trimmed]
        if cache_real:
            self.cached_children[node_path]['paths'] = children_paths[:]
        if include_implied:
            for imp in implied_children:
                if imp not in children_paths:
                    children_paths += [imp]
        if return_type == 'names':
            return name_dict
        return children_paths

    # Stage helpers ---------------------------------------------------------

    def add_node_to_comp_layer(self, path, comp_node, ns=None,
                               add_to_child_order=True):
        if not self.is_comp(comp_node):
            comp_node = self.new_class('comp', [comp_node], {})
        if ns is None:
            ns = nxt_path.str_path_to_node_namespace(path)
        name = self.name(comp_node)
        self.node_table += [[ns, comp_node]]
        self.path_key[path] = comp_node
        self.node_key[comp_node] = path
        parent_node = None
        parent_path = self.getattr(comp_node, INTERNAL_ATTRS.PARENT_PATH)
        self.add_child_to_child_cache(parent_path, path, comp_node)
        if add_to_child_order:
            parent_node = self.lookup(parent_path)
        if parent_node is not None:
            child_order = self.getattr(parent_node,
                                       INTERNAL_ATTRS.CHILD_ORDER)
            if name not in child_order:
                self.setattr(parent_node, INTERNAL_ATTRS.CHILD_ORDER,
                             list_merger(child_order, [name]))
        return comp_node

    def remove_node_from_comp_layer(self, path, comp_node, ns=None):
        # Builds only ever pass rm_from_child_order=False and
        # rm_layer_data=False.
        if not self.is_comp(comp_node):
            raise Fallback('removing a node that is not a comp node')
        if ns is None:
            ns = nxt_path.str_path_to_node_namespace(path)
        parent_path = self.getattr(comp_node, INTERNAL_ATTRS.PARENT_PATH)
        self.node_table.remove([ns, comp_node])
        self.path_key.pop(path)
        self.node_key.pop(comp_node)
        self.clear_node_child_cache(path)
        self.remove_child_from_child_cache(parent_path, path, comp_node)

    def create_spec_node(self, node_data, layer, parent_path=nxt_path.WORLD,
                         is_proxy=False):
        """nxt_node.create_spec_node, making a class here. layer is the comp
        layer (this plan) or a real layer."""
        attrs = {}
        node_name = node_data[INTERNAL_ATTRS.as_save_key(INTERNAL_ATTRS.NAME)]
        layer_real_path = self.real_path if layer is self else layer.real_path
        path = nxt_path.join_node_paths(parent_path, node_name)
        if node_data.get('attrs'):
            raise Fallback('proxy spec data with user attrs')
        for attr in INTERNAL_ATTRS.ALL:
            key = INTERNAL_ATTRS.as_save_key(attr)
            val = node_data.get(key)
            if (not has_opinion(val) and attr not in
                    INTERNAL_ATTRS.ALLOW_NO_OPINION):
                val = INTERNAL_ATTRS.DEFAULTS.get(attr)
                if callable(val):
                    val = val()
            attrs[attr] = val
        child_order = []
        for c in node_data.get('child_order', []):
            if c not in child_order:
                child_order += [c]
        attrs.update({INTERNAL_ATTRS.NAME: node_name,
                      INTERNAL_ATTRS.PROXY: is_proxy,
                      INTERNAL_ATTRS.CHILD_ORDER: child_order,
                      INTERNAL_ATTRS.SOURCE_LAYER: layer_real_path})
        pp_key = INTERNAL_ATTRS.as_save_key(INTERNAL_ATTRS.PARENT_PATH)
        if is_proxy:
            attrs[INTERNAL_ATTRS.PARENT_PATH] = (node_data.get(pp_key) or
                                                 parent_path)
        else:
            attrs[INTERNAL_ATTRS.PARENT_PATH] = parent_path
        node_spec = self.new_class('spec', [self.py(_Node())], attrs)
        if layer is self:
            parent_object = self.lookup(parent_path)
            self.clear_node_child_cache(path)
            self.clear_node_child_cache(parent_path)
            if parent_object is not None:
                proxies = (self.getattr(node_spec, INTERNAL_ATTRS.PROXY) or
                           self.getattr(parent_object, INTERNAL_ATTRS.PROXY))
                co = self.getattr(parent_object, INTERNAL_ATTRS.CHILD_ORDER)
                if node_name not in co and not proxies:
                    self.setattr(parent_object, INTERNAL_ATTRS.CHILD_ORDER,
                                 list_merger(co, [node_name]))
        else:
            parent_object = layer.lookup(parent_path)
            self.layer_calls.append((layer, path))
            self.layer_calls.append((layer, parent_path))
            if parent_object is not None:
                proxies = (is_proxy or
                           getattr(parent_object, INTERNAL_ATTRS.PROXY))
                co = getattr(parent_object, INTERNAL_ATTRS.CHILD_ORDER)
                if node_name not in co and not proxies:
                    raise Fallback('a proxy spec changing a real layer')
        for attr in INTERNAL_ATTRS.TRACKED:
            self.setattr(node_spec, attr + META_ATTRS.SOURCE,
                         (layer_real_path, path))
        return node_spec

    # The comp ----------------------------------------------------------------

    def comp_pre_proxies(self, sublayer_node_tables):
        node_count = 0
        base_mapping = {}
        for table in sublayer_node_tables:
            for namespace, spec_node in table:
                spec = self.py(spec_node)
                path = nxt_path.node_namespace_to_str_path(namespace)
                stronger_match = self.lookup(path)
                bases = base_mapping.get(path, [])
                bases += [spec]
                if stronger_match is not None:
                    continue
                attrs = {INTERNAL_ATTRS.NAME: self.name(spec)}
                comp_node = self.new_class('comp', [spec], attrs)
                self.add_node_to_comp_layer(path, comp_node, ns=namespace,
                                            add_to_child_order=False)
                base_mapping[path] = bases
                node_count += 1
        overload = set(_arcs().INHERITANCE_MAP[_arcs().REFERENCE] +
                       INTERNAL_ATTRS.TRACKED)
        for path, bases in base_mapping.items():
            comp_node = self.lookup(path)
            if bases != self.bases[comp_node]:
                self.set_bases(comp_node, bases)
            idx = 0
            for spec in reversed(bases):
                if idx == 0:
                    self.setattr(comp_node, INTERNAL_ATTRS.CHILD_ORDER,
                                 self.getattr(spec,
                                              INTERNAL_ATTRS.CHILD_ORDER))
                for attr in overload:
                    value, has = self.opinion(spec, attr)
                    if has:
                        src_layer = self.getattr(spec,
                                                 INTERNAL_ATTRS.SOURCE_LAYER)
                        self.setattr(comp_node, attr, value)
                        self.setattr(comp_node, attr + META_ATTRS.SOURCE,
                                     (src_layer, path))
                idx += 1
                if path == nxt_path.WORLD:
                    continue
                spec_co = self.getattr(spec, INTERNAL_ATTRS.CHILD_ORDER)
                comp_co = self.getattr(comp_node, INTERNAL_ATTRS.CHILD_ORDER)
                self.setattr(comp_node, INTERNAL_ATTRS.CHILD_ORDER,
                             list_merger(spec_co, comp_co))
        return node_count

    def create_instance_node(self, source_path, tgt_path, new_tgt_ns=None):
        implied = False
        force_source_layer = False
        if new_tgt_ns is None:
            new_tgt_ns = nxt_path.str_path_to_node_namespace(tgt_path)
        inst_source = self.lookup(source_path)
        if inst_source is None:
            node_name = nxt_path.node_name_from_node_path(source_path)
            data = {INTERNAL_ATTRS.as_save_key(INTERNAL_ATTRS.NAME): node_name}
            inst_pp = nxt_path.get_parent_path(source_path)
            inst_parent = self.lookup(inst_pp)
            p_inst = self.getattr(inst_parent, INTERNAL_ATTRS.INSTANCE_PATH,
                                  None)
            inst_children = self.children(p_inst, return_type='names')
            inst_source = self.create_spec_node(data, self,
                                                parent_path=inst_pp)
            if node_name in inst_children:
                force_source_layer = True
            else:
                implied = True
        target_parent_path = nxt_path.get_parent_path(tgt_path)
        existing = self.lookup(tgt_path)
        layer = self.stage.lookup_layer(
            self.getattr(inst_source, INTERNAL_ATTRS.SOURCE_LAYER))
        if layer is None:
            raise Fallback('instance source layer not in the stage')
        if existing is None:
            save = INTERNAL_ATTRS.as_save_key
            i_dat = {
                save(INTERNAL_ATTRS.NAME): self.getattr(
                    inst_source, INTERNAL_ATTRS.NAME),
                save(INTERNAL_ATTRS.COMMENT): self.getattr(
                    inst_source, INTERNAL_ATTRS.COMMENT),
                save(INTERNAL_ATTRS.ENABLED): self.getattr(
                    inst_source, INTERNAL_ATTRS.ENABLED),
                save(INTERNAL_ATTRS.SOURCE_LAYER): self.getattr(
                    inst_source, INTERNAL_ATTRS.SOURCE_LAYER),
                save(INTERNAL_ATTRS.PARENT_PATH): target_parent_path,
            }
            spec = self.create_spec_node(i_dat, layer,
                                         parent_path=target_parent_path,
                                         is_proxy=True)
            new_target = self.new_class('comp', [spec], {})
            self.add_node_to_comp_layer(tgt_path, new_target, ns=new_tgt_ns)
            parent_node = self.lookup(target_parent_path)
            parent_layer = self.getattr(parent_node,
                                        INTERNAL_ATTRS.SOURCE_LAYER)
            if force_source_layer:
                self.setattr(new_target, INTERNAL_ATTRS.SOURCE_LAYER,
                             parent_layer)
            self.setattr(new_target, INTERNAL_ATTRS.INSTANCE_PATH,
                         source_path)
            self.setattr(new_target,
                         INTERNAL_ATTRS.INSTANCE_PATH + META_ATTRS.SOURCE,
                         (parent_layer, source_path))
        else:
            new_target = existing
            self.setattr(existing, INTERNAL_ATTRS.INSTANCE_PATH, source_path)
            self.setattr(existing,
                         INTERNAL_ATTRS.INSTANCE_PATH + META_ATTRS.SOURCE,
                         (layer.real_path, source_path))
        self.extend_dirty_map(source_path, tgt_path)
        if not implied:
            return new_target
        return False

    def log(self, level, *args, **kwargs):
        self.logs.append((level, args, kwargs))

    def discover_proxies(self, node_path, comp_node, namespace=None):
        to_do = []
        if not namespace:
            namespace = nxt_path.str_path_to_node_namespace(node_path)
        instance_path = self.getattr(comp_node, INTERNAL_ATTRS.INSTANCE_PATH,
                                     None)
        if not instance_path:
            return to_do
        if instance_path is nxt_path.WORLD:
            self.log('error', 'Invalid instance path on {}'.format(node_path),
                     links=[node_path])
            return to_do
        real_inst_path = nxt_path.expand_relative_node_path(instance_path,
                                                            node_path)
        if node_path.startswith(real_inst_path + nxt_path.NODE_SEP):
            self.log('error', '{} attempted to instance an ancestor!'
                     ''.format(node_path), links=[node_path])
            return to_do
        dirties = self.get_node_dirties(node_path)
        if real_inst_path in dirties:
            self.log('error', '{} attempted to instance dependant!'
                     ''.format(node_path), links=[node_path])
            return to_do
        self.setattr(comp_node, INTERNAL_ATTRS.INSTANCE_PATH, real_inst_path)
        self.extend_dirty_map(real_inst_path, node_path)
        if real_inst_path in self.path_key:
            inst_source = self.lookup(real_inst_path)
            comp_co = self.getattr(comp_node, INTERNAL_ATTRS.CHILD_ORDER)
            inst_co = self.getattr(inst_source, INTERNAL_ATTRS.CHILD_ORDER)
            self.setattr(comp_node, INTERNAL_ATTRS.CHILD_ORDER,
                         list_merger(comp_co, inst_co))
        for child_src_path in self.children(real_inst_path, 'paths',
                                            include_implied=True):
            c_ns = nxt_path.str_path_to_node_namespace(child_src_path)
            target_ns = namespace + [c_ns[-1]]
            tgt_path = nxt_path.node_namespace_to_str_path(target_ns)
            target = self.lookup(tgt_path)
            if target is not None:
                ex_inst_path = self.getattr(target,
                                            INTERNAL_ATTRS.INSTANCE_PATH, None)
                if ex_inst_path != '':
                    self.setattr(target, INTERNAL_ATTRS.INSTANCE_PATH,
                                 child_src_path)
            else:
                to_do += [(target_ns, child_src_path, tgt_path)]
        to_do.sort(key=lambda item: len(item[0]))
        return to_do

    def find_instance_cycle(self, node_path, comp_node):
        chain = [node_path]
        node, path = comp_node, node_path
        while True:
            inst_path = self.getattr(node, INTERNAL_ATTRS.INSTANCE_PATH, None)
            if not inst_path or inst_path is nxt_path.WORLD:
                return None
            inst_path = nxt_path.expand_relative_node_path(inst_path, path)
            closes = (inst_path == node_path or
                      nxt_path.is_ancestor(node_path, inst_path))
            if closes and len(chain) == 1 and inst_path != node_path:
                return None
            if closes:
                return chain + [inst_path]
            if inst_path in chain:
                return None
            node = self.lookup(inst_path)
            if node is None:
                return None
            chain += [inst_path]
            path = inst_path

    def break_instance_cycles(self):
        for _, comp_node in list(self.node_table):
            if not self.getattr(comp_node, INTERNAL_ATTRS.INSTANCE_PATH, None):
                continue
            node_path = self.get_node_path(comp_node)
            chain = self.find_instance_cycle(node_path, comp_node)
            if not chain:
                continue
            msg = 'Circular instance: {}. Ignoring the instance path on {}.'
            self.log('error', msg.format(' -> '.join(chain), node_path),
                     links=[node_path])
            self.setattr(self.lookup(node_path),
                         INTERNAL_ATTRS.INSTANCE_PATH, None)

    def get_instance_sources(self, node, trace):
        try:
            inst_path = self.getattr(node, INTERNAL_ATTRS.INSTANCE_PATH)
        except AttributeError:
            return trace
        n = self.lookup(inst_path) if inst_path is not None else None
        if inst_path is not None and not isinstance(inst_path, str):
            raise Fallback('instance path is not a string')
        if n is not None and n not in trace:
            trace += [n]
            self.get_instance_sources(n, trace)
        return trace

    def instance_is_possible(self, node_path, comp_node):
        instance_path = self.getattr(comp_node, INTERNAL_ATTRS.INSTANCE_PATH,
                                     None)
        if not instance_path:
            return None
        if instance_path is nxt_path.WORLD:
            self.log('error', 'Invalid instance path on {}'.format(node_path),
                     links=[node_path])
            return None
        real_inst_path = nxt_path.expand_relative_node_path(instance_path,
                                                            node_path)
        if node_path.startswith(real_inst_path + nxt_path.NODE_SEP):
            self.log('error', '{} attempted to instance an ancestor!'
                     ''.format(node_path), links=[node_path])
            return None
        if real_inst_path in self.get_node_dirties(node_path):
            self.log('error', '{} attempted to instance dependant!'
                     ''.format(node_path), links=[node_path])
            return None
        return real_inst_path

    def sort_instances(self, deep_sort=False):
        items = []
        src = {}
        for _, node in self.node_table:
            trace = self.get_instance_sources(node, [])
            item = (trace, node)
            src[self.get_node_path(node)] = item
            items += [item]
        items.sort(key=lambda item: len(item[0]))
        if not deep_sort:
            return items
        ranked = list(items)
        offsets = {}
        for item in items:
            node = item[1]
            node_path = self.get_node_path(node)
            real_inst_path = self.instance_is_possible(node_path, node)
            src_item = src.get(real_inst_path)
            if src_item:
                idx = _index_of(ranked, src_item)
                offset = offsets.get(real_inst_path, 1)
                ranked.pop(_index_of(ranked, item))
                ranked.insert(idx + offset, item)
                offsets[real_inst_path] = offset + 1
        return ranked

    def comp_proxies(self, node_count):
        new_node_count = -1
        proxy_count = 0
        loops = 0
        implied_proxies = []
        while node_count != new_node_count:
            new_node_count = node_count
            loops += 1
            added = 0
            to_do = []
            self.break_instance_cycles()
            for _, comp_node in self.sort_instances(deep_sort=True):
                node_path = self.get_node_path(comp_node)
                namespace = nxt_path.str_path_to_node_namespace(node_path)
                to_do += self.discover_proxies(node_path, comp_node,
                                               namespace=namespace)
            for new_tgt_ns, new_source_path, new_tgt_path in to_do:
                new = self.create_instance_node(new_source_path, new_tgt_path,
                                                new_tgt_ns)
                if not new:
                    implied_proxies += [(self.lookup(new_tgt_path),
                                         new_tgt_path, new_tgt_ns)]
                node_count += 1
                added += 1
            proxy_count += added
        for implied_proxy, implied_path, ns in implied_proxies:
            proxy_count -= 1
            self.remove_node_from_comp_layer(implied_path, implied_proxy,
                                             ns=ns)
        return proxy_count, loops

    def add_base_class(self, comp_node, base):
        if base is None:
            self.log('error', 'Invalid baseclass provided!')
            return
        self.set_bases(comp_node, self.bases[comp_node] + [base])

    def replace_base_classes(self, comp_node, bases):
        if None in bases:
            raise Fallback('invalid base classes')
        if list(bases) != self.bases[comp_node]:
            self.set_bases(comp_node, bases)

    def safe_mro_add_base_class(self, comp_node, base):
        current = self.bases[comp_node]
        if base in current:
            return
        incoming = self.bases[base] if self.kind[base] != 'py' else \
            [self.py(b) for b in self.pyclass[base].__bases__]
        safe = list(current)
        changed = False
        for c in current:
            for b in incoming:
                if c in self.mro(b) and c in safe:
                    safe.remove(c)
                    changed = True
        if changed:
            self.replace_base_classes(comp_node, tuple(safe) + (base,))
        else:
            self.add_base_class(comp_node, base)

    def post_proxy_comp(self):
        roots = []
        root_count = 0
        total_count = 0
        arc_idx = 0
        world = nxt_path.WORLD
        sorted_nodes = self.sort_instances()
        for arc in _arcs().POST_PROXY_ARCS:
            overload_attrs = _arcs().INHERITANCE_MAP[arc]
            parent_bases = []
            for _, comp_node in sorted_nodes:
                base_path = None
                node_path = self.get_node_path(comp_node)
                if arc is _arcs().PARENT:
                    parent_path = self.getattr(comp_node,
                                               INTERNAL_ATTRS.PARENT_PATH)
                    if not parent_path:
                        continue
                    if self.lookup(parent_path) is None:
                        while parent_path != world:
                            parent_path = nxt_path.get_parent_path(
                                parent_path)
                            if self.lookup(parent_path) is not None:
                                break
                    base_path = parent_path
                elif arc is _arcs().INSTANCE:
                    try:
                        base_path = self.getattr(comp_node,
                                                 INTERNAL_ATTRS.INSTANCE_PATH)
                    except AttributeError:
                        continue
                    if base_path == world:
                        continue
                base = self.path_key.get(base_path)
                if base is None:
                    if base_path and base_path is not world:
                        self.log('error', 'Unable to find {} node for {}'
                                 ''.format(arc, node_path), links=[node_path])
                        cur_node_path = self.node_key[comp_node]
                        real_path = nxt_path.expand_relative_node_path(
                            base_path, cur_node_path)
                        real = ('| ({})'.format(real_path)
                                if real_path != base_path else '')
                        # Three values for two places, as in Stage.
                        self.log('debug', 'requested {} {}'.format(
                            arc, base_path, real))
                    continue
                elif arc is _arcs().PARENT:
                    cached = self.get_cached_child_paths(base_path) or []
                    if node_path not in cached:
                        self.add_child_to_child_cache(base_path, node_path,
                                                      comp_node)
                for attr in overload_attrs:
                    _, has = self.opinion(comp_node, attr)
                    value, _ = self.opinion(base, attr)
                    if has:
                        continue
                    src_layer = self.getattr(base, INTERNAL_ATTRS.SOURCE_LAYER)
                    self.setattr(comp_node, attr, value)
                    self.setattr(comp_node, attr + META_ATTRS.SOURCE,
                                 (src_layer, node_path))
                if arc == _arcs().INSTANCE:
                    self.safe_mro_add_base_class(comp_node, base)
                else:
                    parent_bases += [(node_path, comp_node, base)]
                parent_path = self.getattr(comp_node,
                                           INTERNAL_ATTRS.PARENT_PATH)
                if parent_path is world and comp_node not in roots:
                    roots += [comp_node]
                    root_count += 1
                if arc_idx == 0:
                    total_count += 1
            depth = nxt_path.get_path_depth
            parent_bases.sort(key=lambda item: depth(item[0]))
            for _, comp_node, base in parent_bases:
                self.add_base_class(comp_node, base)
            arc_idx += 1
        return root_count, total_count

    def get_cached_child_paths(self, parent_path):
        entry = self.cached_children.get(parent_path)
        return None if entry is None else entry['paths']

    # Making it real ----------------------------------------------------------

    def build(self, sublayer_node_tables):
        node_count = self.comp_pre_proxies(sublayer_node_tables)
        proxy_count, loops = self.comp_proxies(node_count)
        root_count, total_count = self.post_proxy_comp()
        return node_count, proxy_count, loops, root_count, total_count

    def materialize(self):
        """Make the classes, each once with its final bases, and fill the
        comp layer. Returns {class id: class}."""
        made = {}

        def real(cid):
            if cid == OBJECT:
                return object
            cls = made.get(cid)
            if cls is not None:
                return cls
            kind = self.kind[cid]
            if kind == 'py':
                cls = self.pyclass[cid]
            elif kind == 'spec':
                attrs = self.initial[cid]
                cls = SpecNode.new(attrs=dict(attrs))
                final = self.dicts[cid]
                for key, value in final.items():
                    if key not in attrs or attrs[key] is not value:
                        setattr(cls, key, value)
            else:
                bases = tuple(real(b) for b in self.bases[cid])
                attrs = self.initial[cid]
                cls = CompNode.new_with_bases(bases, dict(attrs))
                for key, value in self.dicts[cid].items():
                    if key not in attrs or attrs[key] is not value:
                        setattr(cls, key, value)
            made[cid] = cls
            return cls

        # Bases before the classes made from them, iteratively.
        order = []
        state = {}
        for cid in range(len(self.dicts)):
            if self.kind[cid] == 'py' or cid in state:
                continue
            stack = [(cid, False)]
            while stack:
                c, done = stack.pop()
                if done:
                    state[c] = 2
                    order.append(c)
                    continue
                if state.get(c):
                    continue
                state[c] = 1
                stack.append((c, True))
                for b in self.bases[c]:
                    if b != OBJECT and self.kind[b] != 'py' and \
                            not state.get(b):
                        stack.append((b, False))
        for cid in order:
            real(cid)
        layer = self.comp_layer
        layer._node_table = [[ns, made[c]] for ns, c in self.node_table]
        layer._nodes_path_as_key = {p: made[c]
                                    for p, c in self.path_key.items()}
        layer._nodes_node_as_key = {made[c]: p
                                    for c, p in self.node_key.items()}
        cache = {}
        for path, entry in self.cached_children.items():
            cache[path] = {
                LayerReturnTypes.Node: [made[c] for c in entry['nodes']],
                LayerReturnTypes.Path: entry['paths'],
                LayerReturnTypes.NodeTable: [[p, made[c]]
                                             for p, c in entry['table']],
                LayerReturnTypes.NameDict: {n: made[c] for n, c in
                                            entry['names'].items()}}
        layer._cached_children = cache
        layer._cached_implied_children = {
            p: {LayerReturnTypes.Path: e['paths']}
            for p, e in self.cached_implied.items()}
        layer._bulk_child_cache_valid = self.bulk_valid
        layer._implied_index = self.implied_index
        layer._implied_index_valid = self.implied_valid
        layer._implied_index_len = self.implied_len
        layer._dirty_map = self.dirty_map
        for real_layer, path in self.layer_calls:
            real_layer.clear_node_child_cache(path)
        for level, args, kwargs in self.logs:
            getattr(logger, level)(*args, **kwargs)
        return made


ENGINE_ENV_VAR = 'NXT_COMP_ENGINE'


def build(stage, comp_layer):
    """Composite with a Plan if asked to, see ENGINE_ENV_VAR. Returns the
    comp's counts, or None for the caller to composite the old way.

    :rtype: tuple | None
    """
    import os
    if os.environ.get(ENGINE_ENV_VAR, '').strip().lower() != 'plan':
        return None
    plan = Plan(stage, comp_layer,
                strict=os.environ.get('NXT_COMP_PLAN_STRICT') == '1')
    try:
        counts = plan.build(comp_layer._sublayer_node_tables)
    except Fallback as err:
        logger.debug('Compositing the old way: {}'.format(err))
        return None
    except Exception:
        logger.debug('Compositing the old way, the plan failed:',
                     exc_info=True)
        return None
    plan.materialize()
    return counts


def _index_of(items, item):
    for i, other in enumerate(items):
        if other is item:
            return i
    raise ValueError('item not in list')


def _Node():
    from nxt.nxt_node import Node
    return Node
