"""A rename must not move the node.

Position and collapsed state are keyed by node path, and the comp layer
keeps its own copy that build_stage refreshes from the spec layers. A
targeted rename skips that rebuild, so it has to carry them across itself.
It did not, and the renamed node lost its position and went back to the
origin, which reads as the graph rearranging itself.

Only root level nodes carry a position; children are drawn against their
parent. That is exactly the case this got wrong.
"""
# Built-in
import logging
import unittest

# Internal
from nxt import nxt_path
from nxt.session import Session

logging.getLogger('nxt').propagate = False


class RenameKeepsPosition(unittest.TestCase):

    def setUp(self):
        self.stage = Session().new_file()
        self.top = self.stage.top_layer
        self.comp = self.stage.build_stage()

    def add_root_node(self, name, pos):
        self.stage.add_node(name=name, data=None, parent=None,
                            layer=self.top.layer_idx(), comp_layer=self.comp)
        path = nxt_path.join_node_paths(nxt_path.WORLD, name)
        self.top.positions[path] = pos
        self.comp.positions[path] = pos
        return path

    def rename(self, path, new_name):
        node = self.top.lookup(path)
        return self.stage.set_node_name(node, new_name, layer=self.top,
                                        comp_layer=self.comp, force=True)

    def test_the_rename_is_targeted_at_all(self):
        # If this stops being true the rest of the file is testing the
        # rebuild instead, which was never broken.
        path = self.add_root_node('alone', [12.0, 34.0])
        can, why = self.stage.can_rename_targeted(path, '/renamed', self.top,
                                                  self.comp)
        self.assertTrue(can, why)

    def test_position_survives_a_targeted_rename(self):
        path = self.add_root_node('alone', [12.0, 34.0])
        new_path = self.rename(path, 'renamed')
        self.assertEqual('/renamed', new_path)
        self.assertEqual([12.0, 34.0], self.comp.positions.get(new_path),
                         'the comp layer lost the position')
        self.assertEqual([12.0, 34.0], self.top.positions.get(new_path),
                         'the spec layer lost the position')
        self.assertNotIn(path, self.comp.positions)
        self.assertNotIn(path, self.top.positions)

    def test_other_nodes_do_not_move(self):
        keep = self.add_root_node('keep', [100.0, 200.0])
        move = self.add_root_node('move', [300.0, 400.0])
        self.rename(move, 'moved')
        self.assertEqual([100.0, 200.0], self.comp.positions.get(keep),
                         'renaming one node moved another')

    def test_collapsed_state_survives(self):
        path = self.add_root_node('alone', [1.0, 2.0])
        self.top.collapse[path] = True
        self.comp.collapse[path] = True
        new_path = self.rename(path, 'renamed')
        self.assertTrue(self.comp.collapse.get(new_path),
                        'the node forgot it was collapsed')
        self.assertNotIn(path, self.comp.collapse)

    def test_a_rebuild_agrees_with_the_targeted_result(self):
        # The rebuild was always right; the targeted path has to match it.
        path = self.add_root_node('alone', [7.0, 8.0])
        new_path = self.rename(path, 'renamed')
        targeted = dict(self.comp.positions)
        rebuilt = self.stage.build_stage()
        self.assertEqual(targeted.get(new_path),
                         rebuilt.positions.get(new_path))


if __name__ == '__main__':
    unittest.main()
