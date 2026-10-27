"""A reference is stored as written, so something has to say where it lands.

References are usually partial: a name, or a path relative to a root, or
relative to the layer holding them. Anything showing a person their
references has to resolve them the way loading does, or it will disagree
with what actually opens.
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
from nxt.plugins import file_fallbacks
from nxt.session import Session
from nxt.stage import Stage

logging.getLogger('nxt').propagate = False

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
# A file that is certainly there, referred to three different ways.
KNOWN = 'StageInstanceTest.nxt'


class ReferencePathsResolve(unittest.TestCase):

    def setUp(self):
        self.saved_roots = os.environ.get(file_fallbacks.NXT_FILE_ROOTS)

    def tearDown(self):
        if self.saved_roots is None:
            os.environ.pop(file_fallbacks.NXT_FILE_ROOTS, None)
        else:
            os.environ[file_fallbacks.NXT_FILE_ROOTS] = self.saved_roots
        file_fallbacks._ENV_ROOTS_CACHE.clear()

    def set_roots(self, *roots):
        os.environ[file_fallbacks.NXT_FILE_ROOTS] = os.pathsep.join(roots)
        # The usable roots are cached against the raw variable.
        file_fallbacks._ENV_ROOTS_CACHE.clear()

    def test_an_absolute_path_resolves_to_itself(self):
        absolute = os.path.join(TEST_DIR, KNOWN)
        resolved, found = nxt_io.expand_reference_path(absolute)
        self.assertTrue(found)
        self.assertTrue(os.path.samefile(absolute, resolved))

    def test_a_partial_path_resolves_against_a_root(self):
        self.set_roots(TEST_DIR)
        resolved, found = nxt_io.expand_reference_path(KNOWN)
        self.assertTrue(found, 'NXT_FILE_ROOTS should have found it')
        self.assertTrue(os.path.samefile(os.path.join(TEST_DIR, KNOWN),
                                         resolved))

    def test_roots_are_tried_in_order(self):
        empty = os.path.join(TEST_DIR, 'no_such_root')
        self.set_roots(empty, TEST_DIR)
        resolved, found = nxt_io.expand_reference_path(KNOWN)
        self.assertTrue(found)
        self.assertTrue(os.path.samefile(os.path.join(TEST_DIR, KNOWN),
                                         resolved))

    def test_a_path_relative_to_the_referring_layer(self):
        # No roots at all: a reference written beside its own layer still
        # has to resolve, which is the common case in a graph on disk.
        os.environ.pop(file_fallbacks.NXT_FILE_ROOTS, None)
        file_fallbacks._ENV_ROOTS_CACHE.clear()
        resolved, found = nxt_io.expand_reference_path(KNOWN,
                                                       layer_dir=TEST_DIR)
        self.assertTrue(found, 'should have looked beside the layer')
        self.assertTrue(os.path.samefile(os.path.join(TEST_DIR, KNOWN),
                                         resolved))

    def test_a_missing_reference_says_where_it_looked(self):
        os.environ.pop(file_fallbacks.NXT_FILE_ROOTS, None)
        file_fallbacks._ENV_ROOTS_CACHE.clear()
        resolved, found = nxt_io.expand_reference_path('not_a_real_file.nxt')
        self.assertFalse(found)
        self.assertTrue(resolved, 'where it looked is the useful thing to '
                                  'show, so it is returned either way')
        self.assertIn('not_a_real_file.nxt', resolved.replace(os.sep, '/'))

    def test_an_empty_reference(self):
        self.assertEqual(('', False), nxt_io.expand_reference_path(''))

    def test_environment_variables_expand(self):
        os.environ['NXT_TEST_REF_DIR'] = TEST_DIR
        try:
            resolved, found = nxt_io.expand_reference_path(
                '$NXT_TEST_REF_DIR/' + KNOWN)
            self.assertTrue(found)
            self.assertTrue(os.path.samefile(os.path.join(TEST_DIR, KNOWN),
                                             resolved))
        finally:
            os.environ.pop('NXT_TEST_REF_DIR', None)

    def test_it_agrees_with_what_loading_does(self):
        # The whole point: a preview that disagrees with the loader is
        # worse than no preview.
        self.set_roots(TEST_DIR)
        resolved, found = nxt_io.expand_reference_path(KNOWN)
        self.assertTrue(found)
        data = nxt_io.load_file_data(KNOWN)
        self.assertTrue(data, 'loading found it too')


class RootsWinOverTheLayerDirectory(unittest.TestCase):
    """The same file name beside a layer and under a root.

    Opening a graph lets the root win, which is what lets a working copy
    listed in NXT_FILE_ROOTS stand in for the file a graph sits beside.
    Everything else that resolves a reference has to agree, or the same
    graph loads different files depending on how its layers got there.
    """

    def setUp(self):
        self.saved_roots = os.environ.get(file_fallbacks.NXT_FILE_ROOTS)
        self.saved_cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp(prefix='nxt_ref_roots_')
        self.graph_dir = os.path.join(self.tmp, 'graph')
        self.root_dir = os.path.join(self.tmp, 'root')
        os.makedirs(self.graph_dir)
        os.makedirs(self.root_dir)
        self.write(self.graph_dir, 'top.nxt', 'top', ['mid.nxt'])
        self.write(self.graph_dir, 'mid.nxt', 'mid', ['leaf.nxt'])
        self.write(self.graph_dir, 'leaf.nxt', 'leaf_beside')
        self.write(self.root_dir, 'leaf.nxt', 'leaf_under_root')
        os.environ[file_fallbacks.NXT_FILE_ROOTS] = self.root_dir
        file_fallbacks._ENV_ROOTS_CACHE.clear()
        # Somewhere that is neither, the way an editor session is.
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.saved_cwd)
        if self.saved_roots is None:
            os.environ.pop(file_fallbacks.NXT_FILE_ROOTS, None)
        else:
            os.environ[file_fallbacks.NXT_FILE_ROOTS] = self.saved_roots
        file_fallbacks._ENV_ROOTS_CACHE.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def write(directory, name, alias, references=()):
        with open(os.path.join(directory, name), 'w') as file_object:
            json.dump({'version': '1.17', 'alias': alias,
                       'references': list(references)}, file_object)

    def test_opening_the_graph_takes_the_root(self):
        stage = Session().load_file(os.path.join(self.graph_dir, 'top.nxt'))
        aliases = [layer.get_alias() for layer in stage._sub_layers]
        self.assertIn('leaf_under_root', aliases)

    def test_adding_a_reference_takes_the_root_too(self):
        # What the editor does when a reference is added: the layer comes
        # in through new_sublayer, and its own references with it.
        mid = os.path.join(self.graph_dir, 'mid.nxt')
        stage = Stage()
        stage.new_sublayer(layer_data=nxt_io.load_file_data(mid), idx=0)
        aliases = [layer.get_alias() for layer in stage._sub_layers]
        self.assertIn('leaf_under_root', aliases)
        self.assertNotIn('leaf_beside', aliases)

    def test_the_preview_shows_the_root(self):
        resolved, found = nxt_io.expand_reference_path(
            'leaf.nxt', layer_dir=self.graph_dir)
        self.assertTrue(found)
        self.assertTrue(os.path.samefile(
            os.path.join(self.root_dir, 'leaf.nxt'), resolved))

    def test_beside_the_layer_when_no_root_has_it(self):
        os.remove(os.path.join(self.root_dir, 'leaf.nxt'))
        resolved, found = nxt_io.expand_reference_path(
            'leaf.nxt', layer_dir=self.graph_dir)
        self.assertTrue(found)
        self.assertTrue(os.path.samefile(
            os.path.join(self.graph_dir, 'leaf.nxt'), resolved))

    def test_the_working_directory_is_not_the_layers(self):
        # A file of the same name where the session happens to be is not
        # what the layer means, when the layer's own directory is known.
        os.remove(os.path.join(self.root_dir, 'leaf.nxt'))
        os.remove(os.path.join(self.graph_dir, 'leaf.nxt'))
        self.write(self.tmp, 'leaf.nxt', 'leaf_in_cwd')
        resolved, found = nxt_io.expand_reference_path(
            'leaf.nxt', layer_dir=self.graph_dir)
        self.assertFalse(found)
        self.assertTrue(os.path.samefile(self.graph_dir,
                                         os.path.dirname(resolved)))


if __name__ == '__main__':
    unittest.main()
