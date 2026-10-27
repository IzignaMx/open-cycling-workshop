"""Tiny enrollment/legacy-ingress races with observed PostgreSQL row-lock waits.

Every case uses the real admission and command paths on an isolated migrated
schema. This proves serialization, not maximum capacity or network cancellation.
"""

from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import replace
from threading import Event

import pytest
from cycling_workshop.api.errors import ApiError
from cycling_workshop.identity.cutover import WriteAdmission, commit_admitted
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.inventory.models import InventoryMovementRecord
from cycling_workshop.inventory.schemas import MovementCreateRequest
from cycling_workshop.inventory.service import record_movement
from cycling_workshop.quotes.models import QuoteLineageRecord
from cycling_workshop.quotes.service import QuoteServiceError
from cycling_workshop.service_orders.models import ServiceOrderRecord
from cycling_workshop.service_orders.router import transition_service_order
from cycling_workshop.service_orders.schemas import OrderTransitionRequest
from cycling_workshop.sync.domain import MutationEnvelope, SyncApplicationContext, SyncConflict
from cycling_workshop.sync.models import MutationReceiptRecord
from cycling_workshop.sync.proof import envelope_digest
from cycling_workshop.sync.service import SyncService
from cycling_workshop.sync.writes import lock_writer
from fastapi import HTTPException
from sqlalchemy import event, func, select, update
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_application_service import actors as actors
from test_quote_application_service import execute, totals
from test_quote_application_service_postgres import postgres_identity as postgres_identity
from test_quote_repository import creation
from test_quote_repository import database as database
from test_quote_service_races_postgres import _observe_organization_wait
from test_quote_storage import NOW, uid

pytestmark = pytest.mark.parametrize("identity_migration_database", ["postgres"], indirect=True)
ORDER_ID = uid(402)


def _legacy_command(session, principal, ingress):
    admission = WriteAdmission.for_fixtures(1, enabled=True)
    if ingress == "http_transition":
        return transition_service_order(
            ORDER_ID, OrderTransitionRequest(action="authorize"), principal, session, admission
        )
    if ingress == "inventory_adjust":
        result = record_movement(
            session,
            principal,
            MovementCreateRequest(
                movement_id=uid(400),
                product_id="product-a",
                order_id=ORDER_ID,
                kind="ADJUST",
                quantity=1,
            ),
            admission=admission,
        )
        commit_admitted(session, principal, admission)
        return result
    assert ingress == "sync_transition"
    principal = lock_writer(session, principal, admission)
    mutation = MutationEnvelope(
        mutation_id=uid(401),
        entity_type="service_order",
        entity_id=ORDER_ID,
        operation="update",
        organization_id="a",
        location_id="location-a",
        base_version=1,
        occurred_at=NOW,
        payload={"transition": {"action": "authorize"}},
    )
    result = SyncService(session).apply(
        mutation,
        context=SyncApplicationContext(
            actor_id=principal.user_id,
            write_protocol=1,
            canonical_digest=envelope_digest(mutation),
            admitted_session_id=id(session),
        ),
    )
    commit_admitted(session, principal, admission)
    return result


@pytest.mark.parametrize("ingress", ["http_transition", "sync_transition", "inventory_adjust"])
@pytest.mark.parametrize("first", ["enrollment", "legacy"])
def test_enrollment_and_every_legacy_ingress_serialize(database, actors, ingress, first):
    grants = actors.capabilities | {"inventory.write", "sync.push"}
    principal = replace(actors, capabilities=frozenset(grants))
    with Session(database) as session:
        session.get(UserRecord, principal.user_id).capabilities = sorted(grants)
        session.execute(
            update(ServiceOrderRecord).where(ServiceOrderRecord.id == "order-a").values(id=ORDER_ID)
        )
        session.commit()

    first_committing, second_connected, release_first = Event(), Event(), Event()
    pids = {}
    second_kind = "legacy" if first == "enrollment" else "enrollment"

    def participant(role, kind):
        with Session(database) as session:

            def connected(_session, transaction, connection):
                if role == "second" and not transaction.nested:
                    pids["second"] = connection.connection.driver_connection.info.backend_pid
                    second_connected.set()

            def before_commit(_session):
                if role == "first":
                    pids["first"] = (
                        session.connection().connection.driver_connection.info.backend_pid
                    )
                    first_committing.set()
                    assert release_first.wait(timeout=2.0), "first writer was not released"

            event.listen(session, "after_begin", connected)
            event.listen(session, "before_commit", before_commit)
            try:
                if kind == "enrollment":
                    return execute(session, principal, creation(order_id=ORDER_ID))
                return _legacy_command(session, principal, ingress)
            except (QuoteServiceError, ApiError, HTTPException, SyncConflict) as error:
                return error
            finally:
                event.remove(session, "after_begin", connected)
                event.remove(session, "before_commit", before_commit)

    executor = ThreadPoolExecutor(max_workers=2)
    futures = []
    try:
        winner = executor.submit(participant, "first", first)
        futures.append(winner)
        assert first_committing.wait(timeout=2.0), "first writer never reached commit"
        contender = executor.submit(participant, "second", second_kind)
        futures.append(contender)
        assert second_connected.wait(timeout=1.0), "contender never opened its session"
        _observe_organization_wait(database, pids["second"], pids["first"], contender)
    finally:
        release_first.set()
        _, unfinished = wait(futures, timeout=8.0)
        executor.shutdown(wait=False, cancel_futures=True)
        assert not unfinished, "ingress participants did not finish within the cleanup wait"

    assert not isinstance(winner.result(timeout=0), Exception)
    refused = contender.result(timeout=0)
    assert isinstance(refused, Exception)
    if first == "legacy":
        assert isinstance(refused, QuoteServiceError)
        assert refused.code == "quote_conflict"
        assert refused.outcome_unknown is False
    elif ingress == "sync_transition":
        assert isinstance(refused, SyncConflict)
        assert refused.error_code == "sync_conflict"
    else:
        assert isinstance(refused, (ApiError, HTTPException))
        assert refused.status_code == 409

    with Session(database) as session:
        lineage_count = session.scalar(select(func.count()).select_from(QuoteLineageRecord))
        movement_count = session.scalar(select(func.count()).select_from(InventoryMovementRecord))
        receipt_count = session.scalar(select(func.count()).select_from(MutationReceiptRecord))
        order = session.get(ServiceOrderRecord, ORDER_ID)
        if first == "enrollment":
            assert lineage_count == 1
            assert movement_count == receipt_count == 0
            assert (order.state, order.version) == ("DIAGNOSIS", 1)
            assert totals(session) == (1, 0, 0, 1)
        else:
            assert lineage_count == 0
            assert movement_count == (1 if ingress == "inventory_adjust" else 0)
            assert receipt_count == (1 if ingress == "sync_transition" else 0)
            if ingress == "inventory_adjust":
                assert (order.state, order.version) == ("DIAGNOSIS", 1)
                assert totals(session) == (0, 0, 0, 0)
            else:
                assert (order.state, order.version) == ("AUTHORIZED", 2)
                assert totals(session) == (0, 1, 1, 1)
