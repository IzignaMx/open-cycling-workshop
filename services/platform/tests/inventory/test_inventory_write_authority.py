"""Functional stale-principal proof; real lock waits are tested separately."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from cycling_workshop.identity.dependencies import principal_from_request
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.inventory.models import ProductRecord
from sqlalchemy import event, select

from services.platform.tests.inventory.test_inventory_api import (
    CAPABILITIES,
    MOVEMENTS,
    ORDER,
    PRODUCT,
    PRODUCTS,
    InventoryAPI,
    _id,
    _movement_payload,
    _product_payload,
    _record,
)
from services.platform.tests.inventory.test_inventory_api import (
    inventory_api as inventory_api_fixture,
)


@pytest.fixture
def authority_api() -> Iterator[InventoryAPI]:
    yield from inventory_api_fixture.__wrapped__()


@pytest.mark.parametrize(
    "command", ["product", "ADJUST", "RESERVE", "RELEASE", "CONSUME", "replay"]
)
@pytest.mark.parametrize("change", ["session", "inactive", "grants", "location", "narrow_scope"])
def test_inventory_revalidates_stale_principal_before_effects(
    authority_api: InventoryAPI, command: str, change: str
) -> None:
    api = authority_api
    client = api.client(user_id="manager", location_id=None)
    _record(client, 3001)
    reservation = _record(client, 3002, kind="RESERVE", quantity=4, order_id=ORDER)
    original = _record(client, 3003, quantity=2)
    before = [(row.movement_id, row.quantity) for row in api.ledger()]
    stale = Principal("manager", "org-1", None, frozenset(CAPABILITIES))
    if change == "location":
        stale = replace(stale, location_id="loc-1")
    stale = replace(stale, expires_at=datetime.now(UTC) + timedelta(hours=1))
    client.app.dependency_overrides[principal_from_request] = lambda: stale
    with api.factory() as session:
        actor = session.get(UserRecord, "manager")
        assert actor is not None
        if change == "session":
            actor.session_version += 1
        elif change == "inactive":
            actor.is_active = False
        elif change == "grants":
            actor.capabilities = ["inventory.read"]
        else:
            actor.location_id = "loc-2"
        session.commit()

    if command == "product":
        path, payload = PRODUCTS, _product_payload(product_id=_id(4001))
    elif command == "replay":
        path, payload = MOVEMENTS, _movement_payload(3003, quantity=2)
    else:
        path, payload = MOVEMENTS, _movement_payload(4001, kind=command, quantity=4)
        if command != "ADJUST":
            payload["order_id"] = ORDER
        if command in {"RELEASE", "CONSUME"}:
            payload["reference_movement_id"] = reservation["movement_id"]
    response = client.post(path, json=payload)
    assert response.status_code == (403 if change in {"grants", "narrow_scope"} else 401)
    assert [(row.movement_id, row.quantity) for row in api.ledger()] == before
    assert original["movement_id"] in {row.movement_id for row in api.ledger()}
    with api.factory() as session:
        assert session.get(ProductRecord, _id(4001)) is None


@pytest.mark.parametrize("command", ["product", "movement"])
@pytest.mark.parametrize(
    ("incoming", "current", "expected"),
    [
        ({"inventory.write"}, {"*"}, 403),
        ({"*"}, {"inventory.write"}, 403),
        ({"inventory.write"}, {"*", "inventory.write"}, 201),
        ({"*"}, {"*"}, 201),
        ({"*", "inventory.write"}, {"inventory.write"}, 201),
    ],
)
def test_inventory_refresh_preserves_literal_grants(
    authority_api: InventoryAPI, command: str, incoming: set[str], current: set[str], expected: int
) -> None:
    api = authority_api
    client = api.client()
    # The incoming dependency has already intersected token and initial account.
    stale = Principal("writer", "org-1", "loc-1", frozenset(incoming))
    stale = replace(stale, expires_at=datetime.now(UTC) + timedelta(hours=1))
    client.app.dependency_overrides[principal_from_request] = lambda: stale
    with api.factory() as session:
        actor = session.get(UserRecord, "writer")
        assert actor is not None
        actor.capabilities = sorted(current)
        session.commit()
    path, payload = (
        (PRODUCTS, _product_payload(product_id=_id(4001)))
        if command == "product"
        else (MOVEMENTS, _movement_payload(4001))
    )
    response = client.post(path, json=payload)
    assert response.status_code == expected
    if expected == 403:
        assert not api.ledger()
        with api.factory() as session:
            assert session.get(ProductRecord, _id(4001)) is None


@pytest.mark.parametrize("grants", [[], ["inventory.write"]])
def test_movement_refresh_precedes_product_read(
    authority_api: InventoryAPI, grants: list[str]
) -> None:
    api = authority_api
    client = api.client()
    stale = Principal("writer", "org-1", "loc-1", frozenset(CAPABILITIES))
    stale = replace(stale, expires_at=datetime.now(UTC) + timedelta(hours=1))
    client.app.dependency_overrides[principal_from_request] = lambda: stale
    with api.factory() as session:
        actor = session.get(UserRecord, "writer")
        assert actor is not None
        actor.capabilities = grants
        session.commit()
    statements: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(api.engine, "before_cursor_execute", capture)
    try:
        response = client.post(MOVEMENTS, json=_movement_payload(4001))
    finally:
        event.remove(api.engine, "before_cursor_execute", capture)
    assert response.status_code == (201 if grants else 403)
    selects = [statement for statement in statements if statement.startswith("SELECT")]
    assert "FROM organizations" in selects[0]
    assert "FROM users" in selects[1]
    assert any("FROM products" in statement for statement in selects) == bool(grants)
    if grants:
        assert "FROM products" in selects[2]
        with api.factory() as session:
            assert session.scalar(select(ProductRecord.id).where(ProductRecord.id == PRODUCT))
