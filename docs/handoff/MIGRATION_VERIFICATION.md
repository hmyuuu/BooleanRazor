# Migration verification

Date: 2026-07-27 (Asia/Shanghai)

## History and privacy

- Source checkpoint: `c345fa5a2b0a964ee4018bca13cf10fc3b098349`.
- Standalone subtree base: `336f4782a1cab3b7586136405e32aaf3aa6ec2cc`.
- Source prefix tree and standalone base tree both equal
  `e10e773f1f5131b665ba086e9db225cc4d40383e`.
- The standalone base contains 20 ordered solution commits.
- The only retained Git ref is `refs/heads/main`; the source repository's tag
  and unrelated harness objects were removed before this metadata commit.
- No public training archive, sealed evaluator rows, custodian state,
  credentials, raw literature, `.venv`, or Rust build output was copied.
- No remote is configured and no `hpccube` job was submitted.
- The 26 tracked rendered-literature files are byte-identical to their source
  copies. Their source formatting contains whitespace diagnostics, so
  `git diff --cached --check` was scoped to exclude
  `.knowledge/literature/**`; every first-party staged file passed.

## Toolchain

- CPython: 3.11.13 in `.venv` (`.python-version` pinned).
- uv: 0.11.29.
- pytest: 9.1.1; pytest-cov: 7.1.0.
- rustc/cargo: 1.93.0.
- Ion: 0.6.5; 23 vendored local skills validated twice with zero errors.
  Ion reported 46 advisory warnings in the unmodified upstream/local skill
  snapshots (tool declarations, helper placement, and phrase/path heuristics);
  the manifest and lock digests were unchanged across both validations.

## Baseline

`make test` passed:

- Python protocol tests: 29 passed, 29 subtests.
- Python runner and offline-HPC tests: 181 passed, 56 subtests.
- Rust all-feature release suite: 67 passed.
- `cargo fmt --all -- --check`: passed.
- `research/check_gate.py --phase protocol`: passed.

The first `make setup` and `make test` attempt inherited the user's configured
Tsinghua Python index and failed with HTTP 403 while fetching `pytest-cov`.
The root cause was reproduced and isolated. The standalone Makefile now passes
an explicit, overridable `UV_DEFAULT_INDEX` (official PyPI by default) to both
`uv sync` and `uv run`; an idempotent setup and the full baseline then passed.

The credentials-free `hpccube.toml` profile parses to SSH alias `hpccube` and
remote root `~/BooleanRazor`. That smoke check is configuration validation
only, not compute authorization.
