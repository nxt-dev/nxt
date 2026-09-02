"""Time a real build inside Maya, to compare one nxt against another.

build_bench.py measures what nxt costs around each node, with the node
computes replaced by a no-op. That isolates the part of a build that the
comp and resolution work actually changed, but it says nothing about how
long the DCC work inside those computes takes.

This runs the genuine thing. Paste into the Maya script editor, with the
path to this file in your checkout:

    exec(open(r"<nxt checkout>/perf/maya_build_time.py").read())

It builds the graph once with whichever nxt is currently loaded, reports the
time, and tells you how to run the other one for comparison. Each run builds
a real rig into the current scene, so start from an empty scene and expect
it to take as long as a build normally takes.

    time_build()                                  # graph from NXT_PERF_GRAPH
    time_build("path/to/some_rig.nxt")
    time_build(start="/init", new_scene=True)     # wipe the scene first
"""
import os
import sys
import time

GRAPH_ENV_VAR = "NXT_PERF_GRAPH"


def _which_nxt():
    import nxt
    return nxt.__file__


def time_build(graph=None, start="/init", new_scene=True):
    """Build a graph and report where the time went.

    :param graph: .nxt path, defaults to $NXT_PERF_GRAPH
    :param start: start node path
    :param new_scene: open a new scene first, so runs are comparable
    :return: dict of timings
    """
    graph = graph or os.environ.get(GRAPH_ENV_VAR)
    if not graph:
        raise ValueError("no graph given and %s is not set" % GRAPH_ENV_VAR)

    if new_scene:
        from maya import cmds
        cmds.file(new=True, force=True)

    from nxt.session import Session

    print("nxt from : %s" % _which_nxt())
    print("graph    : %s" % graph)

    start_time = time.time()
    stage = Session().load_file(graph)
    load_secs = time.time() - start_time

    start_time = time.time()
    comp = stage.build_stage()
    comp_secs = time.time() - start_time

    exec_order = comp.get_exec_order(start)
    print("comp nodes : %d" % len(comp._nodes_path_as_key))
    print("nodes to run: %d" % len(exec_order))
    print("load       : %.2fs" % load_secs)
    print("comp       : %.2fs" % comp_secs)
    print("building, this is the real thing ...")

    start_time = time.time()
    stage.execute(start=start, layer=comp)
    build_secs = time.time() - start_time

    total = load_secs + comp_secs + build_secs
    print("")
    print("BUILD      : %.1fs" % build_secs)
    print("TOTAL      : %.1fs  (load %.2fs + comp %.2fs + build %.1fs)"
          % (total, load_secs, comp_secs, build_secs))
    print("")
    print("Now compare against the other nxt: restart Maya with it on the")
    print("python path instead, then re-run time_build()")
    return {"load": load_secs, "comp": comp_secs, "build": build_secs,
            "total": total, "nxt": _which_nxt(),
            "nodes_run": len(exec_order)}


if __name__ == "__main__":
    print(__doc__)
    print("time_build is now available. Call time_build() to run.")
