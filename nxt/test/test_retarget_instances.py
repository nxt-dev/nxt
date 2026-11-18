"""Instance paths can follow nodes that are parented somewhere else.

Parenting a node changes its path, which used to leave every instance of
it, or of anything below it, pointing at nothing.
"""
# Builtin
import json
import os
import shutil
import tempfile
import unittest

# Internal
from nxt.session import Session
from nxt.nxt_node import INTERNAL_ATTRS

INST = INTERNAL_ATTRS.INSTANCE_PATH
INST_KEY = INTERNAL_ATTRS.as_save_key(INST)

NODES = {
    '/src': {},
    '/src/child': {},
    '/other': {},
    '/new_parent': {},
    '/abs': {INST_KEY: '/src'},
    '/abs_child': {INST_KEY: '/src/child'},
    '/grp': {},
    '/grp/rel': {INST_KEY: '../../src'},
    '/pair': {},
    '/pair/a': {},
    '/pair/b': {INST_KEY: '../a'},
    '/lone': {INST_KEY: '../other'},
}


class RetargetInstances(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        path = os.path.join(self.folder, 'graph.nxt')
        with open(path, 'w') as f:
            json.dump({'version': '1.17', 'alias': 'graph', 'nodes': NODES},
                      f)
        self.stage = Session().load_file(path)
        self.layer = self.stage.top_layer

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def inst(self, path):
        return getattr(self.layer.lookup(path), INST)

    def parent(self):
        nodes = [self.layer.lookup(p) for p in ('/src', '/pair', '/lone')]
        moved = self.stage.parent_nodes(nodes, '/new_parent', self.layer)
        return self.stage.retarget_instance_paths(moved, self.layer)

    def test_instances_follow_the_move(self):
        self.parent()
        self.assertEqual('/new_parent/src', self.inst('/abs'))
        self.assertEqual('/new_parent/src/child', self.inst('/abs_child'))
        self.assertEqual('../../new_parent/src', self.inst('/grp/rel'))
        # Moved along with its source, still right as it was
        self.assertEqual('../a', self.inst('/new_parent/pair/b'))
        # Moved away from its source
        self.assertEqual('../../other', self.inst('/new_parent/lone'))
        comp = self.stage.build_stage()
        self.assertIsNotNone(comp.lookup('/abs/child'))
        self.assertEqual('/other',
                         getattr(comp.lookup('/new_parent/lone'), INST))

    def test_undo(self):
        changes = self.parent()
        self.assertEqual(4, len(changes))
        self.stage.apply_attr_ref_changes(changes, self.layer, revert=True)
        nodes = [self.layer.lookup(p) for p in ('/new_parent/src',
                                                '/new_parent/pair',
                                                '/new_parent/lone')]
        self.stage.parent_nodes(nodes, '/', self.layer)
        for path, data in NODES.items():
            self.assertEqual(data.get(INST_KEY), self.inst(path), path)

    def test_untouched_without_moves(self):
        self.assertEqual([], self.stage.retarget_instance_paths({},
                                                                self.layer))
