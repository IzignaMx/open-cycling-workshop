"""Focused receipt negatives for ordinary CI; not part of the six repair phases."""

from __future__ import annotations

import base64
import copy
import json
import zlib

import pytest

from scripts.ci import quote_static_repair as repair


def _receipt() -> dict[str, object]:
    path = repair.PATHS[0]
    patch = f"--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-old\n+new\n"
    after = list(repair.BEFORE_HASHES)
    after[0] = "0" * 64
    return {
        "schema": 1, "scope": "repair_proposal_only",
        "target_commit": repair.TARGET_COMMIT, "target_tree": repair.TARGET_TREE,
        "before_sha256": list(repair.BEFORE_HASHES), "after_sha256": after,
        "after_bytes": list(repair.BEFORE_SIZES), "patch": patch,
        "patch_sha256": repair.digest(patch.encode()),
        "tools": [
            {"tool": index, "returncode": 0, "output_bytes": 0, "diagnostics": [],
             "unsupported_lines": 0, "unparsed_lines": 0, "diagnostics_complete": True,
             "reported_remaining": 0}
            for index in range(4)
        ],
    }


def _envelope(raw: bytes, suffix: bytes = b"") -> bytes:
    return repair.canonical({
        "schema": 1, "expanded_bytes": len(raw), "sha256": repair.digest(raw),
        "zlib_base64": base64.b64encode(zlib.compress(raw) + suffix).decode(),
    })


def test_repair_receipt_round_trip_and_final_failure_status() -> None:
    value = _receipt()
    assert repair.decode_receipt(repair.encode_receipt(value), failed=False) == value
    value["tools"][2].update(returncode=1, diagnostics_complete=False, reported_remaining=None)
    encoded = repair.encode_receipt(value)
    assert repair.decode_receipt(encoded, failed=True) == value
    with pytest.raises(repair.RepairReceiptError):
        repair.decode_receipt(encoded, failed=False)


@pytest.mark.parametrize("damage", [
    "duplicate_outer", "nan_outer", "noncanonical_outer", "trailing_zlib",
    "concatenated_zlib", "truncated_zlib", "expanded_over_cap", "duplicate_inner",
])
def test_repair_envelope_rejects_noncanonical_or_unbounded_data(damage: str) -> None:
    raw = repair.canonical(_receipt())
    encoded = _envelope(raw)
    if damage == "duplicate_outer":
        encoded = encoded.replace(b'{', b'{"schema":1,', 1)
    elif damage == "nan_outer":
        encoded = encoded.replace(b'"schema":1', b'"schema":NaN')
    elif damage == "noncanonical_outer":
        encoded += b" "
    elif damage == "trailing_zlib":
        encoded = _envelope(raw, b"trailing")
    elif damage == "concatenated_zlib":
        encoded = _envelope(raw, zlib.compress(b"second"))
    elif damage == "truncated_zlib":
        outer = json.loads(encoded)
        outer["zlib_base64"] = base64.b64encode(zlib.compress(raw)[:-1]).decode()
        encoded = repair.canonical(outer)
    elif damage == "expanded_over_cap":
        encoded = _envelope(b" " * (repair.EXPANDED_LIMIT + 1))
    elif damage == "duplicate_inner":
        encoded = _envelope(raw.replace(b'{', b'{"schema":1,', 1))
    with pytest.raises(repair.RepairReceiptError):
        repair.decode_receipt(encoded, failed=False)


@pytest.mark.parametrize("damage", ["unknown_path", "wrong_hash", "extra_path", "duplicate_rule", "bad_hunk"])
def test_repair_receipt_rejects_wrong_source_or_diagnostic_identity(damage: str) -> None:
    value = copy.deepcopy(_receipt())
    if damage == "unknown_path":
        value["patch"] = value["patch"].replace(repair.PATHS[0], "../outside.py")
    elif damage == "wrong_hash":
        value["before_sha256"][0] = "0" * 64
    elif damage == "extra_path":
        value["after_sha256"].append("0" * 64)
    elif damage == "duplicate_rule":
        value["tools"][0].update(returncode=1, diagnostics=[[0, 1, 0], [0, 1, 0]])
    elif damage == "bad_hunk":
        value["patch"] = value["patch"].replace("@@ -1 +1 @@", "@@ -1,2 +1 @@")
    with pytest.raises(repair.RepairReceiptError):
        repair.validate_receipt(value)


def test_empty_patch_requires_all_source_hashes_and_sizes_unchanged() -> None:
    value = _receipt()
    value.update(patch="", patch_sha256=repair.digest(b""))
    with pytest.raises(repair.RepairReceiptError):
        repair.validate_receipt(value)
    value["after_sha256"] = list(repair.BEFORE_HASHES)
    assert repair.decode_receipt(repair.encode_receipt(value), failed=False) == value
    value["after_bytes"][0] += 1
    with pytest.raises(repair.RepairReceiptError):
        repair.validate_receipt(value)
