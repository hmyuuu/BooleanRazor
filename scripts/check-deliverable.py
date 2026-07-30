#!/usr/bin/env python3
"""Fail closed when the generated research deliverable is stale or unsafe."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import re
import stat
import sys
from html.parser import HTMLParser
from pathlib import Path
from types import ModuleType
from urllib.parse import unquote, urlsplit


MAX_GENERATOR_BYTES = 16 * 1024 * 1024
GENERATOR_DIGEST_DOMAIN = (
    b"BooleanRazor deterministic report generator v2\0"
)
GENERATOR_COMPONENT_PATHS = (
    "scripts/evidence_io.py",
    "scripts/candidate_evidence.py",
    "scripts/check-promotion.py",
    "scripts/report_model.py",
)
_BOOTSTRAP_DIRECTORY_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
)
_BOOTSTRAP_READ_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


class CheckerBootstrapError(ValueError):
    """The checker cannot safely execute its repository dependencies."""


def _bootstrap_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _bootstrap_open_directory(path: Path, label: str) -> int:
    absolute = _bootstrap_absolute(path)
    components = absolute.parts[1:]
    if (
        not absolute.is_absolute()
        or not absolute.anchor
        or not components
        or any(part in {"", ".", ".."} for part in components)
    ):
        raise CheckerBootstrapError(f"{label} has an invalid path")
    descriptor = os.open(
        Path(absolute.anchor).anchor or "/",
        _BOOTSTRAP_DIRECTORY_FLAGS,
    )
    try:
        for component in components:
            child = os.open(
                component,
                _BOOTSTRAP_DIRECTORY_FLAGS,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        raise CheckerBootstrapError(
            f"{label} must be a directory without symlinks"
        ) from exc


def _bootstrap_read_once(path: Path, label: str) -> bytes:
    absolute = _bootstrap_absolute(path)
    parent = _bootstrap_open_directory(absolute.parent, f"{label} parent")
    try:
        try:
            descriptor = os.open(
                absolute.name,
                _BOOTSTRAP_READ_FLAGS,
                dir_fd=parent,
            )
        except OSError as exc:
            raise CheckerBootstrapError(
                f"{label} must be a regular file without symlinks"
            ) from exc
    finally:
        os.close(parent)
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size > MAX_GENERATOR_BYTES
        ):
            raise CheckerBootstrapError(
                f"{label} must be a bounded regular file"
            )
        chunks: list[bytes] = []
        remaining = MAX_GENERATOR_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        after = os.fstat(descriptor)
        if len(content) > MAX_GENERATOR_BYTES:
            raise CheckerBootstrapError(f"{label} exceeds maximum size")
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
            raise CheckerBootstrapError(f"{label} changed while being read")
        return content
    finally:
        os.close(descriptor)


def _bootstrap_read_stable(path: Path, label: str) -> bytes:
    first = _bootstrap_read_once(path, label)
    second = _bootstrap_read_once(path, label)
    if first != second:
        raise CheckerBootstrapError(f"{label} changed between reads")
    return first


def _bootstrap_execute(
    module_name: str,
    path: Path,
    source: bytes,
) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None:
        raise CheckerBootstrapError(
            f"cannot create module specification for {path.name}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        exec(compile(source, os.fspath(path), "exec"), module.__dict__)
    except BaseException:
        if sys.modules.get(module_name) is module:
            sys.modules.pop(module_name, None)
        raise
    return module


def _load_checker_dependencies() -> tuple[
    ModuleType,
    ModuleType,
    ModuleType,
    ModuleType,
    dict[str, bytes],
]:
    scripts = _bootstrap_absolute(Path(__file__).parent)
    paths = {
        relative: scripts / relative.removeprefix("scripts/")
        for relative in GENERATOR_COMPONENT_PATHS
    }
    sources = {
        relative: _bootstrap_read_stable(
            path,
            f"report generator component {relative}",
        )
        for relative, path in paths.items()
    }
    loaded: list[tuple[str, ModuleType]] = []
    try:
        evidence = _bootstrap_execute(
            "evidence_io",
            paths["scripts/evidence_io.py"],
            sources["scripts/evidence_io.py"],
        )
        loaded.append(("evidence_io", evidence))
        candidate = _bootstrap_execute(
            "candidate_evidence",
            paths["scripts/candidate_evidence.py"],
            sources["scripts/candidate_evidence.py"],
        )
        loaded.append(("candidate_evidence", candidate))
        promotion = _bootstrap_execute(
            "_booleanrazor_report_check_promotion",
            paths["scripts/check-promotion.py"],
            sources["scripts/check-promotion.py"],
        )
        loaded.append(("_booleanrazor_report_check_promotion", promotion))
        model = _bootstrap_execute(
            "report_model",
            paths["scripts/report_model.py"],
            sources["scripts/report_model.py"],
        )
        loaded.append(("report_model", model))
        if getattr(model, "_evidence_io", None) is not evidence:
            raise CheckerBootstrapError(
                "report model did not retain the pinned evidence helper"
            )
        if model._load_task4_module() is not promotion:
            raise CheckerBootstrapError(
                "report model did not retain the pinned promotion validator"
            )
        if sys.modules.get("candidate_evidence") is not candidate:
            raise CheckerBootstrapError(
                "report model did not retain the pinned candidate validator"
            )
        return evidence, candidate, promotion, model, sources
    except BaseException:
        for name, module in reversed(loaded):
            if sys.modules.get(name) is module:
                sys.modules.pop(name, None)
        raise


evidence_io: ModuleType | None
candidate_evidence: ModuleType | None
check_promotion: ModuleType | None
report_model: ModuleType | None
_IMPORTED_GENERATOR_BYTES: dict[str, bytes]
_DEPENDENCY_BOOTSTRAP_ERROR: BaseException | None
try:
    (
        evidence_io,
        candidate_evidence,
        check_promotion,
        report_model,
        _IMPORTED_GENERATOR_BYTES,
    ) = _load_checker_dependencies()
except KeyboardInterrupt:
    raise
except BaseException as exc:
    evidence_io = None
    candidate_evidence = None
    check_promotion = None
    report_model = None
    _IMPORTED_GENERATOR_BYTES = {}
    _DEPENDENCY_BOOTSTRAP_ERROR = exc
else:
    _DEPENDENCY_BOOTSTRAP_ERROR = None


GENERATED_PREFIX = b"<!-- GENERATED; DO NOT EDIT."
CANONICAL_SOURCE = "reports/data/project.json"
CANONICAL_OUTPUT_PATHS = frozenset(
    {
        "reports/site/index.html",
        "reports/site/methods.html",
        "reports/site/verification.html",
        "reports/site/experiments.html",
        "reports/site/assets/report.css",
        "reports/site/assets/report.js",
        "docs/STATUS.md",
        "docs/METHODS.md",
        "docs/EXPERIMENT_INDEX.md",
        "research/EVIDENCE_LEDGER.md",
    }
)
MAX_GENERATED_BYTES = 16 * 1024 * 1024
CSS_URL = re.compile(
    r"""url\s*\(\s*(?P<quote>["']?)(?P<url>.*?)(?P=quote)\s*\)""",
    re.IGNORECASE,
)
URI_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
CSS_REMOTE_TOKEN = re.compile(
    r"(?i)(?:https?|data|javascript|ftp|file|blob):|//"
)
CSS_ALTERNATE_LOADER = re.compile(
    r"(?i)(?:-webkit-)?image-set\s*\(|\bsrc\s*\(|"
    r"\bexpression\s*\(|\bbehavior\s*:|(?:-moz-)?binding\s*:"
)
SAFE_REPORT_JS = b"""\
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


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _generated_marker(source_digest: str, generator_digest: str) -> bytes:
    return (
        "<!-- GENERATED; DO NOT EDIT. Source: reports/data/project.json SHA-256: "
        f"{source_digest}; report generator SHA-256: {generator_digest} -->"
    ).encode("utf-8")


def _independent_generator_digest(
    components: dict[str, bytes],
) -> str:
    if set(components) != set(GENERATOR_COMPONENT_PATHS) or any(
        type(content) is not bytes for content in components.values()
    ):
        raise CheckerBootstrapError(
            "report generator digest requires every exact component"
        )
    digest = hashlib.sha256()
    digest.update(GENERATOR_DIGEST_DOMAIN)
    for relative in GENERATOR_COMPONENT_PATHS:
        name = relative.encode("utf-8")
        content = components[relative]
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _restore_pinned_dependency_modules() -> None:
    if (
        evidence_io is None
        or candidate_evidence is None
        or check_promotion is None
        or report_model is None
    ):
        raise CheckerBootstrapError("pinned dependency modules are unavailable")
    sys.modules["evidence_io"] = evidence_io
    sys.modules["candidate_evidence"] = candidate_evidence
    sys.modules["_booleanrazor_report_check_promotion"] = check_promotion
    sys.modules["report_model"] = report_model


def _stable_read(
    path: Path,
    *,
    label: str,
    errors: list[str],
    max_bytes: int = MAX_GENERATED_BYTES,
) -> bytes | None:
    try:
        return evidence_io.read_stable_regular(path, label, max_bytes)
    except (evidence_io.EvidenceError, OSError, ValueError, TypeError) as exc:
        errors.append(f"{label} cannot be read safely: {exc}")
        return None


def _checked_regular(
    root: Path, relative: str, errors: list[str], label: str
) -> Path | None:
    root = _absolute_lexical(root)
    path = root.joinpath(*relative.split("/"))
    current = root
    try:
        root_mode = current.lstat().st_mode
    except OSError:
        errors.append("repository root does not exist")
        return None
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        errors.append("repository root must be a real directory")
        return None
    for part in relative.split("/"):
        current = current / part
        try:
            mode = current.lstat().st_mode
        except OSError:
            errors.append(f"missing generated output: {relative}")
            return None
        if stat.S_ISLNK(mode):
            errors.append(f"{label} uses a symlink component: {relative}")
            return None
    if not stat.S_ISREG(path.lstat().st_mode):
        errors.append(f"{label} is not a regular file: {relative}")
        return None
    return path


def _walk_without_symlinks(root: Path, start: Path):
    if not start.exists():
        return
    for directory, directory_names, file_names in os.walk(
        start, followlinks=False
    ):
        directory_path = Path(directory)
        for name in list(directory_names):
            path = directory_path / name
            if path.is_symlink():
                yield path
                directory_names.remove(name)
        for name in file_names:
            yield directory_path / name


def _unexpected_outputs(root: Path, errors: list[str]) -> None:
    root = _absolute_lexical(root)
    expected = set(CANONICAL_OUTPUT_PATHS)
    site = root / "reports/site"
    for path in _walk_without_symlinks(root, site) or ():
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            errors.append(f"unexpected generated output escapes repository: {path}")
            continue
        if relative not in expected:
            errors.append(f"unexpected generated output: {relative}")
        if path.is_symlink():
            errors.append(f"generated output uses a symlink component: {relative}")

    for parent in (root / "docs", root / "research"):
        for path in _walk_without_symlinks(root, parent) or ():
            if path.is_symlink() or path.suffix != ".md":
                continue
            try:
                relative = path.relative_to(root).as_posix()
                raw = evidence_io.read_stable_regular(
                    path,
                    f"unexpected generated candidate {relative}",
                    MAX_GENERATED_BYTES,
                )
            except (evidence_io.EvidenceError, OSError, ValueError):
                continue
            if raw.startswith(GENERATED_PREFIX) and relative not in expected:
                errors.append(f"unexpected generated output: {relative}")


def _decode_url_path(raw_path: str) -> tuple[str | None, str | None]:
    decoded = raw_path
    for _ in range(4):
        updated = unquote(decoded)
        if updated == decoded:
            break
        decoded = updated
    else:
        return None, "repeated percent encoding"
    from urllib.parse import quote

    if quote(decoded, safe="/-._~") != raw_path:
        return None, "noncanonical percent encoding"
    if (
        not decoded
        or decoded.startswith("/")
        or "\\" in decoded
        or any(ord(character) < 32 or ord(character) == 127 for character in decoded)
    ):
        return None, "unsafe local path"
    return decoded, None


def _decode_fragment(raw_fragment: str) -> tuple[str | None, str | None]:
    decoded = raw_fragment
    for _ in range(4):
        updated = unquote(decoded)
        if updated == decoded:
            break
        decoded = updated
    else:
        return None, "repeated percent encoding"
    from urllib.parse import quote

    if (
        not decoded
        or quote(decoded, safe="!$&'()*+,;=:@/?-._~") != raw_fragment
        or any(ord(character) < 32 or ord(character) == 127 for character in decoded)
    ):
        return None, "noncanonical or unsafe fragment"
    return decoded, None


def _local_target(
    *,
    root: Path,
    base_file: Path,
    value: str,
    label: str,
    errors: list[str],
    allow_external_anchor: bool,
) -> None:
    if value != value.strip() or not value:
        errors.append(f"{label} has an empty or noncanonical URL")
        return
    if value.startswith("#"):
        if allow_external_anchor and len(value) > 1:
            return
        errors.append(f"{label} has an invalid fragment-only URL")
        return
    if value.startswith("//") or URI_SCHEME.match(value):
        if (
            allow_external_anchor
            and value.startswith("https://")
            and report_model._https_url(value)
        ):
            return
        errors.append(f"{label} uses a remote resource URL")
        return
    split = urlsplit(value)
    if split.netloc or split.scheme or split.query:
        errors.append(f"{label} has a noncanonical local URL")
        return
    decoded, problem = _decode_url_path(split.path)
    if problem is not None or decoded is None:
        errors.append(f"{label} has a noncanonical local URL: {problem}")
        return
    root = _absolute_lexical(root)
    target = _absolute_lexical(base_file.parent / decoded)
    try:
        relative = target.relative_to(root)
    except ValueError:
        errors.append(f"{label} local target escapes the repository")
        return
    try:
        evidence_io.resolve_evidence_path(root, relative.as_posix(), label)
    except (evidence_io.EvidenceError, OSError, ValueError, TypeError):
        errors.append(
            f"{label} has a missing local target or unsafe path: {decoded}"
        )


class _PageParser(HTMLParser):
    def __init__(self, page: str) -> None:
        super().__init__(convert_charrefs=True)
        self.page = page
        self.errors: list[str] = []
        self.viewport = 0
        self.skip_link = 0
        self.main = 0
        self.ids: list[str] = []
        self.main_ids: list[str] = []
        self.skip_hrefs: list[str] = []
        self.urls: list[tuple[str, str, str, bool]] = []
        self.inline_css: list[str] = []
        self.stylesheets: list[str] = []
        self.scripts: list[str] = []
        self._style_depth = 0
        self._script_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.lower()
        names = [name.lower() for name, _ in attrs]
        if len(names) != len(set(names)):
            self.errors.append(f"{self.page} has duplicate HTML attributes")
        attributes = {
            name.lower(): value if value is not None else ""
            for name, value in attrs
        }
        if any(name.startswith("on") for name in attributes):
            self.errors.append(f"{self.page} contains an event-handler attribute")
        if tag in {"iframe", "object", "embed"}:
            self.errors.append(f"{self.page} contains forbidden {tag}")
        if tag == "svg":
            self.errors.append(f"{self.page} contains forbidden inline SVG")
        if tag in {
            "animate",
            "animatemotion",
            "animatetransform",
            "discard",
            "set",
        }:
            self.errors.append(
                f"{self.page} contains a forbidden SVG animation element"
            )
        if tag == "base":
            self.errors.append(f"{self.page} contains a forbidden base element")
        if tag == "meta":
            if attributes.get("name", "").lower() == "viewport":
                self.viewport += 1
            if attributes.get("http-equiv", "").lower() == "refresh":
                self.errors.append(f"{self.page} contains a forbidden meta refresh")
        if tag == "main":
            self.main += 1
            self.main_ids.append(attributes.get("id", ""))
        identifier = attributes.get("id")
        if identifier is not None:
            if not identifier:
                self.errors.append(f"{self.page} has an empty fragment id")
            self.ids.append(identifier)
        if tag == "a":
            classes = attributes.get("class", "").split()
            if "skip-link" in classes:
                self.skip_link += 1
                self.skip_hrefs.append(attributes.get("href", ""))
        if tag == "link":
            rel = set(attributes.get("rel", "").lower().split())
            if rel != {"stylesheet"}:
                self.errors.append(f"{self.page} contains a forbidden resource link")
            elif "href" not in attributes:
                self.errors.append(f"{self.page} stylesheet link has no href")
            else:
                self.stylesheets.append(attributes["href"])
        if tag == "script" and "src" not in attributes:
            self.errors.append(f"{self.page} contains a forbidden inline script")
        if tag == "script":
            self._script_depth += 1
            if "src" in attributes:
                self.scripts.append(attributes["src"])
        if tag == "style":
            self._style_depth += 1
        if "style" in attributes:
            self.inline_css.append(attributes["style"])
        for attribute in (
            "action",
            "archive",
            "background",
            "cite",
            "codebase",
            "data",
            "formaction",
            "href",
            "longdesc",
            "manifest",
            "poster",
            "src",
            "usemap",
        ):
            value = attributes.get(attribute)
            if value is not None:
                self.urls.append(
                    (tag, attribute, value, tag == "a" and attribute == "href")
                )
        for attribute, value in attributes.items():
            if attribute.endswith(":href"):
                self.urls.append((tag, attribute, value, False))
        if "srcset" in attributes:
            for candidate in attributes["srcset"].split(","):
                value = candidate.strip().split(" ", 1)[0]
                self.urls.append((tag, "srcset", value, False))
        if "ping" in attributes:
            for value in attributes["ping"].split():
                self.urls.append((tag, "ping", value, False))

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() == "style" and self._style_depth:
            self._style_depth -= 1
        if tag.lower() == "script" and self._script_depth:
            self._script_depth -= 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "style" and self._style_depth:
            self._style_depth -= 1
        if tag.lower() == "script" and self._script_depth:
            self._script_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._style_depth:
            self.inline_css.append(data)
        if self._script_depth and data.strip():
            self.errors.append(f"{self.page} contains inline script content")


def _validate_css(
    *,
    css: str,
    root: Path,
    css_path: Path,
    label: str,
    errors: list[str],
) -> None:
    normalized = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    if "\\" in normalized:
        errors.append(f"{label} contains a forbidden CSS escape")
    if "/*" in normalized or "*/" in normalized:
        errors.append(f"{label} contains an unterminated CSS comment")
    if re.search(r"@import\b", normalized, re.IGNORECASE):
        errors.append(f"{label} contains forbidden CSS @import")
    if CSS_REMOTE_TOKEN.search(normalized):
        errors.append(f"{label} contains a remote CSS token")
    if CSS_ALTERNATE_LOADER.search(normalized):
        errors.append(f"{label} contains a remote CSS token or unsupported loader")
    for match in CSS_URL.finditer(normalized):
        value = match.group("url").strip()
        before = len(errors)
        _local_target(
            root=root,
            base_file=css_path,
            value=value,
            label=label,
            errors=errors,
            allow_external_anchor=False,
        )
        if len(errors) > before:
            diagnostic = errors.pop()
            if "remote resource" in diagnostic:
                errors.append(f"{label} contains a remote CSS URL")
            else:
                errors.append(f"{label} contains a noncanonical CSS URL")


def _has_visible_focus_style(css: str) -> bool:
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        selector, declarations = match.groups()
        if ":focus-visible" not in selector.lower():
            continue
        for declaration in declarations.split(";"):
            if ":" not in declaration:
                continue
            property_name, value = declaration.split(":", 1)
            if property_name.strip().lower() not in {
                "border",
                "box-shadow",
                "outline",
            }:
                continue
            normalized = value.strip().lower()
            if (
                not normalized
                or re.search(r"\b(?:none|transparent)\b", normalized)
                or normalized in {"0", "0.0"}
            ):
                continue
            numeric_values = [
                float(number)
                for number in re.findall(
                    r"(?<![A-Za-z0-9_.-])"
                    r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))"
                    r"(?:[A-Za-z%]+)?",
                    normalized,
                )
            ]
            if any(number != 0.0 for number in numeric_values) or re.search(
                r"\b(?:auto|medium|thick|thin)\b", normalized
            ):
                return True
    return False


def _validate_html(
    *,
    root: Path,
    relative: str,
    raw: bytes,
    errors: list[str],
) -> _PageParser | None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(f"{relative} must be UTF-8 HTML")
        return None
    parser = _PageParser(relative)
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:
        errors.append(f"{relative} cannot be parsed as HTML: {exc}")
        return None
    errors.extend(parser.errors)
    if len(parser.ids) != len(set(parser.ids)):
        errors.append(f"{relative} contains a duplicate fragment id")
    if parser.viewport != 1:
        errors.append(f"{relative} must contain exactly one viewport meta")
    if parser.skip_link != 1:
        errors.append(f"{relative} must contain exactly one skip link")
    if parser.main != 1:
        errors.append(f"{relative} must contain exactly one main landmark")
    if parser.stylesheets != ["assets/report.css"]:
        errors.append(f"{relative} must load exactly assets/report.css")
    if parser.scripts != ["assets/report.js"]:
        errors.append(f"{relative} must load exactly assets/report.js")
    page_path = _absolute_lexical(root).joinpath(*relative.split("/"))
    for tag, attribute, value, allow_external in parser.urls:
        _local_target(
            root=root,
            base_file=page_path,
            value=value,
            label=f"{relative} {tag}[{attribute}]",
            errors=errors,
            allow_external_anchor=allow_external,
        )
    for css in parser.inline_css:
        _validate_css(
            css=css,
            root=root,
            css_path=page_path,
            label=f"{relative} inline CSS",
            errors=errors,
        )
    return parser


def _validate_fragment_targets(
    *,
    root: Path,
    relative: str,
    parser: _PageParser,
    pages: dict[str, _PageParser],
    errors: list[str],
) -> None:
    if parser.skip_link == 1:
        skip_href = parser.skip_hrefs[0]
        split = urlsplit(skip_href)
        decoded, problem = _decode_fragment(split.fragment)
        if (
            problem is not None
            or decoded is None
            or split.scheme
            or split.netloc
            or split.query
            or split.path
            or decoded not in parser.main_ids
        ):
            errors.append(f"{relative} skip link must target the main landmark")

    page_path = _absolute_lexical(root).joinpath(*relative.split("/"))
    for tag, attribute, value, allow_external in parser.urls:
        if not allow_external:
            continue
        split = urlsplit(value)
        if not split.fragment:
            continue
        if split.scheme or split.netloc:
            continue
        fragment, problem = _decode_fragment(split.fragment)
        if problem is not None or fragment is None:
            errors.append(
                f"{relative} {tag}[{attribute}] has a noncanonical fragment"
            )
            continue
        if split.path:
            decoded_path, path_problem = _decode_url_path(split.path)
            if path_problem is not None or decoded_path is None:
                continue
            target = _absolute_lexical(page_path.parent / decoded_path)
            try:
                target_relative = target.relative_to(
                    _absolute_lexical(root)
                ).as_posix()
            except ValueError:
                continue
        else:
            target_relative = relative
        target_page = pages.get(target_relative)
        if target_page is None or fragment not in target_page.ids:
            errors.append(
                f"{relative} {tag}[{attribute}] has a missing fragment target: "
                f"{target_relative}#{fragment}"
            )


def check_deliverable(source: Path, repo_root: Path) -> list[str]:
    """Return sorted diagnostics; an empty list means the deliverable is fresh."""
    if (
        _DEPENDENCY_BOOTSTRAP_ERROR is not None
        or evidence_io is None
        or candidate_evidence is None
        or check_promotion is None
        or report_model is None
    ):
        failure = _DEPENDENCY_BOOTSTRAP_ERROR
        detail = (
            f"{type(failure).__name__}: {failure}"
            if failure is not None
            else "dependency modules are unavailable"
        )
        return [f"report checker dependency bootstrap failed: {detail}"]
    _restore_pinned_dependency_modules()

    errors: list[str] = []
    root = _absolute_lexical(repo_root)
    supplied_source = source
    if supplied_source.is_absolute():
        canonical_spelling = supplied_source == root.joinpath(
            *CANONICAL_SOURCE.split("/")
        )
    else:
        canonical_spelling = supplied_source.as_posix() == CANONICAL_SOURCE
    source = _absolute_lexical(
        supplied_source if supplied_source.is_absolute() else root / supplied_source
    )
    canonical_source = root.joinpath(*CANONICAL_SOURCE.split("/"))
    if not canonical_spelling or source != canonical_source:
        return [
            "project source must be the canonical project source: "
            f"{CANONICAL_SOURCE}"
        ]

    component_modules = {
        "scripts/evidence_io.py": evidence_io,
        "scripts/candidate_evidence.py": candidate_evidence,
        "scripts/check-promotion.py": check_promotion,
        "scripts/report_model.py": report_model,
    }
    component_labels = {
        "scripts/evidence_io.py": "evidence helper",
        "scripts/candidate_evidence.py": "candidate validator",
        "scripts/check-promotion.py": "promotion validator",
        "scripts/report_model.py": "report model",
    }
    for relative in GENERATOR_COMPONENT_PATHS:
        module = component_modules[relative]
        expected_path = root.joinpath(*relative.split("/"))
        try:
            imported_path = _absolute_lexical(Path(module.__file__))
        except (AttributeError, OSError, TypeError, ValueError):
            return [
                f"imported {component_labels[relative]} has no canonical file identity"
            ]
        if imported_path != expected_path:
            return [
                f"imported {component_labels[relative]} is not the canonical repository component: "
                f"{relative}"
            ]
    if getattr(report_model, "_evidence_io", None) is not evidence_io:
        return ["report model and checker do not share the canonical evidence helper"]
    if report_model._load_task4_module() is not check_promotion:
        return ["report model and checker do not share the promotion validator"]
    if sys.modules.get("candidate_evidence") is not candidate_evidence:
        return ["report model and checker do not share the candidate validator"]

    source_raw = _stable_read(
        source,
        label="project source",
        errors=errors,
        max_bytes=report_model.MAX_SOURCE_BYTES,
    )
    if source_raw is None:
        return sorted(set(errors))
    try:
        project = report_model._parse_canonical_object(
            source_raw, "project source"
        )
        model_errors = report_model.validate_project(project, root)
        if model_errors:
            raise report_model.ModelError("\n".join(model_errors))
    except (report_model.ModelError, OSError, ValueError, TypeError) as exc:
        return [f"project source error: {exc}"]
    source_digest = hashlib.sha256(source_raw).hexdigest()

    component_bytes: dict[str, bytes] = {}
    for relative in GENERATOR_COMPONENT_PATHS:
        label = component_labels[relative]
        path = _checked_regular(root, relative, errors, label)
        if path is None:
            return sorted(set(errors))
        raw = _stable_read(path, label=label, errors=errors)
        if raw is None:
            return sorted(set(errors))
        component_bytes[relative] = raw
    generator_digest = _independent_generator_digest(component_bytes)
    model_generator_digest = report_model.report_generator_digest(
        component_bytes["scripts/report_model.py"],
        component_bytes["scripts/evidence_io.py"],
        component_bytes["scripts/candidate_evidence.py"],
        component_bytes["scripts/check-promotion.py"],
    )
    if model_generator_digest != generator_digest:
        return ["report generator digest contract drifted"]
    if component_bytes != _IMPORTED_GENERATOR_BYTES:
        return [
            "report generator changed since checker bootstrap; restart the checker"
        ]
    try:
        expected = report_model.render_outputs(
            project, source_digest, generator_digest
        )
    except (report_model.ModelError, OSError, ValueError, TypeError, KeyError) as exc:
        return [f"report rendering error: {exc}"]
    if not isinstance(expected, dict):
        return ["report renderer must return an output map"]
    if set(report_model.OUTPUT_PATHS) != set(CANONICAL_OUTPUT_PATHS):
        errors.append(
            "report model does not declare the canonical generated output set"
        )
    if set(expected) != set(CANONICAL_OUTPUT_PATHS):
        errors.append("report renderer returned an unexpected generated output set")
    if any(
        not isinstance(name, str) or not isinstance(content, bytes)
        for name, content in expected.items()
    ):
        errors.append("report renderer output map must contain string keys and bytes")
        return sorted(set(errors))

    committed: dict[str, bytes] = {}
    for relative in sorted(CANONICAL_OUTPUT_PATHS):
        path = _checked_regular(root, relative, errors, "generated output")
        if path is None:
            continue
        raw = _stable_read(
            path,
            label=f"generated output {relative}",
            errors=errors,
        )
        if raw is None:
            continue
        committed[relative] = raw
        if expected.get(relative) != raw:
            errors.append(f"generated output drift: {relative}")

    _unexpected_outputs(root, errors)

    exact_marker = _generated_marker(source_digest, generator_digest)
    marker_paths = {
        "reports/site/index.html",
        "reports/site/methods.html",
        "reports/site/verification.html",
        "reports/site/experiments.html",
        "docs/STATUS.md",
        "docs/METHODS.md",
        "docs/EXPERIMENT_INDEX.md",
        "research/EVIDENCE_LEDGER.md",
    }
    for relative in sorted(marker_paths):
        raw = committed.get(relative)
        if raw is None:
            continue
        if not raw.startswith(exact_marker + b"\n") or raw.count(exact_marker) != 1:
            errors.append(f"{relative} lacks the exact generated marker")

    parsed_pages: dict[str, _PageParser] = {}
    for relative in sorted(name for name in committed if name.endswith(".html")):
        parsed = _validate_html(
            root=root, relative=relative, raw=committed[relative], errors=errors
        )
        if parsed is not None:
            parsed_pages[relative] = parsed
    for relative, parsed in sorted(parsed_pages.items()):
        _validate_fragment_targets(
            root=root,
            relative=relative,
            parser=parsed,
            pages=parsed_pages,
            errors=errors,
        )

    css_relative = "reports/site/assets/report.css"
    css_raw = committed.get(css_relative)
    if css_raw is not None:
        try:
            css_text = css_raw.decode("utf-8")
        except UnicodeDecodeError:
            errors.append("report stylesheet must be UTF-8")
        else:
            effective_css = re.sub(
                r"/\*.*?\*/", "", css_text, flags=re.DOTALL
            )
            if (
                re.search(
                    r"@media\s+print\b\s*\{",
                    effective_css,
                    re.IGNORECASE,
                )
                is None
            ):
                errors.append("report stylesheet is missing a print stylesheet")
            if not _has_visible_focus_style(effective_css):
                errors.append("report stylesheet is missing a visible focus style")
            _validate_css(
                css=css_text,
                root=root,
                css_path=root.joinpath(*css_relative.split("/")),
                label=css_relative,
                errors=errors,
            )

    js_raw = committed.get("reports/site/assets/report.js")
    if js_raw is not None:
        if js_raw != SAFE_REPORT_JS:
            errors.append(
                "report script does not match the independently reviewed safe script"
            )

    return sorted(set(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--repo-root", type=Path)
    args = parser.parse_args(argv)
    default_root = Path(__file__).resolve().parent.parent
    root = _absolute_lexical(args.repo_root or default_root)
    source = args.source or Path("reports/data/project.json")
    errors = check_deliverable(source, root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(
        f"deliverable check: pass ({len(CANONICAL_OUTPUT_PATHS)} generated files)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
