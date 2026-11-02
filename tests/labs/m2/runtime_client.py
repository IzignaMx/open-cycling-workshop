"""Prepared fixed-endpoint reader; local tests exercise only pure validators.

No production URL/DSN/path override, client injection, refresh, retry or stale read.
Runtime execution requires the separately approved and isolated controller.
"""

from __future__ import annotations

import errno
import json
import math
import os
import re
import socket
import sqlite3
import ssl
import stat
import time
from pathlib import Path
from uuid import UUID

import httpx

from tests.labs.m2.runtime_transport import (
    OWNER_UID,
    SOCKET_DIR,
    SOCKET_PATH,
    checked_directory,
    private_file,
)

ORIGIN = "https://ocwp-m2-api"
RESOURCE = "/api/v1/connector-catalogue/products"
CA_PATH = Path("/run/m2-public/ca.crt")
CREDENTIAL_PATH = Path("/run/m2-credential/credential")
SCOPE_PATH = Path("/run/m2-credential/scope.json")
STORE_DIR = Path("/run/m2-store")
STORE_PATH = STORE_DIR / "projection.sqlite"
MAX_PAGES = 4
MAX_BODY = 65536
_BOUNDS = {"product_id": 36, "sku": 80, "name": 200, "unit": 30}
_SCOPE_IDS = {
    "organization_id",
    "location_id",
    "dataset_incarnation",
    "installation_id",
    "machine_id",
    "run_id",
}


class RuntimeClientRefused(Exception):
    def __init__(self) -> None:
        super().__init__("Laboratory runtime client refused")


def validate_page(payload: object, offset: int) -> tuple[list[dict[str, object]], int | None]:
    try:
        if not isinstance(payload, dict) or set(payload) != {"items", "next_offset"}:
            raise RuntimeClientRefused()
        items = payload["items"]
        if not isinstance(items, list) or len(items) > 50:
            raise RuntimeClientRefused()
        seen = set()
        for item in items:
            if not isinstance(item, dict) or set(item) != {*_BOUNDS, "version"}:
                raise RuntimeClientRefused()
            if any(
                type(item[key]) is not str or not 0 < len(item[key]) <= limit
                for key, limit in _BOUNDS.items()
            ):
                raise RuntimeClientRefused()
            if str(UUID(item["product_id"])) != item["product_id"]:
                raise RuntimeClientRefused()
            if type(item["version"]) is not int or not 1 <= item["version"] <= 2**63 - 1:
                raise RuntimeClientRefused()
            if item["product_id"] in seen:
                raise RuntimeClientRefused()
            seen.add(item["product_id"])
        following = payload["next_offset"]
        if following is not None and (
            type(following) is not int
            or following != offset + 50
            or following > 200
            or len(items) != 50
        ):
            raise RuntimeClientRefused()
        return items, following
    except Exception:
        raise RuntimeClientRefused() from None


def validate_metadata(payload: object, now: float) -> tuple[dict[str, object], float]:
    try:
        if not isinstance(payload, dict) or set(payload) != {"scope", "run_deadline"}:
            raise RuntimeClientRefused()
        scope, deadline = payload["scope"], payload["run_deadline"]
        if not isinstance(scope, dict) or set(scope) != {*_SCOPE_IDS, "generation"}:
            raise RuntimeClientRefused()
        for key in _SCOPE_IDS:
            value = scope[key]
            if type(value) is not str or UUID(value).hex != value.replace("-", ""):
                raise RuntimeClientRefused()
        if type(scope["generation"]) is not int or scope["generation"] < 1:
            raise RuntimeClientRefused()
        if (
            type(deadline) not in (int, float)
            or not math.isfinite(now)
            or not math.isfinite(deadline)
        ):
            raise RuntimeClientRefused()
        if not now < deadline <= now + 900:
            raise RuntimeClientRefused()
        return scope, float(deadline)
    except Exception:
        raise RuntimeClientRefused() from None


def authorization_header(raw: bytes) -> str:
    """Closed bare-file codec; never accept an already prefixed authorization."""
    try:
        if len(raw) > 128:
            raise RuntimeClientRefused()
        credential = raw.decode("ascii")
        if not re.fullmatch(r"m2_[0-9a-f]{32}_[A-Za-z0-9_-]{43}", credential):
            raise RuntimeClientRefused()
        return "Bearer " + credential
    except Exception:
        raise RuntimeClientRefused() from None


def is_certificate_failure(error: BaseException) -> bool:
    """Only a real verification failure counts, never an arbitrary refused socket."""
    seen: set[int] = set()
    current: BaseException | None = error
    for _ in range(16):
        if current is None or id(current) in seen:
            return False
        if isinstance(current, ssl.SSLCertVerificationError):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def negative_tls_checks() -> dict[str, bool]:
    """Future runtime probes; no key generation and no arbitrary target argument."""
    result = {}
    for label, ca, origin in (
        ("wrong_hostname", CA_PATH, "https://wrong-host.invalid"),
        ("wrong_ca", None, ORIGIN),
    ):
        if ca is not None:
            private_file(ca, 16384, mode=0o444)
        # Unique run CA must not be trusted by the system roots.
        context = ssl.create_default_context(cafile=str(ca) if ca is not None else None)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        transport = httpx.HTTPTransport(
            uds=str(SOCKET_PATH),
            retries=0,
            verify=context,
            trust_env=False,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
        )
        try:
            with httpx.Client(
                transport=transport, trust_env=False, follow_redirects=False, timeout=2
            ) as client:
                client.get(origin + RESOURCE)
        except Exception as error:
            if not is_certificate_failure(error):
                raise RuntimeClientRefused() from None
            result[label] = True
        else:
            raise RuntimeClientRefused()
    return result


def validate_os_evidence(
    *,
    status: str,
    uid: int,
    memory: str,
    pids: str,
    cpu: str,
    interfaces: set[str],
    store_bytes: int,
    mountinfo: str,
    namespace: str,
) -> dict[str, object]:
    """Pure parser only; supplied strings do not qualify a real container."""
    try:
        required = {"Uid", "CapEff", "NoNewPrivs"}
        fields = {}
        for line in status.splitlines():
            key, colon, value = line.partition(":")
            if key in required:
                if not colon or key in fields:
                    raise RuntimeClientRefused()
                fields[key] = value.strip()
        if set(fields) != required or type(uid) is not int or uid <= 0:
            raise RuntimeClientRefused()
        if [int(value) for value in fields["Uid"].split()] != [uid] * 4:
            raise RuntimeClientRefused()
        if int(fields["CapEff"], 16) != 0 or fields["NoNewPrivs"] != "1":
            raise RuntimeClientRefused()
        if interfaces != {"lo"} or int(memory) != 128 * 1024 * 1024 or int(pids) != 32:
            raise RuntimeClientRefused()
        quota, period = [int(value) for value in cpu.split()]
        if quota <= 0 or period <= 0 or quota * 2 != period:
            raise RuntimeClientRefused()
        if type(store_bytes) is not int or not 0 < store_bytes <= 16 * 1024 * 1024:
            raise RuntimeClientRefused()
        mounts = []
        for line in mountinfo.splitlines():
            before, separator, after = line.partition(" - ")
            parts = before.split()
            if len(parts) > 5 and parts[4] == str(STORE_DIR):
                if not separator or not after.split() or "rw" not in parts[5].split(","):
                    raise RuntimeClientRefused()
                mounts.append(after.split()[0])
        if mounts != ["tmpfs"] or not re.fullmatch(r"net:\[[0-9]+\]", namespace):
            raise RuntimeClientRefused()
        return {"isolation_verified": True, "network_namespace": namespace}
    except Exception:
        raise RuntimeClientRefused() from None


def _public_text(path: str) -> str:
    with open(path, encoding="ascii") as handle:
        value = handle.read(65537)
    if len(value) > 65536:
        raise RuntimeClientRefused()
    return value


def isolation_checks() -> dict[str, object]:
    """Future authorized container only; preparation tests NEVER call this.

    Verify loopback-only interfaces and zero capabilities BEFORE fixed negative
    probes: TCP127.0.0.1:5432 must refuse and TCP198.51.100.1:1 (TEST-NET, not a
    provider) must report ENETUNREACH. No DNS query, arbitrary target, application
    request or credential payload. No attempt is allowed outside verified limits.
    """
    try:
        volume = os.statvfs(STORE_DIR)
        result = validate_os_evidence(
            status=_public_text("/proc/self/status"),
            uid=os.geteuid(),
            memory=_public_text("/sys/fs/cgroup/memory.max").strip(),
            pids=_public_text("/sys/fs/cgroup/pids.max").strip(),
            cpu=_public_text("/sys/fs/cgroup/cpu.max").strip(),
            interfaces={entry.name for entry in Path("/sys/class/net").iterdir()},
            store_bytes=volume.f_blocks * volume.f_frsize,
            mountinfo=_public_text("/proc/self/mountinfo"),
            namespace=os.readlink("/proc/self/ns/net"),
        )
        for forbidden in (
            "/run/m2-private",
            "/run/m2-tls",
            "/var/run/docker.sock",
            "/run/postgresql",
            "/var/run/postgresql",
        ):
            if os.path.lexists(forbidden):
                raise RuntimeClientRefused()
        for address, expected in (
            (("127.0.0.1", 5432), errno.ECONNREFUSED),
            (("198.51.100.1", 1), errno.ENETUNREACH),
        ):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.settimeout(1)
                if probe.connect_ex(address) != expected:
                    raise RuntimeClientRefused()
        return result
    except Exception:
        raise RuntimeClientRefused() from None


def run() -> dict[str, object]:
    """Future runtime entrypoint. No call from preparation/unit tests.

    Every run owns one fresh file, removes it on either outcome, and returns counts
    only. The controller additionally verifies tmpfs16MiB and no-network mounts.
    """
    store = None
    owned_file = False
    cleanup_ok = True
    succeeded = False
    count = 0
    credential = ""
    try:
        checked_directory(SOCKET_DIR, 0o700, {"catalogue.sock"})
        socket_info = SOCKET_PATH.lstat()
        if (
            not stat.S_ISSOCK(socket_info.st_mode)
            or socket_info.st_uid != OWNER_UID
            or stat.S_IMODE(socket_info.st_mode) != 0o600
        ):
            raise RuntimeClientRefused()
        checked_directory(
            CREDENTIAL_PATH.parent, 0o700, {"credential", "scope.json", "api-status.json"}
        )
        checked_directory(CA_PATH.parent, 0o700, {"ca.crt"})
        checked_directory(STORE_DIR, 0o700, set())
        isolation = isolation_checks()
        now = time.clock_gettime(time.CLOCK_BOOTTIME)
        scope, deadline = validate_metadata(json.loads(private_file(SCOPE_PATH, 4096)), now)
        previous = now

        def check_time() -> float:
            nonlocal previous
            current = time.clock_gettime(time.CLOCK_BOOTTIME)
            if not math.isfinite(current) or current < previous or current >= deadline:
                raise RuntimeClientRefused()
            previous = current
            return current

        tls_checks = negative_tls_checks()
        check_time()
        credential = authorization_header(private_file(CREDENTIAL_PATH, 128))
        if credential.removeprefix("Bearer ").split("_")[1] != scope["machine_id"]:
            raise RuntimeClientRefused()
        # Validate source before SSL loads the fixed pathname; directory is owned
        # and connector-mounted read-only. No verify=False or alternate host path.
        private_file(CA_PATH, 16384, mode=0o444)
        context = ssl.create_default_context(cafile=str(CA_PATH))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        fd = os.open(STORE_PATH, os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_WRONLY, 0o600)
        os.close(fd)
        owned_file = True
        store = sqlite3.connect(STORE_PATH)
        store.execute("PRAGMA page_size=4096")
        store.execute("PRAGMA max_page_count=4096")
        store.execute("PRAGMA journal_mode=MEMORY")
        store.execute("PRAGMA temp_store=MEMORY")
        store.execute(
            "CREATE TABLE projection (binding TEXT, product_id TEXT PRIMARY KEY, "
            "sku TEXT, name TEXT, unit TEXT, version INTEGER)"
        )
        transport = httpx.HTTPTransport(
            uds=str(SOCKET_PATH),
            retries=0,
            verify=context,
            trust_env=False,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
        )
        with httpx.Client(
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(2),
            limits=httpx.Limits(max_connections=1),
        ) as client:
            offset = 0
            for _page in range(MAX_PAGES):
                check_time()
                request_end = min(check_time() + 8, deadline)
                with client.stream(
                    "GET",
                    ORIGIN + RESOURCE,
                    params={"limit": 50, "offset": offset},
                    headers={"Authorization": credential},
                ) as response:
                    if response.status_code != 200 or response.headers.get("content-encoding"):
                        raise RuntimeClientRefused()
                    data = bytearray()
                    # Do not buffer to a requested chunk size: check the absolute
                    # deadline after every transport-delivered fragment.
                    for chunk in response.iter_raw():
                        if check_time() >= request_end or len(data) + len(chunk) > MAX_BODY:
                            raise RuntimeClientRefused()
                        data.extend(chunk)
                    if check_time() >= request_end:
                        raise RuntimeClientRefused()
                items, following = validate_page(json.loads(data), offset)
                with store:
                    store.executemany(
                        "INSERT INTO projection VALUES (?, ?, ?, ?, ?, ?)",
                        [
                            (
                                json.dumps(scope, sort_keys=True),
                                item["product_id"],
                                item["sku"],
                                item["name"],
                                item["unit"],
                                item["version"],
                            )
                            for item in items
                        ],
                    )
                count += len(items)
                if following is None:
                    check_time()
                    succeeded = True
                    break
                offset = following
            if not succeeded:
                raise RuntimeClientRefused()
    except Exception:
        succeeded = False
    finally:
        credential = ""
        if store is not None:
            try:
                store.execute("DELETE FROM projection")
                store.commit()
                if store.execute("SELECT count(*) FROM projection").fetchone()[0] != 0:
                    cleanup_ok = False
            except Exception:
                cleanup_ok = False
            try:
                store.close()
            except Exception:
                cleanup_ok = False
        if owned_file:
            try:
                STORE_PATH.unlink()
                if STORE_PATH.exists():
                    cleanup_ok = False
            except Exception:
                cleanup_ok = False
    if not succeeded or not cleanup_ok:
        raise RuntimeClientRefused() from None
    return {
        "status": "ok",
        "item_count": count,
        "projection_disposed": True,
        "tls_negative": tls_checks,
        **isolation,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(run(), sort_keys=True))
    except RuntimeClientRefused:
        print('{"status":"refused"}')
        raise SystemExit(2) from None
