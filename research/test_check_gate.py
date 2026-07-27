from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECKER = Path(__file__).with_name("check_gate.py")
SPEC = importlib.util.spec_from_file_location("task9_check_gate", CHECKER)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def matrix_row(comparison_id: str = "cell-a") -> dict[str, str]:
    return {
        "comparison_id": comparison_id,
        "method": "zero-fill",
        "method_version": "1",
        "dataset_id": "opaque-synthetic",
        "tier": "n=1",
        "observation_fraction": "0.10",
        "algorithm_seed": "a" * 64,
        "repeat": "0",
        "timeout_seconds": "300",
        "hardware": "synthetic-card",
    }


def baseline_row(comparison_id: str = "cell-a") -> dict[str, str]:
    row = {
        "comparison_id": comparison_id,
        "role": "baseline",
        "method": "zero-fill",
        "method_version": "1",
        "blind": "true",
        "evaluation_scope": "visible_cv_only",
        "source_commit": "1" * 40,
        "runner_commit": "2" * 40,
        "tree_digest": "3" * 64,
        "image_sha256": "none",
        "compiler_digest": "4" * 64,
        "hardware": "synthetic-card",
        "dataset_id": "opaque-synthetic",
        "tier": "n=1",
        "observation_fraction": "0.10",
        "algorithm_seed": "a" * 64,
        "repeat": "0",
        "timeout_seconds": "300",
        "status": "SUCCESS",
        "exit_code": "0",
        "timed_out": "false",
        "train_exact": "1.0",
        "visible_cv_exact": "0.5",
        "visible_cv_bit_accuracy": "0.75",
        "gates": "7",
        "elapsed_seconds": "1.25",
        "peak_memory_kib": "1024",
        "verifier": "pass",
        "artifact_sha256": "5" * 64,
        "manifest_sha256": "6" * 64,
        "evidence_path": "results/synthetic/evidence.json",
    }
    assert set(row) == set(gate.BASELINES_HEADER.split(","))
    return row


def manifest_payload(row: dict[str, str]) -> dict[str, object]:
    payload: dict[str, object] = {
        key: value
        for key, value in row.items()
        if key not in {"manifest_sha256", "evidence_path"}
    }
    payload["artifact_path"] = "results/synthetic/candidate.netlist"
    payload["scheduler_sha256"] = "7" * 64
    payload["log_sha256"] = "8" * 64
    return payload


def manifest_errors(run: Path, expected_spec: Path) -> list[str]:
    try:
        return gate.check_manifests(run, expected_spec)
    except TypeError:
        # The pre-fix implementation has no expected-spec parameter. Keeping
        # the old call makes the RED result an assertion about behavior.
        return gate.check_manifests(run)


class CheckerReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="task9-check-gate-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.research = self.root / "tracks/qcs/solutions/hmyuuu/research"
        self.results = self.root / "results"
        self.research.mkdir(parents=True)
        self.results.mkdir()
        self.original_research = gate.RESEARCH_ROOT
        self.original_repo = gate.REPO_ROOT
        gate.RESEARCH_ROOT = self.research
        gate.REPO_ROOT = self.root
        self.addCleanup(setattr, gate, "RESEARCH_ROOT", self.original_research)
        self.addCleanup(setattr, gate, "REPO_ROOT", self.original_repo)

    def write_expected_json(
        self, *, cells: list[dict[str, object]] | None = None
    ) -> tuple[Path, Path]:
        expected = self.research / "expected.json"
        run = self.root / "run"
        run.mkdir()
        spec = {"schema_version": 1, "cells": cells or []}
        expected.write_bytes(json_bytes(spec))
        (run / "run_spec.json").write_bytes(json_bytes(spec))
        return expected, run

    def write_cell_manifest(
        self, run: Path, row: dict[str, str], *, nested_secret: bool = False
    ) -> Path:
        cell = run / "cells" / row["comparison_id"]
        cell.mkdir(parents=True)
        payload = manifest_payload(row)
        payload["artifact_path"] = "artifacts/candidate.netlist"
        if nested_secret:
            payload["diagnostics"] = [{"safe": {"secret_seed": "hidden"}}]
        artifact = run / "artifacts/candidate.netlist"
        artifact.parent.mkdir(exist_ok=True)
        artifact.write_bytes(b"xag\n")
        payload["artifact_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
        path = cell / "manifest.json"
        path.write_bytes(json_bytes(payload))
        return path

    def test_cli_requires_expected_spec_for_manifests_phase(self) -> None:
        run = self.root / "run"
        run.mkdir()
        result = subprocess.run(
            [
                sys.executable,
                str(CHECKER),
                "--phase",
                "manifests",
                "--run",
                str(run),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--expected-spec", result.stderr)

    def test_expected_spec_must_resolve_under_research(self) -> None:
        outside = self.root / "outside.json"
        outside.write_bytes(json_bytes({"schema_version": 1, "cells": []}))
        run = self.root / "run"
        run.mkdir()
        errors = manifest_errors(run, outside)
        self.assertTrue(any("under research" in error for error in errors), errors)

    def test_json_expected_spec_requires_byte_identical_run_spec(self) -> None:
        expected, run = self.write_expected_json()
        (run / "run_spec.json").write_bytes(
            b'{\n  "schema_version": 1,\n  "cells": []\n}\n'
        )
        errors = manifest_errors(run, expected)
        self.assertTrue(any("byte-identical" in error for error in errors), errors)

    def test_json_expected_spec_cannot_freeze_an_empty_design(self) -> None:
        expected, run = self.write_expected_json()
        errors = manifest_errors(run, expected)
        self.assertTrue(any("at least one cell" in error for error in errors), errors)

    def test_matrix_expected_spec_binds_native_cell_params_verbatim(self) -> None:
        expected = self.research / "BASELINE_MATRIX.csv"
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(
            stream,
            fieldnames=gate.MATRIX_HEADER.split(","),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow(matrix_row())
        expected.write_text(stream.getvalue(), encoding="utf-8")

        run = self.root / "run"
        run.mkdir()
        wrong = matrix_row()
        wrong["timeout_seconds"] = "299"
        (run / "run_spec.json").write_bytes(
            json_bytes(
                {
                    "schema_version": 1,
                    "cells": [{"cell_id": "cell-a", "params": wrong}],
                }
            )
        )
        errors = manifest_errors(run, expected)
        self.assertTrue(
            any("params" in error and "verbatim" in error for error in errors), errors
        )
        self.assertTrue(any("360 rows" in error for error in errors), errors)

    def test_manifests_require_exactly_one_terminal_json_per_expected_cell(
        self,
    ) -> None:
        params = matrix_row()
        expected, run = self.write_expected_json(
            cells=[{"cell_id": "cell-a", "params": params}]
        )
        extra = run / "cells/extra/manifest.json"
        extra.parent.mkdir(parents=True)
        extra.write_bytes(json_bytes(manifest_payload(baseline_row("extra"))))
        errors = manifest_errors(run, expected)
        self.assertTrue(
            any("missing manifest" in error and "cell-a" in error for error in errors)
        )
        self.assertTrue(any("unexpected manifest" in error for error in errors))

    def test_native_manifest_recursively_rejects_forbidden_keys(self) -> None:
        params = matrix_row()
        expected, run = self.write_expected_json(
            cells=[{"cell_id": "cell-a", "params": params}]
        )
        self.write_cell_manifest(run, baseline_row(), nested_secret=True)
        errors = manifest_errors(run, expected)
        self.assertTrue(any("forbidden key" in error for error in errors), errors)

    def test_run_spec_recursively_rejects_forbidden_keys(self) -> None:
        params = matrix_row()
        params["options"] = {"nested": [{"generator_name": "forbidden"}]}
        expected, run = self.write_expected_json(
            cells=[{"cell_id": "cell-a", "params": params}]
        )
        self.write_cell_manifest(run, baseline_row())
        errors = manifest_errors(run, expected)
        self.assertTrue(
            any(
                "run_spec.json" in error and "forbidden key" in error
                for error in errors
            ),
            errors,
        )

    def test_valid_native_json_manifest_passes(self) -> None:
        params = matrix_row()
        expected, run = self.write_expected_json(
            cells=[{"cell_id": "cell-a", "params": params}]
        )
        self.write_cell_manifest(run, baseline_row())
        self.assertEqual(manifest_errors(run, expected), [])

    def test_baseline_evidence_path_must_be_repository_relative_under_results(
        self,
    ) -> None:
        row = baseline_row()
        row["evidence_path"] = "../outside.json"
        errors: list[str] = []
        checker = getattr(
            gate, "check_baseline_evidence", lambda *_args, **_kwargs: None
        )
        checker(row, errors, label="BASELINES.csv:2")
        self.assertTrue(any("under results" in error for error in errors), errors)

    def test_baseline_evidence_must_exist_and_match_exact_hash(self) -> None:
        row = baseline_row()
        errors: list[str] = []
        checker = getattr(
            gate, "check_baseline_evidence", lambda *_args, **_kwargs: None
        )
        checker(row, errors, label="BASELINES.csv:2")
        self.assertTrue(any("missing evidence" in error for error in errors), errors)

        evidence = self.root / row["evidence_path"]
        evidence.parent.mkdir(parents=True)
        evidence.write_bytes(json_bytes(manifest_payload(row)))
        errors = []
        checker(row, errors, label="BASELINES.csv:2")
        self.assertTrue(any("hash mismatch" in error for error in errors), errors)

    def test_baseline_evidence_recursively_rejects_sealed_and_mismatched_schema(
        self,
    ) -> None:
        row = baseline_row()
        artifact = self.root / "results/synthetic/candidate.netlist"
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(b"xag\n")
        row["artifact_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
        payload = manifest_payload(row)
        payload["status"] = "TIMEOUT"
        payload["diagnostics"] = {"nested": [{"ground_truth": "forbidden"}]}
        evidence = self.root / row["evidence_path"]
        evidence.write_bytes(json_bytes(payload))
        row["manifest_sha256"] = hashlib.sha256(evidence.read_bytes()).hexdigest()

        errors: list[str] = []
        checker = getattr(
            gate, "check_baseline_evidence", lambda *_args, **_kwargs: None
        )
        checker(row, errors, label="BASELINES.csv:2")
        self.assertTrue(any("forbidden key" in error for error in errors), errors)
        self.assertTrue(any("disagrees on status" in error for error in errors), errors)
        self.assertTrue(any("schema" in error for error in errors), errors)

    def test_valid_baseline_evidence_passes(self) -> None:
        row = baseline_row()
        artifact = self.root / "results/synthetic/candidate.netlist"
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(b"xag\n")
        row["artifact_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
        evidence = self.root / row["evidence_path"]
        evidence.write_bytes(json_bytes(manifest_payload(row)))
        row["manifest_sha256"] = hashlib.sha256(evidence.read_bytes()).hexdigest()
        errors: list[str] = []
        gate.check_baseline_evidence(row, errors, label="BASELINES.csv:2")
        self.assertEqual(errors, [])

    def test_status_requires_the_exact_verifier_mapping(self) -> None:
        cases = [
            ("SUCCESS", "not_run", "SUCCESS requires verifier=pass"),
            ("VERIFIER_FAILED", "not_run", "VERIFIER_FAILED requires verifier=fail"),
            ("TIMEOUT", "fail", "TIMEOUT requires verifier=not_run"),
        ]
        for status, verifier, expected in cases:
            with self.subTest(status=status):
                row = baseline_row()
                row.update(
                    status=status,
                    verifier=verifier,
                    timed_out="true" if status == "TIMEOUT" else "false",
                )
                if status != "SUCCESS":
                    for field in (
                        "train_exact",
                        "visible_cv_exact",
                        "visible_cv_bit_accuracy",
                        "gates",
                        "artifact_sha256",
                    ):
                        row[field] = "none"
                errors: list[str] = []
                gate.check_baseline_rows([row], [matrix_row()], errors)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_success_metrics_are_finite_ranged_and_canonical(self) -> None:
        row = baseline_row()
        row.update(
            train_exact="0.999",
            visible_cv_exact="nan",
            visible_cv_bit_accuracy="1.01",
            gates="-1",
            elapsed_seconds="300.01",
            peak_memory_kib="01",
        )
        errors: list[str] = []
        gate.check_baseline_rows([row], [matrix_row()], errors)
        expected_fragments = [
            "train_exact must equal 1.0",
            "visible_cv_exact",
            "visible_cv_bit_accuracy",
            "gates",
            "elapsed_seconds",
            "peak_memory_kib",
        ]
        for fragment in expected_fragments:
            self.assertTrue(
                any(fragment in error for error in errors), (fragment, errors)
            )
        self.assertFalse(math.isfinite(float(row["visible_cv_exact"])))

    def test_failed_elapsed_and_peak_metrics_are_checked_when_present(self) -> None:
        row = baseline_row()
        row.update(
            status="OOM",
            verifier="not_run",
            exit_code="137",
            train_exact="none",
            visible_cv_exact="none",
            visible_cv_bit_accuracy="none",
            gates="none",
            artifact_sha256="none",
            elapsed_seconds="-0.5",
            peak_memory_kib="1.5",
        )
        errors: list[str] = []
        gate.check_baseline_rows([row], [matrix_row()], errors)
        self.assertTrue(any("elapsed_seconds" in error for error in errors), errors)
        self.assertTrue(any("peak_memory_kib" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
