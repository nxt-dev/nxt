"""Time build_stage on a graph.

    python comp_bench.py [graph.nxt] [--profile] [--runs N]

With no graph it uses NXT_PERF_GRAPH.
"""
import sys
import time
import statistics
import cProfile
import pstats

from common import use_repo_nxt, big_graph

use_repo_nxt()

from nxt.session import Session


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    runs = 3
    if "--runs" in sys.argv:
        runs = int(sys.argv[sys.argv.index("--runs") + 1])
        args = [a for a in args if a != str(runs)]
    graph = args[0] if args else big_graph()
    if not graph:
        print("no graph given and NXT_PERF_GRAPH is not set")
        return 2

    start = time.time()
    stage = Session().load_file(graph)
    load_secs = time.time() - start

    timings = []
    comp = None
    for _ in range(runs):
        start = time.time()
        comp = stage.build_stage()
        timings.append(time.time() - start)

    print("graph       : %s" % graph.replace("\\", "/").rsplit("/", 1)[-1])
    print("comp nodes  : %d" % len(comp._nodes_path_as_key))
    print("load        : %.3fs" % load_secs)
    print("build_stage : median %.3fs   (%s)"
          % (statistics.median(timings),
             ", ".join("%.2f" % t for t in timings)))

    if "--profile" in sys.argv:
        pr = cProfile.Profile()
        pr.enable()
        stage.build_stage()
        pr.disable()
        pstats.Stats(pr).sort_stats("tottime").print_stats(20)
    return 0


if __name__ == "__main__":
    sys.exit(main())
