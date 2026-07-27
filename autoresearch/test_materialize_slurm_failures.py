from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MATERIALIZER = (
    Path(__file__).parents[1] / "scripts" / "materialize-slurm-failures.py"
)
RAW_HEADER = b"JobIDRaw|State|ExitCode|MaxRSS|ElapsedRaw\n"


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def params(cell_id: str) -> dict[str, str]:
    return {
        "comparison_id": cell_id,
        "role": "candidate",
        "method": "synthetic",
        "method_version": "1",
        "blind": "true",
        "evaluation_scope": "visible_cv_only",
        "hardware": "synthetic-card",
        "dataset_id": f"opaque-{cell_id}",
        "tier": "n=1",
        "observation_fraction": "0.10",
        "algorithm_seed": hashlib.sha256(cell_id.encode()).hexdigest(),
        "repeat": "0",
        "timeout_seconds": "300",
    }


class MaterializeSlurmFailuresTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="task10-slurm-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write_run(self, name: str = "run", cells: tuple[str, ...] = ("cell-a",)) -> Path:
        run = self.root / name
        run.mkdir()
        spec = {
            "schema_version": 1,
            "cells": [
                {"cell_id": cell_id, "params": params(cell_id)}
                for cell_id in cells
            ],
            "provenance": {
                "source_commit": "1" * 40,
                "runner_commit": "2" * 40,
                "tree_digest": "3" * 64,
                "image_sha256": "4" * 64,
                "compiler_digest": "5" * 64,
            },
        }
        (run / "run_spec.json").write_bytes(canonical_json_bytes(spec))
        return run

    def write_raw(self, run: Path, rows: list[str]) -> Path:
        path = run / "sacct.psv"
        path.write_bytes(RAW_HEADER + ("\n".join(rows) + "\n").encode())
        return path

    def write_logs(
        self, run: Path, job_id: str, count: int, *, omit: int | None = None
    ) -> None:
        for index in range(1, count + 1):
            if index != omit:
                (run / f"slurm-{job_id}_{index}.out").write_bytes(
                    f"task {index}\n".encode()
                )

    def invoke(
        self, run: Path, raw: Path, job_id: str = "8123"
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(MATERIALIZER),
                str(run),
                str(raw),
                "--job-id",
                job_id,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def manifest(self, run: Path, cell_id: str = "cell-a") -> dict[str, object]:
        return json.loads((run / f"cells/{cell_id}/manifest.json").read_bytes())

    def valid_runner_manifest(self, run: Path, cell_id: str) -> bytes:
        cell = run / "cells" / cell_id
        cell.mkdir(parents=True, exist_ok=True)
        stdout = b"runner out\n"
        stderr = b"runner err\n"
        (cell / "stdout.log").write_bytes(stdout)
        (cell / "stderr.log").write_bytes(stderr)
        framed = (
            len(stdout).to_bytes(8, "big")
            + stdout
            + len(stderr).to_bytes(8, "big")
            + stderr
        )
        spec = json.loads((run / "run_spec.json").read_bytes())
        payload: dict[str, object] = {
            **params(cell_id),
            **spec["provenance"],
            "schema_version": 1,
            "producer": "runner",
            "run_spec_sha256": hashlib.sha256(
                (run / "run_spec.json").read_bytes()
            ).hexdigest(),
            "argv": ["synthetic"],
            "started_utc": "2026-07-27T01:02:03.000004Z",
            "ended_utc": "2026-07-27T01:02:04.000005Z",
            "status": "NONZERO_EXIT",
            "exit_code": "1",
            "timed_out": "false",
            "elapsed_seconds": "1.0",
            "cleanup_seconds": "0.0",
            "peak_memory_kib": "1",
            "verifier": "not_run",
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            "log_sha256": hashlib.sha256(framed).hexdigest(),
            "scheduler_sha256": "none",
            "scheduler_job_id": "none",
            "scheduler_task_index": "none",
            "scheduler_state": "none",
            "scheduler_exit_code": "none",
            "scheduler_classification": "none",
            "scheduler_elapsed_seconds": "none",
            "train_exact": "none",
            "visible_cv_exact": "none",
            "visible_cv_bit_accuracy": "none",
            "gates": "none",
            "completed_table_sha256": "none",
            "circuit_sha256": "none",
            "artifact_sha256": "none",
            "artifact_path": "none",
        }
        return canonical_json_bytes(payload)

    def test_every_scheduler_terminal_mapping_never_emits_success(self) -> None:
        cases = (
            ("TIMEOUT", "0:15", "TIMEOUT", "124", "true"),
            ("OUT_OF_MEMORY", "0:9", "OOM", "137", "false"),
            ("FAILED", "17:0", "NONZERO_EXIT", "17", "false"),
            ("CANCELLED", "0:15", "CANCELLED", "130", "false"),
            (
                "COMPLETED",
                "0:0",
                "MISSING_SUCCESS_MANIFEST",
                "70",
                "false",
            ),
        )
        for offset, (state, raw_exit, status, exit_code, timed_out) in enumerate(
            cases
        ):
            with self.subTest(state=state):
                job_id = str(8200 + offset)
                run = self.write_run(f"run-{state.lower()}")
                raw = self.write_raw(
                    run, [f"{job_id}_1|{state}|{raw_exit}|123K|12"]
                )
                self.write_logs(run, job_id, 1)
                result = self.invoke(run, raw, job_id)

                self.assertEqual(result.returncode, 0, result.stderr)
                manifest = self.manifest(run)
                self.assertEqual(manifest["status"], status)
                self.assertNotEqual(manifest["status"], "SUCCESS")
                self.assertEqual(manifest["exit_code"], exit_code)
                self.assertEqual(manifest["timed_out"], timed_out)
                self.assertEqual(manifest["producer"], "scheduler")
                self.assertEqual(manifest["scheduler_state"], state)
                self.assertEqual(manifest["scheduler_exit_code"], raw_exit)
                self.assertEqual(manifest["scheduler_classification"], status)
                self.assertEqual(manifest["scheduler_elapsed_seconds"], "12")
                self.assertEqual(manifest["peak_memory_kib"], "123")
                if status == "TIMEOUT":
                    self.assertEqual(manifest["elapsed_seconds"], "300.0")

    def test_signal_only_failed_exit_is_normalized(self) -> None:
        run = self.write_run()
        raw = self.write_raw(run, ["8123_1|FAILED|0:9|7K|1"])
        self.write_logs(run, "8123", 1)
        result = self.invoke(run, raw)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.manifest(run)["exit_code"], "137")

    def test_peak_memory_uses_maximum_kib_across_root_batch_and_extern(self) -> None:
        cases = (
            ("root", ("101K", "99K", ""), "101"),
            ("blank-root", ("", "202K", ""), "202"),
            ("extern-max", ("100K", "200K", "303K"), "303"),
            ("all-blank", ("", "", ""), "none"),
        )
        for offset, (name, rss, expected) in enumerate(cases):
            with self.subTest(name=name):
                job_id = str(8300 + offset)
                run = self.write_run(f"run-{name}")
                rows = [
                    f"{job_id}_1|FAILED|1:0|{rss[0]}|4",
                    f"{job_id}_1.batch|FAILED|1:0|{rss[1]}|4",
                    f"{job_id}_1.extern|FAILED|1:0|{rss[2]}|4",
                ]
                raw = self.write_raw(run, rows)
                self.write_logs(run, job_id, 1)
                result = self.invoke(run, raw, job_id)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.manifest(run)["peak_memory_kib"], expected)

    def test_complete_raw_and_task_log_bytes_are_hashed(self) -> None:
        run = self.write_run()
        raw = self.write_raw(run, ["8123_1|FAILED|1:0||4"])
        self.write_logs(run, "8123", 1)
        result = self.invoke(run, raw)

        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = self.manifest(run)
        log = (run / "slurm-8123_1.out").read_bytes()
        self.assertEqual(
            manifest["scheduler_sha256"], hashlib.sha256(raw.read_bytes()).hexdigest()
        )
        self.assertEqual(manifest["stdout_sha256"], hashlib.sha256(log).hexdigest())
        self.assertEqual(manifest["log_sha256"], hashlib.sha256(log).hexdigest())
        self.assertEqual(manifest["stderr_sha256"], "none")
        self.assertEqual(manifest["argv"], [])
        self.assertEqual(manifest["started_utc"], "none")
        self.assertEqual(manifest["ended_utc"], "none")

    def test_ordered_cells_require_exactly_one_root_row_and_log_before_writes(
        self,
    ) -> None:
        for name, rows, omit_log, fragment in (
            (
                "missing-root",
                ["8123_1|FAILED|1:0||1"],
                None,
                "root allocation",
            ),
            (
                "duplicate-id",
                [
                    "8123_1|FAILED|1:0||1",
                    "8123_1|FAILED|1:0||1",
                    "8123_2|FAILED|1:0||1",
                ],
                None,
                "duplicate",
            ),
            (
                "missing-log",
                [
                    "8123_1|FAILED|1:0||1",
                    "8123_2|FAILED|1:0||1",
                ],
                2,
                "task log",
            ),
        ):
            with self.subTest(name=name):
                run = self.write_run(f"run-{name}", ("cell-a", "cell-b"))
                raw = self.write_raw(run, rows)
                self.write_logs(run, "8123", 2, omit=omit_log)
                result = self.invoke(run, raw)
                self.assertEqual(result.returncode, 2)
                self.assertIn(fragment, result.stderr)
                self.assertFalse((run / "cells").exists())

    def test_pending_unknown_bad_units_and_inconsistent_exit_are_rejected(self) -> None:
        cases = (
            ("RUNNING", "0:0", "", "1", "terminal"),
            ("MYSTERY", "0:0", "", "1", "state"),
            ("FAILED", "0:0", "", "1", "inconsistent"),
            ("COMPLETED", "1:0", "", "1", "inconsistent"),
            ("FAILED", "1:0", "1.5K", "1", "MaxRSS"),
            ("FAILED", "1:0", "1M", "1", "MaxRSS"),
            ("FAILED", "1:0", "1K", "01", "ElapsedRaw"),
            ("FAILED", "256:0", "1K", "1", "ExitCode"),
        )
        for offset, (state, raw_exit, rss, elapsed, fragment) in enumerate(cases):
            with self.subTest(state=state, raw_exit=raw_exit, rss=rss):
                job_id = str(8400 + offset)
                run = self.write_run(f"bad-{offset}")
                raw = self.write_raw(
                    run, [f"{job_id}_1|{state}|{raw_exit}|{rss}|{elapsed}"]
                )
                self.write_logs(run, job_id, 1)
                result = self.invoke(run, raw, job_id)
                self.assertEqual(result.returncode, 2)
                self.assertIn(fragment, result.stderr)
                self.assertFalse((run / "cells").exists())

    def test_existing_runner_manifest_is_byte_identical_but_other_manifest_rejected(
        self,
    ) -> None:
        run = self.write_run(cells=("cell-a", "cell-b"))
        raw = self.write_raw(
            run,
            [
                "8123_1|FAILED|1:0||1",
                "8123_2|FAILED|1:0||1",
            ],
        )
        self.write_logs(run, "8123", 2)
        existing = run / "cells/cell-a/manifest.json"
        original = self.valid_runner_manifest(run, "cell-a")
        existing.write_bytes(original)
        result = self.invoke(run, raw)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(existing.read_bytes(), original)
        self.assertTrue((run / "cells/cell-b/manifest.json").is_file())

        invalid_run = self.write_run("invalid-existing")
        invalid_raw = self.write_raw(
            invalid_run, ["8123_1|FAILED|1:0||1"]
        )
        self.write_logs(invalid_run, "8123", 1)
        invalid = invalid_run / "cells/cell-a/manifest.json"
        invalid.parent.mkdir(parents=True)
        invalid.write_bytes(canonical_json_bytes({"producer": "scheduler"}))
        invalid_original = invalid.read_bytes()
        rejected = self.invoke(invalid_run, invalid_raw)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("existing manifest", rejected.stderr)
        self.assertEqual(invalid.read_bytes(), invalid_original)

    def test_truncated_runner_manifest_is_not_treated_as_valid(self) -> None:
        run = self.write_run()
        raw = self.write_raw(run, ["8123_1|FAILED|1:0||1"])
        self.write_logs(run, "8123", 1)
        spec = json.loads((run / "run_spec.json").read_bytes())
        path = run / "cells/cell-a/manifest.json"
        path.parent.mkdir(parents=True)
        truncated = canonical_json_bytes(
            {
                **params("cell-a"),
                **spec["provenance"],
                "schema_version": 1,
                "producer": "runner",
                "run_spec_sha256": hashlib.sha256(
                    (run / "run_spec.json").read_bytes()
                ).hexdigest(),
                "status": "NONZERO_EXIT",
            }
        )
        path.write_bytes(truncated)
        result = self.invoke(run, raw)

        self.assertEqual(result.returncode, 2)
        self.assertIn("existing manifest", result.stderr)
        self.assertEqual(path.read_bytes(), truncated)

    def test_materialization_is_deterministic_for_identical_evidence(self) -> None:
        produced: list[bytes] = []
        for name in ("first", "second"):
            run = self.write_run(name)
            raw = self.write_raw(run, ["8123_1|FAILED|17:0|88K|9"])
            self.write_logs(run, "8123", 1)
            result = self.invoke(run, raw)
            self.assertEqual(result.returncode, 0, result.stderr)
            produced.append((run / "cells/cell-a/manifest.json").read_bytes())
        self.assertEqual(produced[0], produced[1])


if __name__ == "__main__":
    unittest.main()
