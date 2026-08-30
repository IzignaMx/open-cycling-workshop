from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from cycling_workshop.db.base import Base
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.domain import MutationEnvelope, SyncConflict
from cycling_workshop.sync.service import SyncService
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord


def build_session() -> Session:
    engine = create_engine(
        'sqlite+pysqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    session.add(OrganizationRecord(id='org-1', name='Taller Uno'))
    session.add(LocationRecord(id='loc-1', organization_id='org-1', name='Principal'))
    session.commit()
    return session


def mutation(
    *,
    entity_id: str,
    operation: str,
    base_version: int | None,
    display_name: str,
    minute: int,
) -> MutationEnvelope:
    return MutationEnvelope(
        mutation_id=new_id(),
        entity_type='customer',
        entity_id=entity_id,
        operation=operation,  # type: ignore[arg-type]
        organization_id='org-1',
        location_id='loc-1',
        base_version=base_version,
        occurred_at=datetime(2026, 8, 7, tzinfo=UTC) + timedelta(minutes=minute),
        payload={'display_name': display_name},
    )


def test_two_devices_converge_after_one_stale_offline_edit_becomes_conflict() -> None:
    with build_session() as session:
        service = SyncService(session)
        customer_id = new_id()

        created = service.apply(
            mutation(
                entity_id=customer_id,
                operation='create',
                base_version=None,
                display_name='Ana',
                minute=0,
            )
        )
        session.commit()
        assert created.entity_version == 1

        initial_page_a = service.pull_changes(
            organization_id='org-1', location_id='loc-1', after_cursor=0, limit=100
        )
        initial_page_b = service.pull_changes(
            organization_id='org-1', location_id='loc-1', after_cursor=0, limit=100
        )
        assert initial_page_a.items[-1].payload['display_name'] == 'Ana'
        assert initial_page_b.items[-1].entity_version == 1

        device_b_update = mutation(
            entity_id=customer_id,
            operation='update',
            base_version=1,
            display_name='Ana B',
            minute=1,
        )
        device_a_stale_update = mutation(
            entity_id=customer_id,
            operation='update',
            base_version=1,
            display_name='Ana A stale',
            minute=2,
        )

        applied_b = service.apply(device_b_update)
        session.commit()
        assert applied_b.entity_version == 2

        with pytest.raises(SyncConflict, match='base version'):
            service.apply(device_a_stale_update)
        session.rollback()

        final_a = service.pull_changes(
            organization_id='org-1',
            location_id='loc-1',
            after_cursor=initial_page_a.next_cursor,
            limit=100,
        )
        final_b = service.pull_changes(
            organization_id='org-1',
            location_id='loc-1',
            after_cursor=initial_page_b.next_cursor,
            limit=100,
        )
        assert final_a.items[-1].payload['display_name'] == 'Ana B'
        assert final_b.items[-1].payload['display_name'] == 'Ana B'
        assert final_a.items[-1].entity_version == final_b.items[-1].entity_version == 2
