# Performance and equivalence harnesses

Tools for changing the comp and execution engines without changing what they
produce. Not shipped with the package, not run by the unit tests.

The comp engine has a lot of behaviour that no unit test pins down: which
layer's opinion wins for a parameter, the base class chain each node ends up
with, the order proxies get created in. These harnesses capture all of it so
a change can be shown to be inert before anyone has to trust it.

## Setup

Nothing to install. Every script imports `nxt` from this checkout, whatever
the working directory.

Point `NXT_PERF_GRAPH` at a real production graph to measure against one.
If that graph references files outside the repo, set `NXT_FILE_ROOTS` the
way its environment sets it:

```bash
export NXT_PERF_GRAPH="/path/to/some_rig.nxt"
export NXT_FILE_ROOTS="..."   # as the project sets it
```

Without it the harnesses still run, against the test suite graphs and any
graphs from `gen_graph.py`.

Generated graphs and captured signatures go in `_work/`, which is not
tracked.

## Proving a change is inert

This is the important one. Run it around any change to compositing:

```bash
python gen_graph.py && python gen_graph.py --big   # optional, adds scale
git stash                                          # back to current code
python verify_comp.py capture before
git stash pop
python verify_comp.py capture after
python verify_comp.py compare before after
```

`compare` exits non zero if anything differs, and prints which nodes and
which fields. For each node it checks every internal attr and its source,
the base chain and MRO, every parameter's raw value, resolved value,
comment, data dict and inherited source, which parameters came through an
instance versus a parent, comped code, child order both raw and ordered,
plus exec order, node creation order and start nodes for the graph.

The expensive per node checks (resolved values, inherited attr lists) are
O(n) each inside the engine, so they run on every node of a small graph and
on a stable spread of 150 to 200 nodes of a large one.

For changes to **execution** rather than compositing, use `build_sig.py`,
which records the fully resolved code and frame attributes for every node
that runs. That is what catches a regression in `file::` / `filelist::`
resolution, historical fallbacks or `infer_lower_comp`:

```bash
git stash && python build_sig.py _work/build_before.json && git stash pop
python build_sig.py _work/build_after.json
# compare the printed sha, or diff the two json files
```

`diff_sort.py` checks `Stage.sort_instances` against the scan based
algorithm it replaced, during real comps. Its output order feeds proxy
creation order, so it has to match item for item.

## Measuring

```bash
python comp_bench.py [graph.nxt] [--profile]   # time build_stage
python build_bench.py [graph.nxt] [--profile]  # time a build
```

`build_bench.py` runs the full execution path with node computes replaced by
a no-op, so it reports what nxt itself costs around each node rather than
what the DCC costs inside it. It also separates out the comps a build
triggers, since executing re-comps the stage on top of the comp you already
have.

## Files

| | |
|---|---|
| `common.py` | paths, graph corpus, shared helpers |
| `comp_sig.py` | deep signature of one comped stage |
| `verify_comp.py` | capture and compare comp signatures over the corpus |
| `build_sig.py` | signature of everything a build resolves |
| `comp_bench.py` | time `build_stage` |
| `build_bench.py` | time a build, comp and nxt overhead split out |
| `diff_sort.py` | `sort_instances` against the algorithm it replaced |
| `gen_graph.py` | generate instance heavy graphs of a chosen size |
