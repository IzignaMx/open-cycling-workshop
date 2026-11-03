"""Prepared fixed TLS/UDS adapter. Unit tests do not execute its runtime entrypoint."""

from __future__ import annotations

import asyncio
import math
import os
import re
import socket
import ssl
import stat
import threading
import time
from collections.abc import Callable
from pathlib import Path

from starlette.types import ASGIApp, Message, Scope

SOCKET_DIR = Path("/run/m2-api")
SOCKET_PATH = SOCKET_DIR / "catalogue.sock"
CERT_PATH = Path("/run/m2-tls/api.crt")
KEY_PATH = Path("/run/m2-tls/api.key")
OWNER_UID = os.geteuid()
PATH = "/api/v1/connector-catalogue/products"


class TransportRefused(Exception):
    def __init__(self) -> None:
        super().__init__("Laboratory transport refused")


def parse_request(raw: bytes) -> Scope:
    """One bounded GET; reject already-buffered pipeline/body bytes.

    Later bytes are never processed/reused (Connection:close), not claimed
    detectable before they arrive. This is not a general HTTP implementation.
    """
    try:
        if len(raw) > 8192 or not raw.endswith(b"\r\n\r\n") or raw.count(b"\r\n\r\n") != 1:
            raise TransportRefused()
        lines = raw[:-4].split(b"\r\n")
        method, target, protocol = lines[0].split(b" ")
        path, _, query = target.partition(b"?")
        if (
            method != b"GET"
            or protocol != b"HTTP/1.1"
            or path != PATH.encode()
            or len(query) > 1024
        ):
            raise TransportRefused()
        if not re.fullmatch(rb"[A-Za-z0-9=&%]*", query):
            raise TransportRefused()
        headers = []
        seen = set()
        for line in lines[1:]:
            name, colon, value = line.partition(b":")
            name = name.lower()
            value = value.strip(b" ")
            if not colon or not re.fullmatch(rb"[a-z0-9-]+", name) or name in seen:
                raise TransportRefused()
            if any(byte < 32 or byte > 126 for byte in value):
                raise TransportRefused()
            if name in (b"transfer-encoding", b"expect", b"upgrade"):
                raise TransportRefused()
            if name == b"content-length" and value != b"0":
                raise TransportRefused()
            seen.add(name)
            headers.append((name, value))
        if dict(headers).get(b"host") != b"ocwp-m2-api":
            raise TransportRefused()
        return {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": PATH,
            "raw_path": path,
            "root_path": "",
            "query_string": query,
            "headers": headers,
            "server": ("ocwp-m2-api", 443),
            "client": None,
        }
    except Exception:
        raise TransportRefused() from None


async def invoke(app: ASGIApp, scope: Scope, timeout: float) -> bytes:
    body = bytearray()
    status = None
    completed = False

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        nonlocal status, completed
        if completed:
            raise TransportRefused()
        if message["type"] == "http.response.start" and status is None:
            status = message["status"]
            if type(status) is not int or status not in (
                200,
                401,
                403,
                405,
                408,
                413,
                422,
                429,
                503,
            ):
                raise TransportRefused()
        elif message["type"] == "http.response.body" and status is not None:
            part = message.get("body", b"")
            if len(body) + len(part) > 65536:
                raise TransportRefused()
            body.extend(part)
            completed = not message.get("more_body", False)
        else:
            raise TransportRefused()

    try:
        if not math.isfinite(timeout) or timeout <= 0 or timeout > 8:
            raise TransportRefused()
        await asyncio.wait_for(app(scope, receive, send), timeout)
        if not completed or status is None:
            raise TransportRefused()
        return (
            f"HTTP/1.1 {status} Response\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n"
            "Cache-Control: private, no-store\r\n\r\n"
        ).encode() + body
    except Exception:
        raise TransportRefused() from None


def checked_directory(path: Path, mode: int, names: set[str]) -> None:
    """Fixed caller paths only. Refuse symlinks in every parent component."""
    if OWNER_UID <= 0:
        raise TransportRefused()
    for component in [path, *path.parents]:
        if component.is_symlink():
            raise TransportRefused()
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != OWNER_UID
        or stat.S_IMODE(info.st_mode) != mode
    ):
        raise TransportRefused()
    if {entry.name for entry in path.iterdir()} != names:
        raise TransportRefused()


def private_file(path: Path, maximum: int, *, mode: int = 0o400) -> bytes:
    """No-follow, regular single-link owner-only bounded input; never print bytes."""
    try:
        if OWNER_UID <= 0:
            raise TransportRefused()
        for component in path.parents:
            if component.is_symlink():
                raise TransportRefused()
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != OWNER_UID
                or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != mode
                or not 0 < info.st_size <= maximum
            ):
                raise TransportRefused()
            data = os.read(fd, maximum + 1)
            if len(data) != info.st_size or len(data) > maximum:
                raise TransportRefused()
            return data
        finally:
            os.close(fd)
    except Exception:
        raise TransportRefused() from None


def accepting(stop_event: threading.Event | None, stopped: threading.Event, accepted: int) -> bool:
    return (
        not stopped.is_set() and (stop_event is None or not stop_event.is_set()) and accepted < 120
    )


def join_handlers(handlers: list[threading.Thread]) -> None:
    """Bounded observation, not a claim that an uncancelled ASGI worker ceased."""
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 2
    for worker in handlers:
        worker.join(timeout=max(0, deadline - time.clock_gettime(time.CLOCK_BOOTTIME)))
    if any(worker.is_alive() for worker in handlers):
        raise TransportRefused()


def announce_ready(on_ready: Callable[[], None] | None) -> None:
    if on_ready is not None:
        on_ready()


def serve(
    app: ASGIApp,
    *,
    run_deadline: float,
    stop_event: threading.Event | None = None,
    on_ready: Callable[[], None] | None = None,
) -> None:
    """Future authorized runtime only. Never called by local preparation tests.

    A timed-out ASGI call stops all admission; Python cannot kill a worker thread.
    Database deadlines and the external bounded controller must reap that process.
    """
    stopped = threading.Event()
    unsafe = threading.Event()
    handlers: list[threading.Thread] = []
    slots = threading.BoundedSemaphore(2)
    clock_lock = threading.Lock()
    previous = time.clock_gettime(time.CLOCK_BOOTTIME)
    if not math.isfinite(run_deadline) or not previous < run_deadline <= previous + 900:
        raise TransportRefused()

    def now() -> float:
        nonlocal previous
        with clock_lock:
            value = time.clock_gettime(time.CLOCK_BOOTTIME)
            if not math.isfinite(value) or value < previous or value >= run_deadline:
                unsafe.set()
                stopped.set()
                raise TransportRefused()
            previous = value
            return value

    checked_directory(SOCKET_DIR, 0o700, set())
    checked_directory(KEY_PATH.parent, 0o700, {"api.crt", "api.key"})
    private_file(KEY_PATH, 16384)
    private_file(CERT_PATH, 16384)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(CERT_PATH, KEY_PATH)

    def handle(connection: socket.socket) -> None:
        tls = None
        invoking = False
        try:
            total_end = min(now() + 8, run_deadline)
            connection.settimeout(min(2, total_end - now()))
            tls = context.wrap_socket(connection, server_side=True)
            header_end = min(now() + 2, total_end)
            data = bytearray()
            while b"\r\n\r\n" not in data:
                tls.settimeout(max(0.001, header_end - now()))
                if now() >= header_end or len(data) >= 8192:
                    raise TransportRefused()
                part = tls.recv(min(1024, 8193 - len(data)))
                if not part:
                    raise TransportRefused()
                data.extend(part)
            scope = parse_request(bytes(data))
            invoking = True
            response = asyncio.run(invoke(app, scope, total_end - now()))
            invoking = False
            tls.settimeout(max(0.001, min(2, total_end - now())))
            if now() >= total_end:
                raise TransportRefused()
            tls.sendall(response)
        except Exception:
            # TLS/parser rejection consumes one bounded attempt, not the run.
            # ASGI failure can leave uncancelled database work: stop admission.
            if invoking:
                unsafe.set()
                stopped.set()
        finally:
            try:
                if tls is not None:
                    tls.close()
                connection.close()
            except Exception:
                unsafe.set()
                stopped.set()
            finally:
                slots.release()

    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        listener.bind(str(SOCKET_PATH))
        os.chmod(SOCKET_PATH, 0o600)
        checked_directory(SOCKET_DIR, 0o700, {"catalogue.sock"})
        info = SOCKET_PATH.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != OWNER_UID:
            raise TransportRefused()
        listener.listen(8)
        listener.settimeout(0.25)
        announce_ready(on_ready)
        accepted = 0
        while accepting(stop_event, stopped, accepted):
            now()
            try:
                connection, _ = listener.accept()
            except TimeoutError:
                continue
            accepted += 1
            if not slots.acquire(blocking=False):
                connection.close()
                continue
            worker = threading.Thread(target=handle, args=(connection,), daemon=True)
            handlers.append(worker)
            worker.start()
    except Exception:
        raise TransportRefused() from None
    finally:
        stopped.set()
        try:
            listener.close()
            join_handlers(handlers)
        except Exception:
            unsafe.set()
        # Even terminated handlers do not prove cancelled AnyIO/database work.
        if unsafe.is_set():
            raise TransportRefused() from None
        # Controller independently verifies/removes the owned socket and workers.
