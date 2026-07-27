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
CANONICAL_TIMEOUT = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
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


def validate_timeout(value: str, label: str) -> Decimal:
    if not CANONICAL_TIMEOUT.fullmatch(value):
        raise ValidationError(f"{label} timeout_seconds is not canonical")
    number = Decimal(value)
    canonical = canonical_timeout_elapsed(value)
    if "." in value and canonical != value:
        raise ValidationError(f"{label} timeout_seconds is not canonical")
    if not number.is_finite() or number <= 0 or number > Decimal(300):
        raise ValidationError(f"{label} timeout_seconds must be in (0,300]")
    return number


def validate_params(params: dict[str, str], cell_id: str) -> Decimal:
    label = f"params for {cell_id}"
    if params["comparison_id"] != cell_id:
        raise ValidationError(f"{label} disagree on comparison_id")
    if params["role"] not in {"baseline", "candidate"}:
        raise ValidationError(f"{label} role must equal baseline or candidate")
    if (
        params["blind"] != "true"
        or params["evaluation_scope"] != "visible_cv_only"
    ):
        raise ValidationError(f"{label} violate blind scope")
    if not HEX_64.fullmatch(params["algorithm_seed"]):
        raise ValidationError(f"{label} algorithm_seed must be 64 lowercase hex")
    if not CANONICAL_INTEGER.fullmatch(params["repeat"]):
        raise ValidationError(f"{label} repeat must be canonical")
    for field in PARAM_FIELDS - {
        "algorithm_seed",
        "repeat",
        "timeout_seconds",
    }:
        if params[field] == "":
            raise ValidationError(f"{label} {field} must not be blank")
    return validate_timeout(params["timeout_seconds"], label)


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
        validate_params(params, cell_id)
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


def validate_destination_components(run_root: Path, cells: list[Cell]) -> None:
    cells_root = run_root / "cells"
    try:
        details = os.lstat(cells_root)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(details.st_mode):
        raise ValidationError("destination component cells must not be a symlink")
    if not stat.S_ISDIR(details.st_mode):
        raise ValidationError("destination component cells must be a directory")
    for cell in cells:
        cell_path = cells_root / cell.cell_id
        try:
            details = os.lstat(cell_path)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(details.st_mode):
            raise ValidationError(
                f"destination component {cell.cell_id} must not be a symlink"
            )
        if not stat.S_ISDIR(details.st_mode):
            raise ValidationError(
                f"destination component {cell.cell_id} must be a directory"
            )


def validate_elapsed_caps(
    cells: list[Cell], rows: dict[str, SchedulerRow], job_id: str
) -> None:
    for task_index, cell in enumerate(cells, start=1):
        row = rows[f"{job_id}_{task_index}"]
        timeout = validate_timeout(
            cell.params["timeout_seconds"], f"params for {cell.cell_id}"
        )
        if row.state != "TIMEOUT" and Decimal(row.elapsed_raw) > timeout:
            raise ValidationError(
                f"raw accounting ElapsedRaw for {cell.cell_id} exceeds timeout_seconds"
            )


def checker_module() -> object:
    global _CHECKER_MODULE
    if _CHECKER_MODULE is None:
        checker_path = (
            Path(__file__).resolve().parents[1] / "research" / "check_gate.py"
        )
        module_spec = importlib.util.spec_from_file_location(
            "task10_materializer_check_gate", checker_path
        )
        if module_spec is None or module_spec.loader is None:
            raise ValidationError("cannot load checker for manifest validation")
        _CHECKER_MODULE = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(_CHECKER_MODULE)
    return _CHECKER_MODULE


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
    checker = checker_module()
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


def validate_planned_manifest(
    data: bytes,
    run_root: Path,
    cell: Cell,
    run_spec_sha256: str,
    task_index: int,
) -> None:
    payload = json.loads(data)
    checker = checker_module()
    errors: list[str] = []
    label = f"planned manifest for {cell.cell_id}"
    row = checker.check_manifest_schema(payload, label, errors)
    checker.check_execution_row(row, label, errors)
    checker.check_operational_metadata(
        run_root,
        payload,
        row,
        label,
        run_spec_sha256,
        errors,
        expected_task_index=task_index,
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
    validate_destination_components(run_root, cells)
    rows, scheduler_raw = read_scheduler_rows(raw_path.resolve(strict=True))
    validate_job_rows(rows, job_id, len(cells))
    validate_elapsed_caps(cells, rows, job_id)
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
        data = build_manifest(
            cell,
            provenance,
            run_spec_sha256,
            scheduler_sha256,
            rows[root_id],
            job_id,
            task_index,
            log,
            rows,
        )
        validate_planned_manifest(
            data, run_root, cell, run_spec_sha256, task_index
        )
        planned.append(PlannedManifest(manifest_path, data))
    return planned


def open_or_create_directory(
    parent_fd: int, name: str, label: str
) -> int:
    try:
        os.mkdir(name, dir_fd=parent_fd)
    except FileExistsError:
        pass
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(name, flags, dir_fd=parent_fd)
    except OSError as exc:
        raise ValidationError(
            f"destination component {label} must be a directory, not a symlink"
        ) from exc
    details = os.fstat(descriptor)
    if not stat.S_ISDIR(details.st_mode):
        os.close(descriptor)
        raise ValidationError(
            f"destination component {label} must be a directory, not a symlink"
        )
    return descriptor


def write_all_manifests(run_root: Path, planned: list[PlannedManifest]) -> None:
    if not planned:
        return
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    run_fd = os.open(run_root, directory_flags)
    cells_fd: int | None = None
    entries: list[tuple[int, str]] = []
    linked: list[int] = []
    try:
        cells_fd = open_or_create_directory(run_fd, "cells", "cells")
        for index, item in enumerate(planned):
            cell_id = item.path.parent.name
            cell_fd = open_or_create_directory(cells_fd, cell_id, cell_id)
            temporary = f".manifest.json.tmp-{os.getpid()}-{index}"
            entries.append((cell_fd, temporary))
            flags = (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0)
            )
            descriptor = os.open(
                temporary, flags, 0o600, dir_fd=cell_fd
            )
            try:
                remaining = memoryview(item.data)
                while remaining:
                    written = os.write(descriptor, remaining)
                    remaining = remaining[written:]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

        for cell_fd, temporary in entries:
            try:
                os.link(
                    temporary,
                    "manifest.json",
                    src_dir_fd=cell_fd,
                    dst_dir_fd=cell_fd,
                    follow_symlinks=False,
                )
            except FileExistsError as exc:
                raise ValidationError(
                    "refusing to replace existing manifest"
                ) from exc
            linked.append(cell_fd)
            os.fsync(cell_fd)
    except Exception:
        for cell_fd in reversed(linked):
            try:
                os.unlink("manifest.json", dir_fd=cell_fd)
                os.fsync(cell_fd)
            except FileNotFoundError:
                pass
        raise
    finally:
        for cell_fd, temporary in entries:
            try:
                os.unlink(temporary, dir_fd=cell_fd)
            except FileNotFoundError:
                pass
        for cell_fd, _ in entries:
            os.close(cell_fd)
        if cells_fd is not None:
            os.close(cells_fd)
        os.close(run_fd)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    parser.add_argument("raw_accounting", type=Path)
    parser.add_argument("--job-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_root = args.run_root.resolve(strict=True)
        planned = plan_materialization(
            run_root, args.raw_accounting, args.job_id
        )
        write_all_manifests(run_root, planned)
    except (OSError, ValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
