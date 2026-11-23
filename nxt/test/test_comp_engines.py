"""The native comp engine leaves exactly what the old one does, see
comp_plan.

Each test graph, and some generated ones that lean on the awkward parts, is
composited the old way and the native way, and everything the comp leaves
behind is compared, down to which strings and lists are the same object.
perf/deep_parity.py does the comparing, so this runs from a checkout; it
checks the Python plan engine the same way, with `plan`.
"""
import glob
import os
import random
import shutil
import sys
import tempfile
import unittest

from nxt import native

HERE = os.path.dirname(os.path.abspath(__file__))
PERF_DIR = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'perf')

try:
    sys.path.insert(0, PERF_DIR)
    import deep_parity
    from common import SKIP_GRAPHS
except ImportError:
    deep_parity = None
finally:
    if sys.path and sys.path[0] == PERF_DIR:
        sys.path.pop(0)


def has_native_comp():
    return native.lib is not None and hasattr(native.lib, 'comp_plan')


class EngineParity(object):
    ENGINE = None
    # Random graphs, from a seed whose graphs the old engine finishes; some
    # instance loops it never finishes compositing.
    RANDOM_GRAPHS = 40
    SEED = 12

    def setUp(self):
        self.cwd = os.getcwd()
        self.env = os.environ.get('NXT_COMP_ENGINE')

    def tearDown(self):
        os.chdir(self.cwd)
        if self.env is None:
            os.environ.pop('NXT_COMP_ENGINE', None)
        else:
            os.environ['NXT_COMP_ENGINE'] = self.env

    def check(self, path):
        problems = deep_parity.compare(path, self.ENGINE, verbose=False)
        if problems == 'old raised':
            return
        self.assertEqual([], problems, os.path.basename(path))

    def test_test_graphs(self):
        os.chdir(HERE)
        for path in sorted(glob.glob(os.path.join(HERE, '*.nxt'))):
            if os.path.basename(path) in SKIP_GRAPHS:
                continue
            self.check(path)

    def test_random_graphs(self):
        rnd = random.Random(self.SEED)
        tmp = tempfile.mkdtemp(prefix='nxt_comp_engines_')
        try:
            for i in range(self.RANDOM_GRAPHS):
                folder = os.path.join(tmp, str(i))
                os.makedirs(folder)
                self.check(deep_parity.random_graph(folder, rnd))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


@unittest.skipUnless(deep_parity, 'needs perf/ from a checkout')
@unittest.skipUnless(has_native_comp(), 'no native build for this platform')
class NativeParity(EngineParity, unittest.TestCase):
    ENGINE = 'native'


class DefaultEngine(unittest.TestCase):
    """Graphs are composited the native way unless asked otherwise."""

    def setUp(self):
        self.env = os.environ.pop('NXT_COMP_ENGINE', None)
        self.addCleanup(self.restore)

    def restore(self):
        os.environ.pop('NXT_COMP_ENGINE', None)
        if self.env is not None:
            os.environ['NXT_COMP_ENGINE'] = self.env

    def engine_used(self):
        from unittest import mock
        from nxt import comp_plan
        from nxt.session import Session
        used = []
        real = comp_plan.native_build

        def native_build(*args, **kwargs):
            used.append('native')
            return real(*args, **kwargs)
        path = os.path.join(HERE, 'StageInstanceTest.nxt')
        with mock.patch.object(comp_plan, 'native_build', native_build):
            Session().load_file(path).build_stage()
        return used

    def test_native_by_default(self):
        self.assertEqual(['native'], self.engine_used())

    def test_python_when_asked(self):
        os.environ['NXT_COMP_ENGINE'] = 'python'
        self.assertEqual([], self.engine_used())


class Panic(BaseException):
    """What a Rust panic reaches Python as."""


class BrokenModule(object):
    """A native module that loads and then fails at everything."""

    def __init__(self):
        from nxt import comp_plan
        self.VERSION = comp_plan.NATIVE_VERSION
        self.calls = 0

    def comp_plan(self, *args):
        self.calls += 1
        raise Panic('comp')

    def standalone_tokens(self, *args):
        self.calls += 1
        raise Panic('tokens')


class NativeFails(unittest.TestCase):
    """A native module that fails, a panic included, leaves nxt working
    the same in Python, says so once, and is not tried again."""

    def setUp(self):
        self.env = os.environ.pop('NXT_COMP_ENGINE', None)
        self.lib = native.lib
        self.addCleanup(self.restore)

    def restore(self):
        native.lib = self.lib
        os.environ.pop('NXT_COMP_ENGINE', None)
        if self.env is not None:
            os.environ['NXT_COMP_ENGINE'] = self.env

    @staticmethod
    def comp_paths():
        from nxt.session import Session
        path = os.path.join(HERE, 'StageInstanceTest.nxt')
        stage = Session().load_file(path)
        comp = stage.build_stage()
        return sorted(comp._nodes_path_as_key)

    def test_compositing_falls_back_to_python(self):
        native.lib = None
        expected = self.comp_paths()
        broken = native.lib = BrokenModule()
        with self.assertLogs('nxt', level='WARNING') as logs:
            self.assertEqual(expected, self.comp_paths())
            self.assertEqual(expected, self.comp_paths())
        self.assertEqual(1, broken.calls)
        self.assertEqual(1, len(logs.records))
        self.assertIsNone(native.lib)

    def test_finding_tokens_falls_back_to_python(self):
        from nxt import tokens
        value = 'a ${b} ${c:${d}} e'
        native.lib = None
        expected = tokens.get_standalone_tokens(value)
        broken = native.lib = BrokenModule()
        with self.assertLogs('nxt', level='WARNING'):
            self.assertEqual(expected, tokens.get_standalone_tokens(value))
        self.assertEqual(expected, tokens.get_standalone_tokens(value))
        self.assertEqual(1, broken.calls)


class EngineInUse(unittest.TestCase):
    """nxt --version says which engine composites, see engine_in_use."""
    def setUp(self):
        self.env = os.environ.get('NXT_COMP_ENGINE')
        self.lib = native.lib

    def tearDown(self):
        native.lib = self.lib
        if self.env is None:
            os.environ.pop('NXT_COMP_ENGINE', None)
        else:
            os.environ['NXT_COMP_ENGINE'] = self.env

    def test_python_when_asked(self):
        from nxt import comp_plan
        os.environ['NXT_COMP_ENGINE'] = 'python'
        self.assertEqual('python (NXT_COMP_ENGINE=python)',
                         comp_plan.engine_in_use())

    def test_python_without_a_native_build(self):
        from nxt import comp_plan
        os.environ.pop('NXT_COMP_ENGINE', None)
        native.lib = None
        self.assertTrue(comp_plan.engine_in_use().startswith('python ('))

    @unittest.skipUnless(has_native_comp(), 'no native build here')
    def test_native_by_default(self):
        from nxt import comp_plan
        os.environ.pop('NXT_COMP_ENGINE', None)
        self.assertEqual('native', comp_plan.engine_in_use())

    def test_the_version_says_it(self):
        from nxt import cli, comp_plan
        self.assertIn('| Comp ' + comp_plan.engine_in_use(),
                      cli.get_version())
