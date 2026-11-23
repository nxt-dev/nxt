import setuptools
import json
import io
import os
import subprocess
import sys

from setuptools.command.build_py import build_py

HERE = os.path.dirname(os.path.abspath(__file__))


class BuildPy(build_py):
    """Builds the native speedups for this machine first, where there are
    none for it yet and Rust is installed, as in an install from git.
    Releases carry them already. Without Rust, or should the build fail,
    nxt uses the same code in Python, so the install goes on regardless.
    """
    def run(self):
        script = os.path.join(HERE, 'native', 'build.py')
        off = os.environ.get('NXT_NO_NATIVE', '').strip() not in ('', '0')
        if os.path.isfile(script) and not off:
            try:
                subprocess.check_call([sys.executable, script,
                                       '--if-missing'], cwd=HERE)
            except (OSError, subprocess.CalledProcessError) as err:
                print('Not building the native speedups, nxt uses its '
                      'Python code: {}'.format(err))
        build_py.run(self)


with io.open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

desc = ("A general purpose code compositor designed for rigging, "
        "scene assembly, and automation. (node execution tree)")

with open("nxt/version.json", 'r') as fh:
    version_data = json.load(fh)
api_v_data = version_data['API']
api_major = api_v_data['MAJOR']
api_minor = api_v_data['MINOR']
api_patch = api_v_data['PATCH']
api_version = '{}.{}.{}'.format(api_major, api_minor, api_patch)

setuptools.setup(
    name="nxt_core",
    version=api_version,
    author="The nxt contributors",
    author_email="dev@opennxt.dev",
    description=desc,
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nxt-dev/nxt",
    cmdclass={'build_py': BuildPy},
    packages=setuptools.find_packages(),
    # Maya 2022 is 3.7, Maya 2027 and its 3.13 is the current ceiling.
    python_requires='>=3.10, <3.14',
    entry_points={
        'console_scripts': [
            'nxt=nxt.cli:main',
        ],
    },
    package_data={
        # covers text nxt files
        "": ["*.nxt"],
        # Covers builtin, and full depth of test graphs/files
        "nxt": ["version.json",
                "builtin/*",
                # The native speedups, one per OS, see native/.
                "_bin/*/_nxt_native.pyd",
                "_bin/*/_nxt_native.so",
                "test/*",
                "test/spec_graphs/*",
                "test/legacy/*",
                "test/plugins/*",
                "test/plugins/fallbacks/*",
                "test/plugins/fallbacks/another/*",
                "test/plugins/fallbacks/base/*"
                ],
    }
)
