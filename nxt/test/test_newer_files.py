"""A file saved by a newer nxt can be opened anyway, when asked to.

Opening one raises NewerFileError, still an IOError as before, which says
what version saved it. Inside allow_newer_files it opens instead, with a
warning, and so do the newer files it references.
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
from nxt.constants import GRAPH_VERSION
from nxt.session import Session

# The failed opens are logged, and these tests cause them on purpose.
logging.getLogger('nxt').propagate = False

NEWER_MINOR = '{}.{}'.format(GRAPH_VERSION.MAJOR, GRAPH_VERSION.MINOR + 1)
# A newer major version with a lower minor one, which is no reason to run
# the old file converters on it.
NEWER_MAJOR = '{}.0'.format(GRAPH_VERSION.MAJOR + 1)


def write_graph(path, name, version, references=()):
    data = {'version': version, 'alias': name, 'references': list(references),
            'nodes': {'/' + name: {}}}
    with open(path, 'w') as file_object:
        json.dump(data, file_object)
    return path


class NewerFiles(unittest.TestCase):

    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp(prefix='nxt_newer_')
        self.newer = write_graph(os.path.join(self.tmp, 'newer.nxt'),
                                 'newer', NEWER_MINOR)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_it_raises_saying_which_version(self):
        with self.assertRaises(nxt_io.NewerFileError) as caught:
            nxt_io.load_file_data(self.newer)
        self.assertEqual(NEWER_MINOR, caught.exception.version)
        self.assertTrue(os.path.samefile(self.newer, caught.exception.path))

    def test_it_is_still_an_io_error(self):
        self.assertRaises(IOError, nxt_io.load_file_data, self.newer)

    def test_it_opens_when_allowed(self):
        with nxt_io.allow_newer_files():
            data = nxt_io.load_file_data(self.newer)
        self.assertIn('/newer', data['nodes'])
        # Only inside the block.
        self.assertRaises(nxt_io.NewerFileError, nxt_io.load_file_data,
                          self.newer)

    def test_a_newer_major_version_is_not_converted(self):
        path = write_graph(os.path.join(self.tmp, 'major.nxt'), 'major',
                           NEWER_MAJOR)
        with nxt_io.allow_newer_files():
            data = nxt_io.load_file_data(path)
        self.assertEqual(NEWER_MAJOR, data['version'])

    def test_its_newer_references_open_too(self):
        write_graph(os.path.join(self.tmp, 'ref.nxt'), 'ref', NEWER_MINOR)
        top = write_graph(os.path.join(self.tmp, 'top.nxt'), 'top',
                          NEWER_MINOR, references=['ref.nxt'])
        with nxt_io.allow_newer_files():
            stage = Session().load_file(top)
        aliases = [layer.get_alias() for layer in stage._sub_layers]
        self.assertEqual(['top', 'ref'], aliases)


if __name__ == '__main__':
    unittest.main()
