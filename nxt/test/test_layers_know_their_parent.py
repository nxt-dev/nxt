"""A loaded layer is wired to the layer that references it, right away.

The link runs both ways: a referenced layer knows its parent from the
moment it is built, but the parent's own list of references held nothing
but a file path until somebody composited the whole stack, which is what
filled the layer object in. Anything that walks a layer's references to
find the layers behind them -- removing a reference is the one that bites
-- saw nothing there and did nothing, and the layer stayed in the stage
with its nodes still comping.

Compositing from part way down the stack only walks the layers below the
index it starts at, so it never wired the ones above. A stage composited
only through a lower layer, which is what looking at a graph through one
of its references does, was left half wired for the rest of its life.
"""
# Built-in
import json
import os
import shutil
import tempfile
import unittest

# Internal
from nxt.session import Session


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


class LayersKnowTheirParent(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp(prefix='nxt_layer_parents_')
        for name in ('a', 'b', 'c'):
            write_graph(os.path.join(self.tmp, '%s.nxt' % name), name,
                        node_names=['from_%s' % name])
        self.top_path = write_graph(
            os.path.join(self.tmp, 'top.nxt'), 'top',
            references=['a.nxt', 'b.nxt', 'c.nxt'],
            node_names=['from_top'])
        self.stage = Session().load_file(filepath=self.top_path)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def referenced_layers(self):
        """The layers the top layer's references point at."""
        return [d.get('layer') for d in self.stage.top_layer.sub_layers]

    def aliases(self):
        return [layer.get_alias() for layer in self.stage._sub_layers]

    def test_loading_wires_every_reference(self):
        self.assertEqual([], [l for l in self.referenced_layers()
                              if l is None],
                         'a reference was left pointing at nothing, so '
                         'anything following it finds no layer to work on')

    def test_they_are_the_layers_in_the_stage(self):
        for layer in self.referenced_layers():
            self.assertIn(layer, self.stage._sub_layers)

    def test_compositing_part_way_down_leaves_them_wired(self):
        # What looking at a graph through one of its references does.
        self.stage.build_stage(from_idx=3)
        self.assertEqual([], [l for l in self.referenced_layers()
                              if l is None])

    def test_references_can_be_taken_out_through_their_parent(self):
        # How setting a layer's references starts: walk what the layer
        # references and take out the layer each one points at.
        for ref_data in list(self.stage.top_layer.sub_layers):
            layer = ref_data.get('layer')
            if layer is not None:
                self.stage.remove_sublayer(layer)
        self.assertEqual(['top'], self.aliases(),
                         'a reference pointing at nothing left its layer '
                         'in the stage, with its nodes still comping')


if __name__ == '__main__':
    unittest.main()
