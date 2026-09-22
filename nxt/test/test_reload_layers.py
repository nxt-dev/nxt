"""Re-reading a layer from disk, without rebuilding the stage around it.

Somebody else saves a file the open graph is built on, and the graph
should be able to go and get it. What arrives is a different set of nodes
for a layer that is otherwise where it was: same place in the stack, same
layer referencing it, same layer object, because a stage holds its layers
by object and so does everything looking at one.

What the file says it references comes back with it, so a reference
added, taken out or moved since the graph was opened lands in the stack:
the layers it now names are loaded, the ones it stopped naming are let
go, and the rest are stacked in the order it gives, because that order
decides whose opinion wins. A reference that is still there keeps the
layer it had, whatever state that layer is in, since nobody asked for
that one to be read again.
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


class ReloadingALayer(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp(prefix='nxt_reload_')
        self.write('deep', node_names=['from_deep'])
        self.write('a', references=['deep.nxt'], node_names=['from_a'])
        self.top_path = self.write('top', references=['a.nxt'],
                                   node_names=['from_top'])
        self.stage = Session().load_file(filepath=self.top_path)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, references=(), node_names=()):
        return write_graph(os.path.join(self.tmp, '%s.nxt' % name), name,
                           references=references, node_names=node_names)

    def layer(self, alias):
        for layer in self.stage._sub_layers:
            if layer.get_alias() == alias:
                return layer
        return None

    def comped(self):
        return sorted(self.stage.build_stage()._nodes_path_as_key)

    # -- what it reads --------------------------------------------------

    def test_it_picks_up_what_the_file_now_says(self):
        self.assertNotIn('/added_since', self.comped())
        self.write('a', references=['deep.nxt'],
                   node_names=['from_a', 'added_since'])
        self.stage.reload_layers([self.layer('a')])
        self.assertIn('/added_since', self.comped())

    def test_it_drops_what_the_file_no_longer_says(self):
        self.write('a', references=['deep.nxt'], node_names=[])
        self.stage.reload_layers([self.layer('a')])
        self.assertNotIn('/from_a', self.comped())

    def test_it_leaves_the_layers_it_was_not_given_alone(self):
        self.write('deep', node_names=['from_deep', 'deep_added'])
        self.write('a', references=['deep.nxt'],
                   node_names=['from_a', 'a_added'])
        self.stage.reload_layers([self.layer('a')])
        self.assertIn('/a_added', self.comped())
        self.assertNotIn('/deep_added', self.comped(),
                         'a layer nobody asked to reload was read anyway')

    def test_a_layer_that_was_never_saved_is_skipped(self):
        stage = Session().new_file()
        self.assertEqual({}, stage.reload_layers([stage.top_layer]))

    # -- and what it keeps ----------------------------------------------

    def test_the_layer_is_the_same_object(self):
        layer = self.layer('a')
        self.write('a', references=['deep.nxt'], node_names=['different'])
        self.stage.reload_layers([layer])
        self.assertIs(layer, self.layer('a'))
        self.assertIn(layer, self.stage._sub_layers,
                      'the graph is holding a layer that is not in the '
                      'stage any more')

    def test_it_stays_where_it_was_in_the_stack(self):
        layer = self.layer('a')
        idx = layer.layer_idx()
        self.write('a', references=['deep.nxt'], node_names=['different'])
        self.stage.reload_layers([layer])
        self.assertEqual(idx, layer.layer_idx())
        self.assertEqual(['top', 'a', 'deep'],
                         [l.get_alias() for l in self.stage._sub_layers])

    def test_the_layer_that_references_it_still_reaches_it(self):
        layer = self.layer('a')
        self.write('a', references=['deep.nxt'], node_names=['different'])
        self.stage.reload_layers([layer])
        self.assertIs(self.stage.top_layer, layer.parent_layer)
        reached = [d.get('layer') for d in self.stage.top_layer.sub_layers]
        self.assertIn(layer, reached)

    def test_what_it_references_is_still_loaded(self):
        layer = self.layer('a')
        self.write('a', references=['deep.nxt'], node_names=['different'])
        self.stage.reload_layers([layer])
        behind = [d.get('layer') for d in layer.sub_layers]
        self.assertEqual([self.layer('deep')], behind)

    def test_a_locked_layer_stays_locked(self):
        # Locking is a local opinion that is never written to a file, so
        # reading the file back must not be able to unlock anything.
        layer = self.layer('a')
        layer.set_locked(True)
        self.write('a', references=['deep.nxt'], node_names=['different'])
        self.stage.reload_layers([layer])
        self.assertTrue(layer.get_locked())

    # -- putting it back ------------------------------------------------

    def test_what_was_there_comes_back_out(self):
        before = self.comped()
        self.write('a', references=['deep.nxt'], node_names=['different'])
        previous = self.stage.reload_layers([self.layer('a')])
        self.assertNotEqual(before, self.comped())
        self.stage.reload_layers([self.layer('a')], source=previous)
        self.assertEqual(before, self.comped(),
                         'a reload could not be undone')

    def test_it_comes_back_without_reading_the_file_again(self):
        # Undoing a reload must put back what was in memory, not whatever
        # the file has come to say in the meantime.
        self.write('a', references=['deep.nxt'], node_names=['first_change'])
        previous = self.stage.reload_layers([self.layer('a')])
        self.write('a', references=['deep.nxt'], node_names=['second_change'])
        self.stage.reload_layers([self.layer('a')], source=previous)
        self.assertIn('/from_a', self.comped())
        self.assertNotIn('/second_change', self.comped())

    # -- what a layer is built from -------------------------------------

    def test_the_dependencies_are_the_layer_and_what_it_references(self):
        found = self.stage.reference_dependencies(self.stage.top_layer)
        self.assertEqual(['top', 'a', 'deep'],
                         [l.get_alias() for l in found])

    def test_they_start_from_the_layer_asked_about(self):
        found = self.stage.reference_dependencies(self.layer('a'))
        self.assertEqual(['a', 'deep'], [l.get_alias() for l in found])

    def test_a_file_referenced_twice_is_two_layers_and_both_are_listed(self):
        # Loading gives a layer per reference, even for the same file, and
        # both of them are in the stack holding their own copy of it. A
        # reload that refreshed one and not the other would leave the
        # graph composited from the file as it was and as it is at once.
        self.write('b', references=['deep.nxt'], node_names=['from_b'])
        self.write('top', references=['a.nxt', 'b.nxt'],
                   node_names=['from_top'])
        self.stage = Session().load_file(filepath=self.top_path)
        found = self.stage.reference_dependencies(self.stage.top_layer)
        self.assertEqual(sorted(['top', 'a', 'b', 'deep', 'deep']),
                         sorted(l.get_alias() for l in found))
        self.assertEqual(len(found), len(set(id(l) for l in found)))

    def test_reloading_a_file_reloads_every_layer_of_it(self):
        self.write('b', references=['deep.nxt'], node_names=['from_b'])
        self.write('top', references=['a.nxt', 'b.nxt'],
                   node_names=['from_top'])
        self.stage = Session().load_file(filepath=self.top_path)
        deeps = [l for l in self.stage._sub_layers
                 if l.get_alias() == 'deep']
        self.assertEqual(2, len(deeps), 'this graph loads it twice')
        self.write('deep', node_names=['from_deep', 'deep_added'])
        self.stage.reload_layers(deeps)
        for layer in deeps:
            self.assertIn('/deep_added', layer._nodes_path_as_key)

    def test_a_reference_that_did_not_resolve_is_left_out(self):
        self.write('top', references=['a.nxt', 'not_here.nxt'],
                   node_names=['from_top'])
        self.stage = Session().load_file(filepath=self.top_path)
        found = self.stage.reference_dependencies(self.stage.top_layer)
        self.assertEqual(['top', 'a', 'deep'],
                         [l.get_alias() for l in found],
                         'there is no layer loaded to go and reload')

    # -- references that changed on disk --------------------------------

    def stacked(self):
        return [l.get_alias() for l in self.stage._sub_layers]

    def test_a_reference_added_since_is_loaded(self):
        self.write('new', node_names=['from_new'])
        self.write('top', references=['a.nxt', 'new.nxt'],
                   node_names=['from_top'])
        self.stage.reload_layers([self.stage.top_layer])
        self.assertEqual(['top', 'a', 'deep', 'new'], self.stacked())
        self.assertIn('/from_new', self.comped())

    def test_what_an_added_reference_references_comes_with_it(self):
        self.write('nested', node_names=['from_nested'])
        self.write('new', references=['nested.nxt'], node_names=['from_new'])
        self.write('top', references=['a.nxt', 'new.nxt'],
                   node_names=['from_top'])
        self.stage.reload_layers([self.stage.top_layer])
        self.assertEqual(['top', 'a', 'deep', 'new', 'nested'],
                         self.stacked())
        self.assertIn('/from_nested', self.comped())

    def test_a_reference_taken_out_since_is_let_go(self):
        self.write('top', references=[], node_names=['from_top'])
        self.stage.reload_layers([self.stage.top_layer])
        self.assertEqual(['top'], self.stacked(),
                         'a layer nothing references any more is still in '
                         'the stack, so its nodes are still comping')
        self.assertEqual(['/from_top'], self.comped())

    def test_the_layers_it_referenced_go_with_it(self):
        self.write('top', references=[], node_names=['from_top'])
        self.stage.reload_layers([self.stage.top_layer])
        self.assertNotIn('/from_deep', self.comped())

    def test_references_put_in_a_different_order_restack(self):
        self.write('b', node_names=['from_b'])
        self.write('top', references=['a.nxt', 'b.nxt'],
                   node_names=['from_top'])
        self.stage = Session().load_file(filepath=self.top_path)
        self.assertEqual(['top', 'a', 'deep', 'b'], self.stacked())
        self.write('top', references=['b.nxt', 'a.nxt'],
                   node_names=['from_top'])
        self.stage.reload_layers([self.stage.top_layer])
        self.assertEqual(['top', 'b', 'a', 'deep'], self.stacked(),
                         'the order references are listed in is the order '
                         'the layers stack, which decides which of them '
                         'wins')
        self.assertEqual(list(range(4)),
                         [l.layer_idx() for l in self.stage._sub_layers])

    def test_a_reference_still_there_keeps_the_layer_it_had(self):
        # Nobody asked for that layer to be read again, so whatever is in
        # it, including work nobody has saved, stays in it.
        deep = self.layer('deep')
        self.write('new', node_names=['from_new'])
        self.write('top', references=['a.nxt', 'new.nxt'],
                   node_names=['from_top'])
        self.stage.reload_layers([self.stage.top_layer])
        self.assertIs(deep, self.layer('deep'))

    def test_a_reference_this_machine_cannot_find_is_kept_as_written(self):
        self.write('top', references=['a.nxt', 'not_here.nxt'],
                   node_names=['from_top'])
        self.stage.reload_layers([self.stage.top_layer])
        self.assertEqual(['a.nxt', 'not_here.nxt'],
                         self.stage.top_layer.get_references(),
                         'a reference that resolves on somebody else\'s '
                         'machine is still what the graph asks for')
        self.assertEqual(['top', 'a', 'deep'], self.stacked())

    def test_undoing_puts_the_stack_back(self):
        before = self.stacked()
        self.write('new', node_names=['from_new'])
        self.write('top', references=['new.nxt'], node_names=['from_top'])
        previous = self.stage.reload_layers([self.stage.top_layer])
        self.assertEqual(['top', 'new'], self.stacked())
        self.stage.reload_layers([self.stage.top_layer], source=previous)
        self.assertEqual(before, self.stacked())
        self.assertIn('/from_deep', self.comped())

    def test_undoing_puts_back_what_a_dropped_layer_held(self):
        # The layer went out of the stage with the reference to it, so
        # what it held has to come back from the undo rather than from
        # the file, which by then may say something else.
        self.write('top', references=[], node_names=['from_top'])
        previous = self.stage.reload_layers([self.stage.top_layer])
        self.write('a', references=['deep.nxt'], node_names=['changed_on_disk'])
        self.stage.reload_layers([self.stage.top_layer], source=previous)
        self.assertIn('/from_a', self.comped())
        self.assertNotIn('/changed_on_disk', self.comped())


if __name__ == '__main__':
    unittest.main()
