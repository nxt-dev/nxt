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
