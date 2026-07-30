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


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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


def git(root: Path, *args: str) -> None:
    subprocess.run(
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


def valid_project() -> dict[str, object]:
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
                "evidence": [evidence()],
                "limitations": ["Public evaluation has not run."],
                "missing_proof": ["Sealed confirmation."],
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
            "title": "BooleanRazor",
        },
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
        f"{source_digest}; report model SHA-256: {generator_digest} -->"
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
        "reports/site/assets/report.js": b'"use strict";\n',
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
) -> tuple[Path, Path, str, str, dict[str, bytes]]:
    root = tmp_path / "repo"
    (root / "evidence").mkdir(parents=True)
    (root / "evidence/base.md").write_text("evidence\n", encoding="utf-8")
    (root / "scripts").mkdir()
    (root / "scripts/report_model.py").write_bytes(
        (SCRIPTS / "report_model.py").read_bytes()
    )
    git(root.parent, "init", "-q", str(root))
    git(root, "add", "evidence/base.md", "scripts/report_model.py")
    source = root / "reports/data/project.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(canonical(valid_project()))
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    generator_digest = hashlib.sha256(
        (root / "scripts/report_model.py").read_bytes()
    ).hexdigest()
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
    ("removed", "fragment"),
    (
        (b"@media print", "print stylesheet"),
        (b":focus-visible", "visible focus style"),
    ),
)
def test_stylesheet_accessibility_contract(
    deliverable_repo: tuple[Path, Path, str, str, dict[str, bytes]],
    monkeypatch: pytest.MonkeyPatch,
    removed: bytes,
    fragment: str,
) -> None:
    root, source, _, _, outputs = deliverable_repo
    changed = mutate_matching_output(
        root,
        outputs,
        "reports/site/assets/report.css",
        lambda css: css.replace(removed, b"removed", 1),
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
    real_outputs = report_model.render_outputs(
        valid_project(), source_digest, generator_digest
    )
    write_outputs(root, real_outputs)
    result = subprocess.run(
        [
            sys.executable,
            str(CHECKER_PATH),
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
