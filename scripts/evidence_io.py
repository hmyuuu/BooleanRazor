"""Strict, canonical, race-resistant evidence file primitives."""

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


def _absolute_lexical(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def _reject_symlink_components(path: Path, label: str) -> None:
    absolute = _absolute_lexical(path)
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise EvidenceError(f"{label} cannot inspect path component") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise EvidenceError(f"{label} must not traverse a symlink component")


def _read_once(path: Path, label: str, max_bytes: int) -> bytes:
    if max_bytes < 0:
        raise EvidenceError(f"{label} maximum size is invalid")
    try:
        if stat.S_ISLNK(os.lstat(path).st_mode):
            raise EvidenceError(f"{label} must be a regular file")
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise EvidenceError(f"{label} must be a regular readable file") from exc
    _reject_symlink_components(path, label)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise EvidenceError(f"{label} must be a regular readable file") from exc
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


def resolve_evidence_path(root: Path, value: str, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise EvidenceError(f"{label} path must be a nonempty relative path")
    if Path(value).is_absolute():
        raise EvidenceError(f"{label} path must be relative")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise EvidenceError(f"{label} path has an invalid component")
    _reject_symlink_components(root, f"{label} root")
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise EvidenceError(f"{label} root must exist") from exc
    if not resolved_root.is_dir():
        raise EvidenceError(f"{label} root must be a directory")
    candidate = root.joinpath(*parts)
    _reject_symlink_components(candidate, label)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise EvidenceError(f"{label} path must exist") from exc
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise EvidenceError(f"{label} path escapes evidence root") from exc
    try:
        metadata = os.lstat(candidate)
    except OSError as exc:
        raise EvidenceError(f"{label} must be a regular file") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise EvidenceError(f"{label} must be a regular file")
    return candidate


def atomic_create(path: Path, data: bytes) -> None:
    """Publish *data* exactly once without replacing an existing target."""
    parent = path.parent
    _reject_symlink_components(parent, "output")
    if not parent.is_dir():
        raise EvidenceError("output parent must be a directory")
    temporary = parent / f".{path.name}.{secrets.token_hex(16)}.tmp"
    descriptor: int | None = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temporary, flags, 0o600)
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
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as exc:
            raise EvidenceError("output already exists") from exc
        directory = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError as exc:
        raise EvidenceError("failed to create immutable output") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
