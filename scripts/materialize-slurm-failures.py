#!/usr/bin/env python3
"""Materialize missing runner manifests from frozen raw Slurm evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


RAW_HEADER = b"JobIDRaw|State|ExitCode|MaxRSS|ElapsedRaw\n"
CELL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
JOB_ID = re.compile(r"[1-9][0-9]*")
CANONICAL_INTEGER = re.compile(r"(?:0|[1-9][0-9]*)")
EXIT_CODE = re.compile(r"((?:0|[1-9][0-9]*)):((?:0|[1-9][0-9]*))")
RSS_KIB = re.compile(r"((?:0|[1-9][0-9]*))K")
HEX_64 = re.compile(r"[0-9a-f]{64}")
COMMIT_HASH = re.compile(r"[0-9a-f]{40}")
PARAM_FIELDS = {
    "comparison_id",
    "role",
    "method",
    "method_version",
    "blind",
    "evaluation_scope",
    "hardware",
    "dataset_id",
    "tier",
    "observation_fraction",
    "algorithm_seed",
    "repeat",
    "timeout_seconds",
}
PROVENANCE_FIELDS = {
    "source_commit",
    "runner_commit",
    "tree_digest",
    "image_sha256",
    "compiler_digest",
}
TERMINAL_RUNNER_STATES = {
    "SUCCESS",
    "TIMEOUT",
    "OOM",
    "NONZERO_EXIT",
    "INVALID_METRICS",
    "VERIFIER_FAILED",
    "VERIFIER_NOT_RUN",
    "CANCELLED",
    "MISSING_SUCCESS_MANIFEST",
}
SLURM_STATES = {
    "TIMEOUT",
    "OUT_OF_MEMORY",
    "FAILED",
    "CANCELLED",
    "COMPLETED",
}
PENDING_STATES = {
    "PENDING",
    "RUNNING",
    "CONFIGURING",
    "COMPLETING",
    "SUSPENDED",
}
FAILED_QUALITY_FIELDS = (
    "train_exact",
    "visible_cv_exact",
    "visible_cv_bit_accuracy",
    "gates",
    "completed_table_sha256",
    "circuit_sha256",
    "artifact_sha256",
    "artifact_path",
)
_CHECKER_MODULE: object | None = None


class ValidationError(ValueError):
    """Invalid or incomplete scheduler evidence."""


@dataclass(frozen=True)
class Cell:
    cell_id: str
    params: dict[str, str]


@dataclass(frozen=True)
class SchedulerRow:
    job_id_raw: str
    state: str
    exit_code: str
    code: int
    signal: int
    max_rss_kib: int | None
    elapsed_raw: str


@dataclass(frozen=True)
class PlannedManifest:
    path: Path
    data: bytes


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_timeout_elapsed(value: str) -> str:
    text = format(Decimal(value).normalize(), "f")
    if "." not in text:
        text += ".0"
    return text


def read_regular(path: Path, label: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValidationError(f"{label} must be an existing regular file") from exc
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise ValidationError(f"{label} must be a regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def read_canonical_object(path: Path, label: str) -> tuple[dict[str, object], bytes]:
    raw = read_regular(path, label)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be a JSON object")
    if raw != canonical_json_bytes(value):
        raise ValidationError(f"{label} must be canonical JSON")
    return value, raw


def string_object(
    value: object, fields: set[str], label: str
) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValidationError(f"{label} has the wrong fields")
    if any(not isinstance(item, str) for item in value.values()):
        raise ValidationError(f"{label} values must be strings")
    return {str(key): item for key, item in value.items()}


def read_run_spec(run_root: Path) -> tuple[list[Cell], dict[str, str], bytes]:
    spec, raw = read_canonical_object(run_root / "run_spec.json", "run_spec.json")
    if set(spec) != {"schema_version", "cells", "provenance"}:
        raise ValidationError("run_spec.json has the wrong top-level fields")
    if spec["schema_version"] != 1:
        raise ValidationError("run_spec.json schema_version must equal 1")
    provenance = string_object(
        spec["provenance"], PROVENANCE_FIELDS, "run_spec.json provenance"
    )
    for field in ("source_commit", "runner_commit"):
        if not COMMIT_HASH.fullmatch(provenance[field]):
            raise ValidationError(f"run_spec.json {field} is invalid")
    if not HEX_64.fullmatch(provenance["tree_digest"]):
        raise ValidationError("run_spec.json tree_digest is invalid")
    for field in ("image_sha256", "compiler_digest"):
        value = provenance[field]
        if value != "none" and not HEX_64.fullmatch(value):
            raise ValidationError(f"run_spec.json {field} is invalid")
    raw_cells = spec["cells"]
    if not isinstance(raw_cells, list) or not raw_cells:
        raise ValidationError("run_spec.json cells must be a nonempty array")
    cells: list[Cell] = []
    seen: set[str] = set()
    for index, value in enumerate(raw_cells):
        if not isinstance(value, dict) or set(value) != {"cell_id", "params"}:
            raise ValidationError(f"run_spec.json cells[{index}] is invalid")
        cell_id = value["cell_id"]
        if not isinstance(cell_id, str) or not CELL_ID.fullmatch(cell_id):
            raise ValidationError(f"run_spec.json cells[{index}] has invalid cell_id")
        if cell_id in seen:
            raise ValidationError(f"run_spec.json has duplicate cell_id: {cell_id}")
        seen.add(cell_id)
        params = string_object(value["params"], PARAM_FIELDS, f"params for {cell_id}")
        if params["comparison_id"] != cell_id:
            raise ValidationError(f"params for {cell_id} disagree on comparison_id")
        if (
            params["blind"] != "true"
            or params["evaluation_scope"] != "visible_cv_only"
        ):
            raise ValidationError(f"params for {cell_id} violate blind scope")
        cells.append(Cell(cell_id, params))
    return cells, provenance, raw


def parse_row(line: str, row_number: int) -> SchedulerRow:
    fields = line.split("|")
    if len(fields) != 5:
        raise ValidationError(f"raw accounting row {row_number} has wrong width")
    job_id_raw, state, raw_exit, max_rss, elapsed = fields
    match = EXIT_CODE.fullmatch(raw_exit)
    if match is None:
        raise ValidationError(f"raw accounting row {row_number} has invalid ExitCode")
    code, exit_signal = map(int, match.groups())
    if code > 255 or exit_signal > 255:
        raise ValidationError(f"raw accounting row {row_number} has invalid ExitCode")
    if not CANONICAL_INTEGER.fullmatch(elapsed):
        raise ValidationError(f"raw accounting row {row_number} has invalid ElapsedRaw")
    if max_rss == "":
        rss = None
    else:
        rss_match = RSS_KIB.fullmatch(max_rss)
        if rss_match is None:
            raise ValidationError(f"raw accounting row {row_number} has invalid MaxRSS")
        rss = int(rss_match.group(1))
    if state in PENDING_STATES:
        raise ValidationError(f"raw accounting row {row_number} is not terminal")
    if state not in SLURM_STATES:
        raise ValidationError(f"raw accounting row {row_number} has unknown state")
    if state == "COMPLETED" and (code != 0 or exit_signal != 0):
        raise ValidationError(
            f"raw accounting row {row_number} has inconsistent state/exit pair"
        )
    if state == "FAILED" and code == 0 and exit_signal == 0:
        raise ValidationError(
            f"raw accounting row {row_number} has inconsistent state/exit pair"
        )
    return SchedulerRow(
        job_id_raw=job_id_raw,
        state=state,
        exit_code=raw_exit,
        code=code,
        signal=exit_signal,
        max_rss_kib=rss,
        elapsed_raw=elapsed,
    )


def read_scheduler_rows(raw_path: Path) -> tuple[dict[str, SchedulerRow], bytes]:
    raw = read_regular(raw_path, "raw accounting file")
    if not raw.startswith(RAW_HEADER):
        raise ValidationError(
            "raw accounting file must use exact header "
            "JobIDRaw|State|ExitCode|MaxRSS|ElapsedRaw"
        )
    body = raw[len(RAW_HEADER) :]
    if not body or not body.endswith(b"\n") or b"\r" in raw:
        raise ValidationError("raw accounting file must be complete LF-terminated text")
    try:
        lines = body[:-1].decode("utf-8").split("\n")
    except UnicodeDecodeError as exc:
        raise ValidationError("raw accounting file must be UTF-8") from exc
    indexed: dict[str, SchedulerRow] = {}
    for row_number, line in enumerate(lines, start=2):
        row = parse_row(line, row_number)
        if row.job_id_raw in indexed:
            raise ValidationError(
                f"raw accounting file has duplicate JobIDRaw: {row.job_id_raw}"
            )
        indexed[row.job_id_raw] = row
    return indexed, raw


def validate_job_rows(
    rows: dict[str, SchedulerRow], job_id: str, cell_count: int
) -> None:
    allowed: set[str] = set()
    for index in range(1, cell_count + 1):
        root = f"{job_id}_{index}"
        allowed.update({root, f"{root}.batch", f"{root}.extern"})
        if root not in rows:
            raise ValidationError(f"missing root allocation row {root}")
    unexpected = set(rows) - allowed
    if unexpected:
        raise ValidationError(
            f"raw accounting file has unexpected JobIDRaw: {sorted(unexpected)[0]}"
        )


def validate_existing_runner_manifest(
    path: Path,
    cell: Cell,
    provenance: dict[str, str],
    run_spec_sha256: str,
) -> None:
    payload, _ = read_canonical_object(path, f"existing manifest for {cell.cell_id}")
    expected = {
        **cell.params,
        **provenance,
        "schema_version": 1,
        "producer": "runner",
        "run_spec_sha256": run_spec_sha256,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise ValidationError(
            f"existing manifest for {cell.cell_id} is not a provenance-bound runner manifest"
        )
    if payload.get("status") not in TERMINAL_RUNNER_STATES:
        raise ValidationError(
            f"existing manifest for {cell.cell_id} is not terminal"
        )
    global _CHECKER_MODULE
    if _CHECKER_MODULE is None:
        checker_path = (
            Path(__file__).resolve().parents[1] / "research" / "check_gate.py"
        )
        module_spec = importlib.util.spec_from_file_location(
            "task10_materializer_check_gate", checker_path
        )
        if module_spec is None or module_spec.loader is None:
            raise ValidationError(
                "cannot load checker for existing manifest validation"
            )
        _CHECKER_MODULE = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(_CHECKER_MODULE)
    checker = _CHECKER_MODULE
    errors: list[str] = []
    label = f"existing manifest for {cell.cell_id}"
    row = checker.check_manifest_schema(payload, label, errors)
    checker.check_execution_row(row, label, errors)
    run_root = path.parents[2]
    checker.check_operational_metadata(
        run_root, payload, row, label, run_spec_sha256, errors
    )
    checker.check_native_artifacts(run_root, payload, row, label, errors)
    if errors:
        raise ValidationError(f"{label} is invalid: {errors[0]}")


def classify(row: SchedulerRow) -> tuple[str, str, str]:
    if row.state == "TIMEOUT":
        return "TIMEOUT", "124", "true"
    if row.state == "OUT_OF_MEMORY":
        return "OOM", "137", "false"
    if row.state == "CANCELLED":
        return "CANCELLED", "130", "false"
    if row.state == "COMPLETED":
        return "MISSING_SUCCESS_MANIFEST", "70", "false"
    normalized = (
        row.code
        if row.code != 0
        else 128 + row.signal
        if row.signal != 0
        else 1
    )
    return "NONZERO_EXIT", str(normalized), "false"


def peak_memory(
    rows: dict[str, SchedulerRow], root_id: str
) -> str:
    observations = [
        rows[row_id].max_rss_kib
        for row_id in (root_id, f"{root_id}.batch", f"{root_id}.extern")
        if row_id in rows and rows[row_id].max_rss_kib is not None
    ]
    return str(max(observations)) if observations else "none"


def build_manifest(
    cell: Cell,
    provenance: dict[str, str],
    run_spec_sha256: str,
    scheduler_sha256: str,
    row: SchedulerRow,
    job_id: str,
    task_index: int,
    log: bytes,
    rows: dict[str, SchedulerRow],
) -> bytes:
    status, exit_code, timed_out = classify(row)
    root_id = f"{job_id}_{task_index}"
    payload: dict[str, object] = {
        **cell.params,
        **provenance,
        "schema_version": 1,
        "producer": "scheduler",
        "run_spec_sha256": run_spec_sha256,
        "argv": [],
        "started_utc": "none",
        "ended_utc": "none",
        "status": status,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "elapsed_seconds": (
            canonical_timeout_elapsed(cell.params["timeout_seconds"])
            if status == "TIMEOUT"
            else f"{row.elapsed_raw}.0"
        ),
        "cleanup_seconds": "none",
        "peak_memory_kib": peak_memory(rows, root_id),
        "verifier": "not_run",
        "stdout_sha256": sha256_bytes(log),
        "stderr_sha256": "none",
        "log_sha256": sha256_bytes(log),
        "scheduler_sha256": scheduler_sha256,
        "scheduler_job_id": job_id,
        "scheduler_task_index": str(task_index),
        "scheduler_state": row.state,
        "scheduler_exit_code": row.exit_code,
        "scheduler_classification": status,
        "scheduler_elapsed_seconds": row.elapsed_raw,
    }
    payload.update({field: "none" for field in FAILED_QUALITY_FIELDS})
    return canonical_json_bytes(payload)


def plan_materialization(
    run_root: Path, raw_path: Path, job_id: str
) -> list[PlannedManifest]:
    if not JOB_ID.fullmatch(job_id):
        raise ValidationError("job-id must be a canonical positive integer")
    run_root = run_root.resolve(strict=True)
    if not run_root.is_dir():
        raise ValidationError("run root must be a directory")
    cells, provenance, run_spec_raw = read_run_spec(run_root)
    rows, scheduler_raw = read_scheduler_rows(raw_path.resolve(strict=True))
    validate_job_rows(rows, job_id, len(cells))
    run_spec_sha256 = sha256_bytes(run_spec_raw)
    scheduler_sha256 = sha256_bytes(scheduler_raw)

    planned: list[PlannedManifest] = []
    for task_index, cell in enumerate(cells, start=1):
        manifest_path = run_root / "cells" / cell.cell_id / "manifest.json"
        if manifest_path.exists() or manifest_path.is_symlink():
            validate_existing_runner_manifest(
                manifest_path, cell, provenance, run_spec_sha256
            )
            continue
        log_path = run_root / f"slurm-{job_id}_{task_index}.out"
        log = read_regular(log_path, f"task log {log_path.name}")
        root_id = f"{job_id}_{task_index}"
        planned.append(
            PlannedManifest(
                manifest_path,
                build_manifest(
                    cell,
                    provenance,
                    run_spec_sha256,
                    scheduler_sha256,
                    rows[root_id],
                    job_id,
                    task_index,
                    log,
                    rows,
                ),
            )
        )
    return planned


def atomic_create(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("xb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise ValidationError(f"refusing to replace existing manifest: {path}") from exc
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    parser.add_argument("raw_accounting", type=Path)
    parser.add_argument("--job-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        planned = plan_materialization(
            args.run_root, args.raw_accounting, args.job_id
        )
        for item in planned:
            atomic_create(item.path, item.data)
    except (OSError, ValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
