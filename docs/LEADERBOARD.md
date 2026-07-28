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

## Current public field

As of 2026-07-28, the harness has no merged aggregate leaderboard and still
defines ranking per instance. The following comparison covers the public
scored solution artifacts found in open pull requests:

- [Ranger PR #220](https://github.com/QuantumBFS/quantum.harness/pull/220)
  reports 100% hidden-row accuracy and `37, 50, 167, 186` gates.
- [lifeIsShort PR #213](https://github.com/QuantumBFS/quantum.harness/pull/213)
  reports prediction hashes matching the organizer commitments and
  `37, 50, 168, 225` gates.
- The other open issue-71 registrations inspected did not publish complete
  scored circuit artifacts.

| Instance | BooleanRazor | Best competing public artifact | Provisional position |
| --- | ---: | ---: | --- |
| mystery-A | 37 | 37 | tied first |
| mystery-B | 49 | 50 | first by 1 gate |
| mystery-C | 168 | 167 | second by 1 gate |
| mystery-D | 127 | 186 | first by 59 gates |

All compared rows have matching full prediction commitments, so gate count is
the relevant tie-break. BooleanRazor and Ranger are not mutually dominating:
Ranger leads mystery-C, while BooleanRazor leads mystery-B and mystery-D.

For orientation only, BooleanRazor's four-instance gate sum is 381, versus 440
for Ranger and 480 for lifeIsShort. That is 59 gates (13.4%) below the
strongest competing total, but the challenge does not define this sum as an
official score.

These positions are provisional. BooleanRazor is public but has not yet been
submitted to the harness as a challenge pull request, and its fresh
reproduction has not been run through the official Julia verifier. The next
gate-optimization target is therefore mystery-C: 167 gates ties the current
public best and 166 would lead every inspected instance.
