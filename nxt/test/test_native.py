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
    def test_a_shipped_build_loads(self):
        # A package carries a build for this platform that does not load,
        # or is not the version the comp uses: nxt still works, slower, so
        # nothing else would say.
        import os
        from nxt import comp_plan
        tag = native.platform_tag()
        name = '_nxt_native.so'
        if tag and tag.startswith('windows'):
            name = '_nxt_native.pyd'
        if not tag or not os.path.isfile(
                os.path.join(native.BIN_DIR, tag, name)):
            self.skipTest('no native build here')
        if os.environ.get(native.NO_NATIVE_ENV_VAR, '').strip() not in (
                '', '0'):
            self.skipTest('turned off')
        lib = native._load()
        self.assertIsNotNone(lib, 'the native build here did not load')
        self.assertEqual(comp_plan.NATIVE_VERSION, lib.VERSION)

    def test_platform_tag_names_a_bin_folder(self):
        tag = native.platform_tag()
        if tag is not None:
            self.assertRegex(tag, r'^(windows|linux)_(x86_64|arm64)$|'
                                  r'^macos_universal$')
