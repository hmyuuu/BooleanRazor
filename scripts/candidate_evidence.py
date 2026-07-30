"""Typed, transitive validation of native runner candidate evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from evidence_io import (
    DEFAULT_MAX_BYTES,
    HEX_64,
    MAX_ARTIFACT_BYTES,
    EvidenceError,
    load_canonical_object,
    read_stable_regular,
    resolve_evidence_path,
    sha256_bytes,
)


PARAM_FIELDS = {
    "comparison_id", "role", "method", "method_version", "blind",
    "evaluation_scope", "hardware", "dataset_id", "tier",
    "observation_fraction", "algorithm_seed", "repeat", "timeout_seconds",
}
PROVENANCE_FIELDS = {
    "source_commit", "runner_commit", "tree_digest", "image_sha256", "compiler_digest",
}
QUALITY_FIELDS = {
    "train_exact", "visible_cv_exact", "visible_cv_bit_accuracy", "gates",
    "completed_table_sha256", "circuit_sha256", "artifact_sha256", "artifact_path",
}
OPERATIONAL_FIELDS = {
    "schema_version", "producer", "run_spec_sha256", "argv", "started_utc",
    "ended_utc", "status", "exit_code", "timed_out", "elapsed_seconds",
    "cleanup_seconds", "peak_memory_kib", "verifier", "stdout_sha256",
    "stderr_sha256", "log_sha256", "scheduler_sha256", "scheduler_job_id",
    "scheduler_task_index", "scheduler_state", "scheduler_exit_code",
    "scheduler_classification", "scheduler_elapsed_seconds",
}
MANIFEST_FIELDS = PARAM_FIELDS | PROVENANCE_FIELDS | QUALITY_FIELDS | OPERATIONAL_FIELDS
ARTIFACT_FIELDS = {
    "circuit_path", "circuit_sha256", "completed_table_path",
    "completed_table_sha256", "equivalence", "schema_version",
}
CANDIDATE_STATES = {"SUCCESS", "VERIFIER_FAILED", "VERIFIER_NOT_RUN"}
TERMINAL_STATES = CANDIDATE_STATES | {"INVALID_METRICS", "NONZERO_EXIT", "TIMEOUT"}
SCHEDULER_FIELDS = {
    "scheduler_sha256", "scheduler_job_id", "scheduler_task_index", "scheduler_state",
    "scheduler_exit_code", "scheduler_classification", "scheduler_elapsed_seconds",
}
CANONICAL_INTEGER = re.compile(r"(?:0|[1-9][0-9]*)")
CANONICAL_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]+")
COMMIT_40 = re.compile(r"[0-9a-f]{40}")
RFC3339_UTC = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z"
)


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
            self.source_commit, self.tree_digest, self.dataset_id, self.method,
            self.train_exact, self.visible_cv_exact, self.visible_cv_bit_accuracy,
            self.gates, self.completed_table_sha256, self.circuit_sha256,
            self.artifact_sha256,
        )


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise EvidenceError(f"{label} must be a string")
    return value


def _require_digest(value: object, label: str) -> str:
    text = _require_string(value, label)
    if not HEX_64.fullmatch(text):
        raise EvidenceError(f"{label} must be 64 lowercase hexadecimal characters")
    return text


def _run_root_for_manifest(path: Path, comparison_id: str, evidence_root: Path | None) -> Path:
    if path.name != "manifest.json" or path.parent.name != comparison_id or path.parent.parent.name != "cells":
        raise EvidenceError("manifest must be at native cells/COMPARISON_ID/manifest.json location")
    root = evidence_root if evidence_root is not None else path.parent.parent.parent
    try:
        resolved_root = root.resolve(strict=True)
        resolved_manifest = path.resolve(strict=True)
    except OSError as exc:
        raise EvidenceError("evidence root and manifest must exist") from exc
    if resolved_manifest != resolved_root / "cells" / comparison_id / "manifest.json":
        raise EvidenceError("manifest is outside the declared evidence root")
    return root


def _check_status(manifest: dict[str, object]) -> None:
    status = _require_string(manifest["status"], "status")
    verifier = _require_string(manifest["verifier"], "verifier")
    exit_code = _require_string(manifest["exit_code"], "exit_code")
    expected = {
        "SUCCESS": ("pass", "0"),
        "VERIFIER_FAILED": ("fail", "66"),
        "VERIFIER_NOT_RUN": ("not_run", "67"),
        "INVALID_METRICS": ("not_run", "65"),
        "TIMEOUT": ("not_run", "124"),
    }
    if status == "NONZERO_EXIT":
        valid = verifier == "not_run" and CANONICAL_INTEGER.fullmatch(exit_code) and int(exit_code) > 0
    else:
        valid = status in expected and (verifier, exit_code) == expected[status]
    if not valid:
        raise EvidenceError("status, verifier, and exit_code do not have the native mapping")
    if _require_string(manifest["timed_out"], "timed_out") != ("true" if status == "TIMEOUT" else "false"):
        raise EvidenceError("timed_out does not match terminal status")


def _canonical_integer(value: object, label: str) -> int:
    text = _require_string(value, label)
    if not CANONICAL_INTEGER.fullmatch(text):
        raise EvidenceError(f"{label} must be a canonical nonnegative integer")
    return int(text)


def _canonical_decimal(value: object, label: str, *, maximum: Decimal | None = None) -> Decimal:
    text = _require_string(value, label)
    if not CANONICAL_DECIMAL.fullmatch(text):
        raise EvidenceError(f"{label} must be a canonical decimal")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise EvidenceError(f"{label} must be a canonical decimal") from exc
    if not number.is_finite() or number < 0 or (maximum is not None and number > maximum):
        raise EvidenceError(f"{label} is out of range")
    canonical = format(number.normalize(), "f")
    if "." not in canonical:
        canonical += ".0"
    if text != canonical:
        raise EvidenceError(f"{label} must be a canonical decimal")
    return number


def _canonical_timeout(value: object) -> Decimal:
    text = _require_string(value, "timeout_seconds")
    if CANONICAL_INTEGER.fullmatch(text):
        number = Decimal(text)
    else:
        number = _canonical_decimal(text, "timeout_seconds")
    if number <= 0 or number > Decimal(300):
        raise EvidenceError("timeout_seconds must be in (0,300]")
    return number


def _timestamp(value: object, label: str) -> None:
    text = _require_string(value, label)
    if not RFC3339_UTC.fullmatch(text):
        raise EvidenceError(f"{label} must be RFC3339 UTC")
    try:
        datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise EvidenceError(f"{label} must be RFC3339 UTC") from exc


def _validate_params(params: dict[str, object], cell_id: str) -> Decimal:
    if any(not isinstance(value, str) for value in params.values()):
        raise EvidenceError("run parameters must be strings")
    if params["comparison_id"] != cell_id:
        raise EvidenceError("comparison_id must match native cell directory")
    if params["role"] not in {"baseline", "candidate"}:
        raise EvidenceError("role must be baseline or candidate")
    if params["blind"] != "true" or params["evaluation_scope"] != "visible_cv_only":
        raise EvidenceError("params must preserve blind visible-CV scope")
    if not HEX_64.fullmatch(params["algorithm_seed"]):
        raise EvidenceError("algorithm_seed must be 64 lowercase hexadecimal characters")
    _canonical_integer(params["repeat"], "repeat")
    for field in PARAM_FIELDS - {"algorithm_seed", "repeat", "timeout_seconds"}:
        if params[field] == "":
            raise EvidenceError(f"{field} must be nonempty")
    return _canonical_timeout(params["timeout_seconds"])


def _validate_provenance(provenance: dict[str, object]) -> None:
    if any(not isinstance(value, str) for value in provenance.values()):
        raise EvidenceError("provenance values must be strings")
    for field in ("source_commit", "runner_commit"):
        if not COMMIT_40.fullmatch(provenance[field]):
            raise EvidenceError(f"{field} must be 40 lowercase hexadecimal characters")
    if not HEX_64.fullmatch(provenance["tree_digest"]):
        raise EvidenceError("tree_digest must be 64 lowercase hexadecimal characters")
    for field in ("image_sha256", "compiler_digest"):
        if provenance[field] != "none" and not HEX_64.fullmatch(provenance[field]):
            raise EvidenceError(f"{field} must be none or 64 lowercase hexadecimal characters")


def _validate_metrics(manifest: dict[str, object], timeout: Decimal) -> None:
    status = _require_string(manifest["status"], "status")
    if status in CANDIDATE_STATES:
        if any(manifest[field] == "none" for field in QUALITY_FIELDS):
            raise EvidenceError("candidate-bearing status lacks candidate evidence")
        if manifest["train_exact"] != "1.0":
            raise EvidenceError("candidate train_exact must equal 1.0")
        _canonical_decimal(manifest["visible_cv_exact"], "visible_cv_exact", maximum=Decimal(1))
        _canonical_decimal(
            manifest["visible_cv_bit_accuracy"], "visible_cv_bit_accuracy", maximum=Decimal(1)
        )
        _canonical_integer(manifest["gates"], "gates")
        elapsed = _canonical_decimal(manifest["elapsed_seconds"], "elapsed_seconds")
        if elapsed > timeout:
            raise EvidenceError("elapsed_seconds exceeds timeout_seconds")
        _canonical_integer(manifest["peak_memory_kib"], "peak_memory_kib")
        return
    for field in QUALITY_FIELDS:
        if manifest[field] != "none":
            raise EvidenceError("noncandidate terminal manifest must not claim candidate evidence")
    elapsed = manifest["elapsed_seconds"]
    if status == "TIMEOUT":
        if elapsed == "none" or _canonical_decimal(elapsed, "elapsed_seconds") != timeout:
            raise EvidenceError("TIMEOUT must record the declared timeout")
    elif elapsed != "none":
        if _canonical_decimal(elapsed, "elapsed_seconds") > timeout:
            raise EvidenceError("elapsed_seconds exceeds timeout_seconds")
    if manifest["peak_memory_kib"] != "none":
        _canonical_integer(manifest["peak_memory_kib"], "peak_memory_kib")


def _validate_runner_metadata(manifest: dict[str, object], timeout: Decimal) -> None:
    if not isinstance(manifest["argv"], list) or not manifest["argv"] or not all(
        isinstance(arg, str) for arg in manifest["argv"]
    ):
        raise EvidenceError("runner argv must be a nonempty string array")
    _timestamp(manifest["started_utc"], "started_utc")
    _timestamp(manifest["ended_utc"], "ended_utc")
    if any(manifest[field] != "none" for field in SCHEDULER_FIELDS):
        raise EvidenceError("runner scheduler fields must be none")
    if manifest["status"] == "TIMEOUT":
        _canonical_decimal(manifest["cleanup_seconds"], "cleanup_seconds")
    elif manifest["cleanup_seconds"] != "0.0":
        raise EvidenceError("non-timeout cleanup_seconds must equal 0.0")
    _validate_metrics(manifest, timeout)


def _frame(stdout: bytes, stderr: bytes) -> str:
    return sha256_bytes(
        len(stdout).to_bytes(8, "big") + stdout + len(stderr).to_bytes(8, "big") + stderr
    )


def load_terminal_manifest(path: Path, evidence_root: Path | None = None) -> TerminalEvidence:
    manifest, manifest_raw = load_canonical_object(path, "manifest.json")
    if set(manifest) != MANIFEST_FIELDS:
        raise EvidenceError("manifest has missing or extra fields")
    if manifest["schema_version"] != 1 or manifest["producer"] != "runner":
        raise EvidenceError("manifest must be runner schema version 1")
    for field in PARAM_FIELDS | PROVENANCE_FIELDS | {"started_utc", "ended_utc", "elapsed_seconds", "cleanup_seconds", "peak_memory_kib"}:
        _require_string(manifest[field], field)
    for field in SCHEDULER_FIELDS:
        if manifest[field] != "none":
            raise EvidenceError("runner scheduler fields must be none")
    _check_status(manifest)
    comparison_id = _require_string(manifest["comparison_id"], "comparison_id")
    root = _run_root_for_manifest(path, comparison_id, evidence_root)
    run_spec_path = root / "run_spec.json"
    spec, spec_raw = load_canonical_object(run_spec_path, "run_spec.json")
    if set(spec) != {"schema_version", "cells", "provenance"} or spec["schema_version"] != 1:
        raise EvidenceError("run_spec.json has an invalid native schema")
    if _require_digest(manifest["run_spec_sha256"], "run_spec_sha256") != sha256_bytes(spec_raw):
        raise EvidenceError("run_spec digest binding mismatch")
    if not isinstance(spec["provenance"], dict) or set(spec["provenance"]) != PROVENANCE_FIELDS:
        raise EvidenceError("run_spec provenance is invalid")
    if not isinstance(spec["cells"], list):
        raise EvidenceError("run_spec cells is invalid")
    selected: dict[str, object] | None = None
    for cell in spec["cells"]:
        if not isinstance(cell, dict) or set(cell) != {"cell_id", "params"} or cell.get("cell_id") != comparison_id:
            continue
        if selected is not None:
            raise EvidenceError("run_spec has duplicate comparison_id")
        selected = cell
    if selected is None or not isinstance(selected["params"], dict) or set(selected["params"]) != PARAM_FIELDS:
        raise EvidenceError("run_spec does not contain the manifest cell")
    timeout = _validate_params(selected["params"], comparison_id)
    _validate_provenance(spec["provenance"])
    for field in PARAM_FIELDS:
        if selected["params"][field] != manifest[field]:
            raise EvidenceError("manifest parameters disagree with run_spec")
    for field in PROVENANCE_FIELDS:
        if spec["provenance"][field] != manifest[field]:
            raise EvidenceError("manifest provenance disagrees with run_spec")
    _validate_params({field: manifest[field] for field in PARAM_FIELDS}, comparison_id)
    _validate_provenance({field: manifest[field] for field in PROVENANCE_FIELDS})
    _validate_runner_metadata(manifest, timeout)
    cell_dir = root / "cells" / comparison_id
    stdout = read_stable_regular(cell_dir / "stdout.log", "stdout.log", MAX_ARTIFACT_BYTES)
    stderr = read_stable_regular(cell_dir / "stderr.log", "stderr.log", MAX_ARTIFACT_BYTES)
    if _require_digest(manifest["stdout_sha256"], "stdout_sha256") != sha256_bytes(stdout):
        raise EvidenceError("stdout digest binding mismatch")
    if _require_digest(manifest["stderr_sha256"], "stderr_sha256") != sha256_bytes(stderr):
        raise EvidenceError("stderr digest binding mismatch")
    if _require_digest(manifest["log_sha256"], "log_sha256") != _frame(stdout, stderr):
        raise EvidenceError("combined log digest binding mismatch")
    return TerminalEvidence(
        manifest_path=path, manifest_sha256=sha256_bytes(manifest_raw), run_root=root,
        run_spec_path=run_spec_path, run_spec_sha256=sha256_bytes(spec_raw),
        comparison_id=comparison_id, source_commit=_require_string(manifest["source_commit"], "source_commit"),
        tree_digest=_require_string(manifest["tree_digest"], "tree_digest"),
        dataset_id=_require_string(manifest["dataset_id"], "dataset_id"),
        blind=_require_string(manifest["blind"], "blind"),
        evaluation_scope=_require_string(manifest["evaluation_scope"], "evaluation_scope"),
        hardware=_require_string(manifest["hardware"], "hardware"),
        timeout_seconds=_require_string(manifest["timeout_seconds"], "timeout_seconds"),
        role=_require_string(manifest["role"], "role"), method=_require_string(manifest["method"], "method"),
        status=_require_string(manifest["status"], "status"), verifier=_require_string(manifest["verifier"], "verifier"),
    )


def load_candidate_manifest(path: Path, evidence_root: Path | None = None) -> CandidateEvidence:
    terminal = load_terminal_manifest(path, evidence_root)
    if terminal.status not in CANDIDATE_STATES:
        raise EvidenceError("terminal manifest is not candidate-bearing")
    manifest, _ = load_canonical_object(path, "manifest.json")
    if manifest["train_exact"] != "1.0":
        raise EvidenceError("candidate train_exact must equal 1.0")
    gates_text = _require_string(manifest["gates"], "gates")
    if not CANONICAL_INTEGER.fullmatch(gates_text):
        raise EvidenceError("candidate gates must be a canonical decimal string")
    artifact_value = f"cells/{terminal.comparison_id}/artifact.json"
    if manifest["artifact_path"] != artifact_value:
        raise EvidenceError("candidate artifact path is not native")
    artifact_path = resolve_evidence_path(terminal.run_root, artifact_value, "artifact")
    artifact, artifact_raw = load_canonical_object(artifact_path, "artifact.json")
    if set(artifact) != ARTIFACT_FIELDS or artifact.get("schema_version") != 1:
        raise EvidenceError("artifact has missing or extra fields")
    if artifact.get("equivalence") != "pass":
        raise EvidenceError("artifact equivalence must equal pass")
    if artifact.get("circuit_path") != "circuit.txt" or artifact.get("completed_table_path") != "completed-table.csv":
        raise EvidenceError("artifact paths are not native")
    if _require_digest(manifest["artifact_sha256"], "artifact_sha256") != sha256_bytes(artifact_raw):
        raise EvidenceError("artifact digest binding mismatch")
    cell_dir = terminal.run_root / "cells" / terminal.comparison_id
    table_path = cell_dir / "completed-table.csv"
    circuit_path = cell_dir / "circuit.txt"
    table = read_stable_regular(table_path, "completed-table.csv", MAX_ARTIFACT_BYTES)
    circuit = read_stable_regular(circuit_path, "circuit.txt", MAX_ARTIFACT_BYTES)
    table_digest = sha256_bytes(table)
    circuit_digest = sha256_bytes(circuit)
    if _require_digest(artifact["completed_table_sha256"], "artifact completed_table_sha256") != table_digest:
        raise EvidenceError("artifact completed table binding mismatch")
    if _require_digest(artifact["circuit_sha256"], "artifact circuit_sha256") != circuit_digest:
        raise EvidenceError("artifact circuit binding mismatch")
    if _require_digest(manifest["completed_table_sha256"], "manifest completed_table_sha256") != table_digest:
        raise EvidenceError("manifest completed table binding mismatch")
    if _require_digest(manifest["circuit_sha256"], "manifest circuit_sha256") != circuit_digest:
        raise EvidenceError("manifest circuit binding mismatch")
    return CandidateEvidence(
        **terminal.__dict__, train_exact="1.0",
        visible_cv_exact=_require_string(manifest["visible_cv_exact"], "visible_cv_exact"),
        visible_cv_bit_accuracy=_require_string(manifest["visible_cv_bit_accuracy"], "visible_cv_bit_accuracy"),
        gates=int(gates_text), artifact_path=artifact_path,
        artifact_sha256=sha256_bytes(artifact_raw), completed_table_path=table_path,
        completed_table_sha256=table_digest, circuit_path=circuit_path,
        circuit_sha256=circuit_digest,
    )
