from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


RUNNER = Path(__file__).parents[1] / "scripts" / "run-experiment.py"
RUNNER_SPEC = importlib.util.spec_from_file_location("task10_runner", RUNNER)
assert RUNNER_SPEC is not None and RUNNER_SPEC.loader is not None
runner = importlib.util.module_from_spec(RUNNER_SPEC)
sys.modules[RUNNER_SPEC.name] = runner
RUNNER_SPEC.loader.exec_module(runner)
TABLE_BYTES = b"input,output\n0,0\n"
CIRCUIT_BYTES = b"xag\n"


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


class RunExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="task10-runner-")
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.run_index = 0
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "config", "user.email", "test@example.invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.repo), "config", "user.name", "Task 10 Test"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.repo), "config", "commit.gpgSign", "false"],
            check=True,
        )
        (self.repo / ".gitignore").write_text("results/\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", ".gitignore"], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "-qm", "synthetic fixture"],
            check=True,
        )

    def write_run_spec(
        self,
        timeout_seconds: str,
        *,
        cell_id: str = "cell-001",
        role: str = "candidate",
    ) -> tuple[Path, Path]:
        source_commit = subprocess.check_output(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True
        ).strip()
        tree_bytes = subprocess.check_output(
            ["git", "-C", str(self.repo), "ls-tree", "-rz", "--full-tree", "HEAD"]
        )
        self.run_index += 1
        run_root = self.repo / "results" / f"run-{self.run_index}"
        run_root.mkdir(parents=True)
        metrics_path = run_root / "cells" / cell_id / "metrics.json"
        params = {
            "comparison_id": cell_id,
            "role": role,
            "method": "synthetic",
            "method_version": "1",
            "blind": "true",
            "evaluation_scope": "visible_cv_only",
            "hardware": "synthetic-card",
            "dataset_id": "opaque-synthetic",
            "tier": "n=1",
            "observation_fraction": "0.10",
            "algorithm_seed": "a" * 64,
            "repeat": "0",
            "timeout_seconds": timeout_seconds,
        }
        spec = {
            "schema_version": 1,
            "cells": [{"cell_id": cell_id, "params": params}],
            "provenance": {
                "source_commit": source_commit,
                "runner_commit": source_commit,
                "tree_digest": hashlib.sha256(tree_bytes).hexdigest(),
                "image_sha256": "none",
                "compiler_digest": "b" * 64,
            },
        }
        (run_root / "run_spec.json").write_bytes(canonical_json_bytes(spec))
        return run_root, metrics_path

    def invoke(
        self,
        run_root: Path,
        metrics_path: Path,
        command: list[str],
        *,
        cell_id: str = "cell-001",
        container_provenance: Path | None = None,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        argv = [
            sys.executable,
            str(RUNNER),
            "--run-root",
            str(run_root),
            "--cell-id",
            cell_id,
            "--metrics-json",
            str(metrics_path),
        ]
        if container_provenance is not None:
            argv.extend(["--container-provenance", str(container_provenance)])
        argv.extend(["--", *command])
        return subprocess.run(
            argv,
            cwd=self.repo,
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )

    def artifact_command(
        self,
        *,
        metrics_updates: dict[str, object] | None = None,
        remove_metrics: tuple[str, ...] = (),
        artifact_updates: dict[str, object] | None = None,
        raw_metrics: bytes | None = None,
        raw_artifact: bytes | None = None,
        symlink: str | None = None,
    ) -> list[str]:
        table_digest = hashlib.sha256(TABLE_BYTES).hexdigest()
        circuit_digest = hashlib.sha256(CIRCUIT_BYTES).hexdigest()
        metrics: dict[str, object] = {
            "train_exact": 1.0,
            "visible_cv_exact": 0.75,
            "visible_cv_bit_accuracy": 0.875,
            "gates": 37,
            "completed_table_sha256": table_digest,
            "verifier": "pass",
        }
        metrics.update(metrics_updates or {})
        for key in remove_metrics:
            metrics.pop(key)
        artifact: dict[str, object] = {
            "circuit_path": "circuit.txt",
            "circuit_sha256": circuit_digest,
            "completed_table_path": "completed-table.csv",
            "completed_table_sha256": table_digest,
            "equivalence": "pass",
            "schema_version": 1,
        }
        artifact.update(artifact_updates or {})
        metrics_bytes = (
            raw_metrics if raw_metrics is not None else canonical_json_bytes(metrics)
        )
        artifact_bytes = (
            raw_artifact if raw_artifact is not None else canonical_json_bytes(artifact)
        )
        code = "\n".join(
            [
                "from pathlib import Path",
                f"Path('completed-table.csv').write_bytes({TABLE_BYTES!r})",
                f"Path('circuit.txt').write_bytes({CIRCUIT_BYTES!r})",
                f"Path('artifact.json').write_bytes({artifact_bytes!r})",
                f"Path('metrics.json').write_bytes({metrics_bytes!r})",
            ]
        )
        if symlink is not None:
            code += (
                f"\nPath({symlink!r}).unlink()"
                f"\nPath({symlink!r}).symlink_to('artifact.json')"
            )
        return [sys.executable, "-c", code]

    def read_manifest(self, run_root: Path, cell_id: str = "cell-001") -> tuple[bytes, dict[str, object]]:
        raw = (run_root / "cells" / cell_id / "manifest.json").read_bytes()
        return raw, json.loads(raw)

    def test_subsecond_sleep_becomes_terminal_timeout_manifest(self) -> None:
        run_root, metrics_path = self.write_run_spec("0.05")
        result = self.invoke(
            run_root,
            metrics_path,
            [sys.executable, "-c", "import time; time.sleep(0.2)"],
        )

        self.assertEqual(result.returncode, 124, result.stderr)
        manifest_path = run_root / "cells" / "cell-001" / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        self.assertEqual(manifest["status"], "TIMEOUT")
        self.assertEqual(manifest["exit_code"], "124")
        self.assertEqual(manifest["timed_out"], "true")
        self.assertEqual(manifest["elapsed_seconds"], "0.05")

    def test_timeout_above_five_minutes_is_rejected_before_cell_or_child(self) -> None:
        run_root, metrics_path = self.write_run_spec("300.001")
        marker = self.repo / "child-ran"
        result = self.invoke(
            run_root,
            metrics_path,
            [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"],
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("timeout_seconds", result.stderr)
        self.assertFalse((run_root / "cells" / "cell-001").exists())
        self.assertFalse(marker.exists())

    def test_noncanonical_decimal_timeout_is_rejected_before_cell_creation(self) -> None:
        run_root, metrics_path = self.write_run_spec("1.00")
        result = self.invoke(
            run_root,
            metrics_path,
            [sys.executable, "-c", "raise SystemExit(19)"],
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("canonical", result.stderr)
        self.assertFalse((run_root / "cells/cell-001").exists())

    def test_sigterm_ignoring_process_tree_is_absent_after_deadline(self) -> None:
        run_root, metrics_path = self.write_run_spec("0.1")
        pid_path = self.repo / "grandchild.pid"
        grandchild = (
            "import signal,time;"
            "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
            "time.sleep(10)"
        )
        parent = "\n".join(
            [
                "import signal,subprocess,sys,time",
                "from pathlib import Path",
                "signal.signal(signal.SIGTERM, signal.SIG_IGN)",
                f"child=subprocess.Popen([sys.executable,'-c',{grandchild!r}])",
                f"Path({str(pid_path)!r}).write_text(str(child.pid))",
                "time.sleep(10)",
            ]
        )
        started = time.monotonic()
        result = self.invoke(
            run_root, metrics_path, [sys.executable, "-c", parent]
        )
        elapsed = time.monotonic() - started

        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertLess(elapsed, 0.50)
        grandchild_pid = int(pid_path.read_text())
        for _ in range(50):
            try:
                os.kill(grandchild_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.01)
        else:
            self.fail(f"grandchild process {grandchild_pid} survived timeout")

    def test_nonzero_exit_preserves_logs_hashes_argv_and_exit_code(self) -> None:
        run_root, metrics_path = self.write_run_spec("2")
        command = [
            sys.executable,
            "-c",
            "import sys;print('out value');print('err value',file=sys.stderr);sys.exit(17)",
            "argument with spaces",
            "tail",
        ]
        result = self.invoke(run_root, metrics_path, command)

        self.assertEqual(result.returncode, 17, result.stderr)
        _, manifest = self.read_manifest(run_root)
        stdout = b"out value\n"
        stderr = b"err value\n"
        framed = (
            len(stdout).to_bytes(8, "big")
            + stdout
            + len(stderr).to_bytes(8, "big")
            + stderr
        )
        self.assertEqual(manifest["status"], "NONZERO_EXIT")
        self.assertEqual(manifest["exit_code"], "17")
        self.assertEqual(manifest["argv"], command)
        self.assertEqual(manifest["stdout_sha256"], hashlib.sha256(stdout).hexdigest())
        self.assertEqual(manifest["stderr_sha256"], hashlib.sha256(stderr).hexdigest())
        self.assertEqual(manifest["log_sha256"], hashlib.sha256(framed).hexdigest())
        self.assertEqual((run_root / "cells/cell-001/stdout.log").read_bytes(), stdout)
        self.assertEqual((run_root / "cells/cell-001/stderr.log").read_bytes(), stderr)

    def test_child_cannot_remove_runner_owned_terminal_logs(self) -> None:
        run_root, metrics_path = self.write_run_spec("2")
        command = [
            sys.executable,
            "-c",
            "\n".join(
                (
                    "import os, sys",
                    "print('owned out')",
                    "print('owned err', file=sys.stderr)",
                    "sys.stdout.flush()",
                    "sys.stderr.flush()",
                    "os.unlink('stdout.log')",
                    "os.unlink('stderr.log')",
                    "raise SystemExit(17)",
                )
            ),
        ]
        result = self.invoke(run_root, metrics_path, command)

        self.assertEqual(result.returncode, 17, result.stderr)
        _, manifest = self.read_manifest(run_root)
        stdout = b"owned out\n"
        stderr = b"owned err\n"
        self.assertEqual((run_root / "cells/cell-001/stdout.log").read_bytes(), stdout)
        self.assertEqual((run_root / "cells/cell-001/stderr.log").read_bytes(), stderr)
        self.assertEqual(manifest["stdout_sha256"], hashlib.sha256(stdout).hexdigest())
        self.assertEqual(manifest["stderr_sha256"], hashlib.sha256(stderr).hexdigest())

    def test_child_cannot_precreate_runner_atomic_log_temporaries(self) -> None:
        run_root, metrics_path = self.write_run_spec("2")
        command = [
            sys.executable,
            "-c",
            "\n".join(
                (
                    "import os, sys",
                    "from pathlib import Path",
                    "runner_pid = os.getppid()",
                    "Path(f'.stdout.log.tmp-{runner_pid}').write_bytes(b'blocked')",
                    "Path(f'.stderr.log.tmp-{runner_pid}').write_bytes(b'blocked')",
                    "print('owned out')",
                    "print('owned err', file=sys.stderr)",
                    "raise SystemExit(17)",
                )
            ),
        ]
        result = self.invoke(run_root, metrics_path, command)

        self.assertEqual(result.returncode, 17, result.stderr)
        _, manifest = self.read_manifest(run_root)
        self.assertEqual(manifest["status"], "NONZERO_EXIT")
        self.assertEqual(
            (run_root / "cells/cell-001/stdout.log").read_bytes(), b"owned out\n"
        )
        self.assertEqual(
            (run_root / "cells/cell-001/stderr.log").read_bytes(), b"owned err\n"
        )

    def test_signal_exit_is_normalized_to_128_plus_signal(self) -> None:
        run_root, metrics_path = self.write_run_spec("2")
        result = self.invoke(
            run_root,
            metrics_path,
            [
                sys.executable,
                "-c",
                "import os,signal;os.kill(os.getpid(),signal.SIGTERM)",
            ],
        )

        self.assertEqual(result.returncode, 128 + signal.SIGTERM, result.stderr)
        _, manifest = self.read_manifest(run_root)
        self.assertEqual(manifest["status"], "NONZERO_EXIT")
        self.assertEqual(manifest["exit_code"], str(128 + signal.SIGTERM))

    def test_existing_cell_is_rejected_without_overwrite(self) -> None:
        run_root, metrics_path = self.write_run_spec("2")
        cell = run_root / "cells/cell-001"
        cell.mkdir(parents=True)
        marker = cell / "keep.txt"
        marker.write_text("preserve", encoding="utf-8")
        result = self.invoke(
            run_root, metrics_path, [sys.executable, "-c", "raise SystemExit(0)"]
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")
        self.assertFalse((cell / "manifest.json").exists())

    def test_metrics_path_outside_cell_and_empty_command_are_rejected(self) -> None:
        for outside, command, fragment in (
            (True, [sys.executable, "-c", "pass"], "metrics-json"),
            (False, [], "command"),
        ):
            with self.subTest(fragment=fragment):
                run_root, metrics_path = self.write_run_spec("2")
                if outside:
                    metrics_path = run_root / "metrics.json"
                result = self.invoke(run_root, metrics_path, command)
                self.assertEqual(result.returncode, 2)
                self.assertIn(fragment, result.stderr)
                self.assertFalse((run_root / "cells/cell-001").exists())

    def test_missing_and_duplicate_cells_are_rejected_before_execution(self) -> None:
        for mode in ("missing", "duplicate"):
            with self.subTest(mode=mode):
                run_root, metrics_path = self.write_run_spec("2")
                spec = json.loads((run_root / "run_spec.json").read_bytes())
                if mode == "missing":
                    spec["cells"][0]["cell_id"] = "other"
                    spec["cells"][0]["params"]["comparison_id"] = "other"
                else:
                    spec["cells"].append(spec["cells"][0])
                (run_root / "run_spec.json").write_bytes(canonical_json_bytes(spec))
                result = self.invoke(
                    run_root,
                    metrics_path,
                    [sys.executable, "-c", "raise SystemExit(0)"],
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn(
                    "does not declare" if mode == "missing" else "duplicate",
                    result.stderr,
                )
                self.assertFalse((run_root / "cells/cell-001").exists())

    def test_every_cell_has_full_semantic_validation_before_execution(self) -> None:
        cases = {
            "role": "untrusted",
            "algorithm_seed": "not-a-digest",
            "repeat": "01",
            "method": "",
            "timeout_seconds": "301",
        }
        for field, invalid in cases.items():
            with self.subTest(field=field):
                run_root, metrics_path = self.write_run_spec("2")
                spec_path = run_root / "run_spec.json"
                spec = json.loads(spec_path.read_bytes())
                sibling = json.loads(json.dumps(spec["cells"][0]))
                sibling["cell_id"] = "cell-002"
                sibling["params"]["comparison_id"] = "cell-002"
                sibling["params"][field] = invalid
                spec["cells"].append(sibling)
                spec_path.write_bytes(canonical_json_bytes(spec))
                result = self.invoke(
                    run_root,
                    metrics_path,
                    [sys.executable, "-c", "raise SystemExit(0)"],
                )

                self.assertEqual(result.returncode, 2)
                self.assertIn(field, result.stderr)
                self.assertFalse((run_root / "cells/cell-001").exists())

    def test_run_spec_symlink_outside_run_root_is_rejected(self) -> None:
        run_root, metrics_path = self.write_run_spec("2")
        outside = self.repo / "results" / "outside.json"
        outside.write_bytes((run_root / "run_spec.json").read_bytes())
        (run_root / "run_spec.json").unlink()
        (run_root / "run_spec.json").symlink_to(outside)
        result = self.invoke(
            run_root, metrics_path, [sys.executable, "-c", "raise SystemExit(0)"]
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("run_spec.json", result.stderr)
        self.assertFalse((run_root / "cells/cell-001").exists())

    def test_local_provenance_rejects_untracked_file_before_cell_creation(self) -> None:
        run_root, metrics_path = self.write_run_spec("2")
        (self.repo / "untracked.txt").write_text("dirty", encoding="utf-8")
        result = self.invoke(
            run_root, metrics_path, [sys.executable, "-c", "raise SystemExit(0)"]
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("clean including untracked", result.stderr)
        self.assertFalse((run_root / "cells/cell-001").exists())

    def test_matching_container_provenance_is_independent_of_local_worktree(self) -> None:
        run_root, metrics_path = self.write_run_spec("2")
        spec = json.loads((run_root / "run_spec.json").read_bytes())
        spec["provenance"]["image_sha256"] = "c" * 64
        (run_root / "run_spec.json").write_bytes(canonical_json_bytes(spec))
        provenance_path = run_root / "container-provenance.json"
        provenance_path.write_bytes(canonical_json_bytes(spec["provenance"]))
        (self.repo / "untracked.txt").write_text("container dirt is irrelevant", encoding="utf-8")
        result = self.invoke(
            run_root,
            metrics_path,
            [sys.executable, "-c", "raise SystemExit(19)"],
            container_provenance=provenance_path,
        )

        self.assertEqual(result.returncode, 19, result.stderr)

    def test_container_provenance_symlink_is_rejected(self) -> None:
        run_root, metrics_path = self.write_run_spec("2")
        spec = json.loads((run_root / "run_spec.json").read_bytes())
        spec["provenance"]["image_sha256"] = "c" * 64
        (run_root / "run_spec.json").write_bytes(canonical_json_bytes(spec))
        provenance_path = run_root / "container-provenance.json"
        provenance_path.write_bytes(canonical_json_bytes(spec["provenance"]))
        provenance_link = run_root / "container-provenance-link.json"
        provenance_link.symlink_to(provenance_path)
        result = self.invoke(
            run_root,
            metrics_path,
            [sys.executable, "-c", "raise SystemExit(19)"],
            container_provenance=provenance_link,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("regular file", result.stderr)
        self.assertFalse((run_root / "cells/cell-001").exists())

    def test_ru_maxrss_normalizes_darwin_bytes_and_linux_kib(self) -> None:
        self.assertEqual(runner._normalize_peak_memory_kib(123 * 1024, "Darwin"), 123)
        self.assertEqual(runner._normalize_peak_memory_kib(123, "Linux"), 123)

    def test_integer_timeout_has_canonical_decimal_elapsed_evidence(self) -> None:
        self.assertEqual(runner._canonical_timeout_elapsed("300"), "300.0")
        self.assertEqual(runner._canonical_timeout_elapsed("0.05"), "0.05")

    def test_child_launch_failure_still_writes_one_terminal_manifest(self) -> None:
        run_root, metrics_path = self.write_run_spec("2")
        result = self.invoke(
            run_root,
            metrics_path,
            [str(self.repo / "definitely-missing-executable")],
        )

        self.assertEqual(result.returncode, 127, result.stderr)
        _, manifest = self.read_manifest(run_root)
        self.assertEqual(manifest["status"], "NONZERO_EXIT")
        self.assertEqual(manifest["exit_code"], "127")
        self.assertEqual(manifest["timed_out"], "false")

    def test_valid_metrics_and_transitively_bound_artifacts_produce_success(self) -> None:
        run_root, metrics_path = self.write_run_spec("2")
        result = self.invoke(run_root, metrics_path, self.artifact_command())

        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_raw, manifest = self.read_manifest(run_root)
        artifact_raw = (run_root / "cells/cell-001/artifact.json").read_bytes()
        table_digest = hashlib.sha256(TABLE_BYTES).hexdigest()
        circuit_digest = hashlib.sha256(CIRCUIT_BYTES).hexdigest()
        self.assertEqual(manifest_raw, canonical_json_bytes(manifest))
        self.assertEqual(manifest["status"], "SUCCESS")
        self.assertEqual(manifest["train_exact"], "1.0")
        self.assertEqual(manifest["visible_cv_exact"], "0.75")
        self.assertEqual(manifest["visible_cv_bit_accuracy"], "0.875")
        self.assertEqual(manifest["gates"], "37")
        self.assertEqual(manifest["completed_table_sha256"], table_digest)
        self.assertEqual(manifest["circuit_sha256"], circuit_digest)
        self.assertEqual(manifest["artifact_path"], "cells/cell-001/artifact.json")
        self.assertEqual(manifest["artifact_sha256"], hashlib.sha256(artifact_raw).hexdigest())

    def test_missing_malformed_nonfinite_and_out_of_range_metrics_are_invalid(
        self,
    ) -> None:
        cases = {
            "missing-file": [sys.executable, "-c", "raise SystemExit(0)"],
            "malformed": self.artifact_command(raw_metrics=b"{not json}\n"),
            "missing-key": self.artifact_command(remove_metrics=("gates",)),
            "extra-key": self.artifact_command(metrics_updates={"bit_accuracy": 0.5}),
            "nan": self.artifact_command(metrics_updates={"visible_cv_exact": float("nan")}),
            "out-of-range": self.artifact_command(
                metrics_updates={"visible_cv_bit_accuracy": 1.01}
            ),
            "train-not-exact": self.artifact_command(
                metrics_updates={"train_exact": 0.999}
            ),
            "negative-gates": self.artifact_command(metrics_updates={"gates": -1}),
            "huge-integer": self.artifact_command(
                metrics_updates={"visible_cv_exact": 10**400}
            ),
        }
        for name, command in cases.items():
            with self.subTest(name=name):
                run_root, metrics_path = self.write_run_spec("2")
                result = self.invoke(run_root, metrics_path, command)
                self.assertEqual(result.returncode, 65, result.stderr)
                _, manifest = self.read_manifest(run_root)
                self.assertEqual(manifest["status"], "INVALID_METRICS")
                for field in runner.FAILED_QUALITY_FIELDS:
                    self.assertEqual(manifest[field], "none")

    def test_verifier_fail_and_not_run_have_distinct_terminal_codes(self) -> None:
        for verifier, status, code in (
            ("fail", "VERIFIER_FAILED", 66),
            ("not_run", "VERIFIER_NOT_RUN", 67),
        ):
            with self.subTest(verifier=verifier):
                run_root, metrics_path = self.write_run_spec("2")
                result = self.invoke(
                    run_root,
                    metrics_path,
                    self.artifact_command(metrics_updates={"verifier": verifier}),
                )
                self.assertEqual(result.returncode, code, result.stderr)
                _, manifest = self.read_manifest(run_root)
                self.assertEqual(manifest["status"], status)
                self.assertEqual(manifest["verifier"], verifier)
                for field in (
                    "train_exact",
                    "visible_cv_exact",
                    "visible_cv_bit_accuracy",
                    "gates",
                    "completed_table_sha256",
                    "circuit_sha256",
                    "artifact_sha256",
                    "artifact_path",
                ):
                    self.assertEqual(manifest[field], "none")

    def test_integer_digit_limit_metrics_terminalize_as_invalid(self) -> None:
        run_root, metrics_path = self.write_run_spec("2")
        table_digest = hashlib.sha256(TABLE_BYTES).hexdigest().encode()
        raw_metrics = (
            b'{"completed_table_sha256":"'
            + table_digest
            + b'","gates":37,"train_exact":1.0,"verifier":"pass",'
            + b'"visible_cv_bit_accuracy":0.875,"visible_cv_exact":'
            + b"9" * 5000
            + b"}\n"
        )
        result = self.invoke(
            run_root,
            metrics_path,
            self.artifact_command(raw_metrics=raw_metrics),
        )

        self.assertEqual(result.returncode, 65, result.stderr)
        _, manifest = self.read_manifest(run_root)
        self.assertEqual(manifest["status"], "INVALID_METRICS")
        self.assertEqual(manifest["exit_code"], "65")

    def test_invalid_artifact_binding_never_produces_success(self) -> None:
        table_digest = hashlib.sha256(TABLE_BYTES).hexdigest()
        cases = {
            "index-extra": self.artifact_command(artifact_updates={"extra": "no"}),
            "index-not-canonical": self.artifact_command(
                raw_artifact=b'{ "schema_version": 1 }\n'
            ),
            "equivalence-fail": self.artifact_command(
                artifact_updates={"equivalence": "fail"}
            ),
            "table-digest-mismatch": self.artifact_command(
                artifact_updates={"completed_table_sha256": "d" * 64}
            ),
            "metrics-table-digest-mismatch": self.artifact_command(
                metrics_updates={"completed_table_sha256": "d" * 64}
            ),
            "circuit-digest-mismatch": self.artifact_command(
                artifact_updates={"circuit_sha256": "e" * 64}
            ),
            "bit-accuracy-alias": self.artifact_command(
                metrics_updates={"bit_accuracy": 0.875},
                remove_metrics=("visible_cv_bit_accuracy",),
            ),
            "symlink": self.artifact_command(symlink="circuit.txt"),
            "wrong-table-path": self.artifact_command(
                artifact_updates={"completed_table_path": "other.csv"}
            ),
        }
        self.assertEqual(len(table_digest), 64)
        for name, command in cases.items():
            with self.subTest(name=name):
                run_root, metrics_path = self.write_run_spec("2")
                result = self.invoke(run_root, metrics_path, command)
                self.assertEqual(result.returncode, 65, result.stderr)
                _, manifest = self.read_manifest(run_root)
                self.assertEqual(manifest["status"], "INVALID_METRICS")

    def test_manifest_contains_no_environment_values_or_log_contents(self) -> None:
        run_root, metrics_path = self.write_run_spec("2")
        secret = "sealed-value-must-not-enter-manifest"
        environment = dict(os.environ)
        environment["SYNTHETIC_SECRET"] = secret
        command = [
            sys.executable,
            "-c",
            "import os,sys;print(os.environ['SYNTHETIC_SECRET']);"
            "print(os.environ['SYNTHETIC_SECRET'],file=sys.stderr);sys.exit(9)",
        ]
        result = self.invoke(
            run_root, metrics_path, command, environment=environment
        )

        self.assertEqual(result.returncode, 9, result.stderr)
        raw, manifest = self.read_manifest(run_root)
        self.assertNotIn(secret.encode(), raw)
        self.assertFalse(any("env" in key.lower() for key in manifest))


if __name__ == "__main__":
    unittest.main()
