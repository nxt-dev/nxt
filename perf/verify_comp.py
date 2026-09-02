"""Capture or compare comp signatures across a corpus of graphs.

    python verify_comp.py capture <tag>      write signatures to _work/sigs/<tag>
    python verify_comp.py compare <a> <b>    diff two captured sets

The workflow for any change to the comp engine is:

    git stash                        # get back to the code you are changing
    python verify_comp.py capture before
    git stash pop
    python verify_comp.py capture after
    python verify_comp.py compare before after

The corpus is every graph in the nxt test suite, plus the synthetic
instance heavy graphs from gen_graph.py if they have been generated, plus
the graph named by NXT_PERF_GRAPH if it is set. So a change has to hold up
on tricky small cases and at production scale at once.

Exits non zero if anything differs, so it can gate a change.
"""
import os
import sys
import json
import time
import subprocess

from common import corpus, work_dir, PERF_DIR

SIG_SCRIPT = os.path.join(PERF_DIR, "comp_sig.py")


def capture(tag):
    out_dir = work_dir("sigs", tag, "")
    graphs = corpus()
    print("capturing %d graph(s) to %s\n" % (len(graphs), out_dir))
    failures = 0
    for label, path, sample in graphs:
        out = os.path.join(out_dir, label + ".json")
        cmd = [sys.executable, SIG_SCRIPT, path, out]
        if sample:
            cmd += ["--sample", str(sample)]
        start = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              cwd=PERF_DIR)
        took = time.time() - start
        if proc.returncode != 0:
            failures += 1
            print("%-34s FAILED\n%s" % (label, proc.stderr[-600:]))
            continue
        print("%-34s %6.1fs  %s" % (label, took, proc.stdout.strip()))
    if failures:
        print("\n%d graph(s) failed to capture" % failures)
    return failures


def compare(tag_a, tag_b):
    dir_a = work_dir("sigs", tag_a, "")
    dir_b = work_dir("sigs", tag_b, "")
    names = sorted(set(os.listdir(dir_a)) | set(os.listdir(dir_b)))
    bad = 0
    for name in names:
        path_a, path_b = os.path.join(dir_a, name), os.path.join(dir_b, name)
        if not (os.path.isfile(path_a) and os.path.isfile(path_b)):
            print("%-34s MISSING on one side" % name)
            bad += 1
            continue
        with open(path_a) as f:
            a = json.load(f)
        with open(path_b) as f:
            b = json.load(f)
        if a == b:
            print("%-34s identical  (%d nodes)" % (name, a["node_count"]))
            continue
        bad += 1
        print("%-34s DIFFERS" % name)
        _report_diff(a, b)
    print("\n%d graph(s) differ out of %d" % (bad, len(names)))
    return bad


def _report_diff(a, b, limit=12):
    if a["node_count"] != b["node_count"]:
        print("    node_count %s -> %s" % (a["node_count"], b["node_count"]))
    for key in ("exec_order", "insertion_order", "node_table", "start_nodes"):
        if a.get(key) != b.get(key):
            same_members = (isinstance(a.get(key), list)
                            and sorted(a[key]) == sorted(b.get(key) or []))
            note = " (same members, different order)" if same_members else ""
            print("    %s differs%s" % (key, note))
    nodes_a, nodes_b = a["nodes"], b["nodes"]
    only_a = sorted(set(nodes_a) - set(nodes_b))
    only_b = sorted(set(nodes_b) - set(nodes_a))
    if only_a:
        print("    only in A (%d): %s" % (len(only_a), only_a[:limit]))
    if only_b:
        print("    only in B (%d): %s" % (len(only_b), only_b[:limit]))
    shown = 0
    for path in sorted(set(nodes_a) & set(nodes_b)):
        if nodes_a[path] == nodes_b[path]:
            continue
        fields = [k for k in sorted(set(nodes_a[path]) | set(nodes_b[path]))
                  if nodes_a[path].get(k) != nodes_b[path].get(k)]
        print("    %s  fields: %s" % (path, fields))
        for field in fields[:3]:
            print("        A %s = %.200s"
                  % (field, json.dumps(nodes_a[path].get(field))))
            print("        B %s = %.200s"
                  % (field, json.dumps(nodes_b[path].get(field))))
        shown += 1
        if shown >= limit:
            print("    ... more nodes differ")
            break


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    if sys.argv[1] == "capture":
        return 1 if capture(sys.argv[2]) else 0
    if sys.argv[1] == "compare":
        return 1 if compare(sys.argv[2], sys.argv[3]) else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
