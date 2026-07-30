#!/usr/bin/env python3
"""Run one frozen autoresearch cell under a hard wall-clock deadline."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import resource
import secrets
import signal
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


CELL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
HEX_64 = re.compile(r"[0-9a-f]{64}")
COMMIT_HASH = re.compile(r"[0-9a-f]{40}")
CANONICAL_INTEGER = re.compile(r"(?:0|[1-9][0-9]*)")
CANONICAL_TIMEOUT = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
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
METRICS_FIELDS = {
    "train_exact",
    "visible_cv_exact",
    "visible_cv_bit_accuracy",
    "gates",
    "completed_table_sha256",
    "verifier",
}
ARTIFACT_FIELDS = {
    "circuit_path",
    "circuit_sha256",
    "completed_table_path",
    "completed_table_sha256",
    "equivalence",
    "schema_version",
}


class ValidationError(ValueError):
    """A fail-closed preflight error."""


@dataclass(frozen=True)
class RunResult:
    status: str
    exit_code: int
    timed_out: bool
    elapsed_seconds: str
    cleanup_seconds: str
    peak_memory_kib: str
    started_utc: str
    ended_utc: str
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True)
class PreparedRun:
    run_root: Path
    run_spec_path: Path
    run_spec_bytes: bytes
    cell_id: str
    cell_dir: Path
    metrics_path: Path
    params: dict[str, str]
    provenance: dict[str, str]
    timeout: float
    argv: list[str]


@dataclass(frozen=True)
class CandidateEvidence:
    train_exact: str
    visible_cv_exact: str
    visible_cv_bit_accuracy: str
    gates: str
    completed_table_sha256: str
    circuit_sha256: str
    artifact_sha256: str
    artifact_path: str


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def canonical_seconds(value: float) -> str:
    if not math.isfinite(value) or value < 0:
        raise ValueError("seconds must be finite and nonnegative")
    text = f"{value:.9f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return text


def canonical_accuracy(value: object, field: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be a finite JSON number")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be a finite JSON number") from exc
    if not number.is_finite() or not Decimal(0) <= number <= Decimal(1):
        raise ValidationError(f"{field} must be finite and in [0,1]")
    text = format(number.normalize(), "f")
    if "." not in text:
        text += ".0"
    return text


def _canonical_timeout_elapsed(value: str) -> str:
    text = format(Decimal(value).normalize(), "f")
    if "." not in text:
        text += ".0"
    return text


def _normalize_peak_memory_kib(raw_maxrss: float, system: str | None = None) -> int:
    normalized = raw_maxrss / 1024 if (system or platform.system()) == "Darwin" else raw_maxrss
    return max(0, int(math.ceil(normalized)))


def git_output(repo: Path, *args: str) -> bytes:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args], stderr=subprocess.PIPE
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise ValidationError(f"git {' '.join(args)} failed: {detail}") from exc


def read_canonical_object(path: Path, label: str) -> tuple[dict[str, object], bytes]:
    try:
        if path.is_symlink() or not path.is_file():
            raise ValidationError(f"{label} must be a regular file")
        raw = path.read_bytes()
    except OSError as exc:
        raise ValidationError(f"cannot read {label}: {exc}") from exc
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, ValueError, RecursionError, OverflowError) as exc:
        raise ValidationError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be a JSON object")
    if raw != canonical_json_bytes(value):
        raise ValidationError(f"{label} must be compact sorted-key JSON with one final LF")
    return value, raw


def string_object(
    value: object, expected_fields: set[str], label: str
) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise ValidationError(f"{label} must contain exactly {sorted(expected_fields)}")
    if any(not isinstance(item, str) for item in value.values()):
        raise ValidationError(f"{label} values must be strings")
    return {str(key): item for key, item in value.items()}


def validate_timeout(value: str) -> float:
    if not CANONICAL_TIMEOUT.fullmatch(value):
        raise ValidationError("timeout_seconds must be a canonical positive decimal")
    try:
        timeout = Decimal(value)
    except InvalidOperation as exc:
        raise ValidationError("timeout_seconds must be a canonical positive decimal") from exc
    if not timeout.is_finite() or timeout <= 0 or timeout > Decimal(300):
        raise ValidationError("timeout_seconds must be in (0,300]")
    if "." in value and _canonical_timeout_elapsed(value) != value:
        raise ValidationError("timeout_seconds must be canonical")
    return float(timeout)


def validate_params(params: dict[str, str], cell_id: str) -> float:
    if params["comparison_id"] != cell_id:
        raise ValidationError("cell params comparison_id must equal cell_id")
    if params["role"] not in {"baseline", "candidate"}:
        raise ValidationError("cell params role must equal baseline or candidate")
    if params["blind"] != "true":
        raise ValidationError("cell params blind must equal true")
    if params["evaluation_scope"] != "visible_cv_only":
        raise ValidationError(
            "cell params evaluation_scope must equal visible_cv_only"
        )
    if not HEX_64.fullmatch(params["algorithm_seed"]):
        raise ValidationError("algorithm_seed must be 64 lowercase hex")
    if not CANONICAL_INTEGER.fullmatch(params["repeat"]):
        raise ValidationError("repeat must be a canonical nonnegative integer")
    for field in PARAM_FIELDS - {
        "algorithm_seed",
        "repeat",
        "timeout_seconds",
    }:
        if params[field] == "":
            raise ValidationError(f"{field} must not be empty")
    return validate_timeout(params["timeout_seconds"])


def validate_provenance(
    provenance: dict[str, str],
    repo: Path,
    container_provenance: Path | None,
) -> None:
    if not COMMIT_HASH.fullmatch(provenance["source_commit"]):
        raise ValidationError("source_commit must be 40 lowercase hex")
    if not COMMIT_HASH.fullmatch(provenance["runner_commit"]):
        raise ValidationError("runner_commit must be 40 lowercase hex")
    if not HEX_64.fullmatch(provenance["tree_digest"]):
        raise ValidationError("tree_digest must be 64 lowercase hex")
    for field in ("image_sha256", "compiler_digest"):
        value = provenance[field]
        if value != "none" and not HEX_64.fullmatch(value):
            raise ValidationError(f"{field} must be none or 64 lowercase hex")

    if container_provenance is not None:
        container, _ = read_canonical_object(
            container_provenance, "container provenance"
        )
        checked = string_object(
            container, PROVENANCE_FIELDS, "container provenance"
        )
        if checked != provenance:
            raise ValidationError("container provenance disagrees with run_spec.json")
        return

    status = git_output(repo, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise ValidationError("local worktree must be clean including untracked files")
    head = git_output(repo, "rev-parse", "HEAD").decode("ascii").strip()
    tree = sha256_bytes(git_output(repo, "ls-tree", "-rz", "--full-tree", "HEAD"))
    if provenance["source_commit"] != head or provenance["runner_commit"] != head:
        raise ValidationError("local source_commit and runner_commit must equal HEAD")
    if provenance["tree_digest"] != tree:
        raise ValidationError("local tree_digest does not identify HEAD")
    if provenance["image_sha256"] != "none":
        raise ValidationError("local image_sha256 must equal none")


def prepare_run(args: argparse.Namespace) -> PreparedRun:
    if not args.command:
        raise ValidationError("command after -- must not be empty")
    if not CELL_ID.fullmatch(args.cell_id):
        raise ValidationError("cell-id is invalid")
    run_root = args.run_root.resolve(strict=True)
    if not run_root.is_dir():
        raise ValidationError("run-root must be a directory")
    run_spec_path = run_root / "run_spec.json"
    if run_spec_path.resolve(strict=True).parent != run_root:
        raise ValidationError("run_spec.json must be a regular file inside run-root")
    spec, spec_bytes = read_canonical_object(run_spec_path, "run_spec.json")
    if set(spec) != {"schema_version", "cells", "provenance"}:
        raise ValidationError(
            "run_spec.json must contain exactly schema_version, cells, provenance"
        )
    if spec["schema_version"] != 1:
        raise ValidationError("run_spec.json schema_version must equal 1")
    cells = spec["cells"]
    if not isinstance(cells, list) or not cells:
        raise ValidationError("run_spec.json cells must be a nonempty array")
    selected_params: dict[str, str] | None = None
    selected_timeout: float | None = None
    seen: set[str] = set()
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict) or set(cell) != {"cell_id", "params"}:
            raise ValidationError(
                f"run_spec.json cells[{index}] must contain exactly cell_id and params"
            )
        cell_id = cell["cell_id"]
        if not isinstance(cell_id, str) or not CELL_ID.fullmatch(cell_id):
            raise ValidationError(f"run_spec.json cells[{index}] has invalid cell_id")
        if cell_id in seen:
            raise ValidationError(f"run_spec.json has duplicate cell_id: {cell_id}")
        seen.add(cell_id)
        params = string_object(
            cell["params"], PARAM_FIELDS, f"params for {cell_id}"
        )
        timeout = validate_params(params, cell_id)
        if cell_id == args.cell_id:
            selected_params = params
            selected_timeout = timeout
    if selected_params is None or selected_timeout is None:
        raise ValidationError(f"run_spec.json does not declare cell {args.cell_id}")
    provenance = string_object(
        spec["provenance"], PROVENANCE_FIELDS, "run_spec.json provenance"
    )
    repo = Path.cwd().resolve()
    validate_provenance(provenance, repo, args.container_provenance)

    cell_dir = run_root / "cells" / args.cell_id
    if cell_dir.exists() or cell_dir.is_symlink():
        raise ValidationError(f"cell directory already exists: {args.cell_id}")
    metrics_path = args.metrics_json.resolve(strict=False)
    if metrics_path.parent != cell_dir:
        raise ValidationError("metrics-json must be a direct child of the selected cell")
    return PreparedRun(
        run_root=run_root,
        run_spec_path=run_spec_path,
        run_spec_bytes=spec_bytes,
        cell_id=args.cell_id,
        cell_dir=cell_dir,
        metrics_path=metrics_path,
        params=selected_params,
        provenance=provenance,
        timeout=selected_timeout,
        argv=list(args.command),
    )


def terminate_process_group(
    process: subprocess.Popen[bytes], start: float, timeout: float
) -> tuple[bool, float]:
    deadline = start + timeout
    grace = min(1.0, max(0.01, timeout / 5))
    term_at = max(start, deadline - grace)
    term_sent = False
    while process.poll() is None:
        now = time.monotonic()
        if not term_sent and now >= term_at:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            term_sent = True
        if now >= deadline:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            break
        time.sleep(min(0.005, max(0.0, deadline - now)))
    process.wait()
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    reaped = time.monotonic()
    return term_sent, max(0.0, reaped - deadline) if term_sent else 0.0


def run_child(prepared: PreparedRun) -> RunResult:
    prepared.cell_dir.mkdir(parents=True, exist_ok=False)
    stdout_path = prepared.cell_dir / "stdout.log"
    stderr_path = prepared.cell_dir / "stderr.log"
    started_utc = utc_now()
    start = time.monotonic()
    launch_exit_code: int | None = None
    raw_returncode = 0
    timed_out = False
    cleanup = 0.0
    with stdout_path.open("x+b") as stdout_file, stderr_path.open("x+b") as stderr_file:
        try:
            process = subprocess.Popen(
                prepared.argv,
                cwd=prepared.cell_dir,
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                start_new_session=True,
            )
        except OSError as exc:
            launch_exit_code = 127 if isinstance(exc, FileNotFoundError) else 126
            stderr_file.write(f"runner launch error: {exc}\n".encode())
            stderr_file.flush()
            os.fsync(stderr_file.fileno())
        else:
            timed_out, cleanup = terminate_process_group(
                process, start, prepared.timeout
            )
            raw_returncode = process.returncode
        stdout_file.flush()
        stderr_file.flush()
        os.fsync(stdout_file.fileno())
        os.fsync(stderr_file.fileno())
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read()
        stderr = stderr_file.read()
    atomic_write(stdout_path, stdout)
    atomic_write(stderr_path, stderr)
    ended_utc = utc_now()
    measured = max(0.0, time.monotonic() - start)
    if timed_out:
        status = "TIMEOUT"
        exit_code = 124
        elapsed = _canonical_timeout_elapsed(prepared.params["timeout_seconds"])
    elif launch_exit_code is not None:
        status = "NONZERO_EXIT"
        exit_code = launch_exit_code
        elapsed = canonical_seconds(measured)
    elif raw_returncode == 0:
        status = "INVALID_METRICS"
        exit_code = 65
        elapsed = canonical_seconds(measured)
    else:
        status = "NONZERO_EXIT"
        exit_code = (
            128 + abs(raw_returncode) if raw_returncode < 0 else raw_returncode
        )
        elapsed = canonical_seconds(measured)
    peak = _normalize_peak_memory_kib(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    return RunResult(
        status=status,
        exit_code=exit_code,
        timed_out=timed_out,
        elapsed_seconds=elapsed,
        cleanup_seconds=canonical_seconds(cleanup) if timed_out else "0.0",
        peak_memory_kib=str(peak),
        started_utc=started_utc,
        ended_utc=ended_utc,
        stdout=stdout,
        stderr=stderr,
    )


def framed_log_hash(stdout: bytes, stderr: bytes) -> str:
    framed = (
        len(stdout).to_bytes(8, "big")
        + stdout
        + len(stderr).to_bytes(8, "big")
        + stderr
    )
    return sha256_bytes(framed)


def read_regular_once(path: Path, label: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValidationError(f"{label} must be an existing regular file") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValidationError(f"{label} must be a regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        if identity != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise ValidationError(f"{label} changed while it was read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def read_stable_regular(path: Path, label: str) -> bytes:
    first = read_regular_once(path, label)
    second = read_regular_once(path, label)
    if first != second:
        raise ValidationError(f"{label} changed between stable reads")
    return first


def decode_json_object(raw: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, ValueError, RecursionError, OverflowError) as exc:
        raise ValidationError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be a JSON object")
    return value


def classify_zero_exit(
    prepared: PreparedRun,
) -> tuple[str, int, str, CandidateEvidence | None]:
    try:
        metrics_raw = read_stable_regular(prepared.metrics_path, "metrics-json")
        metrics = decode_json_object(metrics_raw, "metrics-json")
        if set(metrics) != METRICS_FIELDS:
            raise ValidationError("metrics-json has missing or extra fields")
        verifier = metrics["verifier"]
        if verifier not in {"pass", "fail", "not_run"}:
            raise ValidationError("metrics-json verifier is invalid")
        train_exact = canonical_accuracy(metrics["train_exact"], "train_exact")
        if train_exact != "1.0":
            raise ValidationError("train_exact must equal 1.0")
        visible_exact = canonical_accuracy(
            metrics["visible_cv_exact"], "visible_cv_exact"
        )
        visible_bits = canonical_accuracy(
            metrics["visible_cv_bit_accuracy"], "visible_cv_bit_accuracy"
        )
        gates = metrics["gates"]
        if isinstance(gates, bool) or not isinstance(gates, int) or gates < 0:
            raise ValidationError("gates must be a nonnegative integer")
        metrics_table_digest = metrics["completed_table_sha256"]
        if not isinstance(metrics_table_digest, str) or not HEX_64.fullmatch(
            metrics_table_digest
        ):
            raise ValidationError(
                "metrics completed_table_sha256 must be 64 lowercase hex"
            )

        artifact_path = prepared.cell_dir / "artifact.json"
        artifact_raw = read_stable_regular(artifact_path, "artifact.json")
        artifact = decode_json_object(artifact_raw, "artifact.json")
        if artifact_raw != canonical_json_bytes(artifact):
            raise ValidationError(
                "artifact.json must be compact sorted-key JSON with one final LF"
            )
        if set(artifact) != ARTIFACT_FIELDS:
            raise ValidationError("artifact.json has missing or extra fields")
        if artifact["schema_version"] != 1:
            raise ValidationError("artifact.json schema_version must equal 1")
        if artifact["circuit_path"] != "circuit.txt":
            raise ValidationError("artifact.json circuit_path is not fixed")
        if artifact["completed_table_path"] != "completed-table.csv":
            raise ValidationError("artifact.json completed_table_path is not fixed")
        if artifact["equivalence"] != "pass":
            raise ValidationError("artifact.json equivalence must equal pass")
        circuit_digest = artifact["circuit_sha256"]
        table_digest = artifact["completed_table_sha256"]
        if not isinstance(circuit_digest, str) or not HEX_64.fullmatch(
            circuit_digest
        ):
            raise ValidationError("artifact circuit_sha256 must be 64 lowercase hex")
        if not isinstance(table_digest, str) or not HEX_64.fullmatch(table_digest):
            raise ValidationError(
                "artifact completed_table_sha256 must be 64 lowercase hex"
            )
        table_raw = read_stable_regular(
            prepared.cell_dir / "completed-table.csv", "completed-table.csv"
        )
        circuit_raw = read_stable_regular(
            prepared.cell_dir / "circuit.txt", "circuit.txt"
        )
        actual_table = sha256_bytes(table_raw)
        actual_circuit = sha256_bytes(circuit_raw)
        if table_digest != actual_table or metrics_table_digest != actual_table:
            raise ValidationError("completed table digest binding mismatch")
        if circuit_digest != actual_circuit:
            raise ValidationError("circuit digest binding mismatch")
        relative_artifact = artifact_path.relative_to(prepared.run_root).as_posix()
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
    except (OSError, ValidationError):
        return "INVALID_METRICS", 65, "not_run", None


def terminal_manifest(
    prepared: PreparedRun,
    result: RunResult,
    verifier: str,
    evidence: CandidateEvidence | None,
) -> dict[str, object]:
    stdout = result.stdout
    stderr = result.stderr
    payload: dict[str, object] = {
        **prepared.params,
        **prepared.provenance,
        "schema_version": 1,
        "producer": "runner",
        "run_spec_sha256": sha256_bytes(prepared.run_spec_bytes),
        "argv": prepared.argv,
        "started_utc": result.started_utc,
        "ended_utc": result.ended_utc,
        "status": result.status,
        "exit_code": str(result.exit_code),
        "timed_out": "true" if result.timed_out else "false",
        "elapsed_seconds": result.elapsed_seconds,
        "cleanup_seconds": result.cleanup_seconds,
        "peak_memory_kib": result.peak_memory_kib,
        "verifier": verifier,
        "stdout_sha256": sha256_bytes(stdout),
        "stderr_sha256": sha256_bytes(stderr),
        "log_sha256": framed_log_hash(stdout, stderr),
        "scheduler_sha256": "none",
        "scheduler_job_id": "none",
        "scheduler_task_index": "none",
        "scheduler_state": "none",
        "scheduler_exit_code": "none",
        "scheduler_classification": "none",
        "scheduler_elapsed_seconds": "none",
    }
    if evidence is None:
        payload.update({field: "none" for field in FAILED_QUALITY_FIELDS})
    else:
        payload.update(
            {
                "train_exact": evidence.train_exact,
                "visible_cv_exact": evidence.visible_cv_exact,
                "visible_cv_bit_accuracy": evidence.visible_cv_bit_accuracy,
                "gates": evidence.gates,
                "completed_table_sha256": evidence.completed_table_sha256,
                "circuit_sha256": evidence.circuit_sha256,
                "artifact_sha256": evidence.artifact_sha256,
                "artifact_path": evidence.artifact_path,
            }
        )
    return payload


def atomic_write(path: Path, data: bytes) -> None:
    temporary: Path | None = None
    descriptor: int | None = None
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
    )
    for _ in range(16):
        candidate = path.with_name(
            f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(16)}"
        )
        try:
            descriptor = os.open(candidate, flags, 0o600)
        except FileExistsError:
            continue
        temporary = candidate
        break
    if temporary is None or descriptor is None:
        raise ValidationError(f"cannot reserve atomic temporary for {path.name}")
    try:
        try:
            remaining = memoryview(data)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise OSError("atomic temporary write made no progress")
                remaining = remaining[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, path)
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
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--cell-id", required=True)
    parser.add_argument("--metrics-json", required=True, type=Path)
    parser.add_argument("--container-provenance", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command[:1] == ["--"]:
        args.command = args.command[1:]
    return args


def main() -> int:
    args = parse_args()
    try:
        prepared = prepare_run(args)
    except (OSError, ValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    result = run_child(prepared)
    verifier = "not_run"
    evidence = None
    if result.status == "INVALID_METRICS":
        status, exit_code, verifier, evidence = classify_zero_exit(prepared)
        result = RunResult(
            status=status,
            exit_code=exit_code,
            timed_out=False,
            elapsed_seconds=result.elapsed_seconds,
            cleanup_seconds=result.cleanup_seconds,
            peak_memory_kib=result.peak_memory_kib,
            started_utc=result.started_utc,
            ended_utc=result.ended_utc,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    manifest = terminal_manifest(prepared, result, verifier, evidence)
    atomic_write(prepared.cell_dir / "manifest.json", canonical_json_bytes(manifest))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
