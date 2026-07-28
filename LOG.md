# Experiment task-12-sat-resynthesis

## Hypothesis

Deterministic bounded exact synthesis in the challenge-native XOR/AND basis
with complemented literals can replace small local windows by a circuit with
at least one fewer reachable gate. RustSAT 0.7.5 with CaDiCaL 0.7.5 will be
used only on complete cut truth tables with at most six inputs. A solver
`UNSAT` result establishes only that the frozen encoding has no circuit within
the stated local bound; it is not a whole-circuit minimality claim or a checked
proof certificate.

The frozen local search contract is:

- enumerate candidate cuts and ties deterministically;
- at most six cut inputs;
- at most 128 candidate cuts and 64 solver calls per command;
- ask only for `original_cut_gates - 1` or fewer gates;
- share one absolute 285-second deadline across enumeration, all SAT calls,
  reinsertion, serialization, and final whole-circuit verification;
- map an interrupt to `Timeout` only when that deadline fired, otherwise to
  `Unknown(reason)`;
- accept a rewrite only when the replacement is smaller in the challenge's
  reachable XOR-plus-AND metric, the cut is exhaustively equivalent, the
  reinserted whole circuit is exhaustively equivalent, and a deterministic
  rerun emits identical bytes.

## Parent commit and diff digest

Parent commit:
`8562e0f676780b1e08d83783ae77fbb708536647`.

Branch: `codex/task-12-sat-resynthesis`.

This hypothesis log is committed before production code. The synthetic-only
implementation commit and clean tree digest will be recorded after review.

## Permitted data

Until the synthetic-only implementation commit is frozen:

- tracked contracts, survey, schemas, and nonidentifying manifest metadata;
- generated complete Boolean tables and generated circuits;
- disclosed-v1 arithmetic functions only as explicitly labelled controls;
- no public reblind `train.csv`, public baseline outcome, sealed row, hidden
  label, family/source identifier, evaluator feedback, custodian state, or
  private digest.

Standalone resynthesis is tool-only. It cannot become benchmark evidence
unless it is later composed inside a `PublicSuite`-backed learner that emits
the exact Task 10 table, circuit, artifact index, and metrics.

## Command, seed, and environment

Focused development uses:

```text
cargo test --locked --features sat --release --test sat -- --nocapture
```

The planned runner-compatible command is:

```text
occam-circuit-hmyuuu resynthesize INPUT_CIRCUIT OUTPUT_DIR \
  --max-cut-inputs 6 --deadline-seconds 285 \
  --metrics-json OUTPUT_DIR/metrics.json
```

No stochastic seed is used. Candidate order, source order, gate order, and
tie-breaking are numeric and deterministic. SAT diagnostics belong in
`sat-report.json` or hash-bound logs, never as extra keys in Task 10
`metrics.json`.

## Hardware and five-minute cap

Development and promoted CPU resynthesis cells run locally. The outer
experiment runner enforces 300 seconds including startup and cleanup; the
command uses a 285-second internal absolute deadline. `hpccube` is not
authorized or appropriate for this CPU-only hypothesis.

## Result: accuracy, gates, runtime, memory, verifier

Synthetic-only implementation evidence:

- The exact small-function test proves that two-input XOR is `UNSAT` at bound
  zero and independently exhaustively verifies a one-gate SAT model at bound
  one. A constant-zero output is recovered at zero reachable gates by the
  at-most interface.
- The multi-output fixture is `UNSAT` through one gate and SAT at exactly two
  reachable gates. The verified model shares the first gate between the two
  outputs.
- The synthetic standalone rewrite reduces a three-gate OR/AND/XOR expression
  for XOR to one reachable challenge gate. Two fresh command outputs are
  byte-identical and exhaustively equivalent.
- The wider synthetic fixture finds the same three-to-one local replacement
  inside a seven-primary-input circuit. After reinsertion the whole circuit is
  exhaustively equivalent and falls from four to two reachable challenge
  gates.
- An already-expired synthesis deadline returns `Timeout` before solver work;
  an expired rewrite deadline returns `Timeout` during cut enumeration with
  zero solver calls. A solver interruption without the deadline signal is
  classified as `Unknown`, never `UNSAT`.
- The pinned `rustsat-cadical` 0.7.5 binding bundles CaDiCaL 2.2.1 and exposes
  DRAT tracing. The command preserves the final frozen DIMACS and any final
  UNSAT trace as hash-bound artifacts. No independent DRAT checker is pinned,
  so `proof_checked` is false and no certificate claim is made.
- CLI tests reject every resource override except the literal six-input and
  285-second values. Reports retain the fixed 128-cut and 64-solver-call
  budgets.

Focused RED evidence was retained during development:

- `cargo test --locked --features sat --test sat` first failed with unresolved
  import `occam_circuit_hmyuuu::sat`.
- The initial command tests failed on the usage boundary before the
  `resynthesize` command existed.
- The wider local-window test failed because the initial whole-circuit-only
  implementation rejected seven primary inputs.
- The trace tests failed before `sat-proof.drat` and `sat-instance.cnf` were
  preserved.
- The rewrite-deadline test initially returned an error instead of `Timeout`,
  and the interruption-classification unit test initially failed to compile
  before the classifier existed.

Fresh precommit verification:

- `cargo test --locked --features sat --release --manifest-path Cargo.toml
  --test sat -- --nocapture`: 9 passed, 0 failed in 0.50 seconds.
- `make test`: 29 protocol tests plus 29 subtests passed; 181 runner/cluster
  tests plus 56 subtests passed; 101 Rust tests passed; formatting passed; and
  `research/check_gate.py --phase protocol` passed.

No public or sealed rows, public baseline outcomes, private digests, or HPC
resources were used. Peak memory was not measured by these development test
commands and no claim is made for it.

Clean-worktree baseline:

- `make setup`: passed after allowing access to the existing shared uv cache;
- `make skills`: zero errors, warnings only;
- `make test`: 29 protocol tests plus 29 subtests, 181 runner/cluster tests
  plus 56 subtests, every Rust test, and the protocol gate passed.

The preflight's earlier nonreproducing `AlreadyExists` failure remains retained
as flaky test-isolation evidence. It did not reproduce in this worktree and
the unrelated helper was not modified.

## Failure signal and interpretation

Reject or stop increasing a local bound after two successive
`Timeout`/`Unknown` outcomes, any invalid SAT model, cut or whole-circuit
inequivalence, non-improving reachable gate count, nondeterministic bytes,
missing verifier evidence, or violation of the 300-second cell cap.

`Timeout` and `Unknown` are censored outcomes, never `UNSAT`. A CaDiCaL
`UNSAT` result is scoped to the exact frozen local encoding and bound.

## Next pivot

Review the synthetic-only commit before mounting any public data. Standalone
results remain tool evidence only. Any later benchmark cell must compose this
rewriter inside a `PublicSuite`-backed learner and satisfy the Task 10 artifact,
training-consistency, visible-CV, and verifier contract without changing these
budgets.

## Task 12 review-fix pass

The five Important findings in `.superpowers/sdd/task-12-review.md` were
addressed without changing the benchmark, evaluator, or evidence boundary:

- The SAT module now exposes only `SatResult`, `synthesize_xag_at_most`, and
  the narrow documented library-to-binary command bridge. Diagnostics and cut
  machinery are private. The production bridge fixes the 128-cut and
  64-solver-call limits internally; its callers cannot select them.
- The single 285-second operation deadline is threaded through CNF and DIMACS
  construction, model decoding, exhaustive checks, proof retrieval, cut
  construction, whole-table evaluation, canonicalization, reinsertion,
  deterministic serialization, hashing, completed-table serialization, and
  rollback-aware artifact publication. Deadline-phase errors are converted to
  a censored timeout outcome, never a successful artifact set.
- Timeout and unknown outcomes write only `sat-report.json` within the
  15-second cleanup reserve, omit success metrics/artifact claims, and return a
  failing command status. Unknown reports bind the reason by digest.
- Input and selected circuits are replayed through the production XAG and
  serialized canonically before gate metrics and output. Dead definitions are
  therefore absent from both sides of `whole_circuit_gate_delta`.
- Selector model-read errors are propagated into the existing invalid-model
  `Unknown` path instead of being treated as false selector values.

Strict review-fix RED evidence:

- The injected selector-read test initially failed because
  `selected_source_from_results` did not exist.
- The internal budget test initially showed that 129 cuts were accepted.
- The expired-phase test initially failed because deadline-aware
  canonicalization and serialization helpers did not exist.
- The timeout evidence test initially failed because no command-at-deadline
  bridge wrote a censored report.
- The dead-definition command test initially emitted and scored two gates
  instead of one.

Fresh review-fix verification:

- Focused debug SAT integration: 9 passed, 0 failed.
- Focused SAT unit regressions: 6 passed, 0 failed.
- Focused release SAT integration: 9 passed, 0 failed.
- `make test`: 29 protocol tests plus 29 subtests passed; 181 runner/cluster
  tests plus 56 subtests passed; 20 library tests and every Rust integration
  test passed; formatting and the protocol gate passed.
- `git diff --check`: passed.

The first `make test` attempt could not open the existing shared uv cache under
the workspace sandbox. The identical command was rerun with access to that
cache and passed. No dependency installation, private data, public benchmark
rows, sealed data, remote compute, or HPC was used.

## Task 12 second review-fix pass

The four residual Important findings in
`.superpowers/sdd/task-12-rereview.md` were resolved:

- `Encoding::exactly_one` now receives the absolute deadline and checks it
  before allocation and inside both the outer and inner pairwise-clause loops.
  An injected-expiry regression distinguishes those two loop checkpoints.
- Censored timeout and unknown reports are built from the actual
  `NetlistResynthesis`, preserving cuts considered, solver calls,
  requested/encoded bounds, and cleanup-deadline-bound DIMACS/proof hashes.
  Nonempty diagnostic bytes are published as `sat-instance.cnf` and
  `sat-proof.drat`; success metrics, circuit, completed table, and artifact
  index remain absent.
- Solver `Unknown` is frozen before evidence handling. Its reason is hashed
  against the cleanup deadline, and the command classifier cannot reinterpret
  either a successful or failed unknown-report publication as `Timeout` merely
  because the 285-second operation deadline has elapsed.
- The common artifact publisher now stages every file in a create-new
  temporary path, syncs it, installs with a create-new hard link, and removes
  the staging names. Deadline expiry, injected write/sync failure, or a
  final-name collision rolls back every staged path and every final path
  installed by that transaction without overwriting runner-owned files.

Second-pass strict RED evidence:

- The exactly-one regression failed to compile before the injected-expiry
  helper existed.
- The precise censored-evidence regression failed to compile before the
  `NetlistResynthesis` publisher existed.
- The frozen-unknown regression failed to compile before the command-failure
  classifier existed.
- Atomic rollback regressions failed to compile before the staged publisher
  and injected write/sync control existed.

Fresh second-pass verification:

- Release SAT integration: 9 passed, 0 failed.
- Release SAT review unit regressions: 11 passed, 0 failed.
- `make test`: 29 protocol tests plus 29 subtests passed; 181 runner/cluster
  tests plus 56 subtests passed; 25 library tests and all Rust integrations
  passed; formatting and the protocol gate passed.
- `git diff --check`: passed.

No dependency installation, public or sealed rows, public baseline outcomes,
private digests, remote compute, or HPC was used.

## Task 12 final narrow review pass

The two residual Important findings in
`.superpowers/sdd/task-12-final-rereview.md` were addressed:

- The actual `NetlistResynthesis` is now owned by one post-solver guard across
  selected-circuit serialization, whole-table verification, hashing, report
  construction, diagnostic copying, and success publication. A shared-deadline
  failure in any of those phases changes only the outcome status to `Timeout`
  and publishes the real cuts considered, solver calls, requested/encoded
  bounds, DIMACS, and proof evidence during the cleanup reserve.
- Artifact publication now creates a sibling staging directory while
  `OUTPUT_DIR` remains absent, writes and syncs the complete evidence set
  there, syncs the staging directory, and exposes the whole set with one
  directory rename. Deadline, write/sync, existing-output, staging, and rename
  failures clean up the staging directory and leave no partial final output.
  The report is therefore never visible without the diagnostic files it
  references.

Final-pass strict RED evidence:

- The post-solver timeout test failed to compile before the outcome-owning
  guard existed.
- The evidence-set rollback test failed because the previous per-file
  publisher left `OUTPUT_DIR` visible after an injected pre-commit deadline.

Fresh final-pass verification:

- Release SAT integration: 9 passed, 0 failed.
- Release SAT review unit regressions: 12 passed, 0 failed.
- `cargo test --locked --all-features --release`: 26 library tests and all
  Rust integrations passed.
- `research/check_gate.py --phase protocol`: passed.
- `git diff --check`: passed.

The full `make test` command was attempted twice after the final code. Its
protocol suite passed 29 tests plus 29 subtests each time, and 180 of 181
runner/cluster tests plus all 56 subtests passed. The same unrelated existing
test,
`test_sigterm_ignoring_process_tree_is_absent_after_deadline`, failed on both
full runs and a focused rerun because macOS denied the runner's
`os.killpg(..., SIGKILL)` with `PermissionError: [Errno 1] Operation not
permitted`. The Rust and protocol portions were then run independently and
passed. No runner code was changed; full-suite green proof is therefore
missing and no contrary claim is made.

The three exact reproductions were:

1. `make test` — failed at that single runner test with the `os.killpg`
   `PermissionError`.
2. `uv run --default-index https://pypi.org/simple pytest -q
   autoresearch/test_run_experiment.py::RunExperimentTests::test_sigterm_ignoring_process_tree_is_absent_after_deadline`
   — failed identically.
3. `make test` after the spawned ten-second process had time to exit — failed
   identically at the same single runner test.

No dependency installation, public or sealed rows, public baseline outcomes,
private digests, remote compute, or HPC was used.
