# BooleanRazor

BooleanRazor is an evidence-first workspace for learning and synthesizing exact
Boolean circuits from partial observations. Accuracy comes first; reachable
gate count breaks ties under the challenge's one-gate XOR metric.

## Current result

Blind advantage has not been demonstrated. The public training bundle is
absent, the public baseline and visible-blind comparison have not run, and no
sealed confirmation exists.

ProjectedSupportBDD R2 is the strongest recorded internal synthetic result:
104,857/104,857 exact rows and 72 reachable gates on its recorded fixture. It
is historical branch-only evidence, not a public, blind, sealed, or global
SOTA result.

## Disclosed controls

The public v1 release exposes the mappings, so they serve only as exact
constructive controls.

| Instance | Function | Reachable gates |
| --- | --- | ---: |
| A | `x + y` | 37 |
| B | `abs(x - y)` | 49 |
| C | `x * y` | 168 |
| D | `x² + y²` | 127 |

These counts are upper bounds, not minimality proofs or blind-learning
evidence. Negation is free in the challenge metric.

## Evidence boundaries

| Track | Permitted evidence | Highest decision |
| --- | --- | --- |
| `disclosed_control` | Known v1 mappings and data | `promote_control` |
| `synthetic` | Generated development fixtures | `advance_public_candidate` |
| `blind_visible` | Reviewed public bundle only | `freeze_candidate` |
| `sealed_confirmation` | Frozen custodian evaluation | `promote_blind_result` |

The proposer cannot receive sealed rows, private digests, source identities,
or per-example evaluator feedback.

## Verification

A promoted result needs visible training consistency, Internal exhaustive equivalence,
byte-identical reruns, an input-bound
`official-verification.json`, and any sealed decision required by its track.
Internal Rust equivalence and Official Julia verification are separate claims.

## Start here

- [Current status](docs/STATUS.md)
- [Methods and stop rules](docs/METHODS.md)
- [Experiment index](docs/EXPERIMENT_INDEX.md)
- [Evidence ledger](research/EVIDENCE_LEDGER.md)
- [Offline research report](reports/site/index.html)
- [Agent guide](AGENTS.md)
- [Session handoff](docs/handoff/SESSION_HANDOFF.md)

This repository includes no public archive, sealed data, private custodian
state, or cluster authorization.
