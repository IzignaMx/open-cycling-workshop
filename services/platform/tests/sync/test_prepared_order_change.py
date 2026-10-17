"""Prepared exact-bind cases; authored before implementation, not executed locally.

PostgreSQL uses the existing isolated migration fixture. SQLite is a functional
surrogate and establishes neither PostgreSQL locking nor bounded prefetch.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import MappingProxyType, SimpleNamespace
from typing import cast

import pytest
from alembic import command
from cycling_workshop.events import outbox
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.sync import order_projection_integrity as codec
from cycling_workshop.sync.models import ChangeRecord
from cycling_workshop.sync.writes import _append_prepared_order_change, append_change
from sqlalchemy import Text, event, func, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from services.platform.tests.identity.test_identity_migration import (
    identity_migration_database as identity_migration_database,
)

NOW = datetime(2026, 10, 17, 0, 0, 0, 1, tzinfo=UTC)


def projection():
    return codec.encode_order_projection(
        dict(
            order_id="order-a",
            customer_id="customer-a",
            bicycle_id=None,
            organization_id="a",
            location_id="location-a",
            state="AUTHORIZED",
            reported_problem='  é🚲\\"\n  ',
            intake_condition=None,
            accessories="",
            priority="normal",
            diagnosis="preserve  spaces",
            created_at="2026-10-17T00:00:00+00:00",
            updated_at=NOW.isoformat(),
            version=2,
        )
    )


def append(session, prepared, **changes):
    arguments = dict(
        organization_id="a",
        location_id="location-a",
        entity_id="order-a",
        entity_version=2,
        occurred_at=NOW,
        projection=prepared,
    )
    return _append_prepared_order_change(session, **(arguments | changes))


class CapturedSession:
    """Capture actual Core statements without executing a dialect or driver."""

    def __init__(self, dialect):
        self.dialect = dialect
        self.statements = []

    def get_bind(self):
        return SimpleNamespace(dialect=self.dialect)

    def execute(self, statement):
        self.statements.append(statement)
        return SimpleNamespace(scalar_one=lambda: 41)


@pytest.mark.parametrize("dialect", [postgresql.dialect(), sqlite.dialect()])
def test_prepared_statements_bind_original_text_without_json_adapter(monkeypatch, dialect):
    prepared = projection()
    session = CapturedSession(dialect)
    allocated = []

    def allocate():
        allocated.append("allocated-order-outbox")
        return allocated[-1]

    monkeypatch.setattr(outbox, "new_id", allocate)
    result = append(cast(Session, session), prepared)
    assert result.cursor == 41
    assert result.outbox_event_id == "allocated-order-outbox"
    assert allocated == [result.outbox_event_id]
    assert len(session.statements) == 2
    assert [statement.table.name for statement in session.statements] == [
        "sync_changes",
        "outbox_events",
    ]
    for statement in session.statements:
        compiled = statement.compile(dialect=dialect)
        bind = compiled.binds["prepared_order_payload"]
        assert isinstance(bind.type, Text)
        assert compiled.params["prepared_order_payload"] is prepared.raw_json
        assert bind.type.bind_processor(dialect) is None
        assert (" AS pg_catalog.json)" in str(compiled)) is (dialect.name == "postgresql")
        assert "order_payload_raw_octets" not in compiled.params
    assert "RETURNING" in str(session.statements[0].compile(dialect=dialect))
    assert list(session.statements[0].exported_columns.keys()) == ["cursor"]


@pytest.mark.parametrize(
    "field",
    ["raw_octets", "canonical_utf8", "payload_value", "payload_type", "mutable_payload"],
)
def test_forged_preparation_refuses_before_any_insert_or_id_allocation(monkeypatch, field):
    prepared = projection()
    if field == "raw_octets":
        forged = replace(prepared, raw_octets=prepared.raw_octets + 1)
    elif field == "canonical_utf8":
        forged = replace(prepared, canonical_utf8=prepared.canonical_utf8 + b" ")
    elif field == "payload_value":
        forged = replace(
            prepared,
            payload=MappingProxyType(dict(prepared.payload) | {"diagnosis": "different"}),
        )
    elif field == "payload_type":
        forged = replace(
            prepared,
            payload=MappingProxyType(dict(prepared.payload) | {"version": 2.0}),
        )
    else:
        forged = replace(prepared)
        object.__setattr__(forged, "payload", dict(prepared.payload))

    def allocate():
        pytest.fail("invalid preparation allocated a delivery identity")

    monkeypatch.setattr(outbox, "new_id", allocate)
    session = CapturedSession(sqlite.dialect())
    with pytest.raises(codec.OrderProjectionIntegrityError):
        append(cast(Session, session), forged)
    assert session.statements == []


@pytest.mark.parametrize(
    "changes",
    [
        {"organization_id": "other"},
        {"location_id": "other"},
        {"entity_id": "other"},
        {"entity_version": 3},
        {"entity_version": 2.0},
        {"occurred_at": NOW + timedelta(microseconds=1)},
        {"occurred_at": NOW.replace(tzinfo=None)},
    ],
)
def test_prepared_scope_version_and_time_must_match_before_insert(changes):
    session = CapturedSession(sqlite.dialect())
    with pytest.raises(codec.OrderProjectionIntegrityError):
        append(cast(Session, session), projection(), **changes)
    assert session.statements == []


@pytest.fixture
def database(identity_migration_database):
    config, engine = identity_migration_database
    command.upgrade(config, "0013")
    return engine


def retained_pair(session):
    change = session.execute(
        select(
            ChangeRecord.cursor,
            ChangeRecord.organization_id,
            ChangeRecord.location_id,
            ChangeRecord.entity_type,
            ChangeRecord.entity_id,
            ChangeRecord.operation,
            ChangeRecord.entity_version,
            sql_cast(ChangeRecord.payload, Text).label("raw_json"),
            ChangeRecord.order_payload_raw_octets,
        )
    ).one()
    delivery = session.execute(
        select(
            OutboxRecord.event_id,
            OutboxRecord.event_type,
            OutboxRecord.aggregate_type,
            OutboxRecord.aggregate_id,
            OutboxRecord.organization_id,
            OutboxRecord.location_id,
            OutboxRecord.attempts,
            OutboxRecord.published_at,
            sql_cast(OutboxRecord.payload, Text).label("raw_json"),
            OutboxRecord.order_payload_raw_octets,
        )
    ).one()
    return change, delivery


def test_prepared_writer_retains_both_exact_raw_copies_and_generated_counts(database, monkeypatch):
    # A valid noncanonical raw spelling must survive unchanged, including padding
    # and escaped non-ASCII. Canonical equivalence alone cannot prove raw binding.
    base = projection()
    raw = " \n" + base.raw_json.replace("é", "\\u00e9").replace("🚲", "\\ud83d\\udeb2") + "\n "
    prepared = codec.decode_order_projection(raw, stored_octets=len(raw.encode("utf-8")))
    assert prepared.canonical_utf8 == base.canonical_utf8
    monkeypatch.setattr(outbox, "new_id", lambda: "allocated-order-outbox")
    with Session(database) as session:
        result = append(session, prepared)
        assert type(result.cursor) is int and result.cursor > 0
        assert session.in_transaction()
        session.commit()

    with Session(database) as session:
        change, delivery = retained_pair(session)
        assert change.cursor == result.cursor
        assert delivery.event_id == result.outbox_event_id == "allocated-order-outbox"
        assert change.organization_id == delivery.organization_id == "a"
        assert change.location_id == delivery.location_id == "location-a"
        assert change.entity_type == delivery.aggregate_type == "service_order"
        assert change.entity_id == delivery.aggregate_id == "order-a"
        assert change.operation == "update" and change.entity_version == 2
        assert delivery.event_type == "service_order.updated"
        assert delivery.attempts == 0 and delivery.published_at is None
        for retained in (change, delivery):
            assert retained.raw_json == prepared.raw_json
            assert retained.order_payload_raw_octets == prepared.raw_octets
            assert len(retained.raw_json.encode("utf-8")) == prepared.raw_octets


@pytest.mark.parametrize("failure_after", ["sync_changes", "outbox_events", "caller"])
def test_prepared_inserts_are_owned_by_caller_rollback(database, failure_after):
    reached = []

    def fail_after_insert(connection, cursor, statement, parameters, context, executemany):
        for table in ("sync_changes", "outbox_events"):
            if statement.startswith(f"INSERT INTO {table}"):
                reached.append(table)
                if failure_after == table:
                    raise RuntimeError("synthetic post-insert refusal")

    event.listen(database, "after_cursor_execute", fail_after_insert)
    try:
        with (
            Session(database) as session,
            pytest.raises(RuntimeError, match="synthetic"),
            session.begin(),
        ):
            append(session, projection())
            raise RuntimeError("synthetic caller refusal")
    finally:
        event.remove(database, "after_cursor_execute", fail_after_insert)
    assert reached == (
        ["sync_changes"]
        if failure_after == "sync_changes"
        else ["sync_changes", "outbox_events"]
    )
    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(ChangeRecord)) == 0
        assert session.scalar(select(func.count()).select_from(OutboxRecord)) == 0


def test_ordinary_dictionary_writers_keep_payload_and_unbounded_contract(database, monkeypatch):
    # A tiny injected quote-only budget proves ordinary paths do not call the
    # projection codec. It is not a production-capacity fixture.
    monkeypatch.setattr(codec, "ORDER_RAW_MAX_BYTES", 1)
    monkeypatch.setattr(codec, "ORDER_CANONICAL_MAX_BYTES", 1)
    allocated = iter(("ordinary-change-outbox", "ordinary-direct-outbox"))
    monkeypatch.setattr(outbox, "new_id", lambda: next(allocated))
    payload = {"legacy_text": 'é🚲\\"\n  ', "arbitrary_nested": {"value": [1, True, None]}}
    with Session(database) as session:
        result = append_change(
            session,
            organization_id="a",
            location_id="location-a",
            entity_type="service_order",
            entity_id="legacy-order",
            operation="create",
            entity_version=1,
            occurred_at=NOW,
            payload=payload,
        )
        direct_id = outbox.enqueue_outbox(
            session,
            event_type="ordinary.created",
            aggregate_type="ordinary",
            aggregate_id="ordinary-id",
            organization_id="a",
            location_id=None,
            payload=payload,
            occurred_at=NOW,
        )
        session.commit()
    with Session(database) as session:
        change = session.get(ChangeRecord, result.cursor)
        delivery = session.get(OutboxRecord, result.outbox_event_id)
        direct = session.get(OutboxRecord, direct_id)
        assert change.payload == delivery.payload == direct.payload == payload
        assert delivery.event_id == "ordinary-change-outbox"
        assert delivery.event_type == "service_order.created"
        assert direct.event_id == "ordinary-direct-outbox" and direct.location_id is None
        assert delivery.attempts == direct.attempts == 0
        assert delivery.published_at is direct.published_at is None
        assert change.order_payload_raw_octets == delivery.order_payload_raw_octets
        assert change.order_payload_raw_octets > 1
        assert direct.order_payload_raw_octets is None
