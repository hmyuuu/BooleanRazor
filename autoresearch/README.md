# Five-minute autoresearch protocol

Each hypothesis gets a fresh worktree from the latest accepted commit. Replace
the placeholder with an opaque experiment ID:

```bash
git worktree add ../occam-exp-<opaque-id> \
  -b codex/occam-exp-<opaque-id> <accepted-commit>
cp tracks/qcs/solutions/hmyuuu/autoresearch/LOG_TEMPLATE.md \
  ../occam-exp-<opaque-id>/LOG.md
```

Never reuse a worktree for another hypothesis. Before attaching any data, fill
the hypothesis, permitted-data, and parent-commit sections of the root
`LOG.md`, then include that log in the synthetic-test-only algorithm commit.
Every later result update is a separate evidence commit. This makes a clean
`git status --porcelain=v1` compatible with the required Git bundle without
discarding the scientific record.

A promoted change is reviewed and cherry-picked into the accepted branch. A
failed worktree remains available until its manifest and `LOG.md` lessons are
consolidated.

## Proposal/evaluator firewall

The three roles have disjoint evidence access:

1. The **custodian** generates the sealed complete tables, opaque IDs, public
   training rows, and checksums. Per-example mismatches and source-family
   labels remain in an ignored, custodian-only results root.
2. The **proposer** receives only the reviewed contract, public rows, test
   domain policy, and aggregate lessons. It writes a completed table and
   circuit without access to sealed rows, mappings, or evaluator diagnostics.
3. The **evaluator** checks the sealed rows and returns only `experiment_id`,
   train exact accuracy, sealed exact accuracy, bit accuracy, reachable gates,
   elapsed time, peak memory, and terminal status.

Before transfer, recursively inspect the proposer bundle. Reject it if a path,
CSV header, or JSON key contains `family`, `generator`, `ground_truth`,
`test_outputs`, or a sealed digest. Values not named by the reviewed return
contract, including per-example failures and family labels, never cross back
to the proposer.

## Evidence boundary

`run-experiment.py` consumes one cell from a frozen native run root and writes
only that cell's logs, artifacts, and terminal manifest. Its five-minute
deadline includes child startup. `materialize-slurm-failures.py` may fill a
missing manifest only from separately captured raw Slurm parsable accounting
and the exact task log; it never creates a successful observation.

The stable top-level harness is intentionally unchanged. The approved raw
accounting capture command remains deferred until the Task 14 resource-card
ratification.
