"""Build the native speedups for this machine into nxt/_bin/<platform>/.

    python native/build.py
    python native/build.py --if-missing    # only if there is none yet

Needs Rust (https://rustup.rs). nxt works without this, using the same code
in Python. Releases carry a build for every OS, see build_all.py. An install
from git runs it with --if-missing, see setup.py.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from nxt import native  # noqa: E402


def main():
    tag = native.platform_tag()
    if not tag:
        sys.exit('nxt has no native build for this platform.')
    if '--if-missing' in sys.argv[1:] and os.path.isfile(
            os.path.join(native.BIN_DIR, tag, module_name(tag))):
        print('nxt already has a native build for ' + tag)
        return
    env = dict(os.environ, PYO3_PYTHON=sys.executable)
    target = env.setdefault('CARGO_TARGET_DIR', os.path.join(HERE, 'target'))
    subprocess.check_call(['cargo', 'build', '--release'], cwd=HERE, env=env)
    release = os.path.join(target, 'release')
    if sys.platform == 'win32':
        built = '_nxt_native.dll'
    elif sys.platform == 'darwin':
        built = 'lib_nxt_native.dylib'
    else:
        built = 'lib_nxt_native.so'
    print('Built ' + place(os.path.join(release, built), tag))


def module_name(tag):
    """The file name nxt loads the module from, see nxt/native.py."""
    if tag.startswith('windows'):
        return '_nxt_native.pyd'
    return '_nxt_native.so'


def place(built, tag):
    """Copy a built module into nxt/_bin/<tag>/, under the name nxt loads,
    and return where it went."""
    out_name = module_name(tag)
    out_dir = os.path.join(native.BIN_DIR, tag)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, out_name)
    for stale in os.listdir(out_dir):
        if stale.startswith(out_name + '.old'):
            try:
                os.remove(os.path.join(out_dir, stale))
            except OSError:
                pass  # Still loaded somewhere.
    if os.path.exists(out_path):
        # Windows will not replace a module a running Python has loaded,
        # but will let it be renamed out of the way.
        aside = '{}.old{}'.format(out_path, os.getpid())
        os.replace(out_path, aside)
    shutil.copyfile(built, out_path)
    return out_path


if __name__ == '__main__':
    main()
