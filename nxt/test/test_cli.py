# Builtin
import unittest
import os
import json
import subprocess
import sys

# Internal
import nxt
from nxt.session import Session
from nxt.test import get_test_file_path


class CLI(unittest.TestCase):
    '''The test graph writes /cli_test.my_attr to the location specified by
    The env var $_TEST_WRITE_PATH, allowing verification of paramter overrides
    by reading the resulting file.'''
    test_graph = get_test_file_path('cli_test.nxt')

    def setUp(self):
        self.test_path = get_test_file_path('delete_me')
        # Test graph writes a file to the location of this env var.
        self.test_env = os.environ.copy()
        self.test_env.update({'_TEST_WRITE_PATH': self.test_path})

    def tearDown(self):
        try:
            os.remove(self.test_path)
        except FileNotFoundError:
            pass

    def read_test_path(self):
        with open(self.test_path, 'r') as fp:
            return fp.read()

    def test_basic_cli_exec(self):
        """Basic call proves test graph works as expected"""
        ret = subprocess.call([sys.executable, '-m', 'nxt.cli', 'exec',
                               self.test_graph], env=self.test_env)
        self.assertEqual(0, ret)
        self.assertTrue(self.read_test_path() == 'default')

    def test_cli_parameters(self):
        """Overwriting attributes from the cli"""
        subprocess.call([sys.executable, '-m', 'nxt.cli', 'exec',
                        self.test_graph, '-p', '/cli_test.my_attr',
                        'from_cli'], env=self.test_env)
        self.assertTrue(self.read_test_path() == 'from_cli')

    def test_file_parameters(self):
        """Overwriting attributes from parameters file"""
        tmp_params_path = get_test_file_path('test_params')
        with open(tmp_params_path, "w+") as fp:
            json.dump({'/cli_test.my_attr': 'from_file'}, fp)
        subprocess.call([sys.executable, '-m', 'nxt.cli', 'exec',
                        self.test_graph, '-p', tmp_params_path],
                        env=self.test_env)
        os.remove(tmp_params_path)
        self.assertTrue(self.read_test_path() == 'from_file')


class PythonEntry(unittest.TestCase):

    graph_path = get_test_file_path("StageRuntimeScope.nxt")

    def test_simple_python_entry(self):
        nxt.execute_graph(self.graph_path)

    def test_python_entry(self):
        my_session = Session()
        rtl = my_session.execute_graph(self.graph_path)
        self.assertIsNotNone(rtl)
