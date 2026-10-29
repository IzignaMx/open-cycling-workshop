"""Pure pinned-image metadata checks; no Docker/image/network operations."""

import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / "scripts/ci/quote_ownership_images.py"
spec = importlib.util.spec_from_file_location("ownership_images", PATH)
images = importlib.util.module_from_spec(spec)
spec.loader.exec_module(images)
CONFIG = "sha256:" + "a" * 64
REFERENCE = "postgres@sha256:" + "b" * 64


def metadata(**changes):
    return json.dumps(
        dict(Id=CONFIG, RepoDigests=[REFERENCE], Os="linux", Architecture="amd64") | changes
    )


def test_unique_manifest_reference_not_raw_config_id():
    assert images.base_reference(metadata()) == (CONFIG, REFERENCE)
    images.verify_reference(metadata(), CONFIG, REFERENCE)


@pytest.mark.parametrize(
    "changes",
    [
        {"RepoDigests": []},
        {"RepoDigests": [REFERENCE, REFERENCE]},
        {"RepoDigests": ["evil/postgres@sha256:" + "b" * 64]},
        {"RepoDigests": [CONFIG]},
        {"RepoDigests": None},
        {"RepoDigests": ["postgres@sha256:" + "B" * 64]},
        {"Id": "private canary"},
        {"Os": "windows"},
        {"Architecture": "arm64"},
        {"extra": "field"},
    ],
)
def test_invalid_or_multiple_reference_refuses(changes):
    with pytest.raises(images.ImageRefusal, match="ownership_image_refused"):
        images.base_reference(metadata(**changes))


@pytest.mark.parametrize(
    "raw",
    [
        metadata(Id="sha256:" + "c" * 64),
        metadata(RepoDigests=["postgres@sha256:" + "c" * 64]),
        metadata(Architecture="arm64"),
    ],
)
def test_digest_inspection_must_match_original_config_and_platform(raw):
    with pytest.raises(images.ImageRefusal):
        images.verify_reference(raw, CONFIG, REFERENCE)


@pytest.mark.parametrize("raw", ["[]", "null", "x" * 16385, '{"Id":1,"Id":2}'])
def test_bounded_closed_metadata(raw):
    with pytest.raises(images.ImageRefusal):
        images.base_reference(raw)


def test_workflow_uses_verified_manifest_reference_within_shared_pg_window():
    source = (PATH.parents[2] / ".github/workflows/quote-ownership-measurement.yml").read_text()
    pg = source.split("pg_deadline = min(deadline, time.monotonic() + 60)", 1)[1].split(
        "          PY", 1
    )[0]
    assert "base, reference = base_reference(raw_base)" in pg
    assert "verify_reference(raw_selected, base, reference)" in pg
    assert "f'PG_BASE_IMAGE={reference}'" in pg
    assert "f'PG_BASE_IMAGE={base}'" not in pg
    assert pg.count("pg_deadline - time.monotonic()") == 5
    assert "('pg_base_reference', reference)" in pg


def test_official_fully_qualified_alias_is_canonicalized():
    raw = json.dumps(
        {
            "Id": "sha256:" + "a" * 64,
            "RepoDigests": ["docker.io/library/postgres@sha256:" + "b" * 64],
            "Os": "linux",
            "Architecture": "amd64",
        }
    )
    from scripts.ci.quote_ownership_images import base_reference

    assert base_reference(raw) == ("sha256:" + "a" * 64, "postgres@sha256:" + "b" * 64)
