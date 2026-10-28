from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/docs/build_public_site.py"


def builder():
    assert SCRIPT.is_file(), "public site builder is not implemented"
    spec = importlib.util.spec_from_file_location("public_site", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_site_build(tmp_path):
    mod = builder()
    mod.build(ROOT / "docs/site", tmp_path / "output")
    assert (tmp_path / "output/index.html").is_file()
    assert not (tmp_path / "output/.git").exists()


@pytest.fixture
def site(tmp_path):
    builder()
    target = tmp_path / "repo/docs/site"
    shutil.copytree(ROOT / "docs/site", target)
    # A copy of the explicitly fingerprinted source is sufficient; no .git needed.
    data = json.loads((target / "screenshots.json").read_text())
    for name in data["runtime_files"]:
        path = target.parents[1] / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if (ROOT / name).is_file():
            shutil.copyfile(ROOT / name, path)
        else:
            path.write_text("isolated synthetic runtime fixture")
        data["runtime_files"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (target / "screenshots.json").write_text(json.dumps(data))
    return target


@pytest.mark.parametrize("path", ["private.env", "assets/extra.txt", "sw.js"])
def test_unknown_files_rejected_before_output(site, tmp_path, path):
    (site / path).parent.mkdir(parents=True, exist_ok=True)
    (site / path).write_text("private")
    with pytest.raises(ValueError):
        builder().build(site, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "payload",
    [
        "<script>alert(1)</script>",
        '<IFRAME src="https://example.com"></IFRAME>',
        '<img src="https://example.com/a.png" alt="bad">',
        '<a href="&#106;avascript:alert(1)">x</a>',
        '<div onClick="alert(1)">x</div>',
        '<form action="https://example.com">x</form>',
        '<img src="../secret.png" alt="bad">',
        '<img src="%2e%2e/secret.png" alt="bad">',
        '<a href="/root-path">x</a>',
        '<object data="x"></object>',
    ],
)
def test_unsafe_html_rejected(site, tmp_path, payload):
    with (site / "index.html").open("a") as file:
        file.write(payload)
    with pytest.raises(ValueError):
        builder().build(site, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "payload", ['@import "https://example.com";', "a{background:URL(x)}", "a{background:u\\72l(x)}"]
)
def test_network_css_rejected(site, tmp_path, payload):
    with (site / "styles.css").open("a") as file:
        file.write(payload)
    with pytest.raises(ValueError):
        builder().build(site, tmp_path / "out")


def test_missing_and_changed_screenshot_rejected(site, tmp_path):
    data = json.loads((site / "screenshots.json").read_text())
    image = site / data["images"][0]["path"]
    image.write_bytes(b"changed")
    with pytest.raises(ValueError):
        builder().build(site, tmp_path / "out")
    image.unlink()
    with pytest.raises(ValueError):
        builder().build(site, tmp_path / "out")


@pytest.mark.parametrize("kind", ["nonempty", "symlink", "overlap", "source-symlink"])
def test_unsafe_destinations_or_source_symlink(site, tmp_path, kind):
    out = tmp_path / "out"
    if kind == "nonempty":
        out.mkdir()
        (out / "secret").write_text("secret")
    elif kind == "symlink":
        out.symlink_to(site, target_is_directory=True)
    elif kind == "overlap":
        out = site / "output"
    else:
        (site / "styles.css").unlink()
        (site / "styles.css").symlink_to(ROOT / "docs/site/styles.css")
    with pytest.raises(ValueError):
        builder().build(site, out)


def test_freshness_docs_only_vs_runtime_change(site, tmp_path):
    mod = builder()
    (site.parents[1] / "README.md").write_text("different documentation")
    mod.build(site, tmp_path / "current", require_current=True)
    assert "current-runtime" in (tmp_path / "current/build-info.json").read_text()
    data = json.loads((site / "screenshots.json").read_text())
    first = site.parents[1] / next(iter(data["runtime_files"]))
    first.write_bytes(first.read_bytes() + b"\n")
    mod.build(site, tmp_path / "historical")
    assert "historical-runtime" in (tmp_path / "historical/build-info.json").read_text()
    assert "Capturas históricas" in (tmp_path / "historical/index.html").read_text()
    with pytest.raises(ValueError):
        mod.build(site, tmp_path / "rejected", require_current=True)


@pytest.mark.parametrize(
    "field,value",
    [
        ("runtime_files", {}),
        ("source_commit", "main"),
        ("runtime_files", {"../../secret": "0" * 64}),
    ],
)
def test_invalid_provenance_rejected(site, tmp_path, field, value):
    data = json.loads((site / "screenshots.json").read_text())
    data[field] = value
    (site / "screenshots.json").write_text(json.dumps(data))
    with pytest.raises(ValueError):
        builder().build(site, tmp_path / "out")


def test_manifest_covers_all_shipped_images_and_pngs(site, tmp_path):
    data = json.loads((site / "screenshots.json").read_text())
    image = site / data["images"][0]["path"]
    image.write_bytes(b"not-png")
    data["images"][0]["sha256"] = hashlib.sha256(image.read_bytes()).hexdigest()
    (site / "screenshots.json").write_text(json.dumps(data))
    with pytest.raises(ValueError):
        builder().build(site, tmp_path / "out")


def test_destination_symlink_parent_rejected(site, tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError):
        builder().build(site, link / "out")
    assert not (real / "out").exists()


def test_added_runtime_file_is_historical_not_a_broken_docs_build(site, tmp_path):
    (site.parents[1] / "apps/web/src/new-module.ts").write_text("export {}")
    builder().build(site, tmp_path / "out")
    assert "historical-runtime" in (tmp_path / "out/build-info.json").read_text()
    with pytest.raises(ValueError):
        builder().build(site, tmp_path / "rejected", require_current=True)


def test_missing_local_anchor_is_rejected(site, tmp_path):
    with (site / "index.html").open("a") as file:
        file.write('<a href="#missing">broken</a>')
    with pytest.raises(ValueError):
        builder().build(site, tmp_path / "out")


@pytest.mark.parametrize(
    "payload",
    [
        'body{background-image:image-set("https://example.com/tracker" 1x)}',
        'body{background-image:-webkit-image-set("https://example.com/tracker" 1x)}',
        'body{background-image:image("https://example.com/tracker")}',
    ],
)
def test_css_string_image_fetch_rejected(site, tmp_path, payload):
    with (site / "styles.css").open("a") as file:
        file.write(payload)
    with pytest.raises(ValueError):
        builder().build(site, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("replacement", ["", "default-src *"])
def test_required_restrictive_csp(site, tmp_path, replacement):
    page = site / "index.html"
    text = page.read_text().replace(
        "default-src 'none'; img-src 'self'; style-src 'self'; base-uri 'none'; form-action 'none'",
        replacement,
    )
    page.write_text(text)
    with pytest.raises(ValueError):
        builder().build(site, tmp_path / "out")


def test_dark_section_focus_has_explicit_high_contrast_color():
    # This stylesheet invariant complements the actual keyboard/browser contrast check.
    css = (ROOT / "docs/site/styles.css").read_text()
    assert ".dark a:focus-visible" in css
    assert "outline-color: #e1f3c3" in css
