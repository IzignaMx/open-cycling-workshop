"""One fixed source-only Ruff repair receipt; no container controller or patch application."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import zlib
from pathlib import Path

TARGET_COMMIT = "dff067af840b8e83d87d17ae6fa36cfd10e75653"
TARGET_TREE = "c3ba32738c5996badcf575bc47dfac9b9499fb4f"
INPUT_ROOT = Path("/opt/quote-static-repair-input")
REPORT_PATH = "/tmp/quote-static-repair-proposal.json"
MARKER = b"OCWP_STATIC_REPAIR_V1:"
TOOL_OUTPUT_LIMIT = 16 * 1024
FILE_LIMIT = 128 * 1024
SOURCE_TOTAL_LIMIT = 512 * 1024
COMPRESSED_LIMIT = 10 * 1024
ENVELOPE_LIMIT = 14 * 1024
EXPANDED_LIMIT = 256 * 1024
PATCH_LIMIT = 192 * 1024
MAX_DIAGNOSTICS = 512
PATHS = (
    'services/platform/src/cycling_workshop/quotes/effects.py',
    'services/platform/src/cycling_workshop/quotes/reconstruction.py',
    'services/platform/src/cycling_workshop/quotes/repository.py',
    'services/platform/src/cycling_workshop/quotes/responses.py',
    'services/platform/src/cycling_workshop/quotes/service.py',
    'services/platform/src/cycling_workshop/sync/writes.py',
    'services/platform/tests/quotes/test_quote_application_service.py',
    'services/platform/tests/quotes/test_quote_atomic_effects.py',
    'services/platform/tests/quotes/test_quote_command_response.py',
    'services/platform/tests/quotes/test_quote_driver_budgets.py',
    'services/platform/tests/quotes/test_quote_reconstruction.py',
    'services/platform/tests/quotes/test_quote_result_codec_once.py',
    'services/platform/tests/quotes/test_quote_single_pass.py',
    'scripts/ci/quote_capacity_micro.py',
    'scripts/ci/quote_collection_regression.py',
    'scripts/ci/quote_guard_bootstrap.py',
    'tests/operations/test_quote_capacity_micro.py',
    'tests/operations/test_quote_service_collection.py',
    'tests/operations/test_quote_service_static_contracts.py',
)
BEFORE_HASHES = (
    'be28112ecb601f72fbc813fc193418c2dae5f9c75862a6916fdd317f2204993c',
    'bf098222a4665599b7962646048bb8555305aef2329e4e2e1ac04f86600109c2',
    '82364c98fcfdf6d111f5c5b1b258ded541c18e459180dba19f479e97b7ba2606',
    'cf667e1b2e3ccdb6c9a746a8517ab4f7076e97d2bc0f79f64ee6bde00985490a',
    'acd427a9fdd454bbfeafdbebc1c24186b5ce7f17fcd18aaccb88f4cf1917424b',
    '9cba8cf7d795b4bee01dd91d5b98f5341400ba899e6f9148eff81f4c3410944f',
    'bd7eba2b375444adc48e07af183e739f161cdd6ef400de110cb572f7c14467ce',
    '86e8ec0a3f939d7139a08613e89359dd4824cbfc2b5a35ce62c119309f38bced',
    'a3eb008d0e1d77d71068b355b88c8c8d64fc6e3223566a7119f71923143c9752',
    '389c355166067a89ba2772776c3dbf07c8814060eeb560c6bf6252c04f5c7025',
    '9ab93cf84831241cff51885a60a6bb6a1b0d39216e798565b4a497322ab8d653',
    '3781fcb840b470202cdd44546cb6eca13367690b4fe7f8c049325fffb50b8b23',
    '7aea93ffc2f01e5d667a5da0925ead7646501b70465db65bc6cd9fe4ee809dd7',
    'd0d634b4061f95aff982e8743cfea35c7a3e9cd6199e8a70ae25810bbb47a202',
    '8a856286199a6f5881e518a9ab567126514ca5445deb4749869040fe1948a997',
    '2feb6d2ce1fe035ef3df2fc3b1285fd6c287f47491dd55a5030d0c7d782d985c',
    '58b20f714fd268b54b9b8c89d6d434214695a1c00a31a29cd2636c3303e17caf',
    'c58c97cdf9e3df128f08daf9c6abb261405fee144ff5effb3c4707f15977877e',
    'cec5f7cd99f2b3023744cd020e7081ad5517581afdaac0cbccae793b29334852',
)
BEFORE_SIZES = (7672, 26142, 29508, 5846, 22659, 3632, 13048, 15482, 12665, 1158, 6781, 12966, 15666, 62247, 28885, 31112, 59374, 2012, 6456)
CONFIG_HASH = '3c800aaa57197c26a88afb5caa3b1dbcdd1b970c97f04888fb63bc69757a53dc'
RULES = (
    'B006',
    'B007',
    'B008',
    'B009',
    'B010',
    'B011',
    'B017',
    'B018',
    'B023',
    'B904',
    'B905',
    'E402',
    'E501',
    'E711',
    'E712',
    'E713',
    'E714',
    'E721',
    'E722',
    'E731',
    'F401',
    'F402',
    'F403',
    'F405',
    'F541',
    'F601',
    'F602',
    'F621',
    'F622',
    'F631',
    'F632',
    'F633',
    'F634',
    'F701',
    'F702',
    'F704',
    'F706',
    'F707',
    'F811',
    'F821',
    'F822',
    'F823',
    'F841',
    'F901',
    'I001',
    'I002',
    'RUF005',
    'RUF010',
    'RUF012',
    'RUF013',
    'RUF015',
    'RUF019',
    'RUF020',
    'RUF022',
    'RUF023',
    'RUF100',
    'SIM102',
    'SIM103',
    'SIM105',
    'SIM108',
    'SIM110',
    'SIM115',
    'SIM117',
    'SIM118',
    'SIM201',
    'SIM202',
    'SIM208',
    'SIM210',
    'SIM211',
    'SIM212',
    'UP006',
    'UP007',
    'UP008',
    'UP009',
    'UP010',
    'UP015',
    'UP017',
    'UP018',
    'UP024',
    'UP031',
    'UP032',
    'UP034',
    'UP035',
    'UP037',
    'UP038',
    'UP039',
    'UP040',
    'UP041',
    'UP042',
    'UP043',
    'UP045',
    'format',
)


class RepairReceiptError(ValueError):
    pass


def strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RepairReceiptError("duplicate_key")
        result[key] = value
    return result


def reject_constant(_value: str) -> None:
    raise RepairReceiptError("nonfinite")


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _integer(value: object, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def _hash(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def patch_paths(patch: str) -> list[int]:
    """Validate fixed-path unified headers and exact hunk counts, without applying it."""
    if type(patch) is not str:
        raise RepairReceiptError("patch_text")
    if patch == "":
        return []
    if "\x00" in patch or not patch.endswith("\n"):
        raise RepairReceiptError("patch_text")
    if not 0 < len(patch.encode("utf-8")) <= PATCH_LIMIT:
        raise RepairReceiptError("patch_size")
    lines = patch.splitlines(keepends=True)
    position, previous = 0, -1
    changed: list[int] = []
    while position < len(lines):
        header = lines[position]
        if not header.startswith("--- a/") or not header.endswith("\n"):
            raise RepairReceiptError("patch_header")
        path = header[6:-1]
        if path not in PATHS:
            raise RepairReceiptError("patch_path")
        index = PATHS.index(path)
        if index <= previous or lines[position + 1:position + 2] != [f"+++ b/{path}\n"]:
            raise RepairReceiptError("patch_order")
        previous = index
        changed.append(index)
        position += 2
        hunks = 0
        while position < len(lines) and lines[position].startswith("@@ "):
            match = re.fullmatch(r"@@ -([0-9]+)(?:,([0-9]+))? \+([0-9]+)(?:,([0-9]+))? @@\n", lines[position])
            if match is None or any(len(v) > 7 for v in match.groups() if v is not None):
                raise RepairReceiptError("patch_hunk")
            old_start, old_count, new_start, new_count = match.groups()
            if int(old_start) > 1_000_000 or int(new_start) > 1_000_000:
                raise RepairReceiptError("patch_hunk")
            old, new = int(old_count or 1), int(new_count or 1)
            if not 0 <= old <= 1_000_000 or not 0 <= new <= 1_000_000 or old + new == 0:
                raise RepairReceiptError("patch_hunk")
            position += 1
            edits = 0
            while old or new:
                if position >= len(lines) or not lines[position].endswith("\n"):
                    raise RepairReceiptError("patch_truncated")
                prefix = lines[position][:1]
                if prefix == " ":
                    old, new = old - 1, new - 1
                elif prefix == "-":
                    old -= 1
                    edits += 1
                elif prefix == "+":
                    new -= 1
                    edits += 1
                else:
                    raise RepairReceiptError("patch_line")
                if old < 0 or new < 0:
                    raise RepairReceiptError("patch_hunk_count")
                position += 1
            if not edits:
                raise RepairReceiptError("patch_empty_hunk")
            hunks += 1
        if not hunks:
            raise RepairReceiptError("patch_missing_hunk")
    return changed


def validate_receipt(value: object) -> dict[str, object]:
    fields = {
        "schema", "scope", "target_commit", "target_tree", "before_sha256", "after_sha256",
        "after_bytes", "tools", "patch", "patch_sha256",
    }
    if type(value) is not dict or set(value) != fields:
        raise RepairReceiptError("receipt_shape")
    if (type(value["schema"]) is not int or value["schema"] != 1
            or value["scope"] != "repair_proposal_only"
            or value["target_commit"] != TARGET_COMMIT or value["target_tree"] != TARGET_TREE
            or value["before_sha256"] != list(BEFORE_HASHES)):
        raise RepairReceiptError("receipt_identity")
    after, sizes = value["after_sha256"], value["after_bytes"]
    if (type(after) is not list or len(after) != 19 or not all(_hash(v) for v in after)
            or type(sizes) is not list or len(sizes) != 19
            or not all(_integer(v, 1, FILE_LIMIT) for v in sizes)
            or sum(sizes) > SOURCE_TOTAL_LIMIT):
        raise RepairReceiptError("receipt_sources")
    patch = value["patch"]
    changed = patch_paths(patch)
    if (not _hash(value["patch_sha256"]) or value["patch_sha256"] != digest(patch.encode("utf-8"))
            or changed != [i for i in range(19) if after[i] != BEFORE_HASHES[i]]):
        raise RepairReceiptError("receipt_patch_binding")
    if any(sizes[i] != BEFORE_SIZES[i] for i in range(19) if i not in changed):
        raise RepairReceiptError("receipt_unchanged_size")
    rows = value["tools"]
    if type(rows) is not list or len(rows) != 4:
        raise RepairReceiptError("receipt_tools")
    tool_fields = {
        "tool", "returncode", "output_bytes", "diagnostics", "unsupported_lines",
        "unparsed_lines", "diagnostics_complete", "reported_remaining",
    }
    for index, row in enumerate(rows):
        if (type(row) is not dict or set(row) != tool_fields
                or type(row["tool"]) is not int or row["tool"] != index
                or not _integer(row["returncode"], 0, 1)
                or (index == 1 and row["returncode"] != 0)
                or not _integer(row["output_bytes"], 0, TOOL_OUTPUT_LIMIT - 1)
                or not _integer(row["unsupported_lines"], 0, TOOL_OUTPUT_LIMIT)
                or not _integer(row["unparsed_lines"], 0, TOOL_OUTPUT_LIMIT)
                or type(row["diagnostics_complete"]) is not bool
                or (row["reported_remaining"] is not None
                    and not _integer(row["reported_remaining"], 0, MAX_DIAGNOSTICS))):
            raise RepairReceiptError("receipt_tool_status")
        diagnostics = row["diagnostics"]
        if type(diagnostics) is not list or len(diagnostics) > MAX_DIAGNOSTICS:
            raise RepairReceiptError("receipt_diagnostics")
        seen: set[tuple[int, int, int]] = set()
        for diagnostic in diagnostics:
            if (type(diagnostic) is not list or len(diagnostic) != 3
                    or not _integer(diagnostic[0], 0, 18)
                    or not _integer(diagnostic[1], 0, 1_000_000)
                    or not _integer(diagnostic[2], 0, len(RULES) - 1)):
                raise RepairReceiptError("receipt_diagnostic_shape")
            item = tuple(diagnostic)
            if item in seen or ((RULES[item[2]] == "format") != (index in (1, 3))):
                raise RepairReceiptError("receipt_diagnostic_identity")
            seen.add(item)
        if row["diagnostics_complete"] and (
            row["unsupported_lines"] or row["reported_remaining"] != len(diagnostics)
        ):
            raise RepairReceiptError("receipt_diagnostic_count")
        if row["returncode"] == 0 and (diagnostics or row["unsupported_lines"]):
            raise RepairReceiptError("receipt_clean_status")
    return value


def encode_receipt(value: object) -> bytes:
    raw = canonical(validate_receipt(value))
    if len(raw) > EXPANDED_LIMIT:
        raise RepairReceiptError("expanded_limit")
    compressed = zlib.compress(raw, level=9)
    if len(compressed) > COMPRESSED_LIMIT:
        raise RepairReceiptError("compressed_limit")
    envelope = canonical({
        "schema": 1, "expanded_bytes": len(raw), "sha256": digest(raw),
        "zlib_base64": base64.b64encode(compressed).decode("ascii"),
    })
    if len(envelope) + len(MARKER) + 2 > ENVELOPE_LIMIT:
        raise RepairReceiptError("envelope_limit")
    return envelope


def decode_receipt(raw: bytes, *, failed: bool) -> dict[str, object]:
    """Bounded data decoding only. No source import, execution or patch application."""
    if type(raw) is not bytes or not 0 < len(raw) <= ENVELOPE_LIMIT:
        raise RepairReceiptError("envelope_limit")
    try:
        envelope = json.loads(raw.decode("ascii"), object_pairs_hook=strict_object,
                              parse_constant=reject_constant)
        if (type(envelope) is not dict
                or set(envelope) != {"schema", "expanded_bytes", "sha256", "zlib_base64"}
                or type(envelope["schema"]) is not int or envelope["schema"] != 1
                or not _integer(envelope["expanded_bytes"], 1, EXPANDED_LIMIT)
                or not _hash(envelope["sha256"]) or type(envelope["zlib_base64"]) is not str
                or canonical(envelope) != raw):
            raise RepairReceiptError("envelope_shape")
        compressed = base64.b64decode(envelope["zlib_base64"], validate=True)
        if (not 0 < len(compressed) <= COMPRESSED_LIMIT
                or base64.b64encode(compressed).decode("ascii") != envelope["zlib_base64"]):
            raise RepairReceiptError("compressed_limit")
        decoder = zlib.decompressobj()
        expanded = decoder.decompress(compressed, EXPANDED_LIMIT + 1)
        if (len(expanded) != envelope["expanded_bytes"] or len(expanded) > EXPANDED_LIMIT
                or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail
                or digest(expanded) != envelope["sha256"]):
            raise RepairReceiptError("compressed_integrity")
        value = json.loads(expanded.decode("ascii"), object_pairs_hook=strict_object,
                           parse_constant=reject_constant)
        if canonical(value) != expanded:
            raise RepairReceiptError("receipt_encoding")
        result = validate_receipt(value)
        clean = all(result["tools"][index]["returncode"] == 0 for index in (2, 3))
        if clean == failed:
            raise RepairReceiptError("receipt_outcome_mismatch")
        return result
    except (ValueError, TypeError, KeyError, IndexError, RecursionError, zlib.error) as error:
        raise RepairReceiptError("repair_receipt_invalid") from error


def decode_failure_marker(raw: bytes, *, failure: dict[str, int]) -> dict[str, object]:
    expected = {
        "schema": 1, "stage": 3, "session_exitstatus": 1, "collection_count": 6,
        "collection_errors": 0, "unhandled_errors": 0, "protocol_errors": 0,
        "report_count": 18, "setup_reports": 6, "call_reports": 6,
        "teardown_reports": 6, "failed_reports": 1, "skipped_reports": 0,
    }
    if (type(raw) is not bytes or len(raw) >= TOOL_OUTPUT_LIMIT or raw.count(MARKER) != 1
            or failure != expected or any(type(v) is not int for v in failure.values())):
        raise RepairReceiptError("repair_failure_protocol")
    lines = [line for line in raw.split(b"\n")[:-1] if line.startswith(MARKER)]
    if len(lines) != 1 or len(lines[0]) + 1 > ENVELOPE_LIMIT:
        raise RepairReceiptError("repair_failure_marker")
    return decode_receipt(lines[0][len(MARKER):], failed=True)


def retain_proposal(value: dict[str, object], evidence: Path) -> dict[str, object]:
    """Write the already-validated proposed patch artifact, never apply it."""
    evidence.parent.mkdir(parents=True, exist_ok=True)
    target = evidence.parent / "quote-static-repair-proposal.patch"
    data = value["patch"].encode("utf-8")
    target.write_bytes(data)
    return {key: item for key, item in value.items() if key != "patch"} | {
        "patch_artifact": target.name, "patch_bytes": len(data),
        "final_ruff_clean": all(value["tools"][index]["returncode"] == 0 for index in (2, 3)),
    }
