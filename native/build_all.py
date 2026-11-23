"""Build the native speedups for every OS nxt ships for, into nxt/_bin/.

    python native/build_all.py          # what this machine can build
    python native/build_all.py --all    # all of them, or fail

A release builds them all on the studio's macOS runner: macOS's own, Linux's
with zig and Windows' with xwin, so one machine makes the four and the
package carries every one. Linux and Windows can build all but macOS's.

The tools it needs are put in a cache folder the first time, Rust with
rustup where there is none, then maturin, zig and xwin. NXT_NATIVE_CACHE
moves the folder. nxt works without any of this, using the same code in
Python.
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build  # noqa: E402

# nxt/_bin folder, Rust target and what else maturin is told.
TARGETS = [
    ('macos_universal', 'universal2-apple-darwin', []),
    ('linux_x86_64', 'x86_64-unknown-linux-gnu',
     # Old enough glibc for the Linux versions studios run hosts on.
     ['--zig', '--compatibility', 'manylinux2014']),
    ('linux_arm64', 'aarch64-unknown-linux-gnu',
     ['--zig', '--compatibility', 'manylinux2014']),
    ('windows_x86_64', 'x86_64-pc-windows-msvc', []),
]
# The Rust targets each needs installed.
RUST_TARGETS = {
    'universal2-apple-darwin': ['x86_64-apple-darwin', 'aarch64-apple-darwin'],
}
TOOLS = ['maturin>=1.7,<2', 'ziglang', 'cargo-xwin']


def can_build(tag):
    # macOS's linker and SDK are only on a Mac.
    return sys.platform == 'darwin' or not tag.startswith('macos')


def cache_dir():
    return os.environ.get('NXT_NATIVE_CACHE') or os.path.join(
        os.path.expanduser('~'), '.cache', 'nxt_native')


def scripts(venv):
    return os.path.join(venv, 'Scripts' if sys.platform == 'win32' else 'bin')


def find_cargo_bin():
    """The folder with cargo and rustup, installing Rust if there is none."""
    cargo = shutil.which('cargo')
    if cargo:
        return os.path.dirname(cargo)
    home = os.environ.get('CARGO_HOME') or os.path.join(
        os.path.expanduser('~'), '.cargo')
    folder = os.path.join(home, 'bin')
    exe = '.exe' if sys.platform == 'win32' else ''
    if os.path.isfile(os.path.join(folder, 'cargo' + exe)):
        return folder
    if sys.platform == 'win32':
        sys.exit('Rust is needed: https://rustup.rs')
    print('Installing Rust with rustup')
    subprocess.check_call(
        'curl --proto =https --tlsv1.2 -sSf https://sh.rustup.rs | '
        'sh -s -- -y --profile minimal --no-modify-path', shell=True)
    return folder


def tools_env(tags):
    """The environment maturin runs in, with every tool it needs for the
    targets of these tags."""
    cache = cache_dir()
    venv = os.path.join(cache, 'venv')
    if not os.path.isdir(scripts(venv)):
        subprocess.check_call([sys.executable, '-m', 'venv', venv])
    python = os.path.join(scripts(venv), 'python')
    subprocess.check_call([python, '-m', 'pip', 'install', '-q',
                           '--disable-pip-version-check'] + TOOLS)
    # zig itself, so maturin finds it whichever python it looks with.
    zig_dir = subprocess.check_output(
        [python, '-c', 'import os, ziglang; '
                       'print(os.path.dirname(ziglang.__file__))'],
        universal_newlines=True).strip()
    cargo_bin = find_cargo_bin()
    env = dict(os.environ)
    env['PATH'] = os.pathsep.join([scripts(venv), zig_dir, cargo_bin,
                                   env['PATH']])
    # Kept between builds, so a build only redoes what changed.
    env['CARGO_TARGET_DIR'] = os.path.join(cache, 'target')
    env['XWIN_CACHE_DIR'] = os.path.join(cache, 'xwin')
    # pyo3 makes Windows' python3.lib with it, off Windows.
    env['ZIG_COMMAND'] = os.path.join(
        zig_dir, 'zig.exe' if sys.platform == 'win32' else 'zig')
    wanted = []
    for tag, target, _ in TARGETS:
        if tag in tags:
            wanted += RUST_TARGETS.get(target, [target])
    rustup = shutil.which('rustup', path=env['PATH'])
    if rustup:
        subprocess.check_call([rustup, 'target', 'add'] + wanted, env=env)
    return env


def build_one(tag, target, extra, env):
    out = tempfile.mkdtemp(prefix='nxt_native_')
    try:
        maturin = shutil.which('maturin', path=env['PATH'])
        subprocess.check_call(
            [maturin, 'build', '--release', '--target', target,
             '--manifest-path', os.path.join(HERE, 'Cargo.toml'),
             '--out', out] + extra, env=env, cwd=HERE)
        wheel, = glob.glob(os.path.join(out, '*.whl'))
        with zipfile.ZipFile(wheel) as zipped:
            name, = [n for n in zipped.namelist()
                     if os.path.basename(n).startswith('_nxt_native') and
                     n.endswith(('.pyd', '.so'))]
            zipped.extract(name, out)
        return build.place(os.path.join(out, name), tag)
    finally:
        shutil.rmtree(out, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--all', action='store_true',
                        help='fail unless every OS builds')
    parser.add_argument('tags', nargs='*',
                        help='only these, of ' +
                             ', '.join(t for t, _, _ in TARGETS))
    args = parser.parse_args(argv)
    tags = args.tags or [t for t, _, _ in TARGETS]
    unknown = set(tags) - {t for t, _, _ in TARGETS}
    if unknown:
        parser.error('no such build: ' + ', '.join(sorted(unknown)))
    skipped = [t for t in tags if not can_build(t)]
    if skipped and args.all:
        sys.exit('This machine cannot build ' + ', '.join(skipped))
    tags = [t for t in tags if t not in skipped]
    env = tools_env(tags)
    for tag, target, extra in TARGETS:
        if tag in tags:
            print('Built ' + build_one(tag, target, extra, env))
    for tag in skipped:
        print('Not built here: ' + tag)


if __name__ == '__main__':
    main()
