"""A file picked from a folder an env file names is stored with its variable.

With PROJECT_GRAPHS declared in an env file, `$PROJECT_GRAPHS/rig.nxt` is
how that file is written by anyone who types it. Picked in a file browser
it used to be stored as the whole path it has on this machine.

Only variables an env file declares are used. Whatever else is in the
environment was not put there to name a place graphs live.
"""
# Built-in
import json
import logging
import os
import shutil
import tempfile
import unittest
from unittest import mock

# Internal
from nxt import env_files, nxt_io
from nxt.plugins import file_fallbacks
from nxt.session import Session

logging.getLogger('nxt').propagate = False


class VariableReferences(unittest.TestCase):

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix='nxt_var_ref_'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = self.folder('project')
        self.common = self.folder('common')
        for patch in (mock.patch.dict(os.environ, clear=False),
                      mock.patch.object(env_files, '_applied', {}),
                      mock.patch.object(env_files, '_declared', [])):
            patch.start()
            self.addCleanup(patch.stop)
        for name in ('NXT_T_COMMON', 'NXT_T_DEEP', 'NXT_T_OTHER',
                     file_fallbacks.NXT_FILE_ROOTS):
            os.environ.pop(name, None)
        file_fallbacks._ENV_ROOTS_CACHE.clear()
        self.addCleanup(file_fallbacks._ENV_ROOTS_CACHE.clear)

    def folder(self, *parts):
        path = os.path.join(self.tmp, *parts)
        os.makedirs(path)
        return path

    def declare(self, **variables):
        env = os.path.join(self.tmp, 'env.json')
        with open(env, 'w') as file_object:
            json.dump({'variables': variables}, file_object)
        env_files.apply([env])

    @staticmethod
    def write(directory, name, alias='layer', references=()):
        path = os.path.join(directory, name)
        with open(path, 'w') as file_object:
            json.dump({'version': '1.17', 'alias': alias,
                       'references': list(references)}, file_object)
        return path

    def test_stored_with_the_variable(self):
        self.declare(NXT_T_COMMON=self.common)
        picked = self.write(self.common, 'rig.nxt')
        self.assertEqual('$NXT_T_COMMON/rig.nxt',
                         nxt_io.stored_reference_path(picked, self.project))

    def test_it_loads_back(self):
        self.declare(NXT_T_COMMON=self.common)
        picked = self.write(self.common, 'rig.nxt', alias='picked')
        stored = nxt_io.stored_reference_path(picked, self.project)
        top = self.write(self.project, 'top.nxt', 'top', [stored])
        stage = Session().load_file(top)
        self.assertIn('picked',
                      [layer.get_alias() for layer in stage._sub_layers])

    def test_a_declared_variable_set_by_the_launcher_counts(self):
        # Declared in the file, but already set when nxt started, so nxt
        # left the value alone. It is still the project's name for it.
        os.environ['NXT_T_COMMON'] = self.common
        self.declare(NXT_T_COMMON='/somewhere/else')
        picked = self.write(self.common, 'rig.nxt')
        self.assertEqual('$NXT_T_COMMON/rig.nxt',
                         nxt_io.stored_reference_path(picked, self.project))

    def test_a_variable_no_env_file_declares_is_not_used(self):
        os.environ['NXT_T_OTHER'] = self.common
        self.declare()
        picked = self.write(self.common, 'rig.nxt')
        self.assertEqual(picked.replace(os.sep, '/'),
                         nxt_io.stored_reference_path(picked, self.project))

    def test_the_deepest_folder_wins(self):
        deep = self.folder('common', 'deep')
        self.declare(NXT_T_COMMON=self.common, NXT_T_DEEP=deep)
        picked = self.write(deep, 'rig.nxt')
        self.assertEqual('$NXT_T_DEEP/rig.nxt',
                         nxt_io.stored_reference_path(picked, self.project))

    def test_beside_the_layer_still_wins(self):
        self.declare(NXT_T_COMMON=self.project)
        picked = self.write(self.project, 'beside.nxt')
        self.assertEqual('beside.nxt',
                         nxt_io.stored_reference_path(picked, self.project))

    def test_a_list_of_paths_is_not_a_folder(self):
        self.declare(NXT_T_COMMON=[self.common, self.project])
        picked = self.write(self.common, 'rig.nxt')
        self.assertEqual(picked.replace(os.sep, '/'),
                         nxt_io.stored_reference_path(picked, self.project))

    def test_picked_through_a_link_keeps_the_link(self):
        from nxt.test.test_root_relative_references import link_folder
        os.makedirs(os.path.join(self.common, 'v12'))
        self.write(os.path.join(self.common, 'v12'), 'rig.nxt')
        link_folder(os.path.join(self.common, 'v12'),
                    os.path.join(self.common, 'current'))
        self.declare(NXT_T_COMMON=self.common)
        picked = os.path.join(self.common, 'current', 'rig.nxt')
        self.assertEqual('$NXT_T_COMMON/current/rig.nxt',
                         nxt_io.stored_reference_path(picked, self.project))

    def test_a_name_that_starts_with_two_dots(self):
        self.declare(NXT_T_COMMON=self.common)
        picked = self.write(self.common, '..odd.nxt')
        self.assertEqual('$NXT_T_COMMON/..odd.nxt',
                         nxt_io.stored_reference_path(picked, self.project))

    def test_a_root_is_tried_first(self):
        os.environ[file_fallbacks.NXT_FILE_ROOTS] = self.common
        file_fallbacks._ENV_ROOTS_CACHE.clear()
        self.declare(NXT_T_COMMON=self.common)
        picked = self.write(self.common, 'rig.nxt')
        self.assertEqual('rig.nxt',
                         nxt_io.stored_reference_path(picked, self.project))


if __name__ == '__main__':
    unittest.main()
