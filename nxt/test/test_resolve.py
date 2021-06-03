# Builtin
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
