# Disclosed-v1 leaderboard

This page tracks the leakage-disclosed v1 control submission for Occam's
Circuit. It is not evidence that the blind learner recovered the four
arithmetic families.

## Scoring contract

The public challenge ranks each mystery instance by:

1. exact-match accuracy on its hidden test rows;
2. fewer fan-in-two gates after an accuracy tie.

Negated literals are free. BooleanRazor reports reachable XOR-plus-AND gates
after dead-code elimination. The challenge does not publish an A–D aggregation
rule, so the summed gate count below is informational rather than an official
leaderboard score.

Source: [QuantumBFS/quantum.harness issue #71](https://github.com/QuantumBFS/quantum.harness/issues/71).

## Current verified control

| Instance | Disclosed function | Test rows | Exact accuracy | Bit accuracy | Reachable gates |
| --- | --- | ---: | ---: | ---: | ---: |
| mystery-A | `x+y` | 2,000 | 1.0 | 1.0 | 37 |
| mystery-B | `abs(x-y)` | 2,000 | 1.0 | 1.0 | 49 |
| mystery-C | `x*y` | 1,500 | 1.0 | 1.0 | 168 |
| mystery-D | `x²+y²` | 624 | 1.0 | 1.0 | 127 |
| **Informational total** | — | **6,124** | **1.0 micro** | **1.0 micro** | **381** |

Reproduction on 2026-07-27:

- two solver runs produced byte-identical circuits and predictions;
- all 6,124 committed test rows matched the disclosed functions;
- all 87,040 assignments across the four complete domains matched the emitted
  circuits;
- each prediction file SHA-256 matched the commitment anchored in issue #71;
- the focused Rust v1 suite passed 3/3 tests.

The fresh reproduction used the committed prediction inputs and outputs as a
transparent replay fixture because the official release asset could not be
downloaded through the available GitHub routes. Julia was not installed, so
this particular run did not execute the official Julia verifier. These missing
checks are not folded into the success claim.

## Improvement against the original references

The public issue publishes only one concrete reference circuit: mystery-A at
37 gates and 100% exact accuracy. It does not publish reference gate counts for
B, C, or D.

| Instance | Published reference | Current | Verified improvement |
| --- | ---: | ---: | ---: |
| mystery-A | 37 gates at 100% | 37 gates at 100% | 0 gates (0%) |
| mystery-B | not published | 49 gates at 100% | not measurable |
| mystery-C | not published | 168 gates at 100% | not measurable |
| mystery-D | not published | 127 gates at 100% | not measurable |

The first committed BooleanRazor submission, standalone commit `7ca8fb4`, also
used 37, 49, 168, and 127 gates. Relative to that internal baseline, current
accuracy and gate count are unchanged:

- exact accuracy: 100% → 100%;
- informational gate sum: 381 → 381;
- gate reduction: 0 (0%).

The current result is therefore a reproduced and hardened semantic baseline,
not a gate-optimization improvement or a minimality certificate. Future
leaderboard entries must retain exact accuracy and report improvements against
both the published reference where available and the first committed internal
baseline.
