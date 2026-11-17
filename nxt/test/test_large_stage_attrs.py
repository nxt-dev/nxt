"""Running a node does not copy what it inherits from the world node.

Every attr a node inherits used to be deep copied before its compute ran,
so a big value put on STAGE made every node that ran after it slow, even
nodes that never looked at it. Attrs from the world node are shared, the
way they already are through STAGE. Anything else a node inherits is still
copied, so changing it in place stays local to the node that did it.
"""
# Builtin
import json
import os
import shutil
import tempfile
import unittest

# Internal
from nxt.session import Session

GRAPH = {
    'version': '1.17',
    'alias': 'big_stage',
    'nodes': {
        '/': {'code': ['']},
        '/root': {'start_point': True,
                  'child_order': ['make', 'p', 'check']},
        '/root/make': {'code': ['STAGE.big = list(range(100000))']},
        '/root/p': {'child_order': ['a', 'b'],
                    'attrs': {'lst': {'value': 'None'}},
                    'code': ['self.lst = [1]']},
        '/root/p/a': {'code': ['self.lst.append(2)',
                               'self.shared = self.big is STAGE.big']},
        '/root/p/b': {'code': ['self.seen = list(self.lst)']},
        '/root/check': {'code': ["self.big = ['mine']"]},
        '/root/check/after': {'code': ['self.seen = self.big',
                                       'self.stage_len = len(STAGE.big)']},
    }
}


class LargeStageAttrs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.mkdtemp()
        path = os.path.join(cls.folder, 'big_stage.nxt')
        with open(path, 'w') as f:
            json.dump(GRAPH, f)
        stage = Session().load_file(path)
        cls.cache = stage.execute(start='/root').cache_layer

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.folder, ignore_errors=True)

    def frame(self, path):
        return self.cache.lookup(path)

    def test_world_attrs_are_not_copied(self):
        self.assertIs(True, self.frame('/root/p/a').shared)

    def test_changing_an_inherited_attr_stays_local(self):
        self.assertEqual([1, 2], self.frame('/root/p/a').lst)
        self.assertEqual([1], self.frame('/root/p/b').seen)

    def test_reassigning_a_world_attr_stays_local(self):
        self.assertEqual(['mine'], self.frame('/root/check/after').seen)
        self.assertEqual(100000, self.frame('/root/check/after').stage_len)
