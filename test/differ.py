"""Diff the results of no5 against nxt, print a report card."""
import os
import sys
import difflib

import nxt
from nxt.stage import Stage
import no5
from no5 import no5_tokens

try:
    graph_path = os.path.realpath(sys.argv[1])
except IndexError:
    graph_path = ""
if not graph_path:
    raise ValueError("Need a graph to diff!")
test_file = "/home/michael/Projects/nxt/other_n/test/pile.nxt"

print_title = lambda words : print("> {} <".format(words).center(os.get_terminal_size().columns, "-"))

PRINT_DIFF = ONLY_ONE = False

print_title("Loading")

print("Loading no5", end="")
no5_comp = no5.CompGraph(graph_path)
print(" Done\nLoading nxt", end="")
nxt_stage = Stage.load_from_filepath(graph_path)
print(" Done\nComping nxt", end="")
nxt_comp = nxt_stage.build_stage()
print(" Done")

print_title("Loaded, diffing")

nxt_starts = nxt_stage.get_layer_start_nodes(nxt_comp)
try:
    no5_starts = no5_comp.get_starts()
except:
    no5_starts = []
if set(nxt_starts) != set(no5_starts):
    print("Starts differ.")
    if PRINT_DIFF:
        sys.stdout.writelines(
            difflib.unified_diff(sorted(nxt_starts), sorted(no5_starts),
                                fromfile='nxt', tofile='no5')
        )
        print("")
else:
    print("Starts match.")

start = None
try:
    start = sys.argv[2]
except IndexError:
    pass

if start:
    print_title("Only diffing {0}".format(start))
    no5_exec = [start]
else:
    start = nxt_starts[0]

    if not nxt_comp.node_exists(start):
        raise ValueError("Cannot start with a node that doesn't exist")
    nxt_exec = ["/"] + nxt_comp.get_exec_order(start)
    no5_exec = no5_comp.get_exec_order(start)
    if nxt_exec != no5_exec:
        print("Exec orders differ.")
        if PRINT_DIFF:
            print(" ".join(nxt_exec))
            print(" ".join(no5_exec))
    else:
        print("Exec orders match.")

print_title("Raw")

raw_lines = {"no5": {}, "nxt": {}}
raw_broken = 0

for node in no5_exec:
    print(".", end="")
    nxt_raw_lines = nxt_stage.get_node_code_lines(nxt_comp.lookup(node), nxt_comp, data_state=nxt.DATA_STATE.RAW)
    no5_raw_lines = no5_comp.get_node_code_lines(node, False)
    if nxt_raw_lines != no5_raw_lines:
        raw_broken += 1
        if not PRINT_DIFF:
            continue
        print("")
        sys.stdout.writelines(
            difflib.unified_diff(nxt_raw_lines, no5_raw_lines,
                                fromfile='nxt: ' + node, tofile='no5: ' + node)
        )
        print("") # Just need the newline for the above.
        if ONLY_ONE:
            break
    raw_lines["no5"][node] = no5_raw_lines
    raw_lines["nxt"][node] = nxt_raw_lines

if raw_broken:
    print("\nRaw {}% match.".format((raw_broken / len(no5_exec)) * 10))
else:
    print("\nRaw matches.")


print_title("Resolved")

resolved_lines = {"no5": {}, "nxt": {}}
resolved_broken = 0

skip_nodes = []

for node in no5_exec:
    nxt_resolved_lines = []
    no5_resolved_lines = []
    if node in skip_nodes:
        resolved_broken += 1
        print("S", end="")
        continue
    for line in raw_lines["nxt"][node]:
        nxt_resolved_lines.append(nxt_stage.resolve(nxt_comp.lookup(node), line, nxt_comp) + "\n")
    for line in raw_lines["no5"][node]:
        no5_resolved_lines.append(no5_tokens.resolve(line, node, no5_comp) + "\n")
    if nxt_resolved_lines != no5_resolved_lines:
        resolved_broken += 1
        print("X", end="")
        if not PRINT_DIFF:
            if ONLY_ONE:
                break
            continue
        print("")
        print ("\n".join(raw_lines["no5"][node]))
        print("")
        sys.stdout.writelines(
            difflib.unified_diff(
                nxt_resolved_lines, no5_resolved_lines,
                fromfile='nxt: ' + node, tofile='no5: ' + node)
        )
        if ONLY_ONE:
            break
    else:
        print(".", end="")
    resolved_lines["no5"][node] = no5_resolved_lines
    resolved_lines["nxt"][node] = nxt_resolved_lines

if resolved_broken and not ONLY_ONE:
    print("\nResolved {} broken out of {} ({}%)".format(
        resolved_broken,
        len(no5_exec),
        int(100 - (resolved_broken / len(no5_exec)) * 100)
    ))
elif not resolved_broken:
    print("\nResovled matches.")

print_title("Done")
