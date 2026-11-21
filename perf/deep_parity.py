"""Composite graphs with the old engine and a new one and compare everything
the comp leaves behind, not only what verify_comp signs.

    python deep_parity.py ENGINE [--random N] [--seed S] [graph.nxt ...]

ENGINE is the NXT_COMP_ENGINE value to compare with the old engine, e.g.
plan or native. Compares, for every comp node: its __dict__ (keys in order,
values), its bases and MRO, and the spec classes made for proxies; and for
the comp layer: node table, insertion order, child caches, implied caches
and index, dirty map; and every log record the comp writes.

It also compares which strings are the same object. nxt tests some strings
with `is` (a path against nxt_path.WORLD, a child name against a child
order), so an engine has to hand back the same objects the old one does,
not only equal ones. Each engine composites its own fresh load of the
graph, so neither sees what the other left behind.

--random N also composites N generated graphs that lean on the awkward
parts: references across layers, relative and missing instance paths,
instance cycles, instancing an ancestor, empty instance overrides, implied
nodes and child orders naming nodes that do not exist.
"""
import json
import logging
import os
import random
import shutil
import sys
import tempfile
import traceback

from common import use_repo_nxt

use_repo_nxt()

from nxt.session import Session  # noqa: E402
from nxt import nxt_path  # noqa: E402
from nxt import comp_plan  # noqa: E402
from nxt.nxt_layer import LayerReturnTypes as R  # noqa: E402


class Capture(logging.Handler):
    def __init__(self):
        super(Capture, self).__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        if record.name != 'nxt.stage':
            return
        msg = record.getMessage()
        if 'comp layer created in' in msg or 'Compositing the old way' in msg:
            return
        self.records.append((record.levelname, msg,
                             tuple(getattr(record, 'links', ()) or ())))


FALLBACKS = []


def build(stage, engine):
    os.environ[comp_plan.ENGINE_ENV_VAR] = engine
    if engine != 'old':
        orig = comp_plan.build

        def counted(stage_, layer_):
            result = orig(stage_, layer_)
            if result is None:
                FALLBACKS.append(1)
            return result
        comp_plan.build = counted
        import nxt.stage as stage_mod
        stage_mod.comp_plan.build = counted
    handler = Capture()
    log = logging.getLogger('nxt.stage')
    old_level = log.level
    log.setLevel(1)
    log.addHandler(handler)
    try:
        comp = stage.build_stage()
    finally:
        log.removeHandler(handler)
        log.setLevel(old_level)
        if engine != 'old':
            comp_plan.build = orig
    return comp, handler.records


def canon_value(v):
    if isinstance(v, type):
        return ('class', getattr(v, '_name', '?'))
    if isinstance(v, (list, tuple)):
        return (type(v).__name__, [canon_value(x) for x in v])
    if isinstance(v, dict):
        return ('dict', [(k, canon_value(x)) for k, x in v.items()])
    return v


def describe(comp, known_specs):
    paths = {node: path for path, node in comp._nodes_path_as_key.items()}

    def cls_key(cls):
        if cls is object:
            return 'object'
        if cls in paths:
            return ('comp', paths[cls])
        if id(cls) in known_specs:
            return ('spec', known_specs[id(cls)])
        if cls.__name__ == 'Node':
            return 'Node'
        # A spec class made during the comp, for a proxy or a missing
        # instance source: its own contents identify it.
        return ('made', cls.__name__, tuple(
            (k, repr(canon_value(v))) for k, v in cls.__dict__.items()
            if not k.startswith('__')))

    out = {}
    for path, node in comp._nodes_path_as_key.items():
        out[path] = {
            'dict': [(k, canon_value(v)) for k, v in node.__dict__.items()
                     if k not in ('__dict__', '__weakref__')],
            'bases': [cls_key(b) for b in node.__bases__],
            'mro': [cls_key(b) for b in node.__mro__],
            'name': node.__name__, 'module': node.__module__,
        }
    layer = {
        'insertion': list(comp._nodes_path_as_key),
        'table': [(ns, paths.get(n)) for ns, n in comp._node_table],
        'node_key': [(paths.get(n), p) for n, p in
                     comp._nodes_node_as_key.items()],
        'children': [(p, e[R.Path], [paths.get(n) for n in e[R.Node]],
                      [(tp, paths.get(tn)) for tp, tn in e[R.NodeTable]],
                      [(k, paths.get(n)) for k, n in e[R.NameDict].items()])
                     for p, e in comp._cached_children.items()],
        'implied': [(p, e[R.Path]) for p, e in
                    comp._cached_implied_children.items()],
        'bulk': comp._bulk_child_cache_valid,
        'implied_index': [(p, b) for p, b in comp._implied_index.items()],
        'implied_valid': comp._implied_index_valid,
        'implied_len': comp._implied_index_len,
        'dirty': [(p, list(c)) for p, c in comp._dirty_map.items()],
        'failure': bool(comp.failure),
    }
    return out, layer


def identities(stage, comp):
    """Every string the comp holds, in a fixed walk, as the number of the
    first place that same object was seen. The spec layers are walked first,
    so a string the comp got from a layer gets the layer's number.

    :return: (numbers, where each was seen)
    """
    seen = {}
    numbers = []
    where = []

    def walk(value, label):
        if isinstance(value, str):
            numbers.append(seen.setdefault(id(value), len(seen)))
            where.append(label)
        elif isinstance(value, (list, tuple)):
            numbers.append(seen.setdefault(id(value), len(seen)))
            where.append(label + ' ' + type(value).__name__)
            for i, item in enumerate(value):
                walk(item, label)
        elif isinstance(value, dict):
            for k, item in value.items():
                walk(k, label)
                walk(item, label)

    def walk_class(cls, label):
        for k, v in cls.__dict__.items():
            if not k.startswith('__'):
                walk(v, '{} {}'.format(label, k))

    walk(nxt_path.WORLD, 'WORLD')
    for layer in stage._sub_layers:
        for p, n in layer._nodes_path_as_key.items():
            walk(p, 'layer path')
            walk_class(n, 'layer ' + p)
    paths = {node: path for path, node in comp._nodes_path_as_key.items()}
    for p, node in comp._nodes_path_as_key.items():
        walk(p, 'comp path')
        for cls in node.__mro__:
            if cls is node or (cls not in paths and
                               cls.__name__ == 'SpecNode' and
                               cls.__module__ == node.__module__):
                walk_class(cls, 'comp ' + p)
    for row in comp._node_table:
        walk(row, 'node table')
    for value in comp._nodes_node_as_key.values():
        walk(value, 'node key')
    for p, e in comp._cached_children.items():
        walk(p, 'children key')
        walk(e[R.Path], 'children paths ' + p)
        walk(e[R.Node], 'children nodes ' + p)
        walk(e[R.NodeTable], 'children table ' + p)
        for name in e[R.NameDict]:
            walk(name, 'children names ' + p)
    walk(comp._cached_implied_children, 'implied')
    walk(comp._implied_index, 'implied index')
    walk(comp._dirty_map, 'dirty')
    return numbers, where


def ordered_children(comp):
    """Each node's ordered children, which nxt orders by name identity."""
    return [(p, [paths for paths in
                 (comp._nodes_node_as_key.get(n) for n in
                  comp.children(p, ordered=True))])
            for p in comp._nodes_path_as_key]


def compare(path, engine, verbose=True):
    def load():
        stage = Session().load_file(path)
        known = {}
        for layer in stage._sub_layers:
            for p, n in layer._nodes_path_as_key.items():
                known[id(n)] = (layer.real_path, p)
        return stage, known
    old_stage, old_known = load()
    try:
        old, old_logs = build(old_stage, 'old')
    except Exception:
        return 'old raised'
    new_stage, new_known = load()
    try:
        new, new_logs = build(new_stage, engine)
    except Exception:
        return 'new raised:\n' + traceback.format_exc()
    a_nodes, a_layer = describe(old, old_known)
    b_nodes, b_layer = describe(new, new_known)
    problems = []
    a_ids, a_where = identities(old_stage, old)
    b_ids, b_where = identities(new_stage, new)
    if a_ids != b_ids:
        problems.append('string identity')
        if verbose:
            for i, (x, y) in enumerate(zip(a_ids, b_ids)):
                if x != y:
                    print('   identity', i, a_where[i], x, '!=', y,
                          b_where[i])
                    break
            if len(a_ids) != len(b_ids):
                print('   identity counts', len(a_ids), len(b_ids))
    if ordered_children(old) != ordered_children(new):
        problems.append('ordered children')
    for key in a_layer:
        if a_layer[key] != b_layer[key]:
            problems.append('layer ' + key)
    if list(a_nodes) != list(b_nodes):
        problems.append('node paths')
    for p in a_nodes:
        if p in b_nodes and a_nodes[p] != b_nodes[p]:
            for k in a_nodes[p]:
                if a_nodes[p][k] != b_nodes[p][k]:
                    problems.append('node {} {}'.format(p, k))
                    if verbose and len(problems) < 4:
                        print('   old', a_nodes[p][k])
                        print('   new', b_nodes[p][k])
            if len(problems) > 6:
                break
    if old_logs != new_logs:
        problems.append('logs')
        if verbose:
            for i, (x, y) in enumerate(zip(old_logs, new_logs)):
                if x != y:
                    print('   log', i, x, '!=', y)
                    break
            if len(old_logs) != len(new_logs):
                print('   log counts', len(old_logs), len(new_logs))
    return problems


def random_graph(folder, rnd):
    """A few layers referencing each other, with awkward instancing."""
    names = ['a', 'b', 'c', 'd', 'e', 'f']
    n_layers = rnd.randint(1, 3)
    files = ['layer{}.nxt'.format(i) for i in range(n_layers)]
    all_paths = []
    for _ in range(rnd.randint(3, 14)):
        depth = rnd.randint(1, 4)
        path = '/' + '/'.join(rnd.choice(names) for _ in range(depth))
        all_paths.append(path)
    for i, f in enumerate(files):
        nodes = {}
        for path in rnd.sample(all_paths, rnd.randint(1, len(all_paths))):
            data = {}
            roll = rnd.random()
            if roll < 0.35:
                choice = rnd.random()
                if choice < 0.5:
                    data['instance'] = rnd.choice(all_paths)
                elif choice < 0.7:
                    data['instance'] = '../' + rnd.choice(names)
                elif choice < 0.8:
                    data['instance'] = './' + rnd.choice(names)
                elif choice < 0.9:
                    data['instance'] = '/missing/' + rnd.choice(names)
                else:
                    data['instance'] = ''
            if rnd.random() < 0.3:
                data['child_order'] = rnd.sample(names, rnd.randint(1, 4))
            if rnd.random() < 0.2:
                data['enabled'] = rnd.random() < 0.5
            if rnd.random() < 0.2:
                data['comment'] = 'c' + str(rnd.randint(0, 9))
            if rnd.random() < 0.3:
                data['code'] = ['x = ${v}']
            if rnd.random() < 0.15 and path.count('/') == 1:
                data['execute_in'] = rnd.choice(all_paths).split('/')[1]
                data['execute_in'] = '/' + data['execute_in']
            if rnd.random() < 0.1 and path.count('/') == 1:
                data['start_point'] = True
            if rnd.random() < 0.4:
                data['attrs'] = {'v': {'value': str(rnd.randint(0, 9))}}
            nodes[path] = data
        layer = {'version': '1.17', 'alias': 'l{}'.format(i),
                 'references': files[i + 1:i + 2], 'nodes': nodes}
        with open(os.path.join(folder, f), 'w') as fp:
            json.dump(layer, fp)
    return os.path.join(folder, files[0])


def main():
    args = sys.argv[1:]
    engine = args.pop(0)
    n_random = 0
    seed = 1
    if '--random' in args:
        i = args.index('--random')
        n_random = int(args[i + 1])
        del args[i:i + 2]
    if '--seed' in args:
        i = args.index('--seed')
        seed = int(args[i + 1])
        del args[i:i + 2]
    logging.disable(logging.NOTSET)
    bad = 0
    total = 0
    for path in args:
        total += 1
        problems = compare(path, engine)
        if problems and problems != 'old raised':
            bad += 1
            print('DIFFER', os.path.basename(path), problems)
    rnd = random.Random(seed)
    tmp = tempfile.mkdtemp(prefix='nxt_deep_parity_')
    skipped = 0
    try:
        for i in range(n_random):
            folder = os.path.join(tmp, str(i))
            os.makedirs(folder)
            path = random_graph(folder, rnd)
            problems = compare(path, engine, verbose=bad < 3)
            if problems == 'old raised':
                skipped += 1
                continue
            total += 1
            if problems:
                bad += 1
                if bad <= 5:
                    keep = os.path.join(os.path.dirname(os.path.abspath(
                        __file__)), '_work', 'parity_fail_{}'.format(i))
                    shutil.rmtree(keep, ignore_errors=True)
                    shutil.copytree(folder, keep)
                    print('DIFFER random', i, problems, '->', keep)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('{} differ out of {} ({} random graphs the old engine could not '
          'comp, {} fell back to the old engine)'.format(
              bad, total, skipped, len(FALLBACKS)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
