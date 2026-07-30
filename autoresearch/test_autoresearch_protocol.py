from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path


AUTORESEARCH = Path(__file__).parent
REPO_ROOT = AUTORESEARCH.parent
LOG_TEMPLATE = AUTORESEARCH / "LOG_TEMPLATE.md"
README = AUTORESEARCH / "README.md"
FORBIDDEN = {
    "family",
    "generator",
    "ground_truth",
    "test_outputs",
}


def nested_json_keys(value: object) -> list[str]:
    if isinstance(value, dict):
        return [
            str(key)
            for key, child in value.items()
            for key in (key,)
        ] + [
            nested
            for child in value.values()
            for nested in nested_json_keys(child)
        ]
    if isinstance(value, list):
        return [nested for child in value for nested in nested_json_keys(child)]
    return []


def bundle_violations(root: Path, sealed_digest: str) -> list[str]:
    violations: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        lowered_path = relative.lower()
        if any(token in lowered_path for token in FORBIDDEN) or sealed_digest in relative:
            violations.append(f"path:{relative}")
        if not path.is_file():
            continue
        if path.suffix == ".csv":
            with path.open(newline="", encoding="utf-8") as stream:
                header = next(csv.reader(stream), [])
            for field in header:
                lowered = field.lower()
                if any(token in lowered for token in FORBIDDEN) or sealed_digest in field:
                    violations.append(f"header:{relative}:{field}")
        elif path.suffix == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
            for key in nested_json_keys(value):
                lowered = key.lower()
                if any(token in lowered for token in FORBIDDEN) or sealed_digest in key:
                    violations.append(f"json-key:{relative}:{key}")
    return violations


class AutoresearchProtocolTests(unittest.TestCase):
    def test_log_template_has_exact_required_headings(self) -> None:
        headings = [
            line
            for line in LOG_TEMPLATE.read_text(encoding="utf-8").splitlines()
            if line.startswith("#")
        ]
        self.assertEqual(
            headings,
            [
                "# Experiment <opaque-id>",
                "## Hypothesis",
                "## Parent commit and diff digest",
                "## Permitted data",
                "## Command, seed, and environment",
                "## Hardware and five-minute cap",
                "## Result: accuracy, gates, runtime, memory, verifier",
                "## Failure signal and interpretation",
                "## Next pivot",
            ],
        )

    def test_readme_binds_worktree_and_three_role_firewall(self) -> None:
        text = README.read_text(encoding="utf-8")
        required = (
            'git worktree add "../booleanrazor-exp-${experiment_id}"',
            '-b "codex/booleanrazor-exp-${experiment_id}" "$accepted_commit"',
            "autoresearch/LOG_TEMPLATE.md",
            '"../booleanrazor-exp-${experiment_id}/LOG.md"',
            "custodian",
            "proposer",
            "evaluator",
            "experiment_id",
            "train exact accuracy",
            "sealed exact accuracy",
            "bit accuracy",
            "reachable gates",
            "elapsed time",
            "peak memory",
            "terminal status",
            "separate evidence commit",
        )
        for phrase in required:
            self.assertIn(phrase, text)

    def test_navigation_documents_route_evidence_and_verifier_work(self) -> None:
        required = {
            "AGENTS.md": (
                "Current answer",
                "Choose the activity",
                "Choose the evidence track",
                "Verification ladder",
                "Promotion state machine",
                "VERIFIER_NOT_RUN",
                "absolute paths",
                "make report-check",
            ),
            "README.md": (
                "reports/site/index.html",
                "Internal exhaustive equivalence",
                "Official Julia verification",
                "Blind advantage has not been demonstrated",
            ),
            "autoresearch/README.md": (
                "autoresearch/LOG_TEMPLATE.md",
                "child runs in its cell directory",
                "absolute",
            ),
            "reblind/README.md": (
                "learn-care",
                "record-verification.py",
                "freeze_candidate",
                "promote_blind_result",
            ),
        }
        for relative, phrases in required.items():
            text = (REPO_ROOT / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(path=relative, phrase=phrase):
                    self.assertIn(phrase, text)

        active_examples = "\n".join(
            (REPO_ROOT / relative).read_text(encoding="utf-8")
            for relative in (
                "AGENTS.md",
                "README.md",
                "autoresearch/README.md",
                "reblind/README.md",
            )
        )
        self.assertNotIn(
            "tracks/qcs/solutions/hmyuuu/autoresearch/LOG_TEMPLATE.md",
            active_examples,
        )
        self.assertNotIn("--experiment-id", active_examples)
        self.assertNotIn("--results-root", active_examples)

    def test_recursive_bundle_scan_rejects_forbidden_metadata_surfaces(self) -> None:
        sealed_digest = "f" * 64
        temporary = tempfile.TemporaryDirectory(prefix="task10-firewall-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        safe = root / "safe"
        safe.mkdir()
        (safe / "rows.csv").write_text("opaque_id,input\nx,0\n", encoding="utf-8")
        (safe / "config.json").write_text(
            json.dumps({"method": {"version": 1}}), encoding="utf-8"
        )
        self.assertEqual(bundle_violations(safe, sealed_digest), [])

        cases = {
            "forbidden-path": ("family/rows.txt", "plain"),
            "forbidden-header": ("rows.csv", "opaque_id,ground_truth\nx,0\n"),
            "forbidden-json-key": (
                "config.json",
                json.dumps({"nested": [{"test_outputs": "hidden"}]}),
            ),
            "sealed-digest-path": (f"{sealed_digest}.txt", "plain"),
        }
        for name, (relative, content) in cases.items():
            with self.subTest(name=name):
                case = root / name
                path = case / relative
                path.parent.mkdir(parents=True)
                path.write_text(content, encoding="utf-8")
                self.assertTrue(bundle_violations(case, sealed_digest))


if __name__ == "__main__":
    unittest.main()
