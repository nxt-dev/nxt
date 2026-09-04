"""Node attributes must be the ones the user authored, and nothing python
happens to put on a class.

Python 3.13 started writing __firstlineno__ and __static_attributes__ onto
classes declared in source. INTERNAL_ATTRS.BUILTINS is built by asking a
probe class what it has, and the probe was made with type(), which the
compiler does not decorate the same way. So those two leaked through as
user attributes: they showed up in the property editor, took part in the
comp, resolved to strings, and were written to save files.
"""
# Built-in
import logging
import os
import unittest

# Internal
from nxt.nxt_node import INTERNAL_ATTRS
from nxt.session import Session

logging.getLogger('nxt').propagate = False


class BuiltinAttrsAreFiltered(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.chdir(os.path.dirname(__file__))
        cls.stage = Session().load_file(filepath="StageInheritTest.nxt")
        cls.comp_layer = cls.stage.build_stage()

    def test_no_dunders_reach_node_attrs(self):
        """Whatever python decorates a class with is not a node attribute."""
        for path in self.comp_layer._nodes_path_as_key:
            node = self.comp_layer.lookup(path)
            leaked = [name for name in self.stage.get_node_attr_names(node)
                      if name.startswith('__') and name.endswith('__')]
            self.assertEqual([], leaked,
                             '%s exposes python internals as attrs' % path)

    def test_the_probes_cover_both_kinds_of_class(self):
        """A class from type() and one declared in source can differ.

        Asking only one of them is what let the 3.13 additions through.
        """
        made_with_type = set(dir(type('Probe', (object,), {})))

        class Declared(object):
            pass

        declared = set(dir(Declared))
        for name in made_with_type | declared:
            self.assertIn(name, INTERNAL_ATTRS.PROTECTED,
                          '%s is on a plain class but not protected' % name)

    def test_known_313_additions_are_protected(self):
        # Named outright so a future reader can see what this is guarding,
        # even on a python that does not add them.
        for name in ('__firstlineno__', '__static_attributes__'):
            if hasattr(BuiltinAttrsAreFiltered, name):
                self.assertIn(name, INTERNAL_ATTRS.PROTECTED)


if __name__ == '__main__':
    unittest.main()
