#!/usr/bin/env python3
"""Canonical evidence model and deterministic offline report rendering."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from html import escape
from pathlib import Path, PurePosixPath
from types import ModuleType
from urllib.parse import quote, urlsplit


def _load_sibling_module(module_name: str, filename: str) -> ModuleType:
    path = Path(
        os.path.abspath(os.fspath(Path(__file__).parent / filename))
    )
    existing = sys.modules.get(module_name)
    if isinstance(existing, ModuleType):
        existing_file = getattr(existing, "__file__", None)
        if (
            isinstance(existing_file, str)
            and Path(os.path.abspath(existing_file)) == path
        ):
            return existing
        del sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load sibling module {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_evidence_io = _load_sibling_module("evidence_io", "evidence_io.py")
EvidenceError = _evidence_io.EvidenceError
canonical_evidence_json_bytes = _evidence_io.canonical_json_bytes
load_canonical_evidence_object = _evidence_io.load_canonical_object
read_stable_regular = _evidence_io.read_stable_regular


PROJECT_FIELDS = {
    "schema_version",
    "project",
    "controls",
    "methods",
    "experiments",
    "research_rounds",
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
    "synthetic_frontier_round_id",
}
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
RESEARCH_ROUND_FIELDS = {
    "round_id",
    "parent_round_ids",
    "round_index",
    "title",
    "branch",
    "base_revision",
    "result_revision",
    "track",
    "status",
    "turning_point",
    "hypothesis",
    "independent_variable",
    "permitted_data",
    "frozen_controls",
    "runs",
    "outcome",
    "decision",
    "insight",
    "limitations",
    "next_pivot",
    "evidence",
}
ROUND_RUN_FIELDS = {
    "run_id",
    "status",
    "classification",
    "outcome",
    "evidence",
}
CLAIM_FIELDS = {
    "claim_id",
    "claim_kind",
    "track",
    "status",
    "summary",
    "evidence",
    "limitations",
    "missing_proof",
    "proof",
}
CLAIM_PROOF_FIELDS = {
    "official_record",
    "promotion_decision",
    "promotion_request",
    "trust_policy",
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
RUN_STATUSES = {
    "successful",
    "failed",
    "timed_out",
    "invalid",
    "equal",
    "superseded",
    "blocked",
    "not_run",
}
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
REPORT_GENERATOR_DIGEST_DOMAIN = (
    b"BooleanRazor deterministic report generator v2\0"
)
REPORT_GENERATOR_COMPONENT_PATHS = (
    b"scripts/evidence_io.py",
    b"scripts/candidate_evidence.py",
    b"scripts/check-promotion.py",
    b"scripts/report_model.py",
)
HISTORICAL_OFFICIAL_PROOFS: dict[
    tuple[str, str], dict[tuple[str, str], str]
] = {
    ("disclosed_control", "verified_branch_only"): {
        (
            "41518ce876b9c2a5939a525e538473165765203c",
            "LOG.md",
        ): "daa8b4eb4db5a25cd8506c0785a4a64a7296d37d9c510fd268625f7fcaf77754",
    }
}

# Claim prose is intentionally not authoritative.  A report statement exists
# only when an exact structural (claim_kind, track, status) tuple appears here.
# This keeps both validation and rendering independent of author-controlled IDs
# and prose.
CLAIM_POLICY: dict[str, dict[tuple[str, str], str]] = {
    "blind_advantage": {
        (
            "blind_visible",
            "blocked",
        ): "Blind advantage has not been demonstrated.",
        (
            "blind_visible",
            "absent",
        ): "Blind-visible and sealed evidence are absent; blind advantage has not been demonstrated.",
        (
            "sealed_confirmation",
            "blocked",
        ): "Sealed confirmation is blocked; blind advantage has not been demonstrated.",
    },
    "control_equivalence": {
        (
            "disclosed_control",
            "verified_main",
        ): "The disclosed controls pass current internal exhaustive equivalence.",
        (
            "disclosed_control",
            "verified_branch_only",
        ): "Disclosed-control equivalence is recorded only at the cited historical revision.",
    },
    # Current-head official claims have no permitted positive tuple until a
    # sanitized authenticated attestation contract exists.
    "official_verifier_pass": {},
    "historical_disclosed_julia_pass": {
        (
            "disclosed_control",
            "verified_branch_only",
        ): (
            "The ratified historical disclosed-v1 log records Julia verifier "
            "passes for disclosed controls only; this is not a fresh "
            "current-HEAD official verification or blind-learning evidence."
        ),
    },
    "promotion_state": {
        (
            "blind_visible",
            "blocked",
        ): "The current blind-visible promotion decision is blocked.",
        (
            "synthetic",
            "blocked",
        ): "The current synthetic promotion decision is blocked.",
        (
            "disclosed_control",
            "blocked",
        ): "The current disclosed-control promotion decision is blocked.",
    },
    "sealed_promotion": {
        (
            "sealed_confirmation",
            "blocked",
        ): "Sealed promotion is blocked.",
        (
            "sealed_confirmation",
            "absent",
        ): "No sealed-promotion evidence is present.",
    },
    "synthetic_candidate": {
        (
            "synthetic",
            "verified_branch_only",
        ): "A synthetic candidate result is recorded only at the cited historical revision.",
        (
            "synthetic",
            "rejected",
        ): "The cited synthetic candidate was rejected.",
        (
            "synthetic",
            "proposed",
        ): "The cited synthetic candidate is proposed, not promoted.",
    },
}


class ModelError(ValueError):
    """The report source or one of its proof credentials is invalid."""


def report_generator_digest(
    report_model_bytes: bytes,
    evidence_io_bytes: bytes,
    candidate_evidence_bytes: bytes,
    check_promotion_bytes: bytes,
) -> str:
    """Bind every executable report-generator component into one digest."""
    components = (
        evidence_io_bytes,
        candidate_evidence_bytes,
        check_promotion_bytes,
        report_model_bytes,
    )
    if any(type(component) is not bytes for component in components):
        raise ModelError("report generator components must be exact bytes")
    digest = hashlib.sha256()
    digest.update(REPORT_GENERATOR_DIGEST_DOMAIN)
    for path, content in zip(
        REPORT_GENERATOR_COMPONENT_PATHS,
        components,
        strict=True,
    ):
        digest.update(len(path).to_bytes(4, "big"))
        digest.update(path)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


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
    try:
        return read_stable_regular(path, label, max_bytes)
    except EvidenceError as exc:
        raise ModelError(
            f"{label} must be a stable regular file without symlink components: {exc}"
        ) from exc


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
            part not in {"", ".", ".."}
            and not part.startswith("-")
            and re.fullmatch(r"[A-Za-z0-9_.@+][A-Za-z0-9._@+=,-]*", part)
            is not None
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


def _git_bytes(repo_root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_")
    }
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    try:
        return subprocess.run(
            [
                "git",
                "--no-replace-objects",
                "-c",
                "core.useReplaceRefs=false",
                "-C",
                os.fspath(repo_root),
                *arguments,
            ],
            check=False,
            capture_output=True,
            env=environment,
        )
    except OSError as exc:
        raise ModelError("Git is required to validate report evidence") from exc


def _resolve_head_oid(repo_root: Path, errors: list[str]) -> str | None:
    root = _absolute_lexical(repo_root)
    resolved = _git_bytes(
        root,
        "rev-parse",
        "--verify",
        "--end-of-options",
        "HEAD^{commit}",
    )
    try:
        oid = resolved.stdout.decode("ascii").removesuffix("\n")
    except UnicodeDecodeError:
        oid = ""
    if (
        resolved.returncode != 0
        or resolved.stdout.count(b"\n") != 1
        or HEX_40.fullmatch(oid) is None
    ):
        errors.append("repository HEAD must resolve to one exact Git commit OID")
        return None
    object_type = _git_bytes(root, "cat-file", "-t", oid)
    if object_type.returncode != 0 or object_type.stdout != b"commit\n":
        errors.append("repository HEAD must name an exact Git commit object")
        return None
    return oid


def _commit_object_exists(
    repo_root: Path,
    revision: object,
    label: str,
    errors: list[str],
) -> bool:
    if not isinstance(revision, str) or HEX_40.fullmatch(revision) is None:
        errors.append(f"{label} must be 40 lowercase hex")
        return False
    object_type = _git_bytes(
        _absolute_lexical(repo_root), "cat-file", "-t", revision
    )
    if object_type.returncode != 0 or object_type.stdout != b"commit\n":
        errors.append(f"{label} must name an existing exact Git commit object")
        return False
    return True


def _head_regular_path(
    repo_root: Path,
    head_oid: str | None,
    locator: str,
    label: str,
    errors: list[str],
) -> tuple[Path, bytes] | None:
    if not _safe_repo_locator(locator):
        errors.append(f"{label} must use a safe repo-relative POSIX path")
        return None
    if head_oid is None:
        errors.append(f"{label} cannot resolve pinned HEAD evidence")
        return None
    root = _absolute_lexical(repo_root)
    path = root.joinpath(*locator.split("/"))
    try:
        head_type = _git_bytes(
            root, "cat-file", "-t", f"{head_oid}:{locator}"
        )
    except ModelError as exc:
        errors.append(f"{label} cannot verify the HEAD-tracked evidence path: {exc}")
        return None
    if head_type.returncode != 0 or head_type.stdout != b"blob\n":
        errors.append(f"{label} must be a HEAD-tracked evidence path")
        return None
    head_size = _git_bytes(root, "cat-file", "-s", f"{head_oid}:{locator}")
    try:
        blob_size = int(head_size.stdout.decode("ascii").removesuffix("\n"))
    except (UnicodeDecodeError, ValueError):
        blob_size = -1
    if (
        head_size.returncode != 0
        or head_size.stdout.count(b"\n") != 1
        or blob_size < 0
        or blob_size > MAX_SOURCE_BYTES
    ):
        errors.append(
            f"{label} HEAD blob must not exceed {MAX_SOURCE_BYTES} bytes"
        )
        return None
    head_blob = _git_bytes(root, "cat-file", "blob", f"{head_oid}:{locator}")
    if head_blob.returncode != 0:
        errors.append(f"{label} cannot read the exact HEAD blob")
        return None
    try:
        worktree = _read_regular_without_symlinks(path, root, label)
    except ModelError as exc:
        errors.append(str(exc))
        return None
    if worktree != head_blob.stdout:
        errors.append(f"{label} must match the HEAD blob byte for byte")
        return None
    return path, head_blob.stdout


def _commit_blob_exists(
    repo_root: Path,
    revision: str,
    locator: str,
    label: str,
    errors: list[str],
) -> bool:
    root = _absolute_lexical(repo_root)
    object_type = _git_bytes(root, "cat-file", "-t", revision)
    if object_type.returncode != 0:
        errors.append(f"{label} revision must name an existing Git commit object")
        return False
    if object_type.stdout != b"commit\n":
        errors.append(f"{label} revision must name an exact Git commit object")
        return False
    blob = _git_bytes(root, "cat-file", "-t", f"{revision}:{locator}")
    if blob.returncode != 0 or blob.stdout != b"blob\n":
        errors.append(f"{label} locator must name a blob at the exact commit")
        return False
    return True


def _validate_evidence(
    value: object,
    repo_root: Path,
    head_oid: str | None,
    verified_head_blobs: dict[str, bytes],
    label: str,
    errors: list[str],
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
            checked = _head_regular_path(
                repo_root, head_oid, locator, label, errors
            )
            if checked is not None:
                _, blob = checked
                verified_head_blobs[locator] = blob
        else:
            errors.append(f"{label} must use a safe repo-relative POSIX path")
    elif kind == "commit":
        if not isinstance(revision, str) or HEX_40.fullmatch(revision) is None:
            errors.append(f"{label} commit revision must be 40 lowercase hex")
        if not _safe_repo_locator(locator):
            errors.append(f"{label} must use a safe repo-relative POSIX path")
        elif isinstance(revision, str) and HEX_40.fullmatch(revision) is not None:
            _commit_blob_exists(repo_root, revision, locator, label, errors)
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
    value: object,
    repo_root: Path,
    head_oid: str | None,
    verified_head_blobs: dict[str, bytes],
    label: str,
    errors: list[str],
) -> list[dict[str, object]]:
    if not isinstance(value, list) or not value:
        errors.append(f"{label} must be a nonempty evidence list")
        return []
    result = []
    for index, row in enumerate(value):
        checked = _validate_evidence(
            row,
            repo_root,
            head_oid,
            verified_head_blobs,
            f"{label}[{index}]",
            errors,
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


def _lineage_has_cycle(parent_map: dict[str, list[str]]) -> bool:
    states: dict[str, int] = {}

    def visit(round_id: str) -> bool:
        state = states.get(round_id, 0)
        if state == 1:
            return True
        if state == 2:
            return False
        states[round_id] = 1
        for parent in parent_map.get(round_id, []):
            if parent in parent_map and visit(parent):
                return True
        states[round_id] = 2
        return False

    return any(visit(round_id) for round_id in sorted(parent_map))


def _load_proof(path: Path, repo_root: Path, label: str) -> dict[str, object]:
    try:
        value, _ = load_canonical_evidence_object(path, label)
    except EvidenceError as exc:
        raise ModelError(str(exc)) from exc
    return value


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


def _load_task4_module() -> ModuleType:
    # check-promotion imports candidate_evidence by its script module name.
    # Loading the exact sibling modules keeps report validation on the same
    # transitive evidence and decision implementation as Task 4.
    _load_sibling_module("candidate_evidence", "candidate_evidence.py")
    return _load_sibling_module(
        "_booleanrazor_report_check_promotion",
        "check-promotion.py",
    )


def _claim_statement(row: dict[str, object]) -> str:
    kind = row.get("claim_kind")
    track = row.get("track")
    status = row.get("status")
    if not isinstance(kind, str) or not isinstance(track, str) or not isinstance(
        status, str
    ):
        raise ModelError("claim policy tuple is incomplete")
    statement = CLAIM_POLICY.get(kind, {}).get((track, status))
    if statement is None:
        raise ModelError(
            f"claim policy forbids claim_kind={kind}, track={track}, status={status}"
        )
    return statement


def _status_evidence_contract(
    row: dict[str, object],
    evidence: list[dict[str, object]],
    label: str,
    errors: list[str],
) -> None:
    status = row.get("status")
    if status == "verified_main" and not any(
        item.get("kind") == "path" and item.get("revision") == "main"
        for item in evidence
    ):
        errors.append(f"{label} verified_main requires HEAD-bound path evidence")
    if status == "verified_branch_only" and not any(
        item.get("kind") == "commit"
        and isinstance(item.get("revision"), str)
        and HEX_40.fullmatch(item["revision"]) is not None
        for item in evidence
    ):
        errors.append(
            f"{label} verified_branch_only requires full-SHA commit evidence"
        )


def _validate_historical_official_proof(
    row: dict[str, object],
    evidence: list[dict[str, object]],
    repo_root: Path,
    label: str,
    errors: list[str],
) -> None:
    track = row.get("track")
    status = row.get("status")
    if not isinstance(track, str) or not isinstance(status, str):
        errors.append(
            f"{label} has no ratified historical official provenance"
        )
        return
    key = (track, status)
    expected = HISTORICAL_OFFICIAL_PROOFS.get(key)
    if expected is None:
        errors.append(
            f"{label} has no ratified historical official provenance"
        )
        return
    proof = row.get("proof")
    if not isinstance(proof, dict) or any(
        proof.get(role) != "none" for role in CLAIM_PROOF_FIELDS
    ):
        errors.append(
            f"{label} historical official provenance uses commit bindings, not current-HEAD proof roles"
        )
    bindings = {
        (item.get("revision"), item.get("locator"))
        for item in evidence
        if item.get("kind") == "commit"
    }
    root = _absolute_lexical(repo_root)
    for (revision, locator), digest in sorted(expected.items()):
        if (revision, locator) not in bindings:
            errors.append(
                f"{label} requires ratified historical official provenance "
                f"{revision}:{locator}"
            )
            continue
        blob = _git_bytes(root, "cat-file", "blob", f"{revision}:{locator}")
        if blob.returncode != 0 or hashlib.sha256(blob.stdout).hexdigest() != digest:
            errors.append(
                f"{label} ratified historical official provenance digest mismatch"
            )


def _validate_claim_proof(
    row: dict[str, object],
    evidence: list[dict[str, object]],
    repo_root: Path,
    verified_head_blobs: dict[str, bytes],
    label: str,
    errors: list[str],
) -> dict[str, object] | None:
    proof = row.get("proof")
    if not _exact_keys(proof, CLAIM_PROOF_FIELDS, f"{label}.proof", errors):
        return None
    assert isinstance(proof, dict)
    path_locators = {
        item["locator"]
        for item in evidence
        if item.get("kind") == "path"
        and isinstance(item.get("locator"), str)
        and _safe_repo_locator(item["locator"])
    }
    resolved: dict[str, Path | None] = {}
    role_locators: dict[str, str] = {}
    root = _absolute_lexical(repo_root)
    for role in sorted(CLAIM_PROOF_FIELDS):
        locator = proof[role]
        if locator == "none":
            resolved[role] = None
            continue
        if not _safe_repo_locator(locator):
            errors.append(
                f"{label}.proof.{role} must be none or a safe repo-relative POSIX path"
            )
            resolved[role] = None
            continue
        assert isinstance(locator, str)
        if locator not in path_locators:
            errors.append(
                f"{label}.proof.{role} must reference exact HEAD-bound path evidence"
            )
            resolved[role] = None
            continue
        if locator not in verified_head_blobs:
            errors.append(
                f"{label}.proof.{role} lacks verified pinned-HEAD bytes"
            )
            resolved[role] = None
            continue
        role_locators[role] = locator
        resolved[role] = root.joinpath(*locator.split("/"))

    def roles_match_pinned_head(stage: str) -> bool:
        valid = True
        for role, locator in sorted(role_locators.items()):
            path = resolved[role]
            assert path is not None
            try:
                current = _read_regular_without_symlinks(
                    path,
                    repo_root,
                    f"{label}.proof.{role}",
                )
            except ModelError as exc:
                errors.append(f"{label}.proof.{role} {stage}: {exc}")
                valid = False
                continue
            if current != verified_head_blobs[locator]:
                errors.append(
                    f"{label}.proof.{role} changed from the pinned HEAD blob {stage}"
                )
                valid = False
        return valid

    if not roles_match_pinned_head("before proof replay"):
        return None

    official_path = resolved["official_record"]
    if official_path is not None:
        _validate_official_record(official_path, repo_root, errors)

    decision_path = resolved["promotion_decision"]
    request_path = resolved["promotion_request"]
    policy_path = resolved["trust_policy"]
    decision: dict[str, object] | None = None
    decision_raw: bytes | None = None
    if decision_path is not None:
        try:
            decision = _load_proof(
                decision_path, repo_root, "promotion decision"
            )
            decision_locator = role_locators.get("promotion_decision")
            if decision_locator is not None:
                decision_raw = verified_head_blobs[decision_locator]
        except ModelError as exc:
            errors.append(f"{label} promotion decision: {exc}")
        if row.get("claim_kind") == "sealed_promotion":
            _validate_sealed_decision(decision_path, repo_root, errors)

    if (decision_path is None) != (request_path is None):
        errors.append(
            f"{label} replayable promotion proof requires both promotion_decision and promotion_request"
        )
    if decision_path is None or request_path is None or decision_raw is None:
        roles_match_pinned_head("after proof validation")
        return decision

    try:
        task4 = _load_task4_module()
        recomputed = task4.build_decision(request_path, policy_path)
        recomputed_raw = canonical_evidence_json_bytes(recomputed)
    except (
        EvidenceError,
        ModelError,
        OSError,
        TypeError,
        ValueError,
        KeyError,
        ImportError,
    ) as exc:
        errors.append(f"{label} replayable promotion proof is invalid: {exc}")
        roles_match_pinned_head("after proof replay")
        return decision
    if not roles_match_pinned_head("after proof replay"):
        return decision
    if decision_raw != recomputed_raw:
        errors.append(
            f"{label} promotion decision must equal the recomputed Task 4 decision byte for byte"
        )
        return decision
    return recomputed


def validate_project(
    project: dict[str, object], repo_root: Path
) -> list[str]:
    """Return deterministic diagnostics for one decoded project object."""
    errors: list[str] = []
    head_oid = _resolve_head_oid(repo_root, errors)
    verified_head_blobs: dict[str, bytes] = {}
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
    research_rounds = _record_list(
        project, "research_rounds", RESEARCH_ROUND_FIELDS, errors
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
        (research_rounds, "round_id", "research_rounds"),
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
        evidence = _validate_evidence_list(
            row["evidence"],
            repo_root,
            head_oid,
            verified_head_blobs,
            f"{label}.evidence",
            errors,
        )
        _status_evidence_contract(row, evidence, label, errors)
    if seen_instances != set(CONTROL_GATES) or len(controls) != 4:
        errors.append("controls must contain each disclosed mystery-A through mystery-D once")

    def evidence_for(
        row: dict[str, object], label: str
    ) -> list[dict[str, object]]:
        evidence = _validate_evidence_list(
            row["evidence"],
            repo_root,
            head_oid,
            verified_head_blobs,
            f"{label}.evidence",
            errors,
        )
        _status_evidence_contract(row, evidence, label, errors)
        return evidence

    for index, row in enumerate(methods):
        label = f"methods[{index}]"
        for field in ("method_id", "title", "scope", "summary"):
            _nonempty_string(row[field], f"{label}.{field}", errors)
        if not isinstance(row["status"], str) or row["status"] not in STATUSES:
            errors.append(f"{label} has invalid status")
        for field in ("insights", "optimization", "stop_rules", "limitations"):
            _string_list(row[field], f"{label}.{field}", errors)
        evidence = evidence_for(row, label)
        if row["status"] != "verified_main" and not row["limitations"]:
            errors.append(f"{label} limitation must not be empty")

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
        evidence = evidence_for(row, label)
        if row["status"] != "verified_main" and not row["limitations"]:
            errors.append(f"{label} limitation must not be empty")
        if (
            row["track"] == "sealed_confirmation"
            and row["status"] == "verified_main"
        ):
            errors.append(
                f"{label} cannot report verified_main sealed evidence without a sanitized authenticated attestation"
            )

    round_ids: dict[str, int] = {}
    parent_map: dict[str, list[str]] = {}
    seen_round_indexes: set[int] = set()
    root_count = 0
    turning_point_count = 0
    for index, row in enumerate(research_rounds):
        label = f"research_rounds[{index}]"
        for field in (
            "round_id",
            "title",
            "branch",
            "hypothesis",
            "independent_variable",
            "outcome",
            "decision",
            "insight",
            "next_pivot",
        ):
            _nonempty_string(row[field], f"{label}.{field}", errors)
        for field in ("permitted_data", "frozen_controls", "limitations"):
            _string_list(
                row[field],
                f"{label}.{field}",
                errors,
                require_nonempty=True,
            )

        round_index = row["round_index"]
        if type(round_index) is not int or round_index <= 0:
            errors.append(
                f"{label}.round_index must be a positive JSON integer"
            )
        else:
            if round_index in seen_round_indexes:
                errors.append(
                    f"research_rounds has duplicate round_index: {round_index}"
                )
            seen_round_indexes.add(round_index)

        round_id = row["round_id"]
        parents = row["parent_round_ids"]
        if _string_list(parents, f"{label}.parent_round_ids", errors):
            assert isinstance(parents, list)
            if len(parents) != len(set(parents)):
                errors.append(f"{label}.parent_round_ids must be unique")
            if isinstance(round_id, str) and round_id in parents:
                errors.append(f"{label}.parent_round_ids must not name itself")
            if not parents:
                root_count += 1
            if isinstance(round_id, str):
                parent_map[round_id] = list(parents)
        if isinstance(round_id, str) and type(round_index) is int:
            round_ids[round_id] = round_index

        if not isinstance(row["track"], str) or row["track"] not in TRACKS:
            errors.append(f"{label} has invalid track")
        if not isinstance(row["status"], str) or row["status"] not in STATUSES:
            errors.append(f"{label} has invalid status")
        if (
            row["track"] == "sealed_confirmation"
            and row["status"] == "verified_main"
        ):
            errors.append(
                f"{label} cannot report verified_main sealed evidence without a sanitized authenticated attestation"
            )
        if type(row["turning_point"]) is not bool:
            errors.append(f"{label}.turning_point must be a JSON boolean")
        elif row["turning_point"]:
            turning_point_count += 1

        _commit_object_exists(
            repo_root, row["base_revision"], f"{label}.base_revision", errors
        )
        _commit_object_exists(
            repo_root,
            row["result_revision"],
            f"{label}.result_revision",
            errors,
        )
        evidence = evidence_for(row, label)
        if not any(
            item.get("kind") == "commit"
            and item.get("revision") == row["result_revision"]
            for item in evidence
        ):
            errors.append(
                f"{label} must include commit evidence bound to result_revision"
            )

        runs = row["runs"]
        if not isinstance(runs, list) or not runs:
            errors.append(f"{label}.runs must be a nonempty list")
            continue
        checked_runs: list[dict[str, object]] = []
        for run_index, run in enumerate(runs):
            run_label = f"{label}.runs[{run_index}]"
            if not _exact_keys(run, ROUND_RUN_FIELDS, run_label, errors):
                continue
            assert isinstance(run, dict)
            checked_runs.append(run)
            for field in ("run_id", "classification", "outcome"):
                _nonempty_string(run[field], f"{run_label}.{field}", errors)
            if (
                not isinstance(run["status"], str)
                or run["status"] not in RUN_STATUSES
            ):
                errors.append(f"{run_label} has invalid status")
            _validate_evidence_list(
                run["evidence"],
                repo_root,
                head_oid,
                verified_head_blobs,
                f"{run_label}.evidence",
                errors,
            )
        _unique_ids(checked_runs, "run_id", f"{label}.runs", errors)

    if seen_round_indexes != set(range(1, len(research_rounds) + 1)):
        errors.append(
            "research_rounds round_index values must be contiguous positive integers starting at 1"
        )
    if root_count != 1:
        errors.append("research_rounds must contain exactly one root")
    if turning_point_count < 1:
        errors.append("research_rounds must contain at least one turning point")
    for round_id, parents in sorted(parent_map.items()):
        child_index = round_ids.get(round_id)
        for parent in parents:
            parent_index = round_ids.get(parent)
            if parent_index is None:
                errors.append(
                    f"research_rounds round {round_id} names missing parent {parent}"
                )
            elif child_index is not None and parent_index >= child_index:
                errors.append(
                    f"research_rounds parent {parent} must precede child {round_id}"
                )
    if _lineage_has_cycle(parent_map):
        errors.append("research_rounds lineage must not contain a cycle")
    frontier_id = (
        info.get("synthetic_frontier_round_id")
        if isinstance(info, dict)
        else None
    )
    frontier_matches = [
        row for row in research_rounds if row.get("round_id") == frontier_id
    ]
    if len(frontier_matches) != 1:
        errors.append(
            "project.synthetic_frontier_round_id must reference exactly one research round"
        )
    elif (
        frontier_matches[0].get("track") != "synthetic"
        or frontier_matches[0].get("status")
        not in {"verified_main", "verified_branch_only"}
    ):
        errors.append(
            "project.synthetic_frontier_round_id must reference a verified synthetic round"
        )

    for index, row in enumerate(claims):
        label = f"claims[{index}]"
        for field in ("claim_id", "claim_kind", "summary"):
            _nonempty_string(row[field], f"{label}.{field}", errors)
        if not isinstance(row["track"], str) or row["track"] not in TRACKS:
            errors.append(f"{label} has invalid track")
        if not isinstance(row["status"], str) or row["status"] not in STATUSES:
            errors.append(f"{label} has invalid status")
        _string_list(row["limitations"], f"{label}.limitations", errors)
        _string_list(row["missing_proof"], f"{label}.missing_proof", errors)
        evidence = evidence_for(row, label)
        if row["status"] != "verified_main" and not row["limitations"]:
            errors.append(f"{label} limitation must not be empty")
        proof_decision = _validate_claim_proof(
            row,
            evidence,
            repo_root,
            verified_head_blobs,
            label,
            errors,
        )
        claim_kind = row.get("claim_kind")
        if not isinstance(claim_kind, str) or claim_kind not in CLAIM_POLICY:
            errors.append(f"{label} has unknown claim_kind")
        else:
            try:
                _claim_statement(row)
            except ModelError as exc:
                errors.append(f"{label} {exc}")

        if claim_kind == "historical_disclosed_julia_pass":
            _validate_historical_official_proof(
                row,
                evidence,
                repo_root,
                label,
                errors,
            )

        if claim_kind == "promotion_state":
            if proof_decision is None:
                errors.append(
                    f"{label} promotion_state requires replayable promotion proof"
                )
            elif (
                proof_decision.get("track") != row.get("track")
                or proof_decision.get("decision") != row.get("status")
            ):
                errors.append(
                    f"{label} promotion_state must match the recomputed Task 4 track and decision"
                )

        if (
            row.get("status") == "verified_main"
            and claim_kind in {"official_verifier_pass", "blind_advantage"}
        ):
            errors.append(
                f"{label} positive current-head official or blind claims require a replayable promotion proof and a sanitized authenticated attestation"
            )
        proof = row.get("proof")
        if (
            claim_kind == "official_verifier_pass"
            and row.get("status") == "verified_main"
            and (
                not isinstance(proof, dict)
                or proof.get("official_record") == "none"
            )
        ):
            errors.append(
                f"{label} requires a canonical official-verification.json proof role"
            )
        if (
            row.get("status") == "verified_main"
            and (
                row.get("track") == "sealed_confirmation"
                or claim_kind == "sealed_promotion"
            )
        ):
            errors.append(
                f"{label} positive sealed claims require a sanitized authenticated attestation"
            )
        if (
            claim_kind == "sealed_promotion"
            and row.get("status") == "verified_main"
            and (
                not isinstance(proof, dict)
                or proof.get("promotion_decision") == "none"
            )
        ):
            errors.append(
                f"{label} requires a canonical sealed promotion decision proof role"
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
        f"{source_digest}; report generator SHA-256: {generator_digest} -->"
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
        f"report generator SHA-256: <code>{generator_digest}</code>"
        "</footer>\n"
        '  <script src="assets/report.js"></script>\n'
        "</body>\n"
        "</html>\n"
    ).encode("utf-8")


def _authoritative_conclusion(project: dict[str, object]) -> str:
    claims = project.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ModelError("authoritative conclusion requires claim records")
    statements = []
    for row in claims:
        if not isinstance(row, dict):
            raise ModelError("authoritative conclusion requires valid claim records")
        statements.append(_claim_statement(row))
    return " ".join(statements)


def _ordered_rounds(project: dict[str, object]) -> list[dict[str, object]]:
    rounds = project.get("research_rounds")
    if not isinstance(rounds, list):
        raise ModelError("research rounds are unavailable")
    if any(not isinstance(row, dict) for row in rounds):
        raise ModelError("research rounds must be valid records")
    return sorted(rounds, key=lambda row: int(row["round_index"]))


def _round_anchor(row: dict[str, object]) -> str:
    return "round-" + quote(str(row["round_id"]), safe="-._~")


def _html_string_list(items: object) -> str:
    if not isinstance(items, list):
        raise ModelError("rendered list field is unavailable")
    return "<ul>" + "".join(
        f"<li>{escape(str(item), quote=True)}</li>" for item in items
    ) + "</ul>"


def _sentence_list_text(items: object) -> str:
    if not isinstance(items, list):
        raise ModelError("rendered sentence-list field is unavailable")
    sentences: list[str] = []
    for item in items:
        sentence = str(item).strip()
        if sentence and sentence[-1] not in ".!?":
            sentence += "."
        sentences.append(sentence)
    return " ".join(sentences)


def _html_parent_links(
    row: dict[str, object], *, from_index: bool
) -> str:
    parents = row["parent_round_ids"]
    assert isinstance(parents, list)
    if not parents:
        return '<span class="root-label">Root round</span>'
    prefix = "experiments.html" if from_index else ""
    return ", ".join(
        f'<a href="{prefix}#round-{quote(str(parent), safe="-._~")}">'
        f"{escape(str(parent), quote=True)}</a>"
        for parent in parents
    )


def _render_lineage(project: dict[str, object]) -> str:
    nodes = []
    for row in _ordered_rounds(project):
        child = str(row["round_id"])
        child_attr = escape(child, quote=True)
        parents = row["parent_round_ids"]
        assert isinstance(parents, list)
        if parents:
            origins_class = (
                "lineage-origins has-multiple-parents"
                if len(parents) > 1
                else "lineage-origins"
            )
            origins = (
                f'<div class="{origins_class}" '
                f'aria-label="Parents of {child_attr}">'
                + "".join(
                    '<a class="lineage-parent-edge" '
                    f'data-lineage-parent="{escape(str(parent), quote=True)}" '
                    f'data-lineage-child="{child_attr}" '
                    f'href="#trace-{quote(str(parent), safe="-._~")}" '
                    f'aria-label="Parent edge {escape(str(parent), quote=True)} '
                    f'to {child_attr}">{escape(str(parent), quote=True)}</a>'
                    for parent in parents
                )
                + "</div>"
            )
        else:
            origins = (
                f'<div class="lineage-origins root-origin" '
                f'aria-label="{child_attr} is the root round">'
                '<span class="root-label">Root</span></div>'
            )
        turning = bool(row["turning_point"])
        turning_label = (
            '<span class="turning-label">Turning point</span>' if turning else ""
        )
        node_class = "lineage-node turning-point" if turning else "lineage-node"
        nodes.append(
            f'<li class="lineage-row">{origins}'
            '<span class="lineage-connector" aria-hidden="true"></span>'
            f'<article class="{node_class}" '
            f'id="trace-{quote(child, safe="-._~")}">'
            '<div class="lineage-kicker">'
            f'<span class="round-id">{child_attr}</span>'
            f'<span class="status status-{escape(str(row["status"]), quote=True)}">'
            f'{escape(str(row["status"]), quote=True)}</span>{turning_label}</div>'
            f'<h3><a href="experiments.html#{_round_anchor(row)}">'
            f'{escape(str(row["title"]), quote=True)}</a></h3>'
            '<p class="lineage-parents"><strong>Parents:</strong> '
            f"{_html_parent_links(row, from_index=True)}</p>"
            f'<p>{escape(str(row["outcome"]), quote=True)}</p>'
            f'<p class="lineage-decision"><strong>Decision:</strong> '
            f'{escape(str(row["decision"]), quote=True)}</p>'
            "</article></li>"
        )
    return (
        '<ol class="research-lineage" '
        'aria-label="Executed research-round parent-edge map">'
        + "".join(nodes)
        + "</ol>"
    )


def _synthetic_frontier(project: dict[str, object]) -> dict[str, object]:
    info = project.get("project")
    if not isinstance(info, dict):
        raise ModelError("project info is unavailable")
    frontier_id = info.get("synthetic_frontier_round_id")
    matches = [
        row
        for row in _ordered_rounds(project)
        if row.get("round_id") == frontier_id
    ]
    if len(matches) != 1:
        raise ModelError("synthetic frontier pointer is invalid")
    frontier = matches[0]
    if frontier.get("track") != "synthetic" or frontier.get("status") not in {
        "verified_main",
        "verified_branch_only",
    }:
        raise ModelError("synthetic frontier must be a verified synthetic round")
    return frontier


def _render_external_references(project: dict[str, object]) -> str:
    references = project.get("external_references")
    if not isinstance(references, list) or not references:
        raise ModelError("external report-design references are unavailable")
    items = []
    for reference in references:
        if not isinstance(reference, dict):
            raise ModelError("external report-design reference is invalid")
        items.append(
            "<li>"
            f'<a href="{escape(str(reference["url"]), quote=True)}" '
            'rel="noreferrer">'
            f'{escape(str(reference["title"]), quote=True)}</a>'
            f' — {escape(str(reference["use"]), quote=True)}'
            "</li>"
        )
    return (
        '<section class="design-references"><h2>Report design references</h2>'
        "<p>These examples informed the report's provenance and "
        "overview-to-detail presentation only. The report remains a local, "
        "deterministic renderer of BooleanRazor evidence.</p><ul>"
        + "".join(items)
        + "</ul></section>"
    )


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
        f"<li>{escape(_claim_statement(row), quote=True)}</li>"
        for row in claims
        if isinstance(row, dict) and row.get("status") in {"blocked", "absent"}
    )
    frontier = _synthetic_frontier(project)
    frontier_body = (
        '<p class="eyebrow">Recorded research trace · internal only</p>'
        f'<h2>{escape(str(frontier["round_id"]), quote=True)} · '
        f'{escape(str(frontier["title"]), quote=True)}</h2>'
        f'<p>{escape(str(frontier["outcome"]), quote=True)}</p>'
        '<div class="frontier-boundary"><strong>Boundary:</strong>'
        f"{_html_string_list(frontier['limitations'])}</div>"
        f'<p><a href="experiments.html#{_round_anchor(frontier)}">'
        "Inspect the exact round and runs</a></p>"
    )
    return (
        '<section class="hero">'
        f"<h1>{escape(str(info['title']), quote=True)}</h1>"
        f"<p>{escape(str(info['purpose']), quote=True)}</p>"
        "</section>"
        '<section class="frontier"><h2>Current internal synthetic frontier</h2>'
        f"{frontier_body}</section>"
        "<section><h2>Current conclusion</h2>"
        f"<p>{escape(_authoritative_conclusion(project), quote=True)}</p>"
        "<p><small>Generated from structural claim policy; author narrative is not "
        "used as verification evidence.</small></p></section>"
        '<section class="lineage-section"><div class="section-heading">'
        "<div><p class=\"eyebrow\">Executed history</p>"
        "<h2>Research trajectory</h2></div>"
        "<p>Each node is an actual recorded research round. Left-hand endpoints "
        "show its exact parent edges; merge rows join multiple parents. Dead ends "
        "and superseded runs remain in the detailed trace.</p></div>"
        f"{_render_lineage(project)}</section>"
        '<section class="table-wrap"><h2>Disclosed controls</h2>'
        "<table><thead><tr><th>Instance</th><th>Function</th><th>Gates</th>"
        f"<th>Status</th><th>Boundary</th></tr></thead><tbody>{rows}</tbody></table>"
        "</section><section><h2>Missing public and sealed proof</h2>"
        f"<ul>{blockers}</ul></section><section><h2>Next gate</h2>"
        f"<p>{escape(str(info['next_gate']), quote=True)}</p></section>"
        f"{_render_external_references(project)}"
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
    return (
        '<section class="hero"><h1>Methods</h1>'
        "<p>Method notes describe process. Authoritative scientific status is "
        "generated only from structural claim records in the evidence ledger.</p>"
        '</section><div class="method-grid">'
        + "".join(cards)
        + "</div>"
    )


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
        "separate authorities. This layer inventory is explanatory; authoritative "
        "result statements come only from structural claim records.</p></section>"
        '<section class="table-wrap"><table><thead><tr><th>Layer</th>'
        "<th>Authority</th><th>Meaning</th><th>Current state</th></tr></thead>"
        f"<tbody>{layer_rows}</tbody></table></section>"
        f'<section class="cards">{command_cards}</section>'
    )


def _render_experiments(project: dict[str, object]) -> str:
    experiments = project["experiments"]
    assert isinstance(experiments, list)
    registry_rows = "".join(
        "<tr "
        f'class="status-{escape(str(row["status"]), quote=True)}">'
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
    rounds = _ordered_rounds(project)
    status_buttons = "".join(
        '<button type="button" '
        f'data-status-filter="{escape(status, quote=True)}" '
        f'aria-pressed="false">{escape(status, quote=True)}</button>'
        for status in sorted({str(row["status"]) for row in rounds})
    )
    round_cards = []
    for row in rounds:
        turning = bool(row["turning_point"])
        turning_label = (
            '<span class="turning-label">Turning point</span>' if turning else ""
        )
        run_rows = "".join(
            "<tr "
            f'class="run-status-{escape(str(run["status"]), quote=True)}">'
            f'<td><code>{escape(str(run["run_id"]), quote=True)}</code></td>'
            f"<td>{escape(str(run['status']), quote=True)}</td>"
            f"<td>{escape(str(run['classification']), quote=True)}</td>"
            f"<td>{escape(str(run['outcome']), quote=True)}</td>"
            f"<td>{_html_evidence_list(run['evidence'])}</td>"
            "</tr>"
            for run in row["runs"]
            if isinstance(run, dict)
        )
        round_cards.append(
            f'<article class="research-round" id="{_round_anchor(row)}" '
            f'data-status="{escape(str(row["status"]), quote=True)}">'
            '<header class="round-header"><div>'
            f'<p class="round-id">{escape(str(row["round_id"]), quote=True)} '
            f'· round {row["round_index"]}</p>'
            f'<h2>{escape(str(row["title"]), quote=True)}</h2></div>'
            f'<div class="round-badges"><span class="status '
            f'status-{escape(str(row["status"]), quote=True)}">'
            f'{escape(str(row["status"]), quote=True)}</span>{turning_label}</div>'
            "</header>"
            '<dl class="trace-grid">'
            "<dt>Parents</dt>"
            f"<dd>{_html_parent_links(row, from_index=False)}</dd>"
            "<dt>Branch</dt>"
            f'<dd><code>{escape(str(row["branch"]), quote=True)}</code></dd>'
            "<dt>Base revision</dt>"
            f'<dd><code>{escape(str(row["base_revision"]), quote=True)}</code></dd>'
            "<dt>Result revision</dt>"
            f'<dd><code>{escape(str(row["result_revision"]), quote=True)}</code></dd>'
            "<dt>Track</dt>"
            f"<dd>{escape(str(row['track']), quote=True)}</dd>"
            "<dt>Status</dt>"
            f"<dd>{escape(str(row['status']), quote=True)}</dd>"
            "<dt>Turning point</dt>"
            f"<dd>{'Yes — research direction changed' if turning else 'No'}</dd>"
            "</dl>"
            '<div class="trace-fields">'
            '<section class="trace-field"><h3>Hypothesis</h3>'
            f"<p>{escape(str(row['hypothesis']), quote=True)}</p></section>"
            '<section class="trace-field"><h3>Independent variable</h3>'
            f"<p>{escape(str(row['independent_variable']), quote=True)}</p></section>"
            '<section class="trace-field"><h3>Permitted data</h3>'
            f"{_html_string_list(row['permitted_data'])}</section>"
            '<section class="trace-field"><h3>Frozen controls</h3>'
            f"{_html_string_list(row['frozen_controls'])}</section>"
            '<section class="trace-field"><h3>Outcome</h3>'
            f"<p>{escape(str(row['outcome']), quote=True)}</p></section>"
            '<section class="trace-field"><h3>Decision</h3>'
            f"<p>{escape(str(row['decision']), quote=True)}</p></section>"
            '<section class="trace-field"><h3>Insight</h3>'
            f"<p>{escape(str(row['insight']), quote=True)}</p></section>"
            '<section class="trace-field"><h3>Limitations</h3>'
            f"{_html_string_list(row['limitations'])}</section>"
            '<section class="trace-field"><h3>Next pivot</h3>'
            f"<p>{escape(str(row['next_pivot']), quote=True)}</p></section>"
            '<section class="trace-field"><h3>Round evidence</h3>'
            f"{_html_evidence_list(row['evidence'])}</section>"
            "</div>"
            '<section class="runs"><h3>Runs</h3>'
            '<div class="table-wrap"><table><thead><tr><th>Run ID</th>'
            "<th>Status</th><th>Classification</th><th>Outcome</th>"
            f"<th>Evidence</th></tr></thead><tbody>{run_rows}</tbody></table></div>"
            "</section></article>"
        )
    return (
        '<section class="hero"><h1>Experiments</h1>'
        "<p>This is the executed research trace, round by round. Outcomes and "
        "decisions are trace notes, not proof-bearing claims; failed, invalid, "
        "timed-out, equal, and superseded runs remain visible.</p></section>"
        '<section class="filter-bar" aria-label="Filter research rounds">'
        '<button type="button" data-status-filter="all" '
        f'aria-pressed="true">All rounds</button>{status_buttons}</section>'
        '<section class="round-stack" aria-label="Research round details">'
        + "".join(round_cards)
        + "</section>"
        '<section class="table-wrap"><h2>Study registry</h2>'
        "<p>The registry is a compact cross-check against the detailed rounds above.</p>"
        "<table><thead><tr><th>Experiment</th>"
        "<th>Track</th><th>Status</th><th>Location</th><th>Outcome</th>"
        f"<th>Decision</th><th>Evidence</th></tr></thead><tbody>{registry_rows}</tbody>"
        "</table></section>"
    )


REPORT_CSS = """\
:root { color-scheme: light; --ink: #172033; --paper: #f7f4ed; --panel: #fff;
  --line: #c8d0dc; --accent: #0b6e69; --accent-soft: #dff3ef;
  --muted: #596579; --turn: #b45124; --turn-soft: #fff0e7;
  --danger-soft: #fbe8e7; --shadow: 0 12px 32px rgb(23 32 51 / 8%); }
* { box-sizing: border-box; }
body { margin: 0; color: var(--ink); background: var(--paper);
  font-family: ui-sans-serif, system-ui, sans-serif; line-height: 1.55; }
.skip-link { position: absolute; left: -9999px; }
.skip-link:focus { left: 1rem; top: 1rem; z-index: 10; }
a:focus-visible, button:focus-visible { outline: 3px solid var(--accent);
  outline-offset: 3px; }
a { color: #075f5b; text-underline-offset: .18em; }
main, header, footer { width: min(1120px, calc(100% - 2rem)); margin-inline: auto; }
nav { display: flex; flex-wrap: wrap; gap: .5rem; padding-block: 1rem; }
nav a { padding: .45rem .7rem; }
.hero { padding: 3rem 0 1.5rem; }
section { margin-block: 2rem; }
.eyebrow, .round-id { margin: 0 0 .35rem; color: var(--muted);
  font-size: .78rem; font-weight: 750; letter-spacing: .08em;
  text-transform: uppercase; }
.frontier { padding: clamp(1.25rem, 3vw, 2rem); border: 1px solid #99c9c4;
  border-left: .45rem solid var(--accent); background: linear-gradient(135deg, #fff, var(--accent-soft));
  box-shadow: var(--shadow); }
.frontier > h2:first-child { margin-top: 0; font-size: .9rem; letter-spacing: .08em;
  text-transform: uppercase; }
.frontier-boundary ul { margin: .35rem 0 0; padding-left: 1.25rem; }
.section-heading { display: grid; grid-template-columns: minmax(0, 1fr) minmax(16rem, .8fr);
  gap: 1.5rem; align-items: end; }
.research-lineage { display: grid; gap: 1rem; margin: 1.5rem 0 0;
  padding: 0; list-style: none; }
.lineage-row { display: grid; grid-template-columns: minmax(6.5rem, 10rem) 2.5rem minmax(0, 1fr);
  align-items: stretch; }
.lineage-origins { position: relative; display: grid; align-content: center; gap: .4rem;
  padding-right: .8rem; }
.lineage-parent-edge, .root-origin .root-label { position: relative; z-index: 1;
  display: block; width: fit-content; max-width: 100%; margin-left: auto;
  padding: .2rem .48rem; border: 1px solid var(--line); border-radius: 999px;
  color: var(--muted); background: var(--paper); font-size: .76rem; font-weight: 750;
  overflow-wrap: anywhere; }
.lineage-parent-edge::after { position: absolute; top: 50%; left: 100%;
  width: .8rem; border-top: 2px solid var(--line); content: ""; }
.lineage-origins.has-multiple-parents::after { position: absolute; top: 1rem;
  right: 0; bottom: 1rem; border-right: 2px solid var(--line); content: ""; }
.lineage-connector { position: relative; min-height: 100%; }
.lineage-connector::before { position: absolute; top: 50%; left: 0; right: 0;
  border-top: 2px solid var(--line); content: ""; }
.lineage-connector::after { position: absolute; top: calc(50% - .28rem); right: .15rem;
  width: .48rem; height: .48rem; border-top: 2px solid var(--accent);
  border-right: 2px solid var(--accent); content: ""; transform: rotate(45deg); }
.lineage-node { position: relative; padding: 1rem 1.15rem; border: 1px solid var(--line);
  border-left: .28rem solid var(--accent);
  background: var(--panel); box-shadow: 0 4px 16px rgb(23 32 51 / 5%); }
.lineage-node.turning-point { border-color: #e0a27f; border-left-color: var(--turn);
  background: var(--turn-soft); }
.lineage-node h3 { margin: .35rem 0; }
.lineage-kicker, .round-badges { display: flex; flex-wrap: wrap; gap: .45rem;
  align-items: center; }
.lineage-parents, .lineage-decision { color: var(--muted); font-size: .92rem; }
.turning-label, .status { display: inline-flex; align-items: center; width: fit-content;
  padding: .16rem .48rem; border-radius: 999px; font-size: .75rem; font-weight: 750; }
.turning-label { color: #753214; background: #ffd9c4; }
.status { color: #24504d; background: var(--accent-soft); }
.status-rejected, .status-blocked, .status-absent { color: #712e2a;
  background: var(--danger-soft); }
.cards, .method-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; }
.card, .method-card { min-width: 0; padding: 1rem; border: 1px solid var(--line);
  background: var(--panel); }
.filter-bar { display: flex; flex-wrap: wrap; gap: .5rem; }
button { padding: .48rem .72rem; border: 1px solid var(--line); border-radius: .25rem;
  color: var(--ink); background: var(--panel); cursor: pointer; }
button[aria-pressed="true"] { color: #fff; border-color: var(--accent);
  background: var(--accent); }
.round-stack { display: grid; gap: 1.5rem; }
.research-round { min-width: 0; scroll-margin-top: 1rem; padding: clamp(1rem, 3vw, 2rem);
  border: 1px solid var(--line); border-top: .35rem solid var(--accent);
  background: var(--panel); box-shadow: var(--shadow); }
.research-round[hidden] { display: none; }
.round-header { display: flex; justify-content: space-between; gap: 1rem;
  align-items: flex-start; }
.round-header h2 { margin: 0; }
.trace-grid { display: grid; grid-template-columns: max-content minmax(0, 1fr);
  gap: .35rem 1rem; padding: 1rem; background: #f2f5f6; }
.trace-grid dt { color: var(--muted); font-weight: 700; }
.trace-grid dd { min-width: 0; margin: 0; overflow-wrap: anywhere; }
.trace-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: .75rem; }
.trace-field { margin: 0; padding: .9rem; border: 1px solid #dde2e8;
  background: #fff; }
.trace-field h3 { margin-top: 0; font-size: 1rem; }
.runs { margin-bottom: 0; }
.run-status-failed, .run-status-invalid, .run-status-timed_out {
  background: var(--danger-soft); }
.run-status-superseded, .run-status-equal { color: #4b5565; background: #eef0f3; }
.table-wrap { max-width: 100%; min-width: 0; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; background: var(--panel); }
th, td { padding: .7rem; border: 1px solid var(--line); text-align: left; }
code { overflow-wrap: anywhere; }
pre { padding: 1rem; overflow-x: auto; color: #fff; background: var(--ink); }
footer { padding-block: 2rem; }
@media (max-width: 760px) {
  .cards, .method-grid, .section-heading, .trace-fields { grid-template-columns: 1fr; }
  .round-header { display: grid; }
  .trace-grid { grid-template-columns: 1fr; }
  .trace-grid dd { margin-bottom: .45rem; }
  .lineage-row { grid-template-columns: minmax(4.5rem, 5.5rem) 1.35rem minmax(0, 1fr); }
  .lineage-origins { padding-right: .45rem; }
  .lineage-parent-edge, .root-origin .root-label { padding-inline: .35rem;
    font-size: .69rem; }
}
@media print { nav, .skip-link, script, button { display: none !important; }
  body { background: #fff; color: #000; }
  .research-round, .frontier, .lineage-node { box-shadow: none; break-inside: avoid; }
  .round-stack { display: block; }
}
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
    research_rounds = _ordered_rounds(project)
    claims = project["claims"]
    assert all(
        isinstance(rows, list)
        for rows in (controls, methods, experiments, research_rounds, claims)
    )
    status = (
        header
        + "# Status\n\n"
        + _markdown_text(_authoritative_conclusion(project))
        + "\n\n_Authoritative wording is generated from structural claim policy; "
        "author narrative is not verification evidence._"
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
            f"| {_markdown_text(_sentence_list_text(row['insights']))} "
            f"| {_markdown_text(_sentence_list_text(row['optimization']))} "
            f"| {_markdown_text(_sentence_list_text(row['stop_rules']))} |\n"
            for row in methods
            if isinstance(row, dict)
        )
    )
    trajectory_parts = [
        header,
        "# Research trajectory\n\n",
        "This index contains executed research rounds only. Failed, timed-out, "
        "invalid, equal, and superseded runs remain part of the record.\n\n",
        "| Round | Parents | Title | Track | Status | Turning point | Decision |\n",
        "| --- | --- | --- | --- | --- | --- | --- |\n",
    ]
    trajectory_parts.append(
        "".join(
            f"| {_markdown_text(row['round_id'])} "
            f"| {_markdown_text(', '.join(row['parent_round_ids']) or 'root')} "
            f"| {_markdown_text(row['title'])} | {_markdown_text(row['track'])} "
            f"| {_markdown_text(row['status'])} "
            f"| {'yes' if row['turning_point'] else 'no'} "
            f"| {_markdown_text(row['decision'])} |\n"
            for row in research_rounds
        )
    )
    for row in research_rounds:
        trajectory_parts.extend(
            (
                f"\n## {_markdown_text(row['round_id'])} — "
                f"{_markdown_text(row['title'])}\n\n",
                f"- Branch: `{_markdown_text(row['branch'])}`\n",
                f"- Base revision: `{_markdown_text(row['base_revision'])}`\n",
                f"- Result revision: `{_markdown_text(row['result_revision'])}`\n",
                f"- Hypothesis: {_markdown_text(row['hypothesis'])}\n",
                f"- Independent variable: {_markdown_text(row['independent_variable'])}\n",
                f"- Outcome: {_markdown_text(row['outcome'])}\n",
                f"- Insight: {_markdown_text(row['insight'])}\n",
                f"- Next pivot: {_markdown_text(row['next_pivot'])}\n",
                "\n### Runs\n\n",
                "| Run | Status | Classification | Outcome | Evidence |\n",
                "| --- | --- | --- | --- | --- |\n",
                "".join(
                    f"| {_markdown_text(run['run_id'])} "
                    f"| {_markdown_text(run['status'])} "
                    f"| {_markdown_text(run['classification'])} "
                    f"| {_markdown_text(run['outcome'])} "
                    f"| {'; '.join(_markdown_evidence(item) for item in run['evidence'])} |\n"
                    for run in row["runs"]
                    if isinstance(run, dict)
                ),
                "\n### Round evidence\n\n",
                "".join(
                    f"- {_markdown_evidence(item)}\n"
                    for item in row["evidence"]
                ),
            )
        )
    trajectory_parts.extend(
        (
            "\n# Study registry\n\n",
            "| Experiment | Track | Status | Location | Decision |\n",
            "| --- | --- | --- | --- | --- |\n",
            "".join(
                f"| {_markdown_text(row['title'])} | {_markdown_text(row['track'])} "
                f"| {_markdown_text(row['status'])} | {_markdown_text(row['location'])} "
                f"| {_markdown_text(row['decision'])} |\n"
                for row in experiments
                if isinstance(row, dict)
            ),
        )
    )
    experiments_md = "".join(trajectory_parts)
    ledger_parts = [header, "# Evidence ledger\n\n"]
    for row in claims:
        assert isinstance(row, dict)
        ledger_parts.extend(
            (
                f"## {_markdown_text(row['claim_id'])}\n\n",
                _markdown_text(_claim_statement(row)) + "\n\n",
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
    ledger_parts.append("\n# Research-round provenance\n\n")
    for row in research_rounds:
        ledger_parts.extend(
            (
                f"## {_markdown_text(row['round_id'])}\n\n",
                f"Result revision: `{_markdown_text(row['result_revision'])}`\n\n",
                "Round evidence:\n\n",
                "".join(
                    f"- {_markdown_evidence(item)}\n"
                    for item in row["evidence"]
                ),
                "\nRun evidence:\n\n",
                "".join(
                    f"- {_markdown_text(run['run_id'])} "
                    f"({_markdown_text(run['status'])}): "
                    + "; ".join(
                        _markdown_evidence(item)
                        for item in run["evidence"]
                    )
                    + "\n"
                    for run in row["runs"]
                    if isinstance(run, dict)
                ),
                "\n",
            )
        )
    ledger_md = "".join(ledger_parts).rstrip("\n") + "\n"
    return {
        "docs/STATUS.md": status.encode("utf-8"),
        "docs/METHODS.md": methods_md.encode("utf-8"),
        "docs/EXPERIMENT_INDEX.md": experiments_md.encode("utf-8"),
        "research/EVIDENCE_LEDGER.md": ledger_md.encode("utf-8"),
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
