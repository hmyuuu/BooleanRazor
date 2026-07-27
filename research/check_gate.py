#!/usr/bin/env python3
"""Fail-closed gate for the proposer-visible blind-baseline protocol."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


SOLUTION_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / ".knowledge").is_dir()
)
RESEARCH_ROOT = SOLUTION_ROOT / "research"
REBLIND_ROOT = SOLUTION_ROOT / "reblind"

BASELINES_HEADER = (
    "comparison_id,role,method,method_version,blind,evaluation_scope,source_commit,"
    "runner_commit,tree_digest,image_sha256,compiler_digest,hardware,dataset_id,tier,"
    "observation_fraction,algorithm_seed,repeat,timeout_seconds,status,exit_code,timed_out,"
    "train_exact,visible_cv_exact,visible_cv_bit_accuracy,gates,elapsed_seconds,"
    "peak_memory_kib,verifier,artifact_sha256,manifest_sha256,evidence_path"
)
MATRIX_HEADER = (
    "comparison_id,method,method_version,dataset_id,tier,observation_fraction,"
    "algorithm_seed,repeat,timeout_seconds,hardware"
)
PUBLIC_MANIFEST_HEADER = "opaque_id,input_bits,output_bits,train_rows,test_policy,observed_fraction,public_sha256"
FROZEN_METHODS = {"zero-fill", "hamming-1nn"}
TERMINAL_STATES = {
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
FAILED_STATES = TERMINAL_STATES - {"SUCCESS"}
SEALED_TOKENS = {
    "family",
    "generator",
    "secret_seed",
    "label",
    "sealed",
    "ground_truth",
    "test_outputs",
    "test_exact",
    "sealed_accuracy",
    "official_aggregate",
}
SURVEY_SECTIONS = {
    "partial mcsp / occam learning",
    "bdd ordering",
    "exact sat synthesis",
    "xag / logic synthesis",
    "arithmetic circuits",
    "tt / mps completion",
    "available software",
    "reproduced baselines",
    "unresolved gap",
}
SOURCE_ROOTS = (
    ".knowledge/literature/boolean-logic-synthesis/",
    ".knowledge/literature/mps-based-algorithm/",
)
HEX_64 = re.compile(r"[0-9a-f]{64}")
COMMIT_HASH = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
OPAQUE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
SOURCE_PATH = re.compile(r"`(\.knowledge/literature/[^`]+\.md)`")
CANONICAL_INTEGER = re.compile(r"(?:0|[1-9][0-9]*)")
CANONICAL_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]+")
CELL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
RFC3339_UTC = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?Z"
)
RAW_EXIT_CODE = re.compile(
    r"((?:0|[1-9][0-9]*)):((?:0|[1-9][0-9]*))"
)
BASELINE_FIELDS = set(BASELINES_HEADER.split(","))
MANIFEST_ROW_FIELDS = BASELINE_FIELDS - {"manifest_sha256", "evidence_path"}
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
MANIFEST_OPERATIONAL_FIELDS = {
    "schema_version",
    "producer",
    "run_spec_sha256",
    "argv",
    "started_utc",
    "ended_utc",
    "stdout_sha256",
    "stderr_sha256",
    "scheduler_job_id",
    "scheduler_task_index",
    "scheduler_state",
    "scheduler_exit_code",
    "scheduler_classification",
    "scheduler_elapsed_seconds",
    "cleanup_seconds",
    "scheduler_sha256",
    "log_sha256",
}
MANIFEST_REQUIRED_FIELDS = (
    MANIFEST_ROW_FIELDS
    | {
        "artifact_path",
        "completed_table_sha256",
        "circuit_sha256",
    }
    | MANIFEST_OPERATIONAL_FIELDS
)
MANIFEST_ALLOWED_FIELDS = MANIFEST_REQUIRED_FIELDS
RUNNER_STATES = {
    "SUCCESS",
    "TIMEOUT",
    "NONZERO_EXIT",
    "INVALID_METRICS",
    "VERIFIER_FAILED",
    "VERIFIER_NOT_RUN",
}
SCHEDULER_STATES = {
    "TIMEOUT",
    "OOM",
    "NONZERO_EXIT",
    "CANCELLED",
    "MISSING_SUCCESS_MANIFEST",
}
SCHEDULER_STATE_BY_STATUS = {
    "TIMEOUT": "TIMEOUT",
    "OOM": "OUT_OF_MEMORY",
    "NONZERO_EXIT": "FAILED",
    "CANCELLED": "CANCELLED",
    "MISSING_SUCCESS_MANIFEST": "COMPLETED",
}


def missing(path: Path) -> str:
    return f"missing research artifact: {path.relative_to(SOLUTION_ROOT)}"


def display_path(path: Path) -> Path:
    try:
        return path.relative_to(SOLUTION_ROOT)
    except ValueError:
        return path


def read_csv(
    path: Path, expected_header: str, errors: list[str]
) -> list[dict[str, str]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        errors.append(f"cannot read {display_path(path)}: {exc}")
        return []
    label = display_path(path)
    if b"\r" in raw or not raw.endswith(b"\n"):
        errors.append(f"{label} is not canonical LF-terminated CSV")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(f"{label} is not UTF-8")
        return []
    lines = text.splitlines()
    if not lines or lines[0] != expected_header:
        errors.append(f"{label} has the wrong header")
        return []
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        rows = list(reader)
    except csv.Error as exc:
        errors.append(f"{label} is malformed CSV: {exc}")
        return []
    if reader.fieldnames != expected_header.split(","):
        errors.append(f"{label} has noncanonical columns")
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        errors.append(f"{label} has a malformed row width")
    return rows


def check_survey(path: Path, errors: list[str]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"cannot read research/SURVEY.md: {exc}")
        return
    headings = {
        match.group(1).strip().lower()
        for match in re.finditer(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE)
    }
    for section in SURVEY_SECTIONS - headings:
        errors.append(f"SURVEY.md is missing section: {section}")

    source_claims = re.findall(
        r"(?ms)^- \*\*Source claim\.\*\*.*?(?=^\s*-\s|^##\s|\Z)",
        text,
    )
    if not source_claims:
        errors.append("SURVEY.md has no marked source claims")
    for claim_number, claim in enumerate(source_claims, start=1):
        if not SOURCE_PATH.findall(claim):
            errors.append(
                f"SURVEY.md source claim {claim_number} has no rendered-file citation"
            )
    for line_number, line in enumerate(text.splitlines(), start=1):
        citations = SOURCE_PATH.findall(line)
        for citation in citations:
            if not citation.startswith(SOURCE_ROOTS):
                errors.append(
                    f"SURVEY.md:{line_number} cites a disallowed literature root"
                )
            elif not (REPO_ROOT / citation).is_file():
                errors.append(
                    f"SURVEY.md:{line_number} cites missing rendered file: {citation}"
                )


def check_commitment(path: Path, errors: list[str]) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        errors.append(f"cannot read reblind/COMMITMENT.txt: {exc}")
        return None
    if b"\r" in raw:
        errors.append("COMMITMENT.txt contains CR bytes")
    text = raw.decode("ascii", errors="replace")
    if text not in {text.strip(), text.strip() + "\n"} or not HEX_64.fullmatch(
        text.strip()
    ):
        errors.append("COMMITMENT.txt must contain one lowercase 64-hex SHA-256 value")
        return None
    return text.strip()


def check_public_manifest(path: Path, errors: list[str]) -> dict[str, dict[str, str]]:
    rows = read_csv(path, PUBLIC_MANIFEST_HEADER, errors)
    if len(rows) != 180:
        errors.append(f"reblind/manifest.csv has {len(rows)} rows, expected 180")
    headers = PUBLIC_MANIFEST_HEADER.split(",")
    for header in headers:
        lowered = header.lower()
        if any(token in lowered for token in SEALED_TOKENS):
            errors.append(f"reblind/manifest.csv exposes forbidden field: {header}")

    indexed: dict[str, dict[str, str]] = {}
    for row_number, row in enumerate(rows, start=2):
        opaque_id = row.get("opaque_id", "")
        if not OPAQUE_ID.fullmatch(opaque_id):
            errors.append(f"reblind/manifest.csv:{row_number} has invalid opaque_id")
        if opaque_id in indexed:
            errors.append(f"reblind/manifest.csv has duplicate opaque_id: {opaque_id}")
        indexed[opaque_id] = row
        try:
            input_bits = int(row.get("input_bits", ""))
            output_bits = int(row.get("output_bits", ""))
            train_rows = int(row.get("train_rows", ""))
            fraction = row.get("observed_fraction", "")
            if input_bits not in {12, 16, 20} or output_bits != input_bits + 1:
                raise ValueError
            if train_rows <= 0 or train_rows >= 1 << input_bits:
                raise ValueError
            if fraction not in {"0.03", "0.10"}:
                raise ValueError
        except ValueError:
            errors.append(
                f"reblind/manifest.csv:{row_number} has invalid shape/fraction"
            )
        if row.get("test_policy") != "all-unobserved":
            errors.append(f"reblind/manifest.csv:{row_number} has invalid test_policy")
        if not HEX_64.fullmatch(row.get("public_sha256", "")):
            errors.append(
                f"reblind/manifest.csv:{row_number} has invalid public_sha256"
            )
    return indexed


def canonical_csv_bytes(header: str, rows: list[dict[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=header.split(","),
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def check_matrix(
    path: Path,
    digest_path: Path,
    commitment: str | None,
    manifest: dict[str, dict[str, str]],
    errors: list[str],
) -> list[dict[str, str]]:
    rows = read_csv(path, MATRIX_HEADER, errors)
    try:
        raw = path.read_bytes()
    except OSError:
        raw = b""
    if rows and raw != canonical_csv_bytes(MATRIX_HEADER, rows):
        errors.append("research/BASELINE_MATRIX.csv is not canonical CSV")
    try:
        declared_digest = digest_path.read_text(encoding="ascii").strip()
    except OSError as exc:
        errors.append(f"cannot read research/BASELINE_MATRIX.sha256: {exc}")
    else:
        actual_digest = hashlib.sha256(raw).hexdigest()
        if not HEX_64.fullmatch(declared_digest) or declared_digest != actual_digest:
            errors.append(
                "BASELINE_MATRIX.sha256 does not match canonical matrix bytes"
            )

    if len(rows) != 360:
        errors.append(f"BASELINE_MATRIX.csv has {len(rows)} rows, expected 360")
    keys: set[tuple[str, str]] = set()
    comparison_ids: set[str] = set()
    hardware_cards: set[str] = set()
    previous_key: tuple[str, str] | None = None
    for row_number, row in enumerate(rows, start=2):
        method = row.get("method", "")
        opaque_id = row.get("dataset_id", "")
        key = (method, opaque_id)
        if previous_key is not None and key <= previous_key:
            errors.append(f"BASELINE_MATRIX.csv:{row_number} is not canonically sorted")
        previous_key = key
        if key in keys:
            errors.append(
                f"BASELINE_MATRIX.csv has duplicate key: {method}/{opaque_id}"
            )
        keys.add(key)
        comparison_id = row.get("comparison_id", "")
        if not comparison_id or comparison_id in comparison_ids:
            errors.append(f"BASELINE_MATRIX.csv:{row_number} has invalid comparison_id")
        comparison_ids.add(comparison_id)
        hardware_cards.add(row.get("hardware", ""))
        if method not in FROZEN_METHODS or row.get("method_version") != "1":
            errors.append(
                f"BASELINE_MATRIX.csv:{row_number} has unknown method/version"
            )
        public = manifest.get(opaque_id)
        if public is None:
            errors.append(f"BASELINE_MATRIX.csv:{row_number} has unknown dataset_id")
        else:
            expected_tier = f"n={int(public['input_bits']) // 2}"
            if row.get("tier") != expected_tier:
                errors.append(f"BASELINE_MATRIX.csv:{row_number} has wrong tier")
            if row.get("observation_fraction") != public["observed_fraction"]:
                errors.append(f"BASELINE_MATRIX.csv:{row_number} has wrong fraction")
        expected_seed = (
            hashlib.sha256(f"{commitment}{method}{opaque_id}".encode()).hexdigest()
            if commitment is not None
            else None
        )
        if expected_seed is not None and row.get("algorithm_seed") != expected_seed:
            errors.append(f"BASELINE_MATRIX.csv:{row_number} has wrong algorithm_seed")
        if row.get("repeat") != "0" or row.get("timeout_seconds") != "300":
            errors.append(f"BASELINE_MATRIX.csv:{row_number} has wrong repeat/timeout")
    expected_keys = {
        (method, opaque_id) for method in FROZEN_METHODS for opaque_id in manifest
    }
    if keys != expected_keys:
        errors.append("BASELINE_MATRIX.csv is not the exact method × manifest product")
    if hardware_cards == {""} or len(hardware_cards) != 1:
        errors.append(
            "BASELINE_MATRIX.csv must declare exactly one nonblank hardware card"
        )
    return rows


def forbidden_key(value: object) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in SEALED_TOKENS):
                return str(key)
            nested = forbidden_key(child)
            if nested is not None:
                return nested
    elif isinstance(value, list):
        for child in value:
            nested = forbidden_key(child)
            if nested is not None:
                return nested
    return None


def scalar_text(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    return None


def read_json_object(
    path: Path, label: str, errors: list[str]
) -> dict[str, object] | None:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        errors.append(f"{label} cannot be read: {exc}")
        return None
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        errors.append(f"{label} is not valid UTF-8 JSON")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label} must be a JSON object")
        return None
    return value


def check_manifest_schema(
    payload: dict[str, object], label: str, errors: list[str]
) -> dict[str, str]:
    forbidden = forbidden_key(payload)
    if forbidden is not None:
        errors.append(f"{label} contains forbidden key: {forbidden}")
    missing_fields = sorted(MANIFEST_REQUIRED_FIELDS - set(payload))
    extra_fields = sorted(set(payload) - MANIFEST_ALLOWED_FIELDS)
    if missing_fields or extra_fields:
        details = []
        if missing_fields:
            details.append(f"missing={','.join(missing_fields)}")
        if extra_fields:
            details.append(f"extra={','.join(extra_fields)}")
        errors.append(f"{label} violates manifest schema ({'; '.join(details)})")
    row: dict[str, str] = {}
    for field in MANIFEST_ROW_FIELDS:
        if field not in payload:
            continue
        if not isinstance(payload[field], str):
            errors.append(f"{label} field {field} must be a canonical string")
        else:
            row[field] = payload[field]
    if payload.get("schema_version") != 1:
        errors.append(f"{label} schema_version must equal integer 1")
    if payload.get("producer") not in {"runner", "scheduler"}:
        errors.append(f"{label} has invalid producer")
    argv = payload.get("argv")
    if not isinstance(argv, list) or any(not isinstance(value, str) for value in argv):
        errors.append(f"{label} argv must be a string array")
    return row


def canonical_decimal(
    value: str,
    field: str,
    label: str,
    errors: list[str],
    *,
    maximum: Decimal | None = None,
) -> Decimal | None:
    if not CANONICAL_DECIMAL.fullmatch(value):
        errors.append(f"{label} has noncanonical {field}")
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        errors.append(f"{label} has invalid {field}")
        return None
    if (
        not number.is_finite()
        or number < 0
        or (maximum is not None and number > maximum)
    ):
        errors.append(f"{label} has out-of-range {field}")
        return None
    canonical = format(number.normalize(), "f")
    if "." not in canonical:
        canonical += ".0"
    if value != canonical:
        errors.append(f"{label} has noncanonical {field}")
        return None
    return number


def canonical_integer(
    value: str, field: str, label: str, errors: list[str]
) -> int | None:
    if not CANONICAL_INTEGER.fullmatch(value):
        errors.append(f"{label} has noncanonical {field}")
        return None
    return int(value)


def canonical_timeout(
    value: str, field: str, label: str, errors: list[str]
) -> Decimal | None:
    if CANONICAL_INTEGER.fullmatch(value):
        number = Decimal(value)
    elif CANONICAL_DECIMAL.fullmatch(value):
        try:
            number = Decimal(value)
        except InvalidOperation:
            errors.append(f"{label} has invalid {field}")
            return None
        canonical = format(number.normalize(), "f")
        if "." not in canonical:
            canonical += ".0"
        if value != canonical:
            errors.append(f"{label} has noncanonical {field}")
            return None
    else:
        errors.append(f"{label} has noncanonical {field}")
        return None
    if not number.is_finite() or number <= 0 or number > Decimal(300):
        errors.append(f"{label} has out-of-range {field}")
        return None
    return number


def check_terminal_metrics(row: dict[str, str], label: str, errors: list[str]) -> None:
    status = row.get("status", "")
    if status not in TERMINAL_STATES:
        errors.append(f"{label} has nonterminal status")
        return
    expected_verifier = (
        "pass"
        if status == "SUCCESS"
        else "fail"
        if status == "VERIFIER_FAILED"
        else "not_run"
    )
    if row.get("verifier") != expected_verifier:
        errors.append(f"{label} {status} requires verifier={expected_verifier}")
    if row.get("timed_out") not in {"true", "false"}:
        errors.append(f"{label} has invalid timed_out")
    timeout = canonical_timeout(
        row.get("timeout_seconds", ""), "timeout_seconds", label, errors
    )
    expected_exit = {
        "SUCCESS": "0",
        "TIMEOUT": "124",
        "OOM": "137",
        "INVALID_METRICS": "65",
        "VERIFIER_FAILED": "66",
        "VERIFIER_NOT_RUN": "67",
        "CANCELLED": "130",
        "MISSING_SUCCESS_MANIFEST": "70",
    }.get(status)
    if expected_exit is not None and row.get("exit_code") != expected_exit:
        errors.append(f"{label} {status} has inconsistent exit_code")
    if status == "NONZERO_EXIT":
        exit_code = canonical_integer(
            row.get("exit_code", ""), "exit_code", label, errors
        )
        if exit_code == 0:
            errors.append(f"{label} NONZERO_EXIT has zero exit_code")
    if status == "SUCCESS":
        if row.get("exit_code") != "0" or row.get("timed_out") != "false":
            errors.append(f"{label} SUCCESS has inconsistent process status")
        if not HEX_64.fullmatch(row.get("artifact_sha256", "")):
            errors.append(f"{label} SUCCESS has invalid artifact hash")
        if row.get("train_exact") != "1.0":
            errors.append(f"{label} train_exact must equal 1.0")
        for field in ("visible_cv_exact", "visible_cv_bit_accuracy"):
            canonical_decimal(
                row.get(field, ""), field, label, errors, maximum=Decimal(1)
            )
        canonical_integer(row.get("gates", ""), "gates", label, errors)
        elapsed = canonical_decimal(
            row.get("elapsed_seconds", ""), "elapsed_seconds", label, errors
        )
        if elapsed is not None and timeout is not None and elapsed > timeout:
            errors.append(f"{label} elapsed_seconds exceeds timeout_seconds")
        canonical_integer(
            row.get("peak_memory_kib", ""), "peak_memory_kib", label, errors
        )
    else:
        for field in (
            "train_exact",
            "visible_cv_exact",
            "visible_cv_bit_accuracy",
            "gates",
            "artifact_sha256",
        ):
            if row.get(field) != "none":
                errors.append(f"{label} failed row must set {field}=none")
        if status == "TIMEOUT" and row.get("timed_out") != "true":
            errors.append(f"{label} TIMEOUT must set timed_out=true")
        if status != "TIMEOUT" and row.get("timed_out") != "false":
            errors.append(f"{label} non-timeout failure sets timed_out")
        elapsed_text = row.get("elapsed_seconds", "")
        if status == "TIMEOUT" and elapsed_text == "none":
            errors.append(f"{label} TIMEOUT must record the declared censored cap")
        elif elapsed_text != "none":
            elapsed = canonical_decimal(elapsed_text, "elapsed_seconds", label, errors)
            if elapsed is not None and timeout is not None and elapsed > timeout:
                errors.append(f"{label} elapsed_seconds exceeds timeout_seconds")
            if (
                status == "TIMEOUT"
                and elapsed is not None
                and timeout is not None
                and elapsed != timeout
            ):
                errors.append(f"{label} TIMEOUT must record the declared censored cap")
        peak_text = row.get("peak_memory_kib", "")
        if peak_text != "none":
            canonical_integer(peak_text, "peak_memory_kib", label, errors)


def check_execution_row(
    row: dict[str, str], label: str, errors: list[str]
) -> None:
    if any(row.get(field, "") == "" for field in MANIFEST_ROW_FIELDS):
        errors.append(f"{label} contains a blank row field")
    if row.get("role") not in {"baseline", "candidate"}:
        errors.append(f"{label} has invalid role")
    if (
        row.get("blind") != "true"
        or row.get("evaluation_scope") != "visible_cv_only"
    ):
        errors.append(f"{label} violates blind visible-CV scope")
    for field in ("source_commit", "runner_commit"):
        if not COMMIT_HASH.fullmatch(row.get(field, "")):
            errors.append(f"{label} has invalid {field}")
    if not HEX_64.fullmatch(row.get("tree_digest", "")):
        errors.append(f"{label} has invalid tree_digest")
    for field in ("image_sha256", "compiler_digest"):
        value = row.get(field, "")
        if value != "none" and not HEX_64.fullmatch(value):
            errors.append(f"{label} has invalid {field}")
    check_terminal_metrics(row, label, errors)


def results_path(value: str, label: str, errors: list[str]) -> Path | None:
    raw = Path(value)
    results_root = (REPO_ROOT / "results").resolve()
    if raw.is_absolute():
        errors.append(f"{label} must be repository-relative under results")
        return None
    resolved = (REPO_ROOT / raw).resolve()
    if not resolved.is_relative_to(results_root):
        errors.append(f"{label} must be repository-relative under results")
        return None
    return resolved


def check_baseline_evidence(
    row: dict[str, str], errors: list[str], *, label: str
) -> None:
    evidence = results_path(
        row.get("evidence_path", ""), f"{label} evidence_path", errors
    )
    if evidence is None:
        return
    if not evidence.is_file():
        errors.append(f"{label} references missing evidence")
        return
    raw = evidence.read_bytes()
    if hashlib.sha256(raw).hexdigest() != row.get("manifest_sha256"):
        errors.append(f"{label} evidence hash mismatch")
    payload = read_json_object(evidence, f"{label} evidence", errors)
    if payload is None:
        return
    if raw != canonical_json_bytes(payload):
        errors.append(f"{label} evidence is not canonical compact sorted-key JSON")
    evidence_row = check_manifest_schema(payload, f"{label} evidence", errors)
    for field in MANIFEST_ROW_FIELDS:
        if evidence_row.get(field) != row.get(field):
            errors.append(f"{label} evidence disagrees on {field}")
    if (
        evidence.name != "manifest.json"
        or evidence.parent.name != row.get("comparison_id")
        or evidence.parent.parent.name != "cells"
    ):
        errors.append(f"{label} evidence is not at the native cell manifest path")
        return
    run = evidence.parents[2]
    run_spec_path = run / "run_spec.json"
    run_spec_raw = regular_bytes(
        run_spec_path, f"{label} evidence run_spec.json", errors
    )
    if run_spec_raw is None:
        return
    try:
        run_spec = json.loads(run_spec_raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        errors.append(f"{label} evidence run_spec.json is not valid JSON")
        return
    if not isinstance(run_spec, dict):
        errors.append(f"{label} evidence run_spec.json must be an object")
        return
    if run_spec_raw != canonical_json_bytes(run_spec):
        errors.append(f"{label} evidence run_spec.json is not canonical")
    if set(run_spec) != {"schema_version", "cells", "provenance"}:
        errors.append(f"{label} evidence run_spec.json has the wrong schema")
    cells = native_cells(run_spec, f"{label} evidence run_spec.json", errors)
    provenance = check_provenance(
        run_spec.get("provenance"),
        f"{label} evidence run_spec.json provenance",
        errors,
    )
    comparison_id = row.get("comparison_id", "")
    run_params = cells.get(comparison_id)
    if run_params is None or any(
        evidence_row.get(field) != run_params.get(field) for field in PARAM_FIELDS
    ):
        errors.append(f"{label} evidence disagrees with run_spec params")
    if any(
        evidence_row.get(field) != provenance.get(field)
        for field in PROVENANCE_FIELDS
    ):
        errors.append(f"{label} evidence disagrees with run_spec provenance")
    expected_task_index = (
        list(cells).index(comparison_id) + 1 if comparison_id in cells else None
    )
    check_execution_row(evidence_row, f"{label} evidence", errors)
    check_operational_metadata(
        run,
        payload,
        evidence_row,
        f"{label} evidence",
        hashlib.sha256(run_spec_raw).hexdigest(),
        errors,
        expected_task_index=expected_task_index,
    )
    check_native_artifacts(run, payload, evidence_row, f"{label} evidence", errors)


def check_baseline_rows(
    rows: list[dict[str, str]],
    matrix_rows: list[dict[str, str]],
    errors: list[str],
    *,
    label: str = "BASELINES.csv",
    validate_evidence: bool = False,
) -> None:
    matrix = {row["comparison_id"]: row for row in matrix_rows}
    actual: set[str] = set()
    frozen_provenance: dict[tuple[str, str], tuple[str, ...]] = {}
    for row_number, row in enumerate(rows, start=2):
        if any(value == "" for value in row.values()):
            errors.append(f"{label}:{row_number} contains a blank field")
        comparison_id = row.get("comparison_id", "")
        if comparison_id in actual:
            errors.append(f"{label} has duplicate comparison_id: {comparison_id}")
        actual.add(comparison_id)
        expected = matrix.get(comparison_id)
        if expected is None:
            errors.append(f"{label}:{row_number} is not declared by the matrix")
        else:
            for field in (
                "method",
                "method_version",
                "hardware",
                "dataset_id",
                "tier",
                "observation_fraction",
                "algorithm_seed",
                "repeat",
                "timeout_seconds",
            ):
                if row.get(field) != expected.get(field):
                    errors.append(
                        f"{label}:{row_number} does not match matrix field {field}"
                    )
        if row.get("role") != "baseline":
            errors.append(f"{label}:{row_number} role must be baseline")
        if (
            row.get("blind") != "true"
            or row.get("evaluation_scope") != "visible_cv_only"
        ):
            errors.append(f"{label}:{row_number} violates blind visible-CV scope")
        for field in ("source_commit", "runner_commit"):
            if not COMMIT_HASH.fullmatch(row.get(field, "")):
                errors.append(f"{label}:{row_number} has invalid {field}")
        if not HEX_64.fullmatch(row.get("tree_digest", "")):
            errors.append(f"{label}:{row_number} has invalid tree_digest")
        for field in ("image_sha256", "compiler_digest"):
            value = row.get(field, "")
            if value != "none" and not HEX_64.fullmatch(value):
                errors.append(f"{label}:{row_number} has invalid {field}")
        provenance_key = (row.get("method", ""), row.get("method_version", ""))
        provenance = tuple(
            row.get(field, "")
            for field in (
                "source_commit",
                "runner_commit",
                "tree_digest",
                "image_sha256",
                "compiler_digest",
            )
        )
        previous_provenance = frozen_provenance.setdefault(provenance_key, provenance)
        if provenance != previous_provenance:
            errors.append(f"{label}:{row_number} changes frozen method provenance")
        check_terminal_metrics(row, f"{label}:{row_number}", errors)
        if not HEX_64.fullmatch(row.get("manifest_sha256", "")):
            errors.append(f"{label}:{row_number} has invalid manifest_sha256")
        if validate_evidence:
            check_baseline_evidence(row, errors, label=f"{label}:{row_number}")
    if actual != set(matrix):
        errors.append(f"{label} is not the exact matrix result set")


def check_protocol(phase: str) -> list[str]:
    errors: list[str] = []
    required = [
        RESEARCH_ROOT / "SURVEY.md",
        RESEARCH_ROOT / "BASELINE_MATRIX.csv",
        RESEARCH_ROOT / "BASELINE_MATRIX.sha256",
        RESEARCH_ROOT / "BASELINES.csv",
        REBLIND_ROOT / "COMMITMENT.txt",
        REBLIND_ROOT / "manifest.csv",
    ]
    for path in required:
        if not path.is_file():
            errors.append(missing(path))

    survey = RESEARCH_ROOT / "SURVEY.md"
    if survey.is_file():
        check_survey(survey, errors)
    baselines_path = RESEARCH_ROOT / "BASELINES.csv"
    baseline_rows = (
        read_csv(baselines_path, BASELINES_HEADER, errors)
        if baselines_path.is_file()
        else []
    )
    commitment_path = REBLIND_ROOT / "COMMITMENT.txt"
    commitment = (
        check_commitment(commitment_path, errors) if commitment_path.is_file() else None
    )
    manifest_path = REBLIND_ROOT / "manifest.csv"
    manifest = (
        check_public_manifest(manifest_path, errors) if manifest_path.is_file() else {}
    )
    matrix_path = RESEARCH_ROOT / "BASELINE_MATRIX.csv"
    digest_path = RESEARCH_ROOT / "BASELINE_MATRIX.sha256"
    matrix_rows = (
        check_matrix(matrix_path, digest_path, commitment, manifest, errors)
        if matrix_path.is_file() and digest_path.is_file()
        else []
    )
    if phase == "protocol" and baseline_rows:
        errors.append("BASELINES.csv must be header-only during protocol phase")
    if phase == "baseline":
        check_baseline_rows(baseline_rows, matrix_rows, errors, validate_evidence=True)
    return sorted(set(errors))


def expected_spec_path(path: Path, errors: list[str]) -> Path | None:
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        errors.append(f"expected spec does not exist: {path}")
        return None
    research = RESEARCH_ROOT.resolve()
    if not resolved.is_file() or not resolved.is_relative_to(research):
        errors.append("expected spec must resolve to an existing file under research")
        return None
    return resolved


def native_cells(
    spec: dict[str, object], label: str, errors: list[str]
) -> dict[str, dict[str, str]]:
    cells = spec.get("cells")
    if not isinstance(cells, list):
        errors.append(f"{label} must contain a cells array")
        return {}
    if not cells:
        errors.append(f"{label} must contain at least one cell")
    indexed: dict[str, dict[str, str]] = {}
    for index, cell in enumerate(cells):
        cell_label = f"{label} cells[{index}]"
        if not isinstance(cell, dict) or set(cell) != {"cell_id", "params"}:
            errors.append(
                f"{cell_label} must contain exactly cell_id and params"
            )
            continue
        cell_id = cell.get("cell_id")
        params = cell.get("params")
        if not isinstance(cell_id, str) or not CELL_ID.fullmatch(cell_id):
            errors.append(f"{cell_label} has invalid cell_id")
            continue
        if cell_id in indexed:
            errors.append(f"{label} has duplicate cell_id: {cell_id}")
            continue
        if not isinstance(params, dict):
            errors.append(f"{cell_label} must contain an object params")
            continue
        missing_params = sorted(PARAM_FIELDS - set(params))
        extra_params = sorted(set(params) - PARAM_FIELDS)
        if missing_params or extra_params:
            details = []
            if missing_params:
                details.append(f"missing={','.join(missing_params)}")
            if extra_params:
                details.append(f"extra={','.join(extra_params)}")
            errors.append(
                f"{cell_label} params violate schema ({'; '.join(details)})"
            )
        if any(not isinstance(value, str) for value in params.values()):
            errors.append(f"{cell_label} params values must be canonical strings")
            continue
        canonical_params = {str(key): value for key, value in params.items()}
        if canonical_params.get("comparison_id") != cell_id:
            errors.append(f"{cell_label} params comparison_id differs from cell_id")
        if canonical_params.get("role") not in {"baseline", "candidate"}:
            errors.append(f"{cell_label} params has invalid role")
        if (
            canonical_params.get("blind") != "true"
            or canonical_params.get("evaluation_scope") != "visible_cv_only"
        ):
            errors.append(f"{cell_label} params violate blind visible-CV scope")
        if not HEX_64.fullmatch(canonical_params.get("algorithm_seed", "")):
            errors.append(f"{cell_label} params has invalid algorithm_seed")
        canonical_integer(
            canonical_params.get("repeat", ""), "repeat", cell_label, errors
        )
        canonical_timeout(
            canonical_params.get("timeout_seconds", ""),
            "timeout_seconds",
            cell_label,
            errors,
        )
        for field in PARAM_FIELDS - {
            "algorithm_seed",
            "repeat",
            "timeout_seconds",
        }:
            if canonical_params.get(field, "") == "":
                errors.append(f"{cell_label} params has blank {field}")
        indexed[cell_id] = canonical_params
    return indexed


def check_provenance(
    value: object, label: str, errors: list[str]
) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != PROVENANCE_FIELDS:
        errors.append(f"{label} must contain exactly the five provenance fields")
        return {}
    if any(not isinstance(item, str) for item in value.values()):
        errors.append(f"{label} values must be canonical strings")
        return {}
    provenance = {str(key): item for key, item in value.items()}
    for field in ("source_commit", "runner_commit"):
        if not COMMIT_HASH.fullmatch(provenance[field]):
            errors.append(f"{label} has invalid {field}")
    if not HEX_64.fullmatch(provenance["tree_digest"]):
        errors.append(f"{label} has invalid tree_digest")
    for field in ("image_sha256", "compiler_digest"):
        item = provenance[field]
        if item != "none" and not HEX_64.fullmatch(item):
            errors.append(f"{label} has invalid {field}")
    return provenance


def regular_bytes(path: Path, label: str, errors: list[str]) -> bytes | None:
    if path.is_symlink() or not path.is_file():
        errors.append(f"{label} must be an existing regular file, not a symlink")
        return None
    try:
        return path.read_bytes()
    except OSError as exc:
        errors.append(f"{label} cannot be read: {exc}")
        return None


def check_timestamp(value: object, field: str, label: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not RFC3339_UTC.fullmatch(value):
        errors.append(f"{label} has invalid {field}")
        return
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        errors.append(f"{label} has invalid {field}")


def check_operational_metadata(
    run: Path,
    payload: dict[str, object],
    row: dict[str, str],
    label: str,
    run_spec_sha256: str,
    errors: list[str],
    *,
    expected_task_index: int | None = None,
) -> None:
    if payload.get("run_spec_sha256") != run_spec_sha256:
        errors.append(f"{label} run_spec_sha256 does not match frozen run spec")
    producer = payload.get("producer")
    argv = payload.get("argv")
    cell_id = row.get("comparison_id", "")
    if producer == "runner":
        if not isinstance(argv, list) or not argv or any(
            not isinstance(value, str) for value in argv
        ):
            errors.append(f"{label} runner argv must be a nonempty string array")
        check_timestamp(payload.get("started_utc"), "started_utc", label, errors)
        check_timestamp(payload.get("ended_utc"), "ended_utc", label, errors)
        if row.get("status") not in RUNNER_STATES:
            errors.append(f"{label} runner cannot emit {row.get('status', '')}")
        runner_scheduler_fields = (
            "scheduler_sha256",
            "scheduler_job_id",
            "scheduler_task_index",
            "scheduler_state",
            "scheduler_exit_code",
            "scheduler_classification",
            "scheduler_elapsed_seconds",
        )
        if any(payload.get(field) != "none" for field in runner_scheduler_fields):
            errors.append(f"{label} runner scheduler fields must all equal none")
        cleanup_text = scalar_text(payload.get("cleanup_seconds")) or ""
        if row.get("status") == "TIMEOUT":
            if (
                canonical_decimal(
                    cleanup_text,
                    "cleanup_seconds",
                    label,
                    errors,
                )
                is None
            ):
                errors.append(
                    f"{label} timeout cleanup_seconds must be measured, canonical, "
                    "and nonnegative"
                )
        elif cleanup_text != "0.0":
            errors.append(f"{label} non-timeout cleanup_seconds must equal 0.0")
        if row.get("elapsed_seconds") == "none":
            errors.append(f"{label} runner elapsed_seconds must be measured")
        cell = run / "cells" / cell_id
        stdout = regular_bytes(cell / "stdout.log", f"{label} stdout.log", errors)
        stderr = regular_bytes(cell / "stderr.log", f"{label} stderr.log", errors)
        if stdout is not None and payload.get("stdout_sha256") != hashlib.sha256(
            stdout
        ).hexdigest():
            errors.append(f"{label} stdout_sha256 does not match stdout.log")
        if stderr is not None and payload.get("stderr_sha256") != hashlib.sha256(
            stderr
        ).hexdigest():
            errors.append(f"{label} stderr_sha256 does not match stderr.log")
        if stdout is not None and stderr is not None:
            framed = (
                len(stdout).to_bytes(8, "big")
                + stdout
                + len(stderr).to_bytes(8, "big")
                + stderr
            )
            if payload.get("log_sha256") != hashlib.sha256(framed).hexdigest():
                errors.append(f"{label} log_sha256 does not match framed logs")
    elif producer == "scheduler":
        if argv != []:
            errors.append(f"{label} scheduler argv must be empty")
        if payload.get("started_utc") != "none" or payload.get("ended_utc") != "none":
            errors.append(f"{label} scheduler timestamps must equal none")
        if payload.get("cleanup_seconds") != "none":
            errors.append(f"{label} scheduler cleanup_seconds must equal none")
        status = row.get("status", "")
        if status not in SCHEDULER_STATES:
            errors.append(f"{label} scheduler cannot emit {status}")
        if not HEX_64.fullmatch(scalar_text(payload.get("scheduler_sha256")) or ""):
            errors.append(f"{label} scheduler_sha256 is invalid")
        job_id = scalar_text(payload.get("scheduler_job_id")) or ""
        task_index = scalar_text(payload.get("scheduler_task_index")) or ""
        if not re.fullmatch(r"[1-9][0-9]*", job_id):
            errors.append(f"{label} scheduler_job_id is invalid")
        if not re.fullmatch(r"[1-9][0-9]*", task_index):
            errors.append(f"{label} scheduler_task_index is invalid")
        elif (
            expected_task_index is not None
            and task_index != str(expected_task_index)
        ):
            errors.append(f"{label} scheduler ordered task index is inconsistent")
        expected_state = SCHEDULER_STATE_BY_STATUS.get(status)
        if payload.get("scheduler_state") != expected_state:
            errors.append(f"{label} scheduler state/classification is inconsistent")
        if payload.get("scheduler_classification") != status:
            errors.append(f"{label} scheduler state/classification is inconsistent")
        raw_exit = scalar_text(payload.get("scheduler_exit_code")) or ""
        match = RAW_EXIT_CODE.fullmatch(raw_exit)
        if match is None or any(int(value) > 255 for value in match.groups()):
            errors.append(f"{label} scheduler_exit_code is invalid")
        else:
            code, exit_signal = (int(value) for value in match.groups())
            if status == "MISSING_SUCCESS_MANIFEST" and (
                code != 0 or exit_signal != 0
            ):
                errors.append(f"{label} scheduler state/exit pair is inconsistent")
            if status == "NONZERO_EXIT":
                if code == 0 and exit_signal == 0:
                    errors.append(
                        f"{label} scheduler state/exit pair is inconsistent"
                    )
                normalized = code if code else 128 + exit_signal if exit_signal else 1
                if row.get("exit_code") != str(normalized):
                    errors.append(f"{label} scheduler NONZERO_EXIT is not normalized")
        elapsed_raw = scalar_text(payload.get("scheduler_elapsed_seconds")) or ""
        if not CANONICAL_INTEGER.fullmatch(elapsed_raw):
            errors.append(f"{label} scheduler_elapsed_seconds is invalid")
        elif status != "TIMEOUT" and row.get("elapsed_seconds") != f"{elapsed_raw}.0":
            errors.append(f"{label} scheduler elapsed evidence is inconsistent")
        if job_id and task_index:
            log_path = run / f"slurm-{job_id}_{task_index}.out"
            log = regular_bytes(log_path, f"{label} scheduler task log", errors)
            if log is not None:
                digest = hashlib.sha256(log).hexdigest()
                if payload.get("stdout_sha256") != digest:
                    errors.append(
                        f"{label} stdout_sha256 does not match scheduler task log"
                    )
                if payload.get("log_sha256") != digest:
                    errors.append(
                        f"{label} log_sha256 does not match scheduler task log"
                    )
                if payload.get("stderr_sha256") != "none":
                    errors.append(f"{label} scheduler stderr_sha256 must equal none")


def check_native_artifacts(
    run: Path,
    payload: dict[str, object],
    row: dict[str, str],
    label: str,
    errors: list[str],
) -> None:
    artifact_path = scalar_text(payload.get("artifact_path"))
    completed_digest = scalar_text(payload.get("completed_table_sha256"))
    circuit_digest = scalar_text(payload.get("circuit_sha256"))
    if row.get("status") != "SUCCESS":
        for field, value in (
            ("artifact_path", artifact_path),
            ("completed_table_sha256", completed_digest),
            ("circuit_sha256", circuit_digest),
        ):
            if value != "none":
                errors.append(f"{label} failed manifest must set {field}=none")
        return
    cell_id = row.get("comparison_id", "")
    expected_artifact_path = f"cells/{cell_id}/artifact.json"
    if artifact_path != expected_artifact_path:
        errors.append(f"{label} artifact_path is not the fixed in-cell index")
        return
    if not HEX_64.fullmatch(completed_digest or ""):
        errors.append(f"{label} SUCCESS has invalid completed table digest")
    if not HEX_64.fullmatch(circuit_digest or ""):
        errors.append(f"{label} SUCCESS has invalid circuit digest")
    cell = run / "cells" / cell_id
    artifact_raw = regular_bytes(cell / "artifact.json", f"{label} artifact.json", errors)
    if artifact_raw is None:
        return
    try:
        artifact = json.loads(artifact_raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        errors.append(f"{label} artifact.json is not valid UTF-8 JSON")
        return
    if not isinstance(artifact, dict):
        errors.append(f"{label} artifact.json must be an object")
        return
    if artifact_raw != canonical_json_bytes(artifact):
        errors.append(f"{label} artifact.json is not canonical")
    expected_fields = {
        "circuit_path",
        "circuit_sha256",
        "completed_table_path",
        "completed_table_sha256",
        "equivalence",
        "schema_version",
    }
    if set(artifact) != expected_fields:
        errors.append(f"{label} artifact.json has the wrong schema")
        return
    if (
        artifact.get("schema_version") != 1
        or artifact.get("circuit_path") != "circuit.txt"
        or artifact.get("completed_table_path") != "completed-table.csv"
    ):
        errors.append(f"{label} artifact.json has invalid fixed fields")
    if artifact.get("equivalence") != "pass":
        errors.append(f"{label} artifact equivalence must equal pass")
    if hashlib.sha256(artifact_raw).hexdigest() != row.get("artifact_sha256"):
        errors.append(f"{label} artifact index hash mismatch")
    if artifact.get("completed_table_sha256") != completed_digest:
        errors.append(f"{label} completed table digest disagrees with artifact index")
    if artifact.get("circuit_sha256") != circuit_digest:
        errors.append(f"{label} circuit digest disagrees with artifact index")
    table = regular_bytes(
        cell / "completed-table.csv", f"{label} completed-table.csv", errors
    )
    circuit = regular_bytes(cell / "circuit.txt", f"{label} circuit.txt", errors)
    if table is not None and hashlib.sha256(table).hexdigest() != completed_digest:
        errors.append(f"{label} completed table hash mismatch")
    if circuit is not None and hashlib.sha256(circuit).hexdigest() != circuit_digest:
        errors.append(f"{label} circuit hash mismatch")


def check_manifests(run: Path, expected_spec: Path) -> list[str]:
    errors: list[str] = []
    expected = expected_spec_path(expected_spec, errors)
    if expected is None:
        return sorted(set(errors))
    if not run.is_dir():
        return [f"run directory does not exist: {run}"]
    run_spec_path = run / "run_spec.json"
    if not run_spec_path.is_file():
        return ["run is missing run_spec.json"]
    run_spec = read_json_object(run_spec_path, "run_spec.json", errors)
    if run_spec is None:
        return sorted(set(errors))
    run_spec_raw = run_spec_path.read_bytes()
    if run_spec_raw != canonical_json_bytes(run_spec):
        errors.append("run_spec.json is not canonical compact sorted-key JSON")
    forbidden = forbidden_key(run_spec)
    if forbidden is not None:
        errors.append(f"run_spec.json contains forbidden key: {forbidden}")
    if set(run_spec) != {"schema_version", "cells", "provenance"}:
        errors.append(
            "run_spec.json must contain exactly schema_version, cells, and provenance"
        )
    if run_spec.get("schema_version") != 1:
        errors.append("run_spec.json schema_version must equal integer 1")
    cells = native_cells(run_spec, "run_spec.json", errors)
    provenance = check_provenance(
        run_spec.get("provenance"), "run_spec.json provenance", errors
    )

    if expected.suffix == ".json":
        expected_payload = read_json_object(expected, "expected JSON design spec", errors)
        if expected_payload is not None:
            expected_raw = expected.read_bytes()
            if expected_raw != canonical_json_bytes(expected_payload):
                errors.append("expected JSON design spec is not canonical")
            if set(expected_payload) != {"schema_version", "cells"}:
                errors.append(
                    "expected JSON design spec must contain exactly schema_version and cells"
                )
            if expected_payload.get("schema_version") != 1:
                errors.append("expected JSON design spec schema_version must equal 1")
            native_cells(expected_payload, "expected JSON design spec", errors)
            projection = {
                "schema_version": run_spec.get("schema_version"),
                "cells": run_spec.get("cells"),
            }
            if canonical_json_bytes(projection) != expected_raw:
                errors.append(
                    "run_spec.json design projection does not equal tracked design spec"
                )
    elif expected == (RESEARCH_ROOT / "BASELINE_MATRIX.csv").resolve():
        matrix_rows = read_csv(expected, MATRIX_HEADER, errors)
        if len(matrix_rows) != 360:
            errors.append(
                f"canonical BASELINE_MATRIX.csv must contain exactly 360 rows, got {len(matrix_rows)}"
            )
        expected_matrix = {row["comparison_id"]: row for row in matrix_rows}
        if len(expected_matrix) != len(matrix_rows):
            errors.append("canonical BASELINE_MATRIX.csv has duplicate comparison_id")
        if set(cells) != set(expected_matrix):
            errors.append("run_spec.json cells are not the exact baseline matrix cells")
        for cell_id in sorted(set(cells) & set(expected_matrix)):
            params = cells[cell_id]
            matrix_row = expected_matrix[cell_id]
            expected_params = {
                **matrix_row,
                "role": "baseline",
                "blind": "true",
                "evaluation_scope": "visible_cv_only",
            }
            if params != expected_params:
                errors.append(
                    f"run_spec.json cell {cell_id} params do not preserve matrix fields verbatim with fixed baseline fields"
                )
    else:
        errors.append(
            "expected spec must be JSON or the canonical research/BASELINE_MATRIX.csv"
        )

    actual_manifests = (
        set((run / "cells").glob("**/manifest.json"))
        if (run / "cells").is_dir()
        else set()
    )
    expected_manifests = {
        run / "cells" / cell_id / "manifest.json" for cell_id in cells
    }
    for path in sorted(expected_manifests - actual_manifests):
        errors.append(f"missing manifest for expected cell {path.parent.name}")
    for path in sorted(actual_manifests - expected_manifests):
        errors.append(f"unexpected manifest: {path.relative_to(run)}")

    for task_index, cell_id in enumerate(cells, start=1):
        path = run / "cells" / cell_id / "manifest.json"
        if not path.is_file():
            continue
        label = str(path.relative_to(run))
        payload = read_json_object(path, label, errors)
        if payload is None:
            continue
        if path.read_bytes() != canonical_json_bytes(payload):
            errors.append(f"{label} is not canonical compact sorted-key JSON")
        row = check_manifest_schema(payload, label, errors)
        if row.get("comparison_id") != cell_id:
            errors.append(f"{label} comparison_id differs from cell_id")
        params = cells[cell_id]
        for field in PARAM_FIELDS:
            if row.get(field) != params.get(field):
                errors.append(f"{label} disagrees with run_spec params field {field}")
        for field in PROVENANCE_FIELDS:
            if row.get(field) != provenance.get(field):
                errors.append(f"{label} disagrees with run_spec provenance field {field}")
        check_execution_row(row, label, errors)
        check_operational_metadata(
            run,
            payload,
            row,
            label,
            hashlib.sha256(run_spec_raw).hexdigest(),
            errors,
            expected_task_index=task_index,
        )
        check_native_artifacts(run, payload, row, label, errors)
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase", required=True, choices=("protocol", "baseline", "manifests")
    )
    parser.add_argument("--run", type=Path)
    parser.add_argument("--expected-spec", type=Path)
    args = parser.parse_args()
    if args.phase == "manifests":
        if args.run is None:
            parser.error("--phase manifests requires --run")
        if args.expected_spec is None:
            parser.error("--phase manifests requires --expected-spec")
        errors = check_manifests(args.run, args.expected_spec)
    else:
        if args.run is not None:
            parser.error("--run is valid only with --phase manifests")
        if args.expected_spec is not None:
            parser.error("--expected-spec is valid only with --phase manifests")
        errors = check_protocol(args.phase)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"gate passed: {args.phase}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
