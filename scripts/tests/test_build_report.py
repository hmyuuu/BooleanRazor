from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest


SCRIPTS = Path(__file__).resolve().parents[1]
BUILDER_PATH = SCRIPTS / "build-report.py"
REPORT_MODEL_PATH = SCRIPTS / "report_model.py"
EVIDENCE_IO_PATH = SCRIPTS / "evidence_io.py"
CANDIDATE_EVIDENCE_PATH = SCRIPTS / "candidate_evidence.py"
CHECK_PROMOTION_PATH = SCRIPTS / "check-promotion.py"
REPORT_MODEL_TEST_PATH = Path(__file__).with_name("test_report_model.py")
GENERATOR_COMPONENTS = (
    ("scripts/evidence_io.py", EVIDENCE_IO_PATH),
    ("scripts/candidate_evidence.py", CANDIDATE_EVIDENCE_PATH),
    ("scripts/check-promotion.py", CHECK_PROMOTION_PATH),
    ("scripts/report_model.py", REPORT_MODEL_PATH),
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


def load_module(name: str, path: Path) -> ModuleType:
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def valid_project(revision: str) -> dict[str, object]:
    """Share the model fixture so schema additions break both suites visibly."""
    fixture_module = load_module(
        "_build_report_model_fixture",
        REPORT_MODEL_TEST_PATH,
    )
    factory = getattr(fixture_module, "valid_project")
    return copy.deepcopy(factory(revision))


@pytest.fixture
def report_repo(tmp_path: Path) -> tuple[Path, Path, ModuleType]:
    root = tmp_path / "repo"
    scripts = root / "scripts"
    evidence = root / "evidence"
    scripts.mkdir(parents=True)
    evidence.mkdir()
    shutil.copyfile(BUILDER_PATH, scripts / "build-report.py")
    shutil.copyfile(REPORT_MODEL_PATH, scripts / "report_model.py")
    shutil.copyfile(EVIDENCE_IO_PATH, scripts / "evidence_io.py")
    shutil.copyfile(
        CANDIDATE_EVIDENCE_PATH,
        scripts / "candidate_evidence.py",
    )
    shutil.copyfile(CHECK_PROMOTION_PATH, scripts / "check-promotion.py")
    (evidence / "base.md").write_text("fixture evidence\n", encoding="utf-8")
    git(root.parent, "init", "-q", str(root))
    git(root, "add", "evidence/base.md", "scripts/report_model.py")
    git(
        root,
        "-c",
        "user.name=BooleanRazor Report Tests",
        "-c",
        "user.email=report-tests@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        "fixture evidence",
    )
    revision = git(root, "rev-parse", "HEAD").stdout.strip()
    source = root / "reports/data/project.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(canonical(valid_project(revision)))
    builder = load_module(
        f"_build_report_{tmp_path.name.replace('-', '_')}",
        scripts / "build-report.py",
    )
    return root, source, builder


def run_builder(
    builder: ModuleType,
    root: Path,
    source: Path,
) -> int:
    return builder.main(
        ["--source", str(source), "--repo-root", str(root)]
    )


def generated_files(builder: ModuleType, root: Path) -> dict[str, bytes]:
    return {
        relative: (root / relative).read_bytes()
        for relative in builder.report_model.OUTPUT_PATHS
    }


def expected_outputs(
    builder: ModuleType,
    root: Path,
    source: Path,
) -> dict[str, bytes]:
    project, source_digest = builder.report_model.load_project(source, root)
    generator = builder.generator_digest(
        (root / "scripts/report_model.py").read_bytes(),
        (root / "scripts/evidence_io.py").read_bytes(),
        (root / "scripts/candidate_evidence.py").read_bytes(),
        (root / "scripts/check-promotion.py").read_bytes(),
    )
    return builder.report_model.render_outputs(
        project,
        source_digest,
        generator,
    )


def success_output(builder: ModuleType) -> str:
    paths = "".join(
        f"{relative}\n"
        for relative in sorted(builder.report_model.OUTPUT_PATHS)
    )
    return f"report build: wrote 10 generated files\n{paths}"


def test_report_builder_cli_exists() -> None:
    assert BUILDER_PATH.is_file()


def test_first_generation_and_identical_regeneration_succeed(
    report_repo: tuple[Path, Path, ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, source, builder = report_repo

    assert run_builder(builder, root, source) == 0
    first = generated_files(builder, root)
    assert first == expected_outputs(builder, root, source)
    assert capsys.readouterr().out == success_output(builder)

    preserved = root / "docs/STATUS.md"
    preserved.chmod(0o640)
    assert run_builder(builder, root, source) == 0
    assert generated_files(builder, root) == first
    assert stat.S_IMODE(preserved.stat().st_mode) == 0o640
    assert not list(root.rglob(".*.report-*"))


def test_builder_loads_and_hashes_the_exact_sibling_generator(
    report_repo: tuple[Path, Path, ModuleType],
) -> None:
    root, source, builder = report_repo

    assert Path(builder.report_model.__file__) == (
        root / "scripts/report_model.py"
    )
    assert Path(builder.report_model._evidence_io.__file__) == (
        root / "scripts/evidence_io.py"
    )
    assert {
        relative: Path(module.__file__)
        for relative, module in builder.PINNED_GENERATOR_MODULES.items()
    } == {
        "scripts/evidence_io.py": root / "scripts/evidence_io.py",
        "scripts/candidate_evidence.py": (
            root / "scripts/candidate_evidence.py"
        ),
        "scripts/check-promotion.py": root / "scripts/check-promotion.py",
    }
    assert run_builder(builder, root, source) == 0
    digest = builder.generator_digest(
        (root / "scripts/report_model.py").read_bytes(),
        (root / "scripts/evidence_io.py").read_bytes(),
        (root / "scripts/candidate_evidence.py").read_bytes(),
        (root / "scripts/check-promotion.py").read_bytes(),
    )
    assert digest.encode("ascii") in (root / "docs/STATUS.md").read_bytes()


def test_combined_generator_digest_uses_explicit_domain_and_file_frames(
    report_repo: tuple[Path, Path, ModuleType],
) -> None:
    root, _, builder = report_repo
    evidence = (root / "scripts/evidence_io.py").read_bytes()
    candidate = (root / "scripts/candidate_evidence.py").read_bytes()
    promotion = (root / "scripts/check-promotion.py").read_bytes()
    model = (root / "scripts/report_model.py").read_bytes()
    assert builder.GENERATOR_DIGEST_DOMAIN == (
        b"BooleanRazor deterministic report generator v2\0"
    )
    assert builder.GENERATOR_COMPONENT_PATHS == tuple(
        relative for relative, _ in GENERATOR_COMPONENTS
    )
    framed = bytearray(builder.GENERATOR_DIGEST_DOMAIN)
    for relative, content in (
        ("scripts/evidence_io.py", evidence),
        ("scripts/candidate_evidence.py", candidate),
        ("scripts/check-promotion.py", promotion),
        ("scripts/report_model.py", model),
    ):
        name = relative.encode("utf-8")
        framed.extend(len(name).to_bytes(4, "big"))
        framed.extend(name)
        framed.extend(len(content).to_bytes(8, "big"))
        framed.extend(content)
    assert builder.generator_digest(
        model,
        evidence,
        candidate,
        promotion,
    ) == hashlib.sha256(framed).hexdigest()


def test_builder_rejects_model_generator_digest_contract_drift(
    report_repo: tuple[Path, Path, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, source, builder = report_repo
    monkeypatch.setattr(
        builder.report_model,
        "report_generator_digest",
        lambda *_: "0" * 64,
    )

    assert run_builder(builder, root, source) == 1
    assert "generator digest contract drifted" in capsys.readouterr().err
    assert not any(
        (root / path).exists()
        for path in builder.report_model.OUTPUT_PATHS
    )


@pytest.mark.parametrize(
    "relative",
    tuple(relative for relative, _ in GENERATOR_COMPONENTS),
)
@pytest.mark.parametrize("swap_kind", ("content", "symlink"))
def test_generator_component_swap_is_rejected_without_execution(
    report_repo: tuple[Path, Path, ModuleType],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    relative: str,
    swap_kind: str,
) -> None:
    root, source, builder = report_repo
    sentinel = tmp_path / "executed"
    malicious = tmp_path / f"malicious-{Path(relative).name}"
    malicious.write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('bad')\n",
        encoding="utf-8",
    )
    component = root / relative
    if swap_kind == "symlink":
        component.unlink()
        component.symlink_to(malicious)
    else:
        component.write_bytes(malicious.read_bytes())

    assert run_builder(builder, root, source) == 1
    error = capsys.readouterr().err
    assert (
        "symlink" in error
        if swap_kind == "symlink"
        else "changed since import" in error
    )
    assert not sentinel.exists()
    assert not any(
        (root / path).exists()
        for path in builder.report_model.OUTPUT_PATHS
    )


@pytest.mark.parametrize(
    "relative",
    tuple(relative for relative, _ in GENERATOR_COMPONENTS),
)
@pytest.mark.parametrize("case", ("symlink", "corrupt", "system-exit"))
def test_cli_reports_initial_generator_bootstrap_failure_without_traceback(
    tmp_path: Path,
    case: str,
    relative: str,
) -> None:
    root = tmp_path / "repo"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(BUILDER_PATH, scripts / "build-report.py")
    for component_relative, source in GENERATOR_COMPONENTS:
        destination = root / component_relative
        if component_relative != relative:
            shutil.copyfile(source, destination)
    sentinel = tmp_path / "executed"
    component = root / relative
    if case == "symlink":
        malicious = tmp_path / f"malicious-{Path(relative).name}"
        malicious.write_text(
            f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('bad')\n",
            encoding="utf-8",
        )
        component.symlink_to(malicious)
    else:
        component.write_bytes(
            b"raise SystemExit('injected component exit')\n"
            if case == "system-exit"
            else b"this is not valid Python (\n"
        )

    result = subprocess.run(
        [
            sys.executable,
            str(scripts / "build-report.py"),
            "--source",
            str(root / "reports/data/project.json"),
            "--repo-root",
            str(root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.startswith(
        "report build failed: report generator bootstrap failed:"
    )
    assert "Traceback" not in result.stderr
    assert not sentinel.exists()


@pytest.mark.parametrize("case", ("outside", "alternate", "missing-parent"))
def test_noncanonical_or_missing_source_fails_without_outputs(
    report_repo: tuple[Path, Path, ModuleType],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    case: str,
) -> None:
    root, source, builder = report_repo
    if case == "outside":
        requested = tmp_path / "outside.json"
        requested.write_bytes(source.read_bytes())
    elif case == "alternate":
        requested = root / "reports/data/alternate.json"
        requested.write_bytes(source.read_bytes())
    else:
        source.unlink()
        source.parent.rmdir()
        requested = source

    assert run_builder(builder, root, requested) == 1
    assert "report build failed:" in capsys.readouterr().err
    assert not any((root / path).exists() for path in builder.report_model.OUTPUT_PATHS)


def test_symlinked_repo_root_is_rejected(
    report_repo: tuple[Path, Path, ModuleType],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, builder = report_repo
    linked_root = tmp_path / "linked-repo"
    linked_root.symlink_to(root, target_is_directory=True)

    assert run_builder(
        builder,
        linked_root,
        linked_root / "reports/data/project.json",
    ) == 1
    assert "symlink" in capsys.readouterr().err
    assert not any((root / path).exists() for path in builder.report_model.OUTPUT_PATHS)


def test_renderer_must_return_exact_canonical_output_keys(
    report_repo: tuple[Path, Path, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, source, builder = report_repo
    rendered = expected_outputs(builder, root, source)
    rendered["reports/site/escape.html"] = b"unexpected\n"
    monkeypatch.setattr(
        builder.report_model,
        "render_outputs",
        lambda *_: rendered,
    )

    assert run_builder(builder, root, source) == 1
    assert "output keys" in capsys.readouterr().err
    assert not any((root / path).exists() for path in builder.report_model.OUTPUT_PATHS)


def test_oversized_rendered_content_fails_before_any_output_mutation(
    report_repo: tuple[Path, Path, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, source, builder = report_repo
    rendered = expected_outputs(builder, root, source)
    rendered["docs/STATUS.md"] = b"x" * (builder.MAX_OUTPUT_BYTES + 1)
    monkeypatch.setattr(
        builder.report_model,
        "render_outputs",
        lambda *_: rendered,
    )

    assert run_builder(builder, root, source) == 1
    assert "maximum size" in capsys.readouterr().err
    assert not any((root / path).exists() for path in builder.report_model.OUTPUT_PATHS)


def test_symlink_output_is_rejected_without_touching_its_target(
    report_repo: tuple[Path, Path, ModuleType],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, source, builder = report_repo
    assert run_builder(builder, root, source) == 0
    capsys.readouterr()
    before = generated_files(builder, root)
    before = generated_files(builder, root)
    output = root / "reports/site/index.html"
    target = tmp_path / "outside-index.html"
    target.write_bytes(b"outside sentinel\n")
    output.unlink()
    output.symlink_to(target)

    assert run_builder(builder, root, source) == 1
    assert "regular" in capsys.readouterr().err
    assert target.read_bytes() == b"outside sentinel\n"
    for relative, content in before.items():
        if relative != "reports/site/index.html":
            assert (root / relative).read_bytes() == content


def test_symlink_output_parent_is_rejected_without_outside_writes(
    report_repo: tuple[Path, Path, ModuleType],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, source, builder = report_repo
    outside = tmp_path / "outside-site"
    outside.mkdir()
    site = root / "reports/site"
    site.symlink_to(outside, target_is_directory=True)

    assert run_builder(builder, root, source) == 1
    assert "symlink" in capsys.readouterr().err
    assert list(outside.iterdir()) == []
    assert not any((root / path).is_file() for path in builder.report_model.OUTPUT_PATHS)


def test_nondirectory_parent_and_nonregular_destination_are_rejected(
    report_repo: tuple[Path, Path, ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, source, builder = report_repo
    (root / "docs").write_bytes(b"not a directory\n")

    assert run_builder(builder, root, source) == 1
    assert "directory" in capsys.readouterr().err
    assert not any((root / path).is_file() for path in builder.report_model.OUTPUT_PATHS)

    (root / "docs").unlink()
    (root / "docs/STATUS.md").mkdir(parents=True)
    assert run_builder(builder, root, source) == 1
    assert "regular" in capsys.readouterr().err
    assert not any((root / path).is_file() for path in builder.report_model.OUTPUT_PATHS)


def test_destination_replacement_race_fails_before_publication(
    report_repo: tuple[Path, Path, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, source, builder = report_repo
    assert run_builder(builder, root, source) == 0
    capsys.readouterr()
    before = generated_files(builder, root)
    original_snapshot = builder._snapshot_destination
    target = "EXPERIMENT_INDEX.md"
    calls = 0

    def racing_snapshot(
        parent: int,
        name: str,
        label: str,
    ) -> object:
        nonlocal calls
        if name == target:
            calls += 1
            if calls == 2:
                descriptor = os.open(
                    name,
                    os.O_WRONLY | os.O_TRUNC,
                    dir_fd=parent,
                )
                try:
                    os.write(descriptor, b"raced destination\n")
                finally:
                    os.close(descriptor)
        return original_snapshot(parent, name, label)

    monkeypatch.setattr(builder, "_snapshot_destination", racing_snapshot)
    assert run_builder(builder, root, source) == 1
    assert "changed before publication" in capsys.readouterr().err
    assert (root / "docs/EXPERIMENT_INDEX.md").read_bytes() == (
        b"raced destination\n"
    )
    for relative, content in before.items():
        if relative != "docs/EXPERIMENT_INDEX.md":
            assert (root / relative).read_bytes() == content


def test_failed_backup_cleanup_preserves_the_rollback_name(
    report_repo: tuple[Path, Path, ModuleType],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, builder = report_repo
    parent_path = tmp_path / "transaction"
    parent_path.mkdir()
    parent = os.open(parent_path, os.O_RDONLY)
    backup = ".STATUS.md.report-backup-fault"
    (parent_path / backup).write_bytes(b"rollback state\n")
    publication = builder.Publication(
        relative="docs/STATUS.md",
        parent_relative=("docs",),
        parent=parent,
        name="STATUS.md",
        content=b"new\n",
        original=builder.DestinationSnapshot(False),
        backup=backup,
    )
    original_unlink = builder.os.unlink

    def failing_unlink(
        name: str,
        *,
        dir_fd: int,
    ) -> None:
        if name == backup:
            raise PermissionError("injected cleanup failure")
        original_unlink(name, dir_fd=dir_fd)

    monkeypatch.setattr(builder.os, "unlink", failing_unlink)
    try:
        with pytest.raises(builder.BuildError, match="failed to clean"):
            builder._cleanup_transaction([publication])
        assert publication.backup == backup
        assert (parent_path / backup).read_bytes() == b"rollback state\n"
    finally:
        os.close(parent)


def test_postcommit_cleanup_failure_keeps_one_complete_output_generation(
    report_repo: tuple[Path, Path, ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, source, builder = report_repo
    assert run_builder(builder, root, source) == 0
    capsys.readouterr()
    rendered = expected_outputs(builder, root, source)
    rendered["docs/STATUS.md"] += b"\npostcommit generation\n"
    monkeypatch.setattr(
        builder.report_model,
        "render_outputs",
        lambda *_: dict(rendered),
    )
    original_unlink = builder.os.unlink

    def failing_backup_unlink(
        name: str,
        *,
        dir_fd: int,
    ) -> None:
        if ".report-backup-" in name:
            raise PermissionError("injected postcommit cleanup failure")
        original_unlink(name, dir_fd=dir_fd)

    monkeypatch.setattr(builder.os, "unlink", failing_backup_unlink)
    assert run_builder(builder, root, source) == 1
    assert "fully committed" in capsys.readouterr().err
    assert generated_files(builder, root) == rendered
    assert list(root.rglob(".*.report-backup-*"))


def test_parent_replacement_race_is_detected_without_outside_publication(
    report_repo: tuple[Path, Path, ModuleType],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, source, builder = report_repo
    assert run_builder(builder, root, source) == 0
    capsys.readouterr()
    before = generated_files(builder, root)
    outside = tmp_path / "outside-docs"
    outside.mkdir()
    moved = root / "docs.checked"
    original_replace = builder.os.replace
    raced = False

    def racing_replace(
        source_name: str,
        destination_name: str,
        *,
        src_dir_fd: int,
        dst_dir_fd: int,
    ) -> None:
        nonlocal raced
        if not raced:
            raced = True
            (root / "docs").rename(moved)
            (root / "docs").symlink_to(outside, target_is_directory=True)
        original_replace(
            source_name,
            destination_name,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(builder.os, "replace", racing_replace)
    assert run_builder(builder, root, source) == 1
    assert "changed during publication" in capsys.readouterr().err
    assert list(outside.iterdir()) == []
    assert not list(moved.glob(".*.report-*"))
    for relative, content in before.items():
        path = (
            moved / Path(relative).relative_to("docs")
            if relative.startswith("docs/")
            else root / relative
        )
        assert path.read_bytes() == content
