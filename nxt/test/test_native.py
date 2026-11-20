"""The native speedups give exactly what their Python twins give."""
import random
import unittest

from nxt import native, tokens


class WithoutNative(object):
    """Run the Python code even where the native module loaded."""
    def __enter__(self):
        self.lib = native.lib
        native.lib = None

    def __exit__(self, *args):
        native.lib = self.lib


@unittest.skipUnless(native.lib, 'no native build for this platform')
class StandaloneTokens(unittest.TestCase):
    PIECES = ['${', '}', '$', '{', 'a', 'node.attr', '/p/q', 'file::',
              'path::', 'contents::', 'filelist::', ' ', '\n', 'é', '日本',
              '\U0001f600', '${x}', '${file::${y}}', '..']

    def both(self, value, token_types=None):
        fast = tokens.get_standalone_tokens(value, token_types)
        with WithoutNative():
            slow = tokens.get_standalone_tokens(value, token_types)
        self.assertEqual(slow, fast, repr(value))
        return fast

    def test_known_values(self):
        self.assertEqual(['${x}', '${file::${y}}'],
                         self.both('a ${x} b ${file::${y}} c'))
        self.assertEqual([], self.both('${unclosed'))
        self.assertEqual(['${a}'], self.both('é${a}}'))
        self.assertEqual([], self.both(''))
        self.assertEqual([], self.both(None))
        self.assertEqual(['${file::f}'],
                         self.both('${a} ${file::f}', [tokens.TOKENTYPE.FILE]))

    def test_random_values_match(self):
        rnd = random.Random(7)
        types = [None, [tokens.TOKENTYPE.FILE],
                 [tokens.TOKENTYPE.ATTR, tokens.TOKENTYPE.CONTENTS]]
        for _ in range(20000):
            value = ''.join(rnd.choice(self.PIECES)
                            for _ in range(rnd.randint(0, 14)))
            self.both(value, rnd.choice(types))


class Loader(unittest.TestCase):
    def test_platform_tag_names_a_bin_folder(self):
        tag = native.platform_tag()
        if tag is not None:
            self.assertRegex(tag, r'^(windows|linux)_(x86_64|arm64)$|'
                                  r'^macos_universal$')
