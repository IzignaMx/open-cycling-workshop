"""Pure synthetic API/context cases; no HTTP, processes or DB operations."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / "scripts/ci/quote_ownership_actions_guard.py"
spec = importlib.util.spec_from_file_location("ownership_actions_guard", PATH)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

REPO = "IzignaMx/open-cycling-workshop"
WORKFLOW = ".github/workflows/quote-ownership-measurement.yml"
ROOT = f"https://api.github.com/repos/{REPO}"
PROPOSAL_SHA256 = "1951f853a6e6cb1f57d0f66501726cfa370c33e9dd167b9f9a118aae463b8971"


def envelope(url, value):
    return dict(
        url=url,
        status=200,
        content_type="application/json",
        link="",
        body=json.dumps(value).encode(),
    )


def fixture():
    pins = dict(workflow_id=123, source_sha="a" * 40, tree_sha="b" * 40)
    context = dict(
        repository=REPO,
        ref="refs/heads/main",
        sha=pins["source_sha"],
        workflow_ref=f"{REPO}/{WORKFLOW}@refs/heads/main",
        workflow_sha=pins["source_sha"],
        event_name="workflow_dispatch",
        run_id=456,
        run_number=1,
        run_attempt=1,
        authorization_id=PROPOSAL_SHA256,
    )
    repo = dict(id=1327018760, full_name=REPO)
    run = dict(
        id=456,
        workflow_id=123,
        run_number=1,
        run_attempt=1,
        event="workflow_dispatch",
        head_branch="main",
        head_sha=pins["source_sha"],
        path=WORKFLOW,
        status="in_progress",
        conclusion=None,
        repository=repo,
        head_repository=repo,
    )
    return dict(
        context=context,
        pins=pins,
        current_run=envelope(f"{ROOT}/actions/runs/456", run),
        workflow=envelope(
            f"{ROOT}/actions/workflows/123", dict(id=123, path=WORKFLOW, state="active")
        ),
        commit=envelope(
            f"{ROOT}/git/commits/{pins['source_sha']}",
            dict(sha=pins["source_sha"], tree=dict(sha=pins["tree_sha"])),
        ),
        main_ref=envelope(
            f"{ROOT}/git/ref/heads/main",
            dict(ref="refs/heads/main", object=dict(type="commit", sha=pins["source_sha"])),
        ),
        history_pages=[
            envelope(
                f"{ROOT}/actions/workflows/123/runs?per_page=100&page=1",
                dict(total_count=1, workflow_runs=[run]),
            )
        ],
    )


def change_body(data, name, update):
    response = data["history_pages"][0] if name == "history" else data[name]
    body = json.loads(response["body"])
    update(body)
    response["body"] = json.dumps(body).encode()


def refused(data):
    with pytest.raises(guard.GuardRefusal) as caught:
        guard.validate_guard(**data)
    assert str(caught.value) == "ownership_guard_refused"
    assert caught.value.__cause__ is None


def test_valid_first_run_returns_only_closed_binding_without_mutation():
    data = fixture()
    before = copy.deepcopy(data)
    result = guard.validate_guard(**data)
    assert result == dict(
        schema=1,
        authorization_id=PROPOSAL_SHA256,
        repository=REPO,
        workflow_path=WORKFLOW,
        ref="refs/heads/main",
        commit="a" * 40,
        tree="b" * 40,
        workflow_id="123",
        run_id="456",
        run_number=1,
        run_attempt=1,
    )
    assert data == before


@pytest.mark.parametrize(
    "key,value",
    [
        ("repository", "evil/repo"),
        ("ref", "refs/tags/main"),
        ("sha", "c" * 40),
        ("workflow_ref", f"{REPO}/.github/workflows/other.yml@refs/heads/main"),
        ("workflow_sha", "c" * 40),
        ("event_name", "push"),
        ("run_id", True),
        ("run_id", "456"),
        ("run_id", 0),
        ("run_number", 2),
        ("run_number", True),
        ("run_attempt", 2),
        ("run_attempt", 1.0),
        ("authorization_id", "rotated"),
        ("extra", "private canary"),
    ],
)
def test_bad_context_refuses(key, value):
    data = fixture()
    data["context"][key] = value
    refused(data)


@pytest.mark.parametrize(
    "key,value",
    [
        ("workflow_id", True),
        ("workflow_id", 0),
        ("workflow_id", "123"),
        ("source_sha", "A" * 40),
        ("tree_sha", "b" * 39),
        ("extra", 1),
    ],
)
def test_bad_pins_refuse(key, value):
    data = fixture()
    data["pins"][key] = value
    refused(data)


@pytest.mark.parametrize(
    "key,value",
    [
        ("id", 457),
        ("workflow_id", 124),
        ("run_number", 2),
        ("run_attempt", True),
        ("event", "push"),
        ("head_branch", "other"),
        ("head_sha", "c" * 40),
        ("path", ".github/workflows/rotated.yml"),
        ("status", "queued"),
        ("conclusion", "success"),
        ("repository", dict(id=1, full_name=REPO)),
        ("head_repository", dict(id=1327018760, full_name="fork/repo")),
    ],
)
@pytest.mark.parametrize("source", ["current_run", "history"])
def test_bad_run_record_refuses(source, key, value):
    data = fixture()
    change_body(
        data,
        source,
        lambda body: (body["workflow_runs"][0] if source == "history" else body).__setitem__(
            key, value
        ),
    )
    refused(data)


@pytest.mark.parametrize("name", ["current_run", "workflow", "commit", "main_ref", "history"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("status", 403),
        ("status", True),
        ("url", "https://evil.invalid/private"),
        ("content_type", "text/html"),
        ("link", '<https://api.github.com/next>; rel="next"'),
        ("body", b"x" * 65537),
        ("body", b'{"x":1,"x":2}'),
        ("body", b'{"nested":{"x":1,"x":2}}'),
        ("body", b'{"x":NaN}'),
        ("body", b"\xff"),
        ("body", b"[]"),
        ("body", b"null"),
    ],
)
def test_bad_response_refuses(name, field, value):
    data = fixture()
    response = data["history_pages"][0] if name == "history" else data[name]
    response[field] = value
    refused(data)


@pytest.mark.parametrize("count", [0, 2, 101, True, 1.0, "1"])
def test_other_or_unknown_history_spends_attempt(count):
    data = fixture()
    change_body(data, "history", lambda body: body.__setitem__("total_count", count))
    refused(data)


@pytest.mark.parametrize(
    "kind", ["duplicate_record", "empty", "duplicate_page", "missing_page", "filtered_url"]
)
def test_history_completeness(kind):
    data = fixture()
    if kind == "duplicate_record":
        change_body(data, "history", lambda b: b["workflow_runs"].append(b["workflow_runs"][0]))
    if kind == "empty":
        change_body(data, "history", lambda b: b.__setitem__("workflow_runs", []))
    if kind == "duplicate_page":
        data["history_pages"] *= 2
    if kind == "missing_page":
        data["history_pages"] = []
    if kind == "filtered_url":
        data["history_pages"][0]["url"] += "&event=workflow_dispatch"
    refused(data)


@pytest.mark.parametrize(
    "name,field,value",
    [
        ("workflow", "id", 124),
        ("workflow", "state", "disabled_manually"),
        ("workflow", "path", ".github/workflows/other.yml"),
        ("commit", "sha", "c" * 40),
        ("commit", "tree", dict(sha="c" * 40)),
    ],
)
def test_independent_metadata_must_match(name, field, value):
    data = fixture()
    change_body(data, name, lambda b: b.__setitem__(field, value))
    refused(data)


@pytest.mark.parametrize(
    "target", [dict(type="tag", sha="a" * 40), dict(type="commit", sha="c" * 40)]
)
def test_current_main_cannot_drift(target):
    data = fixture()
    change_body(data, "main_ref", lambda b: b.__setitem__("object", target))
    refused(data)


@pytest.mark.parametrize(
    "body", [b'{"x":1e999}', b'{"x":-1e999}', b"\xef\xbb\xbf{}", b"[" * 2000 + b"]" * 2000]
)
def test_parser_envelope_corner_cases(body):
    data = fixture()
    data["current_run"]["body"] = body
    refused(data)


@pytest.mark.parametrize(
    "part", ["context", "pins", "current_run", "workflow", "commit", "main_ref"]
)
def test_missing_and_wrong_shape_refuse(part):
    data = fixture()
    data[part] = {}
    refused(data)
    data[part] = None
    refused(data)


def test_extra_api_metadata_allowed_not_returned():
    data = fixture()
    change_body(data, "current_run", lambda b: b.__setitem__("display_title", "private canary"))
    assert "private canary" not in repr(guard.validate_guard(**data))
