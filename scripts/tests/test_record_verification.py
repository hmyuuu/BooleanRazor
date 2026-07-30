from __future__ import annotations

import importlib.util
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


evidence_io = load_module("evidence_io", "evidence_io.py")


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


def test_atomic_create_refuses_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "record.json"
    evidence_io.atomic_create(output, b"first\n")
    with pytest.raises(evidence_io.EvidenceError, match="already exists"):
        evidence_io.atomic_create(output, b"second\n")
    assert output.read_bytes() == b"first\n"


def test_resolve_evidence_path_rejects_absolute_parent_and_symlink_component(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    evidence = root / "evidence.json"
    evidence.write_bytes(b"{}\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "escaped.json").write_bytes(b"{}\n")
    (root / "linked").symlink_to(outside, target_is_directory=True)

    assert evidence_io.resolve_evidence_path(root, "evidence.json", "evidence") == evidence
    for value in (str(evidence), "../outside/escaped.json", "./evidence.json", "linked/escaped.json"):
        with pytest.raises(evidence_io.EvidenceError):
            evidence_io.resolve_evidence_path(root, value, "evidence")


def _swap_parent_for_symlink(
    monkeypatch: pytest.MonkeyPatch, root: Path, name: str, target: Path
) -> None:
    """Swap one checked ancestor immediately before its first open."""
    original_open = evidence_io.os.open
    swapped = False

    def open_with_swap(path: object, *args: object, **kwargs: object) -> int:
        nonlocal swapped
        text = os.fspath(path)
        if not swapped and (text == name or f"/{name}/" in text):
            swapped = True
            (root / name).rename(root / f"{name}.checked")
            (root / name).symlink_to(target, target_is_directory=True)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(evidence_io.os, "open", open_with_swap)


def test_stable_read_rejects_ancestor_swap_at_use_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    inside = root / "inside"
    outside = tmp_path / "outside"
    inside.mkdir(parents=True)
    outside.mkdir()
    (inside / "evidence.txt").write_bytes(b"inside\n")
    (outside / "evidence.txt").write_bytes(b"outside\n")

    _swap_parent_for_symlink(monkeypatch, root, "inside", outside)
    with pytest.raises(evidence_io.EvidenceError):
        evidence_io.read_stable_regular(inside / "evidence.txt", "evidence", 1024)


def test_atomic_create_rejects_ancestor_swap_at_publication_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    inside = root / "inside"
    outside = tmp_path / "outside"
    inside.mkdir(parents=True)
    outside.mkdir()

    _swap_parent_for_symlink(monkeypatch, root, "inside", outside)
    with pytest.raises(evidence_io.EvidenceError):
        evidence_io.atomic_create(inside / "record.json", b"record\n")
    assert not (outside / "record.json").exists()


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def framed_log_hash(stdout: bytes, stderr: bytes) -> str:
    return sha256(
        len(stdout).to_bytes(8, "big") + stdout + len(stderr).to_bytes(8, "big") + stderr
    )


@dataclass
class CandidateRun:
    run_root: Path
    run_spec: Path
    manifest: Path
    artifact: Path
    dataset: bytes
    circuit: bytes
    verify_jl: Path
    julia_bin: Path

    def write_json(self, path: Path, value: object) -> None:
        path.write_bytes(evidence_io.canonical_json_bytes(value))

    def read_json(self, path: Path) -> dict[str, object]:
        return evidence_io.load_canonical_object(path, path.name)[0]

    def apply_mutation(self, mutation: str) -> None:
        manifest = self.read_json(self.manifest)
        if mutation == "manifest_hash":
            manifest["run_spec_sha256"] = "0" * 64
        elif mutation == "run_spec_hash":
            spec = self.read_json(self.run_spec)
            spec["provenance"]["tree_digest"] = "f" * 64
            self.write_json(self.run_spec, spec)
        elif mutation == "artifact_hash":
            manifest["artifact_sha256"] = "0" * 64
        elif mutation == "table_hash":
            artifact = self.read_json(self.artifact)
            artifact["completed_table_sha256"] = "0" * 64
            self.write_json(self.artifact, artifact)
        elif mutation == "circuit_hash":
            artifact = self.read_json(self.artifact)
            artifact["circuit_sha256"] = "0" * 64
            self.write_json(self.artifact, artifact)
        elif mutation == "equivalence":
            artifact = self.read_json(self.artifact)
            artifact["equivalence"] = "fail"
            self.write_json(self.artifact, artifact)
        elif mutation == "train_exact":
            manifest["train_exact"] = "0.9"
        elif mutation == "status_without_evidence":
            manifest["status"] = "NONZERO_EXIT"
            manifest["exit_code"] = "17"
        else:
            raise AssertionError(mutation)
        self.write_json(self.manifest, manifest)

    def replace_with_nonzero_exit(self) -> None:
        manifest = self.read_json(self.manifest)
        manifest.update(
            {
                "status": "NONZERO_EXIT",
                "exit_code": "17",
                "verifier": "not_run",
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
        self.write_json(self.manifest, manifest)


@pytest.fixture
def candidate_run(tmp_path: Path) -> CandidateRun:
    run_root = tmp_path / "run"
    cell = run_root / "cells" / "cell-a"
    cell.mkdir(parents=True)
    dataset = b"input,output\n0,0\n1,1\n"
    circuit = b"INPUTS a\nOUTPUTS a\n"
    stdout = b"learner stdout\n"
    stderr = b""
    (cell / "completed-table.csv").write_bytes(dataset)
    (cell / "circuit.txt").write_bytes(circuit)
    (cell / "stdout.log").write_bytes(stdout)
    (cell / "stderr.log").write_bytes(stderr)
    provenance = {
        "compiler_digest": "none",
        "image_sha256": "none",
        "runner_commit": "b" * 40,
        "source_commit": "b" * 40,
        "tree_digest": "c" * 64,
    }
    params = {
        "algorithm_seed": "a" * 64,
        "blind": "true",
        "comparison_id": "cell-a",
        "dataset_id": "synthetic-fixture",
        "evaluation_scope": "visible_cv_only",
        "hardware": "local",
        "method": "fixture",
        "method_version": "1",
        "observation_fraction": "0.5",
        "repeat": "0",
        "role": "candidate",
        "tier": "fixture",
        "timeout_seconds": "300",
    }
    run_spec = run_root / "run_spec.json"
    spec = {"cells": [{"cell_id": "cell-a", "params": params}], "provenance": provenance, "schema_version": 1}
    run_spec.write_bytes(evidence_io.canonical_json_bytes(spec))
    artifact = cell / "artifact.json"
    artifact.write_bytes(
        evidence_io.canonical_json_bytes(
            {
                "circuit_path": "circuit.txt",
                "circuit_sha256": sha256(circuit),
                "completed_table_path": "completed-table.csv",
                "completed_table_sha256": sha256(dataset),
                "equivalence": "pass",
                "schema_version": 1,
            }
        )
    )
    manifest = cell / "manifest.json"
    manifest.write_bytes(
        evidence_io.canonical_json_bytes(
            {
                **params,
                **provenance,
                "argv": ["fixture"],
                "artifact_path": "cells/cell-a/artifact.json",
                "artifact_sha256": sha256(artifact.read_bytes()),
                "circuit_sha256": sha256(circuit),
                "cleanup_seconds": "0.0",
                "completed_table_sha256": sha256(dataset),
                "elapsed_seconds": "1.0",
                "ended_utc": "2026-07-30T00:00:01Z",
                "exit_code": "67",
                "gates": "1",
                "log_sha256": framed_log_hash(stdout, stderr),
                "peak_memory_kib": "1",
                "producer": "runner",
                "run_spec_sha256": sha256(run_spec.read_bytes()),
                "scheduler_classification": "none",
                "scheduler_elapsed_seconds": "none",
                "scheduler_exit_code": "none",
                "scheduler_job_id": "none",
                "scheduler_sha256": "none",
                "scheduler_state": "none",
                "scheduler_task_index": "none",
                "schema_version": 1,
                "started_utc": "2026-07-30T00:00:00Z",
                "status": "VERIFIER_NOT_RUN",
                "stderr_sha256": sha256(stderr),
                "stdout_sha256": sha256(stdout),
                "timed_out": "false",
                "train_exact": "1.0",
                "verifier": "not_run",
                "visible_cv_bit_accuracy": "1.0",
                "visible_cv_exact": "1.0",
            }
        )
    )
    verify_jl = tmp_path / "verify.jl"
    verify_jl.write_bytes(b"# fixture verifier\n")
    julia_bin = tmp_path / "julia"
    julia_bin.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then\n"
        "  printf 'julia version 1.12.4\\n'\n"
        "else\n"
        "  printf 'gates: 1 (inverters free)\\n'\n"
        "  printf 'samples: 2\\n'\n"
        "  printf 'exact-match acc: 1.0\\n'\n"
        "  printf 'bit accuracy: 1.0\\n'\n"
        "fi\n"
    )
    julia_bin.chmod(0o700)
    return CandidateRun(run_root, run_spec, manifest, artifact, dataset, circuit, verify_jl, julia_bin)


def test_candidate_loader_binds_manifest_run_spec_and_artifacts(
    candidate_run: CandidateRun,
) -> None:
    candidate_evidence = load_module("candidate_evidence", "candidate_evidence.py")
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
    candidate_evidence = load_module("candidate_evidence", "candidate_evidence.py")
    candidate_run.apply_mutation(mutation)
    with pytest.raises(evidence_io.EvidenceError):
        candidate_evidence.load_candidate_manifest(candidate_run.manifest)


def test_terminal_loader_preserves_failure_without_candidate_claim(
    candidate_run: CandidateRun,
) -> None:
    candidate_evidence = load_module("candidate_evidence", "candidate_evidence.py")
    candidate_run.replace_with_nonzero_exit()
    loaded = candidate_evidence.load_terminal_manifest(candidate_run.manifest)
    assert loaded.status == "NONZERO_EXIT"
    assert loaded.verifier == "not_run"
    with pytest.raises(evidence_io.EvidenceError, match="candidate-bearing"):
        candidate_evidence.load_candidate_manifest(candidate_run.manifest)


def test_terminal_loader_rejects_noncanonical_nonzero_exit(candidate_run: CandidateRun) -> None:
    candidate_evidence = load_module("candidate_evidence", "candidate_evidence.py")
    candidate_run.replace_with_nonzero_exit()
    manifest = candidate_run.read_json(candidate_run.manifest)
    manifest["exit_code"] = "017"
    candidate_run.write_json(candidate_run.manifest, manifest)
    with pytest.raises(evidence_io.EvidenceError, match="mapping"):
        candidate_evidence.load_terminal_manifest(candidate_run.manifest)


def test_terminal_loader_rejects_candidate_without_all_quality_evidence(
    candidate_run: CandidateRun,
) -> None:
    candidate_evidence = load_module("candidate_evidence", "candidate_evidence.py")
    manifest = candidate_run.read_json(candidate_run.manifest)
    manifest["artifact_path"] = "none"
    candidate_run.write_json(candidate_run.manifest, manifest)
    with pytest.raises(evidence_io.EvidenceError, match="candidate-bearing"):
        candidate_evidence.load_terminal_manifest(candidate_run.manifest)


@pytest.mark.parametrize(
    ("field", "value", "terminal"),
    (
        ("role", "not-a-role", False),
        ("blind", "false", False),
        ("evaluation_scope", "sealed", False),
        ("method", "", False),
        ("algorithm_seed", "z" * 64, False),
        ("repeat", "01", False),
        ("timeout_seconds", "300.1", False),
        ("source_commit", "c" * 64, False),
        ("image_sha256", "bad", False),
        ("argv", [], False),
        ("started_utc", "2026-07-30", False),
        ("elapsed_seconds", "none", False),
        ("cleanup_seconds", "1.0", False),
        ("visible_cv_exact", "01.0", False),
        ("visible_cv_bit_accuracy", "1.1", False),
        ("gates", "01", False),
        ("peak_memory_kib", "01", False),
        ("status", "OOM", True),
        ("status", "CANCELLED", True),
    ),
)
def test_terminal_loader_rejects_invalid_runner_dialect(
    candidate_run: CandidateRun, field: str, value: object, terminal: bool
) -> None:
    candidate_evidence = load_module("candidate_evidence", "candidate_evidence.py")
    manifest = candidate_run.read_json(candidate_run.manifest)
    spec = candidate_run.read_json(candidate_run.run_spec)
    if field in manifest and field in spec["cells"][0]["params"]:
        spec["cells"][0]["params"][field] = value
    elif field in manifest and field in spec["provenance"]:
        spec["provenance"][field] = value
    manifest[field] = value
    if field == "status":
        manifest.update(
            {
                "exit_code": "137" if value == "OOM" else "130",
                "verifier": "not_run",
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
    candidate_run.write_json(candidate_run.run_spec, spec)
    manifest["run_spec_sha256"] = sha256(candidate_run.run_spec.read_bytes())
    candidate_run.write_json(candidate_run.manifest, manifest)
    with pytest.raises(evidence_io.EvidenceError):
        candidate_evidence.load_terminal_manifest(candidate_run.manifest)


def record_args(candidate_run: CandidateRun, output: Path):
    import argparse

    return argparse.Namespace(
        manifest=candidate_run.manifest,
        julia_bin=candidate_run.julia_bin,
        verify_jl=candidate_run.verify_jl,
        dataset=candidate_run.run_root / "cells" / "cell-a" / "completed-table.csv",
        output=output,
    )


def test_verification_record_binds_official_assertion(candidate_run: CandidateRun, tmp_path: Path) -> None:
    record_verification = load_module("record_verification", "record-verification.py")
    output = tmp_path / "official-verification.json"
    record = record_verification.build_record(record_args(candidate_run, output))
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
    assert output.read_bytes() == evidence_io.canonical_json_bytes(record)


def test_verification_record_refuses_existing_output(candidate_run: CandidateRun, tmp_path: Path) -> None:
    record_verification = load_module("record_verification", "record-verification.py")
    output = tmp_path / "official-verification.json"
    output.write_bytes(b"existing\n")
    with pytest.raises(evidence_io.EvidenceError):
        record_verification.build_record(record_args(candidate_run, output))
    assert output.read_bytes() == b"existing\n"


@pytest.mark.parametrize("input_name", ("manifest", "verify_jl", "dataset"))
def test_verification_record_rejects_noncanonical_relative_or_symlink_inputs(
    candidate_run: CandidateRun, tmp_path: Path, input_name: str
) -> None:
    record_verification = load_module("record_verification", "record-verification.py")
    args = record_args(candidate_run, tmp_path / "record.json")
    if input_name == "manifest":
        args.manifest = Path("relative.json")
    elif input_name == "verify_jl":
        link = tmp_path / "verify-link.jl"
        link.symlink_to(candidate_run.verify_jl)
        args.verify_jl = link
    else:
        link = tmp_path / "dataset-link.csv"
        link.symlink_to(args.dataset)
        args.dataset = link
    with pytest.raises(evidence_io.EvidenceError):
        record_verification.build_record(args)
    assert not args.output.exists()


@pytest.mark.parametrize("replacement", ("manifest", "run_spec", "artifact", "circuit", "dataset", "verify_jl"))
def test_verification_record_rejects_replacement_race(
    candidate_run: CandidateRun, tmp_path: Path, replacement: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    record_verification = load_module("record_verification", "record-verification.py")
    args = record_args(candidate_run, tmp_path / "record.json")
    paths = {
        "manifest": candidate_run.manifest,
        "run_spec": candidate_run.run_spec,
        "artifact": candidate_run.artifact,
        "circuit": candidate_run.run_root / "cells" / "cell-a" / "circuit.txt",
        "dataset": args.dataset,
        "verify_jl": candidate_run.verify_jl,
    }
    calls = 0

    def run(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            paths[replacement].write_bytes(paths[replacement].read_bytes() + b"race\n")
            return subprocess.CompletedProcess(_args[0], 0, b"instance=cell-a gates=1 samples=2 exact=1.0 bit=1.0 verifier=pass\n", b"")
        return subprocess.CompletedProcess(_args[0], 0, b"julia version 1.12.4\n", b"")

    monkeypatch.setattr(record_verification.subprocess, "run", run)
    with pytest.raises(evidence_io.EvidenceError, match="changed"):
        record_verification.build_record(args)
    assert not args.output.exists()


def test_verification_record_rejects_wrapper_failure(candidate_run: CandidateRun, tmp_path: Path) -> None:
    record_verification = load_module("record_verification", "record-verification.py")
    candidate_run.julia_bin.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then\n"
        "  printf 'julia version 1.12.4\\n'\n"
        "else\n"
        "  exit 1\n"
        "fi\n"
    )
    candidate_run.julia_bin.chmod(0o700)
    output = tmp_path / "record.json"
    with pytest.raises(record_verification.VerifierFailure):
        record_verification.build_record(record_args(candidate_run, output))
    assert not output.exists()


def test_verification_record_rejects_wrapper_launch_error(
    candidate_run: CandidateRun, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    record_verification = load_module("record_verification", "record-verification.py")
    calls = 0

    def run(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return subprocess.CompletedProcess(args[0], 0, b"julia version 1.12.4\n", b"")
        raise OSError("wrapper unavailable")

    monkeypatch.setattr(record_verification.subprocess, "run", run)
    output = tmp_path / "record.json"
    with pytest.raises(evidence_io.EvidenceError, match="launch"):
        record_verification.build_record(record_args(candidate_run, output))
    assert not output.exists()
