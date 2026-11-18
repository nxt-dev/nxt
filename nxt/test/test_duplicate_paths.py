"""A save file naming the same node path twice warns when it loads.

json keeps only the last of a repeated key, so a hand edit or a bad merge
that leaves a node in a file twice used to lose one of them silently.
"""
# Builtin
import os
import shutil
import tempfile
import unittest

# Internal
from nxt.session import Session

SAVE = '''{
    "version": "1.17",
    "alias": "dupes",
    "nodes": {
        "/node": {"attrs": {"attr1": {"value": "first"}}},
        "/other": {},
        "/node": {"attrs": {"attr1": {"value": "second"},
                            "attr1": {"value": "third"}}}
    }
}
'''


class DuplicatePaths(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.path = os.path.join(self.folder, 'dupes.nxt')
        with open(self.path, 'w') as f:
            f.write(SAVE)

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_duplicates_warn_and_load_continues(self):
        with self.assertLogs('nxt', 'WARNING') as logs:
            stage = Session().load_file(self.path)
        dupes = [m for m in logs.output if 'Duplicate' in m]
        self.assertEqual(2, len(dupes), logs.output)
        self.assertIn('node path "/node"', dupes[1])
        self.assertIn('dupes.nxt', dupes[1])
        self.assertIn('key "attr1"', dupes[0])
        # Loading carries on, keeping the last of each as json always has
        comp = stage.build_stage()
        node = comp.lookup('/node')
        self.assertEqual('third', stage.get_node_attr_value(node, 'attr1',
                                                            comp))
        self.assertIsNotNone(comp.lookup('/other'))
