"""One-shot in-process functional surrogate, never an external connector runtime."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from threading import Lock

from starlette.testclient import TestClient

from tests.labs.m2.authority import Credential, MachineScope

_PATH = "/api/v1/connector-catalogue/products"
_FIELDS = {"product_id", "sku", "name", "unit", "version"}
_TEXT_BOUNDS = {"product_id": 36, "sku": 80, "name": 200, "unit": 30}


class ConnectorStopped(Exception):
    def __init__(self) -> None:
        super().__init__("Laboratory connector stopped")


class LabConnector:
    """Explicit test client and trusted fixture scope only; no URL/configuration input.

    Scope is supplied by the fixture harness after authority.read, not inferred
    from catalogue DTOs. This is not a remote scope-attestation protocol.
    """

    def __init__(self, client: TestClient, credential: Credential, scope: MachineScope):
        if (
            type(client) is not TestClient
            or type(credential) is not Credential
            or type(scope) is not MachineScope
            or scope.machine_id != credential.credential_id
        ):
            raise ConnectorStopped()
        self._client = client
        self._credential: Credential | None = credential
        self.binding = scope
        self._lock = Lock()
        self._used = False
        self.closed = False
        self.cleanup_failed = False
        self.disposal_verified = False
        self._store = sqlite3.connect(":memory:", check_same_thread=False)
        self._store.execute(
            "CREATE TABLE projection (binding TEXT, product_id TEXT PRIMARY KEY, "
            "sku TEXT, name TEXT, unit TEXT, version INTEGER)"
        )

    @property
    def row_count(self) -> int:
        if self.cleanup_failed:
            raise ConnectorStopped()
        if self.closed:
            return 0
        count = self._store.execute("SELECT count(*) FROM projection").fetchone()[0]
        if type(count) is not int or count < 0:
            raise ConnectorStopped()
        return count

    def close(self) -> None:
        if self.closed:
            if self.cleanup_failed:
                raise ConnectorStopped()
            return
        self._credential = None
        try:
            self._store.execute("DELETE FROM projection")
            self._store.commit()
            if self._store.execute("SELECT count(*) FROM projection").fetchone()[0] != 0:
                raise ConnectorStopped()
        except Exception:
            self.cleanup_failed = True
        finally:
            try:
                self._store.close()
            except Exception:
                self.cleanup_failed = True
            # Closed means retired from use, not necessarily successfully disposed.
            self.closed = True
        self.disposal_verified = not self.cleanup_failed
        if self.cleanup_failed:
            raise ConnectorStopped() from None

    def fetch(self) -> list[dict[str, object]]:
        if not self._lock.acquire(blocking=False):
            # Refuse a second in-flight request without touching the active SQLite
            # transaction. The active owner observes the stop flag before returning.
            self._used = True
            self._credential = None
            raise ConnectorStopped()
        try:
            if self.closed or self._used or self._credential is None:
                raise ConnectorStopped()
            self._used = True
            credential = self._credential
            offset = 0
            rows: list[dict[str, object]] = []
            seen: set[str] = set()
            for _page in range(4):
                response = self._client.get(
                    _PATH,
                    params={"limit": 50, "offset": offset},
                    headers={"Authorization": credential.authorization()},
                    follow_redirects=False,
                )
                if response.status_code != 200 or len(response.content) > 65536:
                    raise ConnectorStopped()
                payload = response.json()
                if not isinstance(payload, dict) or set(payload) != {"items", "next_offset"}:
                    raise ConnectorStopped()
                items = payload["items"]
                if not isinstance(items, list) or len(items) > 50:
                    raise ConnectorStopped()
                for item in items:
                    if not isinstance(item, dict) or set(item) != _FIELDS:
                        raise ConnectorStopped()
                    if any(
                        type(item[key]) is not str or not 0 < len(item[key]) <= limit
                        for key, limit in _TEXT_BOUNDS.items()
                    ):
                        raise ConnectorStopped()
                    if type(item["version"]) is not int or not 1 <= item["version"] <= 2**63 - 1:
                        raise ConnectorStopped()
                    if item["product_id"] in seen:
                        raise ConnectorStopped()
                    seen.add(item["product_id"])
                with self._store:
                    self._store.executemany(
                        "INSERT INTO projection VALUES (?, ?, ?, ?, ?, ?)",
                        [
                            (
                                json.dumps(asdict(self.binding), sort_keys=True),
                                item["product_id"],
                                item["sku"],
                                item["name"],
                                item["unit"],
                                item["version"],
                            )
                            for item in items
                        ],
                    )
                rows.extend(items)
                following = payload["next_offset"]
                if following is None:
                    if self._credential is None:
                        raise ConnectorStopped()
                    self._credential = None
                    return rows
                if (
                    type(following) is not int
                    or following != offset + 50
                    or following > 200
                    or len(items) != 50
                ):
                    raise ConnectorStopped()
                offset = following
            raise ConnectorStopped()
        except Exception:
            self.close()
            raise ConnectorStopped() from None
        finally:
            self._lock.release()
