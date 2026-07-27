# BooleanRazor

BooleanRazor is a standalone research workspace for learning and synthesizing
small exact Boolean circuits from partial observations. The work has two
strictly separated tracks:

- **Disclosed v1 controls:** reproduce the known arithmetic mappings exactly,
  then optimize their shared XOR–AND graph (XAG) representation.
- **Blind benchmark:** learn opaque functions without generator labels or
  sealed rows, then synthesize and verify the completed truth tables.

Accuracy is the primary objective. Reachable gate count under the challenge's
one-gate XOR metric is secondary and is compared only after exactness.

## Current control

The disclosed v1 mappings are:

| Instance | Function | Current reachable gates |
| --- | --- | ---: |
| A | `x + y` | 37 |
| B | `abs(x - y)` | 49 |
| C | `x * y` | 168 |
| D | `x² + y²` | 127 |

These are controls, not evidence that a blind learner recovered hidden
semantics. The blind track uses opaque IDs, a frozen public protocol, and a
separate sealed evaluator.

## Start here

```bash
make setup
make skills
make test
```

Then read:

- [`GOAL.md`](GOAL.md) — concise research objective and success bar.
- [`docs/plans/2026-07-23-occam-circuit-rust-bdd-tn.md`](docs/plans/2026-07-23-occam-circuit-rust-bdd-tn.md)
  — ratified implementation and evaluation plan.
- [`docs/handoff/SESSION_HANDOFF.md`](docs/handoff/SESSION_HANDOFF.md) —
  current continuation state.
- [`docs/handoff/MIGRATION_VERIFICATION.md`](docs/handoff/MIGRATION_VERIFICATION.md)
  — history, privacy, toolchain, and passing standalone baseline.
- [`autoresearch/README.md`](autoresearch/README.md) — five-minute experiment
  protocol and proposal/evaluator firewall.

No public training archive, sealed evaluation rows, private custodian state, or
cluster authorization is bundled here. Remote work on `hpccube` is allowed
only after a human ratifies the exact promoted cell and its resource card.
