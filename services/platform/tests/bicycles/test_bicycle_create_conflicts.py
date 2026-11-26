"""REST create conflicts preserve the original record and transactional effects."""

import pytest
from cycling_workshop.bicycles.models import BicycleRecord
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.models import ChangeRecord, MutationReceiptRecord
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from services.platform.tests.bicycles.test_bicycle_api import (
    FULL_CAPABILITIES,
    NOW,
    _create_payload,
    build_client,
)


@pytest.fixture
def client():
    client = build_client()
    yield client
    client.close()
    client.app.state.session_factory.kw["bind"].dispose()


def _snapshot(client):
    with client.app.state.session_factory() as session:
        return {
            model.__tablename__: [
                dict(row)
                for row in session.execute(
                    select(model.__table__).order_by(*model.__table__.primary_key)
                ).mappings()
            ]
            for model in (BicycleRecord, ChangeRecord, OutboxRecord, MutationReceiptRecord)
        }


def _assert_conflict(response):
    assert response.status_code == 409
    assert response.headers["cache-control"] == "no-store"
    error = response.json()["error"]
    assert error == {
        "code": "bicycle_conflict",
        "message": "bicycle identifier already exists",
        "details": {},
        "request_id": error["request_id"],
    }
    assert isinstance(error["request_id"], str) and error["request_id"]


@pytest.mark.parametrize("changed", [False, True])
def test_duplicate_bicycle_create_is_conflict_without_effects(client, changed):
    bicycle_id = new_id()
    payload = _create_payload(bicycle_id=bicycle_id)
    first = client.post("/api/v1/bicycles", json=payload)
    assert first.status_code == 201
    before = _snapshot(client)
    if changed:
        payload.update(brand="Replacement brand", notes="replacement must not persist")

    duplicate = client.post("/api/v1/bicycles", json=payload)

    _assert_conflict(duplicate)
    assert _snapshot(client) == before
    assert client.get(f"/api/v1/bicycles/{bicycle_id}").json() == first.json()
    subsequent = client.post("/api/v1/bicycles", json=_create_payload())
    assert subsequent.status_code == 201


@pytest.mark.parametrize("foreign_tenant", [False, True])
def test_duplicate_bicycle_id_does_not_reveal_foreign_scope(client, foreign_tenant):
    bicycle_id = new_id()
    assert (
        client.post(
            "/api/v1/bicycles",
            json=_create_payload(bicycle_id=bicycle_id, notes="private original"),
        ).status_code
        == 201
    )
    organization_id = "org-2" if foreign_tenant else "org-1"
    with client.app.state.session_factory.begin() as session:
        if foreign_tenant:
            session.add(OrganizationRecord(id=organization_id, name="Other"))
        session.add(LocationRecord(id="loc-2", organization_id=organization_id, name="Other"))
        session.add(
            CustomerRecord(
                id="customer-2",
                organization_id=organization_id,
                location_id="loc-2",
                display_name="Other customer",
                created_at=NOW,
                updated_at=NOW,
                version=1,
            )
        )
        session.add(
            UserRecord(
                id="user-2",
                organization_id=organization_id,
                location_id="loc-2",
                username="other",
                display_name="Other",
                password_hash="unused",
                capabilities=FULL_CAPABILITIES,
                is_active=True,
                session_version=1,
            )
        )
    token = client.app.state.session_tokens.issue(
        Principal("user-2", organization_id, "loc-2", frozenset(FULL_CAPABILITIES))
    )
    before = _snapshot(client)

    response = client.post(
        "/api/v1/bicycles",
        headers={"Authorization": f"Bearer {token}"},
        json=_create_payload(bicycle_id=bicycle_id, location_id="loc-2", customer_id="customer-2"),
    )

    _assert_conflict(response)
    assert _snapshot(client) == before
    assert "private original" not in response.text


def test_duplicate_bicycle_id_does_not_bypass_authorization(client):
    bicycle_id = new_id()
    assert (
        client.post("/api/v1/bicycles", json=_create_payload(bicycle_id=bicycle_id)).status_code
        == 201
    )
    before = _snapshot(client)

    forbidden = client.post(
        "/api/v1/bicycles", json=_create_payload(bicycle_id=bicycle_id, location_id="loc-2")
    )
    assert forbidden.status_code == 403
    token = client.app.state.session_tokens.issue(
        Principal("user-1", "org-1", "loc-1", frozenset({"bicycles.read"}))
    )
    missing_capability = client.post(
        "/api/v1/bicycles",
        headers={"Authorization": f"Bearer {token}"},
        json=_create_payload(bicycle_id=bicycle_id),
    )
    assert missing_capability.status_code == 403
    assert _snapshot(client) == before


@pytest.mark.parametrize("stage", ["append_change", "commit_admitted"])
def test_bicycle_create_database_failure_rolls_back_insert_and_effects(client, monkeypatch, stage):
    from cycling_workshop.bicycles import router

    before = _snapshot(client)

    def fail(*args, **kwargs):
        raise SQLAlchemyError("synthetic database failure with private contents")

    monkeypatch.setattr(router, stage, fail)
    response = client.post("/api/v1/bicycles", json=_create_payload(bicycle_id=new_id()))

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_command_failed"
    assert "private contents" not in response.text
    assert _snapshot(client) == before
