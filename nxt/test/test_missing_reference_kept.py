"""A reference this machine cannot find is still the graph's reference.

Loading used to drop a reference it failed to open, out of the layer's
lists entirely. The graph still ran, so it looked harmless, but the layer
in memory no longer said what the file on disk said: the next save of that
layer wrote it out without the reference, and it was gone for everyone.

Somebody opening a graph whose references live on a share they are not on
should not be able to delete those references by saving. So the reference
is kept as written, the failure is logged, and the comp simply goes on
without it.
"""
# Built-in
import json
import logging
import os
import shutil
import tempfile
import unittest

# Internal
from nxt import nxt_io
from nxt.session import Session

# The failed open is logged, and these tests cause it on purpose.
logging.getLogger('nxt').propagate = False


def write_graph(path, name, references=(), node_names=()):
    data = {
        "version": "1.17",
        "alias": name,
        "mute": False,
        "solo": False,
        "references": list(references),
        "meta_data": {},
        "nodes": {"/" + n: {} for n in node_names},
    }
    with open(path, 'w') as file_object:
        json.dump(data, file_object, indent=4)
    return path


class MissingReferencesSurviveLoading(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nxt_missing_ref_')
        write_graph(os.path.join(self.tmp, 'a.nxt'), 'a',
                    node_names=['from_a'])
        write_graph(os.path.join(self.tmp, 'b.nxt'), 'b',
                    node_names=['from_b'])
        self.top_path = os.path.join(self.tmp, 'top.nxt')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def open_graph(self, references):
        write_graph(self.top_path, 'top', references=references,
                    node_names=['from_top'])
        return Session().load_file(filepath=self.top_path)

    def on_disk(self):
        with open(self.top_path) as file_object:
            return json.load(file_object)['references']

    def test_it_is_kept_on_the_layer(self):
        stage = self.open_graph(['a.nxt', 'not_here.nxt'])
        self.assertEqual(['a.nxt', 'not_here.nxt'],
                         stage.top_layer.get_references(),
                         'the reference the file declares was dropped')

    def test_saving_does_not_delete_it(self):
        # The whole point. Open, save for any reason, and the file should
        # still say what it said.
        stage = self.open_graph(['a.nxt', 'not_here.nxt'])
        stage.top_layer.save()
        self.assertEqual(['a.nxt', 'not_here.nxt'], self.on_disk(),
                         'saving wrote the missing reference out of the file')

    def test_order_is_kept(self):
        # References are a stack, so a missing one still holds its place.
        stage = self.open_graph(['a.nxt', 'not_here.nxt', 'b.nxt'])
        self.assertEqual(['a.nxt', 'not_here.nxt', 'b.nxt'],
                         stage.top_layer.get_references())

    def test_the_graph_still_comps_without_it(self):
        stage = self.open_graph(['a.nxt', 'not_here.nxt', 'b.nxt'])
        comp = stage.build_stage()
        comped = comp._nodes_path_as_key
        self.assertIn('/from_top', comped)
        self.assertIn('/from_a', comped,
                      'a reference that does resolve should still load')
        self.assertIn('/from_b', comped,
                      'a missing reference should not stop the ones after it')

    def test_the_missing_layer_is_not_pretended_into_existence(self):
        # Kept as a reference, not faked as a loaded layer. Anything
        # walking the open layers should see only what really opened.
        stage = self.open_graph(['a.nxt', 'not_here.nxt'])
        aliases = [layer.get_alias() for layer in stage._sub_layers]
        self.assertEqual(['top', 'a'], aliases)

    def test_a_reference_that_is_all_there_is_unaffected(self):
        stage = self.open_graph(['a.nxt'])
        self.assertEqual(['a.nxt'], stage.top_layer.get_references())
        stage.top_layer.save()
        self.assertEqual(['a.nxt'], self.on_disk())


class AddingALayerWhoseOwnReferenceIsMissing(unittest.TestCase):
    """Building a layer stack walks nested references and opens each one.

    Keeping references that do not resolve means they now reach here,
    where loading used to prune them before anything else saw them. This
    threw on the first file it could not read, and the callers are usually
    partway through rebuilding a stack, so the stage was left with layers
    taken out and nothing put back.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nxt_nested_')
        # rig references something not on this machine.
        write_graph(os.path.join(self.tmp, 'rig.nxt'), 'rig',
                    references=['$NXT_NO_SUCH_ROOT/lib/muscles.nxt'],
                    node_names=['from_rig'])
        self.top_path = os.path.join(self.tmp, 'top.nxt')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_opening_it(self):
        write_graph(self.top_path, 'top', references=['rig.nxt'],
                    node_names=['from_top'])
        stage = Session().load_file(filepath=self.top_path)
        self.assertEqual(['top', 'rig'],
                         [l.get_alias() for l in stage._sub_layers])
        comped = stage.build_stage()._nodes_path_as_key
        self.assertIn('/from_rig', comped)
        self.assertIn('/from_top', comped)

    def test_adding_it_as_a_sublayer(self):
        # The path that threw: new_sublayer walking rig's own references.
        write_graph(self.top_path, 'top', node_names=['from_top'])
        stage = Session().load_file(filepath=self.top_path)
        top = stage.top_layer
        real_path = os.path.join(self.tmp, 'rig.nxt')
        layer_data = nxt_io.load_file_data(real_path)
        layer_data.update({'parent_layer': top,
                           'filepath': 'rig.nxt',
                           'real_path': real_path,
                           'alias': layer_data.get('name')})
        stage.new_sublayer(layer_data=layer_data, idx=1)
        self.assertEqual(['top', 'rig'],
                         [l.get_alias() for l in stage._sub_layers])
        self.assertIn('/from_rig', stage.build_stage()._nodes_path_as_key)


if __name__ == '__main__':
    unittest.main()
