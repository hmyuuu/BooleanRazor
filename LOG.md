# Experiment task-11-care-bdd

## Hypothesis

A complemented-edge, shared multi-root ROBDD trained directly on the visible
care set can preserve every observed output while completing unobserved
branches deterministically. Reusing a nonempty sibling when the other branch
is empty should improve five-fold visible exact-row accuracy over zero-filling;
deterministic variable-order search should reduce the final shared XAG gate
count without consulting hidden rows.

The predeclared configuration grid is:

- empty-care policy: `reuse-sibling`, `zero`;
- five folds derived by Task 13 from a 64-lowercase-hex selection seed;
- deterministic grouped, interleaved, reversed-grouped, and
  reversed-interleaved seed orders;
- adjacent-swap beam search with width `4`, at most `32` rounds, and at most
  `32` unique visible-CV order evaluations, ranked by integer visible
  exact-row accuracy,
  then full-visible XAG gates, visible bit accuracy, shared ROBDD nodes,
  policy, and numeric order;
- one final all-visible refit of the selected configuration, followed by
  exhaustive completed-table/XAG equivalence and 100% training consistency.

The 180-cell candidate design freezes
`method=care-bdd-reuse-sibling`; `zero` remains a synthetic ablation and
checked API alternative. The production CLI rejects `zero`, requires the
frozen maximum of `32` evaluations, and cannot override widths, raw training
paths, folds, beam width, or round count. These values may not be changed after
public access.

## Parent commit and diff digest

Parent commit:
`8562e0f676780b1e08d83783ae77fbb708536647`.

Hypothesis commit:
`016d0d1` (`research: precommit care-BDD hypothesis`).

The synthetic-only implementation commit and its clean-tree digest will be
recorded in a follow-up log commit before any public bundle is mounted.

## Permitted data

Until the synthetic-only implementation commit is frozen:

- tracked protocol, manifest metadata, commitments, and schemas;
- generated synthetic partial/complete Boolean tables;
- disclosed-v1 arithmetic functions only as explicitly labelled controls;
- no public `train.csv`, sealed row, hidden label, family/source identifier,
  evaluator feedback, private digest, or baseline outcome.

Production learning may later read public rows only through Task 13
`PublicSuite`. The learner API may accept `PartialTable`, never a sealed
`CompleteTable`.

## Command, seed, and environment

Synthetic verification uses locked release-mode Cargo commands. Production
cells, if later authorized and the frozen public archive is available, use:

```text
occam learn-care PUBLIC_ROOT OPAQUE_ID OUTPUT_DIR \
  --folds 5 --seed S --policy reuse-sibling --max-order-evals 32
```

`S` is exactly 64 lowercase hexadecimal characters. Public execution must use
the design-bound
`SHA256(COMMITMENT || "care-bdd-reuse-sibling" || opaque_id)` value; the CLI
recomputes it and rejects any other valid seed. Execution must use the bounded
experiment runner with a clean source commit.

## Hardware and five-minute cap

Development and synthetic timing run locally on the tracked local CPU card.
Every algorithm cell includes startup and cleanup and has a hard 300-second
wall limit. Local execution is required while cells remain below 10 minutes
and 16 GB. `hpccube` is not authorized for this hypothesis unless a promoted
cell is later shown to exceed that boundary and the exact Slurm submission is
separately ratified.

## Result: accuracy, gates, runtime, memory, verifier

Synthetic worst-width timing calibration used 20 inputs, 21 outputs, 104,857
deterministically generated visible rows, five folds, and the complete
artifact path including final enumeration, XAG extraction, netlist
serialization, and exhaustive verification:

- `max_order_evals=1`: `17.621493` seconds;
- `max_order_evals=2`: `19.372526` seconds;
- `max_order_evals=32`: `63.161153` seconds;
- independent `max_order_evals=32` repeat: `65.831928` seconds.

The 32-evaluation result is 4.75× below the 300-second cap on the declared
local development host. It emitted a 45,088,781-byte completed table and a
905,959-byte circuit, and the parsed emitted netlist agreed exhaustively with
all 1,048,576 completed rows. This is timing and exactness evidence only; no
public accuracy, baseline comparison, or sealed score exists.

An attempted `/usr/bin/time -l` wrapper did not yield trustworthy peak-memory
evidence in the managed sandbox: the child test passed, but the wrapper exited
`1` after `sysctl kern.clockrate: Operation not permitted` and reported an
invalid wall time. The failure is retained; promoted cells will obtain memory
from the bounded runner rather than this wrapper.

## Failure signal and interpretation

Pivot or reject the hypothesis if it cannot reproduce all care rows, is
nondeterministic, disagrees with exhaustive XAG evaluation, exceeds its frozen
order budget or 300-second cell cap, or loses visible exact-row accuracy to
both frozen baselines. Timeouts and failures remain recorded evidence.

## Next pivot

Finish independent code/spec review, record the clean synthetic-only
implementation commit and tree digest here, then run public cells only if the
frozen archive is supplied through the trusted Task 13 importer.
