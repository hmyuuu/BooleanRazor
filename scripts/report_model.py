#!/usr/bin/env python3
"""Canonical evidence model and deterministic offline report rendering."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from html import escape
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit


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
PROJECT_INFO_FIELDS = {"title", "purpose", "conclusion", "next_gate"}
EVIDENCE_FIELDS = {"kind", "label", "locator", "revision"}
CONTROL_FIELDS = {
    "control_id",
    "instance",
    "function",
    "gates",
    "status",
    "limitation",
    "evidence",
}
METHOD_FIELDS = {
    "method_id",
    "title",
    "status",
    "scope",
    "summary",
    "insights",
    "optimization",
    "stop_rules",
    "limitations",
    "evidence",
}
EXPERIMENT_FIELDS = {
    "experiment_id",
    "title",
    "track",
    "status",
    "location",
    "outcome",
    "decision",
    "limitations",
    "evidence",
}
CLAIM_FIELDS = {
    "claim_id",
    "track",
    "status",
    "summary",
    "evidence",
    "limitations",
    "missing_proof",
}
LAYER_FIELDS = {
    "layer_id",
    "title",
    "authority",
    "meaning",
    "current_state",
    "command",
}
COMMAND_FIELDS = {"command_id", "title", "command", "scope"}
REFERENCE_FIELDS = {"reference_id", "title", "url", "use"}

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
OUTPUT_PATHS = frozenset(
    {
        "reports/site/index.html",
        "reports/site/methods.html",
        "reports/site/verification.html",
        "reports/site/experiments.html",
        "reports/site/assets/report.css",
        "reports/site/assets/report.js",
        "docs/STATUS.md",
        "docs/METHODS.md",
        "docs/EXPERIMENT_INDEX.md",
        "research/EVIDENCE_LEDGER.md",
    }
)

OFFICIAL_RECORD_FIELDS = {
    "bit_accuracy",
    "circuit_sha256",
    "comparison_id",
    "dataset_sha256",
    "exact_accuracy",
    "gates",
    "julia_version",
    "manifest_sha256",
    "run_spec_sha256",
    "samples",
    "schema_version",
    "status",
    "verify_jl_sha256",
}
PROMOTION_DECISION_FIELDS = {
    "decision",
    "highest_legal_next_step",
    "input_sha256",
    "reasons",
    "schema_version",
    "track",
}
HEX_40 = re.compile(r"[0-9a-f]{40}\Z")
HEX_64 = re.compile(r"[0-9a-f]{64}\Z")
FORBIDDEN_PROPOSER_KEYS = {
    "family_label",
    "generator_name",
    "per_example_evaluator_failures",
    "private_digest",
    "sealed_data",
    "sealed_rows",
    "source_family",
}
MAX_SOURCE_BYTES = 16 * 1024 * 1024


class ModelError(ValueError):
    """The report source or one of its proof credentials is invalid."""


def _canonical_json_bytes(value: object) -> bytes:
    try:
        rendered = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ModelError("project must contain finite JSON values") from exc
    return rendered.encode("utf-8") + b"\n"


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ModelError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise ModelError(f"JSON number must be finite: {value}")


def _parse_canonical_object(raw: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except ModelError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ModelError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ModelError(f"{label} must be a JSON object")
    if raw != _canonical_json_bytes(value):
        raise ModelError(f"{label} must be canonical JSON")
    return value


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _read_regular_without_symlinks(
    path: Path, root: Path, label: str, max_bytes: int = MAX_SOURCE_BYTES
) -> bytes:
    root = _absolute_lexical(root)
    path = _absolute_lexical(path)
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ModelError(f"{label} must remain inside the repository") from exc
    current = root
    try:
        root_mode = root.lstat().st_mode
    except OSError as exc:
        raise ModelError("repository root must exist") from exc
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        raise ModelError("repository root must be a real directory")
    for part in relative.parts:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except OSError as exc:
            raise ModelError(f"{label} does not exist") from exc
        if stat.S_ISLNK(mode):
            raise ModelError(f"{label} must not use a symlink component")
    if not stat.S_ISREG(current.lstat().st_mode):
        raise ModelError(f"{label} must be a regular file")
    try:
        raw = current.read_bytes()
    except OSError as exc:
        raise ModelError(f"{label} cannot be read") from exc
    if len(raw) > max_bytes:
        raise ModelError(f"{label} is too large")
    return raw


def load_project(source: Path, repo_root: Path) -> tuple[dict[str, object], str]:
    """Load one canonical project source and return it with its exact digest."""
    if not isinstance(source, Path) or not isinstance(repo_root, Path):
        raise ModelError("source and repo_root must be Path objects")
    raw = _read_regular_without_symlinks(source, repo_root, "project source")
    project = _parse_canonical_object(raw, "project source")
    errors = validate_project(project, repo_root)
    if errors:
        raise ModelError("\n".join(errors))
    return project, hashlib.sha256(raw).hexdigest()


def _exact_keys(
    value: object, fields: set[str], label: str, errors: list[str]
) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object with exact keys")
        return False
    if set(value) != fields:
        errors.append(
            f"{label} must use exact keys: {', '.join(sorted(fields))}"
        )
        return False
    return True


def _nonempty_string(value: object, label: str, errors: list[str]) -> bool:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a nonempty string")
        return False
    return True


def _string_list(
    value: object,
    label: str,
    errors: list[str],
    *,
    require_nonempty: bool = False,
) -> bool:
    if (
        not isinstance(value, list)
        or (require_nonempty and not value)
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        suffix = "nonempty " if require_nonempty else ""
        errors.append(f"{label} must be a {suffix}list of nonempty strings")
        return False
    return True


def _safe_repo_locator(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return False
    pure = PurePosixPath(value)
    parts = value.split("/")
    return (
        not pure.is_absolute()
        and value not in {".", ".."}
        and all(
            part not in {"", ".", ".."} and not part.startswith("-")
            for part in parts
        )
    )


def _https_url(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    if any(
        character.isspace()
        or ord(character) == 127
        or character in {'"', "'", "<", ">"}
        for character in value
    ):
        return False
    try:
        split = urlsplit(value)
        _ = split.port
    except ValueError:
        return False
    return (
        split.scheme == "https"
        and bool(split.hostname)
        and split.username is None
        and split.password is None
        and not split.path.startswith("//")
    )


def _tracked_regular_path(
    repo_root: Path, locator: str, label: str, errors: list[str]
) -> Path | None:
    if not _safe_repo_locator(locator):
        errors.append(f"{label} must use a safe repo-relative POSIX path")
        return None
    root = _absolute_lexical(repo_root)
    path = root.joinpath(*locator.split("/"))
    current = root
    try:
        if stat.S_ISLNK(current.lstat().st_mode):
            errors.append(f"{label} must not use a symlink component")
            return None
    except OSError:
        errors.append("repository root must exist")
        return None
    for part in locator.split("/"):
        current = current / part
        try:
            mode = current.lstat().st_mode
        except OSError:
            errors.append(f"{label} must be a tracked evidence path")
            return None
        if stat.S_ISLNK(mode):
            errors.append(f"{label} must not use a symlink component")
            return None
    if not stat.S_ISREG(path.lstat().st_mode):
        errors.append(f"{label} must be an existing regular file")
        return None
    try:
        tracked = subprocess.run(
            [
                "git",
                "-C",
                os.fspath(root),
                "ls-files",
                "--error-unmatch",
                "--",
                locator,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        errors.append(f"{label} cannot verify the tracked evidence path")
        return None
    if tracked.returncode != 0:
        errors.append(f"{label} must be a Git-tracked evidence path")
        return None
    return path


def _validate_evidence(
    value: object, repo_root: Path, label: str, errors: list[str]
) -> dict[str, object] | None:
    if not _exact_keys(value, EVIDENCE_FIELDS, label, errors):
        return None
    assert isinstance(value, dict)
    kind = value["kind"]
    locator = value["locator"]
    revision = value["revision"]
    _nonempty_string(value["label"], f"{label}.label", errors)
    if not isinstance(kind, str) or kind not in EVIDENCE_KINDS:
        errors.append(f"{label}.kind is invalid")
        return value
    if kind == "path":
        if revision != "main":
            errors.append(f"{label} path evidence revision must equal main")
        if isinstance(locator, str):
            _tracked_regular_path(repo_root, locator, label, errors)
        else:
            errors.append(f"{label} must use a safe repo-relative POSIX path")
    elif kind == "commit":
        if not isinstance(revision, str) or HEX_40.fullmatch(revision) is None:
            errors.append(f"{label} commit revision must be 40 lowercase hex")
        if not _safe_repo_locator(locator):
            errors.append(f"{label} must use a safe repo-relative POSIX path")
    elif kind == "command":
        if revision != "none" or not isinstance(locator, str) or not locator.strip():
            errors.append(
                f"{label} command evidence requires revision=none and one command"
            )
    elif kind == "test":
        if revision != "main" or not isinstance(locator, str) or not locator.strip():
            errors.append(
                f"{label} test evidence requires revision=main and one selector"
            )
    elif kind == "url":
        if revision != "none" or not _https_url(locator):
            errors.append(
                f"{label} URL evidence requires revision=none and a credential-free https URL"
            )
    return value


def _validate_evidence_list(
    value: object, repo_root: Path, label: str, errors: list[str]
) -> list[dict[str, object]]:
    if not isinstance(value, list) or not value:
        errors.append(f"{label} must be a nonempty evidence list")
        return []
    result = []
    for index, row in enumerate(value):
        checked = _validate_evidence(
            row, repo_root, f"{label}[{index}]", errors
        )
        if checked is not None:
            result.append(checked)
    return result


def _record_list(
    project: dict[str, object],
    key: str,
    fields: set[str],
    errors: list[str],
) -> list[dict[str, object]]:
    rows = project.get(key)
    if not isinstance(rows, list) or not rows:
        errors.append(f"{key} must be a nonempty list")
        return []
    result = []
    for index, row in enumerate(rows):
        if _exact_keys(row, fields, f"{key}[{index}]", errors):
            assert isinstance(row, dict)
            result.append(row)
    return result


def _unique_ids(
    rows: list[dict[str, object]], field: str, label: str, errors: list[str]
) -> None:
    seen: set[str] = set()
    for row in rows:
        identifier = row.get(field)
        if isinstance(identifier, str):
            if identifier in seen:
                errors.append(f"{label} has duplicate {field}: {identifier}")
            seen.add(identifier)


def _forbidden_keys(value: object, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            if key in FORBIDDEN_PROPOSER_KEYS:
                errors.append(
                    f"{child_path} is a forbidden proposer-facing key"
                )
            _forbidden_keys(child, child_path, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _forbidden_keys(child, f"{path}[{index}]", errors)


def _load_proof(path: Path, repo_root: Path, label: str) -> dict[str, object]:
    raw = _read_regular_without_symlinks(path, repo_root, label)
    return _parse_canonical_object(raw, label)


def _validate_official_record(
    path: Path, repo_root: Path, errors: list[str]
) -> bool:
    label = "official-verification.json"
    try:
        record = _load_proof(path, repo_root, label)
    except ModelError as exc:
        errors.append(f"{label}: {exc}")
        return False
    if set(record) != OFFICIAL_RECORD_FIELDS:
        errors.append(f"{label} must use exact keys")
        return False
    valid = True

    def reject(message: str) -> None:
        nonlocal valid
        valid = False
        errors.append(f"{label} {message}")

    if type(record["schema_version"]) is not int or record["schema_version"] != 1:
        reject("schema_version must be integer 1")
    if record["status"] != "pass":
        reject("status must equal pass")
    if record["exact_accuracy"] != "1.0" or record["bit_accuracy"] != "1.0":
        reject("accuracies must be canonical string 1.0")
    if type(record["samples"]) is not int or record["samples"] <= 0:
        reject("samples must be a positive JSON integer")
    if type(record["gates"]) is not int or record["gates"] < 0:
        reject("gates must be a nonnegative JSON integer")
    if (
        not isinstance(record["comparison_id"], str)
        or not record["comparison_id"]
    ):
        reject("comparison_id must be nonempty")
    for field in (
        "circuit_sha256",
        "dataset_sha256",
        "manifest_sha256",
        "run_spec_sha256",
        "verify_jl_sha256",
    ):
        value = record[field]
        if not isinstance(value, str) or HEX_64.fullmatch(value) is None:
            reject(f"{field} must be 64 lowercase hex")
    version = record["julia_version"]
    if not isinstance(version, dict) or set(version) != {"sha256", "text"}:
        reject("julia_version must have exact sha256 and text keys")
    else:
        digest = version["sha256"]
        text = version["text"]
        if not isinstance(digest, str) or HEX_64.fullmatch(digest) is None:
            reject("julia_version.sha256 must be 64 lowercase hex")
        if (
            not isinstance(text, str)
            or not text
            or any(ord(character) < 32 or ord(character) > 126 for character in text)
        ):
            reject("julia_version.text must be nonempty printable ASCII")
        elif isinstance(digest, str) and HEX_64.fullmatch(digest) is not None:
            expected = hashlib.sha256((text + "\n").encode("ascii")).hexdigest()
            if digest != expected:
                reject("julia_version.sha256 must bind LF-terminated text")
    return valid


def _valid_digest_map(value: object) -> bool:
    if (
        not isinstance(value, dict)
        or len(value) < 2
        or "external_trust_policy" not in value
    ):
        return False
    for key, digest in value.items():
        if (
            not isinstance(key, str)
            or not _safe_repo_locator(key)
            or not isinstance(digest, str)
            or HEX_64.fullmatch(digest) is None
        ):
            return False
    return True


def _validate_sealed_decision(
    path: Path, repo_root: Path, errors: list[str]
) -> bool:
    label = "sealed promotion decision"
    try:
        decision = _load_proof(path, repo_root, label)
    except ModelError as exc:
        errors.append(f"{label}: {exc}")
        return False
    if set(decision) != PROMOTION_DECISION_FIELDS:
        errors.append(f"{label} must use exact keys")
        return False
    valid = (
        type(decision["schema_version"]) is int
        and decision["schema_version"] == 1
        and decision["track"] == "sealed_confirmation"
        and decision["decision"] == "promote_blind_result"
        and decision["highest_legal_next_step"] == "promote_blind_result"
        and decision["reasons"] == []
        and _valid_digest_map(decision["input_sha256"])
    )
    if not valid:
        errors.append(
            "sealed promotion decision must be an exact promote_blind_result credential"
        )
    return valid


def validate_project(
    project: dict[str, object], repo_root: Path
) -> list[str]:
    """Return deterministic diagnostics for one decoded project object."""
    errors: list[str] = []
    if not isinstance(project, dict):
        return ["project source must be an object with exact keys"]
    _forbidden_keys(project, "", errors)
    if set(project) != PROJECT_FIELDS:
        errors.append(
            f"project source must use exact keys: {', '.join(sorted(PROJECT_FIELDS))}"
        )
    if (
        type(project.get("schema_version")) is not int
        or project.get("schema_version") != 1
    ):
        errors.append("schema_version must be integer 1")

    info = project.get("project")
    if _exact_keys(info, PROJECT_INFO_FIELDS, "project", errors):
        assert isinstance(info, dict)
        for field in sorted(PROJECT_INFO_FIELDS):
            _nonempty_string(info[field], f"project.{field}", errors)

    controls = _record_list(project, "controls", CONTROL_FIELDS, errors)
    methods = _record_list(project, "methods", METHOD_FIELDS, errors)
    experiments = _record_list(
        project, "experiments", EXPERIMENT_FIELDS, errors
    )
    claims = _record_list(project, "claims", CLAIM_FIELDS, errors)
    layers = _record_list(
        project, "verification_layers", LAYER_FIELDS, errors
    )
    commands = _record_list(project, "commands", COMMAND_FIELDS, errors)
    references = _record_list(
        project, "external_references", REFERENCE_FIELDS, errors
    )

    for rows, field, label in (
        (controls, "control_id", "controls"),
        (methods, "method_id", "methods"),
        (experiments, "experiment_id", "experiments"),
        (claims, "claim_id", "claims"),
        (layers, "layer_id", "verification_layers"),
        (commands, "command_id", "commands"),
        (references, "reference_id", "external_references"),
    ):
        _unique_ids(rows, field, label, errors)

    seen_instances: set[str] = set()
    for index, row in enumerate(controls):
        label = f"controls[{index}]"
        for field in ("control_id", "instance", "function", "limitation"):
            _nonempty_string(row[field], f"{label}.{field}", errors)
        if not isinstance(row["status"], str) or row["status"] not in STATUSES:
            errors.append(f"{label} has invalid status")
        gates = row["gates"]
        if type(gates) is not int or gates < 0:
            errors.append(f"{label}.gates must be a nonnegative JSON integer")
        instance = row["instance"]
        if isinstance(instance, str):
            seen_instances.add(instance)
            expected = CONTROL_GATES.get(instance)
            if expected is None:
                errors.append(f"{label} has an unknown disclosed control")
            elif row["function"] != expected[0] or gates != expected[1]:
                errors.append(
                    f"{instance} must use {expected[1]} gates and function {expected[0]}"
                )
        _validate_evidence_list(row["evidence"], repo_root, f"{label}.evidence", errors)
    if seen_instances != set(CONTROL_GATES) or len(controls) != 4:
        errors.append("controls must contain each disclosed mystery-A through mystery-D once")

    official_paths: dict[Path, bool] = {}
    def evidence_and_proofs(
        row: dict[str, object], label: str
    ) -> tuple[list[dict[str, object]], list[Path], list[Path]]:
        evidence = _validate_evidence_list(
            row["evidence"], repo_root, f"{label}.evidence", errors
        )
        row_official_paths: list[Path] = []
        row_promotion_paths: list[Path] = []
        for item in evidence:
            if item.get("kind") != "path" or not isinstance(item.get("locator"), str):
                continue
            locator = item["locator"]
            if not _safe_repo_locator(locator):
                continue
            path = _absolute_lexical(repo_root).joinpath(*locator.split("/"))
            name = PurePosixPath(locator).name
            if name == "official-verification.json":
                row_official_paths.append(path)
                if path not in official_paths:
                    official_paths[path] = _validate_official_record(
                        path, repo_root, errors
                    )
            lowered = name.lower()
            if "promotion" in lowered and "decision" in lowered:
                row_promotion_paths.append(path)
        return evidence, row_official_paths, row_promotion_paths

    for index, row in enumerate(methods):
        label = f"methods[{index}]"
        for field in ("method_id", "title", "scope", "summary"):
            _nonempty_string(row[field], f"{label}.{field}", errors)
        if not isinstance(row["status"], str) or row["status"] not in STATUSES:
            errors.append(f"{label} has invalid status")
        for field in ("insights", "optimization", "stop_rules", "limitations"):
            _string_list(row[field], f"{label}.{field}", errors)
        evidence, _, _ = evidence_and_proofs(row, label)
        if row["status"] != "verified_main" and not row["limitations"]:
            errors.append(f"{label} limitation must not be empty")
        if row["status"] == "verified_branch_only" and not any(
            item.get("kind") == "commit"
            and isinstance(item.get("revision"), str)
            and HEX_40.fullmatch(item["revision"]) is not None
            for item in evidence
        ):
            errors.append(
                f"{label} verified_branch_only requires full-SHA commit evidence"
            )

    for index, row in enumerate(experiments):
        label = f"experiments[{index}]"
        for field in (
            "experiment_id",
            "title",
            "location",
            "outcome",
            "decision",
        ):
            _nonempty_string(row[field], f"{label}.{field}", errors)
        if not isinstance(row["track"], str) or row["track"] not in TRACKS:
            errors.append(f"{label} has invalid track")
        if not isinstance(row["status"], str) or row["status"] not in STATUSES:
            errors.append(f"{label} has invalid status")
        _string_list(row["limitations"], f"{label}.limitations", errors)
        evidence, _, _ = evidence_and_proofs(row, label)
        if row["status"] != "verified_main" and not row["limitations"]:
            errors.append(f"{label} limitation must not be empty")
        if row["status"] == "verified_branch_only" and not any(
            item.get("kind") == "commit"
            and isinstance(item.get("revision"), str)
            and HEX_40.fullmatch(item["revision"]) is not None
            for item in evidence
        ):
            errors.append(
                f"{label} verified_branch_only requires full-SHA commit evidence"
            )

    for index, row in enumerate(claims):
        label = f"claims[{index}]"
        for field in ("claim_id", "summary"):
            _nonempty_string(row[field], f"{label}.{field}", errors)
        if not isinstance(row["track"], str) or row["track"] not in TRACKS:
            errors.append(f"{label} has invalid track")
        if not isinstance(row["status"], str) or row["status"] not in STATUSES:
            errors.append(f"{label} has invalid status")
        _string_list(row["limitations"], f"{label}.limitations", errors)
        _string_list(row["missing_proof"], f"{label}.missing_proof", errors)
        evidence, row_official_paths, row_promotion_paths = evidence_and_proofs(
            row, label
        )
        if row["status"] != "verified_main" and not row["limitations"]:
            errors.append(f"{label} limitation must not be empty")
        if row["status"] == "verified_branch_only" and not any(
            item.get("kind") == "commit"
            and isinstance(item.get("revision"), str)
            and HEX_40.fullmatch(item["revision"]) is not None
            for item in evidence
        ):
            errors.append(
                f"{label} verified_branch_only requires full-SHA commit evidence"
            )
        if (
            row["status"] == "verified_main"
            and row["track"] == "sealed_confirmation"
            and not any(
                _validate_sealed_decision(path, repo_root, errors)
                for path in row_promotion_paths
            )
        ):
            errors.append(
                f"{label} verified_main sealed claim requires a canonical sealed promotion decision"
            )
        if (
            row["status"] == "verified_main"
            and row["claim_id"] == "official-verifier-pass"
            and not any(
                official_paths.get(path, False) for path in row_official_paths
            )
        ):
            errors.append(
                f"{label} requires a canonical official-verification.json"
            )

    for index, row in enumerate(layers):
        label = f"verification_layers[{index}]"
        for field in LAYER_FIELDS:
            _nonempty_string(row[field], f"{label}.{field}", errors)

    for index, row in enumerate(commands):
        label = f"commands[{index}]"
        for field in COMMAND_FIELDS:
            _nonempty_string(row[field], f"{label}.{field}", errors)

    for index, row in enumerate(references):
        label = f"external_references[{index}]"
        for field in ("reference_id", "title", "use"):
            _nonempty_string(row[field], f"{label}.{field}", errors)
        if not _https_url(row["url"]):
            errors.append(f"{label}.url must be a credential-free https URL")

    return sorted(set(errors))


def _marker(source_digest: str, generator_digest: str) -> str:
    return (
        "<!-- GENERATED; DO NOT EDIT. Source: reports/data/project.json SHA-256: "
        f"{source_digest}; report model SHA-256: {generator_digest} -->"
    )


def _html_evidence(item: dict[str, object]) -> str:
    label = escape(str(item["label"]), quote=True)
    kind = item["kind"]
    locator = str(item["locator"])
    revision = str(item["revision"])
    if kind == "path":
        href = "../../" + quote(locator, safe="/-._~")
        return f'<a href="{escape(href, quote=True)}">{label}</a>'
    if kind == "url":
        return f'<a href="{escape(locator, quote=True)}">{label}</a>'
    if kind == "commit":
        return (
            f"{label}: <code>{escape(revision, quote=True)}</code> "
            f"at <code>{escape(locator, quote=True)}</code>"
        )
    return f"{label}: <code>{escape(locator, quote=True)}</code>"


def _html_evidence_list(items: list[dict[str, object]]) -> str:
    return "<ul>" + "".join(
        f"<li>{_html_evidence(item)}</li>" for item in items
    ) + "</ul>"


def _markdown_text(value: object) -> str:
    text = escape(str(value), quote=True)
    text = text.replace("\\", "\\\\")
    for character in ("|", "[", "]", "(", ")"):
        text = text.replace(character, "\\" + character)
    return text.replace("\r", " ").replace("\n", "<br>")


def _markdown_evidence(item: dict[str, object]) -> str:
    label = _markdown_text(item["label"])
    kind = item["kind"]
    locator = str(item["locator"])
    revision = str(item["revision"])
    if kind == "path":
        return f"[{label}](../{quote(locator, safe='/-._~')})"
    if kind == "url":
        href = quote(
            locator,
            safe=":/?#[]@!$&'*+,;=%-._~",
        )
        return f"[{label}]({href})"
    if kind == "commit":
        return (
            f"{label}: `{_markdown_text(revision)}` at "
            f"`{_markdown_text(locator)}`"
        )
    return f"{label}: `{_markdown_text(locator)}`"


def _html_page(
    *,
    title: str,
    active: str,
    body: str,
    source_digest: str,
    generator_digest: str,
) -> bytes:
    navigation = "".join(
        (
            f'<a href="{path}"'
            + (' aria-current="page"' if path == active else "")
            + f">{escape(label, quote=True)}</a>"
        )
        for path, label in (
            ("index.html", "Status"),
            ("methods.html", "Methods"),
            ("verification.html", "Verification"),
            ("experiments.html", "Experiments"),
        )
    )
    return (
        f"{_marker(source_digest, generator_digest)}\n"
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"  <title>{escape(title, quote=True)}</title>\n"
        '  <link rel="stylesheet" href="assets/report.css">\n'
        "</head>\n"
        "<body>\n"
        '  <a class="skip-link" href="#content">Skip to content</a>\n'
        f'  <header><nav aria-label="Report">{navigation}</nav></header>\n'
        f'  <main id="content">{body}</main>\n'
        "  <footer>"
        f"Evidence source SHA-256: <code>{source_digest}</code>; "
        f"report model SHA-256: <code>{generator_digest}</code>"
        "</footer>\n"
        '  <script src="assets/report.js"></script>\n'
        "</body>\n"
        "</html>\n"
    ).encode("utf-8")


def _render_index(project: dict[str, object]) -> str:
    info = project["project"]
    assert isinstance(info, dict)
    controls = project["controls"]
    claims = project["claims"]
    assert isinstance(controls, list) and isinstance(claims, list)
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(row['instance']), quote=True)}</td>"
        f"<td>{escape(str(row['function']), quote=True)}</td>"
        f"<td>{row['gates']}</td>"
        f"<td>{escape(str(row['status']), quote=True)}</td>"
        f"<td>{escape(str(row['limitation']), quote=True)}</td>"
        "</tr>"
        for row in controls
        if isinstance(row, dict)
    )
    blockers = "".join(
        f"<li>{escape(str(row['summary']), quote=True)}</li>"
        for row in claims
        if isinstance(row, dict) and row.get("status") in {"blocked", "absent"}
    )
    return (
        '<section class="hero">'
        f"<h1>{escape(str(info['title']), quote=True)}</h1>"
        f"<p>{escape(str(info['purpose']), quote=True)}</p>"
        "</section>"
        "<section><h2>Current conclusion</h2>"
        f"<p>{escape(str(info['conclusion']), quote=True)}</p></section>"
        '<section class="table-wrap"><h2>Disclosed controls</h2>'
        "<table><thead><tr><th>Instance</th><th>Function</th><th>Gates</th>"
        f"<th>Status</th><th>Boundary</th></tr></thead><tbody>{rows}</tbody></table>"
        "</section><section><h2>Blind-study blockers</h2>"
        f"<ul>{blockers}</ul></section><section><h2>Next gate</h2>"
        f"<p>{escape(str(info['next_gate']), quote=True)}</p></section>"
    )


def _render_methods(project: dict[str, object]) -> str:
    methods = project["methods"]
    assert isinstance(methods, list)
    cards = []
    for method in methods:
        assert isinstance(method, dict)
        cards.append(
            '<article class="method-card">'
            f"<h2>{escape(str(method['title']), quote=True)}</h2>"
            f'<p class="status status-{escape(str(method["status"]), quote=True)}">'
            f"{escape(str(method['status']), quote=True)}</p>"
            f"<p>{escape(str(method['summary']), quote=True)}</p>"
            "<h3>Insights</h3><ul>"
            + "".join(
                f"<li>{escape(str(item), quote=True)}</li>"
                for item in method["insights"]
            )
            + "</ul><h3>Optimization</h3><ul>"
            + "".join(
                f"<li>{escape(str(item), quote=True)}</li>"
                for item in method["optimization"]
            )
            + "</ul><h3>Stop rules</h3><ul>"
            + "".join(
                f"<li>{escape(str(item), quote=True)}</li>"
                for item in method["stop_rules"]
            )
            + "</ul><h3>Evidence</h3>"
            + _html_evidence_list(method["evidence"])
            + "</article>"
        )
    return '<section class="hero"><h1>Methods</h1></section><div class="method-grid">' + "".join(cards) + "</div>"


def _render_verification(project: dict[str, object]) -> str:
    layers = project["verification_layers"]
    commands = project["commands"]
    assert isinstance(layers, list) and isinstance(commands, list)
    layer_rows = "".join(
        "<tr>"
        f"<td>{escape(str(row['title']), quote=True)}</td>"
        f"<td>{escape(str(row['authority']), quote=True)}</td>"
        f"<td>{escape(str(row['meaning']), quote=True)}</td>"
        f"<td>{escape(str(row['current_state']), quote=True)}</td>"
        "</tr>"
        for row in layers
        if isinstance(row, dict)
    )
    command_cards = "".join(
        "<article class=\"card\">"
        f"<h3>{escape(str(row['title']), quote=True)}</h3>"
        f"<p>{escape(str(row['scope']), quote=True)}</p>"
        f"<pre><code>{escape(str(row['command']), quote=True)}</code></pre>"
        "</article>"
        for row in commands
        if isinstance(row, dict)
    )
    return (
        '<section class="hero"><h1>Verification</h1>'
        "<p>Internal exhaustive equivalence and the official Julia verifier are "
        "separate authorities.</p></section>"
        '<section class="table-wrap"><table><thead><tr><th>Layer</th>'
        "<th>Authority</th><th>Meaning</th><th>Current state</th></tr></thead>"
        f"<tbody>{layer_rows}</tbody></table></section>"
        f'<section class="cards">{command_cards}</section>'
    )


def _render_experiments(project: dict[str, object]) -> str:
    experiments = project["experiments"]
    assert isinstance(experiments, list)
    rows = "".join(
        "<tr "
        f'data-status="{escape(str(row["status"]), quote=True)}">'
        f"<td>{escape(str(row['title']), quote=True)}</td>"
        f"<td>{escape(str(row['track']), quote=True)}</td>"
        f"<td>{escape(str(row['status']), quote=True)}</td>"
        f"<td>{escape(str(row['location']), quote=True)}</td>"
        f"<td>{escape(str(row['outcome']), quote=True)}</td>"
        f"<td>{escape(str(row['decision']), quote=True)}</td>"
        f"<td>{_html_evidence_list(row['evidence'])}</td>"
        "</tr>"
        for row in experiments
        if isinstance(row, dict)
    )
    return (
        '<section class="hero"><h1>Experiments</h1></section>'
        '<section><button type="button" data-status-filter="all" '
        'aria-pressed="true">All</button></section>'
        '<section class="table-wrap"><table><thead><tr><th>Experiment</th>'
        "<th>Track</th><th>Status</th><th>Location</th><th>Outcome</th>"
        f"<th>Decision</th><th>Evidence</th></tr></thead><tbody>{rows}</tbody>"
        "</table></section>"
    )


REPORT_CSS = """\
:root { color-scheme: light; --ink: #172033; --paper: #f7f4ed; --panel: #fff;
  --line: #c8d0dc; --accent: #0b6e69; }
* { box-sizing: border-box; }
body { margin: 0; color: var(--ink); background: var(--paper);
  font-family: ui-sans-serif, system-ui, sans-serif; line-height: 1.55; }
.skip-link { position: absolute; left: -9999px; }
.skip-link:focus { left: 1rem; top: 1rem; z-index: 10; }
a:focus-visible, button:focus-visible { outline: 3px solid var(--accent);
  outline-offset: 3px; }
main, header, footer { width: min(1120px, calc(100% - 2rem)); margin-inline: auto; }
nav { display: flex; flex-wrap: wrap; gap: .5rem; padding-block: 1rem; }
nav a { padding: .45rem .7rem; }
.hero { padding: 3rem 0 1.5rem; }
section { margin-block: 2rem; }
.cards, .method-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; }
.card, .method-card { padding: 1rem; border: 1px solid var(--line);
  background: var(--panel); }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; background: var(--panel); }
th, td { padding: .7rem; border: 1px solid var(--line); text-align: left; }
code { overflow-wrap: anywhere; }
pre { padding: 1rem; overflow-x: auto; color: #fff; background: var(--ink); }
footer { padding-block: 2rem; }
@media (max-width: 760px) { .cards, .method-grid { grid-template-columns: 1fr; } }
@media print { nav, .skip-link, script, button { display: none !important; }
  body { background: #fff; color: #000; } }
"""

REPORT_JS = """\
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
"""


def _markdown_header(source_digest: str, generator_digest: str) -> str:
    return _marker(source_digest, generator_digest) + "\n\n"


def _markdown_outputs(
    project: dict[str, object], source_digest: str, generator_digest: str
) -> dict[str, bytes]:
    header = _markdown_header(source_digest, generator_digest)
    info = project["project"]
    assert isinstance(info, dict)
    controls = project["controls"]
    methods = project["methods"]
    experiments = project["experiments"]
    claims = project["claims"]
    assert all(
        isinstance(rows, list)
        for rows in (controls, methods, experiments, claims)
    )
    status = (
        header
        + "# Status\n\n"
        + _markdown_text(info["conclusion"])
        + "\n\n## Disclosed controls\n\n"
        + "| Instance | Function | Gates | Status | Boundary |\n"
        + "| --- | --- | ---: | --- | --- |\n"
        + "".join(
            f"| {_markdown_text(row['instance'])} | {_markdown_text(row['function'])} "
            f"| {row['gates']} | {_markdown_text(row['status'])} "
            f"| {_markdown_text(row['limitation'])} |\n"
            for row in controls
            if isinstance(row, dict)
        )
        + "\n## Next gate\n\n"
        + _markdown_text(info["next_gate"])
        + "\n"
    )
    methods_md = (
        header
        + "# Methods\n\n"
        + "| Method | Status | Insight | Optimization | Stop rule |\n"
        + "| --- | --- | --- | --- | --- |\n"
        + "".join(
            f"| {_markdown_text(row['title'])} | {_markdown_text(row['status'])} "
            f"| {_markdown_text('; '.join(row['insights']))} "
            f"| {_markdown_text('; '.join(row['optimization']))} "
            f"| {_markdown_text('; '.join(row['stop_rules']))} |\n"
            for row in methods
            if isinstance(row, dict)
        )
    )
    experiments_md = (
        header
        + "# Experiment index\n\n"
        + "| Experiment | Track | Status | Location | Decision |\n"
        + "| --- | --- | --- | --- | --- |\n"
        + "".join(
            f"| {_markdown_text(row['title'])} | {_markdown_text(row['track'])} "
            f"| {_markdown_text(row['status'])} | {_markdown_text(row['location'])} "
            f"| {_markdown_text(row['decision'])} |\n"
            for row in experiments
            if isinstance(row, dict)
        )
    )
    ledger_parts = [header, "# Evidence ledger\n\n"]
    for row in claims:
        assert isinstance(row, dict)
        ledger_parts.extend(
            (
                f"## {_markdown_text(row['claim_id'])}\n\n",
                _markdown_text(row["summary"]) + "\n\n",
                "Evidence:\n\n",
                "".join(
                    f"- {_markdown_evidence(item)}\n"
                    for item in row["evidence"]
                ),
                "\nLimitations:\n\n",
                "".join(
                    f"- {_markdown_text(item)}\n"
                    for item in row["limitations"]
                )
                or "- None recorded.\n",
                "\nMissing proof:\n\n",
                "".join(
                    f"- {_markdown_text(item)}\n"
                    for item in row["missing_proof"]
                )
                or "- None.\n",
                "\n",
            )
        )
    return {
        "docs/STATUS.md": status.encode("utf-8"),
        "docs/METHODS.md": methods_md.encode("utf-8"),
        "docs/EXPERIMENT_INDEX.md": experiments_md.encode("utf-8"),
        "research/EVIDENCE_LEDGER.md": "".join(ledger_parts).encode("utf-8"),
    }


def render_outputs(
    project: dict[str, object],
    source_digest: str,
    generator_digest: str,
) -> dict[str, bytes]:
    """Render the exact deterministic offline output map."""
    if (
        not isinstance(source_digest, str)
        or HEX_64.fullmatch(source_digest) is None
        or not isinstance(generator_digest, str)
        or HEX_64.fullmatch(generator_digest) is None
    ):
        raise ModelError("render digests must be 64 lowercase hex")
    info = project.get("project")
    if not isinstance(info, dict):
        raise ModelError("project info is unavailable")
    outputs = {
        "reports/site/index.html": _html_page(
            title=str(info["title"]),
            active="index.html",
            body=_render_index(project),
            source_digest=source_digest,
            generator_digest=generator_digest,
        ),
        "reports/site/methods.html": _html_page(
            title=f"{info['title']} methods",
            active="methods.html",
            body=_render_methods(project),
            source_digest=source_digest,
            generator_digest=generator_digest,
        ),
        "reports/site/verification.html": _html_page(
            title=f"{info['title']} verification",
            active="verification.html",
            body=_render_verification(project),
            source_digest=source_digest,
            generator_digest=generator_digest,
        ),
        "reports/site/experiments.html": _html_page(
            title=f"{info['title']} experiments",
            active="experiments.html",
            body=_render_experiments(project),
            source_digest=source_digest,
            generator_digest=generator_digest,
        ),
        "reports/site/assets/report.css": REPORT_CSS.encode("utf-8"),
        "reports/site/assets/report.js": REPORT_JS.encode("utf-8"),
    }
    outputs.update(_markdown_outputs(project, source_digest, generator_digest))
    if set(outputs) != OUTPUT_PATHS:
        raise AssertionError("renderer output set drifted")
    return dict(sorted(outputs.items()))
