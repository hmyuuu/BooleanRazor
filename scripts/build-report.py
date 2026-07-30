#!/usr/bin/env python3
"""Build the deterministic BooleanRazor web and Markdown report."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import secrets
import stat
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import ModuleType


MAX_GENERATOR_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
CANONICAL_SOURCE = PurePosixPath("reports/data/project.json")
DEFAULT_OUTPUT_MODE = 0o644
GENERATOR_DIGEST_DOMAIN = (
    b"BooleanRazor deterministic report generator v2\0"
)
GENERATOR_COMPONENT_PATHS = (
    "scripts/evidence_io.py",
    "scripts/candidate_evidence.py",
    "scripts/check-promotion.py",
    "scripts/report_model.py",
)
DIRECTORY_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
)
READ_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


class BuildError(ValueError):
    """The report cannot be generated without crossing a trust boundary."""


@dataclass(frozen=True)
class DestinationSnapshot:
    exists: bool
    device: int = 0
    inode: int = 0
    mode: int = 0
    size: int = 0
    modified_ns: int = 0
    changed_ns: int = 0


@dataclass
class Publication:
    relative: str
    parent_relative: tuple[str, ...]
    parent: int
    name: str
    content: bytes
    original: DestinationSnapshot
    temporary: str | None = None
    backup: str | None = None
    published: bool = False


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _absolute_components(path: Path, label: str) -> tuple[str, ...]:
    absolute = _absolute_lexical(path)
    if not absolute.is_absolute() or not absolute.anchor:
        raise BuildError(f"{label} must be an absolute path")
    components = absolute.parts[1:]
    if not components or any(part in {"", ".", ".."} for part in components):
        raise BuildError(f"{label} has an invalid path component")
    return components


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _open_absolute_directory(path: Path, label: str) -> int:
    components = _absolute_components(path, label)
    descriptor = os.open(Path(path.anchor).anchor or "/", DIRECTORY_FLAGS)
    try:
        for component in components:
            child = os.open(component, DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        raise BuildError(
            f"{label} must be an existing directory without symlinks"
        ) from exc


def _open_regular_path(path: Path, label: str) -> int:
    absolute = _absolute_lexical(path)
    parent = _open_absolute_directory(absolute.parent, f"{label} parent")
    try:
        try:
            descriptor = os.open(absolute.name, READ_FLAGS, dir_fd=parent)
        except OSError as exc:
            raise BuildError(
                f"{label} must be a regular file without symlinks"
            ) from exc
    finally:
        os.close(parent)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise BuildError(f"{label} must be a regular file")
    return descriptor


def _read_regular_once(path: Path, label: str, maximum: int) -> bytes:
    descriptor = _open_regular_path(path, label)
    try:
        before = os.fstat(descriptor)
        if before.st_size > maximum:
            raise BuildError(f"{label} exceeds maximum size")
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        if len(content) > maximum:
            raise BuildError(f"{label} exceeds maximum size")
        after = os.fstat(descriptor)
        before_state = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_state = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_state != after_state:
            raise BuildError(f"{label} changed while being read")
        return content
    finally:
        os.close(descriptor)


def _read_stable_regular(path: Path, label: str, maximum: int) -> bytes:
    first = _read_regular_once(path, label, maximum)
    second = _read_regular_once(path, label, maximum)
    if first != second:
        raise BuildError(f"{label} changed between reads")
    return first


def _execute_exact_module(
    module_name: str,
    path: Path,
    source: bytes,
) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None:
        raise ImportError(f"cannot create module specification for {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        code = compile(source, os.fspath(path), "exec")
        exec(code, module.__dict__)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


class _PinnedImportlibUtil:
    def __init__(
        self,
        protected_names: frozenset[str],
    ) -> None:
        self._protected_names = protected_names

    def spec_from_file_location(
        self,
        module_name: str,
        location: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *args: object,
        **kwargs: object,
    ) -> object:
        if module_name in self._protected_names:
            raise BuildError(
                f"pinned generator module {module_name} changed during use"
            )
        return importlib.util.spec_from_file_location(
            module_name,
            location,
            *args,
            **kwargs,
        )

    def __getattr__(self, name: str) -> object:
        return getattr(importlib.util, name)


class _PinnedImportlib:
    def __init__(self, protected_names: frozenset[str]) -> None:
        self.util = _PinnedImportlibUtil(protected_names)

    def __getattr__(self, name: str) -> object:
        return getattr(importlib, name)


def _load_sibling_generator() -> tuple[
    ModuleType,
    dict[str, bytes],
    dict[str, ModuleType],
]:
    scripts = _absolute_lexical(Path(__file__).parent)
    paths = {
        relative: scripts / PurePosixPath(relative).name
        for relative in GENERATOR_COMPONENT_PATHS
    }
    labels = {
        "scripts/evidence_io.py": "report evidence helper",
        "scripts/candidate_evidence.py": "candidate evidence helper",
        "scripts/check-promotion.py": "promotion checker",
        "scripts/report_model.py": "report model",
    }
    sources = {
        relative: _read_stable_regular(
            path,
            labels[relative],
            MAX_GENERATOR_BYTES,
        )
        for relative, path in paths.items()
    }
    evidence_module = _execute_exact_module(
        "evidence_io",
        paths["scripts/evidence_io.py"],
        sources["scripts/evidence_io.py"],
    )
    candidate_module = _execute_exact_module(
        "candidate_evidence",
        paths["scripts/candidate_evidence.py"],
        sources["scripts/candidate_evidence.py"],
    )
    promotion_module_name = "_booleanrazor_report_check_promotion"
    promotion_module = _execute_exact_module(
        promotion_module_name,
        paths["scripts/check-promotion.py"],
        sources["scripts/check-promotion.py"],
    )
    protected_names = frozenset(
        {"evidence_io", "candidate_evidence", promotion_module_name}
    )
    original_spec_factory = importlib.util.spec_from_file_location

    def guarded_spec_factory(
        module_name: str,
        location: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *args: object,
        **kwargs: object,
    ) -> object:
        # report_model has sibling-module fallbacks.  If a symlink race makes
        # it reject a pinned module, fail closed instead of executing newly
        # named filesystem bytes.
        if module_name in protected_names:
            raise BuildError(
                f"pinned generator module {module_name} changed during import"
            )
        return original_spec_factory(module_name, location, *args, **kwargs)

    importlib.util.spec_from_file_location = guarded_spec_factory
    try:
        model_module = _execute_exact_module(
            "_booleanrazor_build_report_model",
            paths["scripts/report_model.py"],
            sources["scripts/report_model.py"],
        )
    finally:
        importlib.util.spec_from_file_location = original_spec_factory
    if getattr(model_module, "_evidence_io", None) is not evidence_module:
        raise BuildError(
            "report model did not retain the exact pinned evidence helper"
        )
    model_module.importlib = _PinnedImportlib(protected_names)
    task4_module = model_module._load_task4_module()
    if (
        task4_module is not promotion_module
        or sys.modules.get("candidate_evidence") is not candidate_module
    ):
        raise BuildError(
            "report model did not retain the exact pinned promotion modules"
        )
    pinned_modules = {
        "scripts/evidence_io.py": evidence_module,
        "scripts/candidate_evidence.py": candidate_module,
        "scripts/check-promotion.py": promotion_module,
    }
    return model_module, sources, pinned_modules


def generator_digest(
    report_model_bytes: bytes,
    evidence_io_bytes: bytes,
    candidate_evidence_bytes: bytes,
    check_promotion_bytes: bytes,
) -> str:
    """Hash the exact executable generator components with named framing."""
    if not all(
        isinstance(content, bytes)
        for content in (
            report_model_bytes,
            evidence_io_bytes,
            candidate_evidence_bytes,
            check_promotion_bytes,
        )
    ):
        raise BuildError("generator components must be exact bytes")
    components = (
        ("scripts/evidence_io.py", evidence_io_bytes),
        ("scripts/candidate_evidence.py", candidate_evidence_bytes),
        ("scripts/check-promotion.py", check_promotion_bytes),
        ("scripts/report_model.py", report_model_bytes),
    )
    digest = hashlib.sha256()
    digest.update(GENERATOR_DIGEST_DOMAIN)
    for relative, content in components:
        name = relative.encode("utf-8")
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


report_model: ModuleType | None
IMPORTED_GENERATOR_BYTES: dict[str, bytes] = {}
PINNED_GENERATOR_MODULES: dict[str, ModuleType] = {}
BOOTSTRAP_ERROR: str | None = None
try:
    (
        report_model,
        IMPORTED_GENERATOR_BYTES,
        PINNED_GENERATOR_MODULES,
    ) = _load_sibling_generator()
except KeyboardInterrupt:
    raise
except BaseException as exc:
    # Module import must remain safe enough for main() to own the CLI
    # diagnostic.  In particular, do not let a rejected symlink or invalid
    # helper source escape as a raw interpreter traceback.
    report_model = None
    detail = " ".join(str(exc).split()) or type(exc).__name__
    BOOTSTRAP_ERROR = f"report generator bootstrap failed: {detail}"

REPORT_MODEL_ERROR = (
    report_model.ModelError if report_model is not None else BuildError
)


def _require_report_model() -> ModuleType:
    if BOOTSTRAP_ERROR is not None or report_model is None:
        raise BuildError(
            BOOTSTRAP_ERROR or "report generator bootstrap failed"
        )
    return report_model


def _generator_component_paths(root: Path) -> dict[str, Path]:
    return {
        relative: _absolute_lexical(
            root.joinpath(*PurePosixPath(relative).parts)
        )
        for relative in GENERATOR_COMPONENT_PATHS
    }


def _read_generator_sources(root: Path) -> dict[str, bytes]:
    labels = {
        "scripts/evidence_io.py": "report evidence helper",
        "scripts/candidate_evidence.py": "candidate evidence helper",
        "scripts/check-promotion.py": "promotion checker",
        "scripts/report_model.py": "report model",
    }
    return {
        relative: _read_stable_regular(
            path,
            labels[relative],
            MAX_GENERATOR_BYTES,
        )
        for relative, path in _generator_component_paths(root).items()
    }


def _digest_generator_sources(sources: dict[str, bytes]) -> str:
    if set(sources) != set(GENERATOR_COMPONENT_PATHS):
        raise BuildError("report generator component set drifted")
    return generator_digest(
        sources["scripts/report_model.py"],
        sources["scripts/evidence_io.py"],
        sources["scripts/candidate_evidence.py"],
        sources["scripts/check-promotion.py"],
    )


def _relative_parts(relative: str, label: str) -> tuple[str, ...]:
    if not isinstance(relative, str):
        raise BuildError(f"{label} must be a string")
    pure = PurePosixPath(relative)
    parts = pure.parts
    if (
        pure.is_absolute()
        or not parts
        or any(part in {"", ".", ".."} for part in parts)
        or str(pure) != relative
    ):
        raise BuildError(f"{label} must be a canonical repository path")
    return parts


def _open_output_parent(
    root: int,
    parent_parts: tuple[str, ...],
    label: str,
) -> int:
    descriptor = os.dup(root)
    try:
        for component in parent_parts:
            try:
                child = os.open(component, DIRECTORY_FLAGS, dir_fd=descriptor)
            except FileNotFoundError:
                try:
                    os.mkdir(component, 0o755, dir_fd=descriptor)
                except FileExistsError:
                    pass
                child = os.open(component, DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        raise BuildError(
            f"{label} must be a directory without symlinks"
        ) from exc


def _open_existing_parent(
    root: int,
    parent_parts: tuple[str, ...],
    label: str,
) -> int:
    descriptor = os.dup(root)
    try:
        for component in parent_parts:
            child = os.open(component, DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        raise BuildError(
            f"{label} changed during publication or became a symlink"
        ) from exc


def _snapshot_destination(
    parent: int,
    name: str,
    label: str,
) -> DestinationSnapshot:
    try:
        state = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return DestinationSnapshot(False)
    except OSError as exc:
        raise BuildError(f"{label} cannot be inspected") from exc
    if not stat.S_ISREG(state.st_mode):
        raise BuildError(
            f"{label} must be absent or an existing regular file"
        )
    return DestinationSnapshot(
        True,
        state.st_dev,
        state.st_ino,
        state.st_mode,
        state.st_size,
        state.st_mtime_ns,
        state.st_ctime_ns,
    )


def _write_all(descriptor: int, content: bytes) -> None:
    remaining = memoryview(content)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise BuildError("atomic report staging made no progress")
        remaining = remaining[written:]


def _reserve_name(parent: int, name: str, kind: str) -> str:
    for _ in range(32):
        candidate = f".{name}.report-{kind}-{secrets.token_hex(16)}"
        try:
            os.stat(candidate, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return candidate
        except OSError as exc:
            raise BuildError("cannot inspect report transaction name") from exc
    raise BuildError("cannot reserve report transaction name")


def _stage(publication: Publication) -> None:
    mode = (
        stat.S_IMODE(publication.original.mode)
        if publication.original.exists
        else DEFAULT_OUTPUT_MODE
    )
    for _ in range(32):
        temporary = _reserve_name(
            publication.parent,
            publication.name,
            "stage",
        )
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            descriptor = os.open(
                temporary,
                flags,
                mode,
                dir_fd=publication.parent,
            )
        except FileExistsError:
            continue
        publication.temporary = temporary
        try:
            _write_all(descriptor, publication.content)
            os.fchmod(descriptor, mode)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return
    raise BuildError(f"cannot stage {publication.relative}")


def _assert_parent_reachable(
    root_path: Path,
    root: int,
    publication: Publication,
    phase: str,
) -> None:
    reopened_root = _open_absolute_directory(root_path, "repository root")
    try:
        if not _same_identity(os.fstat(root), os.fstat(reopened_root)):
            raise BuildError(f"repository root changed {phase}")
        reopened_parent = _open_existing_parent(
            reopened_root,
            publication.parent_relative,
            f"{publication.relative} parent",
        )
        try:
            if not _same_identity(
                os.fstat(publication.parent),
                os.fstat(reopened_parent),
            ):
                raise BuildError(
                    f"{publication.relative} parent changed {phase}"
                )
        finally:
            os.close(reopened_parent)
    except BuildError as exc:
        message = str(exc)
        if "changed during publication" in message:
            raise
        raise BuildError(
            f"{publication.relative} parent changed {phase}: {message}"
        ) from exc
    finally:
        os.close(reopened_root)


def _read_published(publication: Publication) -> bytes:
    try:
        descriptor = os.open(
            publication.name,
            READ_FLAGS,
            dir_fd=publication.parent,
        )
    except OSError as exc:
        raise BuildError(
            f"{publication.relative} disappeared during publication"
        ) from exc
    try:
        state = os.fstat(descriptor)
        if not stat.S_ISREG(state.st_mode):
            raise BuildError(
                f"{publication.relative} changed during publication"
            )
        chunks: list[bytes] = []
        remaining = MAX_OUTPUT_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _cleanup_transaction(publications: list[Publication]) -> None:
    failures: list[str] = []
    for publication in publications:
        for attribute in ("temporary", "backup"):
            name = getattr(publication, attribute)
            if name is None:
                continue
            try:
                os.unlink(name, dir_fd=publication.parent)
            except FileNotFoundError:
                setattr(publication, attribute, None)
            except OSError:
                failures.append(f"{publication.relative} {attribute}")
            else:
                setattr(publication, attribute, None)
    if failures:
        raise BuildError(
            "failed to clean report transaction files: "
            + ", ".join(sorted(failures))
        )


def _rollback(publications: list[Publication]) -> None:
    failures: list[str] = []
    for publication in reversed(publications):
        if not publication.published:
            continue
        try:
            if publication.original.exists:
                if publication.backup is None:
                    raise OSError("missing rollback backup")
                os.replace(
                    publication.backup,
                    publication.name,
                    src_dir_fd=publication.parent,
                    dst_dir_fd=publication.parent,
                )
                publication.backup = None
            else:
                os.unlink(publication.name, dir_fd=publication.parent)
            publication.published = False
            os.fsync(publication.parent)
        except OSError:
            failures.append(publication.relative)
    try:
        _cleanup_transaction(publications)
    except BuildError as exc:
        failures.append(str(exc))
    if failures:
        raise BuildError(
            "report publication failed and rollback was incomplete: "
            + ", ".join(sorted(failures))
        )


def _prepare_backups(publications: list[Publication]) -> None:
    for publication in publications:
        if not publication.original.exists:
            continue
        backup = _reserve_name(
            publication.parent,
            publication.name,
            "backup",
        )
        try:
            os.link(
                publication.name,
                backup,
                src_dir_fd=publication.parent,
                dst_dir_fd=publication.parent,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise BuildError(
                f"cannot prepare rollback for {publication.relative}"
            ) from exc
        publication.backup = backup
        linked = _snapshot_destination(
            publication.parent,
            backup,
            f"{publication.relative} rollback copy",
        )
        current = _snapshot_destination(
            publication.parent,
            publication.name,
            publication.relative,
        )
        # Creating a hard link legitimately advances the inode ctime.  Every
        # other pre-link property must still identify the exact file that was
        # preflighted, and the two names must now expose one identical inode.
        pre_link_identity = (
            publication.original.exists,
            publication.original.device,
            publication.original.inode,
            publication.original.mode,
            publication.original.size,
            publication.original.modified_ns,
        )
        current_identity = (
            current.exists,
            current.device,
            current.inode,
            current.mode,
            current.size,
            current.modified_ns,
        )
        if pre_link_identity != current_identity or linked != current:
            raise BuildError(
                f"{publication.relative} changed before publication"
            )
        publication.original = current


def _publish(
    root_path: Path,
    root: int,
    publications: list[Publication],
) -> None:
    try:
        _prepare_backups(publications)
        for publication in publications:
            current = _snapshot_destination(
                publication.parent,
                publication.name,
                publication.relative,
            )
            if current != publication.original:
                raise BuildError(
                    f"{publication.relative} changed before publication"
                )
            _assert_parent_reachable(
                root_path,
                root,
                publication,
                "before publication",
            )
            if publication.temporary is None:
                raise BuildError(
                    f"{publication.relative} has no staged content"
                )
            os.replace(
                publication.temporary,
                publication.name,
                src_dir_fd=publication.parent,
                dst_dir_fd=publication.parent,
            )
            publication.temporary = None
            publication.published = True
            _assert_parent_reachable(
                root_path,
                root,
                publication,
                "during publication",
            )
            if _read_published(publication) != publication.content:
                raise BuildError(
                    f"{publication.relative} changed during publication"
                )
        for parent in {item.parent for item in publications}:
            os.fsync(parent)
    except BaseException as exc:
        try:
            _rollback(publications)
        except BuildError as rollback_error:
            raise rollback_error from exc
        if isinstance(exc, BuildError):
            raise
        if isinstance(exc, OSError):
            raise BuildError(f"report publication failed: {exc}") from exc
        raise

    # All canonical replacements and their directories are durable above.
    # Backup removal is post-commit housekeeping: a cleanup fault must never
    # trigger a rollback after some rollback links have already been removed.
    try:
        _cleanup_transaction(publications)
        for parent in {item.parent for item in publications}:
            os.fsync(parent)
    except (BuildError, OSError) as exc:
        raise BuildError(
            "report outputs were fully committed, but transaction cleanup failed: "
            f"{exc}"
        ) from exc


def _validated_rendered_outputs(
    outputs: object,
) -> dict[str, bytes]:
    expected = set(_require_report_model().OUTPUT_PATHS)
    if not isinstance(outputs, dict) or set(outputs) != expected:
        raise BuildError("renderer output keys do not match canonical outputs")
    rendered: dict[str, bytes] = {}
    for relative in sorted(expected):
        _relative_parts(relative, f"output key {relative!r}")
        content = outputs[relative]
        if not isinstance(content, bytes):
            raise BuildError(f"{relative} rendered content must be bytes")
        if len(content) > MAX_OUTPUT_BYTES:
            raise BuildError(f"{relative} exceeds maximum size")
        rendered[relative] = bytes(content)
    return rendered


def build_report(source: Path, repo_root: Path) -> int:
    """Validate, render, and transactionally replace the canonical outputs."""
    model = _require_report_model()
    if not isinstance(source, Path) or not isinstance(repo_root, Path):
        raise BuildError("source and repo_root must be Path objects")
    root_path = _absolute_lexical(repo_root)
    source_path = (
        _absolute_lexical(root_path / source)
        if not source.is_absolute()
        else _absolute_lexical(source)
    )
    canonical_source = _absolute_lexical(
        root_path.joinpath(*CANONICAL_SOURCE.parts)
    )
    if source_path != canonical_source:
        raise BuildError(
            "project source must be exactly reports/data/project.json"
        )

    root = _open_absolute_directory(root_path, "repository root")
    publications: list[Publication] = []
    parent_descriptors: dict[tuple[str, ...], int] = {}
    try:
        component_paths = _generator_component_paths(root_path)
        model_path = component_paths["scripts/report_model.py"]
        imported_model_path = _absolute_lexical(Path(model.__file__))
        if imported_model_path != model_path:
            raise BuildError(
                "report builder must load the exact sibling repository model"
            )
        if set(PINNED_GENERATOR_MODULES) != set(
            GENERATOR_COMPONENT_PATHS[:-1]
        ):
            raise BuildError(
                "pinned report generator module set drifted"
            )
        for relative, module in PINNED_GENERATOR_MODULES.items():
            if _absolute_lexical(Path(module.__file__)) != component_paths[
                relative
            ]:
                raise BuildError(
                    f"report builder must load exact sibling {relative}"
                )
        evidence_module = PINNED_GENERATOR_MODULES[
            "scripts/evidence_io.py"
        ]
        candidate_module = PINNED_GENERATOR_MODULES[
            "scripts/candidate_evidence.py"
        ]
        promotion_module = PINNED_GENERATOR_MODULES[
            "scripts/check-promotion.py"
        ]
        if getattr(model, "_evidence_io", None) is not evidence_module:
            raise BuildError(
                "report model lost its pinned evidence helper"
            )
        sys.modules["evidence_io"] = evidence_module
        sys.modules["candidate_evidence"] = candidate_module
        sys.modules[
            "_booleanrazor_report_check_promotion"
        ] = promotion_module
        if model._load_task4_module() is not promotion_module:
            raise BuildError(
                "report model lost its pinned promotion checker"
            )

        generator_sources = _read_generator_sources(root_path)
        if generator_sources != IMPORTED_GENERATOR_BYTES:
            raise BuildError(
                "report generator changed since import; restart the builder"
            )

        project, source_digest = model.load_project(
            source_path,
            root_path,
        )
        combined_generator_digest = _digest_generator_sources(
            generator_sources
        )
        try:
            model_generator_digest = model.report_generator_digest(
                generator_sources["scripts/report_model.py"],
                generator_sources["scripts/evidence_io.py"],
                generator_sources["scripts/candidate_evidence.py"],
                generator_sources["scripts/check-promotion.py"],
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise BuildError(
                "report model has no valid combined generator digest contract"
            ) from exc
        if model_generator_digest != combined_generator_digest:
            raise BuildError("report generator digest contract drifted")
        rendered = _validated_rendered_outputs(
            model.render_outputs(
                project,
                source_digest,
                combined_generator_digest,
            )
        )

        # Repeat every trust-boundary read before the first filesystem
        # mutation.  Rendering therefore binds one stable source/generator
        # tuple, including the executable evidence helper.
        project_again, source_digest_again = model.load_project(
            source_path,
            root_path,
        )
        generator_again = _read_generator_sources(root_path)
        if (
            project_again != project
            or source_digest_again != source_digest
            or generator_again != generator_sources
        ):
            raise BuildError("report inputs changed while rendering")

        for relative, content in rendered.items():
            parts = _relative_parts(relative, f"output key {relative!r}")
            parent_parts = parts[:-1]
            parent = parent_descriptors.get(parent_parts)
            if parent is None:
                parent = _open_output_parent(
                    root,
                    parent_parts,
                    f"{relative} parent",
                )
                parent_descriptors[parent_parts] = parent
            publications.append(
                Publication(
                    relative=relative,
                    parent_relative=parent_parts,
                    parent=parent,
                    name=parts[-1],
                    content=content,
                    original=_snapshot_destination(
                        parent,
                        parts[-1],
                        relative,
                    ),
                )
            )

        for publication in publications:
            _assert_parent_reachable(
                root_path,
                root,
                publication,
                "before staging",
            )
        for publication in publications:
            _stage(publication)

        # No canonical destination is changed until every staged byte string,
        # parent identity, input, and original destination passes revalidation.
        for publication in publications:
            if (
                _snapshot_destination(
                    publication.parent,
                    publication.name,
                    publication.relative,
                )
                != publication.original
            ):
                raise BuildError(
                    f"{publication.relative} changed before publication"
                )
            _assert_parent_reachable(
                root_path,
                root,
                publication,
                "before publication",
            )
        _, final_source_digest = model.load_project(
            source_path,
            root_path,
        )
        final_generator = _read_generator_sources(root_path)
        if (
            final_source_digest != source_digest
            or final_generator != generator_sources
        ):
            raise BuildError("report inputs changed before publication")

        _publish(root_path, root, publications)
        return len(publications)
    except BaseException:
        if publications and not any(item.published for item in publications):
            _cleanup_transaction(publications)
        raise
    finally:
        for parent in set(parent_descriptors.values()):
            os.close(parent)
        os.close(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--repo-root", type=Path)
    args = parser.parse_args(argv)
    default_root = _absolute_lexical(Path(__file__).parent.parent)
    root = args.repo_root or default_root
    source = args.source or Path(CANONICAL_SOURCE.as_posix())
    try:
        count = build_report(source, root)
    except (BuildError, REPORT_MODEL_ERROR, OSError) as exc:
        print(f"report build failed: {exc}", file=sys.stderr)
        return 1
    print(f"report build: wrote {count} generated files")
    for relative in sorted(_require_report_model().OUTPUT_PATHS):
        print(relative)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
