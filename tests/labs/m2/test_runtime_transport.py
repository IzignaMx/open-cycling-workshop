"""Pure transport contracts only: no socket, TLS key, listener or network execution."""

import asyncio
import importlib

import pytest


def subject():
    return importlib.import_module("tests.labs.m2.runtime_transport")


def request(extra=b"", target=b"/api/v1/connector-catalogue/products?limit=50&offset=0"):
    return b"GET " + target + b" HTTP/1.1\r\nHost: ocwp-m2-api\r\n" + extra + b"\r\n"


def test_closed_get_parser():
    parsed = subject().parse_request(request())
    assert parsed["path"] == "/api/v1/connector-catalogue/products"
    assert parsed["query_string"] == b"limit=50&offset=0"


@pytest.mark.parametrize(
    "raw",
    [
        request(target=b"https://elsewhere.invalid/"),
        request(target=b"/other"),
        request(b"Transfer-Encoding: chunked\r\n"),
        request(b"Content-Length: 1\r\n") + b"x",
        request() + request(),
        request(b"X-Padding: " + b"x" * 8192 + b"\r\n"),
        request(target=b"/api/v1/connector-catalogue/products?" + b"x" * 1025),
        request(b"Host: ocwp-m2-api\r\n"),
        request().replace(b"GET", b"POST", 1),
        request().replace(b"\r\n", b"\n"),
    ],
)
def test_invalid_requests_fail_closed(raw):
    with pytest.raises(subject().TransportRefused):
        subject().parse_request(raw)


def test_asgi_response_is_materialized_before_return():
    async def app(scope, receive, send):
        assert (await receive())["body"] == b""
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    result = asyncio.run(subject().invoke(app, subject().parse_request(request()), 1))
    assert result.endswith(b"\r\n\r\n{}")
    assert b"Connection: close" in result
    assert b"Cache-Control: private, no-store" in result


def test_partial_response_then_failure_releases_no_body():
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"private-canary", "more_body": True})
        raise RuntimeError("private-canary")

    with pytest.raises(subject().TransportRefused) as error:
        asyncio.run(subject().invoke(app, subject().parse_request(request()), 1))
    assert str(error.value) == "Laboratory transport refused"


def test_oversized_response_refused():
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"x" * 65537})

    with pytest.raises(subject().TransportRefused):
        asyncio.run(subject().invoke(app, subject().parse_request(request()), 1))


def test_asgi_timeout_releases_no_buffered_response():
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"private-canary"})
        await asyncio.sleep(1)

    with pytest.raises(subject().TransportRefused):
        asyncio.run(subject().invoke(app, subject().parse_request(request()), 0.001))


@pytest.mark.parametrize(
    "header",
    [
        b"Authorization: one\r\nAuthorization: two\r\n",
        b"Content-Length: 0\r\nContent-Length: 0\r\n",
        b"Upgrade: websocket\r\n",
        b"Expect: 100-continue\r\n",
    ],
)
def test_ambiguous_authority_and_upgrade_headers_are_refused(header):
    with pytest.raises(subject().TransportRefused):
        subject().parse_request(request(header))


@pytest.mark.parametrize(
    "change",
    [
        {"st_mode": 0o100644},
        {"st_uid": 20002},
        {"st_nlink": 2},
        {"st_size": 129},
        {"st_mode": 0o120400},
    ],
)
def test_private_reader_rejects_unsafe_metadata_without_real_files(monkeypatch, change):
    from pathlib import Path
    from types import SimpleNamespace

    module = subject()
    fields = {"st_mode": 0o100400, "st_uid": 10001, "st_nlink": 1, "st_size": 10}
    fields.update(change)
    monkeypatch.setattr(module, "OWNER_UID", 10001)
    monkeypatch.setattr(Path, "is_symlink", lambda self: False)
    monkeypatch.setattr(module.os, "open", lambda *args: 9)
    monkeypatch.setattr(module.os, "fstat", lambda fd: SimpleNamespace(**fields))
    closed = []
    monkeypatch.setattr(module.os, "close", lambda fd: closed.append(fd))
    with pytest.raises(module.TransportRefused):
        module.private_file(Path("/synthetic/metadata-only"), 128)
    assert closed == [9]


def test_private_reader_uses_nofollow_bounded_read_no_real_file(monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace

    module = subject()
    monkeypatch.setattr(module, "OWNER_UID", 10001)
    monkeypatch.setattr(Path, "is_symlink", lambda self: False)
    opened = []
    monkeypatch.setattr(module.os, "open", lambda path, flags: opened.append(flags) or 9)
    monkeypatch.setattr(
        module.os,
        "fstat",
        lambda fd: SimpleNamespace(st_mode=0o100400, st_uid=10001, st_nlink=1, st_size=10),
    )
    monkeypatch.setattr(module.os, "read", lambda fd, limit: b"publictext")
    monkeypatch.setattr(module.os, "close", lambda fd: None)
    assert module.private_file(Path("/synthetic/metadata-only"), 128) == b"publictext"
    assert opened[0] & module.os.O_NOFOLLOW
    assert opened[0] & module.os.O_NONBLOCK


def test_socket_directory_refuses_extra_entry_without_creating_socket(monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace

    module = subject()
    monkeypatch.setattr(module, "OWNER_UID", 10001)
    monkeypatch.setattr(Path, "is_symlink", lambda self: False)
    monkeypatch.setattr(Path, "lstat", lambda self: SimpleNamespace(st_mode=0o40700, st_uid=10001))
    monkeypatch.setattr(Path, "iterdir", lambda self: iter([Path("catalogue.sock"), Path("extra")]))
    with pytest.raises(module.TransportRefused):
        module.checked_directory(Path("/synthetic/metadata-only"), 0o700, {"catalogue.sock"})


def test_actual_closed_asgi_composition_without_listener():
    import json

    from tests.labs.m2.application import create_lab_app
    from tests.labs.m2.authority import LabAuthority

    authority = LabAuthority()
    try:
        credential = authority.issue()
        scope = subject().parse_request(request())
        scope["headers"].append((b"authorization", credential.authorization().encode("ascii")))
        response = asyncio.run(subject().invoke(create_lab_app(authority), scope, 1))
        payload = json.loads(response.split(b"\r\n\r\n", 1)[1])
        assert len(payload["items"]) == 3
        assert all(
            set(row) == {"product_id", "sku", "name", "unit", "version"} for row in payload["items"]
        )
    finally:
        authority.close()


def test_cooperative_stop_closes_admission_without_a_listener():
    import threading

    module = subject()
    stop, unsafe = threading.Event(), threading.Event()
    assert module.accepting(stop, unsafe, 0)
    stop.set()
    assert not module.accepting(stop, unsafe, 0)
    assert not module.accepting(None, unsafe, 120)
    unsafe.set()
    assert not module.accepting(None, unsafe, 0)


def test_join_return_does_not_attest_worker_termination():
    class Unreaped:
        def join(self, timeout):
            pass

        def is_alive(self):
            return True

    with pytest.raises(subject().TransportRefused):
        subject().join_handlers([Unreaped()])


def test_joined_worker_must_be_observed_stopped():
    class Finished:
        def join(self, timeout):
            pass

        def is_alive(self):
            return False

    subject().join_handlers([Finished()])


def test_symlink_parent_refused_before_open(monkeypatch):
    from pathlib import Path

    module = subject()
    monkeypatch.setattr(module, "OWNER_UID", 10001)
    monkeypatch.setattr(Path, "is_symlink", lambda self: True)
    opened = []
    monkeypatch.setattr(module.os, "open", lambda *args: opened.append(1))
    with pytest.raises(module.TransportRefused):
        module.private_file(Path("/synthetic/metadata-only"), 128)
    assert opened == []


def test_tls_directory_is_separate_from_database_secrets():
    module = subject()
    assert str(module.CERT_PATH) == "/run/m2-tls/api.crt"
    assert str(module.KEY_PATH) == "/run/m2-tls/api.key"


def test_ready_callback_contract_without_listener_execution():
    import inspect

    module = subject()
    calls = []
    module.announce_ready(lambda: calls.append(1))
    assert calls == [1]
    module.announce_ready(None)
    source = inspect.getsource(module.serve)
    assert source.index("listener.listen(8)") < source.index("announce_ready(on_ready)")
    assert source.index("announce_ready(on_ready)") < source.index("while accepting(")
