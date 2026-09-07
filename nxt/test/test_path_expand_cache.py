"""Expanding a path is cached, and the cache has to know what it depended on.

realpath is the expensive part of resolving a path, so the answer is kept.
A relative path with no start resolves against the working directory,
which means the answer is only good for the directory it was worked out
in. Leaving that out of the key made a relative path keep its first answer
after a chdir, which pointed layer references at a file that was not there.
"""
# Built-in
import logging
import os
import shutil
import tempfile
import unittest

# Internal
from nxt import nxt_path

logging.getLogger('nxt').propagate = False


class RelativePathsFollowTheWorkingDirectory(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        self.one = tempfile.mkdtemp(prefix='nxt_cache_one_')
        self.two = tempfile.mkdtemp(prefix='nxt_cache_two_')
        for directory in (self.one, self.two):
            with open(os.path.join(directory, 'thing.nxt'), 'w') as handle:
                handle.write('{}')
        nxt_path.clear_file_expand_cache()

    def tearDown(self):
        os.chdir(self.cwd)
        for directory in (self.one, self.two):
            shutil.rmtree(directory, ignore_errors=True)
        nxt_path.clear_file_expand_cache()

    def test_the_same_relative_path_from_two_directories(self):
        os.chdir(self.one)
        first = nxt_path.full_file_expand('thing.nxt')
        os.chdir(self.two)
        second = nxt_path.full_file_expand('thing.nxt')
        self.assertNotEqual(first, second,
                            'the cached answer followed us to another '
                            'directory')
        self.assertTrue(os.path.samefile(
            os.path.join(self.one, 'thing.nxt'), first))
        self.assertTrue(os.path.samefile(
            os.path.join(self.two, 'thing.nxt'), second))

    def test_an_explicit_start_is_unaffected_by_the_working_directory(self):
        os.chdir(self.one)
        first = nxt_path.full_file_expand('thing.nxt', start=self.two)
        os.chdir(self.two)
        second = nxt_path.full_file_expand('thing.nxt', start=self.two)
        self.assertEqual(first, second)
        self.assertTrue(os.path.samefile(
            os.path.join(self.two, 'thing.nxt'), first))

    def test_an_absolute_path_is_unaffected(self):
        absolute = os.path.join(self.one, 'thing.nxt')
        os.chdir(self.one)
        first = nxt_path.full_file_expand(absolute)
        os.chdir(self.two)
        second = nxt_path.full_file_expand(absolute)
        self.assertEqual(first, second)

    def test_repeated_calls_still_come_from_the_cache(self):
        # The point of the key was speed; it should not have become a
        # cache that never hits.
        os.chdir(self.one)
        nxt_path.clear_file_expand_cache()
        nxt_path.full_file_expand('thing.nxt')
        size_after_first = len(nxt_path._REAL_PATH_CACHE)
        for _ in range(20):
            nxt_path.full_file_expand('thing.nxt')
        self.assertEqual(size_after_first, len(nxt_path._REAL_PATH_CACHE),
                         'each call added an entry, so nothing is caching')

    def test_expanding_still_resolves_variables(self):
        os.environ['NXT_TEST_CACHE_DIR'] = self.one
        try:
            nxt_path.clear_file_expand_cache()
            resolved = nxt_path.full_file_expand('$NXT_TEST_CACHE_DIR/thing.nxt')
            self.assertTrue(os.path.samefile(
                os.path.join(self.one, 'thing.nxt'), resolved))
        finally:
            os.environ.pop('NXT_TEST_CACHE_DIR', None)


if __name__ == '__main__':
    unittest.main()
