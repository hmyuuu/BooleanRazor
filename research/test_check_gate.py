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
from typing import Callable


CHECKER = Path(__file__).with_name("check_gate.py")
PROTOCOL = Path(__file__).with_name("BENCHMARK_PROTOCOL.md")
RUNNER = CHECKER.parents[1] / "scripts" / "run-experiment.py"
SPEC = importlib.util.spec_from_file_location("task10_check_gate", CHECKER)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
TABLE_BYTES = b"input,output\n0,0\n"
CIRCUIT_BYTES = b"xag\n"
PROVENANCE = {
    "source_commit": "1" * 40,
    "runner_commit": "2" * 40,
    "tree_digest": "3" * 64,
    "image_sha256": "none",
    "compiler_digest": "4" * 64,
}


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


def params_row(
    comparison_id: str = "cell-a",
    *,
    role: str = "candidate",
    method: str = "novel-candidate",
    timeout_seconds: str = "300",
) -> dict[str, str]:
    row = matrix_row(comparison_id)
    row.update(
        {
            "role": role,
            "method": method,
            "blind": "true",
            "evaluation_scope": "visible_cv_only",
            "timeout_seconds": timeout_seconds,
        }
    )
    return {
        field: row[field]
        for field in (
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
        )
    }


def baseline_row(comparison_id: str = "cell-a") -> dict[str, str]:
    params = params_row(
        comparison_id, role="baseline", method="zero-fill"
    )
    row = {
        **params,
        **PROVENANCE,
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
        "evidence_path": "results/synthetic/cells/cell-a/manifest.json",
    }
    assert set(row) == set(gate.BASELINES_HEADER.split(","))
    return row


def execution_spec(cells: list[dict[str, object]]) -> dict[str, object]:
    return {"schema_version": 1, "cells": cells, "provenance": PROVENANCE}


def framed_hash(stdout: bytes, stderr: bytes) -> str:
    value = (
        len(stdout).to_bytes(8, "big")
        + stdout
        + len(stderr).to_bytes(8, "big")
        + stderr
    )
    return hashlib.sha256(value).hexdigest()


class CheckerReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="task10-check-gate-")
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
        self.counter = 0

    def write_expected_json(
        self,
        *,
        cells: list[dict[str, object]] | None = None,
        name: str | None = None,
    ) -> tuple[Path, Path]:
        self.counter += 1
        cells = cells if cells is not None else []
        expected = self.research / (name or f"expected-{self.counter}.json")
        run = self.root / f"run-{self.counter}"
        run.mkdir()
        design = {"schema_version": 1, "cells": cells}
        expected.write_bytes(json_bytes(design))
        (run / "run_spec.json").write_bytes(json_bytes(execution_spec(cells)))
        return expected, run

    def write_logs(
        self,
        run: Path,
        cell_id: str,
        *,
        stdout: bytes = b"out\n",
        stderr: bytes = b"err\n",
    ) -> tuple[bytes, bytes]:
        cell = run / "cells" / cell_id
        cell.mkdir(parents=True, exist_ok=True)
        (cell / "stdout.log").write_bytes(stdout)
        (cell / "stderr.log").write_bytes(stderr)
        return stdout, stderr

    def write_artifacts(self, run: Path, cell_id: str) -> dict[str, str]:
        cell = run / "cells" / cell_id
        cell.mkdir(parents=True, exist_ok=True)
        table_digest = hashlib.sha256(TABLE_BYTES).hexdigest()
        circuit_digest = hashlib.sha256(CIRCUIT_BYTES).hexdigest()
        (cell / "completed-table.csv").write_bytes(TABLE_BYTES)
        (cell / "circuit.txt").write_bytes(CIRCUIT_BYTES)
        artifact = {
            "circuit_path": "circuit.txt",
            "circuit_sha256": circuit_digest,
            "completed_table_path": "completed-table.csv",
            "completed_table_sha256": table_digest,
            "equivalence": "pass",
            "schema_version": 1,
        }
        artifact_raw = json_bytes(artifact)
        (cell / "artifact.json").write_bytes(artifact_raw)
        return {
            "completed_table_sha256": table_digest,
            "circuit_sha256": circuit_digest,
            "artifact_sha256": hashlib.sha256(artifact_raw).hexdigest(),
            "artifact_path": f"cells/{cell_id}/artifact.json",
        }

    def manifest_payload(
        self,
        run: Path,
        params: dict[str, str],
        *,
        status: str = "SUCCESS",
        producer: str = "runner",
    ) -> dict[str, object]:
        cell_id = params["comparison_id"]
        if producer == "runner":
            stdout, stderr = self.write_logs(run, cell_id)
            scheduler = {
                "scheduler_sha256": "none",
                "scheduler_job_id": "none",
                "scheduler_task_index": "none",
                "scheduler_state": "none",
                "scheduler_exit_code": "none",
                "scheduler_classification": "none",
                "scheduler_elapsed_seconds": "none",
            }
            operational: dict[str, object] = {
                "argv": ["synthetic", "argument with spaces"],
                "started_utc": "2026-07-27T01:02:03.000004Z",
                "ended_utc": "2026-07-27T01:02:04.000005Z",
                "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
                "log_sha256": framed_hash(stdout, stderr),
                "cleanup_seconds": (
                    "0.01" if status == "TIMEOUT" else "0.0"
                ),
                **scheduler,
            }
        else:
            task_index = "1"
            job_id = "8123"
            task_log = run / f"slurm-{job_id}_{task_index}.out"
            task_log.write_bytes(b"scheduler log\n")
            digest = hashlib.sha256(task_log.read_bytes()).hexdigest()
            state = {
                "TIMEOUT": "TIMEOUT",
                "OOM": "OUT_OF_MEMORY",
                "NONZERO_EXIT": "FAILED",
                "CANCELLED": "CANCELLED",
                "MISSING_SUCCESS_MANIFEST": "COMPLETED",
            }[status]
            raw_exit = {
                "TIMEOUT": "0:15",
                "OOM": "0:9",
                "NONZERO_EXIT": "17:0",
                "CANCELLED": "0:15",
                "MISSING_SUCCESS_MANIFEST": "0:0",
            }[status]
            operational = {
                "argv": [],
                "started_utc": "none",
                "ended_utc": "none",
                "stdout_sha256": digest,
                "stderr_sha256": "none",
                "log_sha256": digest,
                "cleanup_seconds": "none",
                "scheduler_sha256": "7" * 64,
                "scheduler_job_id": job_id,
                "scheduler_task_index": task_index,
                "scheduler_state": state,
                "scheduler_exit_code": raw_exit,
                "scheduler_classification": status,
                "scheduler_elapsed_seconds": "12",
            }

        exit_code = {
            "SUCCESS": "0",
            "TIMEOUT": "124",
            "OOM": "137",
            "NONZERO_EXIT": "17",
            "INVALID_METRICS": "65",
            "VERIFIER_FAILED": "66",
            "VERIFIER_NOT_RUN": "67",
            "CANCELLED": "130",
            "MISSING_SUCCESS_MANIFEST": "70",
        }[status]
        verifier = (
            "pass"
            if status == "SUCCESS"
            else "fail"
            if status == "VERIFIER_FAILED"
            else "not_run"
        )
        payload: dict[str, object] = {
            **params,
            **PROVENANCE,
            "schema_version": 1,
            "producer": producer,
            "run_spec_sha256": hashlib.sha256(
                (run / "run_spec.json").read_bytes()
            ).hexdigest(),
            "status": status,
            "exit_code": exit_code,
            "timed_out": "true" if status == "TIMEOUT" else "false",
            "elapsed_seconds": (
                params["timeout_seconds"]
                if status == "TIMEOUT"
                else "12.0"
                if producer == "scheduler"
                else "0.01"
                if params["timeout_seconds"] == "0.05"
                else "1.25"
            ),
            "peak_memory_kib": "1024",
            "verifier": verifier,
            **operational,
        }
        if status == "SUCCESS":
            payload.update(
                {
                    "train_exact": "1.0",
                    "visible_cv_exact": "0.5",
                    "visible_cv_bit_accuracy": "0.75",
                    "gates": "7",
                    **self.write_artifacts(run, cell_id),
                }
            )
        else:
            payload.update(
                {
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
        return payload

    def write_manifest(
        self,
        run: Path,
        params: dict[str, str],
        *,
        status: str = "SUCCESS",
        producer: str = "runner",
        mutate: Callable[[dict[str, object]], None] | None = None,
    ) -> Path:
        payload = self.manifest_payload(
            run, params, status=status, producer=producer
        )
        if mutate is not None:
            mutate(payload)
        path = run / "cells" / params["comparison_id"] / "manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(json_bytes(payload))
        return path

    def manifest_errors(self, run: Path, expected: Path) -> list[str]:
        return gate.check_manifests(run, expected)

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

    def test_protocol_documents_the_amended_native_evidence_dialect(self) -> None:
        text = PROTOCOL.read_text(encoding="utf-8")
        required = (
            "provenance-free canonical design spec",
            "`schema_version` and `cells`",
            "`source_commit`, `runner_commit`, `tree_digest`, `image_sha256`, and `compiler_digest`",
            "git ls-tree -rz --full-tree HEAD",
            "`completed-table.csv`, `circuit.txt`, and `artifact.json`",
            "eight-byte unsigned big-endian length",
            "JobIDRaw|State|ExitCode|MaxRSS|ElapsedRaw",
            "sacct --units=K",
            "Task 14",
            "generic candidate",
        )
        for phrase in required:
            self.assertIn(phrase, text)

    def test_expected_spec_must_resolve_under_research(self) -> None:
        outside = self.root / "outside.json"
        outside.write_bytes(json_bytes({"schema_version": 1, "cells": []}))
        run = self.root / "run"
        run.mkdir()
        errors = self.manifest_errors(run, outside)
        self.assertTrue(any("under research" in error for error in errors), errors)

    def test_execution_projection_must_equal_canonical_provenance_free_design(
        self,
    ) -> None:
        params = params_row()
        expected, run = self.write_expected_json(
            cells=[{"cell_id": "cell-a", "params": params}]
        )
        spec = json.loads((run / "run_spec.json").read_bytes())
        spec["cells"][0]["params"]["method"] = "changed-after-freeze"
        (run / "run_spec.json").write_bytes(json_bytes(spec))
        errors = self.manifest_errors(run, expected)
        self.assertTrue(any("design projection" in error for error in errors), errors)

        expected.write_text(
            json.dumps({"schema_version": 1, "cells": []}, indent=2) + "\n",
            encoding="utf-8",
        )
        errors = self.manifest_errors(run, expected)
        self.assertTrue(any("canonical" in error for error in errors), errors)

    def test_json_expected_spec_cannot_freeze_empty_or_provenance_bearing_design(
        self,
    ) -> None:
        expected, run = self.write_expected_json()
        errors = self.manifest_errors(run, expected)
        self.assertTrue(any("at least one cell" in error for error in errors), errors)

        expected.write_bytes(json_bytes(execution_spec([])))
        errors = self.manifest_errors(run, expected)
        self.assertTrue(any("exactly schema_version and cells" in error for error in errors))

    def test_execution_provenance_is_validated_independently(self) -> None:
        params = params_row()
        expected, run = self.write_expected_json(
            cells=[{"cell_id": "cell-a", "params": params}]
        )
        spec = json.loads((run / "run_spec.json").read_bytes())
        spec["provenance"]["tree_digest"] = "wrong"
        (run / "run_spec.json").write_bytes(json_bytes(spec))
        errors = self.manifest_errors(run, expected)
        self.assertTrue(any("tree_digest" in error for error in errors), errors)

    def test_generic_candidate_design_and_decimal_timeout_round_trip(self) -> None:
        params = params_row(method="unrestricted-candidate", timeout_seconds="0.05")
        expected, run = self.write_expected_json(
            cells=[{"cell_id": "cell-a", "params": params}]
        )
        self.write_manifest(run, params)
        self.assertEqual(self.manifest_errors(run, expected), [])

    def test_matrix_expected_spec_adds_only_fixed_baseline_fields(self) -> None:
        expected = self.research / "BASELINE_MATRIX.csv"
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(
            stream, fieldnames=gate.MATRIX_HEADER.split(","), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerow(matrix_row())
        expected.write_text(stream.getvalue(), encoding="utf-8")
        run = self.root / "run-matrix"
        run.mkdir()
        wrong = params_row(role="baseline", method="zero-fill")
        wrong["timeout_seconds"] = "299"
        cells = [{"cell_id": "cell-a", "params": wrong}]
        (run / "run_spec.json").write_bytes(json_bytes(execution_spec(cells)))
        errors = self.manifest_errors(run, expected)
        self.assertTrue(any("verbatim" in error for error in errors), errors)
        self.assertTrue(any("360 rows" in error for error in errors), errors)

    def test_frozen_matrix_remains_exactly_360_rows_and_digest_bound(self) -> None:
        matrix = self.original_research / "BASELINE_MATRIX.csv"
        digest = self.original_research / "BASELINE_MATRIX.sha256"
        errors: list[str] = []
        rows = gate.read_csv(matrix, gate.MATRIX_HEADER, errors)
        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 360)
        self.assertEqual(
            hashlib.sha256(matrix.read_bytes()).hexdigest(),
            digest.read_text(encoding="ascii").strip(),
        )

    def test_manifests_require_exactly_one_terminal_json_per_expected_cell(
        self,
    ) -> None:
        params = params_row()
        expected, run = self.write_expected_json(
            cells=[{"cell_id": "cell-a", "params": params}]
        )
        extra_params = params_row("extra")
        self.write_manifest(run, extra_params, status="NONZERO_EXIT")
        errors = self.manifest_errors(run, expected)
        self.assertTrue(any("missing manifest" in error for error in errors), errors)
        self.assertTrue(any("unexpected manifest" in error for error in errors), errors)

    def test_run_spec_and_manifest_recursively_reject_forbidden_keys(self) -> None:
        params = params_row()
        expected, run = self.write_expected_json(
            cells=[{"cell_id": "cell-a", "params": params}]
        )
        self.write_manifest(
            run,
            params,
            mutate=lambda payload: payload.update(
                {"diagnostics": [{"safe": {"secret_seed": "hidden"}}]}
            ),
        )
        errors = self.manifest_errors(run, expected)
        self.assertTrue(any("forbidden key" in error for error in errors), errors)

        spec = json.loads((run / "run_spec.json").read_bytes())
        spec["diagnostics"] = {"generator_name": "forbidden"}
        (run / "run_spec.json").write_bytes(json_bytes(spec))
        errors = self.manifest_errors(run, expected)
        self.assertTrue(
            any("run_spec.json" in error and "forbidden key" in error for error in errors),
            errors,
        )

    def test_success_manifest_transitively_binds_table_circuit_and_index(self) -> None:
        params = params_row()
        expected, run = self.write_expected_json(
            cells=[{"cell_id": "cell-a", "params": params}]
        )
        path = self.write_manifest(run, params)
        self.assertEqual(self.manifest_errors(run, expected), [])

        payload = json.loads(path.read_bytes())
        payload["completed_table_sha256"] = "f" * 64
        path.write_bytes(json_bytes(payload))
        errors = self.manifest_errors(run, expected)
        self.assertTrue(any("completed table" in error for error in errors), errors)

        payload["completed_table_sha256"] = hashlib.sha256(TABLE_BYTES).hexdigest()
        path.write_bytes(json_bytes(payload))
        artifact_path = run / "cells/cell-a/artifact.json"
        artifact = json.loads(artifact_path.read_bytes())
        artifact["equivalence"] = "fail"
        artifact_path.write_bytes(json_bytes(artifact))
        errors = self.manifest_errors(run, expected)
        self.assertTrue(any("equivalence" in error for error in errors), errors)

    def test_actual_runner_success_manifest_round_trips_through_checker(self) -> None:
        repo = self.root / "runner-repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        for key, value in (
            ("user.email", "test@example.invalid"),
            ("user.name", "Task 10 Test"),
            ("commit.gpgSign", "false"),
        ):
            subprocess.run(
                ["git", "-C", str(repo), "config", key, value], check=True
            )
        (repo / ".gitignore").write_text("results/\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-qm", "synthetic fixture"],
            check=True,
        )
        source_commit = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
        ).strip()
        tree = subprocess.check_output(
            ["git", "-C", str(repo), "ls-tree", "-rz", "--full-tree", "HEAD"]
        )
        provenance = {
            "source_commit": source_commit,
            "runner_commit": source_commit,
            "tree_digest": hashlib.sha256(tree).hexdigest(),
            "image_sha256": "none",
            "compiler_digest": "4" * 64,
        }
        params = params_row(method="actual-runner")
        cells = [{"cell_id": "cell-a", "params": params}]
        expected = self.research / "actual-runner.json"
        expected.write_bytes(json_bytes({"schema_version": 1, "cells": cells}))
        run = repo / "results" / "run"
        run.mkdir(parents=True)
        (run / "run_spec.json").write_bytes(
            json_bytes(
                {
                    "schema_version": 1,
                    "cells": cells,
                    "provenance": provenance,
                }
            )
        )
        table_digest = hashlib.sha256(TABLE_BYTES).hexdigest()
        circuit_digest = hashlib.sha256(CIRCUIT_BYTES).hexdigest()
        artifact = {
            "circuit_path": "circuit.txt",
            "circuit_sha256": circuit_digest,
            "completed_table_path": "completed-table.csv",
            "completed_table_sha256": table_digest,
            "equivalence": "pass",
            "schema_version": 1,
        }
        metrics = {
            "train_exact": 1.0,
            "visible_cv_exact": 0.75,
            "visible_cv_bit_accuracy": 0.875,
            "gates": 37,
            "completed_table_sha256": table_digest,
            "verifier": "pass",
        }
        child = "\n".join(
            (
                "from pathlib import Path",
                f"Path('completed-table.csv').write_bytes({TABLE_BYTES!r})",
                f"Path('circuit.txt').write_bytes({CIRCUIT_BYTES!r})",
                f"Path('artifact.json').write_bytes({json_bytes(artifact)!r})",
                f"Path('metrics.json').write_bytes({json_bytes(metrics)!r})",
            )
        )
        result = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--run-root",
                str(run),
                "--cell-id",
                "cell-a",
                "--metrics-json",
                str(run / "cells/cell-a/metrics.json"),
                "--",
                sys.executable,
                "-c",
                child,
            ],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.manifest_errors(run, expected), [])

    def test_every_runner_and_scheduler_terminal_failure_round_trips(self) -> None:
        cases = [
            *[
                ("runner", status)
                for status in (
                    "TIMEOUT",
                    "NONZERO_EXIT",
                    "INVALID_METRICS",
                    "VERIFIER_FAILED",
                    "VERIFIER_NOT_RUN",
                )
            ],
            *[
                ("scheduler", status)
                for status in (
                    "TIMEOUT",
                    "OOM",
                    "NONZERO_EXIT",
                    "CANCELLED",
                    "MISSING_SUCCESS_MANIFEST",
                )
            ],
        ]
        for producer, status in cases:
            with self.subTest(producer=producer, status=status):
                params = params_row(timeout_seconds="0.05" if status == "TIMEOUT" else "300")
                expected, run = self.write_expected_json(
                    cells=[{"cell_id": "cell-a", "params": params}]
                )
                self.write_manifest(run, params, status=status, producer=producer)
                self.assertEqual(self.manifest_errors(run, expected), [])

    def test_operational_metadata_is_conditional_on_producer(self) -> None:
        params = params_row()
        expected, run = self.write_expected_json(
            cells=[{"cell_id": "cell-a", "params": params}]
        )
        path = self.write_manifest(run, params, status="NONZERO_EXIT")
        payload = json.loads(path.read_bytes())
        payload["scheduler_job_id"] = "8123"
        path.write_bytes(json_bytes(payload))
        errors = self.manifest_errors(run, expected)
        self.assertTrue(any("runner scheduler" in error for error in errors), errors)

        expected, run = self.write_expected_json(
            cells=[{"cell_id": "cell-a", "params": params}]
        )
        path = self.write_manifest(
            run, params, status="NONZERO_EXIT", producer="scheduler"
        )
        payload = json.loads(path.read_bytes())
        payload["argv"] = ["not allowed"]
        path.write_bytes(json_bytes(payload))
        errors = self.manifest_errors(run, expected)
        self.assertTrue(any("scheduler argv" in error for error in errors), errors)

    def test_timeout_requires_declared_cap_for_runner_and_scheduler(self) -> None:
        for producer in ("runner", "scheduler"):
            with self.subTest(producer=producer):
                params = params_row(timeout_seconds="0.05")
                expected, run = self.write_expected_json(
                    cells=[{"cell_id": "cell-a", "params": params}]
                )
                path = self.write_manifest(
                    run, params, status="TIMEOUT", producer=producer
                )
                payload = json.loads(path.read_bytes())
                payload["elapsed_seconds"] = "none"
                path.write_bytes(json_bytes(payload))

                errors = self.manifest_errors(run, expected)

                self.assertTrue(
                    any("declared censored cap" in error for error in errors),
                    errors,
                )

    def test_runner_requires_measured_elapsed_for_every_observed_terminal(self) -> None:
        for status in (
            "SUCCESS",
            "NONZERO_EXIT",
            "INVALID_METRICS",
            "VERIFIER_FAILED",
            "VERIFIER_NOT_RUN",
        ):
            with self.subTest(status=status):
                params = params_row()
                expected, run = self.write_expected_json(
                    cells=[{"cell_id": "cell-a", "params": params}]
                )
                path = self.write_manifest(run, params, status=status)
                payload = json.loads(path.read_bytes())
                payload["elapsed_seconds"] = "none"
                path.write_bytes(json_bytes(payload))

                errors = self.manifest_errors(run, expected)

                self.assertTrue(
                    any("runner elapsed_seconds must be measured" in error for error in errors),
                    errors,
                )

    def test_runner_cleanup_is_zero_unless_timeout_and_measured_on_timeout(
        self,
    ) -> None:
        cases = (
            ("NONZERO_EXIT", "0.01", "non-timeout cleanup_seconds"),
            ("TIMEOUT", "none", "timeout cleanup_seconds"),
        )
        for status, cleanup, fragment in cases:
            with self.subTest(status=status):
                params = params_row(
                    timeout_seconds="0.05" if status == "TIMEOUT" else "300"
                )
                expected, run = self.write_expected_json(
                    cells=[{"cell_id": "cell-a", "params": params}]
                )
                path = self.write_manifest(run, params, status=status)
                payload = json.loads(path.read_bytes())
                payload["cleanup_seconds"] = cleanup
                path.write_bytes(json_bytes(payload))

                errors = self.manifest_errors(run, expected)

                self.assertTrue(any(fragment in error for error in errors), errors)

    def test_manifest_row_fields_must_be_json_strings(self) -> None:
        params = params_row()
        expected, run = self.write_expected_json(
            cells=[{"cell_id": "cell-a", "params": params}]
        )
        path = self.write_manifest(run, params)
        payload = json.loads(path.read_bytes())
        payload["blind"] = True
        path.write_bytes(json_bytes(payload))
        errors = self.manifest_errors(run, expected)
        self.assertTrue(any("canonical string" in error for error in errors), errors)

    def test_scheduler_raw_exit_elapsed_and_ordered_index_are_bound(self) -> None:
        cases = ("completed-nonzero", "elapsed-mismatch", "wrong-index")
        for case in cases:
            with self.subTest(case=case):
                params = params_row()
                status = (
                    "MISSING_SUCCESS_MANIFEST"
                    if case == "completed-nonzero"
                    else "NONZERO_EXIT"
                )
                expected, run = self.write_expected_json(
                    cells=[{"cell_id": "cell-a", "params": params}]
                )
                path = self.write_manifest(
                    run, params, status=status, producer="scheduler"
                )
                payload = json.loads(path.read_bytes())
                if case == "completed-nonzero":
                    payload["scheduler_exit_code"] = "1:0"
                elif case == "elapsed-mismatch":
                    payload["scheduler_elapsed_seconds"] = "13"
                else:
                    payload["scheduler_task_index"] = "2"
                    (run / "slurm-8123_2.out").write_bytes(b"scheduler log\n")
                path.write_bytes(json_bytes(payload))
                errors = self.manifest_errors(run, expected)
                self.assertTrue(
                    any(
                        fragment in error
                        for error in errors
                        for fragment in (
                            "state/exit",
                            "elapsed",
                            "ordered task index",
                        )
                    ),
                    errors,
                )

    def test_runner_log_hash_and_run_spec_hash_are_checked(self) -> None:
        params = params_row()
        expected, run = self.write_expected_json(
            cells=[{"cell_id": "cell-a", "params": params}]
        )
        path = self.write_manifest(run, params, status="NONZERO_EXIT")
        payload = json.loads(path.read_bytes())
        payload["stdout_sha256"] = "f" * 64
        payload["run_spec_sha256"] = "e" * 64
        path.write_bytes(json_bytes(payload))
        errors = self.manifest_errors(run, expected)
        self.assertTrue(any("stdout_sha256" in error for error in errors), errors)
        self.assertTrue(any("run_spec_sha256" in error for error in errors), errors)

    def test_baseline_evidence_path_hash_schema_and_transitive_artifact(self) -> None:
        row = baseline_row()
        errors: list[str] = []
        row["evidence_path"] = "../outside.json"
        gate.check_baseline_evidence(row, errors, label="BASELINES.csv:2")
        self.assertTrue(any("under results" in error for error in errors), errors)

        row = baseline_row()
        errors = []
        gate.check_baseline_evidence(row, errors, label="BASELINES.csv:2")
        self.assertTrue(any("missing evidence" in error for error in errors), errors)

        run = self.results / "synthetic"
        run.mkdir()
        params = params_row(role="baseline", method="zero-fill")
        cells = [{"cell_id": "cell-a", "params": params}]
        (run / "run_spec.json").write_bytes(json_bytes(execution_spec(cells)))
        path = self.write_manifest(run, params)
        payload = json.loads(path.read_bytes())
        for field in gate.MANIFEST_ROW_FIELDS:
            if field in payload:
                row[field] = str(payload[field]).lower() if isinstance(payload[field], bool) else str(payload[field])
        row["artifact_sha256"] = str(payload["artifact_sha256"])
        row["evidence_path"] = path.relative_to(self.root).as_posix()
        row["manifest_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        errors = []
        gate.check_baseline_evidence(row, errors, label="BASELINES.csv:2")
        self.assertEqual(errors, [])

        (run / "cells/cell-a/circuit.txt").write_bytes(b"tampered\n")
        errors = []
        gate.check_baseline_evidence(row, errors, label="BASELINES.csv:2")
        self.assertTrue(any("circuit" in error for error in errors), errors)

    def test_baseline_evidence_manifest_is_bound_to_its_native_run_spec(self) -> None:
        run = self.results / "synthetic"
        run.mkdir()
        params = params_row(role="baseline", method="zero-fill")
        cells = [{"cell_id": "cell-a", "params": params}]
        run_spec_path = run / "run_spec.json"
        run_spec_path.write_bytes(json_bytes(execution_spec(cells)))
        path = self.write_manifest(run, params)
        payload = json.loads(path.read_bytes())
        row = baseline_row()
        for field in gate.MANIFEST_ROW_FIELDS:
            if field in payload:
                row[field] = str(payload[field])

        changed = json.loads(run_spec_path.read_bytes())
        changed["cells"][0]["params"]["method"] = "changed"
        run_spec_path.write_bytes(json_bytes(changed))
        payload["run_spec_sha256"] = hashlib.sha256(
            run_spec_path.read_bytes()
        ).hexdigest()
        path.write_bytes(json_bytes(payload))
        row["manifest_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        row["evidence_path"] = path.relative_to(self.root).as_posix()
        errors: list[str] = []
        gate.check_baseline_evidence(row, errors, label="BASELINES.csv:2")
        self.assertTrue(
            any("run_spec params" in error for error in errors), errors
        )

    def test_status_requires_exact_verifier_and_metric_mapping(self) -> None:
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
        expected_fragments = (
            "train_exact must equal 1.0",
            "visible_cv_exact",
            "visible_cv_bit_accuracy",
            "gates",
            "elapsed_seconds",
            "peak_memory_kib",
        )
        for fragment in expected_fragments:
            self.assertTrue(any(fragment in error for error in errors), errors)
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
