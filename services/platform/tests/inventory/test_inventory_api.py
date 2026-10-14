from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import pytest
from cycling_workshop.app import create_app
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.db.base import Base
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.inventory.models import InventoryMovementRecord, ProductRecord
from cycling_workshop.service_orders.models import ServiceOrderRecord
from cycling_workshop.settings import Settings
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

NOW = datetime(2026, 10, 13, tzinfo=UTC)
PRODUCTS = "/api/v1/inventory/products"
MOVEMENTS = "/api/v1/inventory/movements"
CAPABILITIES = ["inventory.read", "inventory.write"]


def _id(number: int) -> str:
    return f"00000000-0000-7000-8000-{number:012x}"


PRODUCT = _id(1001)
SECOND_PRODUCT = _id(1002)
OTHER_LOCATION_PRODUCT = _id(1003)
FOREIGN_PRODUCT = _id(1004)
ORDER = _id(2001)
SECOND_ORDER = _id(2002)
OTHER_LOCATION_ORDER = _id(2003)
FOREIGN_ORDER = _id(2004)
MISSING = _id(9999)


@dataclass
class InventoryAPI:
    engine: Engine
    factory: sessionmaker[Session]
    clients: list[TestClient] = field(default_factory=list)

    def client(
        self,
        *,
        user_id: str = "writer",
        organization_id: str = "org-1",
        location_id: str | None = "loc-1",
        capabilities: list[str] | None = None,
    ) -> TestClient:
        app = create_app(
            settings=Settings(
                environment="test",
                database_url="sqlite+pysqlite:///:memory:",
                log_level="WARNING",
                auth_secret="inventory-api-test-secret-long-enough",
            ),
            session_factory=self.factory,
        )
        token = app.state.session_tokens.issue(
            Principal(
                user_id=user_id,
                organization_id=organization_id,
                location_id=location_id,
                capabilities=frozenset(CAPABILITIES if capabilities is None else capabilities),
            )
        )
        client = TestClient(app)
        client.headers["Authorization"] = f"Bearer {token}"
        self.clients.append(client)
        return client

    def ledger(self) -> list[InventoryMovementRecord]:
        with self.factory() as session:
            return list(
                session.scalars(
                    select(InventoryMovementRecord).order_by(InventoryMovementRecord.movement_id)
                )
            )


@pytest.fixture
def inventory_api() -> Iterator[InventoryAPI]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                OrganizationRecord(id="org-1", name="Taller"),
                OrganizationRecord(id="org-2", name="Otro"),
            ]
        )
        session.flush()
        scopes = [("org-1", "loc-1"), ("org-1", "loc-2"), ("org-2", "loc-x")]
        for organization, location in scopes:
            session.add(LocationRecord(id=location, organization_id=organization, name=location))
        session.flush()
        for user_id, organization, location in [
            ("writer", "org-1", "loc-1"),
            ("second-writer", "org-1", "loc-1"),
            ("manager", "org-1", None),
            ("other-location", "org-1", "loc-2"),
            ("foreign", "org-2", "loc-x"),
        ]:
            session.add(
                UserRecord(
                    id=user_id,
                    organization_id=organization,
                    location_id=location,
                    username=user_id,
                    display_name=user_id,
                    password_hash="unused-in-token-tests",
                    capabilities=CAPABILITIES,
                    is_active=True,
                    session_version=1,
                )
            )
        for organization, location in scopes:
            session.add(
                CustomerRecord(
                    id=f"customer-{location}",
                    organization_id=organization,
                    location_id=location,
                    display_name="Cliente",
                    created_at=NOW,
                    updated_at=NOW,
                    version=1,
                )
            )
        session.flush()
        for product_id, order_id, organization, location in [
            (PRODUCT, ORDER, "org-1", "loc-1"),
            (SECOND_PRODUCT, SECOND_ORDER, "org-1", "loc-1"),
            (OTHER_LOCATION_PRODUCT, OTHER_LOCATION_ORDER, "org-1", "loc-2"),
            (FOREIGN_PRODUCT, FOREIGN_ORDER, "org-2", "loc-x"),
        ]:
            session.add(
                ProductRecord(
                    id=product_id,
                    organization_id=organization,
                    location_id=location,
                    sku=f"SKU-{product_id[-4:]}",
                    name=f"Repuesto {product_id[-4:]}",
                    unit="pieza",
                    created_at=NOW,
                    updated_at=NOW,
                    version=1,
                )
            )
            session.add(
                ServiceOrderRecord(
                    id=order_id,
                    organization_id=organization,
                    location_id=location,
                    customer_id=f"customer-{location}",
                    state="INTAKE",
                    reported_problem="Revisión de frenos",
                    priority="normal",
                    created_at=NOW,
                    updated_at=NOW,
                    version=1,
                )
            )
        session.commit()
    api = InventoryAPI(engine, factory)
    try:
        yield api
    finally:
        for client in api.clients:
            client.close()
        engine.dispose()


def _product_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "location_id": "loc-1",
        "sku": "  pad   01  ",
        "name": "  Pastilla   de freno  ",
    }
    payload.update(overrides)
    return payload


def test_create_product_normalizes_and_derives_server_fields(inventory_api: InventoryAPI) -> None:
    before = datetime.now(UTC)
    response = inventory_api.client().post(PRODUCTS, json=_product_payload())

    assert response.status_code == 201, response.text
    body = response.json()
    assert UUID(body["product_id"]).version == 7
    assert body["organization_id"] == "org-1"
    assert body["location_id"] == "loc-1"
    assert body["sku"] == "PAD-01"
    assert body["name"] == "Pastilla de freno"
    assert body["unit"] == "pieza"
    assert body["version"] == 1
    assert before <= datetime.fromisoformat(body["created_at"]) <= datetime.now(UTC)
    assert body["created_at"] == body["updated_at"]


def _movement_payload(movement_number: int, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "movement_id": _id(movement_number),
        "product_id": PRODUCT,
        "kind": "ADJUST",
        "quantity": 10,
    }
    payload.update(overrides)
    return payload


def _record(client: TestClient, movement_number: int, **overrides: object) -> dict[str, object]:
    response = client.post(MOVEMENTS, json=_movement_payload(movement_number, **overrides))
    assert response.status_code == 201, response.text
    return response.json()


def _stock(client: TestClient, product_id: str = PRODUCT) -> int:
    response = client.get(f"{PRODUCTS}/{product_id}/stock")
    assert response.status_code == 200, response.text
    return response.json()["available_quantity"]


def _reserve(client: TestClient, *, quantity: int = 4) -> dict[str, object]:
    _record(client, 3001)
    return _record(client, 3002, kind="RESERVE", quantity=quantity, order_id=ORDER)


def _snapshot(api: InventoryAPI) -> list[tuple[object, ...]]:
    return [
        (
            row.movement_id,
            row.product_id,
            row.organization_id,
            row.location_id,
            row.kind,
            row.quantity,
            row.order_id,
            row.reference_movement_id,
            row.actor_id,
            row.note,
            row.occurred_at,
        )
        for row in api.ledger()
    ]


def test_create_product_accepts_client_uuidv7_and_custom_unit(inventory_api: InventoryAPI) -> None:
    response = inventory_api.client().post(
        PRODUCTS,
        json=_product_payload(product_id=_id(1100), unit="  caja  "),
    )

    assert response.status_code == 201, response.text
    assert response.json()["product_id"] == _id(1100)
    assert response.json()["unit"] == "caja"


@pytest.mark.parametrize("conflict", ["sku", "product_id"])
def test_product_uniqueness_conflicts_leave_existing_product_intact(
    inventory_api: InventoryAPI, conflict: str
) -> None:
    client = inventory_api.client()
    payload = _product_payload(product_id=_id(1100))
    first = client.post(PRODUCTS, json=payload)
    assert first.status_code == 201, first.text
    retry = dict(payload)
    retry["name"] = "Otro nombre"
    retry["product_id" if conflict == "sku" else "sku"] = (
        _id(1101) if conflict == "sku" else "DISTINCT-SKU"
    )

    duplicate = client.post(PRODUCTS, json=retry)

    assert duplicate.status_code == 409, duplicate.text
    with inventory_api.factory() as session:
        products = list(session.scalars(select(ProductRecord)))
        assert len(products) == 5
        existing = session.get(ProductRecord, _id(1100))
        assert existing is not None
        assert existing.name == "Pastilla de freno"
        assert existing.sku == "PAD-01"


@pytest.mark.parametrize(
    "overrides",
    [
        {"product_id": "not-a-uuid"},
        {"product_id": "00000000-0000-4000-8000-000000000001"},
        {"location_id": ""},
        {"location_id": "x" * 37},
        {"sku": ""},
        {"sku": "  "},
        {"sku": "x" * 81},
        {"name": ""},
        {"name": "  "},
        {"name": "x" * 201},
        {"unit": ""},
        {"unit": "  "},
        {"unit": "x" * 31},
        {"organization_id": "org-2"},
        {"created_at": NOW.isoformat()},
        {"updated_at": NOW.isoformat()},
        {"version": 42},
        {"unexpected": "value"},
    ],
)
def test_product_schema_rejects_invalid_or_server_owned_fields(
    inventory_api: InventoryAPI, overrides: dict[str, object]
) -> None:
    response = inventory_api.client().post(PRODUCTS, json=_product_payload(**overrides))

    assert response.status_code == 422, response.text
    with inventory_api.factory() as session:
        assert len(list(session.scalars(select(ProductRecord)))) == 4


def test_product_list_filters_location_and_paginates(inventory_api: InventoryAPI) -> None:
    client = inventory_api.client()
    whole = client.get(PRODUCTS, params={"location_id": "loc-1"})
    first = client.get(PRODUCTS, params={"location_id": "loc-1", "limit": 1, "offset": 0})
    second = client.get(PRODUCTS, params={"location_id": "loc-1", "limit": 1, "offset": 1})
    empty = client.get(PRODUCTS, params={"location_id": "loc-1", "offset": 2})

    assert whole.status_code == first.status_code == second.status_code == empty.status_code == 200
    assert {row["product_id"] for row in whole.json()} == {PRODUCT, SECOND_PRODUCT}
    assert len(first.json()) == len(second.json()) == 1
    assert first.json() + second.json() == whole.json()
    assert empty.json() == []
    assert all(row["organization_id"] == "org-1" for row in whole.json())
    assert all(row["location_id"] == "loc-1" for row in whole.json())


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"location_id": ""},
        {"location_id": "x" * 37},
        {"location_id": "loc-1", "limit": 0},
        {"location_id": "loc-1", "limit": 201},
        {"location_id": "loc-1", "offset": -1},
    ],
)
def test_product_list_validates_bounded_pagination_and_required_location(
    inventory_api: InventoryAPI, params: dict[str, object]
) -> None:
    response = inventory_api.client().get(PRODUCTS, params=params)
    assert response.status_code == 422, response.text


def test_organization_wide_principal_can_explicitly_select_a_location(
    inventory_api: InventoryAPI,
) -> None:
    client = inventory_api.client(user_id="manager", location_id=None)
    created = client.post(PRODUCTS, json=_product_payload(location_id="loc-2"))
    listing = client.get(PRODUCTS, params={"location_id": "loc-2"})

    assert created.status_code == 201, created.text
    assert created.json()["organization_id"] == "org-1"
    assert created.json()["location_id"] == "loc-2"
    assert listing.status_code == 200, listing.text
    assert {row["product_id"] for row in listing.json()} == {
        OTHER_LOCATION_PRODUCT,
        created.json()["product_id"],
    }
    assert _stock(client, OTHER_LOCATION_PRODUCT) == 0


@pytest.mark.parametrize("location", ["loc-x", "missing-location"])
def test_unknown_and_foreign_locations_are_hidden_from_organization_wide_principal(
    inventory_api: InventoryAPI, location: str
) -> None:
    client = inventory_api.client(user_id="manager", location_id=None)
    created = client.post(PRODUCTS, json=_product_payload(location_id=location))
    listing = client.get(PRODUCTS, params={"location_id": location})

    assert created.status_code == 404, created.text
    assert listing.status_code == 404, listing.text


_ENDPOINTS = [
    ("POST", PRODUCTS, _product_payload(), "inventory.write"),
    ("GET", f"{PRODUCTS}?location_id=loc-1", None, "inventory.read"),
    ("GET", f"{PRODUCTS}/{PRODUCT}/stock", None, "inventory.read"),
    ("POST", MOVEMENTS, _movement_payload(3001), "inventory.write"),
]


@pytest.mark.parametrize("method,url,payload,capability", _ENDPOINTS)
def test_inventory_endpoints_require_authentication(
    inventory_api: InventoryAPI,
    method: str,
    url: str,
    payload: dict[str, object] | None,
    capability: str,
) -> None:
    client = inventory_api.client()
    client.headers.pop("Authorization")

    response = client.request(method, url, json=payload)

    assert response.status_code == 401, response.text
    assert inventory_api.ledger() == []


@pytest.mark.parametrize("method,url,payload,capability", _ENDPOINTS)
def test_inventory_endpoints_require_the_matching_capability(
    inventory_api: InventoryAPI,
    method: str,
    url: str,
    payload: dict[str, object] | None,
    capability: str,
) -> None:
    client = inventory_api.client(
        capabilities=[value for value in CAPABILITIES if value != capability]
    )

    response = client.request(method, url, json=payload)

    assert response.status_code == 403, response.text
    assert inventory_api.ledger() == []


def test_persisted_capability_revocation_is_effective_for_existing_token(
    inventory_api: InventoryAPI,
) -> None:
    client = inventory_api.client()
    with inventory_api.factory() as session:
        user = session.get(UserRecord, "writer")
        assert user is not None
        user.capabilities = ["inventory.read"]
        session.commit()

    response = client.post(MOVEMENTS, json=_movement_payload(3001))

    assert response.status_code == 403, response.text
    assert inventory_api.ledger() == []


def test_location_scoped_principal_cannot_access_another_location(
    inventory_api: InventoryAPI,
) -> None:
    client = inventory_api.client()
    responses = [
        client.post(PRODUCTS, json=_product_payload(location_id="loc-2")),
        client.get(PRODUCTS, params={"location_id": "loc-2"}),
        client.get(f"{PRODUCTS}/{OTHER_LOCATION_PRODUCT}/stock"),
        client.post(MOVEMENTS, json=_movement_payload(3001, product_id=OTHER_LOCATION_PRODUCT)),
    ]

    assert [response.status_code for response in responses] == [403, 403, 403, 403]
    assert inventory_api.ledger() == []


@pytest.mark.parametrize("product_id", [MISSING, FOREIGN_PRODUCT])
def test_unknown_and_foreign_products_are_hidden(
    inventory_api: InventoryAPI, product_id: str
) -> None:
    client = inventory_api.client()
    read = client.get(f"{PRODUCTS}/{product_id}/stock")
    write = client.post(MOVEMENTS, json=_movement_payload(3001, product_id=product_id))

    assert read.status_code == write.status_code == 404
    assert inventory_api.ledger() == []


def test_stock_response_includes_scope_and_empty_ledger_quantity(
    inventory_api: InventoryAPI,
) -> None:
    response = inventory_api.client().get(f"{PRODUCTS}/{PRODUCT}/stock")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "product_id": PRODUCT,
        "organization_id": "org-1",
        "location_id": "loc-1",
        "available_quantity": 0,
    }


def test_signed_adjustments_append_audited_rows_and_derive_stock(
    inventory_api: InventoryAPI,
) -> None:
    client = inventory_api.client()
    before = datetime.now(UTC)
    added = _record(client, 3001, note="  Entrega   inicial  ")
    first_snapshot = _snapshot(inventory_api)
    removed = _record(client, 3002, quantity=-3)

    assert added["movement_id"] == _id(3001)
    assert added["product_id"] == PRODUCT
    assert added["organization_id"] == "org-1"
    assert added["location_id"] == "loc-1"
    assert added["actor_id"] == "writer"
    assert added["kind"] == "ADJUST"
    assert added["quantity"] == 10
    assert added["note"] == "Entrega inicial"
    assert added["order_id"] is None
    assert added["reference_movement_id"] is None
    assert before <= datetime.fromisoformat(added["occurred_at"]) <= datetime.now(UTC)
    assert removed["quantity"] == -3
    assert _stock(client) == 7
    assert len(inventory_api.ledger()) == 2
    assert _snapshot(inventory_api)[:1] == first_snapshot


@pytest.mark.parametrize("kind", ["ADJUST", "RESERVE", "RELEASE", "CONSUME"])
@pytest.mark.parametrize("quantity", [0, True, False, 1.0, 1.5, "1", None])
def test_movement_quantity_must_be_a_nonzero_strict_integer(
    inventory_api: InventoryAPI, kind: str, quantity: object
) -> None:
    payload = _movement_payload(3001, kind=kind, quantity=quantity)
    if kind != "ADJUST":
        payload["order_id"] = ORDER
    if kind in {"RELEASE", "CONSUME"}:
        payload["reference_movement_id"] = _id(3000)

    response = inventory_api.client().post(MOVEMENTS, json=payload)

    assert response.status_code == 422, response.text
    assert inventory_api.ledger() == []


@pytest.mark.parametrize("kind", ["RESERVE", "RELEASE", "CONSUME"])
def test_only_adjustments_accept_negative_quantities(
    inventory_api: InventoryAPI, kind: str
) -> None:
    payload = _movement_payload(3001, kind=kind, quantity=-1, order_id=ORDER)
    if kind != "RESERVE":
        payload["reference_movement_id"] = _id(3000)

    response = inventory_api.client().post(MOVEMENTS, json=payload)

    assert response.status_code == 422, response.text
    assert inventory_api.ledger() == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"movement_id": "not-a-uuid"},
        {"movement_id": "00000000-0000-4000-8000-000000000001"},
        {"movement_id": None},
        {"reference_movement_id": "not-a-uuid"},
        {"product_id": ""},
        {"product_id": "x" * 37},
        {"order_id": ""},
        {"order_id": "x" * 37},
        {"reference_movement_id": "x" * 37},
        {"kind": "unknown"},
        {"kind": "adjust"},
        {"note": "x" * 2001},
        {"actor_id": "foreign"},
        {"organization_id": "org-2"},
        {"location_id": "loc-x"},
        {"occurred_at": NOW.isoformat()},
        {"unexpected": "value"},
    ],
)
def test_movement_schema_rejects_invalid_or_server_owned_fields(
    inventory_api: InventoryAPI, overrides: dict[str, object]
) -> None:
    response = inventory_api.client().post(MOVEMENTS, json=_movement_payload(3001, **overrides))

    assert response.status_code == 422, response.text
    assert inventory_api.ledger() == []


def test_movement_requires_caller_supplied_idempotency_identifier(
    inventory_api: InventoryAPI,
) -> None:
    payload = _movement_payload(3001)
    del payload["movement_id"]

    response = inventory_api.client().post(MOVEMENTS, json=payload)

    assert response.status_code == 422, response.text
    assert inventory_api.ledger() == []


@pytest.mark.parametrize(
    "kind,missing_field",
    [
        ("RESERVE", "order_id"),
        ("RELEASE", "order_id"),
        ("CONSUME", "order_id"),
        ("RELEASE", "reference_movement_id"),
        ("CONSUME", "reference_movement_id"),
    ],
)
def test_reservation_commands_require_order_and_finalizer_reference(
    inventory_api: InventoryAPI, kind: str, missing_field: str
) -> None:
    payload = _movement_payload(3001, kind=kind, order_id=ORDER)
    if kind != "RESERVE":
        payload["reference_movement_id"] = _id(3000)
    del payload[missing_field]

    response = inventory_api.client().post(MOVEMENTS, json=payload)

    assert response.status_code == 422, response.text
    assert inventory_api.ledger() == []


@pytest.mark.parametrize("kind", ["ADJUST", "RESERVE"])
def test_adjust_and_reserve_reject_reference_movements(
    inventory_api: InventoryAPI, kind: str
) -> None:
    client = inventory_api.client()
    reservation = _reserve(client)
    before = _snapshot(inventory_api)

    response = client.post(
        MOVEMENTS,
        json=_movement_payload(
            3003, kind=kind, order_id=ORDER, reference_movement_id=reservation["movement_id"]
        ),
    )

    assert response.status_code == 422, response.text
    assert _snapshot(inventory_api) == before


@pytest.mark.parametrize("kind", ["RELEASE", "CONSUME"])
def test_reserve_and_finalize_preserve_stock_and_full_audit_links(
    inventory_api: InventoryAPI, kind: str
) -> None:
    client = inventory_api.client()
    reservation = _reserve(client)
    before = _snapshot(inventory_api)
    assert reservation["quantity"] == -4
    assert reservation["order_id"] == ORDER
    assert _stock(client) == 6

    finalized = _record(
        client,
        3003,
        kind=kind,
        quantity=4,
        order_id=ORDER,
        reference_movement_id=reservation["movement_id"],
        note="  Repuesto   procesado  ",
    )

    assert finalized["kind"] == kind
    assert finalized["quantity"] == 4
    assert finalized["reference_movement_id"] == reservation["movement_id"]
    assert finalized["order_id"] == ORDER
    assert finalized["actor_id"] == "writer"
    assert finalized["note"] == "Repuesto procesado"
    assert _stock(client) == (10 if kind == "RELEASE" else 6)
    rows = inventory_api.ledger()
    assert len(rows) == (3 if kind == "RELEASE" else 4)
    assert _snapshot(inventory_api)[:2] == before
    if kind == "CONSUME":
        issues = [row for row in rows if row.kind == "ADJUST" and row.quantity == -4]
        assert len(issues) == 1
        issue = issues[0]
        assert issue.reference_movement_id == reservation["movement_id"]
        assert finalized["movement_id"] in issue.note
        assert issue.order_id == ORDER
        assert issue.product_id == PRODUCT
        assert issue.organization_id == "org-1"
        assert issue.location_id == "loc-1"
        assert issue.actor_id == "writer"
        assert issue.occurred_at.replace(tzinfo=UTC) == datetime.fromisoformat(
            finalized["occurred_at"]
        )
        assert UUID(issue.movement_id).version == 7
        assert issue.movement_id not in {_id(3001), _id(3002), _id(3003)}


@pytest.mark.parametrize("available,requested", [(0, 1), (3, 4)])
def test_reservation_cannot_exceed_available_stock(
    inventory_api: InventoryAPI, available: int, requested: int
) -> None:
    client = inventory_api.client()
    if available:
        _record(client, 3001, quantity=available)
    before = _snapshot(inventory_api)

    response = client.post(
        MOVEMENTS,
        json=_movement_payload(3002, kind="RESERVE", quantity=requested, order_id=ORDER),
    )

    assert response.status_code == 409, response.text
    assert _stock(client) == available
    assert _snapshot(inventory_api) == before


def test_reservation_can_hold_exactly_all_remaining_stock(inventory_api: InventoryAPI) -> None:
    client = inventory_api.client()
    reservation = _reserve(client, quantity=10)

    assert reservation["quantity"] == -10
    assert _stock(client) == 0
    assert len(inventory_api.ledger()) == 2


@pytest.mark.parametrize("order_id", [MISSING, FOREIGN_ORDER, OTHER_LOCATION_ORDER])
def test_reservation_rejects_missing_foreign_and_other_location_orders_without_writes(
    inventory_api: InventoryAPI, order_id: str
) -> None:
    client = inventory_api.client()
    _record(client, 3001)
    before = _snapshot(inventory_api)

    response = client.post(
        MOVEMENTS,
        json=_movement_payload(3002, kind="RESERVE", quantity=4, order_id=order_id),
    )

    assert response.status_code == 404, response.text
    assert _snapshot(inventory_api) == before
    assert _stock(client) == 10


@pytest.mark.parametrize("kind", ["RELEASE", "CONSUME"])
@pytest.mark.parametrize("quantity", [1, 5])
def test_finalization_requires_the_exact_full_reservation_quantity(
    inventory_api: InventoryAPI, kind: str, quantity: int
) -> None:
    client = inventory_api.client()
    reservation = _reserve(client)
    before = _snapshot(inventory_api)

    response = client.post(
        MOVEMENTS,
        json=_movement_payload(
            3003,
            kind=kind,
            quantity=quantity,
            order_id=ORDER,
            reference_movement_id=reservation["movement_id"],
        ),
    )

    assert response.status_code == 409, response.text
    assert _stock(client) == 6
    assert _snapshot(inventory_api) == before


@pytest.mark.parametrize("kind", ["RELEASE", "CONSUME"])
@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"reference_movement_id": MISSING}, 404),
        ({"reference_movement_id": _id(3001)}, 409),
        ({"product_id": SECOND_PRODUCT}, 409),
        ({"order_id": SECOND_ORDER}, 409),
        ({"order_id": MISSING}, 404),
        ({"order_id": FOREIGN_ORDER}, 404),
        ({"order_id": OTHER_LOCATION_ORDER}, 404),
    ],
)
def test_finalizer_references_are_existing_scoped_matching_reservations(
    inventory_api: InventoryAPI, kind: str, changes: dict[str, object], expected: int
) -> None:
    client = inventory_api.client()
    _reserve(client)
    before = _snapshot(inventory_api)
    payload = _movement_payload(
        3003, kind=kind, quantity=4, order_id=ORDER, reference_movement_id=_id(3002)
    )
    payload.update(changes)

    response = client.post(MOVEMENTS, json=payload)

    assert response.status_code == expected, response.text
    assert _stock(client) == 6
    assert _stock(client, SECOND_PRODUCT) == 0
    assert _snapshot(inventory_api) == before


@pytest.mark.parametrize("kind", ["RELEASE", "CONSUME"])
@pytest.mark.parametrize("scope", ["foreign", "other-location"])
def test_finalizer_cannot_reference_reservations_outside_its_scope(
    inventory_api: InventoryAPI, kind: str, scope: str
) -> None:
    client = inventory_api.client()
    if scope == "foreign":
        other = inventory_api.client(
            user_id="foreign", organization_id="org-2", location_id="loc-x"
        )
        product_id, order_id = FOREIGN_PRODUCT, FOREIGN_ORDER
    else:
        other = inventory_api.client(user_id="other-location", location_id="loc-2")
        product_id, order_id = OTHER_LOCATION_PRODUCT, OTHER_LOCATION_ORDER
    _record(other, 3101, product_id=product_id)
    reservation = _record(
        other, 3102, product_id=product_id, kind="RESERVE", quantity=4, order_id=order_id
    )
    before = _snapshot(inventory_api)

    response = client.post(
        MOVEMENTS,
        json=_movement_payload(
            3001,
            kind=kind,
            quantity=4,
            order_id=ORDER,
            reference_movement_id=reservation["movement_id"],
        ),
    )

    assert response.status_code == 404, response.text
    assert _snapshot(inventory_api) == before
    assert _stock(client) == 0
    assert _stock(other, product_id) == 6


@pytest.mark.parametrize("first_kind", ["RELEASE", "CONSUME"])
@pytest.mark.parametrize("second_kind", ["RELEASE", "CONSUME"])
def test_reservation_can_be_finalized_only_once_across_both_kinds(
    inventory_api: InventoryAPI, first_kind: str, second_kind: str
) -> None:
    client = inventory_api.client()
    reservation = _reserve(client)
    _record(
        client,
        3003,
        kind=first_kind,
        quantity=4,
        order_id=ORDER,
        reference_movement_id=reservation["movement_id"],
    )
    before = _snapshot(inventory_api)

    response = client.post(
        MOVEMENTS,
        json=_movement_payload(
            3004,
            kind=second_kind,
            quantity=4,
            order_id=ORDER,
            reference_movement_id=reservation["movement_id"],
        ),
    )

    assert response.status_code == 409, response.text
    assert _snapshot(inventory_api) == before
    assert _stock(client) == (10 if first_kind == "RELEASE" else 6)


@pytest.mark.parametrize("kind", ["ADJUST", "RESERVE", "RELEASE", "CONSUME"])
def test_identical_normalized_command_retries_return_original_without_duplicate_rows(
    inventory_api: InventoryAPI, kind: str
) -> None:
    client = inventory_api.client()
    if kind in {"RELEASE", "CONSUME"}:
        _reserve(client)
    elif kind == "RESERVE":
        _record(client, 3001)
    payload = _movement_payload(3003, kind=kind, quantity=4, note="  Repuesto   procesado  ")
    if kind != "ADJUST":
        payload["order_id"] = ORDER
    if kind in {"RELEASE", "CONSUME"}:
        payload["reference_movement_id"] = _id(3002)
    first = client.post(MOVEMENTS, json=payload)
    assert first.status_code == 201, first.text
    before = _snapshot(inventory_api)
    stock_before = _stock(client)
    retry_payload = dict(payload, note="Repuesto procesado")
    retry_payload.setdefault("order_id", None)
    retry_payload.setdefault("reference_movement_id", None)

    for _ in range(2):
        retry = client.post(MOVEMENTS, json=retry_payload)
        assert retry.status_code == 201, retry.text
        assert retry.json() == first.json()
    assert _snapshot(inventory_api) == before
    assert _stock(client) == stock_before


def test_reservation_retry_is_idempotent_even_after_it_was_consumed(
    inventory_api: InventoryAPI,
) -> None:
    client = inventory_api.client()
    reservation = _reserve(client)
    _record(
        client,
        3003,
        kind="CONSUME",
        quantity=4,
        order_id=ORDER,
        reference_movement_id=reservation["movement_id"],
    )
    before = _snapshot(inventory_api)

    retry = client.post(
        MOVEMENTS, json=_movement_payload(3002, kind="RESERVE", quantity=4, order_id=ORDER)
    )

    assert retry.status_code == 201, retry.text
    assert retry.json() == reservation
    assert _snapshot(inventory_api) == before
    assert _stock(client) == 6


@pytest.mark.parametrize(
    "changes",
    [
        {"product_id": SECOND_PRODUCT},
        {"kind": "ADJUST"},
        {"quantity": 3},
        {"order_id": SECOND_ORDER},
        {"note": "Changed note"},
    ],
)
def test_reusing_movement_identifier_with_a_different_command_is_conflict(
    inventory_api: InventoryAPI, changes: dict[str, object]
) -> None:
    client = inventory_api.client()
    _reserve(client)
    before = _snapshot(inventory_api)
    payload = _movement_payload(3002, kind="RESERVE", quantity=4, order_id=ORDER)
    payload.update(changes)

    response = client.post(MOVEMENTS, json=payload)

    assert response.status_code == 409, response.text
    assert _snapshot(inventory_api) == before
    assert _stock(client) == 6


def test_reusing_movement_identifier_with_a_different_reservation_is_conflict(
    inventory_api: InventoryAPI,
) -> None:
    client = inventory_api.client()
    _reserve(client)
    second = _record(client, 3003, kind="RESERVE", quantity=4, order_id=ORDER)
    payload = _movement_payload(
        3004, kind="RELEASE", quantity=4, order_id=ORDER, reference_movement_id=_id(3002)
    )
    first = client.post(MOVEMENTS, json=payload)
    assert first.status_code == 201, first.text
    before = _snapshot(inventory_api)

    response = client.post(
        MOVEMENTS, json=dict(payload, reference_movement_id=second["movement_id"])
    )

    assert response.status_code == 409, response.text
    assert _snapshot(inventory_api) == before
    assert _stock(client) == 6


def test_reusing_movement_identifier_from_another_actor_is_conflict(
    inventory_api: InventoryAPI,
) -> None:
    client = inventory_api.client()
    _record(client, 3001)
    before = _snapshot(inventory_api)
    other = inventory_api.client(user_id="second-writer")

    response = other.post(MOVEMENTS, json=_movement_payload(3001))

    assert response.status_code == 409, response.text
    assert _snapshot(inventory_api) == before
    assert _stock(client) == 10


def test_reusing_another_tenants_movement_identifier_does_not_leak_or_modify_ledger(
    inventory_api: InventoryAPI,
) -> None:
    foreign = inventory_api.client(user_id="foreign", organization_id="org-2", location_id="loc-x")
    _record(foreign, 3001, product_id=FOREIGN_PRODUCT)
    before = _snapshot(inventory_api)
    client = inventory_api.client()

    response = client.post(MOVEMENTS, json=_movement_payload(3001))

    assert response.status_code == 409, response.text
    assert _snapshot(inventory_api) == before
    assert FOREIGN_PRODUCT not in response.text
    assert "org-2" not in response.text
    assert _stock(client) == 0
    assert _stock(foreign, FOREIGN_PRODUCT) == 10


def test_failed_consume_companion_append_rolls_back_both_rows_and_can_retry(
    inventory_api: InventoryAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cycling_workshop.inventory.repository import SqlAlchemyInventoryRepository

    client = inventory_api.client()
    _reserve(client)
    before = _snapshot(inventory_api)
    payload = _movement_payload(
        3003, kind="CONSUME", quantity=4, order_id=ORDER, reference_movement_id=_id(3002)
    )
    original_record = SqlAlchemyInventoryRepository.record

    def fail_physical_issue(repository, movement):
        if movement.kind == "ADJUST" and movement.quantity == -4:
            # Flush the pending CONSUME first, then simulate a failed physical
            # issue. The transaction must undo even a flushed finalization.
            repository._session.flush()
            raise RuntimeError("simulated physical issue write failure")
        return original_record(repository, movement)

    with monkeypatch.context() as patch:
        patch.setattr(SqlAlchemyInventoryRepository, "record", fail_physical_issue)
        with pytest.raises(RuntimeError, match="simulated physical issue write failure"):
            client.post(MOVEMENTS, json=payload)

    assert _snapshot(inventory_api) == before
    assert _stock(client) == 6
    retry = client.post(MOVEMENTS, json=payload)
    assert retry.status_code == 201, retry.text
    assert len(inventory_api.ledger()) == 4
    assert _stock(client) == 6


def test_product_listing_defaults_to_100_and_accepts_maximum_200(
    inventory_api: InventoryAPI,
) -> None:
    with inventory_api.factory() as session:
        session.add_all(
            [
                ProductRecord(
                    id=_id(10000 + number),
                    organization_id="org-1",
                    location_id="loc-1",
                    sku=f"BULK-{number:03d}",
                    name=f"Bulk product {number:03d}",
                    unit="pieza",
                    created_at=NOW,
                    updated_at=NOW,
                    version=1,
                )
                for number in range(201)
            ]
        )
        session.commit()
    client = inventory_api.client()

    default = client.get(PRODUCTS, params={"location_id": "loc-1"})
    maximum = client.get(PRODUCTS, params={"location_id": "loc-1", "limit": 200})
    remainder = client.get(PRODUCTS, params={"location_id": "loc-1", "offset": 200})

    assert default.status_code == maximum.status_code == remainder.status_code == 200
    assert len(default.json()) == 100
    assert len(maximum.json()) == 200
    assert len(remainder.json()) == 3
    assert default.json() == maximum.json()[:100]
    assert len({row["product_id"] for row in maximum.json() + remainder.json()}) == 203


def test_schema_accepts_product_and_note_length_boundaries(inventory_api: InventoryAPI) -> None:
    client = inventory_api.client()
    product = client.post(
        PRODUCTS, json=_product_payload(sku="s" * 80, name="n" * 200, unit="u" * 30)
    )
    assert product.status_code == 201, product.text

    movement = client.post(MOVEMENTS, json=_movement_payload(3001, note="n" * 2000))

    assert movement.status_code == 201, movement.text
    assert movement.json()["note"] == "n" * 2000


def test_negative_adjustment_retry_normalizes_blank_notes_without_reapplying_stock(
    inventory_api: InventoryAPI,
) -> None:
    client = inventory_api.client()
    first = _record(client, 3001, quantity=-3)
    before = _snapshot(inventory_api)

    for note in [None, "", "  \n  "]:
        retry = client.post(MOVEMENTS, json=_movement_payload(3001, quantity=-3, note=note))
        assert retry.status_code == 201, retry.text
        assert retry.json() == first
    assert _snapshot(inventory_api) == before
    assert _stock(client) == -3


def test_product_rejects_sku_that_exceeds_limit_after_unicode_normalization(
    inventory_api: InventoryAPI,
) -> None:
    response = inventory_api.client().post(
        PRODUCTS, json={"location_id": "loc-1", "sku": "ß" * 41, "name": "Part"}
    )
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("field", ["sku", "name", "unit"])
def test_product_rejects_nul_text(inventory_api: InventoryAPI, field: str) -> None:
    payload = {"location_id": "loc-1", "sku": "valid", "name": "Part", "unit": "piece"}
    payload[field] = "invalid\x00text"
    response = inventory_api.client().post(PRODUCTS, json=payload)
    assert response.status_code == 422, response.text


def test_movement_rejects_nul_note(inventory_api: InventoryAPI) -> None:
    response = inventory_api.client().post(
        MOVEMENTS, json=_movement_payload(4001, note="invalid\x00text")
    )
    assert response.status_code == 422, response.text


def test_product_list_rejects_out_of_range_offset(inventory_api: InventoryAPI) -> None:
    response = inventory_api.client().get(
        PRODUCTS, params={"location_id": "loc-1", "offset": 2**63}
    )
    assert response.status_code == 422, response.text


def test_inventory_read_identifiers_reject_nul(inventory_api: InventoryAPI) -> None:
    client = inventory_api.client()
    listed = client.get(PRODUCTS, params={"location_id": "loc-1\x00"})
    assert listed.status_code == 422, listed.text
    stock = client.get(f"{PRODUCTS}/invalid%00product/stock")
    assert stock.status_code == 422, stock.text
