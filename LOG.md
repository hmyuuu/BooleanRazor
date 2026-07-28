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

No algorithm result exists yet.

Clean-worktree baseline:

- `make setup`: passed;
- `make skills`: zero errors, warnings only;
- first `make test`: Python suites passed, then the pre-existing
  `failed_install_rolls_back_every_artifact_and_removes_transaction_dirs`
  test failed at `src/main.rs:920` with `AlreadyExists` while creating its
  PID-plus-clock temporary directory;
- the focused failing test, the full binary tests in serial and parallel, and
  a fresh complete `make test` all passed without source changes.

The nonreproducing baseline failure is retained as flaky test-isolation
evidence and is not silently attributed to Task 12.

## Failure signal and interpretation

Reject or stop increasing a local bound after two successive
`Timeout`/`Unknown` outcomes, any invalid SAT model, cut or whole-circuit
inequivalence, non-improving reachable gate count, nondeterministic bytes,
missing verifier evidence, or violation of the 300-second cell cap.

`Timeout` and `Unknown` are censored outcomes, never `UNSAT`. A CaDiCaL
`UNSAT` result is scoped to the exact frozen local encoding and bound.

## Next pivot

Implement exact small-table synthesis test-first, then add deterministic cut
replacement and the runner-compatible artifact boundary. Review the
synthetic-only commit before mounting any public data. If no verified local
rewrite improves mystery-C from 168 gates, retain the exact control and move
to the blind care-BDD comparison rather than broadening claims or time limits.
