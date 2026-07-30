# BooleanRazor Deliverability and Verifier Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn BooleanRazor into an evidence-first, human-navigable research deliverable with truthful verifier states, immutable official-verification records, executable promotion gates, deterministic offline reports, reusable skills, and an operational `AGENTS.md`.

**Architecture:** One canonical report source drives static HTML and concise Markdown, while candidate manifests remain immutable inputs to a separate official-Julia record and promotion-decision pipeline. The runner, protocol checker, report checker, and promotion checker share the same evidence semantics: internal equivalence is distinct from external verification, evidence tracks impose hard claim ceilings, and missing public or sealed evidence produces `blocked`.

**Tech Stack:** Rust 2024 edition with the locked Cargo graph; CPython 3.11.13 and Python standard library; pytest 9.1.1; POSIX `sh`; GNU Make; Ion local skills; semantic HTML, CSS, and dependency-free JavaScript.

## Global Constraints

- Accuracy is primary; reachable gate count is secondary.
- Negation is free and scoring uses reachable serialized XOR/AND gates under the challenge's one-gate XOR metric.
- The disclosed v1 controls A=`x+y`, B=`abs(x-y)`, C=`x*y`, and D=`x²+y²` remain controls, never blind-learning evidence.
- A blind promotion requires 100% training consistency, byte-identical deterministic reruns, exhaustive completed-table equivalence, bound official Julia verification, and the frozen sealed decision.
- The public proposer side never receives sealed rows, source-family labels, generator names, per-example evaluator failures, or private digests.
- The public reblind bundle and sealed results are absent; current blind status must therefore be `blocked`, not passed, failed, or statistically disproved.
- Report generation and validation use only the Python standard library and add no package, font, CDN, tracker, or runtime network dependency.
- Do not install Julia, JAX, a static-site framework, or another heavy tool.
- Do not mount public or sealed data, attach private data, build a container, or submit local/remote Slurm work.
- All new JSON is UTF-8, compact, sorted-key, duplicate-free, finite-number-only, and terminated by one LF.
- All new evidence tools reject symlinks, path escapes, unknown fields, malformed enums, unstable reads, and output overwrite.
- Preserve failed and timed-out cells as censored observations without manufacturing candidate evidence.
- Do not merge care-BDD, GreedyExactConflict, projected-support, fair-scheduler, or TN hypothesis code from experiment branches.
- Preserve the user's pre-existing `docs/LEADERBOARD.md` working-tree change byte-for-byte. At planning time its file SHA-256 is `78e9307b4271f828df5f919de852b52d99af34ad952c366123c744ba643b5d6f` and its Git patch SHA-256 is `c9ce201617ca0e1941031a69a2268aa9e668c497e0b2a6c50598e723c3eb1a3b`.
- Use `apply_patch` for every source, test, data, and documentation edit.
- Use TDD, focused verification, a reviewer gate, and a small commit for every task.

---

## Scope cohesion

This remains one plan because the deliverables are not independent products.
The report's claims depend on the runner status semantics; promotion depends on
the same manifest and verification-record bindings; the skills and navigation
must teach those exact commands and state transitions. Splitting the work into
separate plans would create temporary incompatible evidence dialects. The ten
tasks below are still independently testable and independently reviewable.

## File structure

### Evidence and verifier core

- Modify `src/main.rs`: make frozen-baseline metrics truthfully say
  `verifier:"not_run"` and unit-test the serializer.
- Modify `scripts/run-experiment.py`: validate candidate evidence before
  classifying `pass`, `fail`, or `not_run`, retaining valid evidence for the
  three candidate-bearing terminal states.
- Modify `research/check_gate.py`: recognize the same candidate-bearing states
  and validate their transitive artifacts.
- Modify `research/BENCHMARK_PROTOCOL.md`: document internal equivalence,
  external verification, and retained-but-unsuccessful evidence.
- Create `scripts/evidence_io.py`: bounded canonical JSON, stable regular-file
  reads, evidence-root path resolution, hashing, and non-overwriting atomic
  creation.
- Create `scripts/candidate_evidence.py`: one validator and typed view of
  runner manifest, run spec, artifact index, completed table, and circuit.
- Create `scripts/verify-julia.sh`: reviewed fail-closed official verifier
  wrapper ported byte-for-byte from Task 15.
- Create `scripts/record-verification.py`: invoke the wrapper and create an
  immutable digest-bound `official-verification.json`.
- Create `scripts/check-promotion.py`: evaluate a canonical request and write a
  deterministic, track-bounded promotion decision.

### Report model and generated deliverables

- Create `scripts/report_model.py`: validate `project.json`, render the output
  map, and expose exact report paths.
- Create `scripts/build-report.py`: CLI that writes the deterministic output
  map.
- Create `scripts/check-deliverable.py`: schema, claim, link, freshness, and
  generated-output checker.
- Create `reports/data/project.json`: only hand-edited report content.
- Create `reports/README.md`: generated-versus-authored boundary and local
  viewing commands.
- Create `reports/site/index.html`, `methods.html`, `verification.html`,
  `experiments.html`, `assets/report.css`, and `assets/report.js`: generated
  offline site.
- Create `docs/STATUS.md`, `docs/METHODS.md`,
  `docs/EXPERIMENT_INDEX.md`, and `research/EVIDENCE_LEDGER.md`: generated
  Markdown navigation and claim ledger.
- Create `research/CURRENT_PROMOTION_REQUEST.json`: canonical visible-blind
  request containing literal `none` for unavailable inputs.
- Create `research/CURRENT_PROMOTION_DECISION.json`: deterministic `blocked`
  decision generated from that request.

### Tests

- Modify `autoresearch/test_run_experiment.py`.
- Modify `research/test_check_gate.py`.
- Modify `autoresearch/test_materialize_slurm_failures.py` only if fixture
  assertions need the named candidate-bearing-state constant; scheduler
  behavior must remain unchanged.
- Create `scripts/tests/test_verify_julia.py`.
- Create `scripts/tests/test_record_verification.py`.
- Create `scripts/tests/test_check_promotion.py`.
- Create `scripts/tests/test_report_model.py`.
- Create `scripts/tests/test_build_report.py`.
- Create `scripts/tests/test_check_deliverable.py`.

### Skills, navigation, and build surface

- Create `skills/exact-circuit-optimization/SKILL.md` and its focused
  references.
- Create `skills/circuit-evidence-promotion/SKILL.md` and its focused
  references.
- Modify `Ion.toml` to register both skills.
- Rewrite `AGENTS.md` as the operational decision router.
- Modify `README.md`, `autoresearch/README.md`, `reblind/README.md`,
  `docs/handoff/SESSION_HANDOFF.md`, and only the materially stale command and
  Task 15 status passages in
  `docs/plans/2026-07-23-occam-circuit-rust-bdd-tn.md`.
- Modify `Makefile` to expose and compose report, verifier, promotion, and
  complete verification targets.

---

### Task 1: Make verifier state truthful and retain validated candidate evidence

**Files:**
- Modify: `src/main.rs:273-326`
- Modify: `src/main.rs:1186-1274`
- Modify: `scripts/run-experiment.py:533-625`
- Modify: `autoresearch/test_run_experiment.py:580-617`
- Modify: `research/check_gate.py:40-51`
- Modify: `research/check_gate.py:557-645`
- Modify: `research/check_gate.py:1159-1233`
- Modify: `research/test_check_gate.py:201-335`
- Modify: `research/test_check_gate.py:894-943`
- Modify: `research/BENCHMARK_PROTOCOL.md`

**Interfaces:**
- Consumes: current six-field `metrics.json`, six-field `artifact.json`, native
  run spec, and runner manifest schema version 1.
- Produces: `CANDIDATE_EVIDENCE_STATES =
  {"SUCCESS", "VERIFIER_FAILED", "VERIFIER_NOT_RUN"}` in the checker and the
  invariant that all three states carry transitive candidate evidence while
  only `SUCCESS` returns process code `0`.
- Produces: `baseline_metrics_json(completed_sha256: &str, gates: usize,
  visible_bit_accuracy: f64, visible_exact: f64) -> Vec<u8>`.

- [ ] **Step 1: Add the failing frozen-baseline serializer test**

In the existing `#[cfg(test)]` module in `src/main.rs`, add:

```rust
#[test]
fn frozen_baseline_metrics_do_not_claim_external_verification() {
    let digest = "a".repeat(64);
    let bytes = baseline_metrics_json(&digest, 37, 0.875, 0.75);
    let metrics = std::str::from_utf8(&bytes).unwrap();

    assert_eq!(
        metrics,
        format!(
            "{{\"completed_table_sha256\":\"{digest}\",\"gates\":37,\
\"train_exact\":1.0,\"verifier\":\"not_run\",\
\"visible_cv_bit_accuracy\":0.875,\"visible_cv_exact\":0.75}}\n"
        )
    );
    assert!(!metrics.contains("\"verifier\":\"pass\""));
}
```

- [ ] **Step 2: Verify the Rust test is red**

Run:

```bash
cargo test --locked --all-features --release \
  frozen_baseline_metrics_do_not_claim_external_verification -- --nocapture
```

Expected: compilation fails with `cannot find function
baseline_metrics_json`.

- [ ] **Step 3: Add the truthful serializer and use it**

Place this helper beside `decimal` in `src/main.rs`:

```rust
fn baseline_metrics_json(
    completed_sha256: &str,
    gates: usize,
    visible_bit_accuracy: f64,
    visible_exact: f64,
) -> Vec<u8> {
    format!(
        "{{\"completed_table_sha256\":\"{completed_sha256}\",\
\"gates\":{gates},\"train_exact\":1.0,\"verifier\":\"not_run\",\
\"visible_cv_bit_accuracy\":{},\"visible_cv_exact\":{}}}\n",
        decimal(visible_bit_accuracy),
        decimal(visible_exact),
    )
    .into_bytes()
}
```

Replace the inline `frozen_baseline` metrics `format!` call with:

```rust
let metrics = baseline_metrics_json(
    &completed_sha256,
    gates,
    visible_bit_accuracy,
    visible_exact,
);
```

Write `&metrics` inside `atomic_output`; do not convert it back through UTF-8.

- [ ] **Step 4: Verify the Rust behavior is green**

Run:

```bash
cargo test --locked --all-features --release \
  frozen_baseline_metrics_do_not_claim_external_verification -- --nocapture
```

Expected: one matching test passes and no test fails.

- [ ] **Step 5: Change the runner test to require retained evidence**

Replace
`test_verifier_fail_and_not_run_have_distinct_terminal_codes` in
`autoresearch/test_run_experiment.py` with:

```python
def test_verifier_fail_and_not_run_retain_valid_candidate_evidence(self) -> None:
    table_digest = hashlib.sha256(TABLE_BYTES).hexdigest()
    circuit_digest = hashlib.sha256(CIRCUIT_BYTES).hexdigest()
    for verifier, status, code in (
        ("fail", "VERIFIER_FAILED", 66),
        ("not_run", "VERIFIER_NOT_RUN", 67),
    ):
        with self.subTest(verifier=verifier):
            run_root, metrics_path = self.write_run_spec("2")
            result = self.invoke(
                run_root,
                metrics_path,
                self.artifact_command(metrics_updates={"verifier": verifier}),
            )
            self.assertEqual(result.returncode, code, result.stderr)
            _, manifest = self.read_manifest(run_root)
            self.assertEqual(manifest["status"], status)
            self.assertEqual(manifest["verifier"], verifier)
            self.assertEqual(manifest["train_exact"], "1.0")
            self.assertEqual(manifest["visible_cv_exact"], "0.75")
            self.assertEqual(manifest["visible_cv_bit_accuracy"], "0.875")
            self.assertEqual(manifest["gates"], "37")
            self.assertEqual(manifest["completed_table_sha256"], table_digest)
            self.assertEqual(manifest["circuit_sha256"], circuit_digest)
            self.assertEqual(
                manifest["artifact_path"], "cells/cell-001/artifact.json"
            )
            self.assertRegex(str(manifest["artifact_sha256"]), r"^[0-9a-f]{64}$")
```

Keep `test_missing_malformed_nonfinite_and_out_of_range_metrics_are_invalid`
and `test_invalid_artifact_binding_never_produces_success` unchanged so invalid
evidence still becomes `INVALID_METRICS` with every quality field set to
`none`.

- [ ] **Step 6: Verify the runner test is red for the right reason**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  autoresearch/test_run_experiment.py \
  -k 'verifier_fail_and_not_run or invalid_artifact_binding'
```

Expected: the retained-evidence test fails because the current runner writes
`none`; invalid-artifact tests pass.

- [ ] **Step 7: Validate evidence before status classification**

In `classify_zero_exit`, remove the two early returns for `fail` and
`not_run`. Keep every metrics, artifact, digest, and training-consistency
validation exactly once, construct `CandidateEvidence`, then finish with:

```python
        status, exit_code = {
            "pass": ("SUCCESS", 0),
            "fail": ("VERIFIER_FAILED", 66),
            "not_run": ("VERIFIER_NOT_RUN", 67),
        }[verifier]
        return (
            status,
            exit_code,
            verifier,
            CandidateEvidence(
                train_exact=train_exact,
                visible_cv_exact=visible_exact,
                visible_cv_bit_accuracy=visible_bits,
                gates=str(gates),
                completed_table_sha256=actual_table,
                circuit_sha256=actual_circuit,
                artifact_sha256=sha256_bytes(artifact_raw),
                artifact_path=relative_artifact,
            ),
        )
```

The `except` branch remains:

```python
    except (OSError, ValidationError):
        return "INVALID_METRICS", 65, "not_run", None
```

- [ ] **Step 8: Verify runner evidence retention**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  autoresearch/test_run_experiment.py
```

Expected: the complete runner suite passes.

- [ ] **Step 9: Add checker tests for all candidate-bearing states**

In `research/test_check_gate.py`, change fixture publication from
`if status == "SUCCESS"` to:

```python
if status in gate.CANDIDATE_EVIDENCE_STATES:
    payload.update(
        {
            "train_exact": "1.0",
            "visible_cv_exact": "0.5",
            "visible_cv_bit_accuracy": "0.75",
            "gates": "7",
            **self.write_artifacts(run, cell_id),
        }
    )
else:
    payload.update(
        {
            "train_exact": "none",
            "visible_cv_exact": "none",
            "visible_cv_bit_accuracy": "none",
            "gates": "none",
            "completed_table_sha256": "none",
            "circuit_sha256": "none",
            "artifact_sha256": "none",
            "artifact_path": "none",
        }
    )
```

Add:

```python
def test_candidate_bearing_terminal_states_require_native_artifacts(self) -> None:
    for status in ("SUCCESS", "VERIFIER_FAILED", "VERIFIER_NOT_RUN"):
        with self.subTest(status=status):
            params = params_row()
            expected, run = self.write_expected_json(
                cells=[{"cell_id": "cell-a", "params": params}]
            )
            path = self.write_manifest(run, params, status=status)
            self.assertEqual(self.manifest_errors(run, expected), [])

            payload = json.loads(path.read_bytes())
            payload["artifact_sha256"] = "none"
            path.write_bytes(json_bytes(payload))
            errors = self.manifest_errors(run, expected)
            self.assertTrue(
                any("artifact" in error for error in errors),
                errors,
            )
```

Extend `test_status_requires_exact_verifier_and_metric_mapping` with:

```python
("VERIFIER_NOT_RUN", "pass", "VERIFIER_NOT_RUN requires verifier=not_run"),
```

- [ ] **Step 10: Verify the checker tests are red**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  research/test_check_gate.py \
  -k 'candidate_bearing or status_requires_exact'
```

Expected: collection or execution fails because
`CANDIDATE_EVIDENCE_STATES` does not exist and the checker rejects non-success
artifacts.

- [ ] **Step 11: Align checker semantics with the runner**

Add beside `TERMINAL_STATES`:

```python
CANDIDATE_EVIDENCE_STATES = {
    "SUCCESS",
    "VERIFIER_FAILED",
    "VERIFIER_NOT_RUN",
}
FAILED_STATES = TERMINAL_STATES - {"SUCCESS"}
```

In `check_terminal_metrics`, use:

```python
if status in CANDIDATE_EVIDENCE_STATES:
```

for training, CV, gate, artifact-hash, elapsed, and memory validation. Use the
existing non-success failure branch only for
`TERMINAL_STATES - CANDIDATE_EVIDENCE_STATES`. Keep status-specific exit-code,
timeout, and verifier checks outside that split.

In `check_native_artifacts`, replace the success-only guard with:

```python
if row.get("status") not in CANDIDATE_EVIDENCE_STATES:
    for field, value in (
        ("artifact_path", artifact_path),
        ("completed_table_sha256", completed_digest),
        ("circuit_sha256", circuit_digest),
    ):
        if value != "none":
            errors.append(f"{label} non-candidate manifest must set {field}=none")
    return
```

Change `SUCCESS has invalid completed table digest` to
`candidate has invalid completed table digest`, and change
`SUCCESS has invalid circuit digest` to
`candidate has invalid circuit digest`.

- [ ] **Step 12: Document the distinction**

Add this exact paragraph to the evidence section of
`research/BENCHMARK_PROTOCOL.md`:

```markdown
`artifact.json` field `equivalence="pass"` records exhaustive equivalence
inside the Rust XAG backend. The metrics and manifest field `verifier` records
only the official external verifier. `VERIFIER_NOT_RUN` and
`VERIFIER_FAILED` retain a fully validated, digest-bound candidate so a
separate immutable verification record can be created or diagnosed, but
neither status is runner success. Timeout, OOM, nonzero exit, invalid metrics,
cancellation, and scheduler-only materialization carry no candidate-quality
or artifact claim.
```

- [ ] **Step 13: Run the focused contract**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  autoresearch/test_run_experiment.py \
  research/test_check_gate.py \
  autoresearch/test_materialize_slurm_failures.py
cargo test --locked --all-features --release \
  frozen_baseline_metrics_do_not_claim_external_verification -- --nocapture
```

Expected: all selected Python tests and the Rust test pass.

- [ ] **Step 14: Commit the truthful evidence dialect**

```bash
git add src/main.rs \
  scripts/run-experiment.py \
  autoresearch/test_run_experiment.py \
  research/check_gate.py \
  research/test_check_gate.py \
  autoresearch/test_materialize_slurm_failures.py \
  research/BENCHMARK_PROTOCOL.md
git diff --cached --check
git commit -m "fix: separate candidate evidence from verifier success"
```

Expected: the commit contains no report, skill, branch-only algorithm, or
leaderboard change.

---

### Task 2: Port the reviewed official-Julia wrapper

**Files:**
- Create: `scripts/verify-julia.sh`
- Create: `scripts/tests/test_verify_julia.py`

**Interfaces:**
- Consumes: six positional arguments
  `JULIA_BIN VERIFY_JL CIRCUIT DATASET EXPECTED_GATES INSTANCE`.
- Produces: exactly one canonical line such as
  `instance=mystery-A gates=37 samples=2000 exact=1.0 bit=1.0 verifier=pass`
  only after every official metric matches; instance, gate, and sample values
  come from the validated invocation.
- Historical source: commit
  `41518ce876b9c2a5939a525e538473165765203c`, file SHA-256
  `6f17bb7705d459db3c2e12f0fe0ed679d7e8f8e5cc543f2cc521a220dc4b70cb`;
  test SHA-256
  `5cfe0944c974ce8175a61ae345da89bb0b62e6f0d36ff2fab658faeff0720be8`.

- [ ] **Step 1: Add the reviewed fixture tests before the wrapper**

Read the immutable test source:

```bash
git show \
  41518ce876b9c2a5939a525e538473165765203c:scripts/tests/test_verify_julia.py
```

Use `apply_patch` to add those exact bytes as
`scripts/tests/test_verify_julia.py`. The file must cover:

```text
exact four-line success
gate mismatch
sample mismatch
exact-match mismatch
bit-accuracy mismatch
extra or duplicate output line
nonzero Julia exit
unsafe instance label
missing or symlinked verifier/circuit/dataset
wrong header
empty dataset
CRLF dataset
```

Verify the copied test bytes:

```bash
shasum -a 256 scripts/tests/test_verify_julia.py
```

Expected:

```text
5cfe0944c974ce8175a61ae345da89bb0b62e6f0d36ff2fab658faeff0720be8  scripts/tests/test_verify_julia.py
```

- [ ] **Step 2: Verify the wrapper tests are red**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  scripts/tests/test_verify_julia.py
```

Expected: failure because `scripts/verify-julia.sh` is missing.

- [ ] **Step 3: Add the exact reviewed wrapper**

Read the immutable source:

```bash
git show \
  41518ce876b9c2a5939a525e538473165765203c:scripts/verify-julia.sh
```

Use `apply_patch` to add those exact 95 lines as
`scripts/verify-julia.sh`. Its control flow must remain:

```sh
#!/bin/sh
set -eu
LC_ALL=C
export LC_ALL

fail() {
  printf 'error: %s\n' "$1" >&2
  exit 65
}
```

followed by exact argument-count validation, canonical expected-gate and safe
instance validation, executable/regular/non-symlink input checks, LF CSV
validation, sample counting, temporary stdout capture, exact four-line parsing,
strict equality checks, and the canonical summary:

```sh
printf 'instance=%s gates=%s samples=%s exact=1.0 bit=1.0 verifier=pass\n' \
  "$instance" "$gates" "$samples"
```

Set the executable bit and verify the source digest:

```bash
chmod +x scripts/verify-julia.sh
shasum -a 256 scripts/verify-julia.sh
```

Expected:

```text
6f17bb7705d459db3c2e12f0fe0ed679d7e8f8e5cc543f2cc521a220dc4b70cb  scripts/verify-julia.sh
```

- [ ] **Step 4: Run the complete wrapper contract**

Run:

```bash
sh -n scripts/verify-julia.sh
uv run --default-index https://pypi.org/simple pytest -q \
  scripts/tests/test_verify_julia.py
```

Expected: shell syntax succeeds and 14 wrapper tests pass.

- [ ] **Step 5: Review the port boundary and commit**

Run:

```bash
git diff --no-index \
  /dev/null scripts/verify-julia.sh
git diff --check
```

Confirm that no `LOG.md`, disclosed-v1 result, temporary official archive,
Julia installation, or branch documentation was imported.

```bash
git add scripts/verify-julia.sh scripts/tests/test_verify_julia.py
git commit -m "feat: add fail-closed Julia verifier wrapper"
```

---

### Task 3: Create immutable, race-checked official verification records

**Files:**
- Create: `scripts/evidence_io.py`
- Create: `scripts/candidate_evidence.py`
- Create: `scripts/record-verification.py`
- Create: `scripts/tests/test_record_verification.py`

**Interfaces:**
- Produces in `evidence_io.py`:
  - `EvidenceError(ValueError)`.
  - `canonical_json_bytes(value: object) -> bytes`.
  - `sha256_bytes(value: bytes) -> str`.
  - `read_stable_regular(path: Path, label: str, max_bytes: int) -> bytes`.
  - `load_canonical_object(path: Path, label: str,
    max_bytes: int = 16 * 1024 * 1024) -> tuple[dict[str, object], bytes]`.
  - `resolve_evidence_path(root: Path, value: str, label: str) -> Path`.
  - `atomic_create(path: Path, data: bytes) -> None`.
- Produces in `candidate_evidence.py`:
  - immutable `TerminalEvidence` for every canonical terminal runner manifest.
  - immutable `CandidateEvidence(TerminalEvidence)` for the three
    candidate-bearing states.
  - `load_terminal_manifest(path: Path,
    evidence_root: Path | None = None) -> TerminalEvidence`.
  - `load_candidate_manifest(path: Path,
    evidence_root: Path | None = None) -> CandidateEvidence`.
- Produces in `record-verification.py`:
  - `build_record(args: argparse.Namespace) -> dict[str, object]`.
  - CLI exit `0` on one immutable pass record, `2` on input/validation error,
    and the wrapper's nonzero status on verifier failure.

- [ ] **Step 1: Write low-level evidence I/O tests**

Start `scripts/tests/test_record_verification.py` with tests that import the
three scripts through `importlib.util` and assert:

```python
def test_canonical_loader_rejects_duplicate_keys_nan_and_symlink(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_bytes(b'{"a":1,"a":2}\n')
    with pytest.raises(evidence_io.EvidenceError, match="duplicate"):
        evidence_io.load_canonical_object(duplicate, "duplicate")

    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_bytes(b'{"a":NaN}\n')
    with pytest.raises(evidence_io.EvidenceError, match="finite"):
        evidence_io.load_canonical_object(nonfinite, "nonfinite")

    target = tmp_path / "target.json"
    target.write_bytes(b'{"a":1}\n')
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(evidence_io.EvidenceError, match="regular"):
        evidence_io.load_canonical_object(link, "link")
```

Add `test_atomic_create_refuses_existing_output` and
`test_resolve_evidence_path_rejects_absolute_parent_and_symlink_component`.

- [ ] **Step 2: Verify evidence I/O tests are red**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  scripts/tests/test_record_verification.py \
  -k 'canonical_loader or atomic_create or resolve_evidence_path'
```

Expected: import fails because `scripts/evidence_io.py` does not exist.

- [ ] **Step 3: Implement the exact low-level contract**

Use these constants and signatures in `scripts/evidence_io.py`:

```python
HEX_64 = re.compile(r"[0-9a-f]{64}")
DEFAULT_MAX_BYTES = 16 * 1024 * 1024
MAX_ARTIFACT_BYTES = 512 * 1024 * 1024


class EvidenceError(ValueError):
    """Invalid, unstable, escaped, or noncanonical evidence."""


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
```

The JSON decoder must use both hooks:

```python
def _reject_constant(value: str) -> NoReturn:
    raise EvidenceError(f"JSON number must be finite: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, child in pairs:
        if key in value:
            raise EvidenceError(f"duplicate JSON key: {key}")
        value[key] = child
    return value
```

`read_stable_regular` must open with `O_RDONLY | O_NOFOLLOW`, require
`stat.S_ISREG`, reject sizes above `max_bytes`, read to EOF, compare
device/inode/size/mtime/ctime before and after, then repeat the entire read and
require byte equality. `load_canonical_object` must decode with the hooks,
require a dict, and compare raw bytes with `canonical_json_bytes`.

`resolve_evidence_path` must reject absolute values, empty values, `.`/`..`
components, and every symlinked component before requiring that the resolved
regular file remains under `root.resolve(strict=True)`.

`atomic_create` must create a mode-`0600` same-directory temporary using
`O_CREAT | O_EXCL | O_NOFOLLOW`, write and fsync all bytes, install the final
name with `os.link` so an existing path cannot be replaced, fsync the parent,
and remove the temporary in `finally`.

JSON callers use `DEFAULT_MAX_BYTES`. Candidate completed tables, circuits,
official datasets, and verifier inputs use `MAX_ARTIFACT_BYTES`, which covers
the existing 45,088,781-byte synthetic calibration table without permitting
unbounded reads.

- [ ] **Step 4: Run the low-level tests**

Run the Step 2 command again.

Expected: all selected evidence I/O tests pass.

- [ ] **Step 5: Write a complete candidate-manifest fixture and failing tests**

The fixture must create:

```text
run/
  run_spec.json
  cells/cell-a/
    manifest.json
    artifact.json
    completed-table.csv
    circuit.txt
    stdout.log
    stderr.log
```

Use candidate status `VERIFIER_NOT_RUN`, `verifier="not_run"`,
`train_exact="1.0"`, canonical CV metrics, fixed relative artifact path, and
SHA-256 values computed from exact fixture bytes. Add:

```python
def test_candidate_loader_binds_manifest_run_spec_and_artifacts(
    candidate_run: CandidateRun,
) -> None:
    loaded = candidate_evidence.load_candidate_manifest(candidate_run.manifest)
    assert loaded.comparison_id == "cell-a"
    assert loaded.status == "VERIFIER_NOT_RUN"
    assert loaded.verifier == "not_run"
    assert loaded.gates == 1
    assert loaded.circuit_sha256 == sha256(candidate_run.circuit)
    assert loaded.completed_table_sha256 == sha256(candidate_run.dataset)


@pytest.mark.parametrize(
    "mutation",
    (
        "manifest_hash",
        "run_spec_hash",
        "artifact_hash",
        "table_hash",
        "circuit_hash",
        "equivalence",
        "train_exact",
        "status_without_evidence",
    ),
)
def test_candidate_loader_rejects_broken_transitive_binding(
    candidate_run: CandidateRun, mutation: str
) -> None:
    candidate_run.apply_mutation(mutation)
    with pytest.raises(evidence_io.EvidenceError):
        candidate_evidence.load_candidate_manifest(candidate_run.manifest)


def test_terminal_loader_preserves_failure_without_candidate_claim(
    candidate_run: CandidateRun,
) -> None:
    candidate_run.replace_with_nonzero_exit()
    loaded = candidate_evidence.load_terminal_manifest(candidate_run.manifest)
    assert loaded.status == "NONZERO_EXIT"
    assert loaded.verifier == "not_run"
    with pytest.raises(evidence_io.EvidenceError, match="candidate-bearing"):
        candidate_evidence.load_candidate_manifest(candidate_run.manifest)
```

- [ ] **Step 6: Verify candidate loading is red**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  scripts/tests/test_record_verification.py \
  -k 'candidate_loader'
```

Expected: import fails because `scripts/candidate_evidence.py` is missing.

- [ ] **Step 7: Implement the typed candidate validator**

Define:

```python
@dataclass(frozen=True)
class TerminalEvidence:
    manifest_path: Path
    manifest_sha256: str
    run_root: Path
    run_spec_path: Path
    run_spec_sha256: str
    comparison_id: str
    source_commit: str
    tree_digest: str
    dataset_id: str
    blind: str
    evaluation_scope: str
    hardware: str
    timeout_seconds: str
    role: str
    method: str
    status: str
    verifier: str


@dataclass(frozen=True)
class CandidateEvidence(TerminalEvidence):
    train_exact: str
    visible_cv_exact: str
    visible_cv_bit_accuracy: str
    gates: int
    artifact_path: Path
    artifact_sha256: str
    completed_table_path: Path
    completed_table_sha256: str
    circuit_path: Path
    circuit_sha256: str

    def deterministic_fingerprint(self) -> tuple[object, ...]:
        return (
            self.source_commit,
            self.tree_digest,
            self.dataset_id,
            self.method,
            self.train_exact,
            self.visible_cv_exact,
            self.visible_cv_bit_accuracy,
            self.gates,
            self.completed_table_sha256,
            self.circuit_sha256,
            self.artifact_sha256,
        )
```

`load_terminal_manifest` must require the exact runner schema version 1,
`producer="runner"`, a known terminal status, the exact status/verifier/exit
mapping, fixed native manifest location, canonical run spec whose digest
matches the manifest, matching cell params and provenance, and valid
operational/log hashes. It retains failed states without interpreting their
quality fields as candidates.

`load_candidate_manifest` calls `load_terminal_manifest`, requires a status in
`{"SUCCESS", "VERIFIER_FAILED", "VERIFIER_NOT_RUN"}`, the exact
status/verifier/exit mapping, `train_exact="1.0"`, canonical artifact schema with
`equivalence="pass"`, fixed in-cell filenames, and exact transitive hashes.

- [ ] **Step 8: Run candidate validation tests**

Run the Step 6 command again.

Expected: all selected tests pass.

- [ ] **Step 9: Write failing verification-record tests**

The fixture Julia executable must answer `--version` with exactly
`julia version 1.12.4\n` and otherwise print the official four-line metrics.
Add assertions for this exact record:

```python
assert record == {
    "bit_accuracy": "1.0",
    "circuit_sha256": sha256(candidate_run.circuit),
    "comparison_id": "cell-a",
    "dataset_sha256": sha256(candidate_run.dataset),
    "exact_accuracy": "1.0",
    "gates": 1,
    "julia_version": {
        "sha256": sha256(b"julia version 1.12.4\n"),
        "text": "julia version 1.12.4",
    },
    "manifest_sha256": sha256(candidate_run.manifest.read_bytes()),
    "run_spec_sha256": sha256(candidate_run.run_spec.read_bytes()),
    "samples": 2,
    "schema_version": 1,
    "status": "pass",
    "verify_jl_sha256": sha256(candidate_run.verify_jl.read_bytes()),
}
```

Add separate tests for malformed manifest, wrapper failure, output
non-overwrite, noncanonical/relative/symlink input paths, and parameterized
replacement races for manifest, run spec, artifact, circuit, dataset, and
`verify.jl`. Every failure must leave the requested output absent.

- [ ] **Step 10: Verify record tests are red**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  scripts/tests/test_record_verification.py \
  -k 'verification_record or replacement_race or refuses_existing'
```

Expected: failure because `scripts/record-verification.py` is absent.

- [ ] **Step 11: Implement record creation**

The CLI is exactly:

```python
parser.add_argument("--manifest", required=True, type=Path)
parser.add_argument("--julia-bin", required=True, type=Path)
parser.add_argument("--verify-jl", required=True, type=Path)
parser.add_argument("--dataset", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
```

Require every input and output path to be absolute and lexically normalized.
Read and hash all bound files, load the candidate, run:

```python
environment = os.environ.copy()
environment["LC_ALL"] = "C"
version = subprocess.run(
    [str(args.julia_bin), "--version"],
    check=True,
    capture_output=True,
    env=environment,
)
verified = subprocess.run(
    [
        str(Path(__file__).with_name("verify-julia.sh")),
        str(args.julia_bin),
        str(args.verify_jl),
        str(candidate.circuit_path),
        str(args.dataset),
        str(candidate.gates),
        candidate.comparison_id,
    ],
    check=False,
    capture_output=True,
    env=environment,
)
```

Reject nonzero version or wrapper status, any version stderr, a version stdout
other than one LF-terminated printable line, any wrapper stderr, or a wrapper
stdout not matching:

```python
SUMMARY = re.compile(
    rb"instance=([A-Za-z0-9][A-Za-z0-9._-]*) "
    rb"gates=(0|[1-9][0-9]*) samples=(0|[1-9][0-9]*) "
    rb"exact=1\.0 bit=1\.0 verifier=pass\n"
)
```

Re-read the manifest, run spec, artifact, circuit, dataset, verifier, and Julia
version after wrapper execution; require byte equality with every pre-exec
read. Build the exact record asserted in Step 9 and publish it through
`atomic_create`.

- [ ] **Step 12: Run and review the complete record suite**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  scripts/tests/test_record_verification.py
```

Expected: all canonicality, binding, race, failure, and deterministic-byte
tests pass without a real Julia installation.

- [ ] **Step 13: Commit immutable verification records**

```bash
git add scripts/evidence_io.py \
  scripts/candidate_evidence.py \
  scripts/record-verification.py \
  scripts/tests/test_record_verification.py
git diff --cached --check
git commit -m "feat: bind official verification to candidate evidence"
```

---

### Task 4: Implement deterministic, evidence-track-bounded promotion decisions

**Files:**
- Create: `scripts/check-promotion.py`
- Create: `scripts/tests/test_check_promotion.py`
- Create: `research/CURRENT_PROMOTION_REQUEST.json`
- Create: `research/CURRENT_PROMOTION_DECISION.json`

**Interfaces:**
- Consumes canonical request keys:
  `schema_version`, `track`, `candidate_evidence`,
  `deterministic_pairs`, `official_verifications`, `frozen_comparison`,
  `sealed_results`.
- Allowed tracks and ceilings:
  - `disclosed_control` → `promote_control`
  - `synthetic` → `advance_public_candidate`
  - `blind_visible` → `freeze_candidate`
  - `sealed_confirmation` → `promote_blind_result`
- Also produces `blocked`, `reject`, or `no_change`.
- Produces decision keys:
  `schema_version`, `track`, `decision`, `highest_legal_next_step`, `reasons`,
  `input_sha256`.
- Production types are:

```python
@dataclass(frozen=True)
class VerificationBinding:
    comparison_id: str
    manifest_sha256: str
    circuit_sha256: str
    dataset_sha256: str
    gates: int


@dataclass(frozen=True)
class DeterministicPair:
    left: CandidateEvidence
    right: CandidateEvidence
    byte_identical: bool


@dataclass(frozen=True)
class EvidenceBundle:
    terminals: tuple[TerminalEvidence, ...]
    candidates: tuple[CandidateEvidence, ...]
    pairs: tuple[DeterministicPair, ...]
    verifications: tuple[VerificationBinding, ...]
```

- The test helper `PromotionFixture` exposes:
  `write_valid_request(track: str) -> Path` and
  `run_checker(request: Path) -> tuple[subprocess.CompletedProcess[str], Path]`.

- [ ] **Step 1: Freeze exact request, pair, comparison, sealed, and decision schemas**

Use this request shape in tests:

```json
{"candidate_evidence":["cells/baseline-1nn-r0/manifest.json","cells/baseline-1nn-r1/manifest.json","cells/baseline-zero-r0/manifest.json","cells/baseline-zero-r1/manifest.json","cells/candidate-r0/manifest.json","cells/candidate-r1/manifest.json"],"deterministic_pairs":[{"left":"cells/baseline-1nn-r0/manifest.json","right":"cells/baseline-1nn-r1/manifest.json"},{"left":"cells/baseline-zero-r0/manifest.json","right":"cells/baseline-zero-r1/manifest.json"},{"left":"cells/candidate-r0/manifest.json","right":"cells/candidate-r1/manifest.json"}],"frozen_comparison":"frozen-comparison.json","official_verifications":["cells/baseline-1nn-r0/official-verification.json","cells/baseline-zero-r0/official-verification.json","cells/candidate-r0/official-verification.json"],"schema_version":1,"sealed_results":"none","track":"synthetic"}
```

`candidate_evidence` and `official_verifications` are each either a nonempty
list of unique relative paths or the literal string `none`.
`deterministic_pairs` is either a nonempty list of exact `left`/`right` objects
or `none`. `frozen_comparison` and `sealed_results` are each one unique
relative path string or `none`.

The comparison file schema is:

```json
{"baseline_ids":["baseline-1nn-r0","baseline-zero-r0"],"candidate_ids":["candidate-r0"],"design_path":"visible-design.json","design_sha256":"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff","expected_ids":["baseline-1nn-r0","baseline-1nn-r1","baseline-zero-r0","baseline-zero-r1","candidate-r0","candidate-r1"],"frozen_candidate_id":"candidate-r0","rule":"accuracy_first_then_gates","schema_version":1}
```

The referenced visible design is:

```json
{"cells":[{"comparison_id":"baseline-1nn-r0","dataset_id":"opaque-synthetic"},{"comparison_id":"baseline-1nn-r1","dataset_id":"opaque-synthetic"},{"comparison_id":"baseline-zero-r0","dataset_id":"opaque-synthetic"},{"comparison_id":"baseline-zero-r1","dataset_id":"opaque-synthetic"},{"comparison_id":"candidate-r0","dataset_id":"opaque-synthetic"},{"comparison_id":"candidate-r1","dataset_id":"opaque-synthetic"}],"dataset_boundary":"synthetic-fixture","schema_version":1}
```

In a valid fixture, compute `design_sha256` from those exact canonical design
bytes. The all-`f` value above is the negative digest-mismatch fixture.
For `blind_visible` and `sealed_confirmation`, `dataset_boundary` is the
tracked 64-hex `reblind/COMMITMENT.txt` value. The checker requires the exact
comparison-ID/dataset-ID projection declared by this design.

The sealed file schema is:

```json
{"analysis_rule":"predeclared_100x_or_scaling","baseline_methods":["hamming-1nn","zero-fill"],"comparison_ids":["baseline-1nn-r0","baseline-1nn-r1","baseline-zero-r0","baseline-zero-r1","candidate-r0","candidate-r1"],"failed_cells_normalized":true,"frozen_comparison_sha256":"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff","matched_100x_against":["hamming-1nn","zero-fill"],"scaling_advantage_against":[],"schema_version":1}
```

In the success fixture, assign
`sealed["frozen_comparison_sha256"] =
hashlib.sha256(frozen_comparison.read_bytes()).hexdigest()` before canonical
serialization; the all-`f` value above exercises digest-mismatch rejection.

- [ ] **Step 2: Write the state-machine tests**

Add parameterized tests whose fully valid evidence yields:

```python
(
    ("disclosed_control", "promote_control"),
    ("synthetic", "advance_public_candidate"),
    ("blind_visible", "freeze_candidate"),
    ("sealed_confirmation", "promote_blind_result"),
)
```

Add forbidden-transition tests:

```python
@pytest.mark.parametrize(
    ("track", "forbidden"),
    (
        ("disclosed_control", "promote_blind_result"),
        ("synthetic", "freeze_candidate"),
        ("synthetic", "promote_blind_result"),
        ("blind_visible", "promote_blind_result"),
    ),
)
def test_track_ceiling_never_emits_forbidden_decision(
    promotion_fixture: PromotionFixture,
    track: str,
    forbidden: str,
) -> None:
    request = promotion_fixture.write_valid_request(track=track)
    result, output = promotion_fixture.run_checker(request)
    assert result.returncode == 0, result.stderr
    decision = json.loads(output.read_bytes())
    assert decision["decision"] != forbidden
    assert (
        decision["highest_legal_next_step"]
        == promotion.TRACK_CEILINGS[track]
    )
```

Also test:

```text
literal none for current visible request -> blocked
missing candidate evidence -> blocked
missing official verification -> blocked
foreign/stale verification record -> reject
nondeterministic pair -> reject
mixed source commit/tree/dataset/hardware/timeout -> reject
missing comparison cell -> blocked
filtered terminal failure -> reject
present terminal failure remains visible and blocks a positive decision
candidate worse or equal under strict ordering -> no_change
bit-accuracy-only improvement at equal exact accuracy -> no_change
equal exact accuracy with fewer reachable gates -> positive track-bounded decision
higher exact accuracy remains a strict improvement regardless of diagnostic bit accuracy
sealed result missing either baseline method -> blocked
path escape, absolute path, symlink, duplicate path -> input error and no output
identical inputs -> byte-identical decision
existing output -> no overwrite
committed current request -> byte-identical committed blocked decision
```

- [ ] **Step 3: Verify the promotion suite is red**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  scripts/tests/test_check_promotion.py
```

Expected: import or subprocess failure because `scripts/check-promotion.py`
does not exist.

- [ ] **Step 4: Implement fail-closed request loading**

Expose:

```python
TRACK_CEILINGS = {
    "disclosed_control": "promote_control",
    "synthetic": "advance_public_candidate",
    "blind_visible": "freeze_candidate",
    "sealed_confirmation": "promote_blind_result",
}
REQUEST_FIELDS = {
    "schema_version",
    "track",
    "candidate_evidence",
    "deterministic_pairs",
    "official_verifications",
    "frozen_comparison",
    "sealed_results",
}
```

Resolve every evidence path relative to `request_path.parent` through
`resolve_evidence_path`. Reject duplicates after normalized resolution. Load
candidate manifests with `load_candidate_manifest`; load official records as
canonical JSON and require exact agreement on `comparison_id`,
`manifest_sha256`, `run_spec_sha256`, `circuit_sha256`, `dataset_sha256`,
gates, and
`status="pass"`.

Load every path in `candidate_evidence` first through
`load_terminal_manifest`. Load the candidate-bearing subset again through
`load_candidate_manifest`; never discard or omit a terminal failure when
checking the frozen design's `expected_ids`.

Malformed requests and unsafe or duplicate paths are not scientific decisions.
They exit `2` without creating an output. A canonical, safely loaded request
whose evidence is stale, foreign, nondeterministic, or otherwise ineligible
produces the bounded `reject` decision and an allowed reason code.

- [ ] **Step 5: Implement common gates and deterministic pairing**

For a positive decision, require:

```python
def common_reason_codes(bundle: EvidenceBundle) -> list[str]:
    reasons: list[str] = []
    if not bundle.candidates:
        reasons.append("candidate_evidence_absent")
    if not bundle.pairs:
        reasons.append("deterministic_pairs_absent")
    if not bundle.verifications:
        reasons.append("official_verifications_absent")
    if len({row.source_commit for row in bundle.terminals}) > 1:
        reasons.append("mixed_source_commit")
    if len({row.tree_digest for row in bundle.terminals}) > 1:
        reasons.append("mixed_tree_digest")
    if len(
        {
            (row.blind, row.evaluation_scope)
            for row in bundle.terminals
        }
    ) > 1:
        reasons.append("mixed_dataset_boundary")
    if len({row.hardware for row in bundle.terminals}) > 1:
        reasons.append("mixed_hardware")
    if len({row.timeout_seconds for row in bundle.terminals}) > 1:
        reasons.append("mixed_timeout_cap")
    candidate_circuits = {
        row.circuit_sha256 for row in bundle.candidates
    }
    verified_circuits = {
        record.circuit_sha256 for record in bundle.verifications
    }
    if candidate_circuits != verified_circuits:
        reasons.append("foreign_verification_record")
    if any(not pair.byte_identical for pair in bundle.pairs):
        reasons.append("nondeterministic_pair")
    if any(
        row.status
        not in {"SUCCESS", "VERIFIER_FAILED", "VERIFIER_NOT_RUN"}
        for row in bundle.terminals
    ):
        reasons.append("terminal_failure_present")
    return sorted(set(reasons))
```

The actual implementation must use these exact reason codes:

```text
candidate_evidence_absent
deterministic_pairs_absent
official_verifications_absent
frozen_comparison_absent
sealed_results_absent
foreign_verification_record
nondeterministic_pair
mixed_source_commit
mixed_tree_digest
mixed_dataset_boundary
mixed_hardware
mixed_timeout_cap
missing_comparison_cell
filtered_terminal_failure
terminal_failure_present
strict_improvement_not_met
sealed_baseline_incomplete
frozen_comparison_digest_mismatch
control_instance_set_mismatch
prediction_commitment_mismatch
```

The ordered deterministic pairs must be a perfect partition of all
candidate-bearing manifests. Each endpoint appears exactly once; `left` is the
canonical representative. Each pair must have equal
`deterministic_fingerprint()` and byte-equal completed-table, circuit, and
artifact-index content.

Require exactly one official pass record for every `left` representative and
no other record. Before constructing `VerificationBinding`, require exact
agreement with that left candidate on `comparison_id`, `manifest_sha256`,
`run_spec_sha256`, `circuit_sha256`, and `gates`. Pair byte identity carries
the verification coverage to `right`. `dataset_sha256` is the independently
bound official-verifier input digest; do not equate it to the candidate's
completed-table digest. The disclosed-control gate below additionally binds it
to the public prediction commitment.

For `disclosed_control`, hard-code and verify the four public prediction
commitments already tracked by the disclosed-v1 challenge:

```python
DISCLOSED_PREDICTION_COMMITMENTS = {
    "mystery-A": "51e3f026def41778ecd0d7dcaee9f970b9937488e6716891932b73824c16d4c7",
    "mystery-B": "e2c9d0e23ee36bfc0f12d7f39fdfe2ca5a8abe8eb194fec56500733694b75c28",
    "mystery-C": "c7b37413844bf0b10ebad0010046469f500354a22cc2ba95cbe42709f8e8337d",
    "mystery-D": "b445a717483303fa3c5d8a1f7abe81888b267b7c472121c9c464fa9766808580",
}
```

Require exactly those four `dataset_id` values, a deterministic pair for each,
and one official record whose `dataset_sha256` equals the corresponding
commitment and whose gate count/circuit digest matches the candidate. Use
reason codes `control_instance_set_mismatch` and
`prediction_commitment_mismatch` for violations. This gate remains
control-only.

- [ ] **Step 6: Implement the track decisions**

Use the frozen accuracy-first comparison. Per-bit accuracy remains a reported
diagnostic and cannot override the declared exact-row/gate selection rule:

```python
def quality_key(candidate: CandidateEvidence) -> tuple[Decimal, int]:
    return (
        Decimal(candidate.visible_cv_exact),
        -candidate.gates,
    )
```

Decision logic:

```python
if rejection_reasons:
    decision = "reject"
elif blocking_reasons:
    decision = "blocked"
elif track == "disclosed_control":
    decision = "promote_control"
elif quality_key(frozen_candidate) <= max(quality_key(row) for row in baselines):
    decision = "no_change"
elif track == "synthetic":
    decision = "advance_public_candidate"
elif track == "blind_visible":
    decision = "freeze_candidate"
elif sealed_rules_pass_against_both_baselines:
    decision = "promote_blind_result"
else:
    decision = "no_change"
```

Sort all reason codes. `highest_legal_next_step` is always
`TRACK_CEILINGS[track]`, even for `blocked`, `reject`, or `no_change`.
`input_sha256` is a sorted object containing the request digest and each
resolved input's digest keyed by its request-relative path. Do not include a
timestamp, hostname, absolute path, or environment value.

- [ ] **Step 7: Run the promotion tests**

Run the Step 3 command again.

Expected: all positive, ceiling, blocked, reject, no-change, path, and
determinism tests pass.

- [ ] **Step 8: Add the repository's executable current decision**

Create `research/CURRENT_PROMOTION_REQUEST.json` with these exact canonical
bytes:

```json
{"candidate_evidence":"none","deterministic_pairs":"none","frozen_comparison":"none","official_verifications":"none","schema_version":1,"sealed_results":"none","track":"blind_visible"}
```

Generate the decision once:

```bash
uv run --default-index https://pypi.org/simple python \
  scripts/check-promotion.py \
  --request research/CURRENT_PROMOTION_REQUEST.json \
  --output research/CURRENT_PROMOTION_DECISION.json
```

Expected decision fields:

```json
{"decision":"blocked","highest_legal_next_step":"freeze_candidate","reasons":["candidate_evidence_absent","deterministic_pairs_absent","frozen_comparison_absent","official_verifications_absent"],"schema_version":1,"track":"blind_visible"}
```

The actual decision also contains `input_sha256` with the computed request
digest.

- [ ] **Step 9: Prove deterministic current output and commit**

Generate into a temporary directory and compare:

```bash
promotion_tmp=$(mktemp -d)
uv run --default-index https://pypi.org/simple python \
  scripts/check-promotion.py \
  --request research/CURRENT_PROMOTION_REQUEST.json \
  --output "$promotion_tmp/decision.json"
cmp research/CURRENT_PROMOTION_DECISION.json "$promotion_tmp/decision.json"
```

Expected: `cmp` is silent and exits `0`.

Add
`test_committed_current_request_reproduces_committed_blocked_decision` to
`scripts/tests/test_check_promotion.py`. It resolves the repository root,
invokes the checker on `research/CURRENT_PROMOTION_REQUEST.json` with a
temporary output, compares exact bytes with
`research/CURRENT_PROMOTION_DECISION.json`, and asserts
`decision == "blocked"` and
`highest_legal_next_step == "freeze_candidate"`.

```bash
git add scripts/check-promotion.py \
  scripts/tests/test_check_promotion.py \
  research/CURRENT_PROMOTION_REQUEST.json \
  research/CURRENT_PROMOTION_DECISION.json
git diff --cached --check
git commit -m "feat: enforce evidence-track promotion ceilings"
```

---

### Task 5: Define and validate the canonical deliverable model

**Files:**
- Create: `scripts/report_model.py`
- Create: `scripts/check-deliverable.py`
- Create: `scripts/tests/test_report_model.py`
- Create: `scripts/tests/test_check_deliverable.py`

**Interfaces:**
- Produces `load_project(source: Path, repo_root: Path) ->
  tuple[dict[str, object], str]`, where the second item is the source SHA-256.
- Produces `validate_project(project: dict[str, object], repo_root: Path) ->
  list[str]`, returning sorted unique error strings.
- Produces `render_outputs(project: dict[str, object], source_digest: str,
  generator_digest: str) -> dict[str, bytes]`.
- Produces `check_deliverable(source: Path, repo_root: Path) -> list[str]`.
- Exact generated output keys:
  `reports/site/index.html`, `reports/site/methods.html`,
  `reports/site/verification.html`, `reports/site/experiments.html`,
  `reports/site/assets/report.css`, `reports/site/assets/report.js`,
  `docs/STATUS.md`, `docs/METHODS.md`, `docs/EXPERIMENT_INDEX.md`,
  `research/EVIDENCE_LEDGER.md`.

- [ ] **Step 1: Write schema and claim-safety tests**

Use this exact top-level schema:

```python
PROJECT_FIELDS = {
    "schema_version",
    "project",
    "controls",
    "methods",
    "experiments",
    "claims",
    "verification_layers",
    "commands",
    "external_references",
}
PROJECT_INFO_FIELDS = {
    "title",
    "purpose",
    "conclusion",
    "next_gate",
}
EVIDENCE_FIELDS = {"kind", "label", "locator", "revision"}
```

Record fields:

```python
CONTROL_FIELDS = {
    "control_id", "instance", "function", "gates", "status",
    "limitation", "evidence",
}
METHOD_FIELDS = {
    "method_id", "title", "status", "scope", "summary", "insights",
    "optimization", "stop_rules", "limitations", "evidence",
}
EXPERIMENT_FIELDS = {
    "experiment_id", "title", "track", "status", "location", "outcome",
    "decision", "limitations", "evidence",
}
CLAIM_FIELDS = {
    "claim_id", "track", "status", "summary", "evidence", "limitations",
    "missing_proof",
}
LAYER_FIELDS = {
    "layer_id", "title", "authority", "meaning", "current_state", "command",
}
COMMAND_FIELDS = {"command_id", "title", "command", "scope"}
REFERENCE_FIELDS = {"reference_id", "title", "url", "use"}
```

All IDs, titles, summaries, scopes, outcomes, decisions, and locations are
nonempty strings. `evidence` is a nonempty list of exact evidence-reference
objects. `insights`, `optimization`, `stop_rules`, `limitations`, and
`missing_proof` are lists of nonempty strings. `gates` is a nonnegative JSON
integer, never a Boolean. `schema_version` is integer `1`.

Add one parameterized invalid-project test whose case table contains:

```python
INVALID_CASES = (
    ("missing-project-key", "exact keys"),
    ("duplicate-method-id", "duplicate method_id"),
    ("unknown-track", "invalid track"),
    ("unknown-status", "invalid status"),
    ("wrong-control-count", "mystery-A must use 37 gates"),
    ("missing-limitation", "limitation must not be empty"),
    ("unsafe-url", "https URL"),
    ("short-commit", "40 lowercase hex"),
    ("missing-path", "tracked evidence path"),
    ("duplicate-json-key", "duplicate JSON key"),
    ("forbidden-proposer-key", "forbidden proposer-facing key"),
    ("blind-success-without-sealed-proof", "sealed promotion decision"),
    ("official-pass-without-record", "official-verification.json"),
)
```

For every case, mutate a deep copy of the valid fixture, serialize it
canonically except for `duplicate-json-key`, call `load_project`, and assert
the displayed diagnostic fragment. A separate test sets the conclusion to
`<script>alert("evidence")</script>` and proves the model loader preserves that
literal string for renderer escaping.

- [ ] **Step 2: Verify model tests are red**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  scripts/tests/test_report_model.py
```

Expected: import fails because `scripts/report_model.py` is missing.

- [ ] **Step 3: Implement exact enum and evidence validation**

Use:

```python
TRACKS = {
    "disclosed_control",
    "synthetic",
    "blind_visible",
    "sealed_confirmation",
}
STATUSES = {
    "verified_main",
    "verified_branch_only",
    "rejected",
    "proposed",
    "blocked",
    "absent",
}
EVIDENCE_KINDS = {"path", "commit", "command", "test", "url"}
CONTROL_GATES = {
    "mystery-A": ("x+y", 37),
    "mystery-B": ("abs(x-y)", 49),
    "mystery-C": ("x*y", 168),
    "mystery-D": ("x²+y²", 127),
}
```

Every evidence reference has uniform keys. Enforce:

```text
kind=path    -> revision=main, locator is a Git-tracked existing regular file
kind=commit  -> revision is one lowercase 40-hex SHA, locator is safe relative
kind=command -> revision=none, locator is one nonempty command string
kind=test    -> revision=main, locator is one nonempty test selector
kind=url     -> revision=none, locator is an https URL without credentials
```

Require all non-`verified_main` claims, methods, and experiments to have a
nonempty limitation. Reject a `verified_main` sealed-confirmation claim unless
its evidence includes a tracked path to a canonical sealed promotion decision.
Reject a `verified_main` summary that claims official-verifier pass unless its
path evidence includes a canonical `official-verification.json` with
`status="pass"`.

- [ ] **Step 4: Run schema tests**

Run the Step 2 command again.

Expected: all model tests pass.

- [ ] **Step 5: Write deliverable freshness and link tests**

In `scripts/tests/test_check_deliverable.py`, test:

```text
missing source
noncanonical source
missing generated output
one-byte generated drift
broken local href
external runtime stylesheet
external runtime script
missing viewport
missing print stylesheet
missing visible focus style
missing generated-file marker
wrong embedded source digest
fresh exact output map
```

The test fixture must monkeypatch only `report_model.render_outputs`; it must
not weaken project schema validation.

- [ ] **Step 6: Verify checker tests are red**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  scripts/tests/test_check_deliverable.py
```

Expected: import or subprocess failure because
`scripts/check-deliverable.py` is missing.

- [ ] **Step 7: Implement deliverable checking**

`check_deliverable` must:

```python
project, digest = report_model.load_project(source, repo_root)
generator_digest = hashlib.sha256(
    (repo_root / "scripts/report_model.py").read_bytes()
).hexdigest()
expected = report_model.render_outputs(project, digest, generator_digest)
```

Then compare every expected byte string with the committed path, reject extra
generated site HTML/assets not in `OUTPUT_PATHS`, parse HTML with a standard
library `HTMLParser` subclass, and enforce:

```text
all local href/src targets exist
no http(s) stylesheet or script src
one meta viewport
one skip link
one main landmark
CSS contains @media print and :focus-visible
each HTML and generated Markdown file contains the project source digest
each HTML and generated Markdown file contains the report-model digest
each generated Markdown file begins <!-- GENERATED; DO NOT EDIT
```

The CLI accepts optional `--source` and `--repo-root`, defaulting to
`reports/data/project.json` and the repository root. It prints sorted errors to
stderr and exits `1`, or prints
`deliverable check: pass (10 generated files)` and exits `0`.

- [ ] **Step 8: Run checker tests and commit the model**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  scripts/tests/test_report_model.py \
  scripts/tests/test_check_deliverable.py
```

Expected: both suites pass using temporary report fixtures.

```bash
git add scripts/report_model.py \
  scripts/check-deliverable.py \
  scripts/tests/test_report_model.py \
  scripts/tests/test_check_deliverable.py
git diff --cached --check
git commit -m "feat: validate canonical deliverable evidence"
```

---

### Task 6: Build the original offline report and generated Markdown

**Files:**
- Create: `scripts/build-report.py`
- Create: `scripts/tests/test_build_report.py`
- Create: `reports/data/project.json`
- Create: `reports/README.md`
- Create: `reports/site/index.html`
- Create: `reports/site/methods.html`
- Create: `reports/site/verification.html`
- Create: `reports/site/experiments.html`
- Create: `reports/site/assets/report.css`
- Create: `reports/site/assets/report.js`
- Create: `docs/STATUS.md`
- Create: `docs/METHODS.md`
- Create: `docs/EXPERIMENT_INDEX.md`
- Create: `research/EVIDENCE_LEDGER.md`
- Modify: `scripts/report_model.py`

**Interfaces:**
- Consumes the schema frozen in Task 5 and the current blocked promotion
  request/decision from Task 4.
- Produces one deterministic `dict[str, bytes]` with ten generated files and
  no filesystem-dependent ordering, timestamp, absolute path, or environment
  value.
- CLI:
  `python scripts/build-report.py --source reports/data/project.json
  --repo-root .`.

- [ ] **Step 1: Write renderer tests before renderer code**

Add tests for:

```python
def test_render_outputs_is_deterministic_and_escapes_content(valid_project) -> None:
    project = copy.deepcopy(valid_project)
    project["project"]["conclusion"] = '<script>alert("x")</script>'
    first = report_model.render_outputs(project, "a" * 64, "c" * 64)
    second = report_model.render_outputs(project, "a" * 64, "c" * 64)
    assert first == second
    assert set(first) == report_model.OUTPUT_PATHS
    assert b"<script>alert" not in first["reports/site/index.html"]
    assert b"&lt;script&gt;alert" in first["reports/site/index.html"]


def test_every_page_has_navigation_digest_responsive_and_print_hooks(
    valid_project,
) -> None:
    outputs = report_model.render_outputs(
        valid_project,
        "b" * 64,
        "d" * 64,
    )
    for path in (
        "reports/site/index.html",
        "reports/site/methods.html",
        "reports/site/verification.html",
        "reports/site/experiments.html",
    ):
        page = outputs[path]
        assert b'<meta name="viewport"' in page
        assert b'class="skip-link"' in page
        assert b"<main" in page
        assert b"b" * 64 in page
        assert b"d" * 64 in page
        assert b"assets/report.css" in page
        assert b"assets/report.js" in page
```

Add CLI tests proving a first generation succeeds, a second generation writes
identical bytes, a missing parent fails closed, and a symlinked output is
rejected.

- [ ] **Step 2: Verify renderer tests are red**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  scripts/tests/test_build_report.py
```

Expected: failure because `render_outputs` and `scripts/build-report.py` are
not implemented.

- [ ] **Step 3: Implement semantic page rendering**

Import `escape` with `from html import escape` and call
`escape(value, quote=True)` for every model string.
Build each page through:

```python
def html_page(
    *,
    title: str,
    active: str,
    source_digest: str,
    generator_digest: str,
    body: str,
) -> bytes:
    navigation = "".join(
        nav_link(path, label, active)
        for path, label in (
            ("index.html", "Status"),
            ("methods.html", "Methods"),
            ("verification.html", "Verification"),
            ("experiments.html", "Experiments"),
        )
    )
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"  <title>{escape(title)}</title>\n"
        '  <link rel="stylesheet" href="assets/report.css">\n'
        "</head>\n"
        "<body>\n"
        '  <a class="skip-link" href="#content">Skip to content</a>\n'
        f"  <header><nav aria-label=\"Report\">{navigation}</nav></header>\n"
        f'  <main id="content">{body}</main>\n'
        "  <footer>"
        f"Evidence source SHA-256: <code>{source_digest}</code>; "
        f"report model SHA-256: <code>{generator_digest}</code>"
        "</footer>\n"
        '  <script src="assets/report.js"></script>\n'
        "</body>\n"
        "</html>\n"
    ).encode("utf-8")
```

The four bodies must contain:

```text
index: conclusion, control/blind split, gate table, evidence-level cards,
       blockers, next ratified gate, exact command links
methods: mainline methods, branch-only lessons, optimization directions,
         stop rules, evidence links
verification: five-layer ladder, Rust-vs-Julia distinction, runner statuses,
              record command, promotion command, unavailable checks
experiments: status/track/location/outcome/decision/limitations/evidence table
```

Do not render a dynamic public leaderboard or infer a family label.

- [ ] **Step 4: Implement original local assets**

`report.css` must define:

```css
:root {
  color-scheme: light;
  --ink: #172033;
  --muted: #526078;
  --paper: #f7f4ed;
  --panel: #ffffff;
  --line: #c8d0dc;
  --accent: #0b6e69;
  --accent-strong: #064e4a;
  --blocked: #9a4d00;
  --absent: #6b7280;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  color: var(--ink);
  background: var(--paper);
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
  line-height: 1.55;
}
.skip-link { position: absolute; left: -9999px; }
.skip-link:focus { left: 1rem; top: 1rem; z-index: 10; }
a:focus-visible, button:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
}
main, header, footer { width: min(1120px, calc(100% - 2rem)); margin-inline: auto; }
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; background: var(--panel); }
th, td { padding: .7rem; border: 1px solid var(--line); text-align: left; }
code { overflow-wrap: anywhere; }
header { padding-block: 1rem; }
nav { display: flex; flex-wrap: wrap; gap: .5rem; }
nav a { padding: .45rem .7rem; border-radius: .4rem; }
nav a[aria-current="page"] {
  color: #fff;
  background: var(--accent-strong);
}
.hero { padding: 3rem 0 1.5rem; }
.hero p { max-width: 72ch; color: var(--muted); font-size: 1.1rem; }
section { margin-block: 2rem; }
.card, .method-card {
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: .65rem;
  background: var(--panel);
}
.method-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}
.status {
  display: inline-block;
  padding: .15rem .45rem;
  border: 1px solid currentColor;
  border-radius: 999px;
  font-size: .85rem;
  font-weight: 700;
}
.status-blocked { color: var(--blocked); }
.status-absent { color: var(--absent); }
pre {
  padding: 1rem;
  overflow-x: auto;
  border-radius: .5rem;
  color: #fff;
  background: var(--ink);
}
button {
  padding: .45rem .7rem;
  border: 1px solid var(--accent);
  border-radius: .4rem;
  color: var(--accent-strong);
  background: var(--panel);
}
footer { padding-block: 2rem; color: var(--muted); }
@media (max-width: 760px) {
  .cards { grid-template-columns: 1fr; }
  .method-grid { grid-template-columns: 1fr; }
  th, td { padding: .5rem; }
}
@media print {
  nav, .skip-link, script { display: none !important; }
  body { background: #fff; color: #000; }
  a { color: inherit; text-decoration: none; }
  .cards { grid-template-columns: 1fr 1fr; }
}
```

`report.js` is exactly a progressive enhancement that marks the active
evidence filter and never fetches data:

```javascript
"use strict";
for (const button of document.querySelectorAll("[data-status-filter]")) {
  button.addEventListener("click", () => {
    const wanted = button.dataset.statusFilter;
    for (const row of document.querySelectorAll("[data-status]")) {
      row.hidden = wanted !== "all" && row.dataset.status !== wanted;
    }
    for (const peer of document.querySelectorAll("[data-status-filter]")) {
      peer.setAttribute("aria-pressed", String(peer === button));
    }
  });
}
```

- [ ] **Step 5: Implement generated Markdown**

Every Markdown file begins:

```markdown
<!-- GENERATED; DO NOT EDIT. Source: reports/data/project.json SHA-256: {source_digest}; report model SHA-256: {generator_digest} -->
```

Render:

```text
docs/STATUS.md -> current answer, evidence tracks, blockers, next gate
docs/METHODS.md -> method, insight, optimization, stop-rule table
docs/EXPERIMENT_INDEX.md -> experiment, track, status, location, decision table
research/EVIDENCE_LEDGER.md -> claim, evidence, limitations, missing-proof sections
```

Use repository-relative Markdown links for path evidence, commit text plus
historical path for commit evidence, fenced shell blocks for commands, and
ordinary HTTPS links for external references.

For HTML rendered under `reports/site/`, a `kind=path` evidence locator such as
`src/main.rs` becomes the URL-quoted local href `../../src/main.rs`. Commit
evidence renders the full revision and historical path as text; URL evidence
uses its validated HTTPS locator. No evidence link is constructed from an
absolute filesystem path.

- [ ] **Step 6: Author the canonical project evidence**

Create `reports/data/project.json` in canonical sorted-key form with:

```text
project.title = BooleanRazor
project.purpose = Learn and synthesize small exact Boolean circuits while
  preserving a strict evidence boundary between disclosed controls,
  synthetic development, visible blind selection, and sealed confirmation.
project.conclusion = Blind advantage has not been demonstrated because the
  claim-grade public and sealed evaluations have not occurred.
project.next_gate = Integrate the verified infrastructure, obtain the
  content-addressed public bundle through the custodian boundary, then run the
  frozen baseline and visible-only candidate matrix before any sealed access.
```

Controls are exactly:

| control_id | instance | function | gates | status |
| --- | --- | --- | ---: | --- |
| `control-a` | `mystery-A` | `x+y` | 37 | `verified_main` |
| `control-b` | `mystery-B` | `abs(x-y)` | 49 | `verified_main` |
| `control-c` | `mystery-C` | `x*y` | 168 | `verified_main` |
| `control-d` | `mystery-D` | `x²+y²` | 127 | `verified_main` |

Each limitation says it is a disclosed control, not a blind recovery or
minimality proof. Each cites its circuit path, prediction path, and
`tests/official_v1.rs`.

Methods must include these IDs and statuses:

```text
truth-table-xag          verified_main
arithmetic-controls     verified_main
complemented-robdd      verified_main
care-bdd                verified_main (synthetic/internal evidence scope)
bounded-sat             verified_main (tool evidence scope)
oxidd-oracle            verified_main (oracle-only scope)
bounded-runner          verified_main
official-julia-wrapper  verified_main (wrapper infrastructure)
tensor-network-pilot    verified_branch_only
```

Experiments and exact historical revisions:

```text
disclosed-v1-controls   verified_main
v1-julia-differential   verified_branch_only
  41518ce876b9c2a5939a525e538473165765203c
fair-order-r1            rejected
  d019a3dc3d5afe1aef76a25f266afe27f9d66c6e
greedy-conflict-r1       verified_branch_only
  7ac3c3ba2430ed787bab5ca215c259e259fa1fb5
tn-pilot                 verified_branch_only
  96429f981170766575fd167713a528078f297d67
public-baselines         blocked
blind-visible-study      blocked
sealed-confirmation      absent
```

Record the fair scheduler as deterministic but tied and rejected. Record
GreedyExactConflict as synthetic `36084 -> 34917` gates with exact-row CV
still `0 / 104857`, advancing only to public-candidate consideration. Record
TN as a deterministic synthetic pipeline only. Record the Julia run as
historical disclosed-v1 evidence bound to its branch source, not a fresh
current-HEAD record.

Claims must explicitly state:

```text
control gate counts are verified constructive upper bounds
mainline exact infrastructure is implemented
internal equivalence is not official verification
historical Julia evidence applies only to disclosed v1
synthetic branch outcomes do not establish blind accuracy
public baseline rows are absent
visible blind result is blocked
sealed confirmation and blind advantage are absent
```

Verification layers are exactly:

| layer_id | authority | current_state |
| --- | --- | --- |
| `training-consistency` | visible rows | implemented |
| `internal-equivalence` | Rust exhaustive XAG evaluation | implemented |
| `deterministic-rerun` | byte-identical fresh artifacts | implemented for disclosed controls; required per blind candidate |
| `official-julia` | official Julia verifier | wrapper integrated; current blind record absent |
| `sealed-evaluator` | frozen custodian/evaluator boundary | absent |

Command records use these exact shell strings, with the named environment
variables documented in each record's `scope`:

```text
make setup
make skills
make test

cargo run --locked --release --bin occam-circuit-hmyuuu -- \
  solve-v1 "$DATA_ROOT" "$OUTPUT_ROOT"

cargo run --locked --release --bin occam-circuit-hmyuuu -- \
  frozen-baseline "$PUBLIC_ROOT" "$OPAQUE_ID" "$OUTPUT_DIR" \
  --method zero-fill --metrics-json "$OUTPUT_DIR/metrics.json"

cargo run --locked --release --bin occam-circuit-hmyuuu -- \
  learn-care "$PUBLIC_ROOT" "$OPAQUE_ID" "$OUTPUT_DIR" \
  --folds 5 --seed "$ALGORITHM_SEED" --policy reuse-sibling \
  --max-order-evals 32

cargo run --locked --all-features --release \
  --bin occam-circuit-hmyuuu -- \
  resynthesize "$INPUT_CIRCUIT" "$OUTPUT_DIR" \
  --max-cut-inputs 6 --deadline-seconds 285 \
  --metrics-json "$OUTPUT_DIR/metrics.json"

python "$REPO_ROOT/scripts/run-experiment.py" \
  --run-root "$RUN_ROOT" --cell-id "$CELL_ID" \
  --metrics-json "$RUN_ROOT/cells/$CELL_ID/metrics.json" -- \
  "$REPO_ROOT/target/release/occam-circuit-hmyuuu" \
  learn-care "$PUBLIC_ROOT" "$OPAQUE_ID" \
  "$RUN_ROOT/cells/$CELL_ID" --folds 5 \
  --seed "$ALGORITHM_SEED" --policy reuse-sibling --max-order-evals 32

"$REPO_ROOT/scripts/verify-julia.sh" \
  "$JULIA_BIN" "$VERIFY_JL" "$CIRCUIT" "$DATASET" \
  "$EXPECTED_GATES" "$INSTANCE"

python "$REPO_ROOT/scripts/record-verification.py" \
  --manifest "$MANIFEST" --julia-bin "$JULIA_BIN" \
  --verify-jl "$VERIFY_JL" --dataset "$DATASET" \
  --output "$OFFICIAL_RECORD"

python "$REPO_ROOT/scripts/check-promotion.py" \
  --request "$PROMOTION_REQUEST" --output "$PROMOTION_DECISION"

make report
make report-check
```

External references include:

```text
https://github.com/LiuZY613/quantum.harness/commit/3ed4239e4ce1b6605e20ed5e7702996bac94697a
targeted historical path =
  tracks/qcs/solutions/kskbl-zdjd/report/report.json
use = structured-content/static-render information architecture reference
  only; no source, style, result, circuit, or claim copied
```

- [ ] **Step 7: Implement the build CLI and report README**

`scripts/build-report.py` must parse `--source` and `--repo-root`, call
`load_project`, hash exact `scripts/report_model.py` bytes, pass both digests
to `render_outputs`, reject a symlink or non-directory parent, and atomically
replace each generated regular file only after all output bytes have been
computed. It prints generated paths in sorted order.

`reports/README.md` contains:

````markdown
# BooleanRazor report

`data/project.json` is the only hand-edited report content. The HTML site and
the four concise Markdown indexes are generated and must not be edited by
hand.

```bash
make report
make report-check
python3 -m http.server 8765 --directory reports/site
```

The report is offline-first: it uses no CDN, tracker, external font, runtime
fetch, public benchmark mount, or sealed evidence.
````

- [ ] **Step 8: Run the renderer tests**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  scripts/tests/test_build_report.py \
  scripts/tests/test_report_model.py \
  scripts/tests/test_check_deliverable.py
```

Expected: all report model, render, CLI, security, and freshness fixture tests
pass.

- [ ] **Step 9: Generate and check the committed deliverable**

Run:

```bash
uv run --default-index https://pypi.org/simple python \
  scripts/build-report.py \
  --source reports/data/project.json \
  --repo-root .
uv run --default-index https://pypi.org/simple python \
  scripts/check-deliverable.py \
  --source reports/data/project.json \
  --repo-root .
```

Expected: ten paths are generated and the checker prints one pass line.

- [ ] **Step 10: Commit the report as one reproducible unit**

```bash
git add scripts/build-report.py \
  scripts/tests/test_build_report.py \
  scripts/report_model.py \
  reports/data/project.json \
  reports/README.md \
  reports/site \
  docs/STATUS.md \
  docs/METHODS.md \
  docs/EXPERIMENT_INDEX.md \
  research/EVIDENCE_LEDGER.md
git diff --cached --check
git commit -m "feat: publish deterministic evidence-first report"
```

---

### Task 7: Package optimization and promotion methods as repository skills

**Files:**
- Create: `skills/exact-circuit-optimization/SKILL.md`
- Create: `skills/exact-circuit-optimization/references/evidence-contract.md`
- Create: `skills/exact-circuit-optimization/references/method-map.md`
- Create: `skills/circuit-evidence-promotion/SKILL.md`
- Create: `skills/circuit-evidence-promotion/references/promotion-workflow.md`
- Create: `skills/circuit-evidence-promotion/references/claim-language.md`
- Modify: `Ion.toml`

**Interfaces:**
- Produces skill `exact-circuit-optimization` for designing and stopping a
  fresh optimization hypothesis without weakening the evidence contract.
- Produces skill `circuit-evidence-promotion` for validating an existing
  result, creating an official verification record, requesting a bounded
  decision, and updating claims at the permitted level.

- [ ] **Step 1: Invoke the skill-creation workflow**

Before editing these files, explicitly invoke the available `skill-creator`
skill and follow its validation requirements. Keep the two skills focused;
shared BooleanRazor rules belong in references, not duplicated long prose in
both `SKILL.md` files.

- [ ] **Step 2: Write skill-content tests through Ion's validator**

Add both registrations to `Ion.toml` only after first running:

```bash
ion --json validate
```

Expected before creation: the repository still validates, but neither new
skill appears in the validated skill inventory.

- [ ] **Step 3: Author `exact-circuit-optimization`**

Its frontmatter is:

```yaml
---
name: exact-circuit-optimization
description: Use when proposing, implementing, or evaluating a BooleanRazor circuit-optimization hypothesis under the exact accuracy-first XAG evidence contract.
---
```

Its required workflow is:

```text
1. Classify disclosed_control, synthetic, blind_visible, or sealed_confirmation.
2. Record branch, full HEAD, clean status, parent, hypothesis, independent
   variable, permitted data, frozen controls, failure signal, and stop rule.
3. Create one fresh worktree and root LOG.md; never reuse a hypothesis tree.
4. Write the strict failing test before changing the method.
5. Preserve training consistency and exhaustive completed-table equivalence.
6. Apply the frozen design comparator: rank exact-row accuracy, then reachable
   challenge-native XAG gates; report bit accuracy as diagnostic only. Free
   negation never receives a gate.
7. Treat SAT Timeout/Unknown as censored, never UNSAT.
8. Keep OxiDD as an oracle, not the production learner.
9. Run two fresh deterministic artifact builds.
10. Stop on contract drift, inequivalence, nondeterminism, two successive
    Timeout/Unknown outcomes at one bound, or no strict accuracy-first gain.
11. Preserve equal, worse, failed, and timed-out evidence with an honest
    decision.
12. Hand the result to circuit-evidence-promotion; do not self-promote.
```

`method-map.md` records mainline method roles and the exact fair, greedy, TN,
and historical Julia branch outcomes/revisions from Task 6. It labels every
branch item non-promoted.

- [ ] **Step 4: Author `circuit-evidence-promotion`**

Its frontmatter is:

```yaml
---
name: circuit-evidence-promotion
description: Use when moving a BooleanRazor result through runner validation, official Julia verification, freeze, promotion, and report updates without exceeding its evidence track.
---
```

Its required workflow is:

```text
1. Choose the evidence track and state its maximum positive decision.
2. Run research/check_gate.py against the frozen expected design and native run.
3. Require a candidate-bearing runner state and transitive artifact hashes.
4. Pair deterministic manifests and compare byte-identical table/circuit/index.
5. Run record-verification.py with absolute non-symlink paths.
6. Create one canonical promotion request rooted beside its evidence.
7. Run check-promotion.py and preserve the immutable decision.
8. Interpret blocked as missing proof, reject as violated eligibility,
   no_change as valid-but-not-strictly-better, and positive decisions only at
   the track ceiling.
9. Regenerate and check the report.
10. Update a leaderboard only when its own evidence gate permits it.
```

`claim-language.md` gives exact permitted phrases:

```text
disclosed control: verified constructive upper bound; not blind; not minimality
synthetic: internal/synthetic evidence; may advance to public candidate
blind visible: visible-only frozen candidate; no sealed-performance claim
sealed confirmation: promoted blind result only after positive sealed decision
blocked: required evidence is absent or unavailable
not demonstrated: claim-grade evaluation has not occurred
```

- [ ] **Step 5: Register and validate both skills**

Add under the research workflow section of `Ion.toml`:

```toml
exact-circuit-optimization = { type = "local" }
circuit-evidence-promotion = { type = "local" }
```

Run:

```bash
make skills
```

Expected: zero validation errors; pre-existing warnings may remain unchanged.

- [ ] **Step 6: Commit the reusable methods**

```bash
git add Ion.toml \
  skills/exact-circuit-optimization \
  skills/circuit-evidence-promotion
git diff --cached --check
git commit -m "feat: package circuit optimization and promotion skills"
```

---

### Task 8: Rewrite contributor navigation around evidence and verifier decisions

**Files:**
- Rewrite: `AGENTS.md`
- Modify: `README.md`
- Modify: `autoresearch/README.md`
- Modify: `reblind/README.md`
- Modify: `docs/handoff/SESSION_HANDOFF.md`
- Modify: `docs/plans/2026-07-23-occam-circuit-rust-bdd-tn.md:2845-2868`
- Modify: `docs/plans/2026-07-23-occam-circuit-rust-bdd-tn.md:3168-3173`

**Interfaces:**
- Consumes generated `docs/STATUS.md`, `docs/METHODS.md`,
  `docs/EXPERIMENT_INDEX.md`, and `research/EVIDENCE_LEDGER.md`.
- Produces one command/status vocabulary across agent instructions, public
  README, experiment README, reblind boundary, handoff, and ratified plan.

- [ ] **Step 1: Add navigation assertions**

Extend `autoresearch/test_autoresearch_protocol.py` or add focused assertions
to `scripts/tests/test_check_deliverable.py` requiring these phrases in the
named files:

```python
required = {
    "AGENTS.md": (
        "Current answer",
        "Choose the activity",
        "Choose the evidence track",
        "Verification ladder",
        "Promotion state machine",
        "VERIFIER_NOT_RUN",
        "absolute paths",
        "make report-check",
    ),
    "README.md": (
        "reports/site/index.html",
        "Internal exhaustive equivalence",
        "Official Julia verification",
        "Blind advantage has not been demonstrated",
    ),
    "autoresearch/README.md": (
        "autoresearch/LOG_TEMPLATE.md",
        "child runs in its cell directory",
        "absolute",
    ),
    "reblind/README.md": (
        "learn-care",
        "record-verification.py",
        "freeze_candidate",
        "promote_blind_result",
    ),
}
```

Also assert the stale path
`tracks/qcs/solutions/hmyuuu/autoresearch/LOG_TEMPLATE.md` and stale runner
flags `--experiment-id`/`--results-root` no longer appear in active command
examples.

- [ ] **Step 2: Verify navigation assertions are red**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  autoresearch/test_autoresearch_protocol.py \
  scripts/tests/test_check_deliverable.py \
  -k 'navigation or standalone or documentation'
```

Expected: failures name the stale path and missing verifier/promotion
navigation.

- [ ] **Step 3: Rewrite `AGENTS.md` as a decision router**

Use exactly these top-level sections:

```markdown
# BooleanRazor Agent Guide
## Current answer
## First actions
## Choose the activity
## Choose the evidence track
## Data-access gate
## Candidate routes
## Verification ladder
## Runner rules
## Promotion state machine
## HPC gate
## Report and documentation updates
## Repository map
```

`Current answer` links to the four generated Markdown views and states:

```text
Verified main: disclosed controls and exact core/infrastructure.
Verified branch-only: historical v1 Julia run, GreedyExactConflict, TN pilot.
Rejected: fair scheduler as a quality improvement.
Blocked/absent: public baseline results, visible freeze, sealed confirmation,
and blind advantage.
```

The verification ladder is exactly:

```text
visible training consistency
-> artifact.json equivalence=pass
-> byte-identical deterministic rerun
-> official-verification.json status=pass
-> sealed evaluator/frozen analysis decision when the track requires it
```

The runner table maps:

```text
SUCCESS           candidate retained, official verifier pass, runner success
VERIFIER_NOT_RUN  candidate retained, verifier absent, runner failure code 67
VERIFIER_FAILED   candidate retained, verifier failed, runner failure code 66
other terminal    no candidate-quality/artifact claim
```

State that runner children execute in the cell directory, so repository
binary, manifest, public root, helper, output, and metrics arguments in child
commands must be absolute.

- [ ] **Step 4: Expand the root README**

Keep the control table, then add:

```text
Current scientific answer and missing proof
architecture map: Rust exact core -> runner -> Julia record -> promotion
report link and make report/report-check
command matrix for solve-v1, baseline, care, SAT, runner, Julia, record,
promotion, and tests
verification-level table separating internal and external checks
main/branch-only/blocked status table
```

The first report link is
`reports/site/index.html`; do not link to an external deployed copy.

- [ ] **Step 5: Correct autoresearch and reblind commands**

In `autoresearch/README.md`, the worktree log copy becomes:

```bash
experiment_id=${1:?supply an opaque experiment ID}
cp autoresearch/LOG_TEMPLATE.md \
  "../booleanrazor-exp-${experiment_id}/LOG.md"
```

Add a native runner example that first resolves:

```bash
repo_root=$(git rev-parse --show-toplevel)
run_id=${2:?supply a frozen run ID}
run_root="$repo_root/results/$run_id"
```

and passes absolute `--run-root`, `--metrics-json`, binary, public root, and
output paths. Explicitly explain the child `cwd`.

In `reblind/README.md`, add the exact `learn-care` command from `src/main.rs`
usage, then the absolute `record-verification.py` command and the maximum
visible/sealed decisions `freeze_candidate` and `promote_blind_result`.

- [ ] **Step 6: Reconcile handoff and only materially stale plan text**

Rewrite the handoff to:

```text
main includes the exact core, public importer, care/SAT tools, runner,
truthful verifier semantics, wrapper, record, promotion, report, and skills
branch-only fair/greedy/TN/Julia history is evidence, not merged algorithms
public bundle remains absent
current promotion decision is blocked
next safe step is integration verification, then public acquisition through
the custodian boundary
HPC remains unauthorized
```

In the active plan, replace lines 2852-2868 with the current native runner
shape using `--run-root`, `--cell-id`, `--metrics-json`, `--`, and absolute
child paths. At Task 15 lines 3170-3173, state that the reviewed wrapper,
immutable record tool, and promotion checker are integrated by the
deliverability work; the real disclosed-v1 Julia execution remains historical
branch evidence rather than a fresh current-HEAD record; public/sealed
evaluation and a final blind decision remain absent. Do not rewrite the
historical task body or claim that absent Task 15 result artifacts exist.

- [ ] **Step 7: Run navigation tests and report freshness**

Run:

```bash
uv run --default-index https://pypi.org/simple pytest -q \
  autoresearch/test_autoresearch_protocol.py \
  scripts/tests/test_check_deliverable.py
uv run --default-index https://pypi.org/simple python \
  scripts/check-deliverable.py \
  --source reports/data/project.json \
  --repo-root .
```

If documentation changes alter canonical report content, update only
`reports/data/project.json`, run the generator, and rerun the checker.

- [ ] **Step 8: Commit navigation without the leaderboard**

```bash
git add AGENTS.md \
  README.md \
  autoresearch/README.md \
  reblind/README.md \
  docs/handoff/SESSION_HANDOFF.md \
  docs/plans/2026-07-23-occam-circuit-rust-bdd-tn.md \
  autoresearch/test_autoresearch_protocol.py \
  scripts/tests/test_check_deliverable.py \
  reports/data/project.json \
  reports/site \
  docs/STATUS.md \
  docs/METHODS.md \
  docs/EXPERIMENT_INDEX.md \
  research/EVIDENCE_LEDGER.md
git diff --cached --name-only
git diff --cached --check
git commit -m "docs: route contributors through evidence and verification"
```

Expected staged names do not include `docs/LEADERBOARD.md`.

---

### Task 9: Integrate report, verifier, and promotion checks into Make

**Files:**
- Modify: `Makefile`

**Interfaces:**
- Produces:
  - `make report`
  - `make report-check`
  - `make test-report`
  - `make test-verifier`
  - `make test-promotion`
- Extends `make test` without running a real Julia binary or accessing public,
  sealed, network, or cluster resources.

- [ ] **Step 1: Verify the new targets do not exist**

Run:

```bash
make help
```

Expected: `report`, `report-check`, `test-report`, `test-verifier`, and
`test-promotion` are absent.

- [ ] **Step 2: Add exact Make targets**

Extend `.PHONY` and add:

```make
report: ## Regenerate the offline HTML and Markdown deliverable
	$(UV_RUN) python scripts/build-report.py \
		--source reports/data/project.json \
		--repo-root .

report-check: ## Validate report schema, claims, links, and generated bytes
	$(UV_RUN) python scripts/check-deliverable.py \
		--source reports/data/project.json \
		--repo-root .

test-report: ## Test deterministic report generation and validation
	$(PYTEST) -q \
		scripts/tests/test_report_model.py \
		scripts/tests/test_build_report.py \
		scripts/tests/test_check_deliverable.py

test-verifier: ## Test Julia wrapper and immutable verification records
	sh -n scripts/verify-julia.sh
	$(PYTEST) -q \
		scripts/tests/test_verify_julia.py \
		scripts/tests/test_record_verification.py

test-promotion: ## Test evidence-track promotion decisions
	$(PYTEST) -q scripts/tests/test_check_promotion.py
```

Change the complete target to:

```make
test: test-python test-hpc test-rust test-protocol test-report test-verifier test-promotion report-check ## Run the complete local baseline
```

Do not add `report` as a prerequisite of `test`; tests must detect drift rather
than silently regenerate committed files.

- [ ] **Step 3: Run every new target independently**

Run:

```bash
make report-check
make test-report
make test-verifier
make test-promotion
```

Expected: all four targets pass; verifier tests use only fixture executables.

- [ ] **Step 4: Commit the build surface**

```bash
git add Makefile
git diff --cached --check
git commit -m "build: gate deliverable verifier and promotion checks"
```

---

### Task 10: Run complete acceptance verification and independent review

**Files:**
- Verify: all files changed in Tasks 1-9
- Preserve without staging: `docs/LEADERBOARD.md`

**Interfaces:**
- Consumes every task commit and the committed design at
  `docs/superpowers/specs/2026-07-30-booleanrazor-deliverability-verifier-design.md`.
- Produces fresh local proof for all acceptance criteria and a review record
  with any residual limitation stated plainly.

- [ ] **Step 1: Invoke completion and review skills**

Explicitly invoke:

```text
verification-before-completion
requesting-code-review
```

Use the first to define fresh proof and the second for an independent
spec-versus-diff review. Do not declare completion before both finish.

- [ ] **Step 2: Verify repository state and leaderboard preservation**

Run:

```bash
git status --short --branch
shasum -a 256 docs/LEADERBOARD.md
git diff -- docs/LEADERBOARD.md | shasum -a 256
```

Expected leaderboard hashes remain:

```text
78e9307b4271f828df5f919de852b52d99af34ad952c366123c744ba643b5d6f
c9ce201617ca0e1941031a69a2268aa9e668c497e0b2a6c50598e723c3eb1a3b
```

If the user changes that file during execution, preserve the user's new bytes
and document the new before/after hash rather than restoring these planning
hashes.

- [ ] **Step 3: Run focused gates**

Run:

```bash
cargo test --locked --all-features --release \
  frozen_baseline_metrics_do_not_claim_external_verification -- --nocapture
make test-verifier
make test-promotion
make test-report
make report-check
make skills
```

Expected: every command exits `0`; `make skills` reports zero errors.

- [ ] **Step 4: Run the complete local baseline**

Use the already-created environment. If the managed shared uv cache is not
readable, use the workspace-safe cache path without changing project files:

```bash
UV_CACHE_DIR=/private/tmp/booleanrazor-uv-cache make test
```

Expected:

```text
all protocol/design Python tests pass
all runner/HPC adapter tests pass
cargo fmt --check passes
all locked all-feature release Rust tests pass
the explicit 20-bit calibration remains ignored
protocol gate passes
report/verifier/promotion tests pass
report freshness passes
```

- [ ] **Step 5: Inspect the report at desktop and mobile widths**

Start a local static server:

```bash
python3 -m http.server 8765 --directory reports/site
```

Inspect all four pages at approximately `1440×900` and `390×844`. Confirm:

```text
no horizontal page overflow except deliberate table wrappers
keyboard-visible navigation and skip link
control/blind separation visible above the fold
status colors remain legible without color alone
command blocks wrap
tables remain navigable
print preview removes navigation and JavaScript controls
no network request except localhost page/assets
```

Stop the server after inspection.

- [ ] **Step 6: Review diff hygiene and forbidden content**

Run:

```bash
git diff --check
git diff --stat origin/main...HEAD
git diff --name-only origin/main...HEAD
rg -n \
  'family|generator|ground_truth|test_outputs|private_digest' \
  reports/data reports/site docs/STATUS.md docs/METHODS.md \
  docs/EXPERIMENT_INDEX.md research/EVIDENCE_LEDGER.md
```

Expected: whitespace check passes; changed names match this plan; any token
match is explanatory policy text, never a proposer-facing field or hidden
value.

- [ ] **Step 7: Run the independent review**

The reviewer must compare the complete diff with all 15 acceptance criteria in
the design and answer:

```text
Does any path still equate Rust equivalence with official verification?
Can any failed non-candidate state carry quality/artifact evidence?
Can any promotion exceed its evidence-track ceiling?
Can absent public/sealed evidence produce a positive decision?
Can report content drift from canonical JSON without make test failing?
Are branch-only results visibly branch-only?
Are every report command and runner child path operationally correct?
Did any user leaderboard byte, hidden data, result directory, dependency,
container, or remote-compute artifact enter the diff?
```

Address every Important or higher finding with a new red/green cycle and rerun
the affected focused and full gates.

- [ ] **Step 8: Record final state without overstating evidence**

The handoff and final response must state:

```text
what was implemented
fresh verification commands and outcomes
that the static report is local/offline and not deployed
that the official wrapper is integrated but no fresh current-head real-Julia
record was manufactured
that public and sealed data remain absent
that the current blind promotion decision is blocked
that blind advantage therefore remains not demonstrated
that the user's leaderboard edit remains unstaged and preserved
```

Do not mark the deliverability goal complete if any required focused test,
`make skills`, `make report-check`, complete `make test`, visual inspection, or
review gate is missing.

---

## Self-review coverage map

| Design requirement | Plan task |
| --- | --- |
| Truthful internal/external verifier semantics | Task 1 |
| Candidate evidence retained without success inflation | Task 1 |
| Reviewed Julia wrapper and adversarial tests | Task 2 |
| Immutable digest-bound verification record and race checks | Task 3 |
| Evidence-track ceilings and deterministic decisions | Task 4 |
| Current absent blind evidence produces `blocked` | Task 4 |
| Canonical report source and fail-closed claim model | Task 5 |
| Offline original HTML and generated Markdown | Task 6 |
| Methods and optimization insights packaged as skills | Task 7 |
| Operational `AGENTS.md` and verifier navigation | Task 8 |
| Root command surface and complete test integration | Task 9 |
| Fresh full proof, visual inspection, independent review | Task 10 |
| Preserve user leaderboard change and scientific/data boundaries | Global constraints and Task 10 |
