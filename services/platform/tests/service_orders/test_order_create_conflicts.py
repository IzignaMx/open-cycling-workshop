"""REST identifier conflicts are permanent refusals, not failed DB retries."""

import pytest
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.service_orders import router as order_router
from cycling_workshop.service_orders.models import ServiceOrderEventRecord, ServiceOrderRecord
from cycling_workshop.sync.models import ChangeRecord, MutationReceiptRecord
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import StaticPool

from services.platform.tests.bicycles.test_bicycle_api import FULL_CAPABILITIES, NOW, build_client
from services.platform.tests.service_orders.test_service_order_api import _order_payload

ORDER_ID = "00000000-0000-7000-8000-000000000123"
FRESH_ID = "00000000-0000-7000-8000-000000000124"


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    client = build_client(engine=engine)
    try:
        yield client
    finally:
        client.close()
        engine.dispose()


def _snapshot(client):
    with client.app.state.session_factory() as session:
        return {
            model.__tablename__: session.execute(
                select(model.__table__).order_by(*model.__table__.primary_key)
            ).all()
            for model in (
                ServiceOrderRecord,
                ServiceOrderEventRecord,
                ChangeRecord,
                OutboxRecord,
                MutationReceiptRecord,
            )
        }


def _assert_conflict(response):
    assert response.status_code == 409
    assert response.headers["cache-control"] == "no-store"
    error = response.json()["error"]
    assert error == {
        "code": "order_conflict",
        "message": "order identifier already exists",
        "details": {},
        "request_id": error["request_id"],
    }
    assert isinstance(error["request_id"], str) and error["request_id"]


@pytest.mark.parametrize("changed_payload", [False, True])
@pytest.mark.parametrize("has_history", [False, True])
def test_duplicate_order_id_preserves_order_and_all_effects(client, changed_payload, has_history):
    payload = _order_payload(order_id=ORDER_ID)
    created = client.post("/api/v1/service-orders", json=payload)
    assert created.status_code == 201
    if has_history:
        assert (
            client.post(
                f"/api/v1/service-orders/{ORDER_ID}/transitions",
                json={"action": "start_diagnosis", "note": "Synthetic existing history"},
            ).status_code
            == 200
        )
    before = _snapshot(client)
    existing = client.get(f"/api/v1/service-orders/{ORDER_ID}").json()
    assert len(before["service_orders"]) == 1
    assert len(before["sync_changes"]) == 1 + int(has_history)
    assert len(before["outbox_events"]) == 1 + int(has_history)
    if changed_payload:
        payload["reported_problem"] = "Replacement must never overwrite original"

    refused = client.post("/api/v1/service-orders", json=payload)

    _assert_conflict(refused)
    assert _snapshot(client) == before
    assert client.get(f"/api/v1/service-orders/{ORDER_ID}").json() == existing
    # A new command remains usable after the conflict; no leaked failed transaction.
    payload["order_id"] = FRESH_ID
    assert client.post("/api/v1/service-orders", json=payload).status_code == 201


@pytest.mark.parametrize("foreign_tenant", [False, True])
def test_occupied_order_id_outside_actor_scope_is_generic_conflict(client, foreign_tenant):
    assert (
        client.post("/api/v1/service-orders", json=_order_payload(order_id=ORDER_ID)).status_code
        == 201
    )
    organization = "org-2" if foreign_tenant else "org-1"
    with client.app.state.session_factory() as session:
        if foreign_tenant:
            session.add(OrganizationRecord(id=organization, name="Other synthetic tenant"))
        session.add(LocationRecord(id="loc-2", organization_id=organization, name="Other scope"))
        session.add(
            UserRecord(
                id="user-2",
                organization_id=organization,
                location_id="loc-2",
                username="other-writer",
                display_name="Other writer",
                password_hash="unused-in-token-tests",
                capabilities=FULL_CAPABILITIES,
                is_active=True,
                session_version=1,
            )
        )
        session.add(
            CustomerRecord(
                id="customer-2",
                organization_id=organization,
                location_id="loc-2",
                display_name="Other customer",
                created_at=NOW,
                updated_at=NOW,
                version=1,
            )
        )
        session.commit()
    token = client.app.state.session_tokens.issue(
        Principal(
            user_id="user-2",
            organization_id=organization,
            location_id="loc-2",
            capabilities=frozenset(FULL_CAPABILITIES),
        )
    )
    client.headers["Authorization"] = f"Bearer {token}"
    before = _snapshot(client)
    refused = client.post(
        "/api/v1/service-orders",
        json=_order_payload(order_id=ORDER_ID, customer_id="customer-2", location_id="loc-2"),
    )
    _assert_conflict(refused)
    assert _snapshot(client) == before
    assert "org-1" not in refused.text and "loc-1" not in refused.text


@pytest.mark.parametrize("occupied", [False, True])
@pytest.mark.parametrize("denied_scope", ["capability", "location"])
def test_order_create_authority_precedes_identifier_conflict(client, occupied, denied_scope):
    assert (
        client.post("/api/v1/service-orders", json=_order_payload(order_id=ORDER_ID)).status_code
        == 201
    )
    if denied_scope == "capability":
        reader_token = client.app.state.session_tokens.issue(
            Principal(
                user_id="user-1",
                organization_id="org-1",
                location_id="loc-1",
                capabilities=frozenset({"orders.read"}),
            )
        )
        client.headers["Authorization"] = f"Bearer {reader_token}"
    before = _snapshot(client)
    refused = client.post(
        "/api/v1/service-orders",
        json=_order_payload(
            order_id=ORDER_ID if occupied else FRESH_ID,
            location_id="loc-2" if denied_scope == "location" else "loc-1",
        ),
    )
    assert refused.status_code == 403
    assert refused.json() == {
        "detail": "location scope denied" if denied_scope == "location" else "capability denied"
    }
    assert _snapshot(client) == before


@pytest.mark.parametrize("failure_stage", ["append_change", "commit_admitted"])
def test_other_database_failures_roll_back_order_and_effects(client, monkeypatch, failure_stage):
    assert (
        client.post("/api/v1/service-orders", json=_order_payload(order_id=ORDER_ID)).status_code
        == 201
    )
    before = _snapshot(client)
    original_append = order_router.append_change

    def fail(*args, **kwargs):
        if failure_stage == "append_change":
            original_append(*args, **kwargs)
        raise SQLAlchemyError("synthetic failure must not be public")

    with monkeypatch.context() as patch:
        patch.setattr(order_router, failure_stage, fail)
        refused = client.post("/api/v1/service-orders", json=_order_payload(order_id=FRESH_ID))
    assert refused.status_code == 503
    assert refused.json()["error"]["code"] == "database_command_failed"
    assert "synthetic failure" not in refused.text
    assert _snapshot(client) == before
    assert (
        client.post("/api/v1/service-orders", json=_order_payload(order_id=FRESH_ID)).status_code
        == 201
    )
