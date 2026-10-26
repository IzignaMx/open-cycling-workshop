"""Full-history maintenance on disposable SQLite: not PostgreSQL recovery proof."""

import json
from dataclasses import replace

import pytest
from cycling_workshop.api.errors import ApiError
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.identity.audit import IdentityAuditRecord
from cycling_workshop.identity.cutover_cli import recover_cutover
from cycling_workshop.quotes.models import QuoteLineageRecord
from cycling_workshop.service_orders.models import ServiceOrderRecord
from cycling_workshop.settings import Settings
from cycling_workshop.tenancy.models import OrganizationRecord
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_application_service import actors as actors
from test_quote_application_service import execute, totals
from test_quote_repository import creation, decision
from test_quote_repository import database as database
from test_quote_storage import NOW, uid

pytestmark = pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)


def prepare(database, actors):
    with Session(database) as session:
        execute(session, actors, creation())
        applied = execute(session, actors, decision())
        organization = session.get(OrganizationRecord, "a")
        organization.minimum_write_protocol = 1
        incarnation = organization.dataset_incarnation
        session.commit()
    return incarnation, applied


def recover(database, incarnation):
    return recover_cutover(
        Settings(environment="test", database_url=str(database.url), cutover_enabled=True),
        organization_id="a",
        expected_incarnation=incarnation,
    )


def test_recovery_rejects_corrupt_retained_order_pair_before_rotation(database, actors):
    incarnation, applied = prepare(database, actors)
    with Session(database) as session:
        outbox = session.get(OutboxRecord, applied["receipt"]["effects"]["order_outbox_id"])
        outbox.payload = dict(outbox.payload) | {"reported_problem": "different retained value"}
        session.commit()
        before = totals(session)
    with pytest.raises(ApiError) as failure:
        recover(database, incarnation)
    assert failure.value.code == "quote_integrity_failed"
    with Session(database) as session:
        assert session.get(OrganizationRecord, "a").dataset_incarnation == incarnation
        assert totals(session) == before
        assert (
            session.get(OutboxRecord, applied["receipt"]["effects"]["order_outbox_id"]).payload[
                "reported_problem"
            ]
            == "different retained value"
        )


def test_recovery_uses_complete_reconstruction_not_only_effect_pair(database, actors):
    incarnation, _ = prepare(database, actors)
    with Session(database) as session:
        lineage = session.scalar(select(QuoteLineageRecord))
        lineage.decision_sequence += 1
        session.commit()
    with pytest.raises(ApiError) as failure:
        recover(database, incarnation)
    assert failure.value.code == "quote_integrity_failed"


def test_recovery_valid_history_rotates_without_republishing(database, actors):
    incarnation, applied = prepare(database, actors)
    with Session(database) as session:
        before = totals(session)
        raw = [
            (row.event_id, json.dumps(row.payload, sort_keys=True))
            for row in session.scalars(select(OutboxRecord))
        ]
    result = recover(database, incarnation)
    assert result["dataset_incarnation"] != incarnation
    with Session(database) as session:
        replay = execute(
            session,
            replace(actors, dataset_incarnation=result["dataset_incarnation"]),
            decision(),
            enabled=False,
        )
        assert replay["receipt"] == applied["receipt"]
        assert replay["delivery"] == "replayed"
        assert totals(session) == before
        assert [
            (row.event_id, json.dumps(row.payload, sort_keys=True))
            for row in session.scalars(select(OutboxRecord))
        ] == raw


@pytest.mark.parametrize(
    "damage", ["orphan_outbox", "foreign_outbox", "orphan_target", "unsupported_version"]
)
def test_recovery_refuses_incomplete_inventory_without_repair(database, actors, damage):
    incarnation, _ = prepare(database, actors)
    with database.begin() as connection:
        if damage in ("orphan_outbox", "foreign_outbox"):
            connection.execute(
                OutboxRecord.__table__.insert().values(
                    event_id=uid(900),
                    event_type="quote.created",
                    aggregate_type="quote",
                    aggregate_id=uid(1) if damage == "foreign_outbox" else uid(901),
                    organization_id="b" if damage == "foreign_outbox" else "a",
                    location_id="location-a",
                    payload={},
                    occurred_at=NOW,
                    attempts=0,
                )
            )
        elif damage == "orphan_target":
            # Explicit synthetic damage; production constraints remain unchanged.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.exec_driver_sql("INSERT INTO quote_line_targets VALUES ('missing','x','y')")
        else:
            connection.exec_driver_sql("DROP TRIGGER trg_quote_operations_no_update")
            connection.exec_driver_sql("PRAGMA ignore_check_constraints=ON")
            connection.exec_driver_sql(
                "UPDATE quote_operations SET order_effect_version=2 WHERE kind='decision'"
            )
    with pytest.raises(ApiError) as failure:
        recover(database, incarnation)
    assert failure.value.code == "quote_integrity_failed"
    with Session(database) as session:
        assert session.get(OrganizationRecord, "a").dataset_incarnation == incarnation
        assert list(session.scalars(select(IdentityAuditRecord))) == []


def test_recovery_enumerates_last_lineage_and_preserves_earlier_history(
    database, actors, monkeypatch
):
    incarnation, _ = prepare(database, actors)
    with Session(database) as session:
        order = session.get(ServiceOrderRecord, "order-a")
        values = {
            column.name: getattr(order, column.name)
            for column in ServiceOrderRecord.__table__.columns
        }
        values.update(id="second-order", state="DIAGNOSIS", version=1)
        session.add(ServiceOrderRecord(**values))
        session.commit()
        execute(
            session,
            replace(actors, dataset_incarnation=incarnation),
            creation(order_id="second-order", quote_id=uid(700), operation_id=uid(701)),
        )
        lineage = session.get(QuoteLineageRecord, uid(700))
        lineage.decision_sequence = 1
        session.commit()
    seen = []
    from cycling_workshop.quotes.repository import QuoteRepository

    original = QuoteRepository._load

    def observe(self, lineage):
        seen.append(lineage.lineage_id)
        return original(self, lineage)

    monkeypatch.setattr(QuoteRepository, "_load", observe)
    with pytest.raises(ApiError) as failure:
        recover(database, incarnation)
    assert failure.value.code == "quote_integrity_failed"
    assert seen == [uid(1), uid(700)]
    with Session(database) as session:
        assert session.get(OrganizationRecord, "a").dataset_incarnation == incarnation
        assert list(session.scalars(select(IdentityAuditRecord))) == []


def test_quote_only_recovery_never_hydrates_oversized_current_text(database, actors, monkeypatch):
    with Session(database) as session:
        original = execute(session, actors, creation())
        org = session.get(OrganizationRecord, "a")
        org.minimum_write_protocol = 1
        incarnation = org.dataset_incarnation
        session.get(ServiceOrderRecord, "order-a").reported_problem = "z" * 262145
        session.commit()

    def forbidden(*args, **kwargs):
        raise AssertionError("quote-only recovery must not hydrate current order text")

    monkeypatch.setattr(
        "cycling_workshop.quotes.repository.QuoteRepository._load_bounded_order", forbidden
    )
    result = recover(database, incarnation)
    with Session(database) as session:
        replay = execute(
            session,
            replace(actors, dataset_incarnation=result["dataset_incarnation"]),
            creation(),
            enabled=False,
        )
        assert replay["receipt"] == original["receipt"]
        assert replay["delivery"] == "replayed"
        assert session.get(ServiceOrderRecord, "order-a").reported_problem == "z" * 262145


@pytest.mark.parametrize(
    "table", ["quote_revisions", "quote_lines", "quote_decisions", "quote_operations"]
)
def test_recovery_does_not_skip_orphan_retained_children(database, actors, table):
    incarnation, _ = prepare(database, actors)
    with database.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql(f"DROP TRIGGER trg_{table}_no_update")
        connection.exec_driver_sql("PRAGMA ignore_check_constraints=ON")
        connection.exec_driver_sql(f"UPDATE {table} SET lineage_id='missing'")
    with pytest.raises(ApiError) as failure:
        recover(database, incarnation)
    assert failure.value.code == "quote_integrity_failed"


def test_recovery_failure_after_validation_rolls_back_rotation_and_audit(
    database, actors, monkeypatch
):
    incarnation, _ = prepare(database, actors)
    from cycling_workshop.identity.audit import append_audit

    def fail(*args, **kwargs):
        append_audit(*args, **kwargs)
        raise RuntimeError("synthetic audit interruption")

    monkeypatch.setattr("cycling_workshop.identity.cutover_cli.append_audit", fail)
    with pytest.raises(RuntimeError, match="synthetic audit interruption"):
        recover(database, incarnation)
    with Session(database) as session:
        assert session.get(OrganizationRecord, "a").dataset_incarnation == incarnation
        assert list(session.scalars(select(IdentityAuditRecord))) == []


def test_populated_0012_requires_preserved_upgrade_before_recovery(identity_migration_database):
    from alembic import command as migrate
    from sqlalchemy import MetaData, Table
    from test_quote_historical_upgrade_postgres import TABLE_NAMES, seed_valid_0012_history
    from test_quote_schema import seed_base

    config, engine = identity_migration_database
    migrate.upgrade(config, "0012")
    seed_base(engine)
    with engine.begin() as connection:
        metadata = MetaData()
        tables = {name: Table(name, metadata, autoload_with=connection) for name in TABLE_NAMES}
        seed_valid_0012_history(connection, tables)
    with Session(engine) as session:
        org = session.get(OrganizationRecord, "a")
        org.minimum_write_protocol = 1
        incarnation = org.dataset_incarnation
        session.commit()
    with pytest.raises(ApiError) as refused:
        recover(engine, incarnation)
    assert refused.value.code == "quote_recovery_schema_required"
    migrate.upgrade(config, "head")
    assert recover(engine, incarnation)["dataset_incarnation"] != incarnation


def test_recovery_normalizes_invalid_lineage_scope_without_rotation(database, actors):
    incarnation, _ = prepare(database, actors)
    with database.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql("DROP TRIGGER trg_quote_lineage_identity")
        connection.exec_driver_sql("UPDATE quote_lineages SET order_id='bad scope'")
    with pytest.raises(ApiError) as failure:
        recover(database, incarnation)
    assert failure.value.code == "quote_integrity_failed"
    with Session(database) as session:
        assert session.get(OrganizationRecord, "a").dataset_incarnation == incarnation


def test_recovery_does_not_label_interrupted_validation_as_corruption(
    database, actors, monkeypatch
):
    incarnation, _ = prepare(database, actors)

    def interrupted(*args, **kwargs):
        raise TimeoutError("synthetic unavailable validation")

    monkeypatch.setattr("cycling_workshop.quotes.repository.QuoteRepository._load", interrupted)
    with pytest.raises(TimeoutError, match="synthetic unavailable validation"):
        recover(database, incarnation)
    with Session(database) as session:
        assert session.get(OrganizationRecord, "a").dataset_incarnation == incarnation
        assert list(session.scalars(select(IdentityAuditRecord))) == []


def test_prequote_marker_cannot_hide_retained_quote_tables(database, actors):
    incarnation, _ = prepare(database, actors)
    with database.begin() as connection:
        connection.exec_driver_sql("UPDATE alembic_version SET version_num='0011'")
    with pytest.raises(ApiError) as failure:
        recover(database, incarnation)
    assert failure.value.code == "cutover_schema_incompatible"


@pytest.mark.parametrize("schema", ["0010", "0011"])
def test_prequote_schema_rejects_retained_quote_outbox(identity_migration_database, schema):
    from alembic import command as migrate
    from sqlalchemy import text
    from test_quote_schema import seed_base

    config, engine = identity_migration_database
    migrate.upgrade(config, schema)
    seed_base(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO outbox_events (event_id,event_type,aggregate_type,aggregate_id,"
                "organization_id,location_id,payload,occurred_at,attempts) VALUES "
                "('unsupported','quote.created','quote','unknown','a','location-a','{}',"
                "'2026-10-26 00:00:00',0)"
            )
        )
    with Session(engine) as session:
        org = session.get(OrganizationRecord, "a")
        org.minimum_write_protocol = 1
        incarnation = org.dataset_incarnation
        session.commit()
    with pytest.raises(ApiError) as failure:
        recover(engine, incarnation)
    assert failure.value.code == "quote_integrity_failed"
