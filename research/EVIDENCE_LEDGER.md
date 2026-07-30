<!-- GENERATED; DO NOT EDIT. Source: reports/data/project.json SHA-256: 6e71dd99c9ce7a4d228a5c231a3a4f6abf7e9d1fce56eefeea5a0945b062b8f8; report generator SHA-256: 834732d86d134fe0b7934590f6e4d12bbec7f10b883c49feaa2f285c10e101bd -->

# Evidence ledger

## control-upper-bounds

The disclosed controls pass current internal exhaustive equivalence.

Evidence:

- [Current exhaustive disclosed-v1 tests](../tests/official_v1.rs)

Limitations:

- The gate counts are constructive upper bounds, not minimality certificates or blind recoveries.

Missing proof:

- None.

## historical-julia-controls-only

The ratified historical disclosed-v1 log records Julia verifier passes for disclosed controls only; this is not a fresh current-HEAD official verification or blind-learning evidence.

Evidence:

- Ratified historical real-Julia control log: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md`

Limitations:

- This historical result covers the leakage-disclosed A-D controls only.
- Internal exhaustive equivalence is not official verification, and this log is not a fresh current-HEAD official record.

Missing proof:

- A current immutable official-verification.json for any future blind candidate.

## synthetic-frontier-not-blind

A synthetic candidate result is recorded only at the cited historical revision.

Evidence:

- ProjectedSupportBDD R2 remediation log: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md`

Limitations:

- The 104857/104857, 72-gate result is a tracked-formula synthetic branch result only.
- No public, blind-visible, sealed, external, or global SOTA conclusion follows.

Missing proof:

- Frozen public baseline and candidate rows.
- Official records and sealed confirmation for a previously frozen candidate.

## public-baselines-and-blind-advantage-absent

Blind-visible and sealed evidence are absent; blind advantage has not been demonstrated.

Evidence:

- [Public baseline ledger with header only](../research/BASELINES.csv)
- [Current all-none promotion request](../research/CURRENT_PROMOTION_REQUEST.json)

Limitations:

- The content-addressed public bundle is not mounted and no visible candidate study has run.

Missing proof:

- Executed frozen public baseline rows.
- Matched visible-only candidate repeats.
- Later sealed confirmation.

## visible-promotion-blocked

The current blind-visible promotion decision is blocked.

Evidence:

- [Current promotion request](../research/CURRENT_PROMOTION_REQUEST.json)
- [Current replayable promotion decision](../research/CURRENT_PROMOTION_DECISION.json)

Limitations:

- The request contains no candidate evidence, deterministic pairs, frozen comparison, or official records.

Missing proof:

- Complete visible-only evidence sufficient to freeze a candidate.

## sealed-confirmation-absent

No sealed-promotion evidence is present.

Evidence:

- [Public and sealed publication boundary](../reblind/README.md)
- [Current request with no sealed result](../research/CURRENT_PROMOTION_REQUEST.json)

Limitations:

- Sealed confirmation may occur only after a visible-only candidate is frozen inside the reviewed custodian boundary.

Missing proof:

- Sanitized authenticated sealed attestation for a previously frozen candidate.


# Research-round provenance

## R01

Result revision: `7bf1873df485a72ef4c57a6bb1ec121fc4738d39`

Round evidence:

- Disclosed-v1 baseline record at the round result: `7bf1873df485a72ef4c57a6bb1ec121fc4738d39` at `docs/LEADERBOARD.md`
- [Current exhaustive disclosed-v1 tests](../tests/official_v1.rs)

Run evidence:

- control-a (successful): [mystery-A circuit](../mystery-A.txt)
- control-b (successful): [mystery-B circuit](../mystery-B.txt)
- control-c (successful): [mystery-C circuit](../mystery-C.txt)
- control-d (successful): [mystery-D circuit](../mystery-D.txt)

## R02

Result revision: `336f4782a1cab3b7586136405e32aaf3aa6ec2cc`

Round evidence:

- Frozen benchmark protocol at the round result: `336f4782a1cab3b7586136405e32aaf3aa6ec2cc` at `research/BENCHMARK_PROTOCOL.md`
- [Current frozen benchmark protocol](../research/BENCHMARK_PROTOCOL.md)

Run evidence:

- protocol-freeze-check (successful): [Protocol gate implementation](../research/check_gate.py)

## R03

Result revision: `6946bb43478df6380e62654ff62e8a67b8b972dd`

Round evidence:

- Frozen Care-BDD provenance log: `6946bb43478df6380e62654ff62e8a67b8b972dd` at `LOG.md`
- [Current Care-BDD implementation](../src/care_bdd.rs)

Run evidence:

- care-evals-1 (successful): Care-BDD calibration log: `6946bb43478df6380e62654ff62e8a67b8b972dd` at `LOG.md`
- care-evals-2 (successful): Care-BDD calibration log: `6946bb43478df6380e62654ff62e8a67b8b972dd` at `LOG.md`
- care-evals-32-r0 (successful): Care-BDD calibration log: `6946bb43478df6380e62654ff62e8a67b8b972dd` at `LOG.md`
- care-evals-32-r1 (successful): Care-BDD calibration log: `6946bb43478df6380e62654ff62e8a67b8b972dd` at `LOG.md`
- care-memory-wrapper (failed): Retained memory-wrapper failure: `6946bb43478df6380e62654ff62e8a67b8b972dd` at `LOG.md`

## R04

Result revision: `61312ed6c28333a19b9494321db286c6f6cd08e0`

Round evidence:

- Bounded SAT provenance and outcome log: `61312ed6c28333a19b9494321db286c6f6cd08e0` at `LOG.md`
- [Current bounded SAT implementation](../src/sat.rs)

Run evidence:

- xor-bound-0 (successful): Bounded SAT fixture log: `61312ed6c28333a19b9494321db286c6f6cd08e0` at `LOG.md`
- xor-bound-1 (successful): Bounded SAT fixture log: `61312ed6c28333a19b9494321db286c6f6cd08e0` at `LOG.md`
- rewrite-3-to-1 (successful): Bounded SAT rewrite log: `61312ed6c28333a19b9494321db286c6f6cd08e0` at `LOG.md`
- rewrite-4-to-2 (successful): Bounded SAT reinsertion log: `61312ed6c28333a19b9494321db286c6f6cd08e0` at `LOG.md`
- expired-deadline (timed_out): Retained timeout behavior: `61312ed6c28333a19b9494321db286c6f6cd08e0` at `LOG.md`
- solver-interruption (failed): Retained Unknown behavior: `61312ed6c28333a19b9494321db286c6f6cd08e0` at `LOG.md`

## R05

Result revision: `ca88fafa40680d16805cbf3d7b7a704a3295a03e`

Round evidence:

- Integration and scheduling-audit log: `ca88fafa40680d16805cbf3d7b7a704a3295a03e` at `LOG.md`
- [Current integration log](../LOG.md)

Run evidence:

- care-sat-integration (successful): Focused integration verification: `ca88fafa40680d16805cbf3d7b7a704a3295a03e` at `LOG.md`
- internal-verifier-claim-audit (invalid): Verifier-honesty correction: `ca88fafa40680d16805cbf3d7b7a704a3295a03e` at `LOG.md`
- legacy-scheduler-audit (successful): Decision-diagram scheduling audit: `ca88fafa40680d16805cbf3d7b7a704a3295a03e` at `LOG.md`

## R06

Result revision: `d019a3dc3d5afe1aef76a25f266afe27f9d66c6e`

Round evidence:

- Fair-order R1 completed trace: `d019a3dc3d5afe1aef76a25f266afe27f9d66c6e` at `LOG.md`

Run evidence:

- legacy-control (equal): Legacy scheduler control: `d019a3dc3d5afe1aef76a25f266afe27f9d66c6e` at `LOG.md`
- fair-manual-r0 (equal): Fair manual diagnostic r0: `d019a3dc3d5afe1aef76a25f266afe27f9d66c6e` at `LOG.md`
- fair-manual-r1 (equal): Fair manual diagnostic r1: `d019a3dc3d5afe1aef76a25f266afe27f9d66c6e` at `LOG.md`
- fair-hardcap-r0 (invalid): Fair bounded diagnostic r0: `d019a3dc3d5afe1aef76a25f266afe27f9d66c6e` at `LOG.md`
- fair-hardcap-r1 (invalid): Fair bounded diagnostic r1: `d019a3dc3d5afe1aef76a25f266afe27f9d66c6e` at `LOG.md`

## R07

Result revision: `7ac3c3ba2430ed787bab5ca215c259e259fa1fb5`

Round evidence:

- GreedyExactConflict R1 completed trace: `7ac3c3ba2430ed787bab5ca215c259e259fa1fb5` at `LOG.md`

Run evidence:

- fair-r0-invalid-command (invalid): Preserved invalid initial command cell: `7ac3c3ba2430ed787bab5ca215c259e259fa1fb5` at `LOG.md`
- fair-r0-filter-fix (successful): Corrected fair control: `7ac3c3ba2430ed787bab5ca215c259e259fa1fb5` at `LOG.md`
- greedy-r0-filter-fix (successful): Greedy repeat 0: `7ac3c3ba2430ed787bab5ca215c259e259fa1fb5` at `LOG.md`
- greedy-r1-filter-fix (successful): Greedy repeat 1: `7ac3c3ba2430ed787bab5ca215c259e259fa1fb5` at `LOG.md`

## R08

Result revision: `8f6eda40e089a12faa8df3827207024afd719865`

Round evidence:

- ProjectedSupportBDD R2 completed trace: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md`

Run evidence:

- pilot-greedy-control-r0 (superseded): Unbound pilot control record: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md`
- pilot-projected-r0 (superseded): Unbound pilot projected record: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md`
- pilot-projected-r1 (superseded): Unbound pilot projected repeat: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md`
- preflight-v1-seed (invalid): Rejected seed preflight record: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md`
- preflight-v2-tree-digest (invalid): Rejected tree-digest preflight record: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md`
- v3-greedy-control-r0 (successful): Executable-bound v3 control: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md`
- v3-projected-r0 (successful): Executable-bound v3 projected repeat 0: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md`
- v3-projected-r1 (successful): Executable-bound v3 projected repeat 1: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md`

## R09

Result revision: `96429f981170766575fd167713a528078f297d67`

Round evidence:

- Pinned TN pilot completed trace: `96429f981170766575fd167713a528078f297d67` at `LOG.md`

Run evidence:

- tn-pre-review-r0 (superseded): Retained pre-review pair record: `96429f981170766575fd167713a528078f297d67` at `LOG.md`
- tn-pre-review-r1 (superseded): Retained pre-review pair record: `96429f981170766575fd167713a528078f297d67` at `LOG.md`
- tn-pre-pin-r0 (superseded): Retained pre-pin pair record: `96429f981170766575fd167713a528078f297d67` at `LOG.md`
- tn-pre-pin-r1 (superseded): Retained pre-pin pair record: `96429f981170766575fd167713a528078f297d67` at `LOG.md`
- tn-synthetic-r0 (successful): Pinned final TN repeat 0: `96429f981170766575fd167713a528078f297d67` at `LOG.md`
- tn-synthetic-r1 (successful): Pinned final TN repeat 1: `96429f981170766575fd167713a528078f297d67` at `LOG.md`

## R10

Result revision: `41518ce876b9c2a5939a525e538473165765203c`

Round evidence:

- Historical real-Julia completed trace: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md`

Run evidence:

- julia-a-train (successful): mystery-A train Julia record: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md`
- julia-a-test (successful): mystery-A test Julia record: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md`
- julia-b-train (successful): mystery-B train Julia record: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md`
- julia-b-test (successful): mystery-B test Julia record: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md`
- julia-c-train (successful): mystery-C train Julia record: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md`
- julia-c-test (successful): mystery-C test Julia record: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md`
- julia-d-train (successful): mystery-D train Julia record: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md`
- julia-d-test (successful): mystery-D test Julia record: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md`

## R11

Result revision: `cb813e46b77bcc198bc6ebdacf05d38865f9b42e`

Round evidence:

- Clean integrated deliverability infrastructure snapshot: `cb813e46b77bcc198bc6ebdacf05d38865f9b42e` at `scripts/check-promotion.py`
- [Current promotion checker](../scripts/check-promotion.py)
- [Current blocked decision](../research/CURRENT_PROMOTION_DECISION.json)

Run evidence:

- truthful-verifier-regressions (successful): [Candidate-evidence verifier state tests](../scripts/tests/test_check_promotion.py)
- julia-wrapper-regressions (successful): [Julia wrapper adversarial tests](../scripts/tests/test_verify_julia.py)
- verification-record-regressions (successful): [Immutable official-record tests](../scripts/tests/test_record_verification.py)
- promotion-regressions (successful): [Promotion state machine](../scripts/check-promotion.py)
- current-promotion-replay (blocked): [Replayed blocked decision](../research/CURRENT_PROMOTION_DECISION.json); [All-none request](../research/CURRENT_PROMOTION_REQUEST.json)
