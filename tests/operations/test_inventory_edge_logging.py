"""Source contract plus opt-in actual Caddy upstream-failure privacy proof."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NAMESPACE = "/api/v1/inventory"
CANARY = "private-edge-query-canary"


def privacy_pattern(filename: str) -> str:
    source = (ROOT / "infra/edge" / filename).read_text(encoding="utf-8")
    match = re.search(r"request>uri regexp `(.*?)` `\$\{1\}`", source)
    assert match, "Runtime/error request.uri must filter the complete inventory query"
    assert "log default {" in source and "format filter {" in source
    assert "output discard" not in source
    assert "exclude http" not in source
    return match[1]


@pytest.mark.parametrize("filename", ["Caddyfile", "Caddyfile.lan"])
def test_runtime_log_filter_is_identical_and_narrow(filename: str) -> None:
    pattern = privacy_pattern(filename)
    assert pattern == privacy_pattern("Caddyfile")
    paths = [NAMESPACE, NAMESPACE + "/", NAMESPACE + "/products/p/movements"]
    # The edge logs ORIGINAL RequestURI, while ASGI routing receives decoded
    # paths. Match all single-percent-encoded spellings of the private prefix.
    for index, char in enumerate(NAMESPACE):
        paths.append(NAMESPACE[:index] + f"%{ord(char):02x}" + NAMESPACE[index + 1 :] + "/products")
        paths.append(NAMESPACE[:index] + f"%{ord(char):02X}" + NAMESPACE[index + 1 :] + "/products")
    paths.append(NAMESPACE + "%2fproducts")
    for path in paths:
        assert re.sub(pattern, r"\1", path + "?before=" + CANARY) == path
    for path in [NAMESPACE + "-other", NAMESPACE + "ish/products", "/other", "/API/v1/inventory"]:
        target = path + "?before=" + CANARY
        assert re.sub(pattern, r"\1", target) == target
