"""Save As somewhere else keeps a layer's relative references working.

A reference relative to the layer's folder means a different file once the
layer is saved in another folder, so the copy lost every one of them.
Those references are stored again from the new folder: relative when the
file is beside it, whole when not. Anything that does not depend on the
layer's folder is left as written.
"""
# Builtin
import json
import os
import shutil
import tempfile
import unittest

# Internal
from nxt import nxt_io
from nxt.plugins import file_fallbacks
from nxt.session import Session


def write_graph(path, alias, references=(), overrides=None):
    data = {'version': '1.17', 'alias': alias,
            'references': list(references), 'nodes': {'/' + alias: {}}}
    if overrides:
        data['comp_overrides'] = overrides
    with open(path, 'w') as file_object:
        json.dump(data, file_object)
    return path


class SaveAsKeepsReferences(unittest.TestCase):

    def setUp(self):
        self.saved_roots = os.environ.pop(file_fallbacks.NXT_FILE_ROOTS, None)
        file_fallbacks._ENV_ROOTS_CACHE.clear()
        self.cwd = os.getcwd()
        # Resolved, since nxt writes resolved paths and a temp folder
        # can have a short name on Windows.
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix='nxt_save_as_'))
        self.graph_dir = os.path.join(self.tmp, 'graph')
        self.copy_dir = os.path.join(self.tmp, 'copy')
        self.root_dir = os.path.join(self.tmp, 'root')
        for folder in (self.graph_dir, self.copy_dir, self.root_dir):
            os.makedirs(folder)
        self.beside = write_graph(os.path.join(self.graph_dir, 'beside.nxt'),
                                  'beside')
        write_graph(os.path.join(self.root_dir, 'lib.nxt'), 'lib')
        self.absolute = write_graph(os.path.join(self.tmp, 'abs.nxt'), 'abs')
        self.references = ['beside.nxt', 'lib.nxt',
                           self.absolute.replace(os.sep, '/'),
                           'missing.nxt']
        self.top = write_graph(
            os.path.join(self.graph_dir, 'top.nxt'), 'top', self.references,
            overrides={'beside.nxt': {'mute': True}})
        os.environ[file_fallbacks.NXT_FILE_ROOTS] = self.root_dir
        file_fallbacks._ENV_ROOTS_CACHE.clear()

    def tearDown(self):
        os.chdir(self.cwd)
        if self.saved_roots is None:
            os.environ.pop(file_fallbacks.NXT_FILE_ROOTS, None)
        else:
            os.environ[file_fallbacks.NXT_FILE_ROOTS] = self.saved_roots
        file_fallbacks._ENV_ROOTS_CACHE.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def save_copy(self):
        stage = Session().load_file(self.top)
        copy_path = os.path.join(self.copy_dir, 'top.nxt')
        stage.top_layer.save(copy_path)
        with open(copy_path) as file_object:
            return stage, copy_path, json.load(file_object)

    def test_a_reference_beside_the_old_folder_is_stored_whole(self):
        _, _, data = self.save_copy()
        self.assertIn(self.beside.replace(os.sep, '/'), data['references'])
        self.assertNotIn('beside.nxt', data['references'])

    def test_the_copy_opens_with_its_references(self):
        _, copy_path, _ = self.save_copy()
        stage = Session().load_file(copy_path)
        aliases = [layer.get_alias() for layer in stage._sub_layers]
        for alias in ('beside', 'lib', 'abs'):
            self.assertIn(alias, aliases)

    def test_what_does_not_depend_on_the_folder_is_left_alone(self):
        _, _, data = self.save_copy()
        # Found through a root, absolute, and missing.
        self.assertIn('lib.nxt', data['references'])
        self.assertIn(self.absolute.replace(os.sep, '/'), data['references'])
        self.assertIn('missing.nxt', data['references'])

    def test_the_order_is_kept(self):
        _, _, data = self.save_copy()
        self.assertEqual(len(self.references), len(data['references']))
        self.assertEqual('lib.nxt', data['references'][1])

    def test_overrides_follow_their_reference(self):
        _, _, data = self.save_copy()
        overrides = data.get('comp_overrides', {})
        self.assertNotIn('beside.nxt', overrides)
        self.assertEqual({'mute': True},
                         overrides.get(self.beside.replace(os.sep, '/')))

    def test_a_plain_save_afterwards_writes_the_same(self):
        stage, copy_path, first = self.save_copy()
        stage.top_layer.save()
        with open(copy_path) as file_object:
            again = json.load(file_object)
        self.assertEqual(first['references'], again['references'])

    def test_the_original_is_untouched(self):
        self.save_copy()
        with open(self.top) as file_object:
            original = json.load(file_object)
        self.assertEqual(self.references, original['references'])

    def test_saving_beside_the_original_changes_nothing(self):
        stage = Session().load_file(self.top)
        other = os.path.join(self.graph_dir, 'top_v2.nxt')
        stage.top_layer.save(other)
        with open(other) as file_object:
            data = json.load(file_object)
        self.assertEqual(self.references, data['references'])

    def test_a_copy_leaves_the_layer_as_it_was(self):
        # The editor's Save As writes a copy and keeps working on the
        # original, so the original's references must not change.
        stage = Session().load_file(self.top)
        layer = stage.top_layer
        copy_path = os.path.join(self.copy_dir, 'top.nxt')
        layer.save(copy_path, as_copy=True)
        self.assertEqual(self.references, layer.get_references())
        # The same file, however the temp folder happens to be spelled.
        self.assertTrue(os.path.samefile(self.top, layer.real_path))
        with open(copy_path) as file_object:
            data = json.load(file_object)
        self.assertIn(self.beside.replace(os.sep, '/'), data['references'])
        self.assertEqual({'mute': True}, data['comp_overrides'].get(
            self.beside.replace(os.sep, '/')))
        layer.save()
        with open(self.top) as file_object:
            original = json.load(file_object)
        self.assertEqual(self.references, original['references'])

    def test_a_file_beside_the_new_folder_stays_relative(self):
        self.assertEqual('x.nxt', nxt_io.stored_reference_path(
            os.path.join(self.copy_dir, 'x.nxt'), self.copy_dir))


if __name__ == '__main__':
    unittest.main()
