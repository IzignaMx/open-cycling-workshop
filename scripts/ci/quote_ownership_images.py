"""Pure reviewed PostgreSQL manifest selection; never invokes Docker or network."""

from __future__ import annotations

import json
import re

from scripts.ci.quote_ownership_actions_guard import _object, _pairs


class ImageRefusal(ValueError):
    def __init__(self) -> None:
        super().__init__("ownership_image_refused")


def base_reference(raw: str) -> tuple[str, str]:
    """Require one official manifest reference, not an image configuration ID."""
    try:
        if type(raw) is not str or not 0 < len(raw.encode("utf-8")) <= 16384:
            raise ImageRefusal()
        value = _object(
            json.loads(raw, object_pairs_hook=_pairs), {"Id", "RepoDigests", "Os", "Architecture"}
        )
        config, digests = value["Id"], value["RepoDigests"]
        if (
            type(config) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", config) is None
            or type(digests) is not list
            or len(digests) != 1
            or type(digests[0]) is not str
            or re.fullmatch(r"(?:docker.io/library/)?postgres@sha256:[0-9a-f]{64}", digests[0])
            is None
            or value["Os"] != "linux"
            or value["Architecture"] != "amd64"
        ):
            raise ImageRefusal()
        return config, digests[0].removeprefix("docker.io/library/")
    except Exception:
        raise ImageRefusal() from None


def verify_reference(raw: str, config: str, reference: str) -> None:
    """Inspect the exact selected digest back to the same config/platform."""
    if base_reference(raw) != (config, reference):
        raise ImageRefusal()
