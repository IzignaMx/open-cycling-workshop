"""Finite legacy ingress refusals; SQLite is not concurrency evidence."""

from dataclasses import replace

import pytest
from cycling_workshop.api.errors import ApiError
from cycling_workshop.identity.cutover import WriteAdmission
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.inventory.domain import MovementKind
from cycling_workshop.inventory.schemas import MovementCreateRequest
from cycling_workshop.inventory.service import record_movement
from cycling_workshop.service_orders.models import ServiceOrderRecord
from cycling_workshop.service_orders.router import transition_service_order
from cycling_workshop.service_orders.schemas import OrderTransitionRequest
from cycling_workshop.sync.domain import MutationEnvelope, SyncApplicationContext, SyncConflict
from cycling_workshop.sync.service import SyncService
from sqlalchemy import update
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_application_service import actors as actors
from test_quote_application_service import execute, totals
from test_quote_repository import creation
from test_quote_repository import database as database
from test_quote_storage import NOW, uid

pytestmark = pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)

ACTIONS = [
    ("INTAKE", "start_diagnosis"),
    ("DIAGNOSIS", "authorize"),
    ("DIAGNOSIS", "reject"),
    ("AUTHORIZED", "start_work"),
    ("IN_PROGRESS", "request_parts"),
    ("WAITING_FOR_PARTS", "resume_work"),
    ("IN_PROGRESS", "mark_ready"),
    ("READY", "close"),
]


def enroll(database, actors, state="DIAGNOSIS"):
    with Session(database) as session:
        execute(session, actors, creation())
        session.execute(
            update(ServiceOrderRecord).where(ServiceOrderRecord.id == "order-a").values(state=state)
        )
        session.commit()


def mutation(action, *, mutation_id=None, version=1):
    return MutationEnvelope(
        mutation_id=mutation_id or uid(800),
        organization_id="a",
        location_id="location-a",
        entity_type="service_order",
        entity_id="order-a",
        operation="update",
        base_version=version,
        payload={"transition": {"action": action}},
        occurred_at=NOW,
    )


@pytest.mark.parametrize("state,action", ACTIONS)
@pytest.mark.parametrize("ingress", ["http", "sync"])
def test_managed_order_rejects_every_generic_progression(database, actors, state, action, ingress):
    enroll(database, actors, state)
    with Session(database) as session:
        before = totals(session)
        if ingress == "http":
            with pytest.raises(ApiError) as error:
                transition_service_order(
                    "order-a",
                    OrderTransitionRequest(action=action),
                    actors,
                    session,
                    WriteAdmission.for_fixtures(),
                )
            assert error.value.code == "quote_managed_order"
        else:
            with pytest.raises(SyncConflict) as error:
                SyncService.for_fixtures(session).apply(
                    mutation(action), context=SyncApplicationContext(actor_id="actor-a")
                )
            assert error.value.error_code == "sync_conflict"
            assert str(error.value) == "quote-managed order requires a supported quote command"
        assert totals(session) == before
        assert session.get(ServiceOrderRecord, "order-a").state == state


@pytest.mark.parametrize("ingress", ["http", "sync"])
def test_managed_order_legal_cancel_preserves_lineage_and_receipts(database, actors, ingress):
    enroll(database, actors)
    with Session(database) as session:
        if ingress == "http":
            transition_service_order(
                "order-a",
                OrderTransitionRequest(action="cancel"),
                actors,
                session,
                WriteAdmission.for_fixtures(),
            )
        else:
            service = SyncService.for_fixtures(session)
            context = SyncApplicationContext(actor_id="actor-a")
            first = service.apply(mutation("cancel"), context=context)
            assert service.apply(mutation("cancel"), context=context) == first
            session.commit()
        assert session.get(ServiceOrderRecord, "order-a").state == "CANCELLED"
        assert totals(session) == (1, 1, 1, 2)
        if ingress == "http":
            with pytest.raises(ApiError) as error:
                transition_service_order(
                    "order-a",
                    OrderTransitionRequest(action="authorize"),
                    actors,
                    session,
                    WriteAdmission.for_fixtures(),
                )
            assert error.value.code == "quote_managed_order"
        else:
            with pytest.raises(SyncConflict, match="quote-managed order"):
                service.apply(
                    mutation("authorize", mutation_id=uid(801), version=2), context=context
                )
        assert totals(session) == (1, 1, 1, 2)


@pytest.fixture
def inventory_actor(database, actors):
    grants = actors.capabilities | {"inventory.write"}
    with Session(database) as session:
        session.get(UserRecord, "actor-a").capabilities = sorted(grants)
        session.commit()
    return replace(actors, capabilities=grants)


@pytest.mark.parametrize("kind", list(MovementKind))
def test_managed_order_blocks_every_new_linked_inventory_kind(database, inventory_actor, kind):
    enroll(database, inventory_actor)
    payload = MovementCreateRequest(
        movement_id=uid(900),
        product_id="product-a",
        order_id="order-a",
        kind=kind,
        quantity=1,
        reference_movement_id=uid(901)
        if kind in (MovementKind.RELEASE, MovementKind.CONSUME)
        else None,
    )
    with Session(database) as session:
        with pytest.raises(ApiError) as error:
            record_movement(
                session, inventory_actor, payload, admission=WriteAdmission.for_fixtures()
            )
        assert error.value.code == "quote_managed_order"


@pytest.mark.parametrize("kind", list(MovementKind))
def test_existing_inventory_receipt_replays_but_changed_command_does_not(
    database, inventory_actor, kind
):
    from cycling_workshop.inventory.domain import InventoryMovement
    from cycling_workshop.inventory.models import InventoryMovementRecord
    from cycling_workshop.inventory.repository import SqlAlchemyInventoryRepository
    from sqlalchemy import func, select

    enroll(database, inventory_actor)
    payload = MovementCreateRequest(
        movement_id=uid(910),
        product_id="product-a",
        order_id="order-a",
        kind=kind,
        quantity=1,
        reference_movement_id=uid(911)
        if kind in (MovementKind.RELEASE, MovementKind.CONSUME)
        else None,
    )
    # Model retained legacy effects explicitly. Operational enrollment must NOT
    # accept this state; the legacy retry still cannot duplicate these effects.
    with Session(database) as session:
        repository = SqlAlchemyInventoryRepository(session)
        if payload.reference_movement_id:
            repository.record(
                InventoryMovement.record(
                    movement_id=uid(911),
                    product_id="product-a",
                    organization_id="a",
                    location_id="location-a",
                    order_id="order-a",
                    actor_id="actor-a",
                    kind="RESERVE",
                    quantity=1,
                    now=NOW,
                )
            )
            session.flush()
        original = InventoryMovement.record(
            **payload.model_dump(),
            organization_id="a",
            location_id="location-a",
            actor_id="actor-a",
            now=NOW,
        )
        repository.record(original)
        session.commit()
        count = session.scalar(select(func.count()).select_from(InventoryMovementRecord))
        replay = record_movement(
            session, inventory_actor, payload, admission=WriteAdmission.for_fixtures()
        )
        assert replay == original
        assert session.scalar(select(func.count()).select_from(InventoryMovementRecord)) == count
        with pytest.raises(ApiError) as error:
            record_movement(
                session,
                inventory_actor,
                payload.model_copy(update={"quantity": 2}),
                admission=WriteAdmission.for_fixtures(),
            )
        assert error.value.code == "inventory_conflict"
        assert session.scalar(select(func.count()).select_from(InventoryMovementRecord)) == count


def test_sync_exact_old_receipt_precedes_enrollment_fence(database, actors):
    with Session(database) as session:
        session.execute(
            update(ServiceOrderRecord)
            .where(ServiceOrderRecord.id == "order-a")
            .values(state="INTAKE")
        )
        session.commit()
        service = SyncService.for_fixtures(session)
        context = SyncApplicationContext(actor_id="actor-a")
        command = mutation("start_diagnosis")
        first = service.apply(command, context=context)
        session.commit()
        execute(session, actors, creation(expected_order_version=2))
        before = totals(session)
        assert service.apply(command, context=context) == first
        assert totals(session) == before
        assert session.get(ServiceOrderRecord, "order-a").version == 2


@pytest.mark.parametrize("grants", [frozenset({"orders.write"}), frozenset({"*"})])
def test_missing_quote_grants_cannot_bypass_and_denial_does_not_hydrate_text(
    database, actors, monkeypatch, grants
):
    from cycling_workshop.service_orders.repository import SqlAlchemyServiceOrderRepository

    enroll(database, actors)
    with Session(database) as session:
        session.get(UserRecord, "actor-a").capabilities = sorted(grants)
        session.commit()
        principal = replace(actors, capabilities=grants)

        def forbidden(*_, **__):
            pytest.fail("managed denial hydrated full order")

        monkeypatch.setattr(SqlAlchemyServiceOrderRepository, "get", forbidden)
        with pytest.raises(ApiError) as error:
            transition_service_order(
                "order-a",
                OrderTransitionRequest(action="authorize"),
                principal,
                session,
                WriteAdmission.for_fixtures(),
            )
        assert error.value.code == "quote_managed_order"


def test_unlinked_inventory_adjust_remains_available(database, inventory_actor):
    enroll(database, inventory_actor)
    with Session(database) as session:
        result = record_movement(
            session,
            inventory_actor,
            MovementCreateRequest(
                movement_id=uid(920), product_id="product-a", kind="ADJUST", quantity=1
            ),
            admission=WriteAdmission.for_fixtures(),
        )
        assert result.order_id is None and result.quantity == 1


def test_fresh_order_projection_after_scalar_lock_ignores_stale_identity_map(database, actors):
    with Session(database) as session:
        cached = session.get(ServiceOrderRecord, "order-a")
        assert cached.state == "DIAGNOSIS"
        # Another transaction wins before this writer's organization barrier.
        with database.begin() as connection:
            connection.execute(
                update(ServiceOrderRecord)
                .where(ServiceOrderRecord.id == "order-a")
                .values(state="AUTHORIZED", version=2)
            )
        result = transition_service_order(
            "order-a",
            OrderTransitionRequest(action="start_work"),
            actors,
            session,
            WriteAdmission.for_fixtures(),
        )
        assert result.state == "IN_PROGRESS" and result.version == 3


@pytest.mark.parametrize("ingress", ["transition", "inventory", "sync"])
def test_real_http_ingresses_refuse_and_sync_preserves_independent_batch_item(
    database, actors, ingress
):
    from cycling_workshop.app import create_app
    from cycling_workshop.settings import Settings
    from cycling_workshop.sync.models import MutationReceiptRecord
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    order_id = uid(930)
    grants = frozenset({"orders.write", "inventory.write", "sync.push", "customers.write"})
    with Session(database) as session:
        session.execute(
            update(ServiceOrderRecord).where(ServiceOrderRecord.id == "order-a").values(id=order_id)
        )
        session.commit()
        execute(session, actors, creation(order_id=order_id))
        session.get(UserRecord, "actor-a").capabilities = sorted(grants)
        session.commit()
    app = create_app(
        settings=Settings(
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
            auth_secret="ingress-test-secret-long-enough-for-tokens",
            log_level="WARNING",
        ),
        session_factory=sessionmaker(database, expire_on_commit=False),
    )
    principal = replace(actors, capabilities=grants)
    token = app.state.session_tokens.issue(principal)
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        if ingress == "transition":
            response = client.post(
                f"/api/v1/service-orders/{order_id}/transitions", json={"action": "authorize"}
            )
        elif ingress == "inventory":
            response = client.post(
                "/api/v1/inventory/movements",
                json={
                    "movement_id": uid(931),
                    "product_id": "product-a",
                    "order_id": order_id,
                    "kind": "ADJUST",
                    "quantity": 1,
                },
            )
        else:
            response = client.post(
                "/api/v1/sync/mutations",
                json={
                    "mutations": [
                        {
                            "mutation_id": uid(932),
                            "entity_type": "service_order",
                            "entity_id": order_id,
                            "operation": "update",
                            "organization_id": "a",
                            "location_id": "location-a",
                            "base_version": 1,
                            "occurred_at": NOW.isoformat(),
                            "payload": {"transition": {"action": "authorize"}},
                        },
                        {
                            "mutation_id": uid(933),
                            "entity_type": "customer",
                            "entity_id": uid(934),
                            "operation": "create",
                            "organization_id": "a",
                            "location_id": "location-a",
                            "base_version": None,
                            "occurred_at": NOW.isoformat(),
                            "payload": {"display_name": "Independent"},
                        },
                    ]
                },
            )
        if ingress == "sync":
            assert response.status_code == 200, response.text
            results = response.json()["results"]
            assert (
                results[0]["status"] == "conflict" and results[0]["error_code"] == "sync_conflict"
            )
            assert results[1]["status"] == "applied"
            with Session(database) as session:
                assert session.get(MutationReceiptRecord, uid(932)) is None
                assert session.get(MutationReceiptRecord, uid(933)) is not None
        else:
            assert response.status_code == 409, response.text
            assert response.json()["error"]["code"] == "quote_managed_order"
    with Session(database) as session:
        assert session.get(ServiceOrderRecord, order_id).state == "DIAGNOSIS"


def test_rolled_back_enrollment_does_not_poison_legacy_writer(database, actors, monkeypatch):
    def refuse_response(_):
        raise ValueError("synthetic serialization failure")

    from cycling_workshop.quotes.service import QuoteServiceError

    with monkeypatch.context() as patch:
        patch.setattr("cycling_workshop.quotes.service.encode_command_response", refuse_response)
        with (
            Session(database) as session,
            pytest.raises(QuoteServiceError, match="quote_integrity_failed"),
        ):
            execute(session, actors, creation())
    with Session(database) as session:
        result = transition_service_order(
            "order-a",
            OrderTransitionRequest(action="authorize"),
            actors,
            session,
            WriteAdmission.for_fixtures(),
        )
        assert result.state == "AUTHORIZED"
        assert totals(session) == (0, 1, 1, 1)
