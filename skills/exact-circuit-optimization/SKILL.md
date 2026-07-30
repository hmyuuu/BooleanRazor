---
name: exact-circuit-optimization
description: Use when proposing, implementing, or evaluating a BooleanRazor circuit-optimization hypothesis under the exact accuracy-first XAG evidence contract.
---

# Exact Circuit Optimization

## Prepare

Consult [the evidence contract](references/evidence-contract.md) before
changing a method or launching a cell. Consult
[the method map](references/method-map.md) before selecting an optimization
direction or comparing with earlier work.

If the task is to validate or promote an existing result, stop here and use
`circuit-evidence-promotion`. Do not turn validation into a new hypothesis.

## Workflow

1. Classify the work as `disclosed_control`, `synthetic`, `blind_visible`, or
   `sealed_confirmation`. State the track and its permitted inputs before
   inspecting data.
2. Record the accepted parent revision and its clean status, then create and
   enter one fresh sibling Git worktree from that exact parent. Never reuse a
   hypothesis worktree for another idea.
3. In the fresh worktree, record its branch, full precommit `HEAD`, clean
   baseline, parent revision, hypothesis, sole independent variable, permitted
   data, frozen controls, failure signal, and stop rule in the root `LOG.md`;
   commit that precommit record before implementation.
4. Start with the strict failing test before changing the method. Keep
   evaluator, metric, benchmark, folds, seeds, time cap, and evidence schema
   frozen.
5. Require training consistency and exhaustive XAG equivalence against the
   candidate's completed truth table. This proves artifact agreement, not
   agreement with unavailable hidden outputs.
6. Apply the frozen design comparator: rank exact-row accuracy first, then
   fewer reachable challenge-native XAG gates. Report bit accuracy only as a
   diagnostic. Count XOR as one gate and assign no gate to negation.
7. Treat SAT `Timeout` and `Unknown` as censored outcomes, never as `UNSAT`.
   Attribute `UNSAT` only to the exact frozen encoding and bound that proved it.
8. Keep OxiDD as an independent reduced-check and ordering oracle. Never make
   it the production learner or the challenge cost authority.
9. Build the artifact twice in fresh output roots and require byte-identical
   completed tables, circuits, and artifact indexes.
10. Stop on contract drift, inequivalence, nondeterminism, two successive
    `Timeout`/`Unknown` outcomes at one bound, or no strict accuracy-first gain.
11. Preserve equal, worse, failed, and timed-out cells with their logs,
    manifests, resource measurements, and an honest decision.
12. Hand eligible evidence to `circuit-evidence-promotion`. Do not self-promote
    a method, report claim, or leaderboard row.

## Finish

State the exact comparison, the eligibility result, the stop reason, the
evidence track, and the highest action the evidence could support. Leave
missing official, public, or sealed proof explicit.
