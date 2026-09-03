"""Shared bits for the performance and equivalence harnesses.

Everything here resolves paths from this file's location, so the harnesses
work from any checkout and any working directory.
"""
import os
import sys

PERF_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(PERF_DIR)
TEST_DIR = os.path.join(REPO_ROOT, "nxt", "test")
# Generated graphs and captured signatures land here, not in the repo.
WORK_DIR = os.path.join(PERF_DIR, "_work")

# A big production graph to measure against, if there is one. Set
# NXT_PERF_GRAPH to a .nxt path. Graphs referencing files outside the repo
# also need NXT_FILE_ROOTS and NXT_ROOTS_CONFIG_FILE set the way the graph's
# environment sets them.
BIG_GRAPH_ENV_VAR = "NXT_PERF_GRAPH"

# Graphs that are meant to fail, or that trip a pre-existing crash unrelated
# to anything measured here.
SKIP_GRAPHS = {
    "empty.nxt",
    # Trips a crash in the legacy converter, before compositing happens.
    "0.45.0_to_LATEST.nxt",
}


def use_repo_nxt():
    """Import nxt from this checkout rather than an installed copy."""
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)


def work_dir(*parts):
    """Path inside the scratch area, creating it if needed."""
    path = os.path.join(WORK_DIR, *parts)
    parent = path if not os.path.splitext(path)[1] else os.path.dirname(path)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    return path


def big_graph():
    """The graph named by NXT_PERF_GRAPH, or None if unset or missing."""
    path = os.environ.get(BIG_GRAPH_ENV_VAR)
    if path and os.path.isfile(path):
        return path
    return None


def test_graphs():
    """Every graph in the nxt test suite, as (label, path) pairs."""
    graphs = []
    for name in sorted(os.listdir(TEST_DIR)):
        if name.endswith(".nxt") and name not in SKIP_GRAPHS:
            graphs += [(name, os.path.join(TEST_DIR, name))]
    legacy = os.path.join(TEST_DIR, "legacy")
    if os.path.isdir(legacy):
        for name in sorted(os.listdir(legacy)):
            if name.endswith(".nxt") and name not in SKIP_GRAPHS:
                graphs += [("legacy_" + name, os.path.join(legacy, name))]
    return graphs


def generated_graphs():
    """Synthetic graphs from gen_graph.py, if they have been generated."""
    graphs = []
    for name in ("rig.nxt", "rig_big.nxt"):
        path = os.path.join(WORK_DIR, name)
        if os.path.isfile(path):
            graphs += [(name, path)]
    return graphs


def corpus():
    """Everything worth checking, as (label, path, deep_sample) triples.

    deep_sample caps how many nodes get the expensive per node checks. Small
    graphs get all of them, large ones get a spread out sample so a run
    stays in the seconds rather than the minutes.
    """
    graphs = [(label, path, None) for label, path in test_graphs()]
    graphs += [(label, path, 200) for label, path in generated_graphs()]
    big = big_graph()
    if big:
        graphs += [(os.path.basename(big), big, 150)]
    return graphs


def json_safe(value):
    """JSON friendly form of an arbitrary attribute value."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in sorted(value.items())}
    return repr(value)


def try_call(fn):
    """Call fn, turning any failure into a comparable marker."""
    try:
        return json_safe(fn())
    except Exception as e:
        return "<err %s: %s>" % (type(e).__name__, e)
