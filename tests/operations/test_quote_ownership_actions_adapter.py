"""Mocked adapter tests: no network, subprocesses or actual measurement."""

import importlib.util
import json
from email.message import Message
from pathlib import Path

import pytest
from test_quote_ownership_actions_guard import REPO, ROOT, WORKFLOW, envelope, fixture

PATH = Path(__file__).resolve().parents[2] / "scripts/ci/quote_ownership_actions_adapter.py"
spec = importlib.util.spec_from_file_location("ownership_actions_adapter", PATH)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def environment():
    return dict(
        GITHUB_ACTIONS="true",
        GITHUB_SERVER_URL="https://github.com",
        GITHUB_API_URL="https://api.github.com",
        GITHUB_REPOSITORY=REPO,
        GITHUB_REPOSITORY_ID="1327018760",
        GITHUB_REF="refs/heads/main",
        GITHUB_SHA="a" * 40,
        GITHUB_WORKFLOW_REF=f"{REPO}/{WORKFLOW}@refs/heads/main",
        GITHUB_WORKFLOW_SHA="a" * 40,
        GITHUB_EVENT_NAME="workflow_dispatch",
        GITHUB_RUN_ID="456",
        GITHUB_RUN_NUMBER="1",
        GITHUB_RUN_ATTEMPT="1",
        GITHUB_JOB="ownership-measurement",
        OCWP_EXPECTED_SOURCE_SHA="a" * 40,
        OCWP_EXPECTED_TREE_SHA="b" * 40,
        OCWP_EXPECTED_WORKFLOW_ID="123",
        OCWP_OWNERSHIP_SETUP_DEADLINE_NS="65000000000",
    )


def responses():
    data = fixture()
    values = {
        x["url"]: x
        for x in [
            data["current_run"],
            data["workflow"],
            data["commit"],
            data["main_ref"],
            *data["history_pages"],
        ]
    }
    values[ROOT] = envelope(
        ROOT,
        dict(
            id=1327018760,
            full_name=REPO,
            private=False,
            visibility="public",
            archived=False,
            disabled=False,
            default_branch="main",
        ),
    )
    for state in adapter.ACTIVE_STATES:
        url = f"{ROOT}/actions/runs?status={state}&per_page=100&page=1"
        values[url] = envelope(
            url,
            dict(
                total_count=1 if state == "in_progress" else 0,
                workflow_runs=[json.loads(data["current_run"]["body"])]
                if state == "in_progress"
                else [],
            ),
        )
    return values


def test_both_phases_fetch_fresh_complete_evidence_and_preserve_setup_deadline():
    for phase, now, expected in [
        ("prebuild", 0, 45_000_000_000),
        ("setup", 40_000_000_000, 65_000_000_000),
    ]:
        values = responses()
        calls = []

        def fetch(url, deadline_ns, calls=calls, values=values):
            calls.append((url, deadline_ns))
            return values[url]

        binding = adapter.collect_guard(
            environment(), phase, fetcher=fetch, clock_ns=lambda now=now: now
        )
        assert binding["run_id"] == "456"
        assert len(calls) == 11 and all(deadline == expected for _, deadline in calls)


@pytest.mark.parametrize(
    "field,value",
    [
        ("GITHUB_ACTIONS", "false"),
        ("GITHUB_API_URL", "https://evil.invalid"),
        ("GITHUB_REPOSITORY_ID", "1"),
        ("GITHUB_JOB", "other"),
        ("GITHUB_RUN_ID", "0456"),
        ("GITHUB_RUN_ATTEMPT", "2"),
        ("OCWP_EXPECTED_WORKFLOW_ID", "0"),
        ("OCWP_EXPECTED_SOURCE_SHA", "bad"),
    ],
)
def test_bad_environment_never_fetches(field, value):
    env = environment()
    env[field] = value
    with pytest.raises(adapter.GuardRefusal):
        adapter.collect_guard(
            env,
            "setup",
            fetcher=lambda *_: pytest.fail("network before admission"),
            clock_ns=lambda: 0,
        )


@pytest.mark.parametrize("deadline", ["0", "-1", "nan", "65000000001", "1.0"])
def test_setup_deadline_not_reset_or_extended(deadline):
    env = environment()
    env["OCWP_OWNERSHIP_SETUP_DEADLINE_NS"] = deadline
    with pytest.raises(adapter.GuardRefusal):
        adapter.collect_guard(
            env, "setup", fetcher=lambda *_: pytest.fail("fetch"), clock_ns=lambda: 0
        )


@pytest.mark.parametrize("state", ["queued", "requested", "waiting", "pending"])
def test_other_active_workflow_blocks(state):
    values = responses()
    url = f"{ROOT}/actions/runs?status={state}&per_page=100&page=1"
    values[url] = envelope(url, dict(total_count=1, workflow_runs=[dict(id=999)]))
    with pytest.raises(adapter.GuardRefusal):
        adapter.collect_guard(
            environment(), "setup", fetcher=lambda u, d: values[u], clock_ns=lambda: 0
        )


def test_public_repository_required():
    values = responses()
    values[ROOT] = envelope(
        ROOT,
        dict(
            id=1327018760,
            full_name=REPO,
            private=True,
            visibility="private",
            archived=False,
            disabled=False,
            default_branch="main",
        ),
    )
    with pytest.raises(adapter.GuardRefusal):
        adapter.collect_guard(
            environment(), "setup", fetcher=lambda u, d: values[u], clock_ns=lambda: 0
        )


class Response:
    def __init__(self, body=b"{}", headers=None, status=200, url=ROOT):
        self.body = body
        self.headers = Message()
        self.status = status
        self.url = url
        self.reads = []
        for key, value in (
            headers if headers is not None else [("Content-Type", "application/json")]
        ):
            self.headers[key] = value

    def geturl(self):
        return self.url

    def read1(self, size):
        self.reads.append(size)
        chunk = self.body[:size]
        self.body = self.body[size:]
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


def test_fetch_has_no_auth_and_reads_in_bounded_chunks():
    response = Response(
        b'{"x":1}', [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", "7")]
    )
    observed = []

    def open_request(request, timeout):
        observed.append((request, timeout))
        return response

    result = adapter.fetch_response(
        ROOT, 5_000_000_000, open_request=open_request, clock_ns=lambda: 0
    )
    assert result["body"] == b'{"x":1}' and max(response.reads) <= 4096
    assert "Authorization" not in observed[0][0].headers and observed[0][1] <= 5


@pytest.mark.parametrize(
    "headers",
    [
        [("Content-Type", "application/json"), ("Content-Type", "application/json")],
        [("Content-Type", "application/json"), ("Content-Length", "2"), ("Content-Length", "2")],
        [("Content-Type", "application/json"), ("Content-Encoding", "gzip")],
        [("Content-Type", "application/json"), ("Location", ROOT)],
        [
            ("Content-Type", "application/json"),
            ("Content-Length", "2"),
            ("Transfer-Encoding", "chunked"),
        ],
        [("Content-Type", "application/json"), ("Content-Length", "65537")],
        [("Content-Type", "application/json"), ("Content-Length", "3")],
        [("Content-Type", "text/html")],
    ],
)
def test_bad_headers_or_truncated_body_refuse(headers):
    with pytest.raises(adapter.GuardRefusal):
        adapter.fetch_response(
            ROOT,
            5_000_000_000,
            open_request=lambda *_args, **_kw: Response(headers=headers),
            clock_ns=lambda: 0,
        )


@pytest.mark.parametrize(
    "response",
    [
        Response(status=302),
        Response(status=403),
        Response(url="https://evil.invalid"),
        Response(b"x" * 65537),
    ],
)
def test_fetch_status_redirect_and_size_refuse(response):
    with pytest.raises(adapter.GuardRefusal):
        adapter.fetch_response(
            ROOT, 5_000_000_000, open_request=lambda *_args, **_kw: response, clock_ns=lambda: 0
        )


def test_total_deadline_includes_body_reads():
    ticks = iter([0, 0, 6_000_000_000])
    with pytest.raises(adapter.GuardRefusal):
        adapter.fetch_response(
            ROOT,
            5_000_000_000,
            open_request=lambda *_args, **_kw: Response(),
            clock_ns=lambda: next(ticks),
        )


def test_failure_receipt_exists_before_fetch_and_is_not_promoted(tmp_path):
    def fail(*_):
        saved = json.loads((tmp_path / "guard-setup.json").read_text())
        assert saved["status"] == "unknown_spent"
        raise OSError("private canary")

    assert (
        adapter.run_phase(environment(), "setup", tmp_path, fetcher=fail, clock_ns=lambda: 0) == 1
    )
    text = (tmp_path / "guard-setup.json").read_text()
    assert "private canary" not in text and json.loads(text)["status"] == "refused_spent"


def test_passed_receipt_is_phase_bound_and_no_overwrite(tmp_path):
    values = responses()
    assert (
        adapter.run_phase(
            environment(), "setup", tmp_path, fetcher=lambda u, d: values[u], clock_ns=lambda: 0
        )
        == 0
    )
    saved = (tmp_path / "guard-setup.json").read_bytes()
    assert json.loads(saved)["status"] == "passed"
    assert (
        adapter.run_phase(
            environment(),
            "setup",
            tmp_path,
            fetcher=lambda *_: pytest.fail("fetch"),
            clock_ns=lambda: 0,
        )
        == 1
    )
    assert (tmp_path / "guard-setup.json").read_bytes() == saved


def test_symlink_evidence_root_refuses(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    assert (
        adapter.run_phase(
            environment(),
            "setup",
            link,
            fetcher=lambda *_: pytest.fail("fetch"),
            clock_ns=lambda: 0,
        )
        == 1
    )
    assert not list(actual.iterdir())


@pytest.mark.parametrize(
    "elapsed,expected", [(0, ("45.000", "5.000")), (61_000_000_000, ("2.000", "2.000"))]
)
def test_setup_external_timeout_and_kill_share_original_deadline(elapsed, expected):
    assert adapter.setup_wrapper_budget(environment(), clock_ns=lambda: elapsed) == expected


def test_expired_setup_cannot_mint_a_new_wrapper_window():
    with pytest.raises(adapter.GuardRefusal):
        adapter.setup_wrapper_budget(environment(), clock_ns=lambda: 65_000_000_000)


def test_dedicated_workflow_is_manual_read_only_and_guarded():
    source = (PATH.parents[2] / ".github/workflows/quote-ownership-measurement.yml").read_text()
    assert "  workflow_dispatch:" in source
    assert "pull_request:" not in source and "\n  push:" not in source
    assert "permissions:\n  contents: read" in source
    assert "cancel-in-progress: false" in source
    assert "timeout-minutes: 55" in source and "persist-credentials: false" in source
    assert "--phase prebuild" in source and "--phase setup" in source
    assert source.index("--phase prebuild") < source.index("docker build")
    setup = source.index("OCWP_OWNERSHIP_SETUP_DEADLINE_NS=")
    guard = source.index("--phase setup")
    supervise = source.index("--supervise")
    assert setup < guard < supervise
    assert "setup_wrapper_budget" in source[setup:guard]
    assert "if: always()" in source and "--finalize" in source
    assert "continue-on-error" not in source and "GITHUB_TOKEN" not in source
    assert "id-token:" not in source and "pages:" not in source


def test_fixture_image_copies_only_existing_initializer_and_public_fixture():
    root = PATH.parents[2]
    source = (root / "infra/docker/quote-ownership-postgres.fixture.Dockerfile").read_text()
    assert "FROM ${PG_BASE_IMAGE}" in source and "RUN " not in source
    assert "COPY infra/compose/postgres-init/10-application-role.sql " in source
    assert (
        "COPY tests/fixtures/quote-ownership/public-synthetic-password.txt "
        "/run/secrets/postgres_password" in source
    )
    fixture = (root / "tests/fixtures/quote-ownership/public-synthetic-password.txt").read_text()
    assert fixture == "ocwp-ownership-fixture-only-not-a-secret-20261029\n"


def test_workflow_pg_pull_and_derived_build_share_existing_window():
    source = (PATH.parents[2] / ".github/workflows/quote-ownership-measurement.yml").read_text()
    assert "pg_deadline = min(deadline, time.monotonic() + 60)" in source
    assert source.count("pg_deadline - time.monotonic()") >= 2
    assert "timeout=590" in source and "deadline = time.monotonic() + 650" in source
    assert "OCWP_OWNERSHIP_PG_BASE_IMAGE_ID" in source


def test_real_opener_disables_proxies_and_rejects_redirect(monkeypatch):
    captured = []

    class Opener:
        def open(self, request, timeout):
            captured.append((request, timeout))
            return "sentinel"

    def build(*handlers):
        captured.extend(handlers)
        return Opener()

    monkeypatch.setattr(adapter.urllib.request, "build_opener", build)
    request = adapter.urllib.request.Request(ROOT)
    assert adapter._open(request, 1.0) == "sentinel"
    assert captured[0].proxies == {}
    with pytest.raises(adapter.GuardRefusal):
        captured[1].redirect_request(None, None, None, None, None, None)


@pytest.mark.parametrize(
    "url",
    [
        "http://api.github.com/repos/" + REPO,
        ROOT + "?token=x",
        ROOT + "/actions/runs?status=success",
        ROOT + "/actions/workflows/123/runs?per_page=100&page=2",
    ],
)
def test_nonfixed_url_never_opens(url):
    with pytest.raises(adapter.GuardRefusal):
        adapter.fetch_response(
            url,
            5_000_000_000,
            open_request=lambda *_a, **_k: pytest.fail("open"),
            clock_ns=lambda: 0,
        )


def test_fetch_failure_no_retry_or_exception_echo():
    calls = []

    def failing(*_a, **_k):
        calls.append(True)
        raise OSError("private-token-canary")

    with pytest.raises(adapter.GuardRefusal) as caught:
        adapter.fetch_response(ROOT, 5_000_000_000, open_request=failing, clock_ns=lambda: 0)
    assert calls == [True] and str(caught.value) == "ownership_guard_refused"


def test_failure_in_finalization_is_not_turned_into_workflow_success():
    source = (PATH.parents[2] / ".github/workflows/quote-ownership-measurement.yml").read_text()
    finalizer = source.split("name: Independently finalize", 1)[1].split("name: Retain", 1)[0]
    assert "set -euo pipefail" in finalizer and "|| true" not in finalizer
    assert "continue-on-error" not in source


def test_root_swap_during_fetch_never_writes_outside_or_passes(tmp_path):
    root = tmp_path / "evidence"
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "guard-prebuild.json"
    sentinel.write_text("untouched sentinel")
    values = responses()
    swapped = []

    def fetch(url, deadline):
        if not swapped:
            root.rename(tmp_path / "original")
            root.symlink_to(outside, target_is_directory=True)
            swapped.append(True)
        return values[url]

    assert (
        adapter.run_phase(environment(), "prebuild", root, fetcher=fetch, clock_ns=lambda: 0) == 1
    )
    assert sentinel.read_text() == "untouched sentinel"
    assert not (outside / "guard-prebuild.final.tmp").exists()
    assert (
        json.loads((tmp_path / "original" / "guard-prebuild.json").read_text())["status"]
        == "unknown_spent"
    )


def test_fallback_writer_refuses_symlink_and_preserves_existing(tmp_path):
    root = tmp_path / "evidence"
    outside = tmp_path / "outside"
    outside.mkdir()
    root.symlink_to(outside, target_is_directory=True)
    assert adapter.write_missing_guard_receipts(root) == 1
    assert not list(outside.iterdir())
    root.unlink()
    root.mkdir()
    sentinel = root / "guard-prebuild.json"
    sentinel.write_text("unchanged")
    assert adapter.write_missing_guard_receipts(root) == 0
    assert sentinel.read_text() == "unchanged"
    assert json.loads((root / "guard-setup.json").read_text())["status"] == "unknown_spent"


def test_fallback_root_swap_after_first_write_cannot_touch_outside(tmp_path, monkeypatch):
    root = tmp_path / "evidence"
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "guard-setup.json"
    sentinel.write_text("outside unchanged")
    original = adapter._write_at
    swapped = []

    def swap(descriptor, name, value):
        result = original(descriptor, name, value)
        if not swapped:
            root.rename(tmp_path / "original")
            root.symlink_to(outside, target_is_directory=True)
            swapped.append(True)
        return result

    monkeypatch.setattr(adapter, "_write_at", swap)
    assert adapter.write_missing_guard_receipts(root) == 1
    assert sentinel.read_text() == "outside unchanged"
    assert sorted(p.name for p in outside.iterdir()) == ["guard-setup.json"]
