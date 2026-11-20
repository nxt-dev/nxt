"""Build the native speedups for this machine into nxt/_bin/<platform>/.

    python native/build.py

Needs Rust (https://rustup.rs). nxt works without this, using the same code
in Python. Releases carry a build for every OS, made by CI.
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
    env = dict(os.environ, PYO3_PYTHON=sys.executable)
    target = env.setdefault('CARGO_TARGET_DIR', os.path.join(HERE, 'target'))
    subprocess.check_call(['cargo', 'build', '--release'], cwd=HERE, env=env)
    release = os.path.join(target, 'release')
    if sys.platform == 'win32':
        built, out_name = '_nxt_native.dll', '_nxt_native.pyd'
    elif sys.platform == 'darwin':
        built, out_name = 'lib_nxt_native.dylib', '_nxt_native.so'
    else:
        built, out_name = 'lib_nxt_native.so', '_nxt_native.so'
    out_dir = os.path.join(native.BIN_DIR, tag)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, out_name)
    shutil.copyfile(os.path.join(release, built), out_path)
    print('Built ' + out_path)


if __name__ == '__main__':
    main()
