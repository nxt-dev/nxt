import setuptools
import json
import io

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
    name="nxt-core",
    version=api_version,
    author="The nxt contributors",
    author_email="dev@opennxt.dev",
    description=desc,
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nxt-dev/nxt",
    packages=setuptools.find_packages(),
    python_requires='>=2.7, <3.11',
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
