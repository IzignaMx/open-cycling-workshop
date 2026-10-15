import base64
import hashlib
import struct
import zlib
from dataclasses import replace
from pathlib import Path

import pytest
from cycling_workshop.branding.assets import BrandingAssetStore
from cycling_workshop.branding.images import CanonicalLogo, canonicalize_logo


@pytest.fixture
def logo() -> CanonicalLogo:
    def chunk(kind: bytes, data: bytes = b"") -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0\x11\x22\x33\xff"))
        + chunk(b"IEND")
    )
    return canonicalize_logo(base64.b64encode(data).decode("ascii"))


def test_private_tenant_namespaces_and_no_read_mutation(
    tmp_path: Path, logo: CanonicalLogo
) -> None:
    root = tmp_path / "assets"
    store = BrandingAssetStore(root)
    assert not root.exists()
    key = store.put("legacy-org-a", logo)
    assert key == f"{logo.sha256[:2]}/{logo.sha256}"
    assert (
        store.read("legacy-org-a", key, sha256=logo.sha256, byte_count=logo.byte_count) == logo.data
    )
    assert list(root.iterdir()) == [root / hashlib.sha256(b"legacy-org-a").hexdigest()]
    with pytest.raises(FileNotFoundError):
        store.read("legacy-org-b", key, sha256=logo.sha256, byte_count=logo.byte_count)
    assert len(list(root.iterdir())) == 1
    assert store.put("legacy-org-b", logo) == key
    assert len(list(root.iterdir())) == 2


@pytest.mark.parametrize("identity", ["", "../tenant", "a/b", "a\\b", " a", "a\0", "a" * 161])
def test_invalid_identity_refused(tmp_path: Path, logo: CanonicalLogo, identity: str) -> None:
    store = BrandingAssetStore(tmp_path / "assets")
    with pytest.raises(ValueError):
        store.put(identity, logo)
    assert not (tmp_path / "assets").exists()


def test_bad_descriptor_and_corrupt_storage_refused(tmp_path: Path, logo: CanonicalLogo) -> None:
    store = BrandingAssetStore(tmp_path)
    key = store.put("org", logo)
    for bad in (
        replace(logo, width=512),
        replace(logo, sha256="0" * 64),
        replace(logo, byte_count=0),
    ):
        with pytest.raises(ValueError):
            store.put("org", bad)
    for path in ("../" + key, "00/" + logo.sha256, key + "/"):
        with pytest.raises(ValueError):
            store.read("org", path, sha256=logo.sha256, byte_count=logo.byte_count)
    path = tmp_path / hashlib.sha256(b"org").hexdigest() / key
    path.write_bytes(logo.data[:-1])
    with pytest.raises(ValueError):
        store.read("org", key, sha256=logo.sha256, byte_count=logo.byte_count)
    path.write_bytes(b"x" * 262145)
    with pytest.raises(ValueError, match="byte limit"):
        store.read("org", key, sha256=logo.sha256, byte_count=logo.byte_count)


def test_replacement_retains_old_assets(tmp_path: Path, logo: CanonicalLogo) -> None:
    store = BrandingAssetStore(tmp_path)
    key = store.put("org", logo)
    assert store.put("org", logo) == key
    assert store.read("org", key, sha256=logo.sha256, byte_count=logo.byte_count) == logo.data
    assert len(list(tmp_path.rglob("[0-9a-f]" * 64))) == 2  # namespace plus immutable asset


def test_runtime_volume_probe_is_private_and_leaves_no_files(tmp_path: Path) -> None:
    from cycling_workshop.branding.assets import check_asset_root

    check_asset_root(tmp_path)
    assert not list(tmp_path.iterdir())
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError, match="private"):
        check_asset_root(tmp_path)
    assert not list(tmp_path.iterdir())
