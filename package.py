import json

name = "nxt_core"

description = (
    "A general purpose code compositor designed for rigging, scene assembly, "
    "and automation. (node execution tree)"
)

authors = ["The nxt contributors dev@opennxt.dev"]


# read version json file so we only have to define version number in one location
@early()
def version():
    with open("nxt/version.json", "r") as f:
        data = json.load(f)

    api = data["API"]
    return f"{api['MAJOR']}.{api['MINOR']}.{api['PATCH']}"


tools = ["nxt"]

variants = []

# The released package used to come from `rez pip`, which pinned a variant per
# interpreter. Built from source it is pure python, so one build serves every
# supported interpreter.
requires = ["python-3.10+<3.14"]

private_build_requires = []

release_branches = ["sb_release"]

help = [["Home Page", "https://github.com/nxt-dev/nxt"]]


def commands():
    import os

    if "dev" in ephemerals and os.path.exists(expandvars("$SB_DEV_ROOT/nxt")):
        env.PYTHONPATH.prepend("$SB_DEV_ROOT/nxt")
        env.PATH.prepend(expandvars("$SB_DEV_ROOT/nxt/bin"))
    else:
        env.PYTHONPATH.append("{root}/python")
        env.PATH.append("{root}/bin")


# A script rather than a shell one liner, so the build behaves the same on
# Windows as on the macOS and Linux runners.
build_command = "python {root}/rez_build.py"

