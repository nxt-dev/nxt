"""nxt dumper with similar interface to no5 dumper

python test/dumpshow.py test/pile.nxt > test/pile.nxt.resolved.py
./build/bin/dumper test/pile.nxt > test/pile.no5.resolved.py
"""

import os
import sys

from nxt import DATA_STATE
from nxt.stage import Stage

try:
    graph_path = os.path.realpath(sys.argv[1])
except IndexError:
    graph_path = ""
if not graph_path:
    raise ValueError("Need a graph to dump!")

stage = Stage.load_from_filepath(graph_path)
comp_layer = stage.build_stage()


start = stage.get_layer_start_nodes(comp_layer)[0]
exec_order = ["/"] + comp_layer.get_exec_order(start)

raw_lines = {}
resolved_lines = {}
for node_path in exec_order:
    raw_node_lines = stage.get_node_code_lines(
        comp_layer.lookup(node_path),
        comp_layer,
        data_state=DATA_STATE.RAW
    )
    raw_lines[node_path] = raw_node_lines
    resolved_node_lines = []
    for line in raw_node_lines:
        resolved_node_lines.append(stage.resolve(
            comp_layer.lookup(node_path),
            line,
            comp_layer
        ))
    resolved_lines[node_path] = resolved_node_lines

for node_path in exec_order:
    print("\n".join(resolved_lines[node_path]))
