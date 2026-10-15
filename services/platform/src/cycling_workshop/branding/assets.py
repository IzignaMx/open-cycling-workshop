"""Private tenant-scoped immutable assets; never used as a public static mount."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

from cycling_workshop.blobs.filesystem import FilesystemBlobStorage
from cycling_workshop.branding.images import MAX_PNG_BYTES, CanonicalLogo, inspect_canonical_png

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class BrandingAssetStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    @staticmethod
    def _namespace(organization_id: str) -> str:
        # Legacy installations need not have UUID organization IDs. Hash the
        # exact validated identity, without case folding or normalization.
        if (
            not isinstance(organization_id, str)
            or not 1 <= len(organization_id) <= 160
            or len(organization_id.encode("utf-8")) > 640
            or organization_id != organization_id.strip()
            or organization_id in (".", "..")
            or any(c in "/\\" or unicodedata.category(c).startswith("C") for c in organization_id)
        ):
            raise ValueError("invalid organization identity")
        return hashlib.sha256(organization_id.encode("utf-8")).hexdigest()

    def _storage(self, organization_id: str, *, create: bool) -> FilesystemBlobStorage:
        return FilesystemBlobStorage(self._root / self._namespace(organization_id), create=create)

    def put(self, organization_id: str, logo: CanonicalLogo) -> str:
        if (
            not 1 <= logo.byte_count <= MAX_PNG_BYTES
            or logo.byte_count != len(logo.data)
            or not _DIGEST.fullmatch(logo.sha256)
            or hashlib.sha256(logo.data).hexdigest() != logo.sha256
            or inspect_canonical_png(logo.data) != (logo.width, logo.height)
        ):
            raise ValueError("invalid canonical asset")
        return self._storage(organization_id, create=True).put(logo.data, content_type="image/png")

    def read(self, organization_id: str, key: str, *, sha256: str, byte_count: int) -> bytes:
        if (
            not isinstance(sha256, str)
            or not _DIGEST.fullmatch(sha256)
            or key != f"{sha256[:2]}/{sha256}"
            or not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or not 1 <= byte_count <= MAX_PNG_BYTES
        ):
            raise ValueError("invalid asset descriptor")
        data = self._storage(organization_id, create=False).get_bounded(
            key, max_bytes=MAX_PNG_BYTES
        )
        if len(data) != byte_count or hashlib.sha256(data).hexdigest() != sha256:
            raise ValueError("asset integrity failure")
        inspect_canonical_png(data)
        return data


def check_asset_root(root: Path) -> None:
    """Explicit non-root startup probe for a prepared private named volume.

    Never chmod/chown or initialize an existing installation. A new Docker
    volume inherits the image's 0700/10001 directory; an unsafe old one fails.
    """
    import os
    import secrets
    from contextlib import suppress

    storage = FilesystemBlobStorage(root, create=False)
    with storage._root_fd() as directory:
        if os.fstat(directory).st_mode & 0o077:
            raise ValueError("asset root must be private")
        name = f".ownership-check-{secrets.token_hex(16)}"
        fd = os.open(
            name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory
        )
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
            with suppress(FileNotFoundError):
                os.unlink(name, dir_fd=directory)
        os.fsync(directory)
