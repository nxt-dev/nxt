# Builtin
import unittest
import subprocess
import sys

# Internal
import nxt
from nxt.session import Session
from nxt.test import get_test_file_path

GRAPH_PATH = get_test_file_path("StageRuntimeScope.nxt")

class CLI(unittest.TestCase):

    def test_basic_cli_exec(self):
        ret = subprocess.call([sys.executable, '-m', 'nxt.cli', 'exec',
                               GRAPH_PATH])
        self.assertEqual(0, ret)


class PythonEntry(unittest.TestCase):

    @staticmethod
    def test_simple_python_entry():
        rtl = nxt.execute_graph(GRAPH_PATH)

    def test_python_entry(self):
        my_session = Session()
        rtl = my_session.execute_graph(GRAPH_PATH)
        self.assertIsNotNone(rtl)
