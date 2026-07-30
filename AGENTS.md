# BooleanRazor Agent Guide

## Current answer

Keep disclosed, synthetic, visible-blind, and sealed evidence separate.

## Choose the activity

1. Read `GOAL.md`, `docs/STATUS.md`, the active `docs/plans/` plan, and
   `docs/handoff/SESSION_HANDOFF.md`.
2. Inspect `git status --short`, preserve unrelated work, and from a clean
   checkout run:

   ```bash
   make setup
   make skills
   make test
   make report-check
   ```

3. Choose the evidence track before accessing data or changing a claim.
4. Get approval before heavy installs, nonpublic data, sealed access, or
   remote compute.
5. Use `skills/exact-circuit-optimization/SKILL.md` for optimizations,
   `autoresearch/README.md` for bounded cells, `scripts/record-verification.py`
   for Julia proof, `skills/circuit-evidence-promotion/SKILL.md` for promotion,
   and `skills/using-slurm/SKILL.md` for Slurm.

Use test-driven development for code or contract changes.

## Choose the evidence track

| Track | Permitted evidence | Highest decision |
| --- | --- | --- |
| `disclosed_control` | Known v1 mappings and disclosed data | `promote_control` |
| `synthetic` | Generated fixtures without public or sealed rows | `advance_public_candidate` |
| `blind_visible` | Reviewed public extraction through the importer | `freeze_candidate` |
| `sealed_confirmation` | Frozen candidate evaluated by the custodian | `promote_blind_result` |

Do not upgrade claims through wording. Synthetic results stay synthetic,
historical records stay branch-only, and internal equivalence is not Official
Julia verification.

A=`x+y`, B=`abs(x-y)`, C=`x*y`, and D=`x²+y²` are disclosed controls. Their
37, 49, 168, and 127 gates are upper bounds. Count each reachable fan-in-two
XOR or AND once across all outputs; negation is free.

## Data and experiment rules

- Record the data boundary and frozen run specification in `LOG.md`.
- Give each research hypothesis a fresh worktree and root `LOG.md`.
- Read public rows only through the reviewed `OCCAM_REBLIND_PUBLIC_ROOT`.
- Keep sealed rows, identities, private digests, per-example failures, and
  custodian state from the proposer.
- Record `blocked` when data is absent; do not substitute or fabricate.
- Cap cells at 300 seconds, including startup and cleanup. Use absolute paths
  because children run inside their cell directories.
- Preserve failed, invalid, rejected, tied, timed-out, and OOM cells.
  `VERIFIER_NOT_RUN` retains artifacts but remains a failed runner result.

Accuracy is primary. Reject candidates that lose exact rows, exceed the cap,
fail deterministic reproduction, lack bindings, or lose the frozen comparison.

## Verification ladder

Do not collapse these steps:

```text
visible training consistency
-> artifact.json equivalence=pass
-> byte-identical deterministic rerun
-> official-verification.json status=pass
-> sealed decision when required by the track
```

`artifact.json` records internal Rust equivalence. `official-verification.json`
binds Official Julia verification to the exact inputs, verifier, version, and
digests.

Promotion state machine decisions come from replayable evidence. Mixed
revisions, trees, datasets, hardware, timeouts, identities, or methods fail
closed. Blind promotion requires every rung and the frozen sealed decision.

## Reports and HPC

`reports/data/project.json` is the only hand-edited report source. Run:

```bash
make report
make report-check
make test
```

Do not hand-edit `docs/STATUS.md`, `docs/METHODS.md`,
`docs/EXPERIMENT_INDEX.md`, `research/EVIDENCE_LEDGER.md`, or `reports/site/`.

Use local compute below 10 minutes and 16 GB. Before Slurm, present the exact
revision, clean tree, environment, data boundary, partition, resources, array,
wall time, and output paths. Wait for approval; access is not authorization.
