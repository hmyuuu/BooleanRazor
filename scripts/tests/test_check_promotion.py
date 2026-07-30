from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts" / "check-promotion.py"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))


def framed_log_hash(stdout: bytes, stderr: bytes) -> str:
    return sha256(len(stdout).to_bytes(8, "big") + stdout + len(stderr).to_bytes(8, "big") + stderr)


class PromotionFixture:
    ids = (
        "baseline-1nn-r0", "baseline-1nn-r1", "baseline-zero-r0",
        "baseline-zero-r1", "candidate-r0", "candidate-r1",
    )

    def __init__(self, root: Path) -> None:
        self.root = root
        self._write_evidence()

    @property
    def request_path(self) -> Path:
        return self.root / "request.json"

    def manifest(self, identifier: str) -> Path:
        return self.root / "cells" / identifier / "manifest.json"

    def write_valid_request(self, track: str) -> Path:
        if track in {"blind_visible", "sealed_confirmation"}:
            design_path = self.root / "visible-design.json"
            design = read_json(design_path)
            design["dataset_boundary"] = (ROOT / "reblind/COMMITMENT.txt").read_text().strip()
            write_json(design_path, design)
            frozen_path = self.root / "frozen-comparison.json"
            frozen = read_json(frozen_path)
            frozen["design_sha256"] = sha256(design_path.read_bytes())
            write_json(frozen_path, frozen)
            sealed_path = self.root / "sealed.json"
            sealed = read_json(sealed_path)
            sealed["frozen_comparison_sha256"] = sha256(frozen_path.read_bytes())
            write_json(sealed_path, sealed)
        request = {
            "candidate_evidence": [f"cells/{identifier}/manifest.json" for identifier in self.ids],
            "deterministic_pairs": [
                {"left": "cells/baseline-1nn-r0/manifest.json", "right": "cells/baseline-1nn-r1/manifest.json"},
                {"left": "cells/baseline-zero-r0/manifest.json", "right": "cells/baseline-zero-r1/manifest.json"},
                {"left": "cells/candidate-r0/manifest.json", "right": "cells/candidate-r1/manifest.json"},
            ],
            "frozen_comparison": "frozen-comparison.json",
            "official_verifications": [
                "cells/baseline-1nn-r0/official-verification.json",
                "cells/baseline-zero-r0/official-verification.json",
                "cells/candidate-r0/official-verification.json",
            ],
            "schema_version": 1,
            "sealed_results": "sealed.json" if track == "sealed_confirmation" else "none",
            "track": track,
        }
        write_json(self.request_path, request)
        return self.request_path

    def write_trust_policy(self, *, sealed: bool = False) -> Path:
        frozen = self.root / "frozen-comparison.json"
        policy = {
            "frozen_comparison_sha256": sha256(frozen.read_bytes()),
            "official_verifications": [
                {"comparison_id": read_json(self.root / item)["comparison_id"], "sha256": sha256((self.root / item).read_bytes())}
                for item in read_json(self.request_path)["official_verifications"] if isinstance(read_json(self.request_path)["official_verifications"], list)
            ],
            "schema_version": 1,
            "request_sha256": sha256(self.request_path.read_bytes()),
            "sealed_results_sha256": sha256((self.root / "sealed.json").read_bytes()) if sealed else "none",
        }
        path = self.root / "trust-policy.json"
        write_json(path, policy)
        return path

    def run_checker(self, request: Path, *, policy: Path | None | bool = True) -> tuple[subprocess.CompletedProcess[str], Path]:
        output = self.root / "decision.json"
        command = [sys.executable, str(CHECKER), "--request", str(request), "--output", str(output)]
        if policy is True:
            command.extend(["--trust-policy", str(self.write_trust_policy(sealed=read_json(request)["track"] == "sealed_confirmation"))])
        elif isinstance(policy, Path):
            command.extend(["--trust-policy", str(policy)])
        result = subprocess.run(
            command,
            text=True, capture_output=True, cwd=ROOT,
        )
        return result, output

    def reset_output(self) -> None:
        (self.root / "decision.json").unlink(missing_ok=True)

    def update_manifest(self, identifier: str, **updates: object) -> None:
        path = self.manifest(identifier)
        manifest = read_json(path)
        manifest.update(updates)
        write_json(path, manifest)
        record_path = path.with_name("official-verification.json")
        if record_path.exists():
            record = read_json(record_path)
            record["manifest_sha256"] = sha256(path.read_bytes())
            record["gates"] = int(manifest["gates"])
            write_json(record_path, record)

    def terminal_failure(self, identifier: str) -> None:
        self.update_manifest(
            identifier, status="NONZERO_EXIT", exit_code="17", verifier="not_run",
            train_exact="none", visible_cv_exact="none", visible_cv_bit_accuracy="none",
            gates="none", completed_table_sha256="none", circuit_sha256="none",
            artifact_sha256="none", artifact_path="none",
        )

    def _write_evidence(self) -> None:
        provenance = {
            "compiler_digest": "none", "image_sha256": "none", "runner_commit": "b" * 40,
            "source_commit": "b" * 40, "tree_digest": "c" * 64,
        }
        params: dict[str, dict[str, str]] = {}
        cells: list[dict[str, object]] = []
        for identifier in self.ids:
            role = "candidate" if identifier.startswith("candidate") else "baseline"
            method = "candidate" if role == "candidate" else ("hamming-1nn" if "1nn" in identifier else "zero-fill")
            params[identifier] = {
                "algorithm_seed": "a" * 64, "blind": "true", "comparison_id": identifier,
                "dataset_id": "opaque-synthetic", "evaluation_scope": "visible_cv_only",
                "hardware": "local", "method": method, "method_version": "1",
                "observation_fraction": "0.5", "repeat": "0", "role": role, "tier": "fixture",
                "timeout_seconds": "300",
            }
            cells.append({"cell_id": identifier, "params": params[identifier]})
        run_spec = {"cells": cells, "provenance": provenance, "schema_version": 1}
        write_json(self.root / "run_spec.json", run_spec)
        spec_digest = sha256((self.root / "run_spec.json").read_bytes())
        qualities = {
            "baseline-1nn-r0": ("0.8", "0.9", "12"), "baseline-1nn-r1": ("0.8", "0.9", "12"),
            "baseline-zero-r0": ("0.7", "1.0", "8"), "baseline-zero-r1": ("0.7", "1.0", "8"),
            "candidate-r0": ("0.9", "0.8", "10"), "candidate-r1": ("0.9", "0.8", "10"),
        }
        for identifier in self.ids:
            cell = self.root / "cells" / identifier
            cell.mkdir(parents=True)
            table = b"input,output\n0,0\n1,1\n"
            circuit = b"INPUTS a\nOUTPUTS a\n"
            stdout, stderr = b"fixture\n", b""
            (cell / "completed-table.csv").write_bytes(table)
            (cell / "circuit.txt").write_bytes(circuit)
            (cell / "stdout.log").write_bytes(stdout)
            (cell / "stderr.log").write_bytes(stderr)
            artifact = {
                "circuit_path": "circuit.txt", "circuit_sha256": sha256(circuit),
                "completed_table_path": "completed-table.csv", "completed_table_sha256": sha256(table),
                "equivalence": "pass", "schema_version": 1,
            }
            artifact_path = cell / "artifact.json"
            write_json(artifact_path, artifact)
            exact, bit, gates = qualities[identifier]
            manifest = {
                **params[identifier], **provenance, "argv": ["fixture"],
                "artifact_path": f"cells/{identifier}/artifact.json", "artifact_sha256": sha256(artifact_path.read_bytes()),
                "circuit_sha256": sha256(circuit), "cleanup_seconds": "0.0", "completed_table_sha256": sha256(table),
                "elapsed_seconds": "1.0", "ended_utc": "2026-07-30T00:00:01Z", "exit_code": "67",
                "gates": gates, "log_sha256": framed_log_hash(stdout, stderr), "peak_memory_kib": "1",
                "producer": "runner", "run_spec_sha256": spec_digest, "scheduler_classification": "none",
                "scheduler_elapsed_seconds": "none", "scheduler_exit_code": "none", "scheduler_job_id": "none",
                "scheduler_sha256": "none", "scheduler_state": "none", "scheduler_task_index": "none",
                "schema_version": 1, "started_utc": "2026-07-30T00:00:00Z", "status": "VERIFIER_NOT_RUN",
                "stderr_sha256": sha256(stderr), "stdout_sha256": sha256(stdout), "timed_out": "false",
                "train_exact": "1.0", "verifier": "not_run", "visible_cv_bit_accuracy": bit,
                "visible_cv_exact": exact,
            }
            manifest_path = cell / "manifest.json"
            write_json(manifest_path, manifest)
            if identifier.endswith("r0"):
                record = {
                    "bit_accuracy": "1.0", "circuit_sha256": sha256(circuit), "comparison_id": identifier,
                    "dataset_sha256": sha256(b"official input " + identifier.encode()), "exact_accuracy": "1.0",
                    "gates": int(gates), "julia_version": {"sha256": sha256(b"julia version 1.12.4\n"), "text": "julia version 1.12.4"},
                    "manifest_sha256": sha256(manifest_path.read_bytes()), "run_spec_sha256": spec_digest,
                    "samples": 2, "schema_version": 1, "status": "pass", "verify_jl_sha256": "e" * 64,
                }
                write_json(cell / "official-verification.json", record)
        design = {
            "cells": [{"comparison_id": identifier, "dataset_id": "opaque-synthetic"} for identifier in self.ids],
            "dataset_boundary": "synthetic-fixture", "schema_version": 1,
        }
        design_path = self.root / "visible-design.json"
        write_json(design_path, design)
        frozen = {
            "baseline_ids": ["baseline-1nn-r0", "baseline-zero-r0"], "candidate_ids": ["candidate-r0"],
            "design_path": "visible-design.json", "design_sha256": sha256(design_path.read_bytes()),
            "expected_ids": list(self.ids), "frozen_candidate_id": "candidate-r0",
            "rule": "accuracy_first_then_gates", "schema_version": 1,
        }
        frozen_path = self.root / "frozen-comparison.json"
        write_json(frozen_path, frozen)
        sealed = {
            "analysis_rule": "predeclared_100x_or_scaling", "baseline_methods": ["hamming-1nn", "zero-fill"],
            "comparison_ids": list(self.ids), "failed_cells_normalized": True,
            "frozen_comparison_sha256": sha256(frozen_path.read_bytes()),
            "matched_100x_against": ["hamming-1nn", "zero-fill"], "scaling_advantage_against": [],
            "schema_version": 1,
        }
        write_json(self.root / "sealed.json", sealed)


class DisclosedControlFixture:
    def __init__(self, parent: Path) -> None:
        self.root = parent / "controls"
        self.root.mkdir()
        seed = PromotionFixture(self.root)
        old = list(seed.ids)
        self.ids = tuple(f"mystery-{letter}-r{repeat}" for letter in "ABCD" for repeat in range(2))
        for source, target in zip(old, self.ids[:6]):
            (self.root / "cells" / source).rename(self.root / "cells" / target)
        shutil.copytree(self.root / "cells" / "mystery-A-r0", self.root / "cells" / "mystery-D-r0")
        shutil.copytree(self.root / "cells" / "mystery-A-r1", self.root / "cells" / "mystery-D-r1")
        provenance = read_json(self.root / "run_spec.json")["provenance"]
        cells = []
        for identifier in self.ids:
            letter = identifier.split("-")[1]
            candidate = letter == "D"
            params = {"algorithm_seed": "a" * 64, "blind": "true", "comparison_id": identifier, "dataset_id": f"mystery-{letter}", "evaluation_scope": "visible_cv_only", "hardware": "local", "method": "control-candidate" if candidate else "control-baseline", "method_version": "1", "observation_fraction": "0.5", "repeat": "0", "role": "candidate" if candidate else "baseline", "tier": "fixture", "timeout_seconds": "300"}
            cells.append({"cell_id": identifier, "params": params})
        spec = {"cells": cells, "provenance": provenance, "schema_version": 1}
        write_json(self.root / "run_spec.json", spec)
        spec_digest = sha256((self.root / "run_spec.json").read_bytes())
        params_by_id = {cell["cell_id"]: cell["params"] for cell in cells}
        commitments = {"A": "51e3f026def41778ecd0d7dcaee9f970b9937488e6716891932b73824c16d4c7", "B": "e2c9d0e23ee36bfc0f12d7f39fdfe2ca5a8abe8eb194fec56500733694b75c28", "C": "c7b37413844bf0b10ebad0010046469f500354a22cc2ba95cbe42709f8e8337d", "D": "b445a717483303fa3c5d8a1f7abe81888b267b7c472121c9c464fa9766808580"}
        for identifier in self.ids:
            cell = self.root / "cells" / identifier
            (cell / "official-verification.json").unlink(missing_ok=True)
            manifest_path = cell / "manifest.json"
            manifest = read_json(manifest_path)
            manifest.update(params_by_id[identifier])
            manifest["artifact_path"] = f"cells/{identifier}/artifact.json"
            manifest["run_spec_sha256"] = spec_digest
            write_json(manifest_path, manifest)
            if identifier.endswith("r0"):
                letter = identifier.split("-")[1]
                record = {"bit_accuracy": "1.0", "circuit_sha256": manifest["circuit_sha256"], "comparison_id": identifier, "dataset_sha256": commitments[letter], "exact_accuracy": "1.0", "gates": int(manifest["gates"]), "julia_version": {"sha256": sha256(b"julia version 1.12.4\n"), "text": "julia version 1.12.4"}, "manifest_sha256": sha256(manifest_path.read_bytes()), "run_spec_sha256": spec_digest, "samples": 2, "schema_version": 1, "status": "pass", "verify_jl_sha256": "e" * 64}
                write_json(cell / "official-verification.json", record)
        design = {"cells": [{"comparison_id": identifier, "dataset_id": f"mystery-{identifier.split('-')[1]}"} for identifier in self.ids], "dataset_boundary": "synthetic-fixture", "schema_version": 1}
        write_json(self.root / "visible-design.json", design)
        frozen = {"baseline_ids": ["mystery-A-r0", "mystery-B-r0", "mystery-C-r0"], "candidate_ids": ["mystery-D-r0"], "design_path": "visible-design.json", "design_sha256": sha256((self.root / "visible-design.json").read_bytes()), "expected_ids": list(self.ids), "frozen_candidate_id": "mystery-D-r0", "rule": "accuracy_first_then_gates", "schema_version": 1}
        write_json(self.root / "frozen-comparison.json", frozen)
        self.request = self.root / "request.json"
        request = {"candidate_evidence": [f"cells/{identifier}/manifest.json" for identifier in self.ids], "deterministic_pairs": [{"left": f"cells/mystery-{letter}-r0/manifest.json", "right": f"cells/mystery-{letter}-r1/manifest.json"} for letter in "ABCD"], "frozen_comparison": "frozen-comparison.json", "official_verifications": [f"cells/mystery-{letter}-r0/official-verification.json" for letter in "ABCD"], "schema_version": 1, "sealed_results": "none", "track": "disclosed_control"}
        write_json(self.request, request)
        self.policy = self.root / "policy.json"
        policy = {"frozen_comparison_sha256": sha256((self.root / "frozen-comparison.json").read_bytes()), "official_verifications": [{"comparison_id": f"mystery-{letter}-r0", "sha256": sha256((self.root / f"cells/mystery-{letter}-r0/official-verification.json").read_bytes())} for letter in "ABCD"], "request_sha256": sha256(self.request.read_bytes()), "schema_version": 1, "sealed_results_sha256": "none"}
        write_json(self.policy, policy)

    def run(self) -> tuple[subprocess.CompletedProcess[str], Path]:
        output = self.root / "decision.json"
        return subprocess.run([sys.executable, str(CHECKER), "--request", str(self.request), "--output", str(output), "--trust-policy", str(self.policy)], text=True, capture_output=True, cwd=ROOT), output

    def mutate(self, kind: str) -> None:
        record = self.root / "cells/mystery-A-r0/official-verification.json"
        value = read_json(record)
        if kind == "missing_instance":
            value["comparison_id"] = "missing-r0"
        else:
            value["dataset_sha256"] = "0" * 64
        write_json(record, value)


def disclosed_control_fixture(tmp_path: Path) -> DisclosedControlFixture:
    return DisclosedControlFixture(tmp_path)


@pytest.fixture
def promotion_fixture(tmp_path: Path) -> PromotionFixture:
    return PromotionFixture(tmp_path)


@pytest.mark.parametrize(
    ("track", "expected"),
    (("synthetic", "advance_public_candidate"), ("blind_visible", "freeze_candidate"),
     ("sealed_confirmation", "promote_blind_result")),
)
def test_valid_evidence_emits_track_bounded_promotion(promotion_fixture: PromotionFixture, track: str, expected: str) -> None:
    result, output = promotion_fixture.run_checker(promotion_fixture.write_valid_request(track))
    assert result.returncode == 0, result.stderr
    assert read_json(output)["decision"] == expected


@pytest.mark.parametrize(
    ("track", "forbidden"),
    (("synthetic", "freeze_candidate"), ("synthetic", "promote_blind_result"),
     ("blind_visible", "promote_blind_result")),
)
def test_track_ceiling_never_emits_forbidden_decision(promotion_fixture: PromotionFixture, track: str, forbidden: str) -> None:
    result, output = promotion_fixture.run_checker(promotion_fixture.write_valid_request(track))
    assert result.returncode == 0, result.stderr
    decision = read_json(output)
    assert decision["decision"] != forbidden
    assert decision["highest_legal_next_step"] == {"synthetic": "advance_public_candidate", "blind_visible": "freeze_candidate"}[track]


def test_literal_none_is_canonically_blocked(promotion_fixture: PromotionFixture) -> None:
    request = {"candidate_evidence": "none", "deterministic_pairs": "none", "frozen_comparison": "none", "official_verifications": "none", "schema_version": 1, "sealed_results": "none", "track": "blind_visible"}
    write_json(promotion_fixture.request_path, request)
    result, output = promotion_fixture.run_checker(promotion_fixture.request_path)
    assert result.returncode == 0, result.stderr
    assert read_json(output)["reasons"] == ["candidate_evidence_absent", "deterministic_pairs_absent", "frozen_comparison_absent", "official_verifications_absent"]


def test_positive_track_requires_separate_external_trust_policy(promotion_fixture: PromotionFixture) -> None:
    result, output = promotion_fixture.run_checker(promotion_fixture.write_valid_request("synthetic"), policy=None)
    assert result.returncode == 0, result.stderr
    assert read_json(output)["decision"] == "blocked"
    assert "external_trust_policy_absent" in read_json(output)["reasons"]


def test_policy_cannot_be_replayed_for_a_different_request_track(promotion_fixture: PromotionFixture) -> None:
    request = promotion_fixture.write_valid_request("blind_visible")
    policy = promotion_fixture.write_trust_policy()
    value = read_json(request)
    value["track"] = "synthetic"
    write_json(request, value)
    result, output = promotion_fixture.run_checker(request, policy=policy)
    assert result.returncode == 0, result.stderr
    assert read_json(output)["decision"] == "reject"
    assert "external_trust_policy_mismatch" in read_json(output)["reasons"]


def test_nonsealed_track_rejects_sealed_path_without_reading_it(promotion_fixture: PromotionFixture) -> None:
    request = promotion_fixture.write_valid_request("blind_visible")
    value = read_json(request)
    value["sealed_results"] = "does-not-exist.json"
    write_json(request, value)
    result, output = promotion_fixture.run_checker(request)
    assert result.returncode == 2
    assert not output.exists()


def test_nonsealed_track_rejects_private_sealed_digest_in_policy(promotion_fixture: PromotionFixture) -> None:
    request = promotion_fixture.write_valid_request("synthetic")
    policy = promotion_fixture.write_trust_policy()
    value = read_json(policy)
    value["sealed_results_sha256"] = "a" * 64
    write_json(policy, value)
    result, output = promotion_fixture.run_checker(request, policy=policy)
    assert result.returncode == 2
    assert not output.exists()


def test_same_metadata_other_run_root_is_not_a_complete_native_run(promotion_fixture: PromotionFixture) -> None:
    request = promotion_fixture.write_valid_request("synthetic")
    other = promotion_fixture.root / "other"
    shutil.copytree(promotion_fixture.root, other, ignore=shutil.ignore_patterns("other", "request.json", "decision.json", "trust-policy.json"))
    value = read_json(request)
    value["candidate_evidence"][-1] = "other/cells/candidate-r1/manifest.json"
    value["deterministic_pairs"][-1]["right"] = "other/cells/candidate-r1/manifest.json"
    write_json(request, value)
    result, output = promotion_fixture.run_checker(request)
    assert result.returncode == 0, result.stderr
    assert read_json(output)["decision"] == "reject"
    assert "native_run_incomplete" in read_json(output)["reasons"]


def test_policy_must_bind_exact_official_record_bytes(promotion_fixture: PromotionFixture) -> None:
    request = promotion_fixture.write_valid_request("synthetic")
    policy = promotion_fixture.write_trust_policy()
    value = read_json(policy)
    value["official_verifications"][0]["sha256"] = "0" * 64
    write_json(policy, value)
    result, output = promotion_fixture.run_checker(request, policy=policy)
    assert result.returncode == 0, result.stderr
    assert read_json(output)["decision"] == "reject"
    assert "external_trust_policy_mismatch" in read_json(output)["reasons"]


def test_input_digests_match_the_exact_canonical_bytes_parsed(promotion_fixture: PromotionFixture) -> None:
    request = promotion_fixture.write_valid_request("sealed_confirmation")
    policy = promotion_fixture.write_trust_policy(sealed=True)
    result, output = promotion_fixture.run_checker(request, policy=policy)
    assert result.returncode == 0, result.stderr
    inputs = read_json(output)["input_sha256"]
    for relative in read_json(request)["candidate_evidence"] + read_json(request)["official_verifications"] + ["frozen-comparison.json", "visible-design.json", "sealed.json"]:
        assert inputs[relative] == sha256((promotion_fixture.root / relative).read_bytes())
    assert inputs["external_trust_policy"] == sha256(policy.read_bytes())


@pytest.mark.parametrize("field, value", (("exact_accuracy", "0.9"), ("bit_accuracy", "0.9"), ("samples", True), ("julia_version", {"sha256": "D" * 64, "text": ""}), ("julia_version", {"sha256": "0" * 64, "text": "julia version 1.12.4"})))
def test_official_pass_record_requires_exact_pass_metrics_and_valid_julia_value(promotion_fixture: PromotionFixture, field: str, value: object) -> None:
    request = promotion_fixture.write_valid_request("synthetic")
    path = promotion_fixture.root / "cells/candidate-r0/official-verification.json"
    record = read_json(path)
    record[field] = value
    write_json(path, record)
    result, output = promotion_fixture.run_checker(request)
    assert result.returncode == 2
    assert not output.exists()


def test_disclosed_controls_promote_only_with_all_four_committed_instances(tmp_path: Path) -> None:
    fixture = disclosed_control_fixture(tmp_path)
    result, output = fixture.run()
    assert result.returncode == 0, result.stderr
    assert read_json(output)["decision"] == "promote_control"
    assert read_json(output)["highest_legal_next_step"] == "promote_control"


@pytest.mark.parametrize("mutation, reason", (("missing_instance", "control_instance_set_mismatch"), ("wrong_commitment", "prediction_commitment_mismatch")))
def test_disclosed_controls_reject_incomplete_or_wrong_public_commitment(tmp_path: Path, mutation: str, reason: str) -> None:
    fixture = disclosed_control_fixture(tmp_path)
    fixture.mutate(mutation)
    result, output = fixture.run()
    assert result.returncode == 0, result.stderr
    assert read_json(output)["decision"] == "reject"
    assert reason in read_json(output)["reasons"]


@pytest.mark.parametrize("mutation", ("bad_frozen_candidate", "design_projection", "sealed_schema", "sealed_content", "policy_extra", "policy_symlink", "duplicate_id", "role_swap"))
def test_final_adversarial_schema_projection_role_and_policy_cases_never_promote(promotion_fixture: PromotionFixture, mutation: str) -> None:
    track = "sealed_confirmation" if mutation.startswith("sealed") else "synthetic"
    request = promotion_fixture.write_valid_request(track)
    policy: Path | None | bool = True
    if mutation == "bad_frozen_candidate":
        frozen = promotion_fixture.root / "frozen-comparison.json"
        value = read_json(frozen); value["frozen_candidate_id"] = "not-a-candidate"; write_json(frozen, value)
    elif mutation == "design_projection":
        design = promotion_fixture.root / "visible-design.json"
        value = read_json(design); value["cells"][0]["dataset_id"] = "wrong"; write_json(design, value)
        frozen = promotion_fixture.root / "frozen-comparison.json"
        value = read_json(frozen); value["design_sha256"] = sha256(design.read_bytes()); write_json(frozen, value)
    elif mutation == "sealed_schema":
        sealed = promotion_fixture.root / "sealed.json"
        value = read_json(sealed); value["schema_version"] = True; write_json(sealed, value)
    elif mutation == "sealed_content":
        sealed = promotion_fixture.root / "sealed.json"
        value = read_json(sealed); value["matched_100x_against"] = ["hamming-1nn"]; write_json(sealed, value)
    elif mutation == "policy_extra":
        policy = promotion_fixture.write_trust_policy()
        value = read_json(policy); value["extra"] = "x"; write_json(policy, value)
    elif mutation == "policy_symlink":
        policy = promotion_fixture.write_trust_policy()
        link = promotion_fixture.root / "policy-link.json"; link.symlink_to(policy); policy = link
    elif mutation == "duplicate_id":
        other = promotion_fixture.root / "other"
        shutil.copytree(promotion_fixture.root, other, ignore=shutil.ignore_patterns("other", "request.json", "decision.json", "trust-policy.json"))
        value = read_json(request); value["candidate_evidence"][-1] = "other/cells/candidate-r0/manifest.json"; write_json(request, value)
    else:
        spec = promotion_fixture.root / "run_spec.json"
        value = read_json(spec)
        for cell in value["cells"]:
            if cell["cell_id"] in {"baseline-1nn-r0", "baseline-1nn-r1"}:
                cell["params"]["role"] = "candidate"
        write_json(spec, value)
        for identifier in ("baseline-1nn-r0", "baseline-1nn-r1"):
            path = promotion_fixture.manifest(identifier); row = read_json(path); row["role"] = "candidate"; row["run_spec_sha256"] = sha256(spec.read_bytes()); write_json(path, row)
    result, output = promotion_fixture.run_checker(request, policy=policy)
    assert result.returncode in {0, 2}
    assert not output.exists() or read_json(output)["decision"] in {"blocked", "reject", "no_change"}


@pytest.mark.parametrize("mutation, expected", [
    ("missing_verification", "official_verifications_absent"),
    ("foreign_record", "foreign_verification_record"),
    ("nondeterministic", "nondeterministic_pair"),
    ("mixed_commit", "mixed_source_commit"),
    ("missing_cell", "missing_comparison_cell"),
    ("terminal_failure", "filtered_terminal_failure"),
])
def test_evidence_gates_classify_failures(promotion_fixture: PromotionFixture, mutation: str, expected: str) -> None:
    request = promotion_fixture.write_valid_request("synthetic")
    value = read_json(request)
    if mutation == "missing_verification":
        value["official_verifications"] = "none"
        write_json(request, value)
    elif mutation == "foreign_record":
        record = read_json(promotion_fixture.root / "cells/candidate-r0/official-verification.json")
        record["circuit_sha256"] = "0" * 64
        write_json(promotion_fixture.root / "cells/candidate-r0/official-verification.json", record)
    elif mutation == "nondeterministic":
        promotion_fixture.update_manifest("candidate-r1", gates="11")
    elif mutation == "mixed_commit":
        other = promotion_fixture.root / "other"
        shutil.copytree(promotion_fixture.root, other, ignore=shutil.ignore_patterns("other", "request.json", "decision.json"))
        spec_path = other / "run_spec.json"
        spec = read_json(spec_path)
        spec["provenance"]["source_commit"] = "a" * 40
        write_json(spec_path, spec)
        manifest_path = other / "cells/candidate-r1/manifest.json"
        manifest = read_json(manifest_path)
        manifest["source_commit"] = "a" * 40
        manifest["run_spec_sha256"] = sha256(spec_path.read_bytes())
        write_json(manifest_path, manifest)
        value["candidate_evidence"] = ["other/cells/candidate-r1/manifest.json" if "candidate-r1" in path else path for path in value["candidate_evidence"]]
        value["deterministic_pairs"][-1]["right"] = "other/cells/candidate-r1/manifest.json"
        write_json(request, value)
    elif mutation == "missing_cell":
        value["candidate_evidence"] = [path for path in value["candidate_evidence"] if "candidate-r" not in path]
        value["deterministic_pairs"] = value["deterministic_pairs"][:-1]
        value["official_verifications"] = value["official_verifications"][:-1]
        write_json(request, value)
    else:
        promotion_fixture.terminal_failure("candidate-r1")
    result, output = promotion_fixture.run_checker(request)
    assert result.returncode == 0, result.stderr
    assert read_json(output)["decision"] == ("blocked" if expected == "official_verifications_absent" else "reject")
    assert expected in read_json(output)["reasons"]


def test_exact_row_accuracy_precedes_bit_diagnostic_and_gates(promotion_fixture: PromotionFixture) -> None:
    request = promotion_fixture.write_valid_request("synthetic")
    promotion_fixture.update_manifest("candidate-r0", visible_cv_exact="0.8", visible_cv_bit_accuracy="1.0", gates="12")
    promotion_fixture.update_manifest("candidate-r1", visible_cv_exact="0.8", visible_cv_bit_accuracy="1.0", gates="12")
    result, output = promotion_fixture.run_checker(request)
    assert result.returncode == 0, result.stderr
    assert read_json(output)["decision"] == "no_change"


def test_equal_exact_with_fewer_gates_is_strict_improvement(promotion_fixture: PromotionFixture) -> None:
    request = promotion_fixture.write_valid_request("synthetic")
    promotion_fixture.update_manifest("candidate-r0", visible_cv_exact="0.8", visible_cv_bit_accuracy="0.1", gates="11")
    promotion_fixture.update_manifest("candidate-r1", visible_cv_exact="0.8", visible_cv_bit_accuracy="0.1", gates="11")
    result, output = promotion_fixture.run_checker(request)
    assert result.returncode == 0, result.stderr
    assert read_json(output)["decision"] == "advance_public_candidate"


def test_higher_exact_wins_regardless_of_bit_accuracy(promotion_fixture: PromotionFixture) -> None:
    request = promotion_fixture.write_valid_request("synthetic")
    promotion_fixture.update_manifest("candidate-r0", visible_cv_exact="0.81", visible_cv_bit_accuracy="0.0", gates="999")
    promotion_fixture.update_manifest("candidate-r1", visible_cv_exact="0.81", visible_cv_bit_accuracy="0.0", gates="999")
    result, output = promotion_fixture.run_checker(request)
    assert result.returncode == 0, result.stderr
    assert read_json(output)["decision"] == "advance_public_candidate"


@pytest.mark.parametrize("bad_path", ("/tmp/evil.json", "../escape.json", "cells/baseline-1nn-r0/../baseline-1nn-r0/manifest.json"))
def test_unsafe_or_noncanonical_path_is_input_error_without_output(promotion_fixture: PromotionFixture, bad_path: str) -> None:
    request = promotion_fixture.write_valid_request("synthetic")
    value = read_json(request)
    value["candidate_evidence"][0] = bad_path
    write_json(request, value)
    result, output = promotion_fixture.run_checker(request)
    assert result.returncode == 2
    assert not output.exists()


def test_duplicate_path_is_input_error_without_output(promotion_fixture: PromotionFixture) -> None:
    request = promotion_fixture.write_valid_request("synthetic")
    value = read_json(request)
    value["candidate_evidence"].append(value["candidate_evidence"][0])
    write_json(request, value)
    result, output = promotion_fixture.run_checker(request)
    assert result.returncode == 2
    assert not output.exists()


def test_symlinked_output_parent_is_input_error_without_output(promotion_fixture: PromotionFixture) -> None:
    request = promotion_fixture.write_valid_request("synthetic")
    physical_parent = promotion_fixture.root / "physical-output"
    physical_parent.mkdir()
    linked_parent = promotion_fixture.root / "linked-output"
    linked_parent.symlink_to(physical_parent, target_is_directory=True)
    output = linked_parent / "decision.json"
    result = subprocess.run([sys.executable, str(CHECKER), "--request", str(request), "--output", str(output)], text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 2
    assert not (physical_parent / "decision.json").exists()


def test_identical_inputs_and_existing_output_are_deterministic_and_non_overwriting(promotion_fixture: PromotionFixture, tmp_path: Path) -> None:
    request = promotion_fixture.write_valid_request("synthetic")
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    for output in (first, second):
        result = subprocess.run([sys.executable, str(CHECKER), "--request", str(request), "--output", str(output)], text=True, capture_output=True, cwd=ROOT)
        assert result.returncode == 0, result.stderr
    assert first.read_bytes() == second.read_bytes()
    result = subprocess.run([sys.executable, str(CHECKER), "--request", str(request), "--output", str(first)], text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 2
    assert first.read_bytes() == second.read_bytes()


def test_committed_current_request_reproduces_committed_blocked_decision(tmp_path: Path) -> None:
    output = tmp_path / "decision.json"
    result = subprocess.run([sys.executable, str(CHECKER), "--request", str(ROOT / "research/CURRENT_PROMOTION_REQUEST.json"), "--output", str(output)], text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() == (ROOT / "research/CURRENT_PROMOTION_DECISION.json").read_bytes()
    decision = read_json(output)
    assert decision["decision"] == "blocked"
    assert decision["highest_legal_next_step"] == "freeze_candidate"
