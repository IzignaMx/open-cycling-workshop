"""Fixture batching/order/atomicity only; SQLite is not PostgreSQL timeout proof."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from cycling_workshop.db.base import Base
from cycling_workshop.inventory.models import InventoryMovementRecord, ProductRecord
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from sqlalchemy import create_engine, event, func, insert, select
from sqlalchemy.orm import sessionmaker

from services.platform.tests.inventory import test_inventory_postgres as fixture


@pytest.fixture
def database():
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys = ON")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    now = datetime(2026, 10, 15, tzinfo=UTC)
    with factory.begin() as session:
        for owner, count in [("owned", 1201), ("foreign", 3)]:
            session.add(OrganizationRecord(id=owner, name=owner))
            session.flush()
            session.add(LocationRecord(id=owner, organization_id=owner, name=owner))
            session.flush()
            session.execute(
                insert(ProductRecord),
                [
                    {
                        "id": f"{owner}-{n:04}",
                        "organization_id": owner,
                        "location_id": owner,
                        "sku": str(n),
                        "name": str(n),
                        "created_at": now,
                        "updated_at": now,
                    }
                    for n in range(count)
                ],
            )
            session.add(
                InventoryMovementRecord(
                    movement_id=owner,
                    product_id=f"{owner}-0000",
                    organization_id=owner,
                    location_id=owner,
                    kind="ADJUST",
                    quantity=1,
                    actor_id="synthetic",
                    occurred_at=now,
                )
            )
    try:
        yield engine, factory
    finally:
        engine.dispose()


def product_count(session, owner):
    return session.scalar(
        select(func.count())
        .select_from(ProductRecord)
        .where(ProductRecord.organization_id == owner)
    )


def assert_rolled_back(factory):
    with factory() as session:
        assert product_count(session, "owned") == 1201
        assert product_count(session, "foreign") == 3
        assert session.get(InventoryMovementRecord, "owned") is not None
        assert session.get(InventoryMovementRecord, "foreign") is not None
        assert session.get(OrganizationRecord, "owned") is not None


def test_cleanup_uses_ordered_bounded_scoped_batches_and_keeps_foreign_data(database):
    engine, factory = database
    deletes = []

    def capture(_connection, _cursor, statement, parameters, _context, _many):
        if statement.startswith("DELETE"):
            deletes.append((statement, parameters))

    event.listen(engine, "before_cursor_execute", capture)
    with factory.begin() as session:
        fixture._cleanup_inventory_fixture(session, "owned")
    product_deletes = [
        (sql, values) for sql, values in deletes if sql.startswith("DELETE FROM products")
    ]
    assert [len(values) - 1 for _, values in product_deletes] == [500, 500, 201]
    ids = []
    for sql, values in product_deletes:
        assert "products.organization_id =" in sql and "products.id IN" in sql
        assert values[0] == "owned"
        ids.extend(values[1:])
    assert ids == [f"owned-{n:04}" for n in range(1201)]
    assert deletes[0][0].startswith("DELETE FROM inventory_movements")
    assert deletes[-1][0].startswith("DELETE FROM organizations")
    with factory() as session:
        assert product_count(session, "owned") == 0
        assert product_count(session, "foreign") == 3
        assert session.get(InventoryMovementRecord, "foreign") is not None
        assert session.get(OrganizationRecord, "foreign") is not None
        assert session.get(OrganizationRecord, "owned") is None


def test_second_batch_failure_rolls_back_child_and_first_parent_batch(database):
    engine, factory = database
    batches = 0

    def fail(_connection, _cursor, statement, _parameters, _context, _many):
        nonlocal batches
        if statement.startswith("DELETE FROM products"):
            batches += 1
            if batches == 2:
                raise RuntimeError("synthetic batch failure")

    event.listen(engine, "before_cursor_execute", fail)
    with pytest.raises(RuntimeError, match="synthetic batch failure"), factory.begin() as session:
        fixture._cleanup_inventory_fixture(session, "owned")
    assert batches == 2
    assert_rolled_back(factory)


@pytest.mark.parametrize("fault", ["no_progress", "foreign_ids", "missing_ids", "extra_row"])
def test_cleanup_rejects_incomplete_progress_without_unbounded_repetition(
    database, monkeypatch, fault
):
    _engine, factory = database
    deletes = 0
    with (
        pytest.raises(RuntimeError, match="Inventory fixture cleanup incomplete"),
        factory.begin() as session,
    ):
        original_execute = session.execute

        def execute(statement, *args, **kwargs):
            nonlocal deletes
            if getattr(statement, "is_delete", False) and statement.table.name == "products":
                deletes += 1
                if fault == "no_progress":
                    return SimpleNamespace(rowcount=0)
                result = original_execute(statement, *args, **kwargs)
                if fault == "extra_row" and deletes == 1:
                    now = datetime(2026, 10, 15, tzinfo=UTC)
                    original_execute(
                        insert(ProductRecord),
                        [
                            {
                                "id": "owned-extra",
                                "organization_id": "owned",
                                "location_id": "owned",
                                "sku": "extra",
                                "name": "extra",
                                "created_at": now,
                                "updated_at": now,
                            }
                        ],
                    )
                return result
            return original_execute(statement, *args, **kwargs)

        monkeypatch.setattr(session, "execute", execute)
        if fault in {"foreign_ids", "missing_ids"}:
            monkeypatch.setattr(
                session,
                "scalars",
                lambda *args, **kwargs: (
                    [f"foreign-{n:04}" for n in range(500)] if fault == "foreign_ids" else []
                ),
            )
        fixture._cleanup_inventory_fixture(session, "owned")
    assert deletes <= 3
    assert_rolled_back(factory)


def test_empty_owned_scope_is_a_finite_noop_preserving_other_organizations(database):
    _engine, factory = database
    with factory.begin() as session:
        fixture._cleanup_inventory_fixture(session, "absent")
    assert_rolled_back(factory)
