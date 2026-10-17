"""Finite PostgreSQL specifications; prepared without local execution.

These small cases do not establish capacity, contention, migration rollback or
logical restore. They are not automatically part of the preserved 0012 gate.
"""

import json
from dataclasses import replace

import pytest
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.quotes import repository as repository_module
from cycling_workshop.quotes import service as service_module
from cycling_workshop.quotes.domain import PartLine
from cycling_workshop.quotes.effects import _order_effects
from cycling_workshop.quotes.models import QuoteOperationRecord
from cycling_workshop.quotes.repository import QuoteConflictError, QuoteRepository
from cycling_workshop.quotes.service import QuoteServiceError
from cycling_workshop.service_orders.models import ServiceOrderRecord
from cycling_workshop.sync.models import ChangeRecord
from cycling_workshop.sync.order_projection_integrity import OrderProjectionLimitError
from sqlalchemy import Text, cast, event, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_application_service import actors as actors
from test_quote_application_service import execute, totals
from test_quote_repository import admitted, creation, decision
from test_quote_repository import database as database
from test_quote_storage import NOW

pytestmark = pytest.mark.parametrize("identity_migration_database", ["postgres"], indirect=True)


def test_version_one_binds_both_measured_raw_copies_and_replays(database, actors, monkeypatch):
    measured = []
    original = service_module.encode_order_projection

    def capture(payload):
        prepared = original(payload)
        measured.append(prepared)
        return prepared

    monkeypatch.setattr(service_module, "encode_order_projection", capture)
    with Session(database) as session:
        execute(session, actors, creation())
        applied = execute(session, actors, decision())
        versions = list(session.scalars(select(QuoteOperationRecord.order_effect_version).order_by(
            QuoteOperationRecord.ordinal
        )))
        assert versions == [None, 1] and type(versions[1]) is int
        projection = measured[-1]
        change = session.execute(select(
            cast(ChangeRecord.payload, Text), ChangeRecord.order_payload_raw_octets
        )).one()
        outbox = session.execute(select(
            cast(OutboxRecord.payload, Text), OutboxRecord.order_payload_raw_octets
        ).where(OutboxRecord.aggregate_type == "service_order")).one()
        assert change == outbox == (projection.raw_json, projection.raw_octets)
        assert len(change[0].encode("utf-8")) == change[1]
        assert json.loads(change[0]) == dict(projection.payload)
    with Session(database) as session:
        assert execute(session, actors, decision(), enabled=False)["receipt"] == applied["receipt"]
        assert totals(session) == (2, 1, 1, 3)


def test_common_repository_create_checks_source_before_first_write(database, monkeypatch):
    monkeypatch.setattr(repository_module, "ORDER_SOURCE_MAX_BYTES", 1)
    writes = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "SAVEPOINT")):
            writes.append(statement)

    with Session(database) as session:
        admitted(session)
        event.listen(database, "before_cursor_execute", capture)
        try:
            with pytest.raises(QuoteConflictError, match="order_effect_payload_limit"):
                QuoteRepository(session).apply(creation(), recorded_at=NOW)
        finally:
            event.remove(database, "before_cursor_execute", capture)
        assert writes == []
        assert totals(session) == (0, 0, 0, 0)


def test_invalid_part_reference_refuses_before_order_text_admission(database, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("invalid ordinary command reached Text admission")

    lines = tuple(
        replace(line, product_id="product-b") if isinstance(line, PartLine) else line
        for line in creation().lines
    )
    monkeypatch.setattr(QuoteRepository, "_load_bounded_order", forbidden)
    with Session(database) as session:
        admitted(session)
        with pytest.raises(QuoteConflictError, match="outside order scope"):
            QuoteRepository(session).apply(creation(lines=lines), recorded_at=NOW)
        assert totals(session) == (0, 0, 0, 0)


@pytest.mark.parametrize("replay", [False, True])
def test_exhausted_version_refuses_new_enrollment_but_preserves_replay(
    database, monkeypatch, replay
):
    if replay:
        with Session(database) as session:
            admitted(session)
            original = QuoteRepository(session).apply(creation(), recorded_at=NOW)
            session.commit()
    with database.begin() as connection:
        connection.execute(text(
            "UPDATE service_orders SET version=2147483647 WHERE id='order-a'"
        ))
    writes = []

    def forbidden(*_args, **_kwargs):
        pytest.fail("exhausted order version reached Text hydration")

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "SAVEPOINT")):
            writes.append(statement)

    monkeypatch.setattr(QuoteRepository, "_load_bounded_order", forbidden)
    with Session(database) as session:
        admitted(session)
        event.listen(database, "before_cursor_execute", capture)
        try:
            if replay:
                result = QuoteRepository(session).apply(creation(), recorded_at=NOW)
                assert result.replayed and result.receipt == original.receipt
                assert result.order.version == 2147483647
            else:
                with pytest.raises(QuoteConflictError, match="order version cannot advance"):
                    QuoteRepository(session).apply(
                        creation(expected_order_version=2147483647), recorded_at=NOW
                    )
        finally:
            event.remove(database, "before_cursor_execute", capture)
        assert writes == []
        assert totals(session) == ((1, 0, 0, 1) if replay else (0, 0, 0, 0))


def test_actual_projection_preparation_refuses_before_savepoint_or_write(
    database, actors, monkeypatch
):
    with Session(database) as session:
        execute(session, actors, creation())
    writes = []

    def fail(_payload):
        raise OrderProjectionLimitError("synthetic canonical limit")

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "SAVEPOINT")):
            writes.append(statement)

    monkeypatch.setattr(service_module, "encode_order_projection", fail)
    event.listen(database, "before_cursor_execute", capture)
    try:
        with Session(database) as session:
            with pytest.raises(QuoteServiceError, match="quote_conflict"):
                execute(session, actors, decision())
    finally:
        event.remove(database, "before_cursor_execute", capture)
    assert writes == []
    with Session(database) as session:
        assert totals(session) == (1, 0, 0, 1)


def test_historical_replay_does_not_hydrate_oversized_current_text(database, actors, monkeypatch):
    with Session(database) as session:
        admitted(session)
        repository = QuoteRepository(session)
        repository.apply(creation(), recorded_at=NOW)
        repository.apply(decision(), recorded_at=NOW)
        session.commit()
    with database.begin() as connection:
        connection.execute(text(
            "UPDATE service_orders SET diagnosis = repeat('é', 131073) WHERE id = 'order-a'"
        ))

    def forbidden(*_args, **_kwargs):
        pytest.fail("exact quote-only replay hydrated current Text")

    monkeypatch.setattr(QuoteRepository, "_load_bounded_order", forbidden)
    with Session(database) as session:
        result = execute(session, actors, decision(), enabled=False)
        assert result["receipt"]["effects"]["kind"] == "quote_only"
        assert totals(session) == (2, 0, 0, 2)
        assert session.scalar(select(QuoteOperationRecord.order_effect_version).where(
            QuoteOperationRecord.kind == "decision"
        )) is None


@pytest.mark.parametrize("version", [None, 0, 2, -1, True, "1"])
def test_invalid_version_refuses_before_generic_payload_fetch(database, actors, monkeypatch, version):
    with Session(database) as session:
        execute(session, actors, creation())
        execute(session, actors, decision())

    def forged(operation):
        # Exercise decoder corruption without disabling the live database CHECK.
        if operation.kind == "decision":
            set_committed_value(operation, "order_effect_version", version)
        return _order_effects(operation)

    def forbidden(*_args, **_kwargs):
        pytest.fail("invalid version reached generic payload fetch")

    monkeypatch.setattr(repository_module, "_order_effects", forged)
    monkeypatch.setattr(QuoteRepository, "_load_order_effect_sources", forbidden)
    with Session(database) as session:
        with pytest.raises(QuoteServiceError, match="quote_integrity_failed"):
            execute(session, actors, decision(), enabled=False)


@pytest.mark.parametrize("value", ["infinity", "-infinity", "10000-01-01 00:00:00+00"])
def test_order_timestamp_guard_refuses_before_driver_conversion(database, actors, value):
    with database.begin() as connection:
        connection.execute(text(
            "UPDATE service_orders SET created_at = CAST(:value AS timestamptz) WHERE id = 'order-a'"
        ), {"value": value})
    with Session(database) as session:
        with pytest.raises(QuoteServiceError, match="quote_integrity_failed"):
            execute(session, actors, creation())
        assert not session.info.get("ocwp_quote_unusable", False)
        assert totals(session) == (0, 0, 0, 0)


def test_quote_writer_never_calls_generic_order_save(database, actors, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("quote writer invoked full-row ORM fallback")

    monkeypatch.setattr(
        "cycling_workshop.service_orders.repository.SqlAlchemyServiceOrderRepository.save",
        forbidden,
    )
    materialized = []

    def observe(_session, instance):
        if isinstance(instance, ServiceOrderRecord):
            materialized.append(instance)

    with Session(database) as session:
        event.listen(session, "loaded_as_persistent", observe)
        execute(session, actors, creation())
        result = execute(session, actors, decision())
        assert result["order"]["state"] == "AUTHORIZED"
        assert materialized == []
        event.remove(session, "loaded_as_persistent", observe)
        assert session.get(ServiceOrderRecord, "order-a").version == 2


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_source_utf8_boundary_is_checked_before_enrollment(database, monkeypatch, delta):
    limit = 32
    source = "é🚲" + "x" * (limit - 7 + delta)
    with database.begin() as connection:
        connection.execute(text(
            "UPDATE service_orders SET reported_problem=:source, priority='n', "
            "intake_condition=NULL, accessories=NULL, diagnosis=NULL WHERE id='order-a'"
        ), {"source": source})
    monkeypatch.setattr(repository_module, "ORDER_SOURCE_MAX_BYTES", limit)
    with Session(database) as session:
        admitted(session)
        if delta == 1:
            with pytest.raises(QuoteConflictError, match="order_effect_payload_limit"):
                QuoteRepository(session).apply(creation(), recorded_at=NOW)
            assert totals(session) == (0, 0, 0, 0)
        else:
            assert not QuoteRepository(session).apply(creation(), recorded_at=NOW).replayed


def test_two_transition_claims_refuse_before_generic_payload_fetch(database, actors, monkeypatch):
    with Session(database) as session:
        execute(session, actors, creation())
        execute(session, actors, decision())
        effect = _order_effects(session.scalar(select(QuoteOperationRecord).where(
            QuoteOperationRecord.kind == "decision"
        )))

    def duplicated(_operation):
        return effect

    def forbidden(*_args, **_kwargs):
        pytest.fail("multiple transition claims reached generic source fetch")

    monkeypatch.setattr(repository_module, "_order_effects", duplicated)
    monkeypatch.setattr(QuoteRepository, "_load_order_effect_sources", forbidden)
    with Session(database) as session:
        with pytest.raises(QuoteServiceError, match="quote_integrity_failed"):
            execute(session, actors, decision(), enabled=False)


def test_both_raw_casts_share_both_count_guards_without_orm_materialization(
    database, actors, monkeypatch
):
    with Session(database) as session:
        execute(session, actors, creation())
        execute(session, actors, decision())
    statements = []
    materialized = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        if " AS change_raw" in statement:
            statements.append(statement)

    def observe(_session, instance):
        if isinstance(instance, ChangeRecord):
            materialized.append(instance)
        if isinstance(instance, OutboxRecord) and instance.aggregate_type == "service_order":
            materialized.append(instance)

    # A tiny injected ceiling tests the guard, not production payload capacity.
    monkeypatch.setattr(repository_module, "ORDER_RAW_MAX_BYTES", 1)
    event.listen(database, "before_cursor_execute", capture)
    try:
        with Session(database) as session:
            event.listen(session, "loaded_as_persistent", observe)
            with pytest.raises(QuoteServiceError, match="quote_integrity_failed"):
                execute(session, actors, decision(), enabled=False)
    finally:
        event.remove(database, "before_cursor_execute", capture)
    assert len(statements) == 1 and materialized == []
    sql = statements[0]
    assert sql.count("CAST(sync_changes.payload AS pg_catalog.text)") == 1
    assert sql.count("CAST(outbox_events.payload AS pg_catalog.text)") == 1
    assert sql.count("order_payload_raw_octets") >= 6
    for label in ("change_raw", "outbox_raw"):
        guarded = sql.split(f" AS {label}")[0].rsplit("CASE", 1)[1]
        for table in ("sync_changes", "outbox_events"):
            for operator in (">=", "<="):
                assert (
                    f"{table}.order_payload_raw_octets OPERATOR(pg_catalog.{operator})"
                ) in guarded
        assert " ELSE " in guarded
    assert "service_order_events.note IS NULL" in sql
    assert "service_order_events.note," not in sql


def test_order_row_lock_is_retained_during_prepare_and_persist(database, actors, monkeypatch):
    with Session(database) as session:
        execute(session, actors, creation())
    observed = []
    encode = service_module.encode_order_projection
    persist = service_module._persist_order_effect

    def assert_locked(phase):
        with database.connect() as contender:
            with pytest.raises(DBAPIError) as error:
                contender.execute(text(
                    "SELECT id FROM service_orders WHERE id='order-a' FOR UPDATE NOWAIT"
                ))
            assert error.value.orig.sqlstate == "55P03"
            contender.rollback()
            observed.append(phase)

    def prepare(payload):
        assert_locked("prepare")
        return encode(payload)

    def write(session, prepared):
        assert_locked("persist")
        return persist(session, prepared)

    monkeypatch.setattr(service_module, "encode_order_projection", prepare)
    monkeypatch.setattr(service_module, "_persist_order_effect", write)
    with Session(database) as session:
        execute(session, actors, decision())
    assert observed == ["prepare", "persist"]


def test_small_compressed_text_is_refused_by_length_without_hydration(database, monkeypatch):
    with database.begin() as connection:
        connection.execute(text(
            "UPDATE service_orders SET diagnosis=repeat('é',8192) WHERE id='order-a'"
        ))
        compressed, actual = connection.execute(text(
            "SELECT pg_column_size(diagnosis), octet_length(diagnosis) "
            "FROM service_orders WHERE id='order-a'"
        )).one()
        assert compressed < actual == 16384
    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    monkeypatch.setattr(repository_module, "ORDER_SOURCE_MAX_BYTES", 1024)
    with Session(database) as session:
        admitted(session)
        event.listen(database, "before_cursor_execute", capture)
        try:
            with pytest.raises(QuoteConflictError, match="order_effect_payload_limit"):
                QuoteRepository(session).apply(creation(), recorded_at=NOW)
        finally:
            event.remove(database, "before_cursor_execute", capture)
        assert not any(" AS admitted" in statement for statement in statements)
        length_query = next(
            statement for statement in statements if "pg_catalog.octet_length" in statement
        )
        assert length_query.count("OPERATOR(pg_catalog.+)") == 4
        scalar_query = next(
            statement for statement in statements if " AS created_at" in statement
        )
        assert "pg_catalog.isfinite" in scalar_query
        assert "OPERATOR(pg_catalog.>=)" in scalar_query
        assert "OPERATOR(pg_catalog.<=)" in scalar_query
        assert totals(session) == (0, 0, 0, 0)
    with database.connect() as connection:
        assert connection.scalar(text(
            "SELECT octet_length(diagnosis) FROM service_orders WHERE id='order-a'"
        )) == 16384
        assert connection.scalar(text(
            "SELECT diagnosis FROM service_orders WHERE id='order-a'"
        )) == "é" * 8192


@pytest.mark.parametrize("field,value", [
    ("raw_json", "{}"),
    ("raw_octets", 1),
    ("canonical_utf8", b"{}"),
    ("payload", {"version": True}),
])
def test_bypassed_prepared_projection_refuses_before_any_write(
    database, actors, monkeypatch, field, value
):
    with Session(database) as session:
        execute(session, actors, creation())
    original = service_module.encode_order_projection
    writes = []

    def forged(payload):
        prepared = original(payload)
        object.__setattr__(prepared, field, value)
        return prepared

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "SAVEPOINT")):
            writes.append(statement)

    monkeypatch.setattr(service_module, "encode_order_projection", forged)
    event.listen(database, "before_cursor_execute", capture)
    try:
        with Session(database) as session:
            with pytest.raises(QuoteServiceError, match="quote_integrity_failed"):
                execute(session, actors, decision())
    finally:
        event.remove(database, "before_cursor_execute", capture)
    assert writes == []


def test_quote_outbox_pointer_cannot_prefetch_generic_order_json(database, actors):
    with Session(database) as session:
        created = execute(session, actors, creation())
    identifier = created["receipt"]["effects"]["quote_outbox_id"]
    # Generic outbox rows can be changed by ordinary SQL. The receipt FK alone
    # binds only the identifier and cannot prove the discriminator or scope.
    with database.begin() as connection:
        connection.execute(
            update(OutboxRecord)
            .where(OutboxRecord.event_id == identifier)
            .values(
                aggregate_type="service_order",
                aggregate_id="order-a",
                event_type="service_order.updated",
                payload={"unrelated": "é" * 4096},
            )
        )
    materialized = []

    def observe(_session, instance):
        if isinstance(instance, OutboxRecord) and instance.event_id == identifier:
            materialized.append(instance)

    with Session(database) as session:
        event.listen(session, "loaded_as_persistent", observe)
        with pytest.raises(QuoteServiceError, match="quote_integrity_failed"):
            execute(session, actors, creation(), enabled=False)
    assert materialized == []
