<!-- GENERATED; DO NOT EDIT. Source: reports/data/project.json SHA-256: 6e71dd99c9ce7a4d228a5c231a3a4f6abf7e9d1fce56eefeea5a0945b062b8f8; report generator SHA-256: 834732d86d134fe0b7934590f6e4d12bbec7f10b883c49feaa2f285c10e101bd -->

# Research trajectory

This index contains executed research rounds only. Failed, timed-out, invalid, equal, and superseded runs remain part of the record.

| Round | Parents | Title | Track | Status | Turning point | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| R01 | root | Disclosed v1 controls | disclosed_control | verified_main | yes | Retain the four arithmetic solutions as disclosed controls and constructive upper bounds only. |
| R02 | R01 | Blind protocol and runner freeze | blind_visible | verified_main | yes | Freeze the public-visible and sealed boundaries before proposing a learner; do not execute absent studies. |
| R03 | R02 | Care-BDD synthetic calibration | synthetic | verified_main | no | Integrate the synthetic-verified Care-BDD method, but defer every public claim until the reviewed archive is supplied. |
| R04 | R02 | Bounded SAT exact resynthesis | synthetic | verified_main | no | Integrate bounded SAT as an exact local tool; keep Timeout and Unknown censored and make no whole-circuit minimality claim. |
| R05 | R03, R04 | Integration and scheduler audit | synthetic | verified_main | yes | Correct the false verifier state and test a fairer order scheduler as the next single-variable hypothesis. |
| R06 | R05 | Fair-order R1 | synthetic | rejected | yes | Reject fair scheduling for promotion and pivot from coverage allocation to label-aware order construction. |
| R07 | R06 | GreedyExactConflict R1 | synthetic | verified_branch_only | yes | Advance only to public-candidate consideration, then pivot toward per-output support selection because exact-row CV stayed zero. |
| R08 | R07 | ProjectedSupportBDD R2 | synthetic | verified_branch_only | yes | Treat the final executable-bound result as the current internal tracked-formula synthetic frontier and advance only to a separate public-candidate integration decision. |
| R09 | R04, R05 | Tensor-network local pilot | synthetic | verified_branch_only | no | Retain the final pinned pair as local pipeline evidence only; do not claim learned completion, GPU readiness, public accuracy, or SOTA. |
| R10 | R03, R04 | Historical official-Julia controls | disclosed_control | verified_branch_only | no | Close the historical external-verifier gap for disclosed controls only and keep current blind verification absent. |
| R11 | R08, R09, R10 | Deliverability and promotion infrastructure | blind_visible | blocked | yes | Publish only the replayed blocked state; route the next work to the public visible gate rather than claiming promotion. |

## R01 — Disclosed v1 controls

- Branch: `main`
- Base revision: `65dc09ee37e79284b98594e5089fcc04048a5f98`
- Result revision: `7bf1873df485a72ef4c57a6bb1ec121fc4738d39`
- Hypothesis: Constructive arithmetic circuits can reproduce every disclosed-v1 truth-table output exactly in the challenge XAG metric.
- Independent variable: Arithmetic construction for each disclosed control.
- Outcome: Four deterministic circuits and committed prediction tables reproduce the disclosed controls at 37, 49, 168, and 127 reachable gates.
- Insight: The controls establish a semantic and serialization baseline, not a blind-learning result or minimality certificate.
- Next pivot: Separate disclosed-control reproduction from the genuinely blind benchmark and freeze the evidence tracks.

### Runs

| Run | Status | Classification | Outcome | Evidence |
| --- | --- | --- | --- | --- |
| control-a | successful | disclosed_control_exact | mystery-A implements x+y at 37 reachable gates. | [mystery-A circuit](../mystery-A.txt) |
| control-b | successful | disclosed_control_exact | mystery-B implements abs\(x-y\) at 49 reachable gates. | [mystery-B circuit](../mystery-B.txt) |
| control-c | successful | disclosed_control_exact | mystery-C implements x*y at 168 reachable gates. | [mystery-C circuit](../mystery-C.txt) |
| control-d | successful | disclosed_control_exact | mystery-D implements x²+y² at 127 reachable gates. | [mystery-D circuit](../mystery-D.txt) |

### Round evidence

- Disclosed-v1 baseline record at the round result: `7bf1873df485a72ef4c57a6bb1ec121fc4738d39` at `docs/LEADERBOARD.md`
- [Current exhaustive disclosed-v1 tests](../tests/official_v1.rs)

## R02 — Blind protocol and runner freeze

- Branch: `main`
- Base revision: `54e1f6858f0562d80eed51998ad689baec69f3e4`
- Result revision: `336f4782a1cab3b7586136405e32aaf3aa6ec2cc`
- Hypothesis: A frozen reblind protocol can prevent disclosed-control leakage and sealed-data feedback while preserving reproducible visible-only selection.
- Independent variable: Evidence and information-access boundary, not an algorithm.
- Outcome: The repository gained a content-addressed visible/sealed protocol, bounded runner contract, and terminal-evidence checks without mounting the public archive.
- Insight: Benchmark identity, folds, baselines, metrics, and timeout must be fixed before algorithm selection.
- Next pivot: Implement synthetic-only candidate and exact-resynthesis methods behind the frozen public gate.

### Runs

| Run | Status | Classification | Outcome | Evidence |
| --- | --- | --- | --- | --- |
| protocol-freeze-check | successful | protocol_gate | The frozen protocol and terminal-evidence schemas passed their tracked checks; no benchmark cell was executed. | [Protocol gate implementation](../research/check_gate.py) |

### Round evidence

- Frozen benchmark protocol at the round result: `336f4782a1cab3b7586136405e32aaf3aa6ec2cc` at `research/BENCHMARK_PROTOCOL.md`
- [Current frozen benchmark protocol](../research/BENCHMARK_PROTOCOL.md)

## R03 — Care-BDD synthetic calibration

- Branch: `codex/task-11-care-bdd`
- Base revision: `8562e0f676780b1e08d83783ae77fbb708536647`
- Result revision: `6946bb43478df6380e62654ff62e8a67b8b972dd`
- Hypothesis: A shared complemented-edge Care-BDD can complete unseen branches deterministically while preserving every observed row.
- Independent variable: Care-set completion policy and bounded variable-order search.
- Outcome: Four timing calibrations passed, including two 32-evaluation repeats at 63.161153 and 65.831928 seconds with exhaustive equality over 2^20 rows; the memory wrapper failed.
- Insight: The method is exact and comfortably within the local time budget, but synthetic timing does not establish public accuracy.
- Next pivot: Integrate with bounded exact resynthesis, then inspect how the 32-evaluation scheduler allocates its search.

### Runs

| Run | Status | Classification | Outcome | Evidence |
| --- | --- | --- | --- | --- |
| care-evals-1 | successful | synthetic_timing | max_order_evals=1 completed in 17.621493 seconds. | Care-BDD calibration log: `6946bb43478df6380e62654ff62e8a67b8b972dd` at `LOG.md` |
| care-evals-2 | successful | synthetic_timing | max_order_evals=2 completed in 19.372526 seconds. | Care-BDD calibration log: `6946bb43478df6380e62654ff62e8a67b8b972dd` at `LOG.md` |
| care-evals-32-r0 | successful | synthetic_exactness | First max_order_evals=32 run completed in 63.161153 seconds and passed exhaustive 2^20-row equality. | Care-BDD calibration log: `6946bb43478df6380e62654ff62e8a67b8b972dd` at `LOG.md` |
| care-evals-32-r1 | successful | synthetic_exactness_repeat | Independent max_order_evals=32 repeat completed in 65.831928 seconds and passed exhaustive equality. | Care-BDD calibration log: `6946bb43478df6380e62654ff62e8a67b8b972dd` at `LOG.md` |
| care-memory-wrapper | failed | invalid_memory_measurement | /usr/bin/time -l exited 1 after a sandbox-denied sysctl and yielded no trustworthy peak-memory value. | Retained memory-wrapper failure: `6946bb43478df6380e62654ff62e8a67b8b972dd` at `LOG.md` |

### Round evidence

- Frozen Care-BDD provenance log: `6946bb43478df6380e62654ff62e8a67b8b972dd` at `LOG.md`
- [Current Care-BDD implementation](../src/care_bdd.rs)

## R04 — Bounded SAT exact resynthesis

- Branch: `codex/task-12-sat-resynthesis`
- Base revision: `8562e0f676780b1e08d83783ae77fbb708536647`
- Result revision: `61312ed6c28333a19b9494321db286c6f6cd08e0`
- Hypothesis: Bounded exact synthesis can replace a local XAG window with a strictly smaller exact window under frozen resource bounds.
- Independent variable: Exact local gate bound in a deterministic SAT encoding.
- Outcome: Exact fixtures recovered zero-, one-, and two-gate solutions and reduced 3-to-1 and 4-to-2 gates; deadline and solver-interruption paths remained censored.
- Insight: Small exact rewrites work, but solver interruption and deadline outcomes must stay distinct from UNSAT.
- Next pivot: Compose the tool only after an eligible exact candidate exists, and stop on censored or non-improving outcomes.

### Runs

| Run | Status | Classification | Outcome | Evidence |
| --- | --- | --- | --- | --- |
| xor-bound-0 | successful | exact_bound_unsat | Two-input XOR was UNSAT at the zero-gate bound. | Bounded SAT fixture log: `61312ed6c28333a19b9494321db286c6f6cd08e0` at `LOG.md` |
| xor-bound-1 | successful | exact_bound_sat | Two-input XOR produced an independently verified one-gate model. | Bounded SAT fixture log: `61312ed6c28333a19b9494321db286c6f6cd08e0` at `LOG.md` |
| rewrite-3-to-1 | successful | exact_rewrite | A synthetic OR/AND/XOR expression was rewritten from three gates to one with byte-identical repeats. | Bounded SAT rewrite log: `61312ed6c28333a19b9494321db286c6f6cd08e0` at `LOG.md` |
| rewrite-4-to-2 | successful | exact_rewrite_reinserted | A seven-input synthetic circuit fell from four to two gates after exact local reinsertion. | Bounded SAT reinsertion log: `61312ed6c28333a19b9494321db286c6f6cd08e0` at `LOG.md` |
| expired-deadline | timed_out | deadline_censored | An already expired deadline returned Timeout before solver work; another expired during cut enumeration with zero solver calls. | Retained timeout behavior: `61312ed6c28333a19b9494321db286c6f6cd08e0` at `LOG.md` |
| solver-interruption | failed | unknown_censored | A solver interruption without the deadline signal was classified Unknown and never converted to UNSAT. | Retained Unknown behavior: `61312ed6c28333a19b9494321db286c6f6cd08e0` at `LOG.md` |

### Round evidence

- Bounded SAT provenance and outcome log: `61312ed6c28333a19b9494321db286c6f6cd08e0` at `LOG.md`
- [Current bounded SAT implementation](../src/sat.rs)

## R05 — Integration and scheduler audit

- Branch: `codex/task-11-12-integration`
- Base revision: `0f62ae2ca29ff861b52ad60d22508ca3a37dd898`
- Result revision: `ca88fafa40680d16805cbf3d7b7a704a3295a03e`
- Hypothesis: Integrating Care-BDD and bounded SAT without changing either contract will expose the next high-value optimization bottleneck.
- Independent variable: Integration and read-only scheduler audit; no third algorithm.
- Outcome: Care-BDD and SAT commands integrated, one false verifier pass was corrected to not_run, and the synthetic scheduling audit completed in 70.273820 seconds.
- Insight: The 32-evaluation search allocated adjacent neighbors 19/5/0/0 across the beam, revealing a coverage artifact.
- Next pivot: Hold all other controls fixed and interleave order candidates fairly across the four beam members.

### Runs

| Run | Status | Classification | Outcome | Evidence |
| --- | --- | --- | --- | --- |
| care-sat-integration | successful | integration_gate | Combined Care-BDD, SAT, and reblind focused tests passed. | Focused integration verification: `ca88fafa40680d16805cbf3d7b7a704a3295a03e` at `LOG.md` |
| internal-verifier-claim-audit | invalid | invalid_verifier_claim | Review found artifact metrics reporting verifier=pass after Rust-only equivalence; the claim was rejected and corrected to verifier=not_run. | Verifier-honesty correction: `ca88fafa40680d16805cbf3d7b7a704a3295a03e` at `LOG.md` |
| legacy-scheduler-audit | successful | scheduler_audit | The 104857-row cell passed in 70.273820 seconds and showed a 19/5/0/0 post-seed evaluation allocation. | Decision-diagram scheduling audit: `ca88fafa40680d16805cbf3d7b7a704a3295a03e` at `LOG.md` |

### Round evidence

- Integration and scheduling-audit log: `ca88fafa40680d16805cbf3d7b7a704a3295a03e` at `LOG.md`
- [Current integration log](../LOG.md)

## R06 — Fair-order R1

- Branch: `codex/task-11-fair-order-r1`
- Base revision: `ca88fafa40680d16805cbf3d7b7a704a3295a03e`
- Result revision: `d019a3dc3d5afe1aef76a25f266afe27f9d66c6e`
- Hypothesis: Interleaving adjacent order candidates 6/6/6/6 across the four retained beam members will improve the frozen synthetic BlindScore.
- Independent variable: Candidate scheduling allocation only.
- Outcome: Legacy and fair rank-zero results both scored 0/104857 exact rows and 36084 gates; two fair repeats were deterministic and two bounded diagnostics were retained as invalid.
- Insight: Fair allocation fixed the coverage defect but rank-zero quality remained byte-identical, so the next method must change the order signal.
- Next pivot: Derive a fold-local order from exact label conflicts while keeping all completion and scoring controls fixed.

### Runs

| Run | Status | Classification | Outcome | Evidence |
| --- | --- | --- | --- | --- |
| legacy-control | equal | legacy_control_equal | Legacy rank zero scored 0/104857 exact rows and 36084 gates. | Legacy scheduler control: `d019a3dc3d5afe1aef76a25f266afe27f9d66c6e` at `LOG.md` |
| fair-manual-r0 | equal | fair_manual_equal | Fair manual run 0 passed at 0/104857 and 36084 gates. | Fair manual diagnostic r0: `d019a3dc3d5afe1aef76a25f266afe27f9d66c6e` at `LOG.md` |
| fair-manual-r1 | equal | fair_manual_equal_repeat | Fair manual run 1 reproduced the same completed table, circuit, metrics, and 36084 gates. | Fair manual diagnostic r1: `d019a3dc3d5afe1aef76a25f266afe27f9d66c6e` at `LOG.md` |
| fair-hardcap-r0 | invalid | invalid_metrics | fair-hardcap-r0 retained the internal exact diagnostic but terminated INVALID_METRICS with verifier not_run. | Fair bounded diagnostic r0: `d019a3dc3d5afe1aef76a25f266afe27f9d66c6e` at `LOG.md` |
| fair-hardcap-r1 | invalid | invalid_metrics | fair-hardcap-r1 retained the internal exact diagnostic but terminated INVALID_METRICS with verifier not_run. | Fair bounded diagnostic r1: `d019a3dc3d5afe1aef76a25f266afe27f9d66c6e` at `LOG.md` |

### Round evidence

- Fair-order R1 completed trace: `d019a3dc3d5afe1aef76a25f266afe27f9d66c6e` at `LOG.md`

## R07 — GreedyExactConflict R1

- Branch: `codex/task-11-greedy-exact-conflict-r1`
- Base revision: `d019a3dc3d5afe1aef76a25f266afe27f9d66c6e`
- Result revision: `7ac3c3ba2430ed787bab5ca215c259e259fa1fb5`
- Hypothesis: A fold-local greedy order minimizing differently labelled prefix conflicts will improve exact-row CV over the fair fixed-order beam.
- Independent variable: Fold-local label-aware global variable order.
- Outcome: The corrected fair control used 36084 gates; two byte-identical greedy repeats used 34917 gates, while all three remained 0/104857 exact rows.
- Insight: The label-aware order reduced gates but not exact-row CV; gate-only gains at zero exact-row generalization are secondary.
- Next pivot: Reduce irrelevant-variable overfitting by selecting a separate conflict-free projected support for each output.

### Runs

| Run | Status | Classification | Outcome | Evidence |
| --- | --- | --- | --- | --- |
| fair-r0-invalid-command | invalid | invalid_command_filter | The first fair-r0 command selected zero tests and terminated INVALID_METRICS; it was never overwritten. | Preserved invalid initial command cell: `7ac3c3ba2430ed787bab5ca215c259e259fa1fb5` at `LOG.md` |
| fair-r0-filter-fix | successful | verifier_not_run_control | fair-r0-filter-fix completed below 300 seconds at 0/104857 exact rows and 36084 gates with verifier not_run. | Corrected fair control: `7ac3c3ba2430ed787bab5ca215c259e259fa1fb5` at `LOG.md` |
| greedy-r0-filter-fix | successful | verifier_not_run_candidate | greedy-r0-filter-fix completed at 0/104857 exact rows and 34917 gates with verifier not_run. | Greedy repeat 0: `7ac3c3ba2430ed787bab5ca215c259e259fa1fb5` at `LOG.md` |
| greedy-r1-filter-fix | successful | verifier_not_run_candidate_repeat | greedy-r1-filter-fix reproduced the five candidate artifacts byte-for-byte at 0/104857 and 34917 gates. | Greedy repeat 1: `7ac3c3ba2430ed787bab5ca215c259e259fa1fb5` at `LOG.md` |

### Round evidence

- GreedyExactConflict R1 completed trace: `7ac3c3ba2430ed787bab5ca215c259e259fa1fb5` at `LOG.md`

## R08 — ProjectedSupportBDD R2

- Branch: `codex/task-11-projected-support-bdd-r2`
- Base revision: `7ac3c3ba2430ed787bab5ca215c259e259fa1fb5`
- Result revision: `8f6eda40e089a12faa8df3827207024afd719865`
- Hypothesis: Per-output fold-local projected supports will prevent irrelevant-variable overfitting and improve exact-row CV over GreedyExactConflict R1.
- Independent variable: Greedy per-output support selection under the frozen global order.
- Outcome: The claim-grade v3 control scored 0/104857 and 34917 gates; both R2 repeats scored 104857/104857 and 72 gates with byte-identical artifacts.
- Insight: Support selection, not another global-order tweak, produced the first exact synthetic completion on the tracked formula.
- Next pivot: Approve and freeze R2 as the public candidate before obtaining the reviewed public bundle; only then run the frozen two-baseline visible matrix, before any sealed access.

### Runs

| Run | Status | Classification | Outcome | Evidence |
| --- | --- | --- | --- | --- |
| pilot-greedy-control-r0 | superseded | superseded_unbound_control | Pilot GreedyExactConflict control scored 0/104857 and 34917 gates, but its executable/source binding was incomplete. | Unbound pilot control record: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md` |
| pilot-projected-r0 | superseded | superseded_unbound_candidate | Pilot projected-r0 scored 104857/104857 and 72 gates, but could not establish executable/source binding. | Unbound pilot projected record: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md` |
| pilot-projected-r1 | superseded | superseded_unbound_candidate_repeat | Pilot projected-r1 reproduced 104857/104857 and 72 gates but remained non-claim-grade for the same binding defect. | Unbound pilot projected repeat: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md` |
| preflight-v1-seed | invalid | rejected_seed_preflight | The first executable-bound preflight was rejected before cells because its transcribed seed had 62 rather than 64 hexadecimal characters. | Rejected seed preflight record: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md` |
| preflight-v2-tree-digest | invalid | rejected_tree_digest_preflight | The second preflight was rejected before cells because it used a Git tree OID instead of the required SHA-256 tree digest. | Rejected tree-digest preflight record: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md` |
| v3-greedy-control-r0 | successful | claim_grade_control_verifier_not_run | v3 greedy-control-r0 scored 0/104857 and 34917 gates with exact source/executable binding and verifier not_run. | Executable-bound v3 control: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md` |
| v3-projected-r0 | successful | claim_grade_candidate_verifier_not_run | v3 projected-r0 scored 104857/104857 and 72 gates with exhaustive formula and XAG equality. | Executable-bound v3 projected repeat 0: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md` |
| v3-projected-r1 | successful | claim_grade_candidate_repeat_verifier_not_run | v3 projected-r1 reproduced every required R2 artifact byte-for-byte at 104857/104857 and 72 gates. | Executable-bound v3 projected repeat 1: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md` |

### Round evidence

- ProjectedSupportBDD R2 completed trace: `8f6eda40e089a12faa8df3827207024afd719865` at `LOG.md`

## R09 — Tensor-network local pilot

- Branch: `codex/task-14-tn-pilot`
- Base revision: `68098db87de6ce4fd43be0d205cd011dc61a5343`
- Result revision: `96429f981170766575fd167713a528078f297d67`
- Hypothesis: A deterministic tensor-network pipeline can enumerate predictions and pass them through the same Rust XAG backend with byte-repeatable artifacts.
- Independent variable: Tensor-network prediction pipeline and executable/runtime binding.
- Outcome: Two final cells each produced exact visible metrics 1.0, two reachable gates, and byte-identical artifacts in 3.862811792 and 3.538340916 seconds; four earlier runs remain superseded.
- Insight: The Rust-bound pipeline can be repeatable, but a fully observed parity fixture says nothing about partial-table generalization.
- Next pivot: Only after the public gate, test a permitted partial-table candidate and enumerate its full prediction table through the Rust backend.

### Runs

| Run | Status | Classification | Outcome | Evidence |
| --- | --- | --- | --- | --- |
| tn-pre-review-r0 | superseded | superseded_pre_review | Pre-review repeat r0 is preserved as superseded; the final tracked log does not ratify its metrics for this report. | Retained pre-review pair record: `96429f981170766575fd167713a528078f297d67` at `LOG.md` |
| tn-pre-review-r1 | superseded | superseded_pre_review_repeat | Pre-review repeat r1 is preserved as superseded; the final tracked log does not ratify its metrics for this report. | Retained pre-review pair record: `96429f981170766575fd167713a528078f297d67` at `LOG.md` |
| tn-pre-pin-r0 | superseded | superseded_pre_pin | Pre-pin repeat r0 is preserved as superseded after the executable-path race; no superseded metric is restated. | Retained pre-pin pair record: `96429f981170766575fd167713a528078f297d67` at `LOG.md` |
| tn-pre-pin-r1 | superseded | superseded_pre_pin_repeat | Pre-pin repeat r1 is preserved as superseded after the executable-path race; no superseded metric is restated. | Retained pre-pin pair record: `96429f981170766575fd167713a528078f297d67` at `LOG.md` |
| tn-synthetic-r0 | successful | rust_internal_equivalence | tn-synthetic-r0 completed in 3.862811792 seconds at visible exact 1.0 and two gates; pass means Rust internal equivalence only. | Pinned final TN repeat 0: `96429f981170766575fd167713a528078f297d67` at `LOG.md` |
| tn-synthetic-r1 | successful | rust_internal_equivalence_repeat | tn-synthetic-r1 completed in 3.538340916 seconds and reproduced all four scientific artifacts byte-for-byte at visible exact 1.0 and two gates. | Pinned final TN repeat 1: `96429f981170766575fd167713a528078f297d67` at `LOG.md` |

### Round evidence

- Pinned TN pilot completed trace: `96429f981170766575fd167713a528078f297d67` at `LOG.md`

## R10 — Historical official-Julia controls

- Branch: `codex/task-15-julia-wrapper`
- Base revision: `0f62ae2ca29ff861b52ad60d22508ca3a37dd898`
- Result revision: `41518ce876b9c2a5939a525e538473165765203c`
- Hypothesis: The fail-closed wrapper can invoke the unmodified official Julia verifier and record exact passes for the disclosed-v1 control artifacts.
- Independent variable: External Julia verification layer, not a learning algorithm.
- Outcome: The official verifier passed train and commitment-matching test tables for mystery-A through mystery-D with exact and bit accuracy 1.0.
- Insight: All eight control checks passed, proving the wrapper boundary historically while leaving the blind evidence gap unchanged.
- Next pivot: Use immutable official-verification.json records for future visible candidates inside the custodian boundary.

### Runs

| Run | Status | Classification | Outcome | Evidence |
| --- | --- | --- | --- | --- |
| julia-a-train | successful | historical_official_julia_pass | mystery-A train: 2000 samples, 37 gates, exact 1.0, bit 1.0, pass. | mystery-A train Julia record: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md` |
| julia-a-test | successful | historical_official_julia_pass | mystery-A test commitment: 2000 samples, 37 gates, exact 1.0, bit 1.0, pass. | mystery-A test Julia record: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md` |
| julia-b-train | successful | historical_official_julia_pass | mystery-B train: 1500 samples, 49 gates, exact 1.0, bit 1.0, pass. | mystery-B train Julia record: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md` |
| julia-b-test | successful | historical_official_julia_pass | mystery-B test commitment: 2000 samples, 49 gates, exact 1.0, bit 1.0, pass. | mystery-B test Julia record: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md` |
| julia-c-train | successful | historical_official_julia_pass | mystery-C train: 1200 samples, 168 gates, exact 1.0, bit 1.0, pass. | mystery-C train Julia record: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md` |
| julia-c-test | successful | historical_official_julia_pass | mystery-C test commitment: 1500 samples, 168 gates, exact 1.0, bit 1.0, pass. | mystery-C test Julia record: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md` |
| julia-d-train | successful | historical_official_julia_pass | mystery-D train: 400 samples, 127 gates, exact 1.0, bit 1.0, pass. | mystery-D train Julia record: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md` |
| julia-d-test | successful | historical_official_julia_pass | mystery-D test commitment: 624 samples, 127 gates, exact 1.0, bit 1.0, pass. | mystery-D test Julia record: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md` |

### Round evidence

- Historical real-Julia completed trace: `41518ce876b9c2a5939a525e538473165765203c` at `LOG.md`

## R11 — Deliverability and promotion infrastructure

- Branch: `codex/deliverability-verifier-v2`
- Base revision: `37b30ed218d2651d5f3cccc2a3263148ce808d1c`
- Result revision: `cb813e46b77bcc198bc6ebdacf05d38865f9b42e`
- Hypothesis: Evidence-bound verifier, promotion, skills, and report infrastructure can turn branch research into a navigable deliverable without overstating scientific status.
- Independent variable: Proof and navigation infrastructure, not an optimization algorithm.
- Outcome: The current all-none blind-visible request replays to blocked for four missing evidence classes; the highest legal next step remains freeze_candidate.
- Insight: A human-readable report is useful only when its conclusion is derived from structural proof state and preserves failed, invalid, equal, superseded, and blocked records.
- Next pivot: Approve and freeze the R2 public-candidate integration decision before obtaining the reviewed public bundle; only then run the baseline plus visible-only matrix, before any sealed access.

### Runs

| Run | Status | Classification | Outcome | Evidence |
| --- | --- | --- | --- | --- |
| truthful-verifier-regressions | successful | truthful_verifier_state | Candidate-bearing VERIFIER_NOT_RUN and VERIFIER_FAILED states remain distinct from runner SUCCESS and official proof. | [Candidate-evidence verifier state tests](../scripts/tests/test_check_promotion.py) |
| julia-wrapper-regressions | successful | fail_closed_wrapper | The fail-closed wrapper test suite covers malformed output, mismatches, unsafe paths, and Julia failures. | [Julia wrapper adversarial tests](../scripts/tests/test_verify_julia.py) |
| verification-record-regressions | successful | immutable_record | Verification-record tests bind manifests, circuits, datasets, verifier bytes, Julia identity, and replacement-race checks. | [Immutable official-record tests](../scripts/tests/test_record_verification.py) |
| promotion-regressions | successful | promotion_state_machine | Track ceilings and complete evidence bindings are implemented and regression-tested. | [Promotion state machine](../scripts/check-promotion.py) |
| current-promotion-replay | blocked | blocked_missing_evidence | Replay is blocked because candidate evidence, deterministic pairs, frozen comparison, and official verifications are absent. | [Replayed blocked decision](../research/CURRENT_PROMOTION_DECISION.json); [All-none request](../research/CURRENT_PROMOTION_REQUEST.json) |

### Round evidence

- Clean integrated deliverability infrastructure snapshot: `cb813e46b77bcc198bc6ebdacf05d38865f9b42e` at `scripts/check-promotion.py`
- [Current promotion checker](../scripts/check-promotion.py)
- [Current blocked decision](../research/CURRENT_PROMOTION_DECISION.json)

# Study registry

| Experiment | Track | Status | Location | Decision |
| --- | --- | --- | --- | --- |
| Disclosed v1 constructive controls | disclosed_control | verified_main | mystery-A.txt through mystery-D.txt and committed predictions | Retain as reproduced disclosed-control evidence and never relabel it as blind learning. |
| Historical v1 Julia differential | disclosed_control | verified_branch_only | 41518ce876b9c2a5939a525e538473165765203c:LOG.md | Keep as historical branch-bound disclosed-control evidence only. |
| Fair order scheduling R1 | synthetic | rejected | d019a3dc3d5afe1aef76a25f266afe27f9d66c6e:LOG.md | Reject under the precommitted strict-improvement rule. |
| GreedyExactConflict R1 | synthetic | verified_branch_only | 7ac3c3ba2430ed787bab5ca215c259e259fa1fb5:LOG.md | Advance only to a separate public-candidate integration decision. |
| ProjectedSupportBDD R2 | synthetic | verified_branch_only | 8f6eda40e089a12faa8df3827207024afd719865:LOG.md | Advance to public-candidate integration consideration while retaining every superseded and rejected preflight record. |
| Tensor-network local synthetic pilot | synthetic | verified_branch_only | 96429f981170766575fd167713a528078f297d67:LOG.md | Retain as deterministic local pipeline evidence; do not infer completion generalization or SOTA. |
| Frozen public baselines | blind_visible | blocked | research/BASELINES.csv | Obtain the reviewed public bundle, then execute both frozen baselines before interpreting any candidate. |
| Visible-only blind study | blind_visible | blocked | research/CURRENT_PROMOTION_REQUEST.json | Run only after the public baseline matrix and candidate integration decision are frozen. |
| Sealed confirmation | sealed_confirmation | absent | External reviewed custodian boundary | Keep sealed confirmation outside the proposer workspace until a visible-only candidate is frozen. |
