"""Functional stale-dependency regression; PostgreSQL tests separately prove waits."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from cycling_workshop.identity.cutover import WriteAdmission
from cycling_workshop.identity.dependencies import principal_from_request
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.models import ChangeRecord
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from services.platform.tests.bicycles.test_bicycle_api import (
    FULL_CAPABILITIES,
    _ensure_seed,
    build_client,
)


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
    stale = replace(stale, expires_at=datetime.now(UTC) + timedelta(hours=1))
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


GRANT_SETS = [
    frozenset(),
    frozenset({"*"}),
    frozenset({"customers.write"}),
    frozenset({"customers.read", "customers.write"}),
    frozenset({"*", "customers.write"}),
]


@pytest.fixture
def writer_matrix_factory() -> Iterator[sessionmaker[Session]]:
    # These direct lock_writer cases need the same fresh database as build_client,
    # but never use its HTTP app, client or bearer token.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        _ensure_seed(engine)
        yield sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        engine.dispose()


@pytest.mark.parametrize("token_grants", GRANT_SETS)
@pytest.mark.parametrize("initial_account_grants", GRANT_SETS)
@pytest.mark.parametrize("current_account_grants", GRANT_SETS)
def test_waiting_writer_preserves_literal_intersection_matrix(
    token_grants, initial_account_grants, current_account_grants, writer_matrix_factory
) -> None:
    from cycling_workshop.sync.writes import lock_writer

    # The ordinary HTTP dependency already narrowed token ∩ persisted account.
    # An account change during the lock wait must not resolve wildcard semantics
    # differently or restore grants removed by that first literal intersection.
    incoming = Principal(
        user_id="user-1",
        organization_id="org-1",
        location_id="loc-1",
        capabilities=token_grants.intersection(initial_account_grants),
    )
    with writer_matrix_factory() as session:
        actor = session.get(UserRecord, "user-1")
        actor.capabilities = sorted(current_account_grants)
        session.commit()
        refreshed = lock_writer(session, incoming, WriteAdmission.for_fixtures())
        assert refreshed.capabilities == incoming.capabilities.intersection(current_account_grants)


def test_writer_admission_cannot_be_issued_inside_releasable_savepoint():
    from cycling_workshop.sync.writes import lock_writer

    client = build_client()
    with client.app.state.session_factory() as session:
        with session.begin_nested(), pytest.raises(RuntimeError, match="precede item savepoints"):
            lock_writer(
                session,
                Principal("user-1", "org-1", "loc-1", frozenset(FULL_CAPABILITIES)),
                WriteAdmission.for_fixtures(),
            )
        assert "ocwp_write_admission" not in session.info
