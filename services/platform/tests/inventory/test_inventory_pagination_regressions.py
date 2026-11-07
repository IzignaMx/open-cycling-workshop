"""Combined HTTP pagination regressions; SQLite evidence, not snapshot/PG proof."""

from __future__ import annotations

import base64
import json
import random
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cycling_workshop.db.base import Base
from cycling_workshop.inventory.models import InventoryMovementRecord
from fastapi.testclient import TestClient
from sqlalchemy import select

from services.platform.tests.inventory.test_inventory_api import (
    FOREIGN_PRODUCT,
    OTHER_LOCATION_PRODUCT,
    PRODUCT,
    PRODUCTS,
    SECOND_PRODUCT,
    InventoryAPI,
)
from services.platform.tests.inventory.test_inventory_api import (
    inventory_api as inventory_api_fixture,
)

HISTORY = f"{PRODUCTS}/{PRODUCT}/movements"


@pytest.fixture
def pagination_api() -> Iterator[InventoryAPI]:
    yield from inventory_api_fixture.__wrapped__()


def _row(identifier: str, timestamp: datetime, quantity: int = 1) -> dict[str, Any]:
    return {
        "movement_id": identifier,
        "product_id": PRODUCT,
        "organization_id": "org-1",
        "location_id": "loc-1",
        "kind": "ADJUST",
        "quantity": quantity,
        "occurred_at": timestamp.isoformat(timespec="microseconds").replace("+00:00", "Z"),
    }


def _seed(api: InventoryAPI, rows: list[dict[str, Any]]) -> None:
    with api.factory() as session:
        for row in rows:
            session.add(
                InventoryMovementRecord(
                    **{**row, "occurred_at": datetime.fromisoformat(row["occurred_at"])},
                    actor_id="private-actor",
                    order_id="private-order",
                    note="private-note",
                )
            )
        session.commit()


def _snapshot(api: InventoryAPI) -> dict[str, list[str]]:
    # Compare every column in every table, including otherwise invisible read effects.
    with api.engine.connect() as connection:
        return {
            table.name: sorted(repr(tuple(row)) for row in connection.execute(select(table)))
            for table in Base.metadata.sorted_tables
        }


def _key(row: dict[str, Any]) -> tuple[str, str]:
    # Independent oracle: canonical timestamps and Python Unicode scalar ordering.
    return row["occurred_at"], row["movement_id"]


def _page(
    client: TestClient,
    expected: list[dict[str, Any]],
    limit: int,
    before: str | None,
) -> str | None:
    params = {"limit": str(limit)}
    if before is not None:
        params["before"] = before
    response = client.get(HISTORY, params=params)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    page = response.json()
    assert set(page) == {"items", "next_cursor"}
    assert page["items"] == expected[:limit]
    cursor = page["next_cursor"]
    if len(expected) <= limit:
        assert cursor is None
    else:
        assert isinstance(cursor, str)
        decoded = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        last = expected[limit - 1]
        assert decoded == {
            "before_movement_id": last["movement_id"],
            "before_occurred_at": last["occurred_at"],
            "location_id": "loc-1",
            "organization_id": "org-1",
            "product_id": PRODUCT,
            "version": 1,
        }
    return cursor


@pytest.mark.parametrize(
    ("seed", "limits"),
    [(17, (1, 4, 2, 7)), (83, (7, 2, 5, 1)), (211, (3, 1, 8, 2))],
)
def test_seeded_unicode_extrema_traversal_is_scoped_and_read_only(
    pagination_api: InventoryAPI, seed: int, limits: tuple[int, ...]
) -> None:
    now = datetime(2026, 10, 15, tzinfo=UTC)
    times = [
        datetime(1, 1, 1, tzinfo=UTC),
        now,
        now + timedelta(microseconds=1),
        datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
    ]
    identifiers = ["a", "a\u0301", "é", "漢", "\ue000", "\U00010000", "🚲"]
    rows = [
        _row(f"{identifier}-{index}", timestamp, index * 7 + position - 9)
        for index, timestamp in enumerate(times)
        for position, identifier in enumerate(identifiers)
    ]
    expected = sorted(rows, key=_key, reverse=True)
    scopes = [
        (SECOND_PRODUCT, "org-1", "loc-1"),
        (OTHER_LOCATION_PRODUCT, "org-1", "loc-2"),
        (FOREIGN_PRODUCT, "org-2", "loc-x"),
        # Legacy schema admits a same-product ledger row in another location.
        (PRODUCT, "org-1", "loc-2"),
    ]
    distractors = [
        {
            **_row(f"漢-{index}-hidden-{scope}", timestamp, 10000),
            "product_id": product,
            "organization_id": organization,
            "location_id": location,
        }
        for index, timestamp in enumerate(times)
        for scope, (product, organization, location) in enumerate(scopes)
    ]
    shuffled = rows + distractors
    random.Random(seed).shuffle(shuffled)
    _seed(pagination_api, shuffled)
    client = pagination_api.client(capabilities=["inventory.read"])
    before_tables = _snapshot(pagination_api)
    cursor = None
    offset = 0
    # Finite bound: even a stuck/repeating cursor must fail, never hang CI.
    for index in range(len(expected) + 1):
        limit = limits[index % len(limits)]
        cursor = _page(client, expected[offset:], limit, cursor)
        offset += min(limit, len(expected) - offset)
        if cursor is None:
            break
    assert offset == len(expected)
    assert cursor is None
    assert _snapshot(pagination_api) == before_tables


def test_live_unicode_boundary_inserts_obey_tuple_order_without_snapshot_promise(
    pagination_api: InventoryAPI,
) -> None:
    now = datetime(2026, 10, 15, tzinfo=UTC)
    rows = [_row(identifier, now) for identifier in ["🚲", "\U00010000", "a\u0301", "a"]]
    _seed(pagination_api, rows)
    client = pagination_api.client(capabilities=["inventory.read"])
    expected = sorted(rows, key=_key, reverse=True)
    before_tables = _snapshot(pagination_api)
    cursor = _page(client, expected, 2, None)
    assert cursor is not None
    assert _snapshot(pagination_api) == before_tables
    boundary = _key(expected[1])
    inserted = [
        _row("🛠", now),  # Newer by scalar ID alone: needs refresh.
        _row("\ue000", now),  # Older scalar ID: appears in the continuation.
        _row("0-newer", now + timedelta(microseconds=1)),
        _row("z-older", now - timedelta(microseconds=1)),
    ]
    _seed(pagination_api, inserted)
    before_tables = _snapshot(pagination_api)
    live = sorted(rows + inserted, key=_key, reverse=True)
    remaining = [row for row in live if _key(row) < boundary]
    cursor = _page(client, remaining, 1, cursor)
    assert cursor is not None
    assert _page(client, remaining[1:], 3, cursor) is None
    assert _page(client, live, 100, None) is None
    assert _snapshot(pagination_api) == before_tables
