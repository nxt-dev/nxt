import setuptools
import json

with open("README.md", "r") as fh:
    long_description = fh.read()

desc = ("A general purpose code compositor designed for rigging, "
        "scene assembly, and automation. (node execution tree)")

with open("nxt/version.json", 'r') as fh:
    version_data = json.load(fh)
api_v_data = version_data['API']
api_major = api_v_data['MAJOR']
api_minor = api_v_data['MINOR']
api_patch = api_v_data['PATCH']
api_version = 'v{}.{}.{}'.format(api_major, api_minor, api_patch)

setuptools.setup(
    name="nxt",
    version=api_version,
    author="The nxt contributors",
    author_email="dev@opennxt.dev",
    description=desc,
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nxt-dev/nxt",
    packages=setuptools.find_packages(),
    python_requires='>=2.7, <=3.7',
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
                "nxt/test/spec_graphs/*",
                "nxt/test/legacy/*",
                "nxt/test/plugins/*",
                "nxt/test/plugins/fallbacks/*",
                "nxt/test/plugins/fallbacks/another/*",
                "nxt/test/plugins/fallbacks/base/*"
                ],
    }
)
