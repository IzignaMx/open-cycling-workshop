#!/usr/bin/env python3
"""Validate and copy only reviewed, inert public documentation (no dependencies)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

CSP = "default-src 'none'; img-src 'self'; style-src 'self'; base-uri 'none'; form-action 'none'"

RUNTIME_ROOTS = (
    "apps/web/src/",
    "packages/api-client/src/",
    "packages/ui/src/",
    "packages/branding/src/",
    "services/platform/src/",
)
RUNTIME_FILES = (
    "apps/web/pwa-navigation-policy.mjs",
    "apps/web/pwa-navigation-policy.d.mts",
    "apps/web/tsconfig.json",
    "tsconfig.base.json",
    "pnpm-workspace.yaml",
    "packages/api-client/package.json",
    "packages/ui/package.json",
    "packages/branding/package.json",
    "services/platform/pyproject.toml",
    "apps/web/index.html",
    "apps/web/vite.config.ts",
    "apps/web/package.json",
    "package.json",
    "pnpm-lock.yaml",
    "uv.lock",
    "pyproject.toml",
    "apps/web/e2e/structural-themes.spec.ts",
    "apps/web/e2e/helpers/visual-fixture.ts",
    "apps/web/playwright.config.ts",
)
TAGS = set(
    [
        "html",
        "head",
        "meta",
        "title",
        "link",
        "body",
        "header",
        "nav",
        "main",
        "section",
        "article",
        "aside",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "p",
        "a",
        "span",
        "strong",
        "em",
        "small",
        "ul",
        "ol",
        "li",
        "figure",
        "figcaption",
        "img",
        "div",
        "dl",
        "dt",
        "dd",
        "code",
        "pre",
        "br",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
    ]
)
ATTRS = set(
    [
        "lang",
        "charset",
        "name",
        "content",
        "http-equiv",
        "rel",
        "href",
        "class",
        "id",
        "aria-label",
        "aria-labelledby",
        "aria-hidden",
        "role",
        "tabindex",
        "src",
        "alt",
        "width",
        "height",
        "loading",
        "decoding",
        "scope",
    ]
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_relative(value: str) -> str:
    decoded = unquote(value)
    parts = Path(decoded).parts
    if (
        not decoded
        or decoded.startswith(("/", "\\"))
        or "\\" in decoded
        or ".." in parts
        or ":" in decoded
        or "%" in decoded
    ):
        raise ValueError(f"Unsafe local path: {value}")
    return decoded


class Document(HTMLParser):
    def __init__(self, allowed: set[str]):
        super().__init__(convert_charrefs=True)
        self.allowed = allowed
        self.anchors: set[str] = set()
        self.fragments: list[str] = []
        self.csp_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in TAGS:
            raise ValueError(f"Forbidden HTML tag: {tag}")
        values = dict(attrs)
        for key, value in attrs:
            if key not in ATTRS or value is None:
                raise ValueError(f"Forbidden HTML attribute: {key}")
            if key == "id":
                if value in self.anchors:
                    raise ValueError("Duplicate id")
                self.anchors.add(value)
            if key in ("href", "src"):
                parsed = urlsplit(value)
                if tag == "a" and key == "href" and parsed.scheme == "https" and parsed.netloc:
                    continue
                if value.startswith("#"):
                    self.fragments.append(value[1:])
                    continue
                local = safe_relative(parsed.path)
                if parsed.scheme or parsed.netloc or parsed.query or local not in self.allowed:
                    raise ValueError(f"Nonlocal or unknown asset/link: {value}")
            if key == "http-equiv" and value.lower() != "content-security-policy":
                raise ValueError("Only inert CSP metadata allowed")
        if tag == "meta" and values.get("http-equiv", "").lower() == "content-security-policy":
            if values.get("content") != CSP:
                raise ValueError("Required restrictive CSP changed")
            self.csp_count += 1
        if tag == "link" and (
            values.get("rel") != "stylesheet" or values.get("href") != "styles.css"
        ):
            raise ValueError("Only local stylesheet link allowed")
        if tag == "img" and not values.get("alt"):
            raise ValueError("Screenshot requires meaningful alt text")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


def runtime_paths(repo: Path) -> set[str]:
    files = set(RUNTIME_FILES)
    for root in RUNTIME_ROOTS:
        files.update(
            str(path.relative_to(repo))
            for path in (repo / root).rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        )
    return files


def build(source: Path, destination: Path, *, require_current: bool = False) -> None:
    source, destination = Path(source), Path(destination)
    if any(
        path.is_symlink()
        for path in (
            source,
            destination,
            *source.absolute().parents,
            *destination.absolute().parents,
        )
    ):
        raise ValueError("Symlink source/destination")
    source, destination = source.resolve(), destination.resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("Source/destination overlap")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("Destination must be absent or empty")
    # Check every ancestor too: a destination through a symlink is not an inert path.
    # Callers pass a dedicated artifact directory, never an application dist.
    try:
        data = json.loads((source / "screenshots.json").read_text())
    except (OSError, ValueError) as exc:
        raise ValueError("Missing/invalid screenshot provenance") from exc
    if not re.fullmatch(r"[0-9a-f]{40}", str(data.get("source_commit", ""))):
        raise ValueError("Invalid source SHA")
    if not isinstance(data.get("workflow_run_id"), int) or not isinstance(
        data.get("artifact_id"), int
    ):
        raise ValueError("Missing source-bound hosted provenance")
    runtime = data.get("runtime_files")
    if not isinstance(runtime, dict) or not runtime:
        raise ValueError("Missing runtime fingerprint")
    repo = source.parents[1]
    if not set(RUNTIME_FILES).issubset(runtime):
        raise ValueError("Runtime fingerprint lacks required files")
    if any(
        not (name in RUNTIME_FILES or any(name.startswith(root) for root in RUNTIME_ROOTS))
        for name in runtime
    ):
        raise ValueError("Unexpected runtime fingerprint path")
    current = set(runtime) == runtime_paths(repo)
    for name, expected in runtime.items():
        name = safe_relative(name)
        path = repo / name
        if path.is_symlink() or not re.fullmatch(r"[0-9a-f]{64}", str(expected)):
            raise ValueError("Invalid runtime fingerprint")
        if not path.is_file() or digest(path) != expected:
            current = False
    if require_current and not current:
        raise ValueError("Screenshots are historical for this runtime")
    allowed = {"index.html", "styles.css", "screenshots.json"}
    images = data.get("images")
    if not isinstance(images, list) or not images:
        raise ValueError("Missing images")
    for entry in images:
        name = safe_relative(entry["path"])
        if (
            not name.startswith("assets/screenshots/")
            or not name.endswith(".png")
            or name in allowed
        ):
            raise ValueError("Invalid/duplicate image path")
        allowed.add(name)
        path = source / name
        if path.is_symlink() or not path.is_file() or digest(path) != entry.get("sha256"):
            raise ValueError("Missing or modified screenshot")
        raw = path.read_bytes()
        if raw[:8] != b"\x89PNG\r\n\x1a\n" or len(raw) < 24:
            raise ValueError("Invalid PNG")
        if struct.unpack(">II", raw[16:24]) != (entry.get("width"), entry.get("height")):
            raise ValueError("Screenshot dimensions mismatch")
        if (
            not entry.get("visually_inspected")
            or entry.get("test_status") != "passed"
            or entry.get("retry") != 0
        ):
            raise ValueError("Screenshot lacks reviewed passing capture evidence")
    actual: set[str] = set()
    for path in source.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlink inside public source")
        if path.is_file():
            actual.add(str(path.relative_to(source)))
    if actual != allowed:
        raise ValueError(f"Public allowlist mismatch: {actual ^ allowed}")
    html = (source / "index.html").read_text()
    parser = Document(allowed)
    parser.feed(html)
    if parser.csp_count != 1:
        raise ValueError("Exactly one restrictive CSP required")
    if any(fragment not in parser.anchors for fragment in parser.fragments):
        raise ValueError("Missing fragment target")
    css = (source / "styles.css").read_text()
    if re.search(
        r"@import|url\s*\(|expression\s*\(|(?:image-set|image)\s*\(|\\", css, re.IGNORECASE
    ):
        raise ValueError("Active/network CSS prohibited")
    if html.count("<!-- CAPTURE_STATUS -->") != 1:
        raise ValueError("Missing capture freshness marker")
    state = "current-runtime" if current else "historical-runtime"
    label = (
        "Capturas del código actual" if current else "Capturas históricas: el código ha cambiado"
    )
    html = html.replace("<!-- CAPTURE_STATUS -->", label)
    # Nothing has been written before all validation above succeeds.
    destination.mkdir(parents=True, exist_ok=True)
    for name in sorted(allowed):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    (destination / "index.html").write_text(html)
    (destination / "build-info.json").write_text(
        json.dumps({"capture_status": state, "capture_source": data["source_commit"]}, indent=2)
        + "\n"
    )
    (destination / ".nojekyll").write_text("")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("docs/site"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-current", action="store_true")
    args = parser.parse_args()
    build(args.source, args.output, require_current=args.require_current)
    print(f"Validated public documentation: {args.output}")


if __name__ == "__main__":
    main()
