#!/usr/bin/env python3
"""Fail-closed, deterministic evidence-track promotion decisions."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from candidate_evidence import CandidateEvidence, TerminalEvidence, load_candidate_manifest, load_terminal_manifest
from evidence_io import DEFAULT_MAX_BYTES, HEX_64, EvidenceError, atomic_create, canonical_json_bytes, load_canonical_object, read_stable_regular, resolve_evidence_path, sha256_bytes


TRACK_CEILINGS = {
    "disclosed_control": "promote_control",
    "synthetic": "advance_public_candidate",
    "blind_visible": "freeze_candidate",
    "sealed_confirmation": "promote_blind_result",
}
REQUEST_FIELDS = {"schema_version", "track", "candidate_evidence", "deterministic_pairs", "official_verifications", "frozen_comparison", "sealed_results"}
DISCLOSED_PREDICTION_COMMITMENTS = {
    "mystery-A": "51e3f026def41778ecd0d7dcaee9f970b9937488e6716891932b73824c16d4c7",
    "mystery-B": "e2c9d0e23ee36bfc0f12d7f39fdfe2ca5a8abe8eb194fec56500733694b75c28",
    "mystery-C": "c7b37413844bf0b10ebad0010046469f500354a22cc2ba95cbe42709f8e8337d",
    "mystery-D": "b445a717483303fa3c5d8a1f7abe81888b267b7c472121c9c464fa9766808580",
}
REJECTION_CODES = {
    "foreign_verification_record", "nondeterministic_pair", "mixed_source_commit",
    "mixed_tree_digest", "mixed_dataset_boundary", "mixed_hardware", "mixed_timeout_cap",
    "filtered_terminal_failure", "frozen_comparison_digest_mismatch",
    "control_instance_set_mismatch", "prediction_commitment_mismatch",
    "native_run_incomplete", "comparison_projection_mismatch", "external_trust_policy_mismatch",
}


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


def _require_exact_fields(value: dict[str, object], fields: set[str], label: str) -> None:
    if set(value) != fields:
        raise EvidenceError(f"{label} has missing or extra fields")


def _relative_key(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise EvidenceError("resolved input escapes request root") from exc


def _resolve_many(root: Path, value: object, label: str, digests: dict[str, str]) -> list[Path]:
    if value == "none":
        return []
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise EvidenceError(f"{label} must be none or a nonempty path list")
    paths = [resolve_evidence_path(root, item, label) for item in value]
    if len(set(paths)) != len(paths):
        raise EvidenceError(f"{label} contains duplicate paths")
    for path in paths:
        digests[_relative_key(root, path)] = sha256_bytes(read_stable_regular(path, path.name, DEFAULT_MAX_BYTES))
    return paths


def _resolve_one(root: Path, value: object, label: str, digests: dict[str, str]) -> Path | None:
    if value == "none":
        return None
    if not isinstance(value, str):
        raise EvidenceError(f"{label} must be none or one relative path")
    path = resolve_evidence_path(root, value, label)
    digests[_relative_key(root, path)] = sha256_bytes(read_stable_regular(path, path.name, DEFAULT_MAX_BYTES))
    return path


def _load_record(path: Path) -> tuple[dict[str, object], bytes]:
    record, raw = load_canonical_object(path, "official verification")
    _require_exact_fields(record, {"bit_accuracy", "circuit_sha256", "comparison_id", "dataset_sha256", "exact_accuracy", "gates", "julia_version", "manifest_sha256", "run_spec_sha256", "samples", "schema_version", "status", "verify_jl_sha256"}, "official verification")
    if type(record["schema_version"]) is not int or record["schema_version"] != 1 or record["status"] != "pass":
        raise EvidenceError("official verification is not a pass record")
    if not isinstance(record["comparison_id"], str) or type(record["gates"]) is not int or record["gates"] < 0:
        raise EvidenceError("official verification has invalid identity")
    if record["exact_accuracy"] != "1.0" or record["bit_accuracy"] != "1.0" or type(record["samples"]) is not int or record["samples"] <= 0:
        raise EvidenceError("official verification does not prove an exact pass")
    if not all(isinstance(record[field], str) and HEX_64.fullmatch(record[field]) for field in ("circuit_sha256", "dataset_sha256", "manifest_sha256", "run_spec_sha256", "verify_jl_sha256")):
        raise EvidenceError("official verification has invalid digest")
    if not isinstance(record["julia_version"], dict) or set(record["julia_version"]) != {"sha256", "text"} or not isinstance(record["julia_version"]["sha256"], str) or not HEX_64.fullmatch(record["julia_version"]["sha256"]) or not isinstance(record["julia_version"]["text"], str) or not record["julia_version"]["text"] or any(ord(char) < 32 or ord(char) > 126 for char in record["julia_version"]["text"]):
        raise EvidenceError("official verification has invalid Julia version")
    return record, raw


def _pair_byte_identical(left: CandidateEvidence, right: CandidateEvidence) -> bool:
    if left.deterministic_fingerprint() != right.deterministic_fingerprint():
        return False
    for left_path, right_path in ((left.completed_table_path, right.completed_table_path), (left.circuit_path, right.circuit_path), (left.artifact_path, right.artifact_path)):
        if read_stable_regular(left_path, left_path.name, 512 * 1024 * 1024) != read_stable_regular(right_path, right_path.name, 512 * 1024 * 1024):
            return False
    return True


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
    if len({(row.blind, row.evaluation_scope) for row in bundle.terminals}) > 1:
        reasons.append("mixed_dataset_boundary")
    if len({row.hardware for row in bundle.terminals}) > 1:
        reasons.append("mixed_hardware")
    if len({row.timeout_seconds for row in bundle.terminals}) > 1:
        reasons.append("mixed_timeout_cap")
    if bundle.verifications and {row.circuit_sha256 for row in bundle.candidates} != {record.circuit_sha256 for record in bundle.verifications}:
        reasons.append("foreign_verification_record")
    if any(not pair.byte_identical for pair in bundle.pairs):
        reasons.append("nondeterministic_pair")
    if any(row.status not in {"SUCCESS", "VERIFIER_FAILED", "VERIFIER_NOT_RUN"} for row in bundle.terminals):
        reasons.append("terminal_failure_present")
    return sorted(set(reasons))


def quality_key(candidate: CandidateEvidence) -> tuple[Decimal, int]:
    return (Decimal(candidate.visible_cv_exact), -candidate.gates)


def _load_comparison(root: Path, path: Path, track: str, digests: dict[str, str]) -> tuple[dict[str, object], bytes, dict[str, object]]:
    comparison, raw = load_canonical_object(path, "frozen comparison")
    _require_exact_fields(comparison, {"baseline_ids", "candidate_ids", "design_path", "design_sha256", "expected_ids", "frozen_candidate_id", "rule", "schema_version"}, "frozen comparison")
    if type(comparison["schema_version"]) is not int or comparison["schema_version"] != 1 or comparison["rule"] != "accuracy_first_then_gates":
        raise EvidenceError("frozen comparison has invalid rule")
    for field in ("baseline_ids", "candidate_ids", "expected_ids"):
        if not isinstance(comparison[field], list) or not comparison[field] or not all(isinstance(item, str) for item in comparison[field]) or len(set(comparison[field])) != len(comparison[field]):
            raise EvidenceError("frozen comparison has invalid identifiers")
    if set(comparison["baseline_ids"]) & set(comparison["candidate_ids"]) or comparison["frozen_candidate_id"] not in comparison["candidate_ids"]:
        raise EvidenceError("frozen comparison has invalid role partition")
    if not isinstance(comparison["design_path"], str) or not isinstance(comparison["design_sha256"], str) or not HEX_64.fullmatch(comparison["design_sha256"]):
        raise EvidenceError("frozen comparison has invalid design binding")
    design_path = resolve_evidence_path(root, comparison["design_path"], "visible design")
    design, design_raw = load_canonical_object(design_path, "visible design")
    digests[_relative_key(root, design_path)] = sha256_bytes(design_raw)
    if comparison["design_sha256"] != sha256_bytes(design_raw):
        raise _Reject("frozen_comparison_digest_mismatch")
    _require_exact_fields(design, {"cells", "dataset_boundary", "schema_version"}, "visible design")
    if type(design["schema_version"]) is not int or design["schema_version"] != 1 or not isinstance(design["dataset_boundary"], str) or not isinstance(design["cells"], list):
        raise EvidenceError("visible design has invalid schema")
    projection: list[tuple[str, str]] = []
    for cell in design["cells"]:
        if not isinstance(cell, dict) or set(cell) != {"comparison_id", "dataset_id"} or not all(isinstance(cell[key], str) for key in cell):
            raise EvidenceError("visible design has invalid cell")
        projection.append((cell["comparison_id"], cell["dataset_id"]))
    if len(projection) != len(comparison["expected_ids"]) or len({pair[0] for pair in projection}) != len(projection) or {pair[0] for pair in projection} != set(comparison["expected_ids"]):
        raise EvidenceError("visible design does not match comparison identifiers")
    if track in {"blind_visible", "sealed_confirmation"}:
        commitment_raw = read_stable_regular(Path(__file__).resolve().parents[1] / "reblind" / "COMMITMENT.txt", "reblind commitment", DEFAULT_MAX_BYTES)
        if len(commitment_raw) != 65 or commitment_raw[-1:] != b"\n" or not HEX_64.fullmatch(commitment_raw[:-1].decode("ascii")):
            raise EvidenceError("reblind commitment is invalid")
        commitment = commitment_raw[:-1].decode("ascii")
        if design["dataset_boundary"] != commitment:
            raise EvidenceError("blind design does not match the reblind commitment")
    return comparison, raw, design


class _Reject(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


def _load_trust_policy(path: Path | None, digests: dict[str, str]) -> dict[str, object] | None:
    if path is None:
        return None
    policy, raw = load_canonical_object(path, "external trust policy")
    _require_exact_fields(policy, {"frozen_comparison_sha256", "official_verifications", "schema_version", "sealed_results_sha256"}, "external trust policy")
    if type(policy["schema_version"]) is not int or policy["schema_version"] != 1 or not isinstance(policy["frozen_comparison_sha256"], str) or not HEX_64.fullmatch(policy["frozen_comparison_sha256"]) or (policy["sealed_results_sha256"] != "none" and (not isinstance(policy["sealed_results_sha256"], str) or not HEX_64.fullmatch(policy["sealed_results_sha256"]))):
        raise EvidenceError("external trust policy has invalid schema")
    entries = policy["official_verifications"]
    if not isinstance(entries, list):
        raise EvidenceError("external trust policy has invalid official bindings")
    identifiers: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"comparison_id", "sha256"} or not isinstance(entry["comparison_id"], str) or not HEX_64.fullmatch(entry["sha256"] if isinstance(entry["sha256"], str) else "") or entry["comparison_id"] in identifiers:
            raise EvidenceError("external trust policy has invalid official bindings")
        identifiers.add(entry["comparison_id"])
    digests["external_trust_policy"] = sha256_bytes(raw)
    return policy


def build_decision(request_path: Path, trust_policy_path: Path | None = None) -> dict[str, object]:
    request, request_raw = load_canonical_object(request_path, "promotion request")
    _require_exact_fields(request, REQUEST_FIELDS, "promotion request")
    if type(request["schema_version"]) is not int or request["schema_version"] != 1 or request["track"] not in TRACK_CEILINGS:
        raise EvidenceError("promotion request has invalid schema version or track")
    track = request["track"]
    root = request_path.parent
    digests: dict[str, str] = {request_path.name: sha256_bytes(request_raw)}
    trust_policy = _load_trust_policy(trust_policy_path, digests)
    candidate_paths = _resolve_many(root, request["candidate_evidence"], "candidate evidence", digests)
    verification_paths = _resolve_many(root, request["official_verifications"], "official verifications", digests)
    frozen_path = _resolve_one(root, request["frozen_comparison"], "frozen comparison", digests)
    sealed_path = _resolve_one(root, request["sealed_results"], "sealed results", digests)
    pair_rows = request["deterministic_pairs"]
    if pair_rows != "none" and (not isinstance(pair_rows, list) or not pair_rows):
        raise EvidenceError("deterministic pairs must be none or a nonempty list")
    pair_paths: list[tuple[Path, Path]] = []
    if isinstance(pair_rows, list):
        endpoints: list[Path] = []
        for row in pair_rows:
            if not isinstance(row, dict) or set(row) != {"left", "right"} or not isinstance(row["left"], str) or not isinstance(row["right"], str):
                raise EvidenceError("deterministic pair has invalid shape")
            left = resolve_evidence_path(root, row["left"], "deterministic pair")
            right = resolve_evidence_path(root, row["right"], "deterministic pair")
            if left == right:
                raise EvidenceError("deterministic pair cannot reference itself")
            endpoints.extend((left, right))
            pair_paths.append((left, right))
            for path in (left, right):
                digests.setdefault(_relative_key(root, path), sha256_bytes(read_stable_regular(path, path.name, DEFAULT_MAX_BYTES)))
        if len(set(endpoints)) != len(endpoints):
            raise EvidenceError("deterministic pair endpoints are duplicated")
    terminals = tuple(load_terminal_manifest(path) for path in candidate_paths)
    if len({row.comparison_id for row in terminals}) != len(terminals):
        raise EvidenceError("candidate evidence has duplicate comparison_id")
    candidates: list[CandidateEvidence] = []
    for terminal in terminals:
        if terminal.status in {"SUCCESS", "VERIFIER_FAILED", "VERIFIER_NOT_RUN"}:
            candidates.append(load_candidate_manifest(terminal.manifest_path))
    if len({row.comparison_id for row in candidates}) != len(candidates):
        raise EvidenceError("candidate evidence has duplicate candidate comparison_id")
    by_path = {row.manifest_path: row for row in candidates}
    pairs: list[DeterministicPair] = []
    pair_partition_bad = False
    if pair_paths:
        if {path for pair in pair_paths for path in pair} != set(by_path):
            pair_partition_bad = True
        else:
            for left_path, right_path in pair_paths:
                left, right = by_path[left_path], by_path[right_path]
                if left.comparison_id >= right.comparison_id:
                    pair_partition_bad = True
                pairs.append(DeterministicPair(left, right, _pair_byte_identical(left, right)))
    records: list[VerificationBinding] = []
    record_rows = [(path, *_load_record(path)) for path in verification_paths]
    lefts = {pair.left.comparison_id: pair.left for pair in pairs}
    record_bad = False
    if record_rows:
        if len(record_rows) != len(lefts) or {record["comparison_id"] for _, record, _ in record_rows} != set(lefts):
            record_bad = True
        else:
            for path, record, _ in record_rows:
                left = lefts[record["comparison_id"]]
                if path != left.manifest_path.with_name("official-verification.json") or any(record[field] != getattr(left, field) for field in ("manifest_sha256", "run_spec_sha256", "circuit_sha256")) or record["gates"] != left.gates:
                    record_bad = True
                    continue
                records.append(VerificationBinding(record["comparison_id"], record["manifest_sha256"], record["circuit_sha256"], record["dataset_sha256"], record["gates"]))
    bundle = EvidenceBundle(terminals, tuple(candidates), tuple(pairs), tuple(records))
    reasons = set(common_reason_codes(bundle))
    if pair_partition_bad:
        reasons.add("nondeterministic_pair")
    if record_bad:
        reasons.add("foreign_verification_record")
    if terminals:
        run_roots = {row.run_root for row in terminals}
        if len(run_roots) != 1:
            reasons.add("native_run_incomplete")
        else:
            run_root = next(iter(run_roots))
            spec, _ = load_canonical_object(run_root / "run_spec.json", "run_spec.json")
            native = {run_root / "cells" / cell["cell_id"] / "manifest.json" for cell in spec["cells"] if isinstance(cell, dict) and isinstance(cell.get("cell_id"), str)}
            if native != set(candidate_paths):
                reasons.add("native_run_incomplete")
    comparison: dict[str, object] | None = None
    comparison_raw: bytes | None = None
    design: dict[str, object] | None = None
    if frozen_path is None:
        reasons.add("frozen_comparison_absent")
    else:
        try:
            comparison, comparison_raw, design = _load_comparison(root, frozen_path, track, digests)
        except _Reject as exc:
            reasons.add(exc.code)
    if comparison is not None and design is not None:
        terminal_ids = {row.comparison_id for row in terminals}
        expected_ids = set(comparison["expected_ids"])
        if expected_ids - terminal_ids:
            reasons.add("missing_comparison_cell")
        if any(row.status not in {"SUCCESS", "VERIFIER_FAILED", "VERIFIER_NOT_RUN"} and row.comparison_id in expected_ids for row in terminals):
            reasons.update({"filtered_terminal_failure", "terminal_failure_present"})
        projection = {cell["comparison_id"]: cell["dataset_id"] for cell in design["cells"]}
        if any(row.comparison_id not in projection or row.dataset_id != projection[row.comparison_id] for row in terminals):
            reasons.add("comparison_projection_mismatch")
        if set(pair.left.comparison_id for pair in pairs) != set(comparison["baseline_ids"]) | set(comparison["candidate_ids"]) or {item.comparison_id for pair in pairs for item in (pair.left, pair.right)} != expected_ids:
            reasons.add("comparison_projection_mismatch")
        baseline_ids, candidate_ids = set(comparison["baseline_ids"]), set(comparison["candidate_ids"])
        for pair in pairs:
            if pair.left.role != pair.right.role or (pair.left.comparison_id in baseline_ids and pair.left.role != "baseline") or (pair.left.comparison_id in candidate_ids and pair.left.role != "candidate"):
                reasons.add("comparison_projection_mismatch")
        if trust_policy is None:
            reasons.add("external_trust_policy_absent")
        elif trust_policy["frozen_comparison_sha256"] != sha256_bytes(comparison_raw):
            reasons.add("external_trust_policy_mismatch")
        else:
            anchored = {(entry["comparison_id"], entry["sha256"]) for entry in trust_policy["official_verifications"]}
            actual = {(record["comparison_id"], sha256_bytes(raw)) for _, record, raw in record_rows}
            if anchored != actual:
                reasons.add("external_trust_policy_mismatch")
    sealed_ok = False
    if track == "sealed_confirmation":
        if sealed_path is None:
            reasons.add("sealed_results_absent")
        elif comparison is not None and comparison_raw is not None:
            sealed, _ = load_canonical_object(sealed_path, "sealed result")
            _require_exact_fields(sealed, {"analysis_rule", "baseline_methods", "comparison_ids", "failed_cells_normalized", "frozen_comparison_sha256", "matched_100x_against", "scaling_advantage_against", "schema_version"}, "sealed result")
            if type(sealed["schema_version"]) is not int or sealed["schema_version"] != 1 or sealed["analysis_rule"] != "predeclared_100x_or_scaling" or sealed["failed_cells_normalized"] is not True or not all(isinstance(sealed[key], list) and all(isinstance(value, str) for value in sealed[key]) and len(set(sealed[key])) == len(sealed[key]) for key in ("baseline_methods", "comparison_ids", "matched_100x_against", "scaling_advantage_against")):
                raise EvidenceError("sealed result has invalid schema")
            elif not isinstance(sealed["frozen_comparison_sha256"], str) or not HEX_64.fullmatch(sealed["frozen_comparison_sha256"]):
                raise EvidenceError("sealed result has invalid digest")
            elif set(sealed["comparison_ids"]) != set(comparison["expected_ids"]) or set(sealed["baseline_methods"]) != {"hamming-1nn", "zero-fill"} or set(sealed["matched_100x_against"]) & set(sealed["scaling_advantage_against"]) or not (set(sealed["matched_100x_against"]) | set(sealed["scaling_advantage_against"])).issubset({"hamming-1nn", "zero-fill"}):
                reasons.add("sealed_baseline_incomplete")
            elif sealed["frozen_comparison_sha256"] != sha256_bytes(comparison_raw):
                reasons.add("frozen_comparison_digest_mismatch")
            elif trust_policy is None or trust_policy["sealed_results_sha256"] != sha256_bytes(read_stable_regular(sealed_path, "sealed result", DEFAULT_MAX_BYTES)):
                reasons.add("external_trust_policy_mismatch")
            elif not {"hamming-1nn", "zero-fill"}.issubset(set(sealed["baseline_methods"])) or not {"hamming-1nn", "zero-fill"}.issubset(set(sealed["matched_100x_against"]) | set(sealed["scaling_advantage_against"])):
                reasons.add("sealed_baseline_incomplete")
            else:
                sealed_ok = True
    if track == "disclosed_control":
        bindings = {left.dataset_id: record for left, record in ((lefts.get(record.comparison_id), record) for record in records) if left is not None}
        if set(bindings) != set(DISCLOSED_PREDICTION_COMMITMENTS) or len(pairs) != 4:
            reasons.add("control_instance_set_mismatch")
        elif any(bindings[key].dataset_sha256 != digest for key, digest in DISCLOSED_PREDICTION_COMMITMENTS.items()):
            reasons.add("prediction_commitment_mismatch")
    rejection = sorted(reason for reason in reasons if reason in REJECTION_CODES)
    blocking = sorted(reason for reason in reasons if reason in {"candidate_evidence_absent", "deterministic_pairs_absent", "official_verifications_absent", "frozen_comparison_absent", "sealed_results_absent", "missing_comparison_cell", "terminal_failure_present", "sealed_baseline_incomplete", "external_trust_policy_absent"})
    if rejection:
        decision = "reject"
    elif blocking:
        decision = "blocked"
    elif track == "disclosed_control":
        decision = "promote_control"
    else:
        assert comparison is not None
        by_id = {row.comparison_id: row for row in candidates}
        frozen = by_id.get(comparison["frozen_candidate_id"])
        baselines = [by_id.get(identifier) for identifier in comparison["baseline_ids"]]
        if frozen is None or any(row is None for row in baselines):
            decision = "blocked"
            reasons.add("missing_comparison_cell")
        elif quality_key(frozen) <= max(quality_key(row) for row in baselines if row is not None):
            decision = "no_change"
            reasons.add("strict_improvement_not_met")
        elif track == "synthetic":
            decision = "advance_public_candidate"
        elif track == "blind_visible":
            decision = "freeze_candidate"
        elif sealed_ok:
            decision = "promote_blind_result"
        else:
            decision = "no_change"
            reasons.add("strict_improvement_not_met")
    return {
        "decision": decision, "highest_legal_next_step": TRACK_CEILINGS[track],
        "input_sha256": dict(sorted(digests.items())), "reasons": sorted(reasons),
        "schema_version": 1, "track": track,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--trust-policy", type=Path)
    args = parser.parse_args(argv)
    try:
        decision = build_decision(args.request, args.trust_policy)
        atomic_create(args.output, canonical_json_bytes(decision))
    except (EvidenceError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"promotion input error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
