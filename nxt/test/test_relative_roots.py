"""A relative root in NXT_FILE_ROOTS is looked for from where loading is.

Loading a graph changes into each layer's folder, so a relative root can
exist from one folder and not another. The roots are cached for speed, and
the cache did not say which folder it was worked out in, so a relative
root first checked from the wrong folder was skipped for good. That is how
packaging nxt_editor, which finds nxt's packaging graph through
NXT_FILE_ROOTS=../docs/api_docs, stopped finding it.
"""
# Builtin
import json
import os
import shutil
import tempfile
import unittest

# Internal
from nxt.plugins import file_fallbacks
from nxt.session import Session


class RelativeRoots(unittest.TestCase):

    def setUp(self):
        self.saved_roots = os.environ.get(file_fallbacks.NXT_FILE_ROOTS)
        self.cwd = os.getcwd()
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix='nxt_rel_roots_'))
        file_fallbacks._ENV_ROOTS_CACHE.clear()

    def tearDown(self):
        os.chdir(self.cwd)
        if self.saved_roots is None:
            os.environ.pop(file_fallbacks.NXT_FILE_ROOTS, None)
        else:
            os.environ[file_fallbacks.NXT_FILE_ROOTS] = self.saved_roots
        file_fallbacks._ENV_ROOTS_CACHE.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_relative_root_is_checked_from_each_folder(self):
        here = os.path.join(self.tmp, 'here')
        there = os.path.join(self.tmp, 'there')
        os.makedirs(os.path.join(there, 'root'))
        os.makedirs(here)
        os.environ[file_fallbacks.NXT_FILE_ROOTS] = 'root'
        os.chdir(here)
        self.assertEqual([], list(file_fallbacks.iter_env_roots()))
        os.chdir(there)
        self.assertEqual(['root'], list(file_fallbacks.iter_env_roots()))

    def test_a_reference_found_through_a_relative_root(self):
        # The layout packaging nxt_editor in CI has: nxt checked out inside
        # the editor's folder, found from the editor's build folder through
        # a root that only exists relative to that build folder.
        repo = os.path.join(self.tmp, 'repo')
        os.makedirs(os.path.join(repo, 'build'))
        os.makedirs(os.path.join(repo, 'docs', 'api_docs'))
        os.makedirs(os.path.join(repo, 'nxt', 'build'))
        with open(os.path.join(repo, 'nxt', 'build', 'core.nxt'), 'w') as f:
            json.dump({'version': '1.17', 'alias': 'core',
                       'nodes': {'/from_core': {}}}, f)
        top = os.path.join(repo, 'build', 'editor.nxt')
        with open(top, 'w') as f:
            json.dump({'version': '1.17', 'alias': 'editor',
                       'references': ['../../nxt/build/core.nxt'],
                       'nodes': {'/from_editor': {}}}, f)
        os.environ[file_fallbacks.NXT_FILE_ROOTS] = '../docs/api_docs'
        os.chdir(repo)
        # Asked once from the repository, where the root does not exist.
        list(file_fallbacks.iter_env_roots())
        stage = Session().load_file(top)
        aliases = [layer.get_alias() for layer in stage._sub_layers]
        self.assertIn('core', aliases)


if __name__ == '__main__':
    unittest.main()
