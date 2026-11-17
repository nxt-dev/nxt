"""A file picked from under a root is stored relative to that root.

A reference typed as `shared/rig.nxt` is found through NXT_FILE_ROOTS on any
machine. The same file picked in a file browser used to be stored as the
whole path it was picked at, which only loads on that machine, so graphs
built by picking and graphs built by typing behaved differently.

The rule stays narrow. Beside the layer still wins. A root relative path
is only stored when it resolves back to the very file that was picked, and
never with `..` in it. Nothing is rewritten on save: this is only how a
picked file is written down.
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

logging.getLogger('nxt').propagate = False


class RootRelativeCase(unittest.TestCase):

    def setUp(self):
        self.saved_roots = os.environ.get(file_fallbacks.NXT_FILE_ROOTS)
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix='nxt_root_ref_'))
        self.project = self.folder('project')
        self.first_root = self.folder('first_root')
        self.second_root = self.folder('second_root')
        self.elsewhere = self.folder('elsewhere')
        self.set_roots(self.first_root, self.second_root)

    def tearDown(self):
        if self.saved_roots is None:
            os.environ.pop(file_fallbacks.NXT_FILE_ROOTS, None)
        else:
            os.environ[file_fallbacks.NXT_FILE_ROOTS] = self.saved_roots
        file_fallbacks._ENV_ROOTS_CACHE.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def folder(self, *parts):
        path = os.path.join(self.tmp, *parts)
        os.makedirs(path)
        return path

    def set_roots(self, *roots):
        os.environ[file_fallbacks.NXT_FILE_ROOTS] = \
            file_fallbacks.ROOT_PATH_SEP.join(roots)
        file_fallbacks._ENV_ROOTS_CACHE.clear()

    @staticmethod
    def write(directory, name, alias='layer', references=()):
        if not os.path.isdir(directory):
            os.makedirs(directory)
        path = os.path.join(directory, name)
        with open(path, 'w') as file_object:
            json.dump({'version': '1.17', 'alias': alias,
                       'references': list(references)}, file_object)
        return path


class PickedFromUnderARoot(RootRelativeCase):

    def test_stored_relative_to_the_root(self):
        picked = self.write(os.path.join(self.first_root, 'shared'),
                            'rig.nxt')
        self.assertEqual('shared/rig.nxt', nxt_io.stored_reference_path(
            picked, self.project))

    def test_any_root_will_do(self):
        picked = self.write(self.second_root, 'rig.nxt')
        self.assertEqual('rig.nxt', nxt_io.stored_reference_path(
            picked, self.project))

    def test_it_loads_from_where_it_was_picked(self):
        picked = self.write(os.path.join(self.first_root, 'shared'),
                            'rig.nxt', alias='picked')
        stored = nxt_io.stored_reference_path(picked, self.project)
        top = self.write(self.project, 'top.nxt', 'top', [stored])
        stage = Session().load_file(top)
        self.assertIn('picked',
                      [layer.get_alias() for layer in stage._sub_layers])

    def test_a_layer_that_was_never_saved(self):
        # No folder to be beside yet, but a root is a root from anywhere.
        picked = self.write(self.first_root, 'rig.nxt')
        self.assertEqual('rig.nxt',
                         nxt_io.stored_reference_path(picked, None))


class WhatStaysAsItWas(RootRelativeCase):

    def test_beside_the_layer_still_wins(self):
        # The project is itself under a root here, and the file is beside
        # the layer: relative to the layer is the shorter, older answer.
        self.set_roots(self.tmp)
        picked = self.write(self.project, 'beside.nxt')
        self.assertEqual('beside.nxt', nxt_io.stored_reference_path(
            picked, self.project))

    def test_under_no_root_is_stored_whole(self):
        picked = self.write(self.elsewhere, 'rig.nxt')
        self.assertEqual(picked.replace(os.path.sep, '/'),
                         nxt_io.stored_reference_path(picked, self.project))

    def test_no_roots_at_all(self):
        os.environ.pop(file_fallbacks.NXT_FILE_ROOTS)
        file_fallbacks._ENV_ROOTS_CACHE.clear()
        picked = self.write(self.first_root, 'rig.nxt')
        self.assertEqual(picked.replace(os.path.sep, '/'),
                         nxt_io.stored_reference_path(picked, self.project))

    def test_never_up_and_out_of_a_root(self):
        picked = self.write(self.elsewhere, 'rig.nxt')
        stored = nxt_io.stored_reference_path(picked, self.project)
        self.assertNotIn('..', stored)

    def test_a_file_an_earlier_root_would_hide_is_stored_whole(self):
        # Stored as rig.nxt, loading would take the first root's file,
        # which is not the one that was picked.
        self.write(self.first_root, 'rig.nxt', alias='hides_it')
        picked = self.write(self.second_root, 'rig.nxt', alias='picked')
        self.assertEqual(picked.replace(os.path.sep, '/'),
                         nxt_io.stored_reference_path(picked, self.project))


class Compactors(RootRelativeCase):

    def test_one_that_raises_is_passed_over(self):
        def broken(path):
            raise RuntimeError('not today')
        nxt_io.plugin_compactors.insert(0, broken)
        self.addCleanup(nxt_io.plugin_compactors.remove, broken)
        picked = self.write(self.first_root, 'rig.nxt')
        self.assertEqual('rig.nxt', nxt_io.stored_reference_path(
            picked, self.project))

    def test_one_that_points_somewhere_else_is_not_believed(self):
        self.write(self.first_root, 'other.nxt')

        def wrong(path):
            return 'other.nxt'
        nxt_io.plugin_compactors.insert(0, wrong)
        self.addCleanup(nxt_io.plugin_compactors.remove, wrong)
        picked = self.write(self.first_root, 'rig.nxt')
        self.assertEqual('rig.nxt', nxt_io.stored_reference_path(
            picked, self.project))


if __name__ == '__main__':
    unittest.main()
