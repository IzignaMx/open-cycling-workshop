"""Functional stale-dependency regression; PostgreSQL tests separately prove waits."""

import pytest
from cycling_workshop.identity.dependencies import principal_from_request
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.models import ChangeRecord
from sqlalchemy import func, select

from services.platform.tests.bicycles.test_bicycle_api import FULL_CAPABILITIES, build_client


@pytest.mark.parametrize("kind", ["customer", "bicycle", "order", "transition", "push"])
@pytest.mark.parametrize("revocation", ["session", "inactive", "grants", "location"])
def test_writers_revalidate_stale_dependency_before_effects(kind, revocation) -> None:
    client = build_client()
    created = client.post(
        "/api/v1/service-orders",
        json={
            "customer_id": "customer-1",
            "location_id": "loc-1",
            "reported_problem": "Noise",
        },
    ).json()
    # Request dependency already completed while an administration writer ran.
    stale = Principal(
        user_id="user-1",
        organization_id="org-1",
        location_id="loc-1",
        capabilities=frozenset(FULL_CAPABILITIES),
    )
    client.app.dependency_overrides[principal_from_request] = lambda: stale
    with client.app.state.session_factory() as session:
        actor = session.get(UserRecord, "user-1")
        if revocation == "session":
            actor.session_version += 1
        elif revocation == "inactive":
            actor.is_active = False
        elif revocation == "grants":
            actor.capabilities = ["sync.push"]
        else:
            actor.location_id = "loc-other"
        session.commit()
    cases = {
        "customer": ("/api/v1/customers", {"location_id": "loc-1", "display_name": "Stale"}),
        "bicycle": (
            "/api/v1/bicycles",
            {"location_id": "loc-1", "customer_id": "customer-1", "brand": "Test"},
        ),
        "order": (
            "/api/v1/service-orders",
            {"location_id": "loc-1", "customer_id": "customer-1", "reported_problem": "Noise"},
        ),
        "transition": (
            f"/api/v1/service-orders/{created['order_id']}/transitions",
            {"action": "start_diagnosis"},
        ),
        "push": (
            "/api/v1/sync/mutations",
            {
                "mutations": [
                    {
                        "mutation_id": new_id(),
                        "entity_type": "customer",
                        "entity_id": new_id(),
                        "operation": "create",
                        "organization_id": "org-1",
                        "location_id": "loc-1",
                        "base_version": None,
                        "occurred_at": "2026-10-14T00:00:00Z",
                        "payload": {"display_name": "Stale"},
                    }
                ]
            },
        ),
    }
    path, payload = cases[kind]
    response = client.post(path, json=payload)
    assert response.status_code == (403 if revocation == "grants" else 401)
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ChangeRecord)) == 1
