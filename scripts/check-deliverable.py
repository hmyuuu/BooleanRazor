#!/usr/bin/env python3
"""Fail closed when the generated research deliverable is stale or unsafe."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import report_model


GENERATED_PREFIX = b"<!-- GENERATED; DO NOT EDIT."
CSS_URL = re.compile(
    r"""url\s*\(\s*(?P<quote>["']?)(?P<url>.*?)(?P=quote)\s*\)""",
    re.IGNORECASE,
)
URI_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _generated_marker(source_digest: str, generator_digest: str) -> bytes:
    return (
        "<!-- GENERATED; DO NOT EDIT. Source: reports/data/project.json SHA-256: "
        f"{source_digest}; report model SHA-256: {generator_digest} -->"
    ).encode("utf-8")


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
    expected = set(report_model.OUTPUT_PATHS)
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
                raw = path.read_bytes()
                relative = path.relative_to(root).as_posix()
            except (OSError, ValueError):
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
    current = root
    for part in relative.parts:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except OSError:
            errors.append(f"{label} has a missing local target: {decoded}")
            return
        if stat.S_ISLNK(mode):
            errors.append(f"{label} local target uses a symlink: {decoded}")
            return
    if not stat.S_ISREG(target.lstat().st_mode):
        errors.append(f"{label} local target is not a regular file: {decoded}")


class _PageParser(HTMLParser):
    def __init__(self, page: str) -> None:
        super().__init__(convert_charrefs=True)
        self.page = page
        self.errors: list[str] = []
        self.viewport = 0
        self.skip_link = 0
        self.main = 0
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
        if tag == "base":
            self.errors.append(f"{self.page} contains a forbidden base element")
        if tag == "meta":
            if attributes.get("name", "").lower() == "viewport":
                self.viewport += 1
            if attributes.get("http-equiv", "").lower() == "refresh":
                self.errors.append(f"{self.page} contains a forbidden meta refresh")
        if tag == "main":
            self.main += 1
        if tag == "a":
            classes = attributes.get("class", "").split()
            if "skip-link" in classes and attributes.get("href") == "#content":
                self.skip_link += 1
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
    if re.search(r"@import\b", normalized, re.IGNORECASE):
        errors.append(f"{label} contains forbidden CSS @import")
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


def _validate_html(
    *,
    root: Path,
    relative: str,
    raw: bytes,
    errors: list[str],
) -> None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(f"{relative} must be UTF-8 HTML")
        return
    parser = _PageParser(relative)
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:
        errors.append(f"{relative} cannot be parsed as HTML: {exc}")
        return
    errors.extend(parser.errors)
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


def check_deliverable(source: Path, repo_root: Path) -> list[str]:
    """Return sorted diagnostics; an empty list means the deliverable is fresh."""
    errors: list[str] = []
    root = _absolute_lexical(repo_root)
    source = source if source.is_absolute() else root / source
    try:
        project, source_digest = report_model.load_project(source, root)
    except (report_model.ModelError, OSError, ValueError, TypeError) as exc:
        return [f"project source error: {exc}"]

    generator_relative = "scripts/report_model.py"
    generator_path = _checked_regular(
        root, generator_relative, errors, "report model"
    )
    if generator_path is None:
        return sorted(set(errors))
    try:
        generator_bytes = generator_path.read_bytes()
    except OSError as exc:
        return [f"report model cannot be read: {exc}"]
    generator_digest = hashlib.sha256(generator_bytes).hexdigest()
    try:
        expected = report_model.render_outputs(
            project, source_digest, generator_digest
        )
    except (report_model.ModelError, OSError, ValueError, TypeError, KeyError) as exc:
        return [f"report rendering error: {exc}"]
    if not isinstance(expected, dict):
        return ["report renderer must return an output map"]
    if set(expected) != set(report_model.OUTPUT_PATHS):
        errors.append("report renderer returned an unexpected generated output set")
    if any(
        not isinstance(name, str) or not isinstance(content, bytes)
        for name, content in expected.items()
    ):
        errors.append("report renderer output map must contain string keys and bytes")
        return sorted(set(errors))

    committed: dict[str, bytes] = {}
    for relative in sorted(report_model.OUTPUT_PATHS):
        path = _checked_regular(root, relative, errors, "generated output")
        if path is None:
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:
            errors.append(f"generated output cannot be read: {relative}: {exc}")
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

    for relative in sorted(
        name for name in committed if name.endswith(".html")
    ):
        _validate_html(
            root=root, relative=relative, raw=committed[relative], errors=errors
        )

    css_relative = "reports/site/assets/report.css"
    css_raw = committed.get(css_relative)
    if css_raw is not None:
        try:
            css_text = css_raw.decode("utf-8")
        except UnicodeDecodeError:
            errors.append("report stylesheet must be UTF-8")
        else:
            if re.search(r"@media\s+print\b", css_text, re.IGNORECASE) is None:
                errors.append("report stylesheet is missing a print stylesheet")
            if ":focus-visible" not in css_text:
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
        try:
            js_text = js_raw.decode("utf-8")
        except UnicodeDecodeError:
            errors.append("report script must be UTF-8")
        else:
            if re.search(
                r"(?i)(?:https?:)?//|data:|javascript:", js_text
            ):
                errors.append("report script contains a remote runtime URL")

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
        f"deliverable check: pass ({len(report_model.OUTPUT_PATHS)} generated files)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
