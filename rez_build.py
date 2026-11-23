"""Rez build step for nxt_core.

Copies the python package into the build or install path. This is a script
rather than the shell one liner other packages use so that the same build
works on Windows as well as the macOS and Linux runners, which means a
developer can stage a build locally.
"""
import os
import shutil
import subprocess
import sys

SOURCE = os.path.dirname(os.path.abspath(__file__))

# Copied into <root>/python, which package.py puts on PYTHONPATH.
PYTHON_DIRS = ["nxt"]
# Copied to <root>/<name>, which package.py puts on PATH.
ROOT_DIRS = ["bin"]

IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "*.pyo", ".mypy_cache", ".pytest_cache",
    # Native modules native/build.py moved aside while they were loaded.
    "_nxt_native.*.old*",
)


def destination_root():
    """Where this build should write.

    rez sets REZ_BUILD_INSTALL when the build is being installed, in which
    case it wants the files in REZ_BUILD_INSTALL_PATH rather than the
    temporary build directory.
    """
    if os.environ.get("REZ_BUILD_INSTALL") == "1":
        return os.environ["REZ_BUILD_INSTALL_PATH"]
    return os.environ["REZ_BUILD_PATH"]


def copy_tree(source, destination):
    if os.path.isdir(destination):
        shutil.rmtree(destination)
    parent = os.path.dirname(destination)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    shutil.copytree(source, destination, ignore=IGNORE)
    print("  %s -> %s" % (os.path.basename(source), destination))


def build_native():
    """On CI, build the native speedups for every OS into nxt/_bin, so the
    package carries them. Built on the macOS runner, which makes all four,
    and a failure fails the build rather than shipping a package that is
    quietly slower. A build on a working machine packages whatever
    nxt/_bin already has.
    """
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    script = os.path.join(SOURCE, "native", "build_all.py")
    subprocess.check_call([sys.executable, script, "--all"])


# Run against the package just built: the native module for this machine
# loads, and is the version nxt composites with.
CHECK = (
    "from nxt import native, comp_plan; "
    "assert native.lib is not None, 'no native module loaded'; "
    "assert native.lib.VERSION == comp_plan.NATIVE_VERSION, 'old module'; "
    "print('native module ok: ' + native.lib.__file__)"
)


def check_native(root):
    """On CI, load the package's native module and compare it with the
    Python code, so a package that would quietly run slower fails here."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    python_dir = os.path.join(root, "python")
    env = dict(os.environ, PYTHONPATH=python_dir)
    subprocess.check_call([sys.executable, "-c", CHECK], env=env,
                          cwd=python_dir)
    subprocess.check_call([sys.executable, "-m", "unittest", "-v",
                           "nxt.test.test_native", "nxt.test.test_tokens"],
                          env=env, cwd=python_dir)


def main():
    root = destination_root()
    print("building into %s" % root)
    build_native()
    for name in PYTHON_DIRS:
        copy_tree(os.path.join(SOURCE, name), os.path.join(root, "python", name))
    for name in ROOT_DIRS:
        source = os.path.join(SOURCE, name)
        if os.path.isdir(source):
            copy_tree(source, os.path.join(root, name))
    check_native(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
