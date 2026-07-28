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
- adjacent-swap order search ranked by integer visible exact-row accuracy,
  then full-visible XAG gates, visible bit accuracy, shared ROBDD nodes,
  policy, and numeric order;
- one final all-visible refit of the selected configuration, followed by
  exhaustive completed-table/XAG equivalence and 100% training consistency.

The maximum number of evaluated orders will be frozen from a synthetic
20-input timing calibration before any public row is mounted. It may not be
changed after public access.

## Parent commit and diff digest

Parent commit:
`8562e0f676780b1e08d83783ae77fbb708536647`.

Initial hypothesis diff contains only this `LOG.md`; the implementation commit
and its clean-tree digest will be recorded before any public bundle is mounted.

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
  --folds 5 --seed S --policy POLICY --max-order-evals N
```

`S` is exactly 64 lowercase hexadecimal characters. Public execution must use
the bounded experiment runner with a clean source commit.

## Hardware and five-minute cap

Development and synthetic timing run locally on the tracked local CPU card.
Every algorithm cell includes startup and cleanup and has a hard 300-second
wall limit. Local execution is required while cells remain below 10 minutes
and 16 GB. `hpccube` is not authorized for this hypothesis unless a promoted
cell is later shown to exceed that boundary and the exact Slurm submission is
separately ratified.

## Result: accuracy, gates, runtime, memory, verifier

Not run. No public rows or sealed evaluator have been accessed.

## Failure signal and interpretation

Pivot or reject the hypothesis if it cannot reproduce all care rows, is
nondeterministic, disagrees with exhaustive XAG evaluation, exceeds its frozen
order budget or 300-second cell cap, or loses visible exact-row accuracy to
both frozen baselines. Timeouts and failures remain recorded evidence.

## Next pivot

Implement and differentially test the synthetic-only care-set reducer. Then
time the fixed synthetic 20-input calibration, freeze `N`, and commit the
learner before any public mount.
