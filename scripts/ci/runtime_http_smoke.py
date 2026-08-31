#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
PLATFORM = ROOT / "services/platform"
SOURCE = PLATFORM / "src"
ORG_ID = "00000000-0000-7000-8000-000000000001"
LOCATION_ID = "00000000-0000-7000-8000-000000000002"
USER_ID = "00000000-0000-7000-8000-000000000099"
CUSTOMER_ID = "018f0000-0000-7000-8000-000000000111"
MUTATION_ID = "018f0000-0000-7000-8000-000000000112"
AUTH_SECRET = "runtime-smoke-secret-runtime-smoke-secret-000000000000"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request_json(
    url: str, *, token: str | None = None, payload: dict[str, object] | None = None
) -> tuple[dict[str, object], dict[str, str]]:
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=body, method="POST" if body is not None else "GET")
    request.add_header("Accept", "application/json")
    if body is not None:
        request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urlopen(request, timeout=3) as response:
        return json.loads(response.read()), {
            key.lower(): value for key, value in response.headers.items()
        }


def main() -> int:
    os.environ.setdefault("PYTHONPATH", str(SOURCE))
    sys.path.insert(0, str(SOURCE))

    from cycling_workshop.identity.models import UserRecord
    from cycling_workshop.identity.security import PasswordService
    from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord

    # ignore_cleanup_errors: on Windows the terminated uvicorn child can hold
    # the sqlite file for a few milliseconds after process.wait(), which would
    # fail TemporaryDirectory cleanup and mask a successful smoke run.
    with tempfile.TemporaryDirectory(
        prefix="ocwp-runtime-", ignore_cleanup_errors=True
    ) as directory:
        database_path = Path(directory) / "runtime.sqlite3"
        database_url = f"sqlite+pysqlite:///{database_path}"
        env = dict(os.environ)
        env.update(
            {
                "PYTHONPATH": str(SOURCE),
                "OCWP_DATABASE_URL": database_url,
                "OCWP_AUTH_SECRET": AUTH_SECRET,
            }
        )
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=PLATFORM,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

        engine = create_engine(database_url)
        with Session(engine) as session:
            session.add(OrganizationRecord(id=ORG_ID, name="Runtime Smoke Workshop"))
            session.add(LocationRecord(id=LOCATION_ID, organization_id=ORG_ID, name="Main"))
            session.add(
                UserRecord(
                    id=USER_ID,
                    organization_id=ORG_ID,
                    location_id=LOCATION_ID,
                    username="runtime-admin",
                    display_name="Runtime Admin",
                    password_hash=PasswordService().hash("runtime smoke password"),
                    capabilities=["customers.read", "customers.write", "sync.push", "sync.pull"],
                    is_active=True,
                    session_version=1,
                )
            )
            session.commit()
        engine.dispose()

        port = free_port()
        base_url = f"http://127.0.0.1:{port}"
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "cycling_workshop.runtime:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            deadline = time.monotonic() + 8
            while True:
                if process.poll() is not None:
                    output = process.stdout.read() if process.stdout else ""
                    raise RuntimeError(f"uvicorn exited before readiness:\n{output}")
                try:
                    health, headers = request_json(f"{base_url}/health/live")
                    readiness, _ = request_json(f"{base_url}/health/ready")
                    break
                except URLError as exc:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("uvicorn did not become ready before timeout") from exc
                    time.sleep(0.1)

            login, _ = request_json(
                f"{base_url}/api/v1/auth/login",
                payload={
                    "organization_id": ORG_ID,
                    "username": "runtime-admin",
                    "password": "runtime smoke password",
                },
            )
            token = str(login["access_token"])
            me, _ = request_json(f"{base_url}/api/v1/auth/me", token=token)

            push, _ = request_json(
                f"{base_url}/api/v1/sync/mutations",
                token=token,
                payload={
                    "mutations": [
                        {
                            "mutation_id": MUTATION_ID,
                            "entity_type": "customer",
                            "entity_id": CUSTOMER_ID,
                            "operation": "create",
                            "organization_id": ORG_ID,
                            "location_id": LOCATION_ID,
                            "base_version": None,
                            "occurred_at": "2026-08-07T07:30:00Z",
                            "payload": {
                                "display_name": "Cliente Runtime",
                                "email": "runtime@example.com",
                                "phone": None,
                            },
                        }
                    ]
                },
            )
            pull, _ = request_json(
                f"{base_url}/api/v1/sync/changes?cursor=0&location_id={LOCATION_ID}",
                token=token,
            )
            customer, _ = request_json(f"{base_url}/api/v1/customers/{CUSTOMER_ID}", token=token)

            assert health == {"status": "ok"}
            assert readiness["status"] == "ready"
            assert "x-request-id" in headers
            assert me["user_id"] == USER_ID
            assert me["display_name"] == "Runtime Admin"
            assert push["results"][0]["status"] == "applied"  # type: ignore[index]
            assert pull["items"][0]["entity_id"] == CUSTOMER_ID  # type: ignore[index]
            assert customer["display_name"] == "Cliente Runtime"
            print(
                json.dumps(
                    {
                        "health": health,
                        "readiness": readiness,
                        "request_id_present": True,
                        "login_user": me["user_id"],
                        "push_status": "applied",
                        "pulled_customer": CUSTOMER_ID,
                        "customer_name": customer["display_name"],
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
