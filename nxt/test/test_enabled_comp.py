"""Setting a node's enabled state updates the comp the way a full comp would.

The editor toggles a node by changing the comp in place rather than
building a new one. A node's own opinion used to lose to the node it is an
instance of, so the comp kept the old state until the graph was comped
again from scratch.
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

ENABLED = INTERNAL_ATTRS.ENABLED
ENABLED_KEY = INTERNAL_ATTRS.as_save_key(ENABLED)
INST_KEY = INTERNAL_ATTRS.as_save_key(INTERNAL_ATTRS.INSTANCE_PATH)


class EnabledComp(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        lower = os.path.join(self.folder, 'lower.nxt')
        with open(lower, 'w') as f:
            json.dump({'version': '1.17', 'alias': 'lower', 'nodes': {
                '/src': {},
                '/inst': {INST_KEY: '/src'},
                '/inst_of_inst': {INST_KEY: '/inst'},
                '/overridden': {},
            }}, f)
        top = os.path.join(self.folder, 'top.nxt')
        with open(top, 'w') as f:
            json.dump({'version': '1.17', 'alias': 'top',
                       'references': ['lower.nxt'], 'nodes': {
                           '/inst': {},
                           '/overridden': {ENABLED_KEY: False},
                       }}, f)
        self.stage = Session().load_file(top)
        self.comp = self.stage.build_stage()
        self.top = self.stage.top_layer
        self.lower = self.stage._sub_layers[1]

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def set_enabled(self, layer, path, value):
        node = layer.lookup(path)
        self.stage.node_setattr_data(node, ENABLED, layer, create=True,
                                     comp_layer=self.comp, value=value)

    def enabled(self, comp, path):
        return getattr(comp.lookup(path), ENABLED)

    def assert_matches_a_full_comp(self):
        full = self.stage.build_stage()
        for path in ('/src', '/inst', '/inst_of_inst', '/overridden'):
            self.assertEqual(self.enabled(full, path),
                             self.enabled(self.comp, path), path)

    def test_an_instance_can_be_disabled(self):
        self.set_enabled(self.top, '/inst', False)
        self.assertFalse(self.enabled(self.comp, '/inst'))
        self.assert_matches_a_full_comp()

    def test_an_instance_of_it_follows(self):
        self.set_enabled(self.top, '/inst', False)
        self.assertFalse(self.enabled(self.comp, '/inst_of_inst'))
        self.assert_matches_a_full_comp()

    def test_disabling_a_source_disables_its_instances(self):
        self.set_enabled(self.lower, '/src', False)
        self.assertFalse(self.enabled(self.comp, '/inst'))
        self.assert_matches_a_full_comp()

    def test_an_instance_keeps_its_own_opinion_over_its_source(self):
        self.set_enabled(self.top, '/inst', True)
        self.set_enabled(self.lower, '/src', False)
        self.assertTrue(self.enabled(self.comp, '/inst'))
        self.assert_matches_a_full_comp()

    def test_a_stronger_layer_still_wins(self):
        self.set_enabled(self.lower, '/overridden', True)
        self.assertFalse(self.enabled(self.comp, '/overridden'))
        self.assert_matches_a_full_comp()

    def test_reverting_goes_back_to_the_source(self):
        self.set_enabled(self.lower, '/src', False)
        self.set_enabled(self.top, '/inst', True)
        self.set_enabled(self.top, '/inst', None)
        self.assertFalse(self.enabled(self.comp, '/inst'))
        self.assert_matches_a_full_comp()


if __name__ == '__main__':
    unittest.main()
