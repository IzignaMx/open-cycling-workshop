"""Bounded connected reads: strict wire projection, cursor and fresh authority."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.inventory.models import InventoryMovementRecord
from sqlalchemy import event, select

from services.platform.tests.inventory.test_inventory_api import (
    PRODUCT,
    PRODUCTS,
    InventoryAPI,
)
from services.platform.tests.inventory.test_inventory_api import (
    inventory_api as inventory_api_fixture,
)

HISTORY = f"{PRODUCTS}/{PRODUCT}/movements"
FIELDS = {
    "movement_id",
    "product_id",
    "organization_id",
    "location_id",
    "kind",
    "quantity",
    "occurred_at",
}


@pytest.fixture
def read_api() -> Iterator[InventoryAPI]:
    yield from inventory_api_fixture.__wrapped__()


def seed_rows(api: InventoryAPI, rows: list[tuple[str, datetime, str, int]]) -> None:
    with api.factory() as session:
        for identifier, occurred_at, kind, quantity in rows:
            session.add(
                InventoryMovementRecord(
                    movement_id=identifier,
                    product_id=PRODUCT,
                    organization_id="org-1",
                    location_id="loc-1",
                    kind=kind,
                    quantity=quantity,
                    occurred_at=occurred_at,
                    actor_id="private-actor-canary",
                    order_id="private-order-canary",
                    reference_movement_id=None,
                    note="private-note-canary",
                )
            )
        session.commit()


def test_history_is_a_seven_field_projection_with_canonical_microseconds(
    read_api: InventoryAPI,
) -> None:
    seed_rows(
        read_api, [("move-a", datetime(2026, 10, 15, microsecond=1, tzinfo=UTC), "ADJUST", -7)]
    )
    response = read_api.client(capabilities=["inventory.read"]).get(HISTORY)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "items": [
            {
                "movement_id": "move-a",
                "product_id": PRODUCT,
                "organization_id": "org-1",
                "location_id": "loc-1",
                "kind": "ADJUST",
                "quantity": -7,
                "occurred_at": "2026-10-15T00:00:00.000001Z",
            }
        ],
        "next_cursor": None,
    }
    assert "private-" not in response.text


def test_cursor_uses_last_returned_row_and_microsecond_then_binary_id_order(
    read_api: InventoryAPI,
) -> None:
    start = datetime(2026, 10, 15, tzinfo=UTC)
    seed_rows(
        read_api,
        [
            ("a-new", start + timedelta(microseconds=1), "ADJUST", -3),
            ("\U00010000", start, "CONSUME", 2),
            ("\ue000", start, "ADJUST", -2),
            ("z-old", start - timedelta(microseconds=1), "RESERVE", -1),
        ],
    )
    client = read_api.client()
    seen = []
    before = None
    while True:
        query = {"limit": "1"}
        if before is not None:
            query["before"] = before
        response = client.get(HISTORY, params=query)
        assert response.status_code == 200, response.text
        page = response.json()
        assert len(page["items"]) == 1
        item = page["items"][0]
        assert set(item) == FIELDS
        seen.append(item["movement_id"])
        before = page["next_cursor"]
        if before is None:
            break
        cursor = json.loads(base64.urlsafe_b64decode(before + "=" * (-len(before) % 4)))
        assert cursor["before_movement_id"] == item["movement_id"]
        assert cursor["before_occurred_at"] == item["occurred_at"]
    assert seen == ["a-new", "\U00010000", "\ue000", "z-old"]


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=101",
        "limit=1&limit=2",
        "before=a&before=b",
        "private-secret=canary",
        "before=bad-canary",
        "before=" + "a" * 2049,
    ],
)
def test_new_query_boundary_refuses_without_echo(read_api: InventoryAPI, query: str) -> None:
    response = read_api.client().get(HISTORY + "?" + query)
    assert response.status_code == 422, response.text
    assert "canary" not in response.text
    assert "private-secret" not in response.text


@pytest.mark.parametrize(
    "route", [f"{PRODUCTS}?location_id=loc-1", f"{PRODUCTS}/{PRODUCT}/stock", HISTORY]
)
def test_each_inventory_read_owns_exactly_one_authority_session(
    read_api: InventoryAPI, route: str
) -> None:
    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("SELECT"):
            statements.append(statement)

    event.listen(read_api.engine, "before_cursor_execute", capture)
    try:
        response = read_api.client().get(route)
    finally:
        event.remove(read_api.engine, "before_cursor_execute", capture)
    assert response.status_code == 200, response.text
    assert sum("FROM organizations" in sql for sql in statements) == 1
    assert sum("FROM users" in sql for sql in statements) == 1
    # The legacy dependency performs a detached auth read. New reads must lock
    # and populate-existing inside the very transaction used for projection.
    assert "FROM organizations" in statements[0]
    assert "FROM users" in statements[1]


def test_denied_read_never_queries_product_or_ledger(read_api: InventoryAPI) -> None:
    client = read_api.client()
    with read_api.factory() as session:
        actor = session.get(UserRecord, "writer")
        assert actor is not None
        actor.capabilities = ["inventory.write"]
        session.commit()
    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(read_api.engine, "before_cursor_execute", capture)
    try:
        response = client.get(HISTORY)
    finally:
        event.remove(read_api.engine, "before_cursor_execute", capture)
    assert response.status_code == 403
    assert not any(
        "FROM products" in sql or "FROM inventory_movements" in sql for sql in statements
    )


def test_history_query_selects_only_public_columns_with_limit_plus_one(
    read_api: InventoryAPI,
) -> None:
    statements = []

    def capture(_connection, _cursor, statement, parameters, _context, _executemany):
        if "FROM inventory_movements" in statement:
            statements.append((statement, parameters))

    event.listen(read_api.engine, "before_cursor_execute", capture)
    try:
        response = read_api.client().get(HISTORY, params={"limit": 1})
    finally:
        event.remove(read_api.engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    assert len(statements) == 1
    sql, parameters = statements[0]
    for private in ["actor_id", "order_id", "reference_movement_id", "note"]:
        assert private not in sql
    assert "location_id =" in sql
    assert "COLLATE" in sql
    assert parameters[-2] == 2


@pytest.mark.parametrize("count", [0, 1, 2, 3, 5, 101])
def test_history_empty_exact_and_lookahead_pages(read_api: InventoryAPI, count: int) -> None:
    timestamp = datetime(2026, 10, 15, tzinfo=UTC)
    seed_rows(read_api, [(f"row-{n:03d}", timestamp, "ADJUST", n - 10) for n in range(count)])
    client = read_api.client()
    seen = []
    cursor = None
    while True:
        params = {"limit": "2"}
        if cursor:
            params["before"] = cursor
        response = client.get(HISTORY, params=params)
        assert response.status_code == 200, response.text
        page = response.json()
        assert set(page) == {"items", "next_cursor"}
        assert len(page["items"]) <= 2
        seen.extend(row["movement_id"] for row in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
        assert len(page["items"]) == 2
    assert seen == [f"row-{n:03d}" for n in reversed(range(count))]


def test_live_paging_newer_insert_requires_refresh_older_insert_can_appear(
    read_api: InventoryAPI,
) -> None:
    now = datetime(2026, 10, 15, tzinfo=UTC)
    seed_rows(read_api, [("m", now, "CONSUME", 1), ("a", now, "ADJUST", -1)])
    client = read_api.client()
    first = client.get(HISTORY, params={"limit": 1}).json()
    assert first["items"][0]["movement_id"] == "m"
    seed_rows(read_api, [("z", now, "ADJUST", 2), ("b", now, "RELEASE", 1)])
    older = client.get(HISTORY, params={"before": first["next_cursor"], "limit": 2}).json()
    assert [row["movement_id"] for row in older["items"]] == ["b", "a"]
    assert older["next_cursor"] is None
    newest = client.get(HISTORY).json()
    assert [row["movement_id"] for row in newest["items"]] == ["z", "m", "b", "a"]


@pytest.mark.parametrize(
    "capabilities",
    [["inventory.read"], ["inventory.read", "orders.read", "users.read", "inventory.write"]],
)
def test_additional_grants_do_not_expand_history_privacy(
    read_api: InventoryAPI, capabilities: list[str]
) -> None:
    seed_rows(
        read_api, [("private-fields-fixture", datetime(2026, 10, 15, tzinfo=UTC), "CONSUME", 4)]
    )
    with read_api.factory() as session:
        actor = session.get(UserRecord, "writer")
        assert actor is not None
        actor.capabilities = capabilities
        session.commit()
    response = read_api.client(capabilities=capabilities).get(HISTORY)
    assert response.status_code == 200
    assert set(response.json()["items"][0]) == FIELDS
    for forbidden in [
        "actor_id",
        "order_id",
        "reference_movement_id",
        "note",
        "private-actor",
        "private-order",
        "private-note",
    ]:
        assert forbidden not in response.text


@pytest.mark.parametrize(
    "route", [f"{PRODUCTS}?location_id=loc-1", f"{PRODUCTS}/{PRODUCT}/stock", HISTORY]
)
@pytest.mark.parametrize(
    "incoming,current,expected",
    [
        ({"inventory.read"}, {"*"}, 403),
        ({"*"}, {"inventory.read"}, 403),
        ({"inventory.read"}, {"*", "inventory.read"}, 200),
        ({"*"}, {"*"}, 200),
        ({"inventory.write"}, {"inventory.write"}, 403),
    ],
)
def test_reads_preserve_literal_intersection_and_frozen_wildcard(
    read_api: InventoryAPI, route: str, incoming: set[str], current: set[str], expected: int
) -> None:
    client = read_api.client(capabilities=sorted(incoming))
    with read_api.factory() as session:
        actor = session.get(UserRecord, "writer")
        assert actor is not None
        actor.capabilities = sorted(current)
        session.commit()
    response = client.get(route)
    assert response.status_code == expected, response.text


@pytest.mark.parametrize(
    "route", [f"{PRODUCTS}?location_id=loc-1", f"{PRODUCTS}/{PRODUCT}/stock", HISTORY]
)
@pytest.mark.parametrize("floor", [0, 1])
def test_valid_floors_do_not_require_or_adopt_write_protocol(
    read_api: InventoryAPI, route: str, floor: int
) -> None:
    from cycling_workshop.identity.domain import Principal
    from cycling_workshop.tenancy.models import OrganizationRecord

    client = read_api.client()
    with read_api.factory() as session:
        organization = session.get(OrganizationRecord, "org-1")
        assert organization is not None
        organization.minimum_write_protocol = floor
        incarnation = organization.dataset_incarnation
        session.commit()
    token = client.app.state.session_tokens.issue(
        Principal(
            "writer",
            "org-1",
            "loc-1",
            frozenset({"inventory.read"}),
            dataset_incarnation=incarnation if floor else None,
        )
    )
    client.headers["Authorization"] = "Bearer " + token
    assert "X-OCWP-Write-Protocol" not in client.headers
    response = client.get(route)
    assert response.status_code == 200, response.text
    with read_api.factory() as session:
        organization = session.get(OrganizationRecord, "org-1")
        assert organization is not None
        assert (organization.minimum_write_protocol, organization.dataset_incarnation) == (
            floor,
            incarnation,
        )


@pytest.mark.parametrize(
    "product,status",
    [
        ("00000000-0000-7000-8000-0000000003eb", 403),
        ("00000000-0000-7000-8000-0000000003ec", 404),
        ("missing", 404),
    ],
)
def test_history_keeps_product_scope_refusal_semantics(
    read_api: InventoryAPI, product: str, status: int
) -> None:
    response = read_api.client().get(f"{PRODUCTS}/{product}/movements")
    assert response.status_code == status
    assert product not in response.text


def test_history_explicitly_filters_product_location_even_for_legacy_rows(
    read_api: InventoryAPI,
) -> None:
    seed_rows(read_api, [("in-scope", datetime(2026, 10, 15, tzinfo=UTC), "ADJUST", -2)])
    with read_api.factory() as session:
        session.add(
            InventoryMovementRecord(
                movement_id="other-location",
                product_id=PRODUCT,
                organization_id="org-1",
                location_id="loc-2",
                kind="ADJUST",
                quantity=99,
                occurred_at=datetime(2026, 10, 16, tzinfo=UTC),
                actor_id="private",
                note="secret",
            )
        )
        session.commit()
    response = read_api.client().get(HISTORY)
    assert [row["movement_id"] for row in response.json()["items"]] == ["in-scope"]
    assert read_api.client().get(f"{PRODUCTS}/{PRODUCT}/stock").json()["available_quantity"] == -2


def test_reads_leave_every_business_table_identical_and_never_admit_or_commit(
    read_api: InventoryAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cycling_workshop.db.base import Base
    from cycling_workshop.identity import cutover
    from cycling_workshop.sync import writes

    seed_rows(read_api, [("immutable", datetime(2026, 10, 15, tzinfo=UTC), "CONSUME", 3)])

    def snapshot():
        with read_api.engine.connect() as connection:
            return {
                table.name: list(connection.execute(select(table)).mappings())
                for table in Base.metadata.sorted_tables
            }

    def forbidden(*_args, **_kwargs):
        pytest.fail("GET must never enter writer admission or commit")

    before = snapshot()
    monkeypatch.setattr(cutover, "write_admission", forbidden)
    monkeypatch.setattr(cutover, "commit_admitted", forbidden)
    monkeypatch.setattr(writes, "lock_writer", forbidden)
    client = read_api.client()
    commits = []
    event.listen(read_api.engine, "commit", lambda _connection: commits.append(True))
    for route in [f"{PRODUCTS}?location_id=loc-1", f"{PRODUCTS}/{PRODUCT}/stock", HISTORY]:
        assert client.get(route).status_code == 200
    assert not commits
    assert snapshot() == before


@pytest.mark.parametrize(
    "route,method",
    [
        (f"{PRODUCTS}?location_id=loc-1", "list_products"),
        (f"{PRODUCTS}/{PRODUCT}/stock", "available_quantity"),
        (HISTORY, "history"),
    ],
)
def test_signed_expiry_is_rechecked_after_response_materialization(
    read_api: InventoryAPI, monkeypatch: pytest.MonkeyPatch, route: str, method: str
) -> None:
    from cycling_workshop.identity.domain import Principal
    from cycling_workshop.identity.security import SessionTokenService
    from cycling_workshop.inventory import router as inventory_router
    from cycling_workshop.inventory.repository import SqlAlchemyInventoryRepository

    now = [datetime(2026, 10, 15, tzinfo=UTC)]
    tokens = SessionTokenService(
        secret="synthetic-inventory-read-expiry-secret",
        ttl=timedelta(seconds=60),
        clock=lambda: now[0],
    )
    client = read_api.client()
    client.app.state.session_tokens = tokens
    client.headers["Authorization"] = "Bearer " + tokens.issue(
        Principal("writer", "org-1", "loc-1", frozenset({"inventory.read"}))
    )
    owner = inventory_router if method == "history" else SqlAlchemyInventoryRepository
    name = "read_movement_page" if method == "history" else method
    original = getattr(owner, name)

    def finish_after_expiry(*args, **kwargs):
        result = original(*args, **kwargs)
        now[0] += timedelta(seconds=60)
        return result

    monkeypatch.setattr(owner, name, finish_after_expiry)
    response = client.get(route)
    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "invalid session"}


def test_org_and_actor_reads_are_locked_and_force_refreshed(read_api: InventoryAPI) -> None:
    from sqlalchemy.dialects import postgresql

    statements = []

    def capture(_connection, clause, _multiparams, _params, execution_options):
        sql = str(clause.compile(dialect=postgresql.dialect()))
        if "FROM organizations" in sql or "FROM users" in sql:
            statements.append((sql, execution_options))

    event.listen(read_api.engine, "before_execute", capture)
    try:
        assert read_api.client().get(HISTORY).status_code == 200
    finally:
        event.remove(read_api.engine, "before_execute", capture)
    assert len(statements) == 2
    assert all("FOR UPDATE" in sql and options["populate_existing"] for sql, options in statements)


@pytest.mark.parametrize(
    "route", [f"{PRODUCTS}?location_id=loc-1&limit=0", f"{PRODUCTS}/bad%00id/stock"]
)
def test_legacy_reads_authenticate_before_reporting_invalid_parameters(
    read_api: InventoryAPI, route: str
) -> None:
    client = read_api.client()
    client.headers.pop("Authorization")
    response = client.get(route)
    assert response.status_code == 401


@pytest.mark.parametrize("encoded_id", ["%ED%A0%80", "%ED%BF%BF"])
def test_history_rejects_malformed_surrogate_utf8_path(
    read_api: InventoryAPI, encoded_id: str
) -> None:
    response = read_api.client().get(f"{PRODUCTS}/{encoded_id}/movements")
    assert response.status_code == 422, response.text


def test_history_default_50_maximum_100_and_scope_bound_continuation(
    read_api: InventoryAPI,
) -> None:
    from services.platform.tests.inventory.test_inventory_api import SECOND_PRODUCT

    now = datetime(2026, 10, 15, tzinfo=UTC)
    seed_rows(read_api, [(f"bulk-{n:03d}", now, "ADJUST", 1) for n in range(101)])
    client = read_api.client()
    default = client.get(HISTORY).json()
    maximum = client.get(HISTORY, params={"limit": 100}).json()
    assert len(default["items"]) == 50
    assert len(maximum["items"]) == 100
    assert default["items"] == maximum["items"][:50]
    assert default["next_cursor"] and maximum["next_cursor"]
    mismatch = client.get(
        f"{PRODUCTS}/{SECOND_PRODUCT}/movements", params={"before": default["next_cursor"]}
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["code"] == "invalid_inventory_cursor"
    assert default["next_cursor"] not in mismatch.text


@pytest.mark.parametrize("change", ["inactive", "session", "scope", "incompatible", "incarnation"])
@pytest.mark.parametrize(
    "route", [f"{PRODUCTS}?location_id=loc-1", f"{PRODUCTS}/{PRODUCT}/stock", HISTORY]
)
def test_all_reads_refuse_invalid_current_session(
    read_api: InventoryAPI, change: str, route: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cycling_workshop.tenancy.models import OrganizationRecord

    client = read_api.client()
    with read_api.factory() as session:
        actor = session.get(UserRecord, "writer")
        organization = session.get(OrganizationRecord, "org-1")
        assert actor is not None and organization is not None
        if change == "inactive":
            actor.is_active = False
        elif change == "session":
            actor.session_version += 1
        elif change == "scope":
            actor.location_id = "loc-2"
        elif change == "incompatible":
            # Current SQL constraints reject invalid floors. Simulate the
            # compatibility validator's safe refusal, without bypassing them.
            from cycling_workshop.api.errors import ApiError
            from cycling_workshop.inventory import read_guard

            original = read_guard.lock_compatibility

            def refuse_compatibility(session, organization_id):
                original(session, organization_id)
                raise ApiError(503, "compatibility_state_invalid", "unavailable")

            monkeypatch.setattr(read_guard, "lock_compatibility", refuse_compatibility)
        else:
            organization.minimum_write_protocol = 1
        session.commit()
    response = client.get(route)
    assert response.status_code == 401, response.text
    assert response.headers["cache-control"] == "no-store"


def test_history_legacy_standalone_consumption_and_split_current_pair_are_not_rewritten(
    read_api: InventoryAPI,
) -> None:
    from services.platform.tests.inventory.test_inventory_api import ORDER, _record

    now = datetime(2026, 10, 15, tzinfo=UTC)
    seed_rows(read_api, [("legacy-unlinked", now, "CONSUME", 2)])
    client = read_api.client()
    _record(client, 8001, quantity=10)
    reservation = _record(client, 8002, kind="RESERVE", quantity=3, order_id=ORDER)
    consumed = _record(
        client,
        8003,
        kind="CONSUME",
        quantity=3,
        order_id=ORDER,
        reference_movement_id=reservation["movement_id"],
    )
    before = [
        (row.movement_id, row.kind, row.quantity, row.reference_movement_id, row.note)
        for row in read_api.ledger()
    ]
    seen = []
    cursor = None
    while True:
        params = {"limit": "1"}
        if cursor:
            params["before"] = cursor
        page = client.get(HISTORY, params=params).json()
        seen.extend(page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == 5
    assert sum(row["quantity"] for row in seen) == 9
    assert client.get(f"{PRODUCTS}/{PRODUCT}/stock").json()["available_quantity"] == 9
    assert any(
        row["movement_id"] == "legacy-unlinked"
        and row["kind"] == "CONSUME"
        and row["quantity"] == 2
        for row in seen
    )
    assert any(
        row["movement_id"] == consumed["movement_id"] and row["quantity"] == 3 for row in seen
    )
    assert any(row["kind"] == "ADJUST" and row["quantity"] == -3 for row in seen)
    assert all(set(row) == FIELDS for row in seen)
    assert before == [
        (row.movement_id, row.kind, row.quantity, row.reference_movement_id, row.note)
        for row in read_api.ledger()
    ]
