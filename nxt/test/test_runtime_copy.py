"""A run in a copy of a comp, and a headless run that composites once,
leave exactly what a run in a fresh comp of the graph does.

A run sets values on the classes of the comp it runs in, so every run used
to composite the graph again for itself. A comp that is current, the one
the editor shows or the one a headless run just made, is copied or run in
instead. perf/runtime_parity.py does the comparing of whole graphs, so that
part runs from a checkout.
"""
import json
import os
import random
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from nxt import nxt_path
from nxt.nxt_layer import LayerReturnTypes, comp_differences
from nxt.session import Session
from nxt.stage import Stage

HERE = os.path.dirname(os.path.abspath(__file__))
PERF_DIR = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'perf')

try:
    sys.path.insert(0, PERF_DIR)
    import runtime_parity
except ImportError:
    runtime_parity = None
finally:
    if sys.path and sys.path[0] == PERF_DIR:
        sys.path.pop(0)


def write_graph(folder, nodes, name='graph.nxt', references=()):
    path = os.path.join(folder, name)
    with open(path, 'w') as fp:
        json.dump({'version': '1.17', 'alias': name.split('.')[0],
                   'references': list(references), 'nodes': nodes}, fp)
    return path


class Copy(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix='nxt_runtime_copy_')
        self.addCleanup(shutil.rmtree, self.folder, True)
        lower = write_graph(self.folder, {
            '/base': {'attrs': {'v': {'value': 'x'}},
                      'code': ['self.v = self.v + "1"']},
        }, name='lower.nxt')
        self.path = write_graph(self.folder, {
            '/base/child': {'attrs': {'w': {'value': '2'}}},
            '/inst': {'instance': '/base', 'start_point': True,
                      'code': ['print(self.v)']},
            '/inst/extra': {'code': ['STAGE.seen = True']},
        }, references=[os.path.basename(lower)])
        self.stage = Session().load_file(self.path)

    def test_a_copy_is_a_fresh_comp(self):
        comp = self.stage.build_stage()
        self.assertEqual([], comp_differences(comp.copy(),
                                              self.stage.build_stage()))

    def test_a_copy_has_its_own_node_classes(self):
        comp = self.stage.build_stage()
        copied = comp.copy()
        for path, node in comp._nodes_path_as_key.items():
            self.assertIsNot(node, copied.lookup(path), path)
        # What is inherited is inherited from the copy's own nodes.
        self.assertIn(copied.lookup('/base'),
                      copied.lookup('/inst').__mro__)
        self.assertNotIn(comp.lookup('/base'),
                         copied.lookup('/inst').__mro__)

    def test_a_run_in_a_copy_leaves_the_comp_as_it_was(self):
        comp = self.stage.build_stage()
        before = comp_differences(comp, self.stage.build_stage())
        runtime = self.stage.setup_runtime_layer(comp.copy())
        self.stage.execute_nodes(['/base', '/inst', '/inst/extra'], runtime)
        self.assertEqual('x1', runtime.lookup('/base').v)
        self.assertEqual('x', comp.lookup('/base').v)
        self.assertFalse(comp.runtime)
        self.assertFalse(hasattr(comp.lookup(nxt_path.WORLD), 'seen'))
        self.assertEqual(before, comp_differences(comp,
                                                  self.stage.build_stage()))

    def test_a_value_set_in_a_run_reaches_the_nodes_that_inherit_it(self):
        runtime = self.stage.setup_runtime_layer(
            self.stage.build_stage().copy())
        self.stage.execute_nodes(['/base'], runtime)
        self.assertEqual('x1', runtime.lookup('/inst').v)

    def test_errors_name_the_layer_as_a_fresh_comp_does(self):
        comp = self.stage.build_stage()
        self.assertEqual(comp._console.layer_path,
                         comp.copy()._console.layer_path)
        self.assertIsNot(comp._console, comp.copy()._console)

    def test_differences_are_found(self):
        comp = self.stage.build_stage()
        copied = comp.copy()
        copied.lookup('/inst').v = 'changed'
        found = comp_differences(copied, comp)
        self.assertEqual(1, len(found))
        self.assertIn('/inst', found[0])


class OneComp(unittest.TestCase):
    """A headless run composites the graph once."""

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix='nxt_one_comp_')
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.path = write_graph(self.folder, {
            '/start': {'start_point': True, 'attrs': {'v': {'value': '1'}},
                       'code': ['self.v = "ran"']},
        })

    def count_comps(self):
        real = Stage.build_stage
        calls = []

        def counted(stage, *args, **kwargs):
            calls.append(1)
            return real(stage, *args, **kwargs)
        patch = mock.patch.object(Stage, 'build_stage', counted)
        patch.start()
        self.addCleanup(patch.stop)
        return calls

    def test_execute_graph(self):
        calls = self.count_comps()
        runtime = Session().execute_graph(self.path)
        self.assertEqual(1, len(calls))
        self.assertEqual('ran', runtime.lookup('/start').v)

    def test_session_execute_nodes(self):
        calls = self.count_comps()
        runtime = Session().execute_nodes(self.path, ['/start'])
        self.assertEqual(1, len(calls))
        self.assertEqual('ran', runtime.lookup('/start').v)

    def test_a_comp_given_to_execute_nodes_is_left_alone(self):
        stage = Session().load_file(self.path)
        comp = stage.build_stage()
        calls = self.count_comps()
        runtime = stage.execute_nodes(['/start'], comp)
        # It may be out of date, so the run is in a comp of the stage.
        self.assertEqual(1, len(calls))
        self.assertIsNot(runtime, comp)
        self.assertEqual('1', comp.lookup('/start').v)


class ChildCache(unittest.TestCase):
    """A node's children do not depend on what was asked before."""

    def test_nodes_under_an_implied_parent(self):
        folder = tempfile.mkdtemp(prefix='nxt_child_cache_')
        self.addCleanup(shutil.rmtree, folder, True)
        # /b/c is only implied, so the comp files /b/c/a under /b.
        path = write_graph(folder, {'/b': {}, '/b/c/a': {}, '/d': {}})
        paths = LayerReturnTypes.Path

        def asked(first):
            comp = Session().load_file(path).build_stage()
            for other in first:
                comp.children(other, return_type=paths)
            return comp.children('/b', return_type=paths)

        self.assertEqual(asked([]), asked(['/d', '/b/c/a', '/b/c']))


@unittest.skipUnless(runtime_parity, 'needs perf/ from a checkout')
class Parity(unittest.TestCase):
    RANDOM_GRAPHS = 20
    SEED = 12

    def setUp(self):
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)

    def test_test_graphs(self):
        for name in sorted(os.listdir(HERE)):
            if (not name.endswith('.nxt') or
                    name in runtime_parity.SKIP_GRAPHS):
                continue
            path = os.path.join(HERE, name)
            self.assertEqual([], runtime_parity.compare(path), name)

    def test_random_graphs(self):
        rnd = random.Random(self.SEED)
        tmp = tempfile.mkdtemp(prefix='nxt_runtime_parity_')
        try:
            for i in range(self.RANDOM_GRAPHS):
                folder = os.path.join(tmp, str(i))
                os.makedirs(folder)
                path = runtime_parity.random_graph(folder, rnd)
                self.assertEqual([], runtime_parity.compare(path), i)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
