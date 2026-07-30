#!/usr/bin/env python3
"""Create one immutable external-verifier assertion for a candidate."""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

from candidate_evidence import load_candidate_manifest
from evidence_io import (
    MAX_ARTIFACT_BYTES,
    EvidenceError,
    atomic_create,
    canonical_json_bytes,
    read_stable_regular,
    sha256_bytes,
)


SUMMARY = re.compile(
    rb"instance=([A-Za-z0-9][A-Za-z0-9._-]*) "
    rb"gates=(0|[1-9][0-9]*) samples=(0|[1-9][0-9]*) "
    rb"exact=1\.0 bit=1\.0 verifier=pass\n"
)


class VerifierFailure(EvidenceError):
    """The verifier wrapper ran but did not return an official pass assertion."""

    def __init__(self, returncode: int) -> None:
        super().__init__(f"official verifier wrapper failed with exit status {returncode}")
        self.returncode = returncode


def _require_absolute_normalized(path: Path, label: str) -> None:
    if not path.is_absolute():
        raise EvidenceError(f"{label} must be an absolute path")
    if os.path.normpath(os.fspath(path)) != os.fspath(path):
        raise EvidenceError(f"{label} must be lexically normalized")


def _read_bound(path: Path, label: str) -> bytes:
    return read_stable_regular(path, label, MAX_ARTIFACT_BYTES)


def _validated_julia(path: Path) -> bytes:
    data = _read_bound(path, "julia binary")
    try:
        mode = os.stat(path, follow_symlinks=False).st_mode
    except OSError as exc:
        raise EvidenceError("julia binary cannot be statted") from exc
    if not mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
        raise EvidenceError("julia binary must be executable")
    return data


def _version_output(julia_bin: Path, environment: dict[str, str]) -> bytes:
    try:
        version = subprocess.run(
            [str(julia_bin), "--version"], check=True, capture_output=True, env=environment
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise EvidenceError("Julia --version failed") from exc
    if version.stderr:
        raise EvidenceError("Julia --version must not write stderr")
    if not version.stdout.endswith(b"\n") or version.stdout.count(b"\n") != 1:
        raise EvidenceError("Julia --version must be exactly one LF-terminated line")
    if not version.stdout[:-1] or any(byte < 32 or byte > 126 for byte in version.stdout[:-1]):
        raise EvidenceError("Julia --version must be printable ASCII")
    return version.stdout


def _same(path: Path, label: str, before: bytes) -> None:
    after = _read_bound(path, label)
    if after != before:
        raise EvidenceError(f"{label} changed during verification")


def build_record(args: argparse.Namespace) -> dict[str, object]:
    for name in ("manifest", "julia_bin", "verify_jl", "dataset", "output"):
        value = getattr(args, name)
        if not isinstance(value, Path):
            raise EvidenceError(f"{name} must be a Path")
        _require_absolute_normalized(value, name)

    candidate = load_candidate_manifest(args.manifest)
    manifest_bytes = _read_bound(args.manifest, "manifest.json")
    run_spec_bytes = _read_bound(candidate.run_spec_path, "run_spec.json")
    artifact_bytes = _read_bound(candidate.artifact_path, "artifact.json")
    circuit_bytes = _read_bound(candidate.circuit_path, "circuit.txt")
    dataset_bytes = _read_bound(args.dataset, "official dataset")
    verify_jl_bytes = _read_bound(args.verify_jl, "verify.jl")
    julia_binary_bytes = _validated_julia(args.julia_bin)
    if sha256_bytes(manifest_bytes) != candidate.manifest_sha256:
        raise EvidenceError("manifest changed before verification")
    if sha256_bytes(run_spec_bytes) != candidate.run_spec_sha256:
        raise EvidenceError("run_spec changed before verification")
    if sha256_bytes(artifact_bytes) != candidate.artifact_sha256:
        raise EvidenceError("artifact changed before verification")
    if sha256_bytes(circuit_bytes) != candidate.circuit_sha256:
        raise EvidenceError("circuit changed before verification")

    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    version_bytes = _version_output(args.julia_bin, environment)
    try:
        verified = subprocess.run(
            [
                str(Path(__file__).with_name("verify-julia.sh")), str(args.julia_bin),
                str(args.verify_jl), str(candidate.circuit_path), str(args.dataset),
                str(candidate.gates), candidate.comparison_id,
            ],
            check=False, capture_output=True, env=environment,
        )
    except OSError as exc:
        raise EvidenceError("official verifier wrapper launch failed") from exc
    if verified.returncode:
        raise VerifierFailure(verified.returncode)
    if verified.stderr:
        raise EvidenceError("official verifier wrapper must not write stderr")
    summary = SUMMARY.fullmatch(verified.stdout)
    if summary is None:
        raise EvidenceError("official verifier wrapper summary is invalid")
    instance, gates, samples = summary.groups()
    if instance.decode("ascii") != candidate.comparison_id or int(gates) != candidate.gates:
        raise EvidenceError("official verifier wrapper summary disagrees with candidate")

    _same(args.manifest, "manifest.json", manifest_bytes)
    _same(candidate.run_spec_path, "run_spec.json", run_spec_bytes)
    _same(candidate.artifact_path, "artifact.json", artifact_bytes)
    _same(candidate.circuit_path, "circuit.txt", circuit_bytes)
    _same(args.dataset, "official dataset", dataset_bytes)
    _same(args.verify_jl, "verify.jl", verify_jl_bytes)
    if _validated_julia(args.julia_bin) != julia_binary_bytes:
        raise EvidenceError("julia binary changed during verification")
    if _version_output(args.julia_bin, environment) != version_bytes:
        raise EvidenceError("Julia version evidence changed during verification")

    record: dict[str, object] = {
        "bit_accuracy": "1.0",
        "circuit_sha256": candidate.circuit_sha256,
        "comparison_id": candidate.comparison_id,
        "dataset_sha256": sha256_bytes(dataset_bytes),
        "exact_accuracy": "1.0",
        "gates": candidate.gates,
        "julia_version": {"sha256": sha256_bytes(version_bytes), "text": version_bytes[:-1].decode("ascii")},
        "manifest_sha256": candidate.manifest_sha256,
        "run_spec_sha256": candidate.run_spec_sha256,
        "samples": int(samples),
        "schema_version": 1,
        "status": "pass",
        "verify_jl_sha256": sha256_bytes(verify_jl_bytes),
    }
    atomic_create(args.output, canonical_json_bytes(record))
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--julia-bin", required=True, type=Path)
    parser.add_argument("--verify-jl", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    try:
        build_record(parse_args())
    except VerifierFailure as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.returncode
    except EvidenceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
