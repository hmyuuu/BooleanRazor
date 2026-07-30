"""Strict, canonical, descriptor-anchored evidence file primitives."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
from pathlib import Path
from typing import NoReturn


HEX_64 = re.compile(r"[0-9a-f]{64}")
DEFAULT_MAX_BYTES = 16 * 1024 * 1024
MAX_ARTIFACT_BYTES = 512 * 1024 * 1024
_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
_READ_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


class EvidenceError(ValueError):
    """Invalid, unstable, escaped, or noncanonical evidence."""


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _reject_constant(value: str) -> NoReturn:
    raise EvidenceError(f"JSON number must be finite: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, child in pairs:
        if key in value:
            raise EvidenceError(f"duplicate JSON key: {key}")
        value[key] = child
    return value


def _absolute_parts(path: Path, label: str) -> tuple[str, ...]:
    """Return lexical absolute components without resolving any symlink."""
    absolute = path if path.is_absolute() else Path.cwd() / path
    if not absolute.is_absolute():  # defensive for unusual Path implementations
        raise EvidenceError(f"{label} path must be absolute")
    parts = absolute.parts
    if not parts or parts[0] != absolute.anchor:
        raise EvidenceError(f"{label} path is invalid")
    components = parts[1:]
    if not components or any(part in {"", ".", ".."} for part in components):
        raise EvidenceError(f"{label} path has an invalid component")
    return components


def _open_directory_components(path: Path, label: str) -> tuple[int, str]:
    """Open *path*'s parent directory and return its fd plus final filename.

    Every component is opened relative to an already-open directory descriptor.
    This makes a namespace substitution fail at that component rather than turn a
    checked name into an unchecked new pathname lookup.
    """
    components = _absolute_parts(path, label)
    descriptor = os.open(Path(path.anchor).anchor or "/", _DIRECTORY_FLAGS)
    try:
        for component in components[:-1]:
            child = os.open(component, _DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor, components[-1]
    except OSError as exc:
        os.close(descriptor)
        raise EvidenceError(f"{label} cannot inspect path component") from exc


def _open_regular(path: Path, label: str) -> int:
    parent, name = _open_directory_components(path, label)
    try:
        descriptor = os.open(name, _READ_FLAGS, dir_fd=parent)
    except OSError as exc:
        raise EvidenceError(f"{label} must be a regular readable file") from exc
    finally:
        os.close(parent)
    return descriptor


def _read_once(path: Path, label: str, max_bytes: int) -> bytes:
    if max_bytes < 0:
        raise EvidenceError(f"{label} maximum size is invalid")
    descriptor = _open_regular(path, label)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise EvidenceError(f"{label} must be a regular file")
        if before.st_size > max_bytes:
            raise EvidenceError(f"{label} exceeds maximum size")
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        if len(data) > max_bytes:
            raise EvidenceError(f"{label} exceeds maximum size")
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise EvidenceError(f"{label} changed while being read")
        return data
    finally:
        os.close(descriptor)


def read_stable_regular(path: Path, label: str, max_bytes: int) -> bytes:
    """Return a bounded regular file only after two complete matching reads."""
    first = _read_once(path, label, max_bytes)
    second = _read_once(path, label, max_bytes)
    if first != second:
        raise EvidenceError(f"{label} changed between reads")
    return first


def load_canonical_object(
    path: Path, label: str, max_bytes: int = DEFAULT_MAX_BYTES
) -> tuple[dict[str, object], bytes]:
    raw = read_stable_regular(path, label, max_bytes)
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except EvidenceError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise EvidenceError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"{label} must be a JSON object")
    if raw != canonical_json_bytes(value):
        raise EvidenceError(f"{label} must be canonical JSON")
    return value, raw


def _open_root(root: Path, label: str) -> int:
    root_parts = _absolute_parts(root, f"{label} root")
    descriptor = os.open(Path(root.anchor).anchor or "/", _DIRECTORY_FLAGS)
    try:
        for component in root_parts:
            child = os.open(component, _DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        raise EvidenceError(f"{label} root must be an existing directory without symlinks") from exc


def resolve_evidence_path(root: Path, value: str, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise EvidenceError(f"{label} path must be a nonempty relative path")
    if Path(value).is_absolute():
        raise EvidenceError(f"{label} path must be relative")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise EvidenceError(f"{label} path has an invalid component")
    descriptor = _open_root(root, label)
    try:
        for component in parts[:-1]:
            child = os.open(component, _DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        final = os.open(parts[-1], _READ_FLAGS, dir_fd=descriptor)
        try:
            if not stat.S_ISREG(os.fstat(final).st_mode):
                raise EvidenceError(f"{label} must be a regular file")
        finally:
            os.close(final)
    except EvidenceError:
        raise
    except OSError as exc:
        raise EvidenceError(f"{label} must be an existing regular file under evidence root") from exc
    finally:
        os.close(descriptor)
    # Retain lexical native paths for callers; every later read reopens it securely.
    return root.joinpath(*parts)


def atomic_create(path: Path, data: bytes) -> None:
    """Publish *data* once through a verified parent directory descriptor."""
    parent, final_name = _open_directory_components(path, "output")
    temporary = f".{final_name}.{secrets.token_hex(16)}.tmp"
    descriptor: int | None = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temporary, flags, 0o600, dir_fd=parent)
        offset = 0
        while offset < len(data):
            written = os.write(descriptor, data[offset:])
            if written <= 0:
                raise EvidenceError("failed to write output")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        try:
            os.link(
                temporary,
                final_name,
                src_dir_fd=parent,
                dst_dir_fd=parent,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise EvidenceError("output already exists") from exc
        os.fsync(parent)
    except EvidenceError:
        raise
    except OSError as exc:
        raise EvidenceError("failed to create immutable output") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            os.unlink(temporary, dir_fd=parent)
        except FileNotFoundError:
            pass
        except OSError as exc:
            os.close(parent)
            raise EvidenceError("failed to clean temporary output") from exc
        os.close(parent)
