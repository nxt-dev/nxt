"""Signature of everything a build resolves, to prove execution is unchanged.

Runs the whole execution path with node computes replaced by a no-op, then
records, for every node that ran, the fully resolved code string that would
have been executed and the resolved value of every attribute on the frame
node handed to it.

That covers file:: and filelist:: token resolution, historical fallbacks and
attribute references. It is the check to run against any change touching
resolution, the file fallback plugin, or infer_lower_comp.

    python build_sig.py <graph.nxt> <out.json> [--start /path]

With no graph it uses NXT_PERF_GRAPH.
"""
import sys
import json
import hashlib

from common import use_repo_nxt, json_safe, big_graph

use_repo_nxt()

from nxt.runtime import Console
from nxt.nxt_node import INTERNAL_ATTRS, META_ATTRS
from nxt.session import Session


def main():
    argv = sys.argv[1:]
    start_path = "/init"
    if "--start" in argv:
        i = argv.index("--start")
        start_path = argv[i + 1]
        del argv[i:i + 2]
    if len(argv) == 1:
        graph, out_path = big_graph(), argv[0]
    else:
        graph, out_path = argv[0], argv[1]
    if not graph:
        print("no graph given and NXT_PERF_GRAPH is not set")
        return 2

    Console.runcode = lambda self, code: None

    stage = Session().load_file(graph)
    comp = stage.build_stage()
    exec_order = comp.get_exec_order(start_path)
    runtime = stage.execute(start=start_path, layer=comp)

    sig = {"ran": len(exec_order), "nodes": {}}
    skip = set(INTERNAL_ATTRS.PROTECTED)
    for path in exec_order:
        entry = {}
        node = runtime.lookup(path)
        if node is not None:
            # The resolved compute, tokens and all, as it would have run.
            entry["code"] = json_safe(getattr(node,
                                              INTERNAL_ATTRS.CACHED_CODE,
                                              None))
        frame = runtime.cache_layer.lookup(path)
        attrs = {}
        if frame is not None:
            for attr in sorted(dir(frame)):
                if attr in skip or attr.startswith("__"):
                    continue
                if attr.endswith(META_ATTRS._suffix):
                    continue
                attrs[attr] = json_safe(getattr(frame, attr, None))
        entry["attrs"] = attrs
        sig["nodes"][path] = entry

    blob = json.dumps(sig, indent=1, sort_keys=True)
    with open(out_path, "w") as f:
        f.write(blob)
    print("ran=%d  sha=%s" % (sig["ran"],
                              hashlib.sha1(blob.encode()).hexdigest()[:16]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
