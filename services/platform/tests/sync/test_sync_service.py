from datetime import UTC, datetime

import pytest
from cycling_workshop.db.base import Base
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.domain import MutationEnvelope, SyncConflict
from cycling_workshop.sync.service import SyncService
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def build_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    session.add_all(
        [
            OrganizationRecord(id="org-1", name="Taller Uno"),
            LocationRecord(id="loc-1", organization_id="org-1", name="Principal"),
            OrganizationRecord(id="org-2", name="Taller Dos"),
            LocationRecord(id="loc-2", organization_id="org-2", name="Principal"),
        ]
    )
    session.commit()
    return session


def customer_create_mutation(
    *, mutation_id: str | None = None, entity_id: str | None = None
) -> MutationEnvelope:
    return MutationEnvelope(
        mutation_id=mutation_id or new_id(),
        entity_type="customer",
        entity_id=entity_id or new_id(),
        operation="create",
        organization_id="org-1",
        location_id="loc-1",
        base_version=None,
        occurred_at=datetime(2026, 8, 7, tzinfo=UTC),
        payload={"display_name": "Ana Rivera", "email": "ana@example.com", "phone": None},
    )


def test_duplicate_mutation_id_is_applied_exactly_once() -> None:
    with build_session() as session:
        service = SyncService(session)
        mutation = customer_create_mutation()

        first = service.apply(mutation)
        session.commit()
        second = service.apply(mutation)
        session.commit()

        assert first.status == "applied"
        assert second.status == "applied"
        assert first.entity_version == second.entity_version == 1
        changes = service.pull_changes(
            organization_id="org-1",
            location_id="loc-1",
            after_cursor=0,
            limit=100,
        )
        assert len(changes.items) == 1


def test_change_feed_cursor_is_incremental_and_tenant_scoped() -> None:
    with build_session() as session:
        service = SyncService(session)
        first = customer_create_mutation()
        second = customer_create_mutation()
        service.apply(first)
        service.apply(second)
        session.commit()

        page = service.pull_changes(
            organization_id="org-1",
            location_id="loc-1",
            after_cursor=0,
            limit=1,
        )
        assert len(page.items) == 1
        assert page.next_cursor > 0

        next_page = service.pull_changes(
            organization_id="org-1",
            location_id="loc-1",
            after_cursor=page.next_cursor,
            limit=100,
        )
        assert len(next_page.items) == 1
        assert next_page.items[0].cursor > page.items[0].cursor

        other_tenant = service.pull_changes(
            organization_id="org-2",
            location_id="loc-2",
            after_cursor=0,
            limit=100,
        )
        assert other_tenant.items == []


def test_update_with_stale_base_version_becomes_explicit_conflict() -> None:
    with build_session() as session:
        service = SyncService(session)
        created = customer_create_mutation()
        service.apply(created)
        session.commit()

        stale = MutationEnvelope(
            mutation_id=new_id(),
            entity_type="customer",
            entity_id=created.entity_id,
            operation="update",
            organization_id="org-1",
            location_id="loc-1",
            base_version=0,
            occurred_at=datetime(2026, 8, 7, tzinfo=UTC),
            payload={"display_name": "Ana R."},
        )

        with pytest.raises(SyncConflict, match="base version"):
            service.apply(stale)


def test_customer_mutation_writes_outbox_event_in_same_transaction() -> None:
    from cycling_workshop.events.models import OutboxRecord
    from sqlalchemy import select

    with build_session() as session:
        service = SyncService(session)
        mutation = customer_create_mutation()

        service.apply(mutation)
        session.flush()
        events = list(session.scalars(select(OutboxRecord)))

        assert len(events) == 1
        assert events[0].event_type == "customer.created"
        assert events[0].aggregate_id == mutation.entity_id
        assert events[0].organization_id == mutation.organization_id
