from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
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


report_model = load_module("report_model", "report_model.py")


def canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def path_evidence(locator: str = "evidence/base.md") -> dict[str, str]:
    return {
        "kind": "path",
        "label": "tracked evidence",
        "locator": locator,
        "revision": "main",
    }


def commit_evidence(
    revision: str = "0123456789abcdef0123456789abcdef01234567",
) -> dict[str, str]:
    return {
        "kind": "commit",
        "label": "historical evidence",
        "locator": "LOG.md",
        "revision": revision,
    }


def valid_project() -> dict[str, object]:
    controls = []
    for suffix, instance, function, gates in (
        ("a", "mystery-A", "x+y", 37),
        ("b", "mystery-B", "abs(x-y)", 49),
        ("c", "mystery-C", "x*y", 168),
        ("d", "mystery-D", "x²+y²", 127),
    ):
        controls.append(
            {
                "control_id": f"control-{suffix}",
                "evidence": [path_evidence()],
                "function": function,
                "gates": gates,
                "instance": instance,
                "limitation": "Disclosed control only; not blind evidence or a minimality proof.",
                "status": "verified_main",
            }
        )
    return {
        "claims": [
            {
                "claim_id": "blind-advantage",
                "evidence": [path_evidence()],
                "limitations": ["Public and sealed evaluations have not run."],
                "missing_proof": ["Frozen visible and sealed results."],
                "status": "blocked",
                "summary": "Blind advantage has not been demonstrated.",
                "track": "blind_visible",
            }
        ],
        "commands": [
            {
                "command": "make test",
                "command_id": "test",
                "scope": "Run the local verification suite.",
                "title": "Test",
            }
        ],
        "controls": controls,
        "experiments": [
            {
                "decision": "Retain as exact disclosed-control evidence.",
                "evidence": [path_evidence()],
                "experiment_id": "controls",
                "limitations": [],
                "location": "tests/official_v1.rs",
                "outcome": "All disclosed truth tables are exhaustively equivalent.",
                "status": "verified_main",
                "title": "Disclosed controls",
                "track": "disclosed_control",
            }
        ],
        "external_references": [
            {
                "reference_id": "information-architecture",
                "title": "Historical report structure",
                "url": "https://example.com/reference",
                "use": "Information-architecture reference only.",
            }
        ],
        "methods": [
            {
                "evidence": [path_evidence()],
                "insights": ["Exact equivalence and official verification are separate layers."],
                "limitations": [],
                "method_id": "exact-core",
                "optimization": ["Preserve accuracy before minimizing gates."],
                "scope": "Disclosed controls and synthetic fixtures.",
                "status": "verified_main",
                "stop_rules": ["Stop on any loss of exactness."],
                "summary": "Canonical exact Boolean-circuit core.",
                "title": "Exact core",
            }
        ],
        "project": {
            "conclusion": "Blind advantage has not been demonstrated.",
            "next_gate": "Run the frozen public study before sealed access.",
            "purpose": "Separate constructive controls from blind-learning evidence.",
            "title": "BooleanRazor",
        },
        "schema_version": 1,
        "verification_layers": [
            {
                "authority": "Rust exhaustive evaluation",
                "command": "make test",
                "current_state": "implemented",
                "layer_id": "internal-equivalence",
                "meaning": "Exhaustive equivalence of the completed table and emitted circuit.",
                "title": "Internal equivalence",
            }
        ],
    }


@pytest.fixture
def project_repo(tmp_path: Path) -> tuple[Path, dict[str, object], Path]:
    root = tmp_path / "repo"
    (root / "evidence").mkdir(parents=True)
    (root / "evidence/base.md").write_text("evidence\n", encoding="utf-8")
    git(root.parent, "init", "-q", str(root))
    git(root, "add", "evidence/base.md")
    project = valid_project()
    source = root / "project.json"
    source.write_bytes(canonical(project))
    return root, project, source


def write_source(source: Path, project: object) -> None:
    source.write_bytes(canonical(project))


def official_record(**updates: object) -> dict[str, object]:
    version_text = "julia version 1.10.9"
    record: dict[str, object] = {
        "bit_accuracy": "1.0",
        "circuit_sha256": "a" * 64,
        "comparison_id": "candidate-r0",
        "dataset_sha256": "b" * 64,
        "exact_accuracy": "1.0",
        "gates": 7,
        "julia_version": {
            "sha256": hashlib.sha256(
                (version_text + "\n").encode("ascii")
            ).hexdigest(),
            "text": version_text,
        },
        "manifest_sha256": "d" * 64,
        "run_spec_sha256": "e" * 64,
        "samples": 16,
        "schema_version": 1,
        "status": "pass",
        "verify_jl_sha256": "f" * 64,
    }
    record.update(updates)
    return record


def sealed_decision(**updates: object) -> dict[str, object]:
    decision: dict[str, object] = {
        "decision": "promote_blind_result",
        "highest_legal_next_step": "promote_blind_result",
        "input_sha256": {
            "external_trust_policy": "1" * 64,
            "promotion-request.json": "2" * 64,
        },
        "reasons": [],
        "schema_version": 1,
        "track": "sealed_confirmation",
    }
    decision.update(updates)
    return decision


def add_path(root: Path, project: dict[str, object], name: str, value: object) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))
    git(root, "add", name)
    claim = project["claims"][0]
    assert isinstance(claim, dict)
    claim["evidence"] = [path_evidence(name)]


INVALID_CASES = (
    ("missing-project-key", "exact keys"),
    ("duplicate-method-id", "duplicate method_id"),
    ("unknown-track", "invalid track"),
    ("unknown-status", "invalid status"),
    ("wrong-control-count", "mystery-A must use 37 gates"),
    ("missing-limitation", "limitation must not be empty"),
    ("unsafe-url", "https URL"),
    ("short-commit", "40 lowercase hex"),
    ("missing-path", "tracked evidence path"),
    ("duplicate-json-key", "duplicate JSON key"),
    ("forbidden-proposer-key", "forbidden proposer-facing key"),
    ("blind-success-without-sealed-proof", "sealed promotion decision"),
    ("official-pass-without-record", "official-verification.json"),
)


@pytest.mark.parametrize(("case", "fragment"), INVALID_CASES)
def test_invalid_project_cases(
    project_repo: tuple[Path, dict[str, object], Path],
    case: str,
    fragment: str,
) -> None:
    root, base, source = project_repo
    project = copy.deepcopy(base)
    if case == "missing-project-key":
        del project["project"]["purpose"]
    elif case == "duplicate-method-id":
        project["methods"].append(copy.deepcopy(project["methods"][0]))
    elif case == "unknown-track":
        project["claims"][0]["track"] = "leaked"
    elif case == "unknown-status":
        project["methods"][0]["status"] = "probably"
    elif case == "wrong-control-count":
        project["controls"][0]["gates"] = 38
    elif case == "missing-limitation":
        project["claims"][0]["limitations"] = []
    elif case == "unsafe-url":
        project["external_references"][0]["url"] = "http://example.com/reference"
    elif case == "short-commit":
        project["methods"][0]["status"] = "verified_branch_only"
        project["methods"][0]["limitations"] = ["Historical branch only."]
        project["methods"][0]["evidence"] = [commit_evidence("a" * 39)]
    elif case == "missing-path":
        project["methods"][0]["evidence"] = [path_evidence("evidence/missing.md")]
    elif case == "duplicate-json-key":
        source.write_bytes(
            b'{"schema_version":1,"schema_version":1,"project":{}}\n'
        )
    elif case == "forbidden-proposer-key":
        project["project"]["source_family"] = "private-generator"
    elif case == "blind-success-without-sealed-proof":
        project["claims"][0]["track"] = "sealed_confirmation"
        project["claims"][0]["status"] = "verified_main"
        project["claims"][0]["limitations"] = []
        project["claims"][0]["missing_proof"] = []
    elif case == "official-pass-without-record":
        project["claims"][0]["status"] = "verified_main"
        project["claims"][0]["track"] = "disclosed_control"
        project["claims"][0]["limitations"] = []
        project["claims"][0]["missing_proof"] = []
        project["claims"][0]["evidence"] = [
            path_evidence("evidence/official-verification.json")
        ]
    else:
        raise AssertionError(case)

    if case != "duplicate-json-key":
        write_source(source, project)
    with pytest.raises(report_model.ModelError, match=fragment):
        report_model.load_project(source, root)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_loader_rejects_nonfinite_constants(
    project_repo: tuple[Path, dict[str, object], Path], constant: str
) -> None:
    root, _, source = project_repo
    source.write_bytes(('{"schema_version":' + constant + "}\n").encode())
    with pytest.raises(report_model.ModelError, match="finite"):
        report_model.load_project(source, root)


def test_loader_rejects_nested_duplicate_keys(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, _, source = project_repo
    source.write_bytes(
        b'{"project":{"title":"first","title":"second"},"schema_version":1}\n'
    )
    with pytest.raises(report_model.ModelError, match="duplicate JSON key"):
        report_model.load_project(source, root)


def test_loader_is_canonical_and_preserves_literal_content(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    literal = '<script>alert("evidence")</script>'
    project["project"]["conclusion"] = literal
    write_source(source, project)
    loaded, digest = report_model.load_project(source, root)
    assert loaded["project"]["conclusion"] == literal
    assert digest == hashlib.sha256(source.read_bytes()).hexdigest()

    source.write_bytes(json.dumps(project, ensure_ascii=False).encode() + b"\n")
    with pytest.raises(report_model.ModelError, match="canonical JSON"):
        report_model.load_project(source, root)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("schema_version", True),
        ("gates", True),
        ("samples", False),
        ("samples", 0),
        ("exact_accuracy", 1.0),
        ("bit_accuracy", "0.999"),
        ("circuit_sha256", "A" * 64),
        ("comparison_id", ""),
        ("status", "not_run"),
        ("julia_version", {"sha256": "c" * 64, "text": ""}),
        ("julia_version", {"sha256": "c" * 64, "text": "ok", "extra": "x"}),
    ),
)
def test_official_record_requires_exact_task3_schema_and_types(
    project_repo: tuple[Path, dict[str, object], Path],
    field: str,
    value: object,
) -> None:
    root, project, source = project_repo
    add_path(
        root,
        project,
        "evidence/official-verification.json",
        official_record(**{field: value}),
    )
    project["claims"][0].update(
        {
            "limitations": [],
            "missing_proof": [],
            "status": "verified_main",
            "track": "disclosed_control",
        }
    )
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match="official-verification.json"):
        report_model.load_project(source, root)


def test_forged_minimal_official_record_is_not_proof(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    add_path(
        root,
        project,
        "evidence/official-verification.json",
        {"status": "pass"},
    )
    project["claims"][0].update(
        {
            "limitations": [],
            "missing_proof": [],
            "status": "verified_main",
            "track": "disclosed_control",
        }
    )
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match="exact keys"):
        report_model.load_project(source, root)


def test_official_julia_version_digest_binds_the_exact_lf_terminated_text(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    add_path(
        root,
        project,
        "evidence/official-verification.json",
        official_record(
            julia_version={
                "sha256": "0" * 64,
                "text": "julia version 1.10.9",
            }
        ),
    )
    project["claims"][0].update(
        {
            "limitations": [],
            "missing_proof": [],
            "status": "verified_main",
            "track": "disclosed_control",
        }
    )
    write_source(source, project)
    with pytest.raises(
        report_model.ModelError,
        match="julia_version.sha256 must bind LF-terminated text",
    ):
        report_model.load_project(source, root)


def test_valid_official_record_is_accepted(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    add_path(
        root,
        project,
        "evidence/official-verification.json",
        official_record(),
    )
    project["claims"][0].update(
        {
            "limitations": [],
            "missing_proof": [],
            "status": "verified_main",
            "track": "disclosed_control",
        }
    )
    write_source(source, project)
    loaded, _ = report_model.load_project(source, root)
    assert loaded["claims"][0]["status"] == "verified_main"


@pytest.mark.parametrize(
    ("updates", "fragment"),
    (
        ({"schema_version": True}, "sealed promotion decision"),
        ({"track": "blind_visible"}, "sealed promotion decision"),
        ({"decision": "blocked"}, "sealed promotion decision"),
        ({"highest_legal_next_step": "freeze_candidate"}, "sealed promotion decision"),
        ({"reasons": ["missing_comparison_cell"]}, "sealed promotion decision"),
        ({"input_sha256": {}}, "sealed promotion decision"),
        (
            {"input_sha256": {"promotion-request.json": "1" * 64}},
            "sealed promotion decision",
        ),
        ({"input_sha256": {"request.json": True}}, "sealed promotion decision"),
    ),
)
def test_sealed_success_requires_exact_positive_task4_decision(
    project_repo: tuple[Path, dict[str, object], Path],
    updates: dict[str, object],
    fragment: str,
) -> None:
    root, project, source = project_repo
    add_path(
        root,
        project,
        "evidence/promotion-decision.json",
        sealed_decision(**updates),
    )
    project["claims"][0].update(
        {
            "limitations": [],
            "missing_proof": [],
            "status": "verified_main",
            "track": "sealed_confirmation",
        }
    )
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match=fragment):
        report_model.load_project(source, root)


def test_valid_sealed_decision_is_accepted(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    add_path(
        root,
        project,
        "evidence/promotion-decision.json",
        sealed_decision(),
    )
    project["claims"][0].update(
        {
            "limitations": [],
            "missing_proof": [],
            "status": "verified_main",
            "track": "sealed_confirmation",
        }
    )
    write_source(source, project)
    report_model.load_project(source, root)


def test_blocked_claim_may_cite_a_canonical_blocked_promotion_decision(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    blocked = sealed_decision(
        decision="blocked",
        highest_legal_next_step="freeze_candidate",
        input_sha256={"CURRENT_PROMOTION_REQUEST.json": "2" * 64},
        reasons=["candidate_evidence_absent"],
        track="blind_visible",
    )
    add_path(
        root,
        project,
        "evidence/CURRENT_PROMOTION_DECISION.json",
        blocked,
    )
    write_source(source, project)
    loaded, _ = report_model.load_project(source, root)
    assert loaded["claims"][0]["status"] == "blocked"


@pytest.mark.parametrize(
    "locator",
    (
        "../outside.md",
        "/tmp/outside.md",
        "-leading.md",
        "evidence/./base.md",
        "evidence//base.md",
        "evidence\\base.md",
    ),
)
def test_path_evidence_rejects_lexically_unsafe_locator(
    project_repo: tuple[Path, dict[str, object], Path], locator: str
) -> None:
    root, project, source = project_repo
    project["methods"][0]["evidence"] = [path_evidence(locator)]
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match="safe repo-relative POSIX path"):
        report_model.load_project(source, root)


def test_path_evidence_rejects_symlink_untracked_and_nonregular(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    (root / "evidence/link.md").symlink_to("base.md")
    git(root, "add", "evidence/link.md")
    project["methods"][0]["evidence"] = [path_evidence("evidence/link.md")]
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match="symlink"):
        report_model.load_project(source, root)

    (root / "evidence/untracked.md").write_text("untracked\n", encoding="utf-8")
    project["methods"][0]["evidence"] = [path_evidence("evidence/untracked.md")]
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match="tracked evidence path"):
        report_model.load_project(source, root)

    (root / "evidence/directory").mkdir()
    project["methods"][0]["evidence"] = [path_evidence("evidence/directory")]
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match="regular file"):
        report_model.load_project(source, root)


def test_verified_branch_only_requires_commit_and_limitation(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    project["methods"][0]["status"] = "verified_branch_only"
    project["methods"][0]["limitations"] = ["Historical branch only."]
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match="full-SHA commit evidence"):
        report_model.load_project(source, root)

    project["methods"][0]["evidence"].append(commit_evidence())
    write_source(source, project)
    loaded, _ = report_model.load_project(source, root)
    assert loaded["methods"][0]["status"] == "verified_branch_only"


def test_validate_project_returns_sorted_unique_errors(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, _ = project_repo
    project["claims"][0]["status"] = "bad"
    project["experiments"][0]["status"] = "bad"
    errors = report_model.validate_project(project, root)
    assert errors == sorted(set(errors))
    assert sum("invalid status" in error for error in errors) == 2


def test_renderer_escapes_html_attributes_and_markdown_table_link_syntax() -> None:
    project = valid_project()
    project["project"]["conclusion"] = (
        '\"><img src="https://attacker.invalid/x" onerror="alert(1)">'
    )
    project["methods"][0]["title"] = "<b>unsafe | [label](target)</b>"
    project["methods"][0]["evidence"][0].update(
        {
            "label": 'bad" onclick="alert(2)',
            "locator": 'evidence/x" onclick="alert(3).md',
        }
    )
    project["claims"][0]["evidence"][0]["label"] = (
        'bad" onclick="alert(4) | [proof](fake)'
    )

    outputs = report_model.render_outputs(project, "a" * 64, "b" * 64)
    index = outputs["reports/site/index.html"]
    assert b'<img src="https://attacker.invalid/x"' not in index
    assert b"&lt;img src=&quot;https://attacker.invalid/x&quot;" in index

    methods = outputs["docs/METHODS.md"]
    assert b"<b>unsafe" not in methods
    assert b"\\|" in methods
    assert b"\\[label\\]\\(target\\)" in methods
    methods_html = outputs["reports/site/methods.html"]
    assert b' onclick="alert(2)' not in methods_html
    assert b' onclick="alert(3)' not in methods_html
    assert b"x%22%20onclick%3D%22alert%283%29.md" in methods_html

    ledger = outputs["research/EVIDENCE_LEDGER.md"]
    assert b'onclick="alert(4)' not in ledger
    assert b"\\|" in ledger
    assert b"\\[proof\\]\\(fake\\)" in ledger
