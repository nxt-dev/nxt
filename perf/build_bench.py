"""Measure what nxt itself costs to run a build, before any node code runs.

A real build of a rig graph is mostly the DCC doing rig work, which nothing
in nxt can speed up. What nxt is responsible for is the per node overhead
around each compute: resolving the code and its file tokens, walking the
node's attributes, deep copying them onto the frame node, compiling, and
cleaning globals afterwards. That is what this measures, by running the
whole execution path with the node compute itself replaced by a no-op.

It also counts the comps a build triggers, because executing re-comps the
stage on top of the comp you already paid for.

    python build_bench.py [graph.nxt] [--start /path] [--profile]

With no graph it uses NXT_PERF_GRAPH.
"""
import sys
import time
import cProfile
import pstats

from common import use_repo_nxt, big_graph

use_repo_nxt()

import nxt.stage as stage_mod
from nxt.session import Session
from nxt.runtime import Console

comps = {"n": 0, "seconds": 0.0}


def _count_comps():
    """Wrap build_stage so the comps a build triggers can be separated out."""
    original = stage_mod.Stage.build_stage

    def counted(self, *args, **kwargs):
        start = time.time()
        result = original(self, *args, **kwargs)
        comps["n"] += 1
        comps["seconds"] += time.time() - start
        return result

    stage_mod.Stage.build_stage = counted


def _neuter_computes():
    """Let everything but the node's own code run."""
    Console.runcode = lambda self, code: None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    start_path = "/init"
    if "--start" in sys.argv:
        start_path = sys.argv[sys.argv.index("--start") + 1]
        args = [a for a in args if a != start_path]
    graph = args[0] if args else big_graph()
    if not graph:
        print("no graph given and NXT_PERF_GRAPH is not set")
        return 2
    profile = "--profile" in sys.argv

    _count_comps()
    _neuter_computes()

    session = Session()
    start = time.time()
    stage = session.load_file(graph)
    load_secs = time.time() - start

    comps["n"] = 0
    comps["seconds"] = 0.0
    start = time.time()
    comp = stage.build_stage()
    first_comp = time.time() - start

    exec_order = comp.get_exec_order(start_path)
    print("graph          : %s" % graph.replace("\\", "/").rsplit("/", 1)[-1])
    print("comp nodes     : %d" % len(comp._nodes_path_as_key))
    print("nodes to run   : %d" % len(exec_order))
    print("load           : %.2fs" % load_secs)
    print("first comp     : %.2fs" % first_comp)

    before_n, before_s = comps["n"], comps["seconds"]
    start = time.time()
    stage.execute(start=start_path, layer=comp)
    run_secs = time.time() - start
    extra_comps = comps["n"] - before_n
    extra_comp_secs = comps["seconds"] - before_s
    overhead = run_secs - extra_comp_secs

    print("execute        : %.2fs total" % run_secs)
    print("  of which comp: %.2fs  (%d extra comp%s triggered by execute)"
          % (extra_comp_secs, extra_comps, "" if extra_comps == 1 else "s"))
    print("  nxt overhead : %.2fs  (%.1f ms per node)"
          % (overhead, overhead / max(len(exec_order), 1) * 1000))
    print("BUILD TOTAL    : %.2fs  (comp %.2fs + nxt overhead %.2fs)"
          % (first_comp + run_secs, first_comp + extra_comp_secs, overhead))

    if profile:
        pr = cProfile.Profile()
        pr.enable()
        stage.execute(start=start_path, layer=comp)
        pr.disable()
        pstats.Stats(pr).sort_stats("tottime").print_stats(20)
    return 0


if __name__ == "__main__":
    sys.exit(main())
