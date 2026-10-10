"""Generate rig shaped graphs to measure compositing against.

Produces a library layer of module archetypes and a rig layer that instances
them many times, including nested instances, which is the shape that makes
compositing expensive. Useful when there is no production graph to hand, and
for pushing past the size of one.

    python gen_graph.py                    # ~4.8k comped nodes
    python gen_graph.py --big              # ~10k comped nodes
    python gen_graph.py <modules> <insts>  # pick your own size

Files land in _work/ next to this script, where verify_comp.py picks them up.
"""
import os
import sys
import json

from common import WORK_DIR


def node(**kwargs):
    data = {"enabled": True}
    data.update(kwargs)
    return data


def build_library(n_modules=24, branch=3, depth=3):
    """Module archetypes. Every third module instances an earlier one, so
    the comp has to resolve nested instance traces rather than flat ones.
    """
    nodes = {}
    roots = []
    child_order = {}
    for m in range(n_modules):
        root = "/mod_{}".format(m)
        roots.append(root)
        nodes[root] = node(code=["# module {}".format(m)],
                           attrs={"modAttr": {"type": "raw",
                                              "value": "m{}".format(m)}})
        if m >= 3 and m % 3 == 0:
            nodes[root]["instance"] = "/mod_{}".format(m - 3)
        stack = [(root, 0)]
        while stack:
            path, d = stack.pop()
            if d >= depth:
                continue
            names = []
            for b in range(branch):
                name = "part{}".format(b)
                names.append(name)
                child_path = path + "/" + name
                nodes[child_path] = node(
                    attrs={"a{}".format(b): {"type": "raw", "value": str(b)}})
                stack.append((child_path, d + 1))
            child_order[path] = names
    for path, order in child_order.items():
        nodes[path]["child_order"] = order
    return nodes, roots


def build_rig(module_roots, n_instances=90):
    nodes = {}
    for i in range(n_instances):
        source = module_roots[i % len(module_roots)]
        name = "rig_{}".format(i)
        nodes["/" + name] = node(
            instance=source,
            attrs={"side": {"type": "raw", "value": "L" if i % 2 else "R"}})
        if i % 5 == 0:
            # A node that instances into the middle of another instance.
            nodes["/" + name + "/sub"] = node(instance=source + "/part0")
    return nodes


def write(path, alias, nodes, references=()):
    data = {"version": "1.17", "alias": alias, "color": "#119B77",
            "references": list(references), "meta_data": {"positions": {}},
            "nodes": nodes}
    with open(path, "w") as f:
        json.dump(data, f, indent=4)
    print("wrote %s (%d authored nodes)" % (path, len(nodes)))


def main():
    big = "--big" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        n_modules, n_instances = int(args[0]), int(args[1])
        suffix = ""
    elif big:
        n_modules, n_instances, suffix = 40, 200, "_big"
    else:
        n_modules, n_instances, suffix = 24, 90, ""

    if not os.path.isdir(WORK_DIR):
        os.makedirs(WORK_DIR)
    lib_name = "lib{}.nxt".format(suffix)
    rig_name = "rig{}.nxt".format(suffix)
    lib_nodes, roots = build_library(n_modules=n_modules)
    write(os.path.join(WORK_DIR, lib_name), "lib" + suffix, lib_nodes)
    rig_nodes = build_rig(roots, n_instances=n_instances)
    write(os.path.join(WORK_DIR, rig_name), "rig" + suffix, rig_nodes,
          references=["./" + lib_name])


if __name__ == "__main__":
    main()
