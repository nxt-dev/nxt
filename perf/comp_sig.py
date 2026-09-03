"""Deep signature of a comped stage, used to prove comp behaviour is unchanged.

Captures what the comp engine is responsible for producing:

  * which nodes exist, and the order they were created in
  * every internal attr and the layer/node its opinion came from
  * the base class chain and MRO, which is what the comp arcs actually build
  * every parameter's raw value, comment, data dict, and inherited source
  * comped code, child order (raw and ordered), exec order, start nodes

Resolved parameter values and the inherited/instanced attr name lists are
O(n) per node inside the engine, so on a production sized graph they cost
minutes. They are captured for every node on small graphs and for a
deterministic sample on large ones, which still catches a regression while
keeping a run to seconds.

    python comp_sig.py <graph.nxt> <out.json> [--sample N]
"""
import sys
import json
import hashlib

from common import use_repo_nxt, json_safe, try_call

use_repo_nxt()

from nxt.nxt_node import INTERNAL_ATTRS, META_ATTRS
from nxt.session import Session
from nxt import nxt_path


def node_signature(stage, comp_layer, path, node, deep):
    sig = {}
    for attr in sorted(INTERNAL_ATTRS.ALL):
        sig[attr] = try_call(lambda a=attr: getattr(node, a))
        src = attr + META_ATTRS.SOURCE
        if hasattr(node, src):
            sig[src] = try_call(lambda s=src: getattr(node, s))
    # The base chain is what the comp arcs build.
    sig["bases"] = [getattr(b, INTERNAL_ATTRS.NAME, "?")
                    for b in node.__bases__]
    sig["mro"] = [getattr(b, INTERNAL_ATTRS.NAME, "?") for b in node.__mro__]
    # Parameters. The source is the important part, it says which layer and
    # node won the opinion, which is exactly what compositing decides.
    attrs = {}
    for name in sorted(stage.get_node_attr_names(node)):
        entry = {
            "raw": try_call(lambda n=name: stage.get_node_attr_value(
                node, n, comp_layer, resolved=False)),
            "source": try_call(lambda n=name: stage.get_node_attr_source(node,
                                                                        n)),
            "comment": try_call(lambda n=name: stage.get_node_attr_comment(
                node, n)),
            "data": try_call(lambda n=name: stage.get_node_attr_data(
                node, n, comp_layer, quiet=True)),
        }
        if deep:
            entry["resolved"] = try_call(
                lambda n=name: stage.get_node_attr_value(node, n, comp_layer,
                                                         resolved=True))
        attrs[name] = entry
    sig["attrs"] = attrs
    sig["local_attrs"] = try_call(lambda: stage.get_node_local_attrs_data(node))
    if deep:
        # Which parameters arrived through an instance versus a parent.
        sig["instanced_attrs"] = sorted(
            stage.get_node_instanced_attr_names(node, comp_layer) or [])
        sig["inherited_attrs"] = sorted(
            stage.get_node_inherited_attr_names(node, comp_layer) or [])
    sig["code"] = try_call(lambda: stage.get_node_code_lines(node, comp_layer))
    # Unsorted, so a change in the order nodes were created or cached shows
    # up rather than being normalised away.
    sig["children"] = json_safe(comp_layer.children(path,
                                                    comp_layer.RETURNS.Path))
    sig["children_ordered"] = try_call(
        lambda: comp_layer.children(path, comp_layer.RETURNS.Path,
                                    ordered=True))
    return sig


def stage_signature(filepath, sample=None):
    """
    :param sample: if set, only this many nodes get the expensive deep
    checks. Chosen by stride over the sorted paths, so the selection is
    stable across runs and spread across the graph.
    """
    stage = Session().load_file(filepath)
    comp = stage.build_stage()
    paths = sorted(comp._nodes_path_as_key.keys())
    if sample is None or sample >= len(paths):
        deep_paths = set(paths)
    else:
        stride = max(1, len(paths) // sample)
        deep_paths = set(paths[::stride][:sample])
    out = {"node_count": len(paths),
           "failure": bool(comp.failure),
           "deep_count": len(deep_paths),
           "nodes": {}}
    for path in paths:
        node = comp._nodes_path_as_key[path]
        out["nodes"][path] = node_signature(stage, comp, path, node,
                                            path in deep_paths)
    out["exec_order"] = try_call(lambda: comp.get_exec_order(nxt_path.WORLD))
    # The order nodes were added to the layer. Proxy creation order feeds
    # this, so it catches any reordering of the comp passes.
    out["insertion_order"] = list(comp._nodes_path_as_key.keys())
    out["node_table"] = [nxt_path.node_namespace_to_str_path(ns)
                         for ns, _ in comp._node_table]
    out["start_nodes"] = try_call(lambda: stage.get_layer_start_nodes(comp))
    return out


def main():
    args = [a for a in sys.argv[1:]]
    sample = None
    if "--sample" in args:
        i = args.index("--sample")
        sample = int(args[i + 1])
        del args[i:i + 2]
    sig = stage_signature(args[0], sample=sample)
    blob = json.dumps(sig, indent=1, sort_keys=True)
    with open(args[1], "w") as f:
        f.write(blob)
    name = args[1].replace("\\", "/").rsplit("/", 1)[-1]
    print("%-30s nodes=%-6d deep=%-5d sha=%s"
          % (name, sig["node_count"], sig["deep_count"],
             hashlib.sha1(blob.encode()).hexdigest()[:16]))


if __name__ == "__main__":
    main()
