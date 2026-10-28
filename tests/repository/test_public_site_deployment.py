from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    assert path.is_file(), "live public verifier is not implemented"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verifier():
    return load("public_live_verifier", ROOT / "scripts/docs/verify_public_site.py")


@pytest.fixture
def site(tmp_path, request):
    builder = load("public_live_builder", ROOT / "scripts/docs/build_public_site.py")
    target = tmp_path / "built"
    if getattr(request, "param", False):
        builder.runtime_paths = lambda _repo: set()
    builder.build(ROOT / "docs/site", target)
    return target


def fake_fetch(mod, site, calls):
    def fetch(url):
        calls.append(url)
        name = url.removeprefix(mod.EXPECTED_URL) or "index.html"
        return mod.Fetched(200, url, (site / name).read_bytes())

    return fetch


def test_exact_eight_contents_verified_and_capture_not_claimed_as_deployment(site):
    mod = verifier()
    calls = []
    result = mod.verify(mod.EXPECTED_URL, site, fetch=fake_fetch(mod, site, calls))
    assert len(calls) == len(result["files"]) == 8
    assert calls[0] == mod.EXPECTED_URL
    assert all(url.startswith(mod.EXPECTED_URL) for url in calls)
    assert not any(".nojekyll" in url for url in calls)
    assert (
        result["capture_source"]
        == json.loads((site / "screenshots.json").read_text())["source_commit"]
    )
    assert result["nojekyll"] == "local empty marker; not fetched"
    assert "deployment_sha" not in result and "source_sha" not in result
    assert result["files"]["index.html"]["bytes"] == (site / "index.html").stat().st_size


@pytest.mark.parametrize(
    "url",
    [
        "http://izignamx.github.io/open-cycling-workshop/",
        "https://example.com/open-cycling-workshop/",
        "https://user@izignamx.github.io/open-cycling-workshop/",
        "https://izignamx.github.io:443/open-cycling-workshop/",
        "https://izignamx.github.io/open-cycling-workshop/?x=1",
        "https://izignamx.github.io/open-cycling-workshop/#x",
        "https://izignamx.github.io/open-cycling-workshop",
        "https://izignamx.github.io/",
        "https://izignamx.github.io/open-cycling-workshop/../other/",
        "https://IZIGNAMX.github.io/open-cycling-workshop/",
        " https://izignamx.github.io/open-cycling-workshop/",
        "https://izignamx.github.io/open-cycling-workshop/\n",
    ],
)
def test_bad_urls_fail_before_transport(site, url):
    mod = verifier()
    calls = []
    with pytest.raises(mod.VerificationError, match="E_URL"):
        mod.verify(url, site, fetch=fake_fetch(mod, site, calls))
    assert calls == []


@pytest.mark.parametrize(
    "mutation", ["missing", "extra", "extra_directory", "symlink", "marker", "oversize", "fifo"]
)
def test_bad_local_leaf_fails_before_transport(site, mutation):
    mod = verifier()
    calls = []
    if mutation == "missing":
        (site / "styles.css").unlink()
    elif mutation == "extra":
        (site / "private.env").write_text("private")
    elif mutation == "extra_directory":
        (site / "extra").mkdir()
    elif mutation == "symlink":
        (site / "styles.css").unlink()
        (site / "styles.css").symlink_to(ROOT / "docs/site/styles.css")
    elif mutation == "marker":
        (site / ".nojekyll").write_text("unexpected")
    elif mutation == "oversize":
        (site / "styles.css").write_bytes(b"x" * (mod.MAX_FILE_BYTES + 1))
    else:
        import os

        (site / "styles.css").unlink()
        os.mkfifo(site / "styles.css")
    with pytest.raises(mod.VerificationError):
        mod.verify(mod.EXPECTED_URL, site, fetch=fake_fetch(mod, site, calls))
    assert calls == []


def test_symlink_directory_rejected(site, tmp_path):
    mod = verifier()
    link = tmp_path / "linked"
    link.symlink_to(site, target_is_directory=True)
    with pytest.raises(mod.VerificationError):
        mod.verify(mod.EXPECTED_URL, link, fetch=lambda url: pytest.fail("network"))


@pytest.mark.parametrize("status", [301, 302, 307, 308, 404, 503])
def test_non_200_and_redirect_refused(site, status):
    mod = verifier()
    with pytest.raises(mod.VerificationError, match="E_HTTP"):
        mod.verify(mod.EXPECTED_URL, site, fetch=lambda url: mod.Fetched(status, url, b""))


def test_changed_final_url_refused(site):
    mod = verifier()
    with pytest.raises(mod.VerificationError, match="E_REDIRECT"):
        mod.verify(
            mod.EXPECTED_URL, site, fetch=lambda url: mod.Fetched(200, "https://example.com/", b"")
        )


@pytest.mark.parametrize(
    "body", [b"changed", b"x" * (2 * 1024 * 1024 + 1)], ids=["mismatch", "oversized"]
)
def test_mismatch_or_oversize_live_bytes_refused(site, body):
    mod = verifier()
    with pytest.raises(mod.VerificationError):
        mod.verify(mod.EXPECTED_URL, site, fetch=lambda url: mod.Fetched(200, url, body))


def test_capture_identity_disagreement_rejected_before_network(site):
    mod = verifier()
    (site / "build-info.json").write_text(
        json.dumps({"capture_source": "0" * 40, "capture_status": "current-runtime"})
    )
    with pytest.raises(mod.VerificationError, match="E_PROVENANCE"):
        mod.verify(mod.EXPECTED_URL, site, fetch=lambda url: pytest.fail("network"))


def test_redirect_handler_does_not_create_another_request():
    mod = verifier()
    assert (
        mod.NoRedirect().redirect_request(None, None, 302, "moved", {}, "https://example.com/")
        is None
    )


def test_default_transport_bounds_read_and_disables_proxies_and_redirects(monkeypatch):
    mod = verifier()
    calls = []

    class Response:
        status = 200

        def __init__(self):
            self.headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            calls.append("closed")

        def geturl(self):
            return mod.EXPECTED_URL

        def read(self, size):
            calls.append(size)
            return b"public"

    class Opener:
        def open(self, request, *, timeout):
            assert request.full_url == mod.EXPECTED_URL
            assert request.get_header("Accept-encoding") == "identity"
            assert timeout == mod.REQUEST_SECONDS
            return Response()

    def opener(*handlers):
        assert handlers[0].proxies == {}
        assert isinstance(handlers[1], mod.NoRedirect)
        return Opener()

    monkeypatch.setattr(mod, "build_opener", opener)
    result = mod.fetch_public(mod.EXPECTED_URL)
    assert result == mod.Fetched(200, mod.EXPECTED_URL, b"public")
    assert calls == [mod.MAX_FILE_BYTES + 1, "closed"]
    assert mod.signal.getitimer(mod.signal.ITIMER_REAL) == (0.0, 0.0)


@pytest.mark.parametrize("failure", ["redirect", "network", "timeout"])
def test_transport_errors_fixed_and_do_not_echo_remote_context(monkeypatch, failure):
    mod = verifier()

    class Opener:
        def open(self, request, *, timeout):
            if failure == "redirect":
                raise mod.HTTPError(request.full_url, 302, "PRIVATE-REMOTE-CONTEXT", {}, None)
            if failure == "network":
                raise mod.URLError("PRIVATE-REMOTE-CONTEXT")
            handler = mod.signal.getsignal(mod.signal.SIGALRM)
            handler(mod.signal.SIGALRM, None)

    monkeypatch.setattr(mod, "build_opener", lambda *handlers: Opener())
    with pytest.raises(mod.VerificationError) as caught:
        mod.fetch_public(mod.EXPECTED_URL)
    assert (
        str(caught.value)
        == {"redirect": "E_HTTP", "network": "E_NETWORK", "timeout": "E_TIMEOUT"}[failure]
    )
    assert mod.signal.getitimer(mod.signal.ITIMER_REAL) == (0.0, 0.0)


def test_fetch_rejects_nonallowlisted_resource_before_opener(monkeypatch):
    mod = verifier()
    monkeypatch.setattr(mod, "build_opener", lambda *args: pytest.fail("opener"))
    with pytest.raises(mod.VerificationError, match="E_URL"):
        mod.fetch_public(mod.EXPECTED_URL + "private.env")


def test_existing_deadline_not_overwritten(monkeypatch):
    mod = verifier()
    monkeypatch.setattr(mod.signal, "getitimer", lambda which: (1.0, 0.0))
    monkeypatch.setattr(mod.signal, "setitimer", lambda *args: pytest.fail("timer overwritten"))
    with pytest.raises(mod.VerificationError, match="E_DEADLINE"), mod.request_deadline():
        pytest.fail("request started")


def test_local_total_size_limit_before_transport(site, monkeypatch):
    mod = verifier()
    monkeypatch.setattr(mod, "MAX_TOTAL_BYTES", 1)
    with pytest.raises(mod.VerificationError, match="E_SIZE"):
        mod.verify(mod.EXPECTED_URL, site, fetch=lambda url: pytest.fail("network"))


def test_cli_refuses_url_without_echoing_input(site, capsys):
    mod = verifier()
    assert (
        mod.main(
            ["--url", "https://private-user:private-secret@example.com/", "--directory", str(site)]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "E_URL\n"


@pytest.mark.parametrize("site", [True], indirect=True)
def test_historical_build_is_verifiable_without_claiming_current_runtime(site):
    mod = verifier()
    result = mod.verify(mod.EXPECTED_URL, site, fetch=fake_fetch(mod, site, []))
    assert result["capture_status"] == "historical-runtime"


def test_incomplete_http_body_is_fixed_network_error(monkeypatch):
    from http.client import IncompleteRead

    mod = verifier()

    class Opener:
        def open(self, request, *, timeout):
            raise IncompleteRead(b"PRIVATE-REMOTE-CONTEXT")

    monkeypatch.setattr(mod, "build_opener", lambda *handlers: Opener())
    with pytest.raises(mod.VerificationError, match=r"^E_NETWORK$"):
        mod.fetch_public(mod.EXPECTED_URL)
