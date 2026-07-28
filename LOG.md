# Integration task-11-care-bdd + task-12-sat-resynthesis

## Scope

This worktree integrates two independently precommitted, synthetic-only
hypotheses without changing either scientific contract:

- Task 11 care-set ROBDD: branch `codex/task-11-care-bdd`, implementation
  commit `c757952b193a63706b5a1d84d436f7de88fec836`, provenance commit
  `6946bb43478df6380e62654ff62e8a67b8b972dd`.
- Task 12 bounded SAT resynthesis: main parent
  `61312ed6c28333a19b9494321db286c6f6cd08e0`.

Each original root `LOG.md` remains recoverable from its named parent commit.
This file records only the integration boundary; it is not a third algorithm
hypothesis and creates no new benchmark result.

## Permitted data

Only tracked source, contracts, synthetic fixtures, and the disclosed-v1
controls were available. No public reblind training archive, sealed row,
hidden label, source-family identity, baseline outcome, private digest,
evaluator feedback, remote compute, or HPC resource was read or used.

## Baseline

- `make setup`: passed using the existing uv cache and created the ignored
  worktree-local `.venv`.
- `make skills`: passed with zero errors and 46 pre-existing warnings.
- Initial sandboxed `make test`: stopped before tests because the shared uv
  cache was not readable.
- Approved cache-backed `make test`: passed 29 protocol tests plus 29
  subtests, 181 runner/cluster tests plus 56 subtests, all Rust tests,
  formatting, and the protocol gate.

## Merge boundary

The branches conflicted only where both added root hypothesis logs and where
both extended `src/main.rs`. Resolution preserves both production commands:

```text
learn-care
resynthesize
```

The usage text and dispatcher expose both commands. Task 11 retains its frozen
five folds, sibling-reuse policy, 32-order-evaluation cap, design-bound seed,
training-consistency checks, exact completed-table/XAG verification, and
serialized challenge gate metric. Task 12 retains its six-cut-input and
285-second internal limits, bounded solver calls, atomic evidence publication,
and timeout/unknown classification.

## Verification and outcome

Focused combined verification:

```text
cargo test --locked --all-features --release \
  --bin occam-circuit-hmyuuu \
  --test care_bdd --test sat --test reblind -- --nocapture
```

passed:

- 7 binary tests, with the explicit 20-bit calibration ignored;
- 16 care-BDD tests, including the OxiDD finalist oracle;
- 7 reblind/CLI boundary tests;
- 9 bounded SAT tests.

Diff review found that the Task 11 artifact builder reported
`verifier:"pass"` after Rust exhaustive equivalence even though it never
invoked the official Julia verifier. The benchmark contract reserves `pass`
for external verification; `artifact.json` already records internal
equivalence separately. TDD evidence:

- RED: the focused binary test failed with
  `missing metrics key "verifier":"not_run"`;
- GREEN: the same test passed after the DD builder changed only that field to
  `not_run` and explicitly rejected a false `pass` claim.

The runner will therefore classify an otherwise exact standalone DD cell as
`VERIFIER_NOT_RUN` until a separate official-verifier step supplies genuine
pass/fail evidence. This prevents premature promotion.

The first repeated combined gate then reproduced the previously observed
`AlreadyExists` test-isolation failure in the binary test helper. Root-cause
tracing showed that parallel tests shared one process ID and used a
coarse-resolution wall-clock value as the only per-directory nonce. The
test-only helper now follows the already-established `tests/sat.rs` pattern:
one process-local atomic counter is included in every path. The complete binary
test target passed five consecutive runs after this change; production
artifact naming was not modified.

Fresh post-resolution `make test` passed:

- 31 protocol/design tests plus 29 subtests;
- 181 runner/cluster tests plus 56 subtests;
- formatting;
- every locked all-feature release Rust unit, integration, and doc test;
- the protocol gate.

No public-data, sealed-evaluation, official-Julia, memory, or benchmark-accuracy
claim is made by this integration. Any later command loss, contract drift,
nondeterminism, equivalence failure, or protocol-gate failure rejects it.
