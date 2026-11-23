"""Run graphs in a copy of a comp, and in the comp made for a headless run,
and check each leaves exactly what a run in a fresh comp does.

    python runtime_parity.py [--random N] [--seed S] [graph.nxt ...]

With no graphs, every graph in nxt/test. For each graph it checks:

- copy: CompLayer.copy() describes as a fresh comp does (deep_parity), before
  and after it is made a runtime layer, and shares no node class with the
  comp it was copied from.
- runs: from each start node (or the root nodes, when it has none), a run
  the old way (a fresh comp for the run), a run in a copy of a comp, and a
  headless run that composites once (Stage.execute) print the same, log the
  same, raise the same and leave the same values on every node.

--random N also runs N generated graphs whose nodes set values on
themselves and on the world, read other nodes' values and instance each
other, so a value set at runtime has to reach every node that inherits it.
"""
import contextlib
import io
import json
import logging
import os
import random
import re
import shutil
import sys
import tempfile
import traceback

from common import SKIP_GRAPHS, TEST_DIR, use_repo_nxt

use_repo_nxt()

import deep_parity  # noqa: E402
from nxt import nxt_path  # noqa: E402
from nxt.session import Session  # noqa: E402

# Runs the whole nxt test suite in a node: what it says depends on what
# ran before it in the process.
RUN_SKIP = {'unittests.nxt',
            # Start Maya and Blender.
            'cli_test.nxt', 'test_sub_graph.nxt'}
# Times and addresses differ from run to run.
_NOISE = re.compile(r'\d+(\.\d+)? ?(second\(s\)|ms)|0x[0-9a-fA-F]+')


class Capture(logging.Handler):
    def __init__(self):
        super(Capture, self).__init__(logging.DEBUG)
        self.records = []
        # What a comp says is left out: the old way made one comp more.
        self.compositing = 0

    def emit(self, record):
        if self.compositing or not record.name.startswith('nxt'):
            return
        msg = _NOISE.sub('#', record.getMessage())
        self.records.append((record.levelname, msg))


def load(path):
    stage = Session().load_file(path)
    known = {}
    for layer in stage._sub_layers:
        for p, n in layer._nodes_path_as_key.items():
            known[id(n)] = (layer.real_path, p)
    return stage, known


def node_values(runtime_layer):
    """Every value a run can leave on the runtime layer's nodes."""
    out = []
    for path, node in runtime_layer._nodes_path_as_key.items():
        attrs = {}
        for cls in reversed(node.__mro__):
            for k, v in cls.__dict__.items():
                if not k.startswith('__'):
                    attrs[k] = v
        out.append((path, sorted((k, repr(deep_parity.canon_value(v)))
                                 for k, v in attrs.items())))
    return out


def starts(stage):
    comp = stage.build_stage()
    found = list(stage.get_layer_start_nodes(comp))
    if not found:
        found = list(comp.children(nxt_path.WORLD, ordered=True,
                                   return_type=comp.RETURNS.Path))[:3]
    return found


def run(stage, start, how):
    """Run from start, the old way, in a copy, or headless."""
    handler = Capture()
    log = logging.getLogger('nxt')
    old_level = log.level
    log.setLevel(1)
    log.addHandler(handler)
    out = io.StringIO()
    raised = None
    runtime_layer = None
    build_stage = stage.build_stage

    def quiet_build(*args, **kwargs):
        handler.compositing += 1
        try:
            return build_stage(*args, **kwargs)
        finally:
            handler.compositing -= 1
    stage.build_stage = quiet_build
    try:
        with contextlib.redirect_stdout(out):
            if how == 'old':
                # What every run did: composite again for the run.
                comp = stage.build_stage()
                order = comp.get_exec_order(start)
                runtime_layer = stage.execute_nodes(order, comp)
            elif how == 'copy':
                comp = stage.build_stage()
                order = comp.get_exec_order(start)
                copied = stage.setup_runtime_layer(comp.copy())
                runtime_layer = stage.execute_nodes(order, copied)
            else:
                runtime_layer = stage.execute(start=start)
    except Exception as err:
        raised = _NOISE.sub('#', '{}: {}'.format(type(err).__name__, err))
    finally:
        log.removeHandler(handler)
        log.setLevel(old_level)
    result = {'out': _NOISE.sub('#', out.getvalue()),
              'logs': handler.records, 'raised': raised}
    if runtime_layer is not None:
        result['values'] = node_values(runtime_layer)
    return result


def check_copy(path):
    problems = []
    stage, known = load(path)
    comp = stage.build_stage()
    copied = comp.copy()
    fresh = stage.build_stage()
    if deep_parity.describe(copied, known) != deep_parity.describe(
            fresh, known):
        problems.append('copy differs from a fresh comp')
    if set(comp._nodes_path_as_key.values()) & set(
            copied._nodes_path_as_key.values()):
        problems.append('copy shares node classes')
    if copied._console is comp._console:
        problems.append('copy shares the console')
    if copied._console.layer_path != fresh._console.layer_path:
        problems.append('copy console names another layer')
    if os.path.basename(path) in RUN_SKIP:
        # Making a runtime runs the world node.
        return problems
    try:
        stage.setup_runtime_layer(copied)
        stage.setup_runtime_layer(fresh)
    except Exception:
        return problems
    if deep_parity.describe(copied, known) != deep_parity.describe(
            fresh, known):
        problems.append('runtime copy differs from a fresh runtime')
    return problems


def check_runs(path):
    problems = []
    if os.path.basename(path) in RUN_SKIP:
        return problems
    try:
        start_paths = starts(load(path)[0])
    except Exception:
        return problems
    for start in start_paths:
        # Each run in a fresh load, so none sees what another left.
        results = {how: run(load(path)[0], start, how)
                   for how in ('old', 'copy', 'headless')}
        for how in ('copy', 'headless'):
            for key in ('out', 'logs', 'raised', 'values'):
                if results[how].get(key) != results['old'].get(key):
                    problems.append('{} run from {}: {}'.format(how, start,
                                                                key))
    return problems


def compare(path):
    here = os.getcwd()
    os.chdir(os.path.dirname(os.path.abspath(path)))
    try:
        return check_copy(path) + check_runs(path)
    except Exception:
        return ['raised:\n' + traceback.format_exc()]
    finally:
        os.chdir(here)


CODE = [
    ['self.v = str(self.v) + "1"', 'print("${path}", self.v)'],
    ['STAGE.seen = getattr(STAGE, "seen", "") + "${path};"',
     'print(STAGE.seen)'],
    ['print("${/a.v}", "${v}")'],
    ['self.items = list(getattr(self, "items", [])) + [1]',
     'print(len(self.items))'],
    ['if getattr(STAGE, "seen", ""):', '    self.v = "set"',
     'print(self.v)'],
    ['raise ExitNode()'],
]


def random_graph(folder, rnd):
    """Layers whose nodes set and read values at runtime, instancing each
    other, with a start node."""
    path = deep_parity.random_graph(folder, rnd)
    names = sorted(f for f in os.listdir(folder) if f.endswith('.nxt'))
    for name in names:
        layer_path = os.path.join(folder, name)
        with open(layer_path) as fp:
            layer = json.load(fp)
        for node_path, data in layer['nodes'].items():
            if rnd.random() < 0.7:
                data['code'] = list(rnd.choice(CODE))
            data.setdefault('attrs', {}).setdefault(
                'path', {'value': node_path})
        if name == names[0]:
            layer['nodes'].setdefault('/a', {}).update(
                {'start_point': True,
                 'attrs': {'v': {'value': 'a'}},
                 'code': ['print("start")']})
        with open(layer_path, 'w') as fp:
            json.dump(layer, fp)
    return path


def main():
    args = sys.argv[1:]
    n_random = 0
    seed = 12
    if '--random' in args:
        i = args.index('--random')
        n_random = int(args[i + 1])
        del args[i:i + 2]
    if '--seed' in args:
        i = args.index('--seed')
        seed = int(args[i + 1])
        del args[i:i + 2]
    paths = [os.path.abspath(p) for p in args]
    if not paths and not n_random:
        paths = [os.path.join(TEST_DIR, n) for n in sorted(os.listdir(
            TEST_DIR)) if n.endswith('.nxt') and n not in SKIP_GRAPHS]
    tmp = tempfile.mkdtemp(prefix='runtime_parity_')
    rnd = random.Random(seed)
    for i in range(n_random):
        folder = os.path.join(tmp, str(i))
        os.makedirs(folder)
        paths.append(random_graph(folder, rnd))
    bad = 0
    try:
        for path in paths:
            problems = compare(path)
            if problems:
                bad += 1
                print('DIFFER', path)
                for p in problems[:5]:
                    print('   ', p)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('{} differ out of {}'.format(bad, len(paths)))
    return bad


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
