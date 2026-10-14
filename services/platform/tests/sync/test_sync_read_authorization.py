"""Read-side sync authorization with synthetic records and persisted principals."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from cycling_workshop.app import create_app
from cycling_workshop.db.base import Base
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.settings import Settings
from cycling_workshop.sync.models import ChangeRecord
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_client(capabilities: set[str], *, location_id: str | None = "loc-1") -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                OrganizationRecord(id="org-1", name="Synthetic organization"),
                OrganizationRecord(id="org-2", name="Other synthetic organization"),
            ]
        )
        session.flush()
        session.add_all(
            [
                LocationRecord(id="loc-1", organization_id="org-1", name="First"),
                LocationRecord(id="loc-2", organization_id="org-1", name="Second"),
                LocationRecord(id="loc-3", organization_id="org-2", name="Other tenant"),
            ]
        )
        session.flush()
        session.add(
            UserRecord(
                id="reader-1",
                organization_id="org-1",
                location_id=location_id,
                username="synthetic-reader",
                display_name="Synthetic reader",
                password_hash="unused-in-token-tests",
                capabilities=sorted(capabilities),
                is_active=True,
                session_version=1,
            )
        )
        session.commit()
    app = create_app(
        settings=Settings(
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
            log_level="WARNING",
            auth_secret="test-secret-that-is-long-enough-for-tests",
        ),
        session_factory=factory,
    )
    token = app.state.session_tokens.issue(
        Principal(
            user_id="reader-1",
            organization_id="org-1",
            location_id=location_id,
            capabilities=frozenset(capabilities),
        )
    )
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def add_change(
    client: TestClient,
    entity_type: str,
    *,
    location_id: str = "loc-1",
    organization_id: str = "org-1",
) -> int:
    with client.app.state.session_factory() as session:
        record = ChangeRecord(
            organization_id=organization_id,
            location_id=location_id,
            entity_type=entity_type,
            entity_id=f"synthetic-{entity_type}",
            operation="create",
            entity_version=1,
            occurred_at=datetime(2026, 10, 14, tzinfo=UTC),
            payload={"synthetic": True},
        )
        session.add(record)
        session.commit()
        return int(record.cursor)


def test_omitted_location_is_clamped_to_persisted_principal_scope() -> None:
    client = build_client({"sync.pull", "customers.read"})
    local_cursor = add_change(client, "customer")
    add_change(client, "customer", location_id="loc-2")
    add_change(client, "customer", location_id="loc-3", organization_id="org-2")

    response = client.get("/api/v1/sync/changes")

    assert response.status_code == 200
    page = response.json()
    assert [item["location_id"] for item in page["items"]] == ["loc-1"]
    assert page["next_cursor"] == local_cursor
    assert page["has_more"] is False


def test_explicit_foreign_location_is_denied() -> None:
    client = build_client({"*"})
    add_change(client, "customer", location_id="loc-2")

    response = client.get("/api/v1/sync/changes", params={"location_id": "loc-2"})

    assert response.status_code == 403
    assert "synthetic" not in response.text


@pytest.mark.parametrize(
    ("capabilities", "expected"),
    [
        ({"sync.pull"}, []),
        ({"sync.pull", "customers.read"}, ["customer"]),
        ({"sync.pull", "bicycles.read"}, ["bicycle"]),
        ({"sync.pull", "orders.read"}, ["service_order"]),
        ({"sync.pull", "customers.write", "bicycles.write", "orders.write"}, []),
        ({"sync.pull", "customers.read", "orders.read"}, ["customer", "service_order"]),
        ({"*"}, ["customer", "bicycle", "service_order"]),
        ({"sync.pull", "future.read"}, []),
    ],
)
def test_pull_requires_each_entity_read_capability_and_denies_unknown_types(
    capabilities: set[str], expected: list[str]
) -> None:
    client = build_client(capabilities)
    for entity_type in ("customer", "bicycle", "service_order", "future"):
        add_change(client, entity_type)

    response = client.get("/api/v1/sync/changes", params={"location_id": "loc-1"})

    assert response.status_code == 200
    page = response.json()
    assert [item["entity_type"] for item in page["items"]] == expected
    assert page["next_cursor"] == (page["items"][-1]["cursor"] if expected else 0)
    assert page["has_more"] is False


def test_entity_read_permission_does_not_replace_sync_pull_permission() -> None:
    client = build_client({"customers.read"})
    add_change(client, "customer")
    assert client.get("/api/v1/sync/changes").status_code == 403


def test_unscoped_account_can_read_all_its_locations_or_request_one() -> None:
    client = build_client({"sync.pull", "customers.read"}, location_id=None)
    add_change(client, "customer")
    add_change(client, "customer", location_id="loc-2")
    add_change(client, "customer", location_id="loc-3", organization_id="org-2")

    all_locations = client.get("/api/v1/sync/changes").json()
    one_location = client.get("/api/v1/sync/changes", params={"location_id": "loc-2"}).json()

    assert [item["location_id"] for item in all_locations["items"]] == ["loc-1", "loc-2"]
    assert [item["location_id"] for item in one_location["items"]] == ["loc-2"]


def test_filtering_precedes_limit_and_cursor_lookahead() -> None:
    client = build_client({"sync.pull", "customers.read"})
    add_change(client, "service_order")
    first = add_change(client, "customer")
    add_change(client, "customer", location_id="loc-2")
    add_change(client, "future")
    second = add_change(client, "customer")
    add_change(client, "bicycle")
    third = add_change(client, "customer")
    add_change(client, "service_order")
    add_change(client, "customer", location_id="loc-3", organization_id="org-2")

    cursor = 0
    for expected, has_more in ((first, True), (second, True), (third, False)):
        response = client.get("/api/v1/sync/changes", params={"cursor": cursor, "limit": 1})
        assert response.status_code == 200
        page = response.json()
        assert [item["cursor"] for item in page["items"]] == [expected]
        assert page["next_cursor"] == expected
        assert page["has_more"] is has_more
        cursor = page["next_cursor"]

    empty = client.get("/api/v1/sync/changes", params={"cursor": cursor, "limit": 1}).json()
    assert empty == {"items": [], "next_cursor": third, "has_more": False}


def test_hidden_only_tail_does_not_advance_supplied_cursor_or_has_more() -> None:
    client = build_client({"sync.pull", "customers.read"})
    cursor = add_change(client, "customer")
    add_change(client, "service_order")
    add_change(client, "future")
    add_change(client, "customer", location_id="loc-2")

    page = client.get("/api/v1/sync/changes", params={"cursor": cursor, "limit": 1}).json()

    assert page == {"items": [], "next_cursor": cursor, "has_more": False}


def test_persisted_read_revocation_takes_effect_for_existing_token() -> None:
    client = build_client({"sync.pull", "customers.read", "orders.read"})
    add_change(client, "customer")
    add_change(client, "service_order")
    with client.app.state.session_factory() as session:
        user = session.get(UserRecord, "reader-1")
        assert user is not None
        user.capabilities = ["sync.pull", "customers.read"]
        session.commit()

    page = client.get("/api/v1/sync/changes").json()

    assert [item["entity_type"] for item in page["items"]] == ["customer"]


def test_persisted_grant_does_not_expand_existing_token() -> None:
    client = build_client({"sync.pull", "customers.read"})
    add_change(client, "customer")
    add_change(client, "service_order")
    with client.app.state.session_factory() as session:
        user = session.get(UserRecord, "reader-1")
        assert user is not None
        user.capabilities = ["sync.pull", "customers.read", "orders.read"]
        session.commit()

    page = client.get("/api/v1/sync/changes").json()

    assert [item["entity_type"] for item in page["items"]] == ["customer"]
