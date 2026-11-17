"""Renaming an attr can update the tokens that refer to it.

Asked to, a rename rewrites every attr ref token in the layer that resolved
to the renamed attr, and leaves alone tokens that resolve to some other
attr of the same name.
"""
# Builtin
import json
import os
import shutil
import tempfile
import unittest

# Internal
from nxt import DATA_STATE
from nxt.session import Session
from nxt.nxt_node import INTERNAL_ATTRS

CODE = INTERNAL_ATTRS.COMPUTE
INST_KEY = INTERNAL_ATTRS.as_save_key(INTERNAL_ATTRS.INSTANCE_PATH)

NODES = {
    '/N': {'attrs': {'x': {'value': '1'}, 'y': {'value': '${x}0'}},
           'code': ['a = ${x}', 'b = ${/N.x}']},
    '/N/child': {'code': ['${x} + ${y}']},
    '/N/own': {'attrs': {'x': {'value': '2'}}, 'code': ['${x}']},
    '/M': {'attrs': {'ref': {'value': '${../N.x}'}},
           'code': ['${/N.x}', '${/N/child.x}', '${/N/own.x}']},
    '/I': {INST_KEY: '/N', 'code': ['${x}']},
    '/Z': {'attrs': {'x': {'value': 'z'}}, 'code': ['${x}']},
}


class RenameAttrRefs(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def save(self, name, nodes, references=()):
        path = os.path.join(self.folder, name + '.nxt')
        with open(path, 'w') as f:
            json.dump({'version': '1.17', 'alias': name,
                       'references': list(references), 'nodes': nodes}, f)
        return path

    def load(self, nodes):
        stage = Session().load_file(self.save('graph', nodes))
        return stage, stage.top_layer

    def code(self, layer, path):
        return getattr(layer.lookup(path), CODE)

    def rename(self, stage, layer, refactor):
        comp = stage.build_stage()
        return stage.rename_node_attr(layer.lookup('/N'), 'x', 'size', layer,
                                      refactor=refactor, comp_layer=comp)

    def test_tokens_that_resolved_to_the_attr_follow_it(self):
        stage, layer = self.load(NODES)
        self.rename(stage, layer, refactor=True)
        self.assertEqual(['a = ${size}', 'b = ${/N.size}'],
                         self.code(layer, '/N'))
        self.assertEqual('${size}0', getattr(layer.lookup('/N'), 'y'))
        self.assertEqual(['${size} + ${y}'], self.code(layer, '/N/child'))
        self.assertEqual(['${/N.size}', '${/N/child.size}', '${/N/own.x}'],
                         self.code(layer, '/M'))
        self.assertEqual('${../N.size}', getattr(layer.lookup('/M'), 'ref'))
        self.assertEqual(['${size}'], self.code(layer, '/I'))
        # Tokens resolving to another attr called x are left alone
        self.assertEqual(['${x}'], self.code(layer, '/N/own'))
        self.assertEqual(['${x}'], self.code(layer, '/Z'))
        # And everything still resolves the same
        comp = stage.build_stage()
        resolved = stage.get_node_code_lines(comp.lookup('/N/child'), comp,
                                             DATA_STATE.RESOLVED)
        self.assertEqual(['1 + 10'], resolved)

    def test_revert_puts_tokens_back(self):
        stage, layer = self.load(NODES)
        changes = self.rename(stage, layer, refactor=True)
        stage.rename_node_attr(layer.lookup('/N'), 'size', 'x', layer)
        stage.apply_attr_ref_changes(changes, layer, revert=True)
        for path, data in NODES.items():
            self.assertEqual(data.get('code'), self.code(layer, path), path)
        self.assertEqual('${x}0', getattr(layer.lookup('/N'), 'y'))

    def test_plain_rename_leaves_tokens(self):
        stage, layer = self.load(NODES)
        self.assertEqual([], self.rename(stage, layer, refactor=False))
        self.assertEqual(['a = ${x}', 'b = ${/N.x}'], self.code(layer, '/N'))

    def test_attr_still_given_by_another_layer(self):
        lower = self.save('lower', {'/N': {'attrs': {'x': {'value': '0'}}}})
        top = self.save('top', NODES, references=[os.path.basename(lower)])
        stage = Session().load_file(top)
        layer = stage.top_layer
        self.assertEqual([], self.rename(stage, layer, refactor=True))
        self.assertEqual(['a = ${x}', 'b = ${/N.x}'], self.code(layer, '/N'))
