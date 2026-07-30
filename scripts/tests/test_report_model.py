from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

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


def task4_canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
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


def empty_claim_proof(**updates: str) -> dict[str, str]:
    proof = {
        "official_record": "none",
        "promotion_decision": "none",
        "promotion_request": "none",
        "trust_policy": "none",
    }
    proof.update(updates)
    return proof


def commit_evidence(
    revision: str = "0123456789abcdef0123456789abcdef01234567",
) -> dict[str, str]:
    return {
        "kind": "commit",
        "label": "historical evidence",
        "locator": "LOG.md",
        "revision": revision,
    }


def research_round(
    *,
    round_id: str = "R01",
    parent_round_ids: list[str] | None = None,
    round_index: int = 1,
    revision: str = "0123456789abcdef0123456789abcdef01234567",
    status: str = "verified_main",
    turning_point: bool = True,
) -> dict[str, object]:
    result_evidence = commit_evidence(revision) | {
        "locator": "evidence/base.md"
    }
    evidence = (
        [path_evidence(), result_evidence]
        if status == "verified_main"
        else [result_evidence]
    )
    return {
        "base_revision": revision,
        "branch": "main" if status == "verified_main" else "research/round",
        "decision": "Retain the exact result and preserve its limitations.",
        "evidence": evidence,
        "frozen_controls": ["Accuracy before gate count."],
        "hypothesis": "The exact learner can recover the frozen synthetic fixture.",
        "independent_variable": "Learner configuration.",
        "insight": "Exactness and gate count must be reported separately.",
        "limitations": ["Synthetic fixture only; no public or sealed evaluation."],
        "next_pivot": "Test the next frozen hypothesis without changing the benchmark.",
        "outcome": "The recorded run completed under the frozen controls.",
        "parent_round_ids": [] if parent_round_ids is None else parent_round_ids,
        "permitted_data": ["Tracked synthetic fixtures only."],
        "result_revision": revision,
        "round_id": round_id,
        "round_index": round_index,
        "runs": [
            {
                "classification": "exact synthetic result",
                "evidence": evidence,
                "outcome": "Completed with exact internal equivalence.",
                "run_id": f"{round_id.lower()}-run-01",
                "status": "successful",
            }
        ],
        "status": status,
        "title": "Exact synthetic control",
        "track": "synthetic",
        "turning_point": turning_point,
    }


def valid_project(
    revision: str = "0123456789abcdef0123456789abcdef01234567",
) -> dict[str, object]:
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
                "claim_kind": "blind_advantage",
                "evidence": [path_evidence()],
                "limitations": ["Public and sealed evaluations have not run."],
                "missing_proof": ["Frozen visible and sealed results."],
                "proof": empty_claim_proof(),
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
            "synthetic_frontier_round_id": "R01",
            "title": "BooleanRazor",
        },
        "research_rounds": [research_round(revision=revision)],
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
    git(
        root,
        "-c",
        "user.name=BooleanRazor Tests",
        "-c",
        "user.email=tests@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        "fixture evidence",
    )
    revision = git(root, "rev-parse", "HEAD").stdout.strip()
    project = valid_project(revision)
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
    git(
        root,
        "-c",
        "user.name=BooleanRazor Tests",
        "-c",
        "user.email=tests@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        f"add {name}",
    )
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
        project["claims"][0]["claim_kind"] = "sealed_promotion"
        project["claims"][0]["track"] = "sealed_confirmation"
        project["claims"][0]["status"] = "verified_main"
        project["claims"][0]["limitations"] = []
        project["claims"][0]["missing_proof"] = []
    elif case == "official-pass-without-record":
        project["claims"][0]["claim_kind"] = "official_verifier_pass"
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
            "claim_kind": "official_verifier_pass",
            "limitations": [],
            "missing_proof": [],
            "proof": empty_claim_proof(
                official_record="evidence/official-verification.json"
            ),
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
            "claim_kind": "official_verifier_pass",
            "limitations": [],
            "missing_proof": [],
            "proof": empty_claim_proof(
                official_record="evidence/official-verification.json"
            ),
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
            "claim_kind": "official_verifier_pass",
            "limitations": [],
            "missing_proof": [],
            "proof": empty_claim_proof(
                official_record="evidence/official-verification.json"
            ),
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


def test_shape_valid_official_record_without_replayable_package_is_rejected(
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
            "claim_kind": "official_verifier_pass",
            "limitations": [],
            "missing_proof": [],
            "proof": empty_claim_proof(
                official_record="evidence/official-verification.json"
            ),
            "status": "verified_main",
            "track": "disclosed_control",
        }
    )
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match="replayable promotion proof"):
        report_model.load_project(source, root)


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
            "claim_kind": "sealed_promotion",
            "limitations": [],
            "missing_proof": [],
            "proof": empty_claim_proof(
                promotion_decision="evidence/promotion-decision.json"
            ),
            "status": "verified_main",
            "track": "sealed_confirmation",
        }
    )
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match=fragment):
        report_model.load_project(source, root)


def test_shape_valid_sealed_decision_is_not_a_public_report_attestation(
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
            "claim_kind": "sealed_promotion",
            "limitations": [],
            "missing_proof": [],
            "proof": empty_claim_proof(
                promotion_decision="evidence/promotion-decision.json"
            ),
            "status": "verified_main",
            "track": "sealed_confirmation",
        }
    )
    write_source(source, project)
    with pytest.raises(
        report_model.ModelError,
        match="sanitized authenticated attestation",
    ):
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
    git(
        root,
        "-c",
        "user.name=BooleanRazor Tests",
        "-c",
        "user.email=tests@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        "symlink fixture",
    )
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
    with pytest.raises(report_model.ModelError, match="HEAD-tracked evidence path"):
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

    revision = git(root, "rev-parse", "HEAD").stdout.strip()
    project["methods"][0]["evidence"].append(
        commit_evidence(revision) | {"locator": "evidence/base.md"}
    )
    write_source(source, project)
    loaded, _ = report_model.load_project(source, root)
    assert loaded["methods"][0]["status"] == "verified_branch_only"


def test_branch_only_official_claim_rejects_arbitrary_commit_evidence(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    revision = git(root, "rev-parse", "HEAD").stdout.strip()
    project["claims"][0].update(
        {
            "claim_kind": "historical_disclosed_julia_pass",
            "evidence": [
                commit_evidence(revision)
                | {"locator": "evidence/base.md"}
            ],
            "limitations": [
                "Historical disclosed-control verification only."
            ],
            "missing_proof": [],
            "status": "verified_branch_only",
            "track": "disclosed_control",
        }
    )
    write_source(source, project)

    with pytest.raises(
        report_model.ModelError,
        match="ratified historical official provenance",
    ):
        report_model.load_project(source, root)


def test_branch_only_official_claim_accepts_only_closed_historical_binding(
    project_repo: tuple[Path, dict[str, object], Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, project, source = project_repo
    revision = git(root, "rev-parse", "HEAD").stdout.strip()
    digest = hashlib.sha256((root / "evidence/base.md").read_bytes()).hexdigest()
    monkeypatch.setattr(
        report_model,
        "HISTORICAL_OFFICIAL_PROOFS",
        {
            ("disclosed_control", "verified_branch_only"): {
                (revision, "evidence/base.md"): digest,
            }
        },
        raising=False,
    )
    project["claims"][0].update(
        {
            "claim_kind": "historical_disclosed_julia_pass",
            "evidence": [
                commit_evidence(revision)
                | {"locator": "evidence/base.md"}
            ],
            "limitations": [
                "Historical disclosed-control verification only."
            ],
            "missing_proof": [],
            "status": "verified_branch_only",
            "track": "disclosed_control",
        }
    )
    write_source(source, project)

    loaded, _ = report_model.load_project(source, root)
    assert loaded["claims"][0]["status"] == "verified_branch_only"
    outputs = report_model.render_outputs(loaded, "a" * 64, "b" * 64)
    assert (
        b"not a fresh current-HEAD official verification or blind-learning evidence"
        in outputs["research/EVIDENCE_LEDGER.md"]
    )


def test_historical_official_claim_with_malformed_track_returns_diagnostics(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    project["claims"][0].update(
        {
            "claim_kind": "historical_disclosed_julia_pass",
            "status": "verified_branch_only",
            "track": [],
        }
    )
    write_source(source, project)

    with pytest.raises(report_model.ModelError, match="invalid track"):
        report_model.load_project(source, root)


def test_claim_policy_rejects_unknown_kind_and_track_status_mismatch(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    project["claims"][0].update(
        {
            "claim_id": "anything-the-author-wants",
            "claim_kind": "made_up_scientific_result",
            "limitations": [],
            "missing_proof": [],
            "status": "verified_main",
            "summary": "Official verifier pass proves a promoted blind result.",
            "track": "blind_visible",
        }
    )
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match="unknown claim_kind"):
        report_model.load_project(source, root)

    project["claims"][0].update(
        {
            "claim_kind": "blind_advantage",
            "status": "verified_main",
            "track": "blind_visible",
        }
    )
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match="claim policy"):
        report_model.load_project(source, root)


def test_authoritative_claim_rendering_ignores_author_narrative(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    overstatement = "Official pass proves a promoted sealed blind result."
    project["project"]["conclusion"] = overstatement
    project["claims"][0]["summary"] = overstatement
    write_source(source, project)
    loaded, _ = report_model.load_project(source, root)

    outputs = report_model.render_outputs(loaded, "a" * 64, "b" * 64)
    assert overstatement.encode() not in outputs["reports/site/index.html"]
    assert overstatement.encode() not in outputs["research/EVIDENCE_LEDGER.md"]
    assert b"Blind advantage has not been demonstrated." in outputs[
        "reports/site/index.html"
    ]
    assert b"Blind advantage has not been demonstrated." in outputs[
        "research/EVIDENCE_LEDGER.md"
    ]


def test_verified_main_requires_current_head_bound_path_evidence(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    project["methods"][0]["evidence"] = [
        {
            "kind": "command",
            "label": "command only",
            "locator": "make test",
            "revision": "none",
        }
    ]
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match="HEAD-bound path evidence"):
        report_model.load_project(source, root)


def test_main_path_evidence_must_match_the_head_blob(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    (root / "evidence/base.md").write_text("modified after HEAD\n", encoding="utf-8")
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match="match the HEAD blob"):
        report_model.load_project(source, root)


def test_main_path_evidence_checks_head_blob_size_before_materializing(
    project_repo: tuple[Path, dict[str, object], Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, source = project_repo
    monkeypatch.setattr(report_model, "MAX_SOURCE_BYTES", 4)
    with pytest.raises(report_model.ModelError, match="HEAD blob must not exceed 4"):
        report_model.load_project(source, root)


def test_git_replace_cannot_forge_head_path_evidence(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    original = git(root, "rev-parse", "HEAD").stdout.strip()
    (root / "evidence/base.md").write_text("forged replacement\n", encoding="utf-8")
    git(root, "add", "evidence/base.md")
    git(
        root,
        "-c",
        "user.name=BooleanRazor Tests",
        "-c",
        "user.email=tests@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        "forged replacement",
    )
    forged = git(root, "rev-parse", "HEAD").stdout.strip()
    git(root, "update-ref", "HEAD", original)
    git(root, "replace", original, forged)
    assert (
        git(root, "show", "HEAD:evidence/base.md").stdout
        == "forged replacement\n"
    )
    write_source(source, project)

    with pytest.raises(report_model.ModelError, match="match the HEAD blob"):
        report_model.load_project(source, root)


def test_inherited_git_dir_cannot_redirect_evidence_queries(
    project_repo: tuple[Path, dict[str, object], Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, source = project_repo
    attacker = tmp_path / "attacker"
    attacker.mkdir()
    git(attacker.parent, "init", "-q", str(attacker))
    (attacker / "unrelated.txt").write_text("unrelated\n", encoding="utf-8")
    git(attacker, "add", "unrelated.txt")
    git(
        attacker,
        "-c",
        "user.name=BooleanRazor Tests",
        "-c",
        "user.email=tests@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        "attacker repository",
    )
    monkeypatch.setenv("GIT_DIR", str(attacker / ".git"))

    loaded, _ = report_model.load_project(source, root)
    assert loaded["schema_version"] == 1


def test_staged_only_path_is_not_mainline_evidence(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    (root / "evidence/staged.md").write_text("staged only\n", encoding="utf-8")
    git(root, "add", "evidence/staged.md")
    project["methods"][0]["evidence"] = [path_evidence("evidence/staged.md")]
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match="HEAD-tracked evidence path"):
        report_model.load_project(source, root)


def test_commit_evidence_requires_existing_commit_and_blob(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    project["methods"][0]["status"] = "verified_branch_only"
    project["methods"][0]["limitations"] = ["Historical branch only."]
    project["methods"][0]["evidence"] = [commit_evidence()]
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match="existing Git commit"):
        report_model.load_project(source, root)

    revision = git(root, "rev-parse", "HEAD").stdout.strip()
    project["methods"][0]["evidence"] = [
        commit_evidence(revision) | {"locator": "evidence/missing.md"}
    ]
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match="blob at the exact commit"):
        report_model.load_project(source, root)


def test_commit_evidence_rejects_annotated_tag_object_id(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    git(
        root,
        "-c",
        "user.name=BooleanRazor Tests",
        "-c",
        "user.email=tests@example.invalid",
        "-c",
        "tag.gpgsign=false",
        "tag",
        "-a",
        "evidence-tag",
        "-m",
        "annotated evidence tag",
    )
    tag_oid = git(
        root, "rev-parse", "refs/tags/evidence-tag"
    ).stdout.strip()
    assert git(root, "cat-file", "-t", tag_oid).stdout == "tag\n"
    project["methods"][0]["status"] = "verified_branch_only"
    project["methods"][0]["limitations"] = ["Historical branch only."]
    project["methods"][0]["evidence"] = [
        commit_evidence(tag_oid) | {"locator": "evidence/base.md"}
    ]
    write_source(source, project)

    with pytest.raises(
        report_model.ModelError,
        match="exact Git commit object",
    ):
        report_model.load_project(source, root)


def test_commit_evidence_accepts_exact_fetched_object_without_a_local_branch(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    tree = git(root, "write-tree").stdout.strip()
    unreachable = git(
        root,
        "-c",
        "user.name=BooleanRazor Tests",
        "-c",
        "user.email=tests@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit-tree",
        tree,
        "-m",
        "unreachable evidence commit",
    ).stdout.strip()
    assert (
        git(
            root,
            "for-each-ref",
            f"--contains={unreachable}",
            "--format=%(refname)",
            "refs/heads",
        ).stdout
        == ""
    )
    project["methods"][0]["status"] = "verified_branch_only"
    project["methods"][0]["limitations"] = ["Historical branch only."]
    project["methods"][0]["evidence"] = [
        commit_evidence(unreachable) | {"locator": "evidence/base.md"}
    ]
    write_source(source, project)

    loaded, _ = report_model.load_project(source, root)
    assert loaded == project


def test_project_and_proof_reads_use_descriptor_anchored_stable_reader(
    project_repo: tuple[Path, dict[str, object], Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, source = project_repo

    def unstable(*_args: object, **_kwargs: object) -> bytes:
        raise report_model.EvidenceError("project source changed between reads")

    monkeypatch.setattr(report_model, "read_stable_regular", unstable)
    with pytest.raises(report_model.ModelError, match="changed between reads"):
        report_model.load_project(source, root)


def test_task4_replay_rejects_a_preloaded_foreign_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    foreign = ModuleType("_booleanrazor_report_check_promotion")
    foreign.__file__ = "/tmp/foreign-check-promotion.py"
    foreign.build_decision = lambda *_args, **_kwargs: {"decision": "blocked"}
    monkeypatch.setitem(
        sys.modules,
        "_booleanrazor_report_check_promotion",
        foreign,
    )

    loaded = report_model._load_task4_module()
    assert Path(loaded.__file__).resolve() == (
        SCRIPTS / "check-promotion.py"
    ).resolve()


def test_blocked_promotion_proof_is_recomputed_byte_for_byte(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    request = {
        "candidate_evidence": "none",
        "deterministic_pairs": "none",
        "frozen_comparison": "none",
        "official_verifications": "none",
        "schema_version": 1,
        "sealed_results": "none",
        "track": "blind_visible",
    }
    decision = {
        "decision": "blocked",
        "highest_legal_next_step": "freeze_candidate",
        "input_sha256": {
            "promotion-request.json": hashlib.sha256(canonical(request)).hexdigest()
        },
        "reasons": [
            "candidate_evidence_absent",
            "deterministic_pairs_absent",
            "frozen_comparison_absent",
            "official_verifications_absent",
        ],
        "schema_version": 1,
        "track": "blind_visible",
    }
    (root / "evidence/promotion-request.json").write_bytes(canonical(request))
    (root / "evidence/promotion-decision.json").write_bytes(canonical(decision))
    git(
        root,
        "add",
        "evidence/promotion-request.json",
        "evidence/promotion-decision.json",
    )
    git(
        root,
        "-c",
        "user.name=BooleanRazor Tests",
        "-c",
        "user.email=tests@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        "promotion proof",
    )
    project["claims"][0].update(
        {
            "claim_kind": "promotion_state",
            "evidence": [
                path_evidence("evidence/promotion-request.json"),
                path_evidence("evidence/promotion-decision.json"),
            ],
            "proof": empty_claim_proof(
                promotion_decision="evidence/promotion-decision.json",
                promotion_request="evidence/promotion-request.json",
            ),
            "summary": "Author-controlled text is not authoritative.",
        }
    )
    write_source(source, project)
    loaded, _ = report_model.load_project(source, root)
    assert loaded["claims"][0]["claim_kind"] == "promotion_state"


def test_proof_role_changed_during_replay_is_rejected_against_pinned_head(
    project_repo: tuple[Path, dict[str, object], Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, project, source = project_repo
    request = {
        "candidate_evidence": "none",
        "deterministic_pairs": "none",
        "frozen_comparison": "none",
        "official_verifications": "none",
        "schema_version": 1,
        "sealed_results": "none",
        "track": "blind_visible",
    }
    decision = {
        "decision": "blocked",
        "highest_legal_next_step": "freeze_candidate",
        "input_sha256": {
            "promotion-request.json": hashlib.sha256(
                task4_canonical(request)
            ).hexdigest()
        },
        "reasons": [
            "candidate_evidence_absent",
            "deterministic_pairs_absent",
            "frozen_comparison_absent",
            "official_verifications_absent",
        ],
        "schema_version": 1,
        "track": "blind_visible",
    }
    request_path = root / "evidence/promotion-request.json"
    decision_path = root / "evidence/promotion-decision.json"
    request_path.write_bytes(task4_canonical(request))
    decision_path.write_bytes(task4_canonical(decision))
    git(
        root,
        "add",
        "evidence/promotion-request.json",
        "evidence/promotion-decision.json",
    )
    git(
        root,
        "-c",
        "user.name=BooleanRazor Tests",
        "-c",
        "user.email=tests@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        "promotion proof for replacement race",
    )
    project["claims"][0].update(
        {
            "claim_kind": "promotion_state",
            "evidence": [
                path_evidence("evidence/promotion-request.json"),
                path_evidence("evidence/promotion-decision.json"),
            ],
            "proof": empty_claim_proof(
                promotion_decision="evidence/promotion-decision.json",
                promotion_request="evidence/promotion-request.json",
            ),
        }
    )
    write_source(source, project)
    task4 = report_model._load_task4_module()
    original_build_decision = task4.build_decision

    def mutate_after_replay(
        replay_request: Path, replay_policy: Path | None
    ) -> dict[str, object]:
        result = original_build_decision(replay_request, replay_policy)
        forged = dict(decision)
        forged["reasons"] = ["changed_after_initial_validation"]
        decision_path.write_bytes(task4_canonical(forged))
        return result

    monkeypatch.setattr(task4, "build_decision", mutate_after_replay)
    with pytest.raises(
        report_model.ModelError,
        match="changed from the pinned HEAD blob after proof replay",
    ):
        report_model.load_project(source, root)


def test_task4_replay_uses_task4_canonical_bytes_for_non_ascii_input_key(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    request = {
        "candidate_evidence": "none",
        "deterministic_pairs": "none",
        "frozen_comparison": "none",
        "official_verifications": ["验证.json"],
        "schema_version": 1,
        "sealed_results": "none",
        "track": "blind_visible",
    }
    request_path = root / "evidence/promotion-request.json"
    decision_path = root / "evidence/promotion-decision.json"
    (root / "evidence/验证.json").write_bytes(
        task4_canonical(official_record())
    )
    request_path.write_bytes(task4_canonical(request))
    task4 = report_model._load_task4_module()
    decision = task4.build_decision(request_path, None)
    decision_path.write_bytes(task4_canonical(decision))
    assert b"\\u9a8c\\u8bc1.json" in decision_path.read_bytes()
    git(
        root,
        "add",
        "evidence/验证.json",
        "evidence/promotion-request.json",
        "evidence/promotion-decision.json",
    )
    git(
        root,
        "-c",
        "user.name=BooleanRazor Tests",
        "-c",
        "user.email=tests@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        "non-ASCII promotion input",
    )
    project["claims"][0].update(
        {
            "evidence": [
                path_evidence(),
                path_evidence("evidence/promotion-request.json"),
                path_evidence("evidence/promotion-decision.json"),
            ],
            "proof": empty_claim_proof(
                promotion_decision="evidence/promotion-decision.json",
                promotion_request="evidence/promotion-request.json",
            ),
        }
    )
    write_source(source, project)

    loaded, _ = report_model.load_project(source, root)
    assert loaded["claims"][0]["status"] == "blocked"


def test_forged_blocked_decision_cannot_match_recomputed_task4_result(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    request = {
        "candidate_evidence": "none",
        "deterministic_pairs": "none",
        "frozen_comparison": "none",
        "official_verifications": "none",
        "schema_version": 1,
        "sealed_results": "none",
        "track": "blind_visible",
    }
    forged = {
        "decision": "blocked",
        "highest_legal_next_step": "freeze_candidate",
        "input_sha256": {
            "promotion-request.json": hashlib.sha256(canonical(request)).hexdigest()
        },
        "reasons": ["candidate_evidence_absent"],
        "schema_version": 1,
        "track": "blind_visible",
    }
    (root / "evidence/promotion-request.json").write_bytes(canonical(request))
    (root / "evidence/promotion-decision.json").write_bytes(canonical(forged))
    git(
        root,
        "add",
        "evidence/promotion-request.json",
        "evidence/promotion-decision.json",
    )
    git(
        root,
        "-c",
        "user.name=BooleanRazor Tests",
        "-c",
        "user.email=tests@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        "forged promotion proof",
    )
    project["claims"][0].update(
        {
            "claim_kind": "promotion_state",
            "evidence": [
                path_evidence("evidence/promotion-request.json"),
                path_evidence("evidence/promotion-decision.json"),
            ],
            "proof": empty_claim_proof(
                promotion_decision="evidence/promotion-decision.json",
                promotion_request="evidence/promotion-request.json",
            ),
        }
    )
    write_source(source, project)
    with pytest.raises(report_model.ModelError, match="recomputed Task 4 decision"):
        report_model.load_project(source, root)


@pytest.mark.parametrize(
    ("mutation", "fragment"),
    (
        ("round-extra-key", "research_rounds\\[0\\] must use exact keys"),
        ("run-extra-key", "research_rounds\\[0\\].runs\\[0\\] must use exact keys"),
        ("duplicate-round-id", "duplicate round_id"),
        ("duplicate-round-index", "duplicate round_index"),
        ("noncontiguous-index", "contiguous positive"),
        ("multiple-roots", "exactly one root"),
        ("missing-parent", "missing parent"),
        ("duplicate-parent", "parent_round_ids must be unique"),
        ("self-parent", "must not name itself"),
        ("future-parent", "must precede child"),
        ("cycle", "lineage must not contain a cycle"),
        ("turning-point-not-bool", "turning_point must be a JSON boolean"),
        ("no-turning-point", "at least one turning point"),
        ("invalid-track", "has invalid track"),
        ("invalid-status", "has invalid status"),
        ("invalid-run-status", "runs\\[0\\] has invalid status"),
        ("empty-round-text", "hypothesis must be a nonempty string"),
        ("empty-round-list", "permitted_data must be a nonempty list"),
        ("empty-runs", "runs must be a nonempty list"),
        ("empty-run-text", "classification must be a nonempty string"),
        ("empty-run-evidence", "must be a nonempty evidence list"),
    ),
)
def test_research_round_schema_and_lineage_are_closed(
    project_repo: tuple[Path, dict[str, object], Path],
    mutation: str,
    fragment: str,
) -> None:
    root, project, source = project_repo
    revision = git(root, "rev-parse", "HEAD").stdout.strip()
    first = project["research_rounds"][0]
    assert isinstance(first, dict)
    second = research_round(
        round_id="R02",
        parent_round_ids=["R01"],
        round_index=2,
        revision=revision,
        turning_point=False,
    )
    project["research_rounds"].append(second)

    if mutation == "round-extra-key":
        first["conceptual_method_graph"] = "not a trace record"
    elif mutation == "run-extra-key":
        first["runs"][0]["metric"] = "unbound"
    elif mutation == "duplicate-round-id":
        second["round_id"] = "R01"
    elif mutation == "duplicate-round-index":
        second["round_index"] = 1
    elif mutation == "noncontiguous-index":
        second["round_index"] = 3
    elif mutation == "multiple-roots":
        second["parent_round_ids"] = []
    elif mutation == "missing-parent":
        second["parent_round_ids"] = ["R99"]
    elif mutation == "duplicate-parent":
        second["parent_round_ids"] = ["R01", "R01"]
    elif mutation == "self-parent":
        second["parent_round_ids"] = ["R02"]
    elif mutation == "future-parent":
        third = research_round(
            round_id="R03",
            parent_round_ids=["R01"],
            round_index=3,
            revision=revision,
            turning_point=False,
        )
        project["research_rounds"].append(third)
        second["parent_round_ids"] = ["R03"]
    elif mutation == "cycle":
        first["parent_round_ids"] = ["R02"]
        second["parent_round_ids"] = ["R01"]
    elif mutation == "turning-point-not-bool":
        first["turning_point"] = 1
    elif mutation == "no-turning-point":
        first["turning_point"] = False
    elif mutation == "invalid-track":
        first["track"] = "conceptual"
    elif mutation == "invalid-status":
        first["status"] = "promising"
    elif mutation == "invalid-run-status":
        first["runs"][0]["status"] = "mostly_successful"
    elif mutation == "empty-round-text":
        first["hypothesis"] = ""
    elif mutation == "empty-round-list":
        first["permitted_data"] = []
    elif mutation == "empty-runs":
        first["runs"] = []
    elif mutation == "empty-run-text":
        first["runs"][0]["classification"] = ""
    elif mutation == "empty-run-evidence":
        first["runs"][0]["evidence"] = []
    else:
        raise AssertionError(mutation)

    write_source(source, project)
    with pytest.raises(report_model.ModelError, match=fragment):
        report_model.load_project(source, root)


def test_verified_main_sealed_round_requires_a_sanitized_authenticated_attestation(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    project["research_rounds"][0]["track"] = "sealed_confirmation"
    write_source(source, project)

    with pytest.raises(
        report_model.ModelError,
        match="sanitized authenticated attestation",
    ):
        report_model.load_project(source, root)


@pytest.mark.parametrize("field", ("base_revision", "result_revision"))
def test_research_round_revisions_are_existing_exact_commit_objects(
    project_repo: tuple[Path, dict[str, object], Path],
    field: str,
) -> None:
    root, project, source = project_repo
    project["research_rounds"][0][field] = "a" * 40
    write_source(source, project)
    with pytest.raises(
        report_model.ModelError,
        match=f"{field} must name an existing exact Git commit object",
    ):
        report_model.load_project(source, root)


def test_verified_main_round_preserves_historical_result_and_current_path_binding(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    previous = git(root, "rev-parse", "HEAD").stdout.strip()
    (root / "evidence/current.md").write_text("current\n", encoding="utf-8")
    git(root, "add", "evidence/current.md")
    git(
        root,
        "-c",
        "user.name=BooleanRazor Tests",
        "-c",
        "user.email=tests@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        "advance current head",
    )
    assert git(root, "rev-parse", "HEAD").stdout.strip() != previous
    project["research_rounds"][0]["evidence"] = [path_evidence()]
    write_source(source, project)

    with pytest.raises(
        report_model.ModelError,
        match="must include commit evidence bound to result_revision",
    ):
        report_model.load_project(source, root)

    project["research_rounds"][0]["evidence"].append(
        commit_evidence(previous) | {"locator": "evidence/base.md"}
    )
    write_source(source, project)
    loaded, _ = report_model.load_project(source, root)
    assert loaded["research_rounds"][0]["result_revision"] == previous

    project["research_rounds"][0]["evidence"] = [
        {
            "kind": "command",
            "label": "unbound command",
            "locator": "make test",
            "revision": "none",
        }
    ]
    write_source(source, project)
    with pytest.raises(
        report_model.ModelError,
        match="verified_main requires HEAD-bound path evidence",
    ):
        report_model.load_project(source, root)


def test_branch_only_round_evidence_binds_the_exact_result_revision(
    project_repo: tuple[Path, dict[str, object], Path],
) -> None:
    root, project, source = project_repo
    base_revision = git(root, "rev-parse", "HEAD").stdout.strip()
    (root / "evidence/result.md").write_text("result\n", encoding="utf-8")
    git(root, "add", "evidence/result.md")
    git(
        root,
        "-c",
        "user.name=BooleanRazor Tests",
        "-c",
        "user.email=tests@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        "historical result",
    )
    result_revision = git(root, "rev-parse", "HEAD").stdout.strip()
    round_row = project["research_rounds"][0]
    round_row.update(
        {
            "base_revision": base_revision,
            "branch": "research/exact-result",
            "result_revision": result_revision,
            "status": "verified_branch_only",
            "evidence": [
                commit_evidence(base_revision)
                | {"locator": "evidence/base.md"}
            ],
        }
    )
    round_row["runs"][0]["evidence"] = [
        commit_evidence(result_revision)
        | {"locator": "evidence/result.md"}
    ]
    write_source(source, project)

    with pytest.raises(
        report_model.ModelError,
        match="must include commit evidence bound to result_revision",
    ):
        report_model.load_project(source, root)

    round_row["evidence"] = [
        commit_evidence(result_revision)
        | {"locator": "evidence/result.md"}
    ]
    write_source(source, project)
    loaded, _ = report_model.load_project(source, root)
    assert loaded["research_rounds"][0]["result_revision"] == result_revision


@pytest.mark.parametrize(
    ("mutation", "fragment"),
    (
        ("missing", "must reference exactly one research round"),
        ("wrong-track", "must reference a verified synthetic round"),
        ("unverified", "must reference a verified synthetic round"),
    ),
)
def test_synthetic_frontier_pointer_is_closed_and_evidence_bound(
    project_repo: tuple[Path, dict[str, object], Path],
    mutation: str,
    fragment: str,
) -> None:
    root, project, source = project_repo
    first = project["research_rounds"][0]
    if mutation == "missing":
        project["project"]["synthetic_frontier_round_id"] = "R99"
    elif mutation == "wrong-track":
        first["track"] = "disclosed_control"
    elif mutation == "unverified":
        first["status"] = "rejected"
    else:
        raise AssertionError(mutation)
    write_source(source, project)

    with pytest.raises(report_model.ModelError, match=fragment):
        report_model.load_project(source, root)


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
    assert b"&lt;img src=&quot;https://attacker.invalid/x&quot;" not in index
    assert b"Blind advantage has not been demonstrated." in index

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


def test_renderer_exposes_the_actual_round_lineage_and_retains_dead_ends() -> None:
    project = valid_project()
    first = project["research_rounds"][0]
    first.update(
        {
            "outcome": "The first candidate failed exactness.",
            "title": "<b>R01 unsafe title</b>",
        }
    )
    first["runs"][0].update(
        {
            "classification": "failed exactness <script>alert(1)</script>",
            "outcome": "0 / 104857 exact rows.",
            "status": "failed",
        }
    )
    second = research_round(
        round_id="R02",
        parent_round_ids=["R01"],
        round_index=2,
        status="verified_branch_only",
        turning_point=False,
    )
    second.update(
        {
            "outcome": "The control and candidate were equal.",
            "title": "Fair-order R1",
        }
    )
    second["runs"][0]["status"] = "equal"
    third = research_round(
        round_id="R03",
        parent_round_ids=["R01", "R02"],
        round_index=3,
        status="rejected",
        turning_point=True,
    )
    third.update(
        {
            "decision": "Supersede the pilot and pivot to executable binding.",
            "insight": "A promising unbound pilot is not admissible evidence.",
            "title": "Projected-support preflight",
        }
    )
    third["runs"] = [
        {
            "classification": "unbound pilot",
            "evidence": third["evidence"],
            "outcome": "Promising, then withdrawn.",
            "run_id": "r03-pilot",
            "status": "superseded",
        },
        {
            "classification": "rejected preflight",
            "evidence": third["evidence"],
            "outcome": "Timed out before an admissible comparison.",
            "run_id": "r03-preflight",
            "status": "timed_out",
        },
    ]
    project["research_rounds"] = [third, first, second]

    outputs = report_model.render_outputs(project, "a" * 64, "b" * 64)
    index = outputs["reports/site/index.html"]
    experiments = outputs["reports/site/experiments.html"]
    css = outputs["reports/site/assets/report.css"]

    assert b"Current internal synthetic frontier" in index
    assert b"Missing public and sealed proof" in index
    assert b'<ol class="research-lineage"' in index
    lineage = index[index.index(b'<ol class="research-lineage"') :]
    assert lineage.index(b"R01") < lineage.index(b"R02") < lineage.index(b"R03")
    assert b'data-lineage-parent="R01" data-lineage-child="R02"' in lineage
    assert b'data-lineage-parent="R01" data-lineage-child="R03"' in lineage
    assert b'data-lineage-parent="R02" data-lineage-child="R03"' in lineage
    assert b'class="lineage-origins has-multiple-parents"' in lineage
    assert b'aria-label="Parent edge R01 to R03"' in lineage
    assert b'aria-label="Parent edge R02 to R03"' in lineage
    assert b'class="lineage-node turning-point"' in index
    assert b"Turning point" in index
    assert b"experiments.html#round-R03" in index
    assert b"Report design references" in index
    assert b'href="https://example.com/reference"' in index
    assert b"Information-architecture reference only." in index
    assert b"<svg" not in index
    assert b"<svg" not in experiments

    assert b'id="round-R01"' in experiments
    assert b'href="#round-R01"' in experiments
    assert b'href="#round-R02"' in experiments
    for label in (
        b"Parents",
        b"Branch",
        b"Base revision",
        b"Result revision",
        b"Track",
        b"Status",
        b"Hypothesis",
        b"Independent variable",
        b"Permitted data",
        b"Frozen controls",
        b"Outcome",
        b"Decision",
        b"Insight",
        b"Limitations",
        b"Next pivot",
        b"Round evidence",
        b"Runs",
    ):
        assert label in experiments
    for run_status in (b"failed", b"equal", b"superseded", b"timed_out"):
        assert run_status in experiments
    assert b"0 / 104857 exact rows." in experiments
    assert b"Promising, then withdrawn." in experiments
    assert b"<script>alert(1)</script>" not in experiments
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in experiments

    assert b".lineage-parent-edge::after" in css
    assert b".lineage-origins.has-multiple-parents::after" in css
    assert b".lineage-connector::before" in css
    assert b".turning-point" in css
    assert b".run-status-failed" in css
    assert b".run-status-superseded" in css
    assert b".card, .method-card { min-width: 0;" in css
    assert b".research-round { min-width: 0;" in css
    assert b".table-wrap { max-width: 100%; min-width: 0; overflow-x: auto; }" in css
    assert b"@media (max-width: 760px)" in css
    assert b"@media print" in css

    experiment_index = outputs["docs/EXPERIMENT_INDEX.md"]
    assert b"# Research trajectory" in experiment_index
    assert experiment_index.index(b"R01") < experiment_index.index(b"R02")
    assert b"r03-pilot" in experiment_index
    assert b"superseded" in experiment_index
    assert b"Timed out before an admissible comparison." in experiment_index
    ledger = outputs["research/EVIDENCE_LEDGER.md"]
    assert b"# Research-round provenance" in ledger
    assert b"## R03" in ledger
    assert b"r03-preflight" in ledger
    assert ledger.endswith(b"\n")
    assert not ledger.endswith(b"\n\n")


def test_renderer_round_order_is_chronological_and_output_is_repeatable() -> None:
    project = valid_project()
    revision = project["research_rounds"][0]["result_revision"]
    assert isinstance(revision, str)
    second = research_round(
        round_id="R02",
        parent_round_ids=["R01"],
        round_index=2,
        revision=revision,
        turning_point=False,
    )
    project["research_rounds"] = [second, project["research_rounds"][0]]

    first_render = report_model.render_outputs(
        project, "a" * 64, "b" * 64
    )
    second_render = report_model.render_outputs(
        copy.deepcopy(project), "a" * 64, "b" * 64
    )
    assert first_render == second_render
    experiments = first_render["reports/site/experiments.html"]
    assert experiments.index(b'id="round-R01"') < experiments.index(
        b'id="round-R02"'
    )
    assert first_render["reports/site/assets/report.js"] == (
        report_model.REPORT_JS.encode("utf-8")
    )


def test_report_generator_digest_binds_all_executable_components() -> None:
    evidence_helper = b"evidence helper bytes\n"
    candidate_validator = b"candidate validator bytes\n"
    promotion_validator = b"promotion validator bytes\n"
    report_generator = b"report model bytes\n"
    digest = hashlib.sha256()
    digest.update(b"BooleanRazor deterministic report generator v2\0")
    for path, content in (
        (b"scripts/evidence_io.py", evidence_helper),
        (b"scripts/candidate_evidence.py", candidate_validator),
        (b"scripts/check-promotion.py", promotion_validator),
        (b"scripts/report_model.py", report_generator),
    ):
        digest.update(len(path).to_bytes(4, "big"))
        digest.update(path)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)

    expected = digest.hexdigest()
    assert (
        report_model.report_generator_digest(
            report_generator,
            evidence_helper,
            candidate_validator,
            promotion_validator,
        )
        == expected
    )
    assert (
        report_model.report_generator_digest(
            report_generator + b"# changed\n",
            evidence_helper,
            candidate_validator,
            promotion_validator,
        )
        != expected
    )
    assert (
        report_model.report_generator_digest(
            report_generator,
            evidence_helper + b"# changed\n",
            candidate_validator,
            promotion_validator,
        )
        != expected
    )
    assert (
        report_model.report_generator_digest(
            report_generator,
            evidence_helper,
            candidate_validator + b"# changed\n",
            promotion_validator,
        )
        != expected
    )
    assert (
        report_model.report_generator_digest(
            report_generator,
            evidence_helper,
            candidate_validator,
            promotion_validator + b"# changed\n",
        )
        != expected
    )


def test_renderer_uses_the_structural_frontier_pointer_not_round_chronology() -> None:
    project = valid_project()
    revision = project["research_rounds"][0]["result_revision"]
    assert isinstance(revision, str)
    projected = research_round(
        round_id="R08",
        parent_round_ids=["R01"],
        round_index=2,
        revision=revision,
        turning_point=True,
    )
    projected["title"] = "ProjectedSupportBDD frontier"
    projected["outcome"] = "104857 / 104857 exact rows; 72 gates."
    tensor_network = research_round(
        round_id="R09",
        parent_round_ids=["R08"],
        round_index=3,
        revision=revision,
        turning_point=False,
    )
    tensor_network["title"] = "Tensor-network pipeline"
    tensor_network["outcome"] = "A later plumbing round, not the frontier."
    project["research_rounds"].extend([projected, tensor_network])
    project["project"]["synthetic_frontier_round_id"] = "R08"

    index = report_model.render_outputs(
        project, "a" * 64, "b" * 64
    )["reports/site/index.html"]
    frontier = index[
        index.index(b'<section class="frontier">') :
        index.index(b"</section>", index.index(b'<section class="frontier">'))
    ]
    assert b"R08" in frontier
    assert b"ProjectedSupportBDD frontier" in frontier
    assert b"104857 / 104857 exact rows; 72 gates." in frontier
    assert b"R09" not in frontier
    assert b"Tensor-network pipeline" not in frontier
    assert b"..</p>" not in frontier


def test_renderer_preserves_sentence_list_punctuation_without_dot_semicolons() -> None:
    project = valid_project()
    project["research_rounds"][0]["limitations"] = [
        "Synthetic fixture only.",
        "No public conclusion is permitted.",
    ]
    project["methods"][0]["insights"] = [
        "Exactness is primary.",
        "Gate count is secondary.",
    ]

    outputs = report_model.render_outputs(project, "a" * 64, "b" * 64)

    assert b".;" not in outputs["reports/site/index.html"]
    assert b".;" not in outputs["docs/METHODS.md"]
    assert b'<div class="frontier-boundary">' in outputs[
        "reports/site/index.html"
    ]
