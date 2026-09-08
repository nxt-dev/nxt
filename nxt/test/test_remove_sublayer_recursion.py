"""Removing a layer has to take everything it brought with it.

Layers reference layers. Taking one out of the stage means taking out the
ones it pulled in, or their nodes go on comping with nothing in the stack
asking for them.

The loop that did this walked the list of sub layers while emptying it.
Removing from a list you are iterating skips every other entry, so a layer
with two references only ever recursed into the first. Removing one layer
from a rig left half of what it brought behind: the top of the tree went,
some of the middle went, and whatever was second in each list stayed with
its nodes still in the graph.
"""
# Built-in
import json
import logging
import os
import shutil
import tempfile
import unittest

# Internal
from nxt.session import Session

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


class RemovingALayerTakesItsSubtree(unittest.TestCase):
    """The shape a rig actually has: parts that pull in shared pieces."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nxt_rmsub_')
        self.write('utils')
        self.write('rig_components')
        self.write('builtins')
        # body and face each pull in two of their own.
        self.write('body', references=['utils.nxt', 'rig_components.nxt'])
        self.write('face', references=['builtins.nxt', 'utils.nxt'])
        self.write('spine')
        self.top_path = self.write('biped',
                                   references=['body.nxt', 'face.nxt',
                                               'spine.nxt'])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, references=()):
        return write_graph(os.path.join(self.tmp, '%s.nxt' % name), name,
                           references=references,
                           node_names=['from_%s' % name])

    def open_graph(self):
        stage = Session().load_file(filepath=self.top_path)
        # Loading leaves each reference entry without the layer it opened;
        # compositing is what fills those in, and the editor always comps.
        # Removing a layer walks those entries, so it has nothing to walk
        # until this has happened.
        stage.build_stage()
        return stage

    def aliases(self, stage):
        return sorted(l.get_alias() for l in stage._sub_layers)

    def comped(self, stage):
        return sorted(stage.build_stage()._nodes_path_as_key)

    def layer(self, stage, alias):
        for layer in stage._sub_layers:
            if layer.get_alias() == alias:
                return layer
        return None

    # -- the whole tree opens ------------------------------------------

    def test_everything_is_there_to_start_with(self):
        # utils twice: body and face each reference it, and each gets its
        # own. They are different layers that happen to come from one file.
        stage = self.open_graph()
        self.assertEqual(['biped', 'body', 'builtins', 'face',
                          'rig_components', 'spine', 'utils', 'utils'],
                         self.aliases(stage))

    # -- and leaves together -------------------------------------------

    def test_removing_a_layer_takes_both_of_its_references(self):
        # The one that was broken: rig_components is second in body's
        # list, so the loop skipped it.
        stage = self.open_graph()
        self.stage_remove(stage, 'body')
        remaining = self.aliases(stage)
        self.assertNotIn('body', remaining)
        self.assertNotIn('rig_components', remaining,
                         'the second reference of the removed layer stayed '
                         'in the stage')

    def test_its_nodes_go_with_it(self):
        stage = self.open_graph()
        self.stage_remove(stage, 'body')
        comped = self.comped(stage)
        self.assertNotIn('/from_body', comped)
        self.assertNotIn('/from_rig_components', comped,
                         'a layer nobody references any more is still '
                         'comping its nodes into the graph')

    def test_removing_two_layers(self):
        # body and face between them bring in everything except spine.
        stage = self.open_graph()
        self.stage_remove(stage, 'body')
        self.stage_remove(stage, 'face')
        self.assertEqual(['biped', 'spine'], self.aliases(stage))
        self.assertEqual(['/from_biped', '/from_spine'], self.comped(stage))

    def test_nothing_comped_comes_from_a_layer_that_left(self):
        stage = self.open_graph()
        self.stage_remove(stage, 'body')
        self.stage_remove(stage, 'face')
        loaded = set()
        for layer in stage._sub_layers:
            loaded.update(layer._nodes_path_as_key)
        for node_path in self.comped(stage):
            self.assertIn(node_path, loaded,
                          '%s is comped but no loaded layer has it'
                          % node_path)

    def test_a_layer_something_else_still_wants_stays(self):
        # utils is pulled in by both body and face. Removing one of them
        # must not take it from the other.
        stage = self.open_graph()
        self.stage_remove(stage, 'body')
        self.assertIn('utils', self.aliases(stage),
                      'face still references utils, so it should have '
                      'stayed')
        self.assertIn('/from_utils', self.comped(stage))

    def test_a_sibling_keeps_its_own_reference(self):
        # face references utils too. Removing body takes body's copy, and
        # must leave face still asking for it: face is saveable, and a
        # reference quietly taken off it is written out of the file.
        stage = self.open_graph()
        self.stage_remove(stage, 'body')
        face = self.layer(stage, 'face')
        self.assertIn('utils.nxt', face.sub_layer_paths,
                      "face's own reference was taken off it because "
                      "another layer referencing the same file was removed")
        self.assertEqual(['builtins.nxt', 'utils.nxt'],
                         sorted(face.get_references()))

    def test_the_removed_layers_own_references_are_untouched_on_disk(self):
        stage = self.open_graph()
        self.stage_remove(stage, 'body')
        with open(os.path.join(self.tmp, 'face.nxt')) as file_object:
            on_disk = json.load(file_object)
        self.assertEqual(['builtins.nxt', 'utils.nxt'],
                         sorted(on_disk['references']))

    def stage_remove(self, stage, alias):
        layer = self.layer(stage, alias)
        self.assertIsNotNone(layer, 'no layer called %s' % alias)
        stage.remove_sublayer(layer)


class RemovingALayerWithAnUnresolvedReference(unittest.TestCase):
    """A reference that never opened has no layer behind it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nxt_rmsub_missing_')
        write_graph(os.path.join(self.tmp, 'part.nxt'), 'part',
                    references=['$NXT_NO_SUCH_ROOT/lib/gone.nxt'],
                    node_names=['from_part'])
        self.top_path = write_graph(os.path.join(self.tmp, 'top.nxt'), 'top',
                                    references=['part.nxt'],
                                    node_names=['from_top'])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_removing_it_does_not_throw(self):
        stage = Session().load_file(filepath=self.top_path)
        part = [l for l in stage._sub_layers
                if l.get_alias() == 'part'][0]
        stage.remove_sublayer(part)
        self.assertEqual(['top'],
                         [l.get_alias() for l in stage._sub_layers])
        self.assertEqual(['/from_top'],
                         sorted(stage.build_stage()._nodes_path_as_key))


if __name__ == '__main__':
    unittest.main()
