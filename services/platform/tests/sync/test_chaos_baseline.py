from datetime import UTC, datetime
import random

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from cycling_workshop.db.base import Base
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.domain import MutationEnvelope
from cycling_workshop.sync.service import SyncService
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord


def test_duplicate_and_reordered_independent_mutations_converge_without_duplicate_changes() -> None:
    engine = create_engine(
        'sqlite+pysqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add(OrganizationRecord(id='org-1', name='Taller Uno'))
        session.add(LocationRecord(id='loc-1', organization_id='org-1', name='Principal'))
        session.commit()

        unique: list[MutationEnvelope] = []
        for index in range(20):
            unique.append(
                MutationEnvelope(
                    mutation_id=new_id(),
                    entity_type='customer',
                    entity_id=new_id(),
                    operation='create',
                    organization_id='org-1',
                    location_id='loc-1',
                    base_version=None,
                    occurred_at=datetime(2026, 8, 7, tzinfo=UTC),
                    payload={'display_name': f'Customer {index:02d}'},
                )
            )

        delivery = unique + unique[::2] + unique[::3]
        random.Random(20260807).shuffle(delivery)
        service = SyncService(session)
        for mutation in delivery:
            service.apply(mutation)
            session.commit()

        page = service.pull_changes(
            organization_id='org-1',
            location_id='loc-1',
            after_cursor=0,
            limit=100,
        )

        assert len(page.items) == len(unique)
        assert len({item.entity_id for item in page.items}) == len(unique)
