# Builtin
import unittest
import subprocess
import sys

# Internal
import nxt
from nxt.session import Session


class CLI(unittest.TestCase):

    def test_basic_cli_exec(self):
        ret = subprocess.call([sys.executable, '-m', 'nxt.cli', 'exec',
                               'StageRuntimeScope.nxt'])
        self.assertEqual(0, ret)


class PythonEntry(unittest.TestCase):

    @staticmethod
    def test_simple_python_entry():
        rtl = nxt.execute_graph('StageRuntimeScope.nxt')

    def test_python_entry(self):
        my_session = Session()
        rtl = my_session.execute_graph('StageRuntimeScope.nxt')
        self.assertIsNotNone(rtl)
