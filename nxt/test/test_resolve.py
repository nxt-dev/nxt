# Builtin
import json
import os
import shutil
import tempfile
import unittest

# Internal
from nxt.session import Session
from nxt.test import get_test_file_path
from nxt import DATA_STATE

class TestResolve(unittest.TestCase):
    def test_multiline_code_resolve(self):
        """When an attr has "real" newline and is subsituted into code,
        resolve that into multiple code lines
        """
        test_graph = get_test_file_path("ResolveNewlines.nxt")
        stage = Session().load_file(test_graph)
        comp_layer = stage.build_stage()
        node=comp_layer.lookup("/test_node")
        # Unresolved has 1 line
        raw_lines = stage.get_node_code_lines(node,
                                              layer=comp_layer,
                                              data_state=DATA_STATE.RAW)
        assert len(raw_lines) == 1
        resolved_lines = stage.get_node_code_lines(node,
                                                   layer=comp_layer,
                                                   data_state=DATA_STATE.RESOLVED)
        assert len(resolved_lines) == 2

    def test_code_attr_substitutes_as_text(self):
        """Code is kept as a list of lines, a token naming it should give
        the code text rather than the list.
        """
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        graph = os.path.join(folder, 'code_sub.nxt')
        with open(graph, 'w') as f:
            json.dump({'version': '1.17', 'alias': 'code_sub', 'nodes': {
                '/a': {'attrs': {'v': {'value': '5'}},
                       'code': ['x = ${v}', 'y = 2']},
                '/b': {'code': ['${/a._code}', 'self.z = x + y']},
                '/c': {'attrs': {'text': {'value': '${/a._code}'}}},
            }}, f)
        stage = Session().load_file(graph)
        comp_layer = stage.build_stage()
        node = comp_layer.lookup('/b')
        resolved_lines = stage.get_node_code_lines(node, layer=comp_layer,
                                                   data_state=DATA_STATE.RESOLVED)
        self.assertEqual(['x = 5', 'y = 2', 'self.z = x + y'], resolved_lines)
        text = stage.get_node_attr_value(comp_layer.lookup('/c'), 'text',
                                         comp_layer)
        self.assertEqual('x = 5\ny = 2', text)
        rt_layer = stage.execute_nodes(['/b'], comp_layer)
        self.assertEqual(7, rt_layer.cache_layer.lookup('/b').z)
