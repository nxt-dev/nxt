# Built-in
import unittest
import os

# Internal
from nxt.plugins.file_fallbacks import NXT_FILE_ROOTS
from nxt.session import Session
from nxt.stage import DATA_STATE


class TestFallbacks(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.chdir(os.path.dirname(os.path.realpath(__file__)))

    def test_fallbacks(self):
        print("Test that fallbacks works.")
        graph = "../test/plugins/fallbacks/another/fallbacks_top.nxt"
        cwd = "../test/plugins/fallbacks/base"
        expanded = os.path.abspath(cwd)
        self.stage = Session().load_file(graph)
        comp_layer = self.stage.build_stage()
        node = comp_layer.lookup('/init/node')
        expected = os.path.join(expanded, 'biped_base.txt').replace(os.sep, '/')
        attr_name = 'filepath'
        actual = self.stage.resolve(node, getattr(node, attr_name),
                                    comp_layer, attr_name=attr_name)
        self.assertEqual(expected, actual)

    def test_multi_file_tokens(self):
        print("Test that an attr with multiple file tokens resolves as "
              "expected (using Stage.resolve_file_token).")
        graph = "../test/plugins/fallbacks/another/fallbacks_top.nxt"
        p1 = os.path.abspath(os.path.dirname(graph)).replace(os.sep, '/')
        p2 = os.path.abspath(os.path.join(p1, '..', 'base',
                                          'biped_base.txt')).replace(os.sep,
                                                                     '/')
        self.stage = Session().load_file(graph)
        comp_layer = self.stage.build_stage()
        node = comp_layer.lookup('/init/node2')
        expected = "['{}', '', '{}']".format(p1, p2)
        attr_name = 'limitation'
        actual = self.stage.resolve(node, getattr(node, attr_name),
                                    comp_layer, attr_name=attr_name)
        self.assertEqual(expected, actual)

    def test_instance_fallbacks(self):
        print("Test that fallback work with instances.")
        graph = "../test/plugins/fallbacks/another/fallbacks_top.nxt"
        fb_graph = "../test/plugins/fallbacks/base/fallbacks2.nxt"
        expanded = os.path.abspath(os.path.dirname(fb_graph))
        self.stage = Session().load_file(graph)
        comp_layer = self.stage.build_stage()
        node = comp_layer.lookup('/init2/node')
        expected = os.path.join(expanded, 'biped_base.txt').replace(os.sep, '/')
        attr_name = 'filepath'
        actual = self.stage.resolve(node, getattr(node, attr_name),
                                    comp_layer, attr_name=attr_name)
        self.assertEqual(expected, actual)

    def test_code_file_tokens(self):
        print("Test that fallback give full path in code")
        graph = "../test/plugins/fallbacks/another/fallbacks_top.nxt"
        expanded = os.path.abspath(os.path.dirname(graph))
        self.stage = Session().load_file(graph)
        comp_layer = self.stage.build_stage()
        node = comp_layer.lookup('/init')
        expected = os.path.join(expanded, 'dummy.txt').replace(os.sep, '/')
        actual = self.stage.get_node_code_string(node, comp_layer,
                                                 DATA_STATE.RESOLVED)
        self.assertEqual(expected, actual)

    def test_muted_layers_fallbacks(self):
        print("Test that fallback respects muted layers.")
        # Test base without muting anything
        graph = "../test/plugins/fallbacks/another/fallbacks_top.nxt"
        expanded = os.path.abspath(os.path.dirname(graph))
        self.stage = Session().load_file(graph)
        comp_layer = self.stage.build_stage()
        node = comp_layer.lookup('/test_mute')
        expected = os.path.join(expanded, 'dummy.txt').replace(os.sep, '/')
        attr_name = 'filepath'
        actual = self.stage.resolve(node, getattr(node, attr_name),
                                    comp_layer, attr_name=attr_name)
        self.assertEqual(expected, actual)
        # Mute and test again
        self.stage.top_layer.set_muted(True)
        comp_layer = self.stage.build_stage()
        node = comp_layer.lookup('/test_mute')
        expanded2 = os.path.abspath("../test/plugins/fallbacks/base")
        expected = os.path.join(expanded2, 'biped_base.txt').replace(os.sep,
                                                                     '/')
        attr_name = 'filepath'
        actual = self.stage.resolve(node, getattr(node, attr_name),
                                    comp_layer, attr_name=attr_name)
        self.assertEqual(expected, actual)

    def test_file_list(self):
        print("Test file list token works.")
        graph = "../test/plugins/fallbacks/another/fallbacks_top.nxt"
        cwd = "../test/plugins/fallbacks/base"
        expanded = os.path.abspath(cwd)
        self.stage = Session().load_file(graph)
        comp_layer = self.stage.build_stage()
        node = comp_layer.lookup('/init/node')
        expected = [os.path.join(expanded,
                                 'biped_base.txt').replace(os.sep, '/'),
                    os.path.join(expanded,
                                 'quad_base.txt').replace(os.sep, '/')
                    ]
        attr_name = 'file_list'
        actual = self.stage.resolve(node, getattr(node, attr_name),
                                    comp_layer, attr_name=attr_name)
        self.assertEqual(str(expected), actual)

    def test_nested_file_tokens(self):
        print("Test nested file tokens")
        graph = "../test/plugins/fallbacks/another/fallbacks_top.nxt"
        cwd = "../test/plugins/fallbacks/another"
        expanded = os.path.abspath(cwd)
        self.stage = Session().load_file(graph)
        comp_layer = self.stage.build_stage()
        node = comp_layer.lookup('/init/node')
        expected = os.path.join(expanded, 'dummy.txt').replace(os.sep, '/')
        attr_name = 'nested'
        actual = self.stage.resolve(node, getattr(node, attr_name),
                                    comp_layer, attr_name=attr_name)
        self.assertEqual(expected, actual)

    def test_env_var(self):
        print("Test that NXT_FILE_ROOTS env var works.")
        graph = "../test/plugins/fallbacks/another/fallbacks_top.nxt"
        cwd = "../test/plugins/fallbacks/base"
        expanded = os.path.abspath(cwd)
        os.environ['NXT_FILE_ROOTS'] = expanded
        self.stage = Session().load_file(graph)
        comp_layer = self.stage.build_stage()
        node = comp_layer.lookup('/init/node3')
        expected = os.path.join(expanded, 'biped_base.txt').replace(os.sep, '/')
        attr_name = 'env'
        actual = self.stage.resolve(node, getattr(node, attr_name),
                                    comp_layer, attr_name=attr_name)
        os.environ.pop('NXT_FILE_ROOTS')
        self.assertEqual(expected, actual)

    def test_token_resolve_to_nothing(self):
        print("Test a token containing failed attr subs returns nothing.")
        graph = "../test/plugins/fallbacks/another/fallbacks_top.nxt"
        cwd = "../test/plugins/fallbacks/base"
        expanded = os.path.abspath(cwd)
        self.stage = Session().load_file(graph)
        comp_layer = self.stage.build_stage()
        node = comp_layer.lookup('/init/node4')
        expected = ''
        attr_name = 'nothing'
        actual = self.stage.resolve(node, getattr(node, attr_name),
                                    comp_layer, attr_name=attr_name)
        self.assertEqual(expected, actual)


class TestPathWithRoots(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        self.test_filename = 'NotAFile.txt'
        self.test_input = '${path::' + self.test_filename + '}'

    def test_empty(self):
        print('Test that in an empty file with no environment,'
              ' path:: resolves to cwd')
        test_stage = self.session.new_file()
        test_node, _ = test_stage.add_node()
        test_node = test_node[0]
        test_attr = test_stage.add_node_attr(test_node, 'path_test',
                                             {'value': self.test_input},
                                             test_stage.top_layer)
        my_dir = os.path.dirname(os.path.realpath(__file__))
        old_cwd = os.getcwd()
        # Keep any environment out of this test
        old_env_roots = ''
        if NXT_FILE_ROOTS in os.environ:
            old_env_roots = os.environ.pop(NXT_FILE_ROOTS)
        os.chdir(my_dir)
        expected = os.path.join(my_dir, self.test_filename).replace(os.sep, '/')
        found = test_stage.get_node_attr_value(test_node, test_attr,
                                               test_stage.top_layer,
                                               resolved=True)
        self.assertEqual(expected, found)
        os.chdir(old_cwd)
        os.environ[NXT_FILE_ROOTS] = old_env_roots

    def test_saved(self):
        print('Test in a saved file with no environment, path:: '
              'resolves to graph dir')
        # Keep any existing environment out of this test
        old_env_roots = ''
        if NXT_FILE_ROOTS in os.environ:
            old_env_roots = os.environ.pop(NXT_FILE_ROOTS)
        old_cwd = os.getcwd()
        my_dir = os.path.dirname(os.path.realpath(__file__))
        os.chdir(my_dir)

        graph_path = "../test/plugins/fallbacks/pathroots.nxt"
        graph_path = os.path.abspath(graph_path)
        graph_dir = os.path.dirname(graph_path)
        test_stage = self.session.load_file(graph_path)
        test_node = test_stage.top_layer.lookup('/test_node')
        test_attr = test_stage.add_node_attr(test_node, 'path_test',
                                             {'value': self.test_input},
                                             test_stage.top_layer)
        expected = os.path.join(graph_dir, self.test_filename).replace(os.sep,
                                                                       '/')
        found = test_stage.get_node_attr_value(test_node, test_attr,
                                               test_stage.top_layer,
                                               resolved=True)
        self.assertEqual(expected, found)

        print('Test in a saved file with an environment, path:: '
              'resolves to first real env root')
        test_root = os.path.dirname(my_dir)
        os.environ[NXT_FILE_ROOTS] = 'a super fake root;' + test_root
        expected = os.path.join(test_root, self.test_filename).replace(os.sep,
                                                                       '/')
        found = test_stage.get_node_attr_value(test_node, test_attr,
                                               test_stage.top_layer,
                                               resolved=True)
        self.assertEqual(expected, found)

        os.chdir(old_cwd)
        os.environ[NXT_FILE_ROOTS] = old_env_roots

