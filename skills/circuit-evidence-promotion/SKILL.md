---
name: circuit-evidence-promotion
description: Use when moving a BooleanRazor result through runner validation, official Julia verification, freeze, promotion, and report updates without exceeding its evidence track.
---

# Circuit Evidence Promotion

## Prepare

Consult [the promotion workflow](references/promotion-workflow.md) before
touching evidence. Consult [the claim language](references/claim-language.md)
before updating a report, handoff, or leaderboard.

Establish the active role first. A proposer may validate and hand off public
candidate artifacts, but only an authorized custodian may inspect official or
sealed inputs, execute their commands, or handle their paths and digests. If
the custodian boundary is unavailable, stop at `blocked`; do not request the
private values.

## Workflow

1. Choose `disclosed_control`, `synthetic`, `blind_visible`, or
   `sealed_confirmation`; state its maximum positive decision.
2. Run `research/check_gate.py` against the frozen expected design and the
   complete native run.
3. Require a candidate-bearing runner state and validate every transitive
   run-spec, manifest, artifact, completed-table, circuit, log, and provenance
   binding.
4. Pair fresh deterministic manifests and compare byte-identical completed
   tables, circuits, and artifact indexes. Keep all terminal failures visible.
5. In the custodian environment only, run `record-verification.py` with
   absolute, normalized, non-symlink paths. A failure creates no pass record.
6. In that same evidence boundary, create one canonical promotion request
   rooted beside its evidence. Use literal `none` for unavailable inputs.
7. Run `check-promotion.py` once and preserve the immutable decision and its
   exact input bindings. For sealed confirmation, require one uniform outcome
   against both baseline methods: `100x` against both or scaling advantage
   against both, never a hybrid split. Bind those baseline names to the
   methods in the actual frozen baseline manifests. Treat external
   trust-policy authority as a separate custodian responsibility.
8. Interpret `blocked` as missing proof, `reject` as violated eligibility,
   `no_change` as valid but not strictly better, and a positive decision only
   at the selected track's ceiling.
9. Regenerate the report and run its freshness checker. Publish only claim
   language and evidence locators allowed to cross the information boundary.
10. Update a leaderboard only when that leaderboard's own evidence gate
    permits the exact result and track.

## Finish

Report the track, decision, highest legal next step, public reason codes, and
remaining proof. Do not expose custodian paths, official/sealed raw records,
trust policies, private digests, or per-example evaluator output.
