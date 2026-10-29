"""Pure data guard for the one-shot measurement; never fetches or starts work.

Trusted source/tree pins are externally reviewed inputs, not proof of review.
This is not a durable consumption ledger or protection against admin history edits.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, cast

REPOSITORY = "IzignaMx/open-cycling-workshop"
REPOSITORY_ID = 1327018760
WORKFLOW_PATH = ".github/workflows/quote-ownership-measurement.yml"
PROPOSAL_SHA256 = "1951f853a6e6cb1f57d0f66501726cfa370c33e9dd167b9f9a118aae463b8971"
REF = "refs/heads/main"
API_ROOT = f"https://api.github.com/repos/{REPOSITORY}"
MAX_RESPONSE_BYTES = 65536


class GuardRefusal(ValueError):
    def __init__(self) -> None:
        super().__init__("ownership_guard_refused")


def _require(condition: bool) -> None:
    if not condition:
        raise GuardRefusal()


def _object(value: object, keys: set[str] | None = None) -> dict[str, Any]:
    _require(type(value) is dict)
    result = cast(dict[str, Any], value)
    if keys is not None:
        _require(set(result) == keys)
    return result


def _equal(value: object, expected: object) -> None:
    _require(type(value) is type(expected) and value == expected)


def _positive(value: object) -> None:
    _require(type(value) is int and 0 < value < 10**20)


def _sha(value: object) -> None:
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value) is not None)


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _float(value: str) -> float:
    number = float(value)
    _require(math.isfinite(number))
    return number


def _constant(_: str) -> None:
    raise GuardRefusal()


def _response(value: object, url: str) -> dict[str, Any]:
    response = _object(value, {"url", "status", "content_type", "link", "body"})
    for key, expected in (
        ("url", url),
        ("status", 200),
        ("content_type", "application/json"),
        ("link", ""),
    ):
        _equal(response[key], expected)
    body = response["body"]
    _require(type(body) is bytes and 0 < len(body) <= MAX_RESPONSE_BYTES)
    return _object(
        json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
            parse_float=_float,
        )
    )


def _run(value: object, context: dict[str, Any], pins: dict[str, Any]) -> None:
    run = _object(value)
    expected = {
        "id": context["run_id"],
        "workflow_id": pins["workflow_id"],
        "run_number": 1,
        "run_attempt": 1,
        "event": "workflow_dispatch",
        "head_branch": "main",
        "head_sha": pins["source_sha"],
        "path": WORKFLOW_PATH,
        "status": "in_progress",
        "conclusion": None,
    }
    for key, item in expected.items():
        _equal(run[key], item)
    for key in ("repository", "head_repository"):
        repo = _object(run[key])
        _equal(repo["id"], REPOSITORY_ID)
        _equal(repo["full_name"], REPOSITORY)


def validate_guard(
    *,
    context: object,
    pins: object,
    current_run: object,
    workflow: object,
    commit: object,
    main_ref: object,
    history_pages: object,
) -> dict[str, object]:
    """Refuse any missing/ambiguous metadata; return only source/run binding.

    All responses must be bounded, public, unredirected API reads from the planned
    same-job adapter. This pure function cannot authenticate their origin.
    """
    try:
        expected = _object(pins, {"workflow_id", "source_sha", "tree_sha"})
        _positive(expected["workflow_id"])
        _sha(expected["source_sha"])
        _sha(expected["tree_sha"])
        actual = _object(
            context,
            {
                "repository",
                "ref",
                "sha",
                "workflow_ref",
                "workflow_sha",
                "event_name",
                "run_id",
                "run_number",
                "run_attempt",
                "authorization_id",
            },
        )
        for key, value in {
            "repository": REPOSITORY,
            "ref": REF,
            "sha": expected["source_sha"],
            "workflow_ref": f"{REPOSITORY}/{WORKFLOW_PATH}@{REF}",
            "workflow_sha": expected["source_sha"],
            "event_name": "workflow_dispatch",
            "run_number": 1,
            "run_attempt": 1,
            "authorization_id": PROPOSAL_SHA256,
        }.items():
            _equal(actual[key], value)
        _positive(actual["run_id"])
        workflow_url = f"{API_ROOT}/actions/workflows/{expected['workflow_id']}"
        _run(
            _response(current_run, f"{API_ROOT}/actions/runs/{actual['run_id']}"), actual, expected
        )
        descriptor = _response(workflow, workflow_url)
        for key, value in {
            "id": expected["workflow_id"],
            "path": WORKFLOW_PATH,
            "state": "active",
        }.items():
            _equal(descriptor[key], value)
        source = _response(commit, f"{API_ROOT}/git/commits/{expected['source_sha']}")
        _equal(source["sha"], expected["source_sha"])
        _equal(_object(source["tree"])["sha"], expected["tree_sha"])
        branch = _response(main_ref, f"{API_ROOT}/git/ref/heads/main")
        _equal(branch["ref"], REF)
        target = _object(branch["object"])
        _equal(target["type"], "commit")
        _equal(target["sha"], expected["source_sha"])
        _require(type(history_pages) is list and len(history_pages) == 1)
        history = _response(history_pages[0], f"{workflow_url}/runs?per_page=100&page=1")  # type: ignore[index]
        _equal(history["total_count"], 1)
        runs = history["workflow_runs"]
        _require(type(runs) is list and len(runs) == 1)
        _run(runs[0], actual, expected)
        return {
            "schema": 1,
            "authorization_id": PROPOSAL_SHA256,
            "repository": REPOSITORY,
            "workflow_path": WORKFLOW_PATH,
            "ref": REF,
            "commit": expected["source_sha"],
            "tree": expected["tree_sha"],
            "workflow_id": str(expected["workflow_id"]),
            "run_id": str(actual["run_id"]),
            "run_number": 1,
            "run_attempt": 1,
        }
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        raise GuardRefusal() from None
