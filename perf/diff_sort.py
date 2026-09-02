"""Check Stage.sort_instances against the scan based algorithm it replaced.

sort_instances used to locate items with list.index and list.remove, which
scan from the front and made the sort quadratic in node count. It now uses
nxt_layer.RankedList. The order it produces feeds proxy creation order, so it
has to match item for item, not merely be a valid ordering.

This runs a real comp of each given graph and compares every deep sort along
the way against the original algorithm.

    python diff_sort.py [graph.nxt ...]

With no graphs it uses the instance heavy test graphs, any generated
graphs, and NXT_PERF_GRAPH if set.
"""
import os
import sys

from common import (use_repo_nxt, TEST_DIR, generated_graphs, big_graph)

use_repo_nxt()

import nxt.stage as stage_mod
from nxt.session import Session
from nxt.nxt_layer import sort_multidimensional_list

# Test graphs that actually exercise instancing.
DEFAULT_GRAPHS = (
    "StageInstanceTest.nxt",
    "StageInstanceTest_Layer0.nxt",
    "StageInstanceAcrossLayersTest.nxt",
    "StageRelativeInstanceChildOrder.nxt",
    "test_proxy_stack.nxt",
    "order.nxt",
)

stats = {"sorts": 0, "items": 0, "mismatch": 0}


def reference(stage, comp_layer, sorted_items, src_dict):
    """The scan based deep sort, verbatim as it was."""
    deep = sorted_items[:]
    offsets = {}
    for item in sorted_items:
        _, node = item
        node_path = comp_layer.get_node_path(node)
        real = stage.instance_is_possible(node_path, node, comp_layer)
        src_item = src_dict.get(real)
        if src_item:
            idx = deep.index(src_item)
            offset = offsets.get(real, 1)
            insert_idx = idx + offset
            deep.remove(item)
            deep.insert(insert_idx, item)
            offsets[real] = offset + 1
    return deep


def install_check():
    original = stage_mod.Stage.sort_instances

    def checked(self, comp_layer, deep_sort=False):
        got = original(self, comp_layer, deep_sort)
        if not deep_sort:
            return got
        # Rebuild the same inputs the real call worked from.
        items, src_dict = [], {}
        for _, node in comp_layer._node_table:
            trace = self.get_instance_sources(node, [], comp_layer)
            item = (trace, node)
            src_dict[comp_layer.get_node_path(node)] = item
            items += [item]
        sort_multidimensional_list(items, sort_by_idx=0)
        want = reference(self, comp_layer, items, src_dict)
        stats["sorts"] += 1
        stats["items"] += len(want)
        got_paths = [comp_layer.get_node_path(n) for _, n in got]
        want_paths = [comp_layer.get_node_path(n) for _, n in want]
        if got_paths != want_paths:
            stats["mismatch"] += 1
            first = next((i for i, (a, b) in enumerate(zip(got_paths,
                                                           want_paths))
                          if a != b), None)
            print("  MISMATCH at index %s: got %r want %r"
                  % (first, got_paths[first], want_paths[first]))
        return got

    stage_mod.Stage.sort_instances = checked


def main():
    graphs = sys.argv[1:]
    if not graphs:
        graphs = [os.path.join(TEST_DIR, n) for n in DEFAULT_GRAPHS]
        graphs += [p for _, p in generated_graphs()]
        big = big_graph()
        if big:
            graphs += [big]
    install_check()
    for path in graphs:
        if not os.path.isfile(path):
            print("  skipped, not found: %s" % path)
            continue
        try:
            Session().load_file(path).build_stage()
        except Exception as e:
            print("  skipped %s (%s)"
                  % (os.path.basename(path), type(e).__name__))
    print("deep sorts compared : %d  (%d items total)"
          % (stats["sorts"], stats["items"]))
    print("mismatches          : %d" % stats["mismatch"])
    return 1 if stats["mismatch"] else 0


if __name__ == "__main__":
    sys.exit(main())
