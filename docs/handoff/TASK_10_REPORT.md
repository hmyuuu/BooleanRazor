# Task 10 implementation report

Status: complete through Step 8. Step 9 was intentionally not executed.

## Scope

- Added the five-minute autoresearch cell runner with canonical execution
  specifications, immutable provenance, process-group timeout enforcement,
  normalized terminal outcomes, stable artifact reads, transitive artifact
  binding, and atomic manifests.
- Added the Slurm terminal-failure materializer with strict `sacct` parsing,
  evidence hashing, deterministic manifests, and no-overwrite validation.
- Added the proposer/custodian/evaluator firewall, operator log template, and
  fresh-worktree lifecycle documentation.
- Expanded the protocol gate to validate the exact execution dialect,
  provenance, manifests, logs, artifacts, scheduler evidence, and the frozen
  360-row baseline matrix without changing its bytes.
- Kept all implementation changes inside the solution subtree; no stable
  top-level harness behavior was changed.

## TDD evidence

The implementation was developed as explicit red/green increments:

1. Runner foundation: RED, 2 failures because the runner was absent; GREEN,
   2 passing tests.
2. Runner behavior: RED, 3 success/verifier failures; GREEN, 17 tests and
   23 subtests passed.
3. Slurm failure materializer: RED, 24 failures/subtest assertions because the
   materializer was absent; GREEN, 8 tests and 20 subtests passed.
4. Documentation and firewall: RED, 2 missing-file failures; GREEN, 3 tests
   and 4 subtests passed.
5. Gate dialect migration: RED, 17 failures, 11 passes, and 3 subtests against
   the old dialect; GREEN, 18 tests and 13 subtests passed.
6. Protocol wording: RED against the old protocol language; GREEN, 1 test
   passed.
7. Adversarial review:
   - RED for integer timeout evidence, launch-failure tracebacks, and scheduler
     timeout canonicalization; GREEN, 3 tests and 5 subtests passed.
   - RED for accepting noncanonical `1.00`; GREEN after strict canonical
     numeric parsing.
   - RED for accepting symlinked container provenance; GREEN after no-follow
     validation.
   - RED for accepting a truncated existing runner manifest; GREEN, 2 tests
     passed after full validation.
   - RED for Boolean row fields, scheduler bindings, and run-spec binding;
     GREEN, 3 tests and 3 subtests passed.

## Fresh verification

- `python -m pytest autoresearch research/test_check_gate.py -q`
  — 56 passed, 63 subtests passed.
- `make test` from the activated project virtual environment — 223 passed,
  95% coverage.
- `python research/check_gate.py --phase protocol`
  — protocol gate passed.
- `ruff check` on every changed Python file — passed.
- `python -m py_compile` on every changed Python file — passed.
- `git diff --check` — passed.

The first repository-suite invocation outside the project virtual environment
could not import pytest under the system Python. Re-running the prescribed
command after `source .venv/bin/activate` produced the passing result above.

## Guardrails

- No public or private benchmark data was attached, inspected, or executed.
- No sealed evaluator was invoked.
- Step 9 remains blocked on its declared prerequisites and was not attempted.
- The baseline matrix and public privacy surface remain frozen.

Concerns: none in the implemented Step 1–8 scope.

## Independent-review follow-up

The independent review found six fail-closed gaps. Each was reproduced using
synthetic fixtures before production code changed:

1. RED: both a symlinked `cells` directory and a symlinked per-cell directory
   allowed the Slurm materializer to escape `RUN_ROOT`.
2. RED: a JSON metric equal to `10**400` raised `OverflowError` and prevented a
   terminal manifest.
3. RED: a child that unlinked `stdout.log` and `stderr.log` caused the runner to
   raise `FileNotFoundError` instead of terminalizing.
4. RED: the runner and materializer accepted malformed role, seed, repeat,
   blank-field, and timeout semantics in an unselected sibling cell.
5. RED: a non-timeout `ElapsedRaw` above its declared cap was accepted; in a
   two-cell plan this demonstrated the missing all-plan transaction guard.
6. RED: the checker accepted absent TIMEOUT cap evidence, absent runner elapsed
   evidence for non-success terminal states, and nonzero cleanup evidence for
   non-timeout runner states.

GREEN:

- The runner retains its log descriptors, restores the fixed log paths
  atomically, validates every run-spec cell, and converts all malformed metric
  values—including arbitrarily large integers—to `INVALID_METRICS`/65.
- The materializer validates every cell and elapsed cap before planning,
  rejects symlinked destination components, validates every generated manifest
  before writes, then commits all manifests through no-follow directory
  descriptors with rollback on failure.
- The checker requires the declared censored cap for TIMEOUT, measured elapsed
  evidence for every runner terminal state, exactly `0.0` cleanup outside
  TIMEOUT, and canonical nonnegative measured cleanup for TIMEOUT.

Fresh follow-up evidence:

- Targeted regressions — 9 passed, 30 subtests passed.
- Full Task 10 focused suite — 64 passed, 85 subtests passed.
- Repository suite — 223 passed, 95% coverage.
- Protocol gate, Ruff, py_compile, and `git diff --check` — passed.

The follow-up remained synthetic-only. Step 9, benchmark archives, custodian
results, and sealed data were not accessed.

## Second independent-review follow-up

Two remaining runner terminalization gaps were reproduced before the fix:

- RED: syntactically valid metrics JSON containing a 5,000-digit accuracy
  raised Python's integer-conversion `ValueError`; the runner exited 1 without
  a manifest.
- RED: a child precreated `.stdout.log.tmp-<runner-pid>` and
  `.stderr.log.tmp-<runner-pid>`; the predictable atomic-write name collided,
  and the runner exited 1 without a manifest.

GREEN:

- All JSON decoding conversion failures, including integer-digit limits and
  recursion/overflow failures, are wrapped as validation failures so malformed
  metrics terminalize as `INVALID_METRICS` with exit 65.
- Atomic writes reserve a post-child, cryptographically randomized temporary
  with `O_EXCL` and `O_NOFOLLOW`, bounded to 16 collision retries, before
  atomically replacing the fixed log or manifest path.

Fresh evidence:

- Residual adversarial regressions — 2 passed.
- Full Task 10 focused suite — 66 passed, 85 subtests passed.
- Repository suite — 223 passed, 95% coverage.
- Protocol gate, Ruff, py_compile, and `git diff --check` — passed.

This follow-up changed only the runner and its synthetic test. Step 9 and all
benchmark, custodian, and sealed data remained untouched.
