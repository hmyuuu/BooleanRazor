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
CHECKER_PATH = SCRIPTS / "check-deliverable.py"
CANDIDATE_EVIDENCE_PATH = SCRIPTS / "candidate_evidence.py"
CHECK_PROMOTION_PATH = SCRIPTS / "check-promotion.py"
EXPECTED_SAFE_REPORT_JS = b"""\
"use strict";
for (const button of document.querySelectorAll("[data-status-filter]")) {
  button.addEventListener("click", () => {
    const wanted = button.dataset.statusFilter;
    for (const row of document.querySelectorAll("[data-status]")) {
      row.hidden = wanted !== "all" && row.dataset.status !== wanted;
    }
    for (const peer of document.querySelectorAll("[data-status-filter]")) {
      peer.setAttribute("aria-pressed", String(peer === button));
    }
  });
}
"""


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


evidence_io = load_module("evidence_io", "evidence_io.py")
report_model = load_module("report_model", "report_model.py")
check_deliverable_module = load_module(
    "check_deliverable", "check-deliverable.py"
)


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


def evidence(locator: str = "evidence/base.md") -> dict[str, str]:
    return {
        "kind": "path",
        "label": "evidence",
        "locator": locator,
        "revision": "main",
    }


def valid_project(revision: str) -> dict[str, object]:
    controls = [
        {
            "control_id": f"control-{letter.lower()}",
            "evidence": [evidence()],
            "function": function,
            "gates": gates,
            "instance": f"mystery-{letter}",
            "limitation": "Disclosed control only.",
            "status": "verified_main",
        }
        for letter, function, gates in (
            ("A", "x+y", 37),
            ("B", "abs(x-y)", 49),
            ("C", "x*y", 168),
            ("D", "x²+y²", 127),
        )
    ]
    return {
        "claims": [
            {
                "claim_id": "blind-result",
                "claim_kind": "blind_advantage",
                "evidence": [evidence()],
                "limitations": ["Public evaluation has not run."],
                "missing_proof": ["Sealed confirmation."],
                "proof": {
                    "official_record": "none",
                    "promotion_decision": "none",
                    "promotion_request": "none",
                    "trust_policy": "none",
                },
                "status": "blocked",
                "summary": "Blind advantage is not demonstrated.",
                "track": "blind_visible",
            }
        ],
        "commands": [
            {
                "command": "make test",
                "command_id": "test",
                "scope": "Local suite.",
                "title": "Test",
            }
        ],
        "controls": controls,
        "experiments": [
            {
                "decision": "Retain.",
                "evidence": [evidence()],
                "experiment_id": "controls",
                "limitations": [],
                "location": "tests/official_v1.rs",
                "outcome": "Exact.",
                "status": "verified_main",
                "title": "Controls",
                "track": "disclosed_control",
            }
        ],
        "external_references": [
            {
                "reference_id": "reference",
                "title": "Reference",
                "url": "https://example.com/reference",
                "use": "Navigation only.",
            }
        ],
        "methods": [
            {
                "evidence": [evidence()],
                "insights": ["Exactness first."],
                "limitations": [],
                "method_id": "exact",
                "optimization": ["Minimize gates second."],
                "scope": "Controls.",
                "status": "verified_main",
                "stop_rules": ["Stop on inexactness."],
                "summary": "Exact core.",
                "title": "Exact core",
            }
        ],
        "project": {
            "conclusion": "Blind advantage is not demonstrated.",
            "next_gate": "Run public evaluation.",
            "purpose": "Evidence-first circuit synthesis.",
            "synthetic_frontier_round_id": "R01",
            "title": "BooleanRazor",
        },
        "research_rounds": [
            {
                "base_revision": revision,
                "branch": "main",
                "decision": "Retain the exact synthetic result.",
                "evidence": [
                    evidence(),
                    {
                        "kind": "commit",
                        "label": "historical round evidence",
                        "locator": "evidence/base.md",
                        "revision": revision,
                    },
                ],
                "frozen_controls": ["Accuracy before gate count."],
                "hypothesis": "The exact learner recovers the frozen fixture.",
                "independent_variable": "Learner configuration.",
                "insight": "Exactness and gate count are separate outcomes.",
                "limitations": ["Synthetic fixture only."],
                "next_pivot": "Test the next frozen hypothesis.",
                "outcome": "The frozen synthetic fixture was recovered exactly.",
                "parent_round_ids": [],
                "permitted_data": ["Tracked synthetic fixture only."],
                "result_revision": revision,
                "round_id": "R01",
                "round_index": 1,
                "runs": [
                    {
                        "classification": "exact synthetic result",
                        "evidence": [
                            {
                                "kind": "commit",
                                "label": "historical run evidence",
                                "locator": "evidence/base.md",
                                "revision": revision,
                            }
                        ],
                        "outcome": "Completed with exact internal equivalence.",
                        "run_id": "r01-run-01",
                        "status": "successful",
                    }
                ],
                "status": "verified_main",
                "title": "Exact synthetic control",
                "track": "synthetic",
                "turning_point": True,
            }
        ],
        "schema_version": 1,
        "verification_layers": [
            {
                "authority": "Rust",
                "command": "make test",
                "current_state": "implemented",
                "layer_id": "internal",
                "meaning": "Internal equivalence.",
                "title": "Internal",
            }
        ],
    }


def marker(source_digest: str, generator_digest: str) -> str:
    return (
        "<!-- GENERATED; DO NOT EDIT. Source: reports/data/project.json SHA-256: "
        f"{source_digest}; report generator SHA-256: {generator_digest} -->"
    )


def exact_outputs(
    source_digest: str, generator_digest: str
) -> dict[str, bytes]:
    generated = marker(source_digest, generator_digest)
    page = (
        f"{generated}\n"
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<link rel="stylesheet" href="assets/report.css"></head>'
        '<body><a class="skip-link" href="#content">Skip</a>'
        '<nav><a href="index.html">Status</a>'
        '<a href="methods.html">Methods</a>'
        '<a href="verification.html">Verification</a>'
        '<a href="experiments.html">Experiments</a></nav>'
        '<main id="content">Report</main>'
        '<script src="assets/report.js"></script></body></html>\n'
    ).encode()
    markdown = (generated + "\n\n# Generated\n").encode()
    return {
        "docs/EXPERIMENT_INDEX.md": markdown,
        "docs/METHODS.md": markdown,
        "docs/STATUS.md": markdown,
        "reports/site/assets/report.css": (
            "a:focus-visible { outline: 2px solid; }\n"
            "@media print { nav { display: none; } }\n"
        ).encode(),
        "reports/site/assets/report.js": EXPECTED_SAFE_REPORT_JS,
        "reports/site/experiments.html": page,
        "reports/site/index.html": page,
        "reports/site/methods.html": page,
        "reports/site/verification.html": page,
        "research/EVIDENCE_LEDGER.md": markdown,
    }


def write_outputs(root: Path, outputs: dict[str, bytes]) -> None:
    for name, content in outputs.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


@pytest.fixture
def deliverable_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path, str, str, dict[str, bytes]]:
    root = tmp_path / "repo"
    (root / "evidence").mkdir(parents=True)
    (root / "evidence/base.md").write_text("evidence\n", encoding="utf-8")
    (root / "scripts").mkdir()
    (root / "scripts/report_model.py").write_bytes(
        (SCRIPTS / "report_model.py").read_bytes()
    )
    (root / "scripts/evidence_io.py").write_bytes(
        (SCRIPTS / "evidence_io.py").read_bytes()
    )
    (root / "scripts/candidate_evidence.py").write_bytes(
        CANDIDATE_EVIDENCE_PATH.read_bytes()
    )
    (root / "scripts/check-promotion.py").write_bytes(
        CHECK_PROMOTION_PATH.read_bytes()
    )
    (root / "scripts/check-deliverable.py").write_bytes(
        CHECKER_PATH.read_bytes()
    )
    monkeypatch.setattr(
        check_deliverable_module.report_model,
        "__file__",
        str(root / "scripts/report_model.py"),
    )
    monkeypatch.setattr(
        check_deliverable_module.evidence_io,
        "__file__",
        str(root / "scripts/evidence_io.py"),
    )
    monkeypatch.setattr(
        check_deliverable_module.candidate_evidence,
        "__file__",
        str(root / "scripts/candidate_evidence.py"),
    )
    monkeypatch.setattr(
        check_deliverable_module.check_promotion,
        "__file__",
        str(root / "scripts/check-promotion.py"),
    )
    git(root.parent, "init", "-q", str(root))
    git(root, "add", "evidence/base.md", "scripts/report_model.py")
    git(
        root,
        "-c",
        "user.name=BooleanRazor Test",
        "-c",
        "user.email=booleanrazor-test@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "fixture evidence",
    )
    revision = git(root, "rev-parse", "HEAD").stdout.strip()
    source = root / "reports/data/project.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(canonical(valid_project(revision)))
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    generator_digest = report_model.report_generator_digest(
        (root / "scripts/report_model.py").read_bytes(),
        (root / "scripts/evidence_io.py").read_bytes(),
        (root / "scripts/candidate_evidence.py").read_bytes(),
        (root / "scripts/check-promotion.py").read_bytes(),
    )
    outputs = exact_outputs(source_digest, generator_digest)
    write_outputs(root, outputs)
    return root, source, source_digest, generator_digest, outputs


def patch_outputs(
    monkeypatch: pytest.MonkeyPatch, outputs: dict[str, bytes]
) -> None:
    monkeypatch.setattr(
        check_deliverable_module.report_model,
        "render_outputs",
        lambda project, source_digest, generator_digest: dict(outputs),
    )


def assert_error(errors: list[str], fragment: str) -> None:
    assert any(fragment in error for error in errors), errors


def test_fresh_exact_output_map_passes(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    patch_outputs(monkeypatch, outputs)
    assert check_deliverable_module.check_deliverable(source, root) == []


def test_missing_and_noncanonical_source_fail_closed(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    patch_outputs(monkeypatch, outputs)
    missing = root / "reports/data/missing.json"
    assert_error(
        check_deliverable_module.check_deliverable(missing, root),
        "project source",
    )
    value = json.loads(source.read_text(encoding="utf-8"))
    source.write_text(json.dumps(value) + "\n", encoding="utf-8")
    assert_error(
        check_deliverable_module.check_deliverable(source, root),
        "canonical JSON",
    )


def test_only_the_canonical_project_source_is_accepted(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, source, _, generator_digest, _ = deliverable_repo
    alternate_project = json.loads(source.read_text(encoding="utf-8"))
    alternate_project["project"]["title"] = "Alternate report"
    alternate = root / "reports/data/alternate.json"
    alternate.write_bytes(canonical(alternate_project))
    alternate_digest = hashlib.sha256(alternate.read_bytes()).hexdigest()
    alternate_outputs = exact_outputs(alternate_digest, generator_digest)
    write_outputs(root, alternate_outputs)
    patch_outputs(monkeypatch, alternate_outputs)
    assert_error(
        check_deliverable_module.check_deliverable(alternate, root),
        "canonical project source",
    )


def test_imported_report_model_must_be_the_repo_generator(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    patch_outputs(monkeypatch, outputs)
    other = tmp_path / "other/report_model.py"
    other.parent.mkdir()
    other.write_bytes((root / "scripts/report_model.py").read_bytes())
    monkeypatch.setattr(
        check_deliverable_module.report_model, "__file__", str(other)
    )
    assert_error(
        check_deliverable_module.check_deliverable(source, root),
        "imported report model",
    )


def test_all_checker_content_reads_use_stable_descriptor_io(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    patch_outputs(monkeypatch, outputs)
    labels: list[str] = []
    original = check_deliverable_module.evidence_io.read_stable_regular

    def record(path: Path, label: str, max_bytes: int) -> bytes:
        labels.append(label)
        return original(path, label, max_bytes)

    monkeypatch.setattr(
        check_deliverable_module.evidence_io,
        "read_stable_regular",
        record,
    )
    assert check_deliverable_module.check_deliverable(source, root) == []
    assert "project source" in labels
    assert "report model" in labels
    assert {
        f"generated output {relative}"
        for relative in report_model.OUTPUT_PATHS
    }.issubset(labels)


def test_missing_drift_symlink_and_unexpected_outputs_are_rejected(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    patch_outputs(monkeypatch, outputs)
    missing = root / "docs/STATUS.md"
    missing.unlink()
    assert_error(
        check_deliverable_module.check_deliverable(source, root),
        "missing generated output",
    )
    missing.write_bytes(outputs["docs/STATUS.md"])

    drift = root / "docs/METHODS.md"
    drift.write_bytes(drift.read_bytes() + b"x")
    assert_error(
        check_deliverable_module.check_deliverable(source, root),
        "generated output drift",
    )
    drift.write_bytes(outputs["docs/METHODS.md"])

    target = root / "docs/status-target.md"
    target.write_bytes(outputs["docs/STATUS.md"])
    (root / "docs/STATUS.md").unlink()
    (root / "docs/STATUS.md").symlink_to(target.name)
    assert_error(
        check_deliverable_module.check_deliverable(source, root), "symlink"
    )
    (root / "docs/STATUS.md").unlink()
    (root / "docs/STATUS.md").write_bytes(outputs["docs/STATUS.md"])

    extra = root / "reports/site/extra.html"
    extra.write_text("<p>unexpected</p>\n", encoding="utf-8")
    assert_error(
        check_deliverable_module.check_deliverable(source, root),
        "unexpected generated output",
    )


def test_checker_owns_the_complete_generated_output_set(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    omitted = "docs/STATUS.md"
    reduced = {name: raw for name, raw in outputs.items() if name != omitted}
    (root / omitted).unlink()
    monkeypatch.setattr(
        check_deliverable_module.report_model,
        "OUTPUT_PATHS",
        frozenset(reduced),
    )
    patch_outputs(monkeypatch, reduced)
    errors = check_deliverable_module.check_deliverable(source, root)
    assert_error(errors, "canonical generated output set")
    assert_error(errors, f"missing generated output: {omitted}")


def mutate_matching_output(
    root: Path,
    outputs: dict[str, bytes],
    name: str,
    transform,
) -> dict[str, bytes]:
    changed = dict(outputs)
    changed[name] = transform(changed[name])
    (root / name).write_bytes(changed[name])
    return changed


@pytest.mark.parametrize(
    ("description", "transform", "fragment"),
    (
        (
            "broken href",
            lambda page: page.replace(
                b'href="methods.html"', b'href="missing.html"', 1
            ),
            "missing local target",
        ),
        (
            "remote stylesheet",
            lambda page: page.replace(
                b'href="assets/report.css"',
                b'href="https://cdn.example/report.css"',
                1,
            ),
            "remote resource",
        ),
        (
            "mixed-case stylesheet",
            lambda page: page.replace(
                b'href="assets/report.css"',
                b'href="HTTPS://cdn.example/report.css"',
                1,
            ),
            "remote resource",
        ),
        (
            "scheme-relative image",
            lambda page: page.replace(
                b"<main", b'<img src="//cdn.example/a.png"><main', 1
            ),
            "remote resource",
        ),
        (
            "data image",
            lambda page: page.replace(
                b"<main", b'<img src="data:image/png;base64,AA=="><main', 1
            ),
            "remote resource",
        ),
        (
            "remote image",
            lambda page: page.replace(
                b"<main", b'<img src="https://cdn.example/a.png"><main', 1
            ),
            "remote resource",
        ),
        (
            "iframe",
            lambda page: page.replace(
                b"<main", b'<iframe src="https://example.com"></iframe><main', 1
            ),
            "forbidden iframe",
        ),
        (
            "remote script",
            lambda page: page.replace(
                b'src="assets/report.js"',
                b'src="javascript:alert(1)"',
                1,
            ),
            "remote resource",
        ),
        (
            "preload",
            lambda page: page.replace(
                b"</head>",
                b'<link rel="preload" href="assets/report.js"></head>',
                1,
            ),
            "resource link",
        ),
        (
            "remote form action",
            lambda page: page.replace(
                b"<main",
                b'<form action="https://example.com/submit"></form><main',
                1,
            ),
            "remote resource",
        ),
        (
            "event handler",
            lambda page: page.replace(
                b"<main", b'<button onclick="fetch(\'/x\')">x</button><main', 1
            ),
            "event-handler attribute",
        ),
        (
            "svg set mutates href",
            lambda page: page.replace(
                b"<main",
                (
                    b'<svg><image href="assets/report.css">'
                    b'<set attributeName="href" '
                    b'to="https://cdn.example/remote.svg"></set>'
                    b"</image></svg><main"
                ),
                1,
            ),
            "forbidden SVG animation",
        ),
        (
            "svg animate mutates href",
            lambda page: page.replace(
                b"<main",
                (
                    b'<svg><image href="assets/report.css">'
                    b'<animate attributeName="href" '
                    b'values="assets/report.css;https://cdn.example/remote.svg">'
                    b"</animate></image></svg><main"
                ),
                1,
            ),
            "forbidden SVG animation",
        ),
        (
            "svg external paint server",
            lambda page: page.replace(
                b"<main",
                (
                    b'<svg><rect fill="url(https://tracker.invalid/'
                    b'paint.svg#x)"></rect></svg><main'
                ),
                1,
            ),
            "forbidden inline SVG",
        ),
    ),
)
def test_html_offline_resource_contract(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
    description: str,
    transform,
    fragment: str,
) -> None:
    del description
    root, source, _, _, outputs = deliverable_repo
    changed = mutate_matching_output(
        root, outputs, "reports/site/index.html", transform
    )
    patch_outputs(monkeypatch, changed)
    assert_error(
        check_deliverable_module.check_deliverable(source, root), fragment
    )


@pytest.mark.parametrize(
    ("transform", "fragment"),
    (
        (
            lambda css: b'@IMPORT "https://cdn.example/x.css";\n' + css,
            "CSS @import",
        ),
        (
            lambda css: b'@\\69mport "https://cdn.example/x.css";\n' + css,
            "CSS escape",
        ),
        (
            lambda css: b'@im/**/port "https://cdn.example/x.css";\n' + css,
            "CSS @import",
        ),
        (
            lambda css: b'a{background:url(data:image/png;base64,AA==)}\n' + css,
            "remote CSS URL",
        ),
        (
            lambda css: b'a{background:URL(//cdn.example/x.png)}\n' + css,
            "remote CSS URL",
        ),
        (
            lambda css: b'a{background:url(HTTPS://cdn.example/x.png)}\n' + css,
            "remote CSS URL",
        ),
        (
            lambda css: b'a{background:url(%2e%2e/%2e%2e/out.png)}\n' + css,
            "noncanonical CSS URL",
        ),
        (
            lambda css: (
                b'a{background-image:image-set("https://cdn.example/x.png" 1x)}\n'
                + css
            ),
            "remote CSS token",
        ),
    ),
)
def test_css_offline_resource_contract(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
    transform,
    fragment: str,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    changed = mutate_matching_output(
        root, outputs, "reports/site/assets/report.css", transform
    )
    patch_outputs(monkeypatch, changed)
    assert_error(
        check_deliverable_module.check_deliverable(source, root), fragment
    )


@pytest.mark.parametrize(
    "payload",
    (
        b'fetch(atob("L3RyYWNr"));\n',
        b'new XMLHttpRequest().open("GET", atob("L3RyYWNr"));\n',
        b'navigator.sendBeacon(atob("L3RyYWNr"), "x");\n',
        b'new WebSocket(String.fromCharCode(119,115,58,47,47,120));\n',
    ),
)
def test_report_script_must_match_the_independently_reviewed_safe_contract(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    changed = mutate_matching_output(
        root,
        outputs,
        "reports/site/assets/report.js",
        lambda script: script + payload,
    )
    patch_outputs(monkeypatch, changed)
    assert_error(
        check_deliverable_module.check_deliverable(source, root),
        "reviewed safe script",
    )


def test_every_internal_fragment_must_resolve(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    changed = mutate_matching_output(
        root,
        outputs,
        "reports/site/index.html",
        lambda page: page.replace(
            b"<main",
            b'<a href="#missing">missing</a><main',
            1,
        ),
    )
    patch_outputs(monkeypatch, changed)
    assert_error(
        check_deliverable_module.check_deliverable(source, root),
        "missing fragment target",
    )

    changed = mutate_matching_output(
        root,
        outputs,
        "reports/site/index.html",
        lambda page: page.replace(
            b'href="methods.html"',
            b'href="methods.html#missing"',
            1,
        ),
    )
    patch_outputs(monkeypatch, changed)
    assert_error(
        check_deliverable_module.check_deliverable(source, root),
        "missing fragment target",
    )


def test_cross_page_fragment_resolves_against_the_target_page(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    changed = mutate_matching_output(
        root,
        outputs,
        "reports/site/index.html",
        lambda page: page.replace(
            b'href="methods.html"',
            b'href="methods.html#content"',
            1,
        ),
    )
    patch_outputs(monkeypatch, changed)
    assert check_deliverable_module.check_deliverable(source, root) == []


def test_skip_link_fragment_must_target_the_main_landmark(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    changed = mutate_matching_output(
        root,
        outputs,
        "reports/site/index.html",
        lambda page: page.replace(
            b'<main id="content">',
            b'<div id="content"></div><main id="other">',
            1,
        ),
    )
    patch_outputs(monkeypatch, changed)
    assert_error(
        check_deliverable_module.check_deliverable(source, root),
        "skip link must target the main landmark",
    )


@pytest.mark.parametrize(
    "replacement",
    (
        b"https://example.com#content",
        b"//example.com#content",
        b"?mode=external#content",
        b"index.html#content",
    ),
)
def test_skip_link_must_be_a_same_page_fragment(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
    replacement: bytes,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    changed = mutate_matching_output(
        root,
        outputs,
        "reports/site/index.html",
        lambda page: page.replace(b'href="#content"', b'href="' + replacement + b'"', 1),
    )
    patch_outputs(monkeypatch, changed)
    assert_error(
        check_deliverable_module.check_deliverable(source, root),
        "skip link must target the main landmark",
    )


def test_duplicate_fragment_ids_are_rejected(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    changed = mutate_matching_output(
        root,
        outputs,
        "reports/site/index.html",
        lambda page: page.replace(
            b"<main",
            b'<div id="content"></div><main',
            1,
        ),
    )
    patch_outputs(monkeypatch, changed)
    assert_error(
        check_deliverable_module.check_deliverable(source, root),
        "duplicate fragment id",
    )


@pytest.mark.parametrize(
    ("transform", "fragment"),
    (
        (
            lambda page: page.replace(
                b'<meta name="viewport" content="width=device-width,initial-scale=1">',
                b"",
                1,
            ),
            "viewport",
        ),
        (
            lambda page: page.replace(b'class="skip-link"', b'class="other"', 1),
            "skip link",
        ),
        (
            lambda page: page.replace(b"<main", b"<section", 1).replace(
                b"</main>", b"</section>", 1
            ),
            "main landmark",
        ),
    ),
)
def test_html_accessibility_contract(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
    transform,
    fragment: str,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    changed = mutate_matching_output(
        root, outputs, "reports/site/index.html", transform
    )
    patch_outputs(monkeypatch, changed)
    assert_error(
        check_deliverable_module.check_deliverable(source, root), fragment
    )


@pytest.mark.parametrize(
    ("transform", "fragment"),
    (
        (
            lambda css: css.replace(b"@media print", b"removed", 1),
            "print stylesheet",
        ),
        (
            lambda css: css.replace(
                b"@media print", b"/* @media print */", 1
            ),
            "print stylesheet",
        ),
        (
            lambda css: css.replace(b":focus-visible", b":focus-removed", 1),
            "visible focus style",
        ),
        (
            lambda css: css.replace(
                b"a:focus-visible {",
                b"/* a:focus-visible */ .focus-placeholder {",
                1,
            ),
            "visible focus style",
        ),
        (
            lambda css: css.replace(
                b"outline: 2px solid", b"outline: none", 1
            ),
            "visible focus style",
        ),
        (
            lambda css: css.replace(
                b"outline: 2px solid", b"outline: 0 transparent", 1
            ),
            "visible focus style",
        ),
    ),
)
def test_stylesheet_accessibility_contract(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
    transform,
    fragment: str,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    changed = mutate_matching_output(
        root,
        outputs,
        "reports/site/assets/report.css",
        transform,
    )
    patch_outputs(monkeypatch, changed)
    assert_error(
        check_deliverable_module.check_deliverable(source, root), fragment
    )


def test_exact_generated_marker_and_digests_are_required(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, source, source_digest, generator_digest, outputs = deliverable_repo
    generated = marker(source_digest, generator_digest).encode()
    changed = mutate_matching_output(
        root,
        outputs,
        "reports/site/index.html",
        lambda page: page.replace(generated, b"digests mentioned elsewhere", 1),
    )
    patch_outputs(monkeypatch, changed)
    assert_error(
        check_deliverable_module.check_deliverable(source, root),
        "exact generated marker",
    )

    wrong = marker("0" * 64, generator_digest).encode()
    changed = mutate_matching_output(
        root,
        outputs,
        "reports/site/index.html",
        lambda page: page.replace(generated, wrong, 1),
    )
    patch_outputs(monkeypatch, changed)
    assert_error(
        check_deliverable_module.check_deliverable(source, root),
        "exact generated marker",
    )


def test_checker_rejects_untrusted_evidence_helper_identity_or_symlink(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    patch_outputs(monkeypatch, outputs)
    monkeypatch.setattr(
        check_deliverable_module.evidence_io,
        "__file__",
        str(tmp_path / "outside-evidence_io.py"),
    )
    assert_error(
        check_deliverable_module.check_deliverable(source, root),
        "imported evidence helper is not the canonical repository component",
    )

    monkeypatch.setattr(
        check_deliverable_module.evidence_io,
        "__file__",
        str(root / "scripts/evidence_io.py"),
    )
    helper = root / "scripts/evidence_io.py"
    helper_bytes = helper.read_bytes()
    helper.unlink()
    outside = tmp_path / "outside-evidence_io.py"
    outside.write_bytes(helper_bytes)
    helper.symlink_to(outside)
    assert_error(
        check_deliverable_module.check_deliverable(source, root),
        "evidence helper uses a symlink component",
    )


@pytest.mark.parametrize(
    "component",
    (
        "evidence_io.py",
        "candidate_evidence.py",
        "check-promotion.py",
        "report_model.py",
    ),
)
def test_fresh_checker_rejects_initial_dependency_symlink_before_execution(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    tmp_path: Path,
    component: str,
) -> None:
    root, source, _, _, _ = deliverable_repo
    sentinel = tmp_path / "executed"
    malicious = tmp_path / "malicious-evidence_io.py"
    malicious.write_text(
        "from pathlib import Path\n"
        f"Path({str(sentinel)!r}).write_text('executed')\n",
        encoding="utf-8",
    )
    dependency = root / "scripts" / component
    dependency.unlink()
    dependency.symlink_to(malicious)

    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/check-deliverable.py"),
            "--source",
            str(source),
            "--repo-root",
            str(root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "report checker dependency bootstrap failed" in result.stderr
    assert "Traceback" not in result.stderr
    assert not sentinel.exists()


@pytest.mark.parametrize(
    "component",
    (
        "evidence_io.py",
        "candidate_evidence.py",
        "check-promotion.py",
        "report_model.py",
    ),
)
def test_checker_independently_verifies_the_generator_digest_contract(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
    component: str,
) -> None:
    root, source, _, generator_digest, outputs = deliverable_repo
    patch_outputs(monkeypatch, outputs)
    dependency = root / "scripts" / component
    dependency.write_bytes(dependency.read_bytes() + b"# post-import change\n")
    monkeypatch.setattr(
        check_deliverable_module.report_model,
        "report_generator_digest",
        lambda *_: generator_digest,
    )

    assert_error(
        check_deliverable_module.check_deliverable(source, root),
        "report generator digest contract drifted",
    )


def test_external_https_is_allowed_only_as_anchor_navigation(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    changed = mutate_matching_output(
        root,
        outputs,
        "reports/site/index.html",
        lambda page: page.replace(
            b"<main",
            b'<a href="https://example.com/reference">reference</a><main',
            1,
        ),
    )
    patch_outputs(monkeypatch, changed)
    assert check_deliverable_module.check_deliverable(source, root) == []


def test_cli_reports_success_for_real_renderer(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
) -> None:
    root, source, source_digest, generator_digest, _ = deliverable_repo
    project = json.loads(source.read_text(encoding="utf-8"))
    real_outputs = report_model.render_outputs(
        project, source_digest, generator_digest
    )
    write_outputs(root, real_outputs)
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/check-deliverable.py"),
            "--source",
            str(source),
            "--repo-root",
            str(root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "deliverable check: pass (10 generated files)\n"
