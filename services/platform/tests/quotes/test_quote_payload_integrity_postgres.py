"""Finite payload closure, prepared without local execution.

Fourteen field mismatches and two note-nullness cases reconstruct detached
sources loaded from genuine PostgreSQL effects; they do not mutate stored rows.
Four storage cases use actual SQL in the existing disposable schema fixture.
These tiny specimens do not qualify capacity, maximum history or recovery.
"""

import json

import pytest
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.quotes import repository as repository_module
from cycling_workshop.quotes.reconstruction import QuoteIntegrityError, reconstruct
from cycling_workshop.quotes.repository import QuoteConflictError, QuoteRepository
from cycling_workshop.quotes.service import QuoteServiceError
from cycling_workshop.service_orders.models import ServiceOrderRecord
from cycling_workshop.sync.models import ChangeRecord
from cycling_workshop.sync.order_projection_integrity import encode_order_projection
from sqlalchemy import Text, bindparam, event, text
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_application_service import actors as actors
from test_quote_application_service import execute, totals
from test_quote_application_service_postgres import postgres_identity as postgres_identity
from test_quote_atomic_effects import effect_records as effect_records
from test_quote_repository import admitted, creation, decision
from test_quote_repository import database as database
from test_quote_storage import NOW

pytestmark = pytest.mark.parametrize("identity_migration_database", ["postgres"], indirect=True)


def _assert_detached_outbox_mismatch(effect_records, field, value):
    data, effects, receipt = effect_records
    assert reconstruct(*data, **effects).receipts[-1] == receipt
    change = effects["changes"][0]
    outbox = effects["order_outboxes"][0]
    original = json.loads(change.raw_json)
    assert json.loads(outbox.raw_json) == original
    assert len(original) == 14
    before_change = vars(change).copy()
    before_outbox = vars(outbox).copy()
    prepared = encode_order_projection(original | {field: value})
    assert {key for key in original if original[key] != prepared.payload[key]} == {field}
    assert prepared.raw_octets == len(prepared.raw_json.encode("utf-8"))
    outbox.raw_json = prepared.raw_json
    outbox.raw_octets = prepared.raw_octets
    with pytest.raises(QuoteIntegrityError, match=r"^stored quote history is invalid$"):
        reconstruct(*data, **effects)
    assert vars(change) == before_change
    assert vars(outbox) == before_outbox | {
        "raw_json": prepared.raw_json,
        "raw_octets": prepared.raw_octets,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("order_id", "other-order"),
        ("customer_id", "other-customer"),
        ("bicycle_id", "other-bicycle"),
        ("organization_id", "other-organization"),
        ("location_id", "other-location"),
        ("state", "REJECTED"),
        ("version", 3),
    ],
)
def test_pg_derived_detached_identity_projection_mismatch(effect_records, field, value):
    _assert_detached_outbox_mismatch(effect_records, field, value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("reported_problem", "Other reported problem"),
        ("intake_condition", "Other intake condition"),
        ("accessories", "Other accessories"),
        ("priority", "high"),
        ("diagnosis", "Other diagnosis"),
        ("created_at", "2026-10-14T00:00:00+00:00"),
        ("updated_at", "2026-10-15T12:00:01+00:00"),
    ],
)
def test_pg_derived_detached_content_projection_mismatch(effect_records, field, value):
    _assert_detached_outbox_mismatch(effect_records, field, value)


@pytest.mark.parametrize("note_is_null", [False, 1], ids=["false", "integer-one"])
def test_pg_derived_detached_note_nullness_requires_exact_true(effect_records, note_is_null):
    data, effects, receipt = effect_records
    assert reconstruct(*data, **effects).receipts[-1] == receipt
    source = effects["order_events"][0]
    assert source.note_is_null is True
    source.note_is_null = note_is_null
    with pytest.raises(QuoteIntegrityError, match=r"^stored quote history is invalid$"):
        reconstruct(*data, **effects)


def _retained_pair(database):
    # Full composite Text images preserve every synthetic retained-row column.
    # Separate raw Text/counts also check the original JSON spelling exactly.
    query = text(
        "SELECT 'change' AS side, CAST(payload AS text) AS raw_json, "
        "order_payload_raw_octets AS raw_octets, "
        "pg_column_compression(payload) AS compression, "
        "pg_column_size(payload) AS stored_octets, "
        "CAST(sync_changes AS text) AS retained_row "
        "FROM sync_changes WHERE organization_id='a' AND location_id='location-a' "
        "AND entity_type='service_order' AND entity_id='order-a' "
        "UNION ALL SELECT 'outbox', CAST(payload AS text), order_payload_raw_octets, "
        "pg_column_compression(payload), pg_column_size(payload), "
        "CAST(outbox_events AS text) FROM outbox_events "
        "WHERE organization_id='a' AND location_id='location-a' "
        "AND aggregate_type='service_order' AND aggregate_id='order-a'"
    )
    with database.connect() as connection:
        rows = connection.execute(query).mappings().all()
    assert connection.closed
    assert len(rows) == 2
    assert {row["side"] for row in rows} == {"change", "outbox"}
    for row in rows:
        assert type(row["raw_octets"]) is int
        assert row["raw_octets"] == len(row["raw_json"].encode("utf-8"))
    return {row["side"]: dict(row) for row in rows}


def _replace_raw(connection, side, raw):
    statements = {
        "change": (
            "UPDATE sync_changes SET payload=CAST(:raw AS json) "
            "WHERE organization_id='a' AND location_id='location-a' "
            "AND entity_type='service_order' AND entity_id='order-a'"
        ),
        "outbox": (
            "UPDATE outbox_events SET payload=CAST(:raw AS json) "
            "WHERE organization_id='a' AND location_id='location-a' "
            "AND aggregate_type='service_order' AND aggregate_id='order-a'"
        ),
    }
    statement = text(statements[side]).bindparams(bindparam("raw", type_=Text()))
    assert connection.execute(statement, {"raw": raw}).rowcount == 1


def _assert_replay(database, actors, receipt):
    with Session(database) as session:
        replay = execute(session, actors, decision(), enabled=False)
        assert replay["delivery"] == "replayed"
        assert replay["receipt"] == receipt
        assert totals(session) == (2, 1, 1, 3)


def _assert_guarded_raw_refusal(database, actors, monkeypatch, limit):
    statements = []
    materialized = []

    def capture(_connection, _cursor, statement, parameters, _context, many):
        if " AS change_raw" in statement:
            assert type(parameters) is dict and not many
            statements.append((statement, parameters.copy()))

    def observe(_session, instance):
        if isinstance(instance, (ServiceOrderRecord, ChangeRecord)):
            materialized.append(instance)
        if isinstance(instance, OutboxRecord) and instance.aggregate_type == "service_order":
            materialized.append(instance)

    monkeypatch.setattr(repository_module, "ORDER_RAW_MAX_BYTES", limit)
    event.listen(database, "before_cursor_execute", capture)
    try:
        with Session(database) as session:
            event.listen(session, "loaded_as_persistent", observe)
            try:
                with pytest.raises(QuoteServiceError, match=r"^quote_integrity_failed$"):
                    execute(session, actors, decision(), enabled=False)
            finally:
                event.remove(session, "loaded_as_persistent", observe)
    finally:
        event.remove(database, "before_cursor_execute", capture)
    assert len(statements) == 1
    assert materialized == []
    sql, parameters = statements[0]
    # Re-execute the real loader's one scoped statement after rollback, without
    # rebuilding its predicates or passing JSON through an ORM result adapter.
    with database.connect() as connection:
        guarded = connection.exec_driver_sql(sql, parameters).mappings().one()
    assert connection.closed
    for side in ("change", "outbox"):
        assert type(guarded[f"{side}_octets"]) is int
        assert guarded[f"{side}_raw"] is None
    with Session(database) as session:
        assert totals(session) == (2, 1, 1, 3)
    return guarded


def test_external_text_sql_preflight_refuses_without_hydration(database, monkeypatch):
    source = "é" * 4096
    snapshot = text(
        "SELECT diagnosis, octet_length(diagnosis), pg_column_toast_chunk_id(diagnosis), "
        "pg_column_compression(diagnosis), CAST(service_orders AS text) "
        "FROM service_orders WHERE id='order-a'"
    )
    with database.begin() as connection:
        # Storage strategy is changed only in this test's disposable schema.
        connection.execute(text("ALTER TABLE service_orders ALTER diagnosis SET STORAGE EXTERNAL"))
        connection.execute(
            text("UPDATE service_orders SET diagnosis=:source WHERE id='order-a'"),
            {"source": source},
        )
        before = connection.execute(snapshot).one()
    assert before[0] == source
    assert before[1] == len(source.encode("utf-8")) == 8192
    assert type(before[2]) is int and before[2] > 0
    assert before[3] is None
    # Enrollment is valid at the ordinary ceiling. Roll it back so the refusal
    # below remains a fresh enrollment rather than an admission-bypassing replay.
    with Session(database) as session:
        admitted(session)
        assert not QuoteRepository(session).apply(creation(), recorded_at=NOW).replayed
        session.rollback()
    statements = []
    materialized = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    def observe(_session, instance):
        if isinstance(instance, ServiceOrderRecord):
            materialized.append(instance)

    monkeypatch.setattr(repository_module, "ORDER_SOURCE_MAX_BYTES", 1024)
    with Session(database) as session:
        admitted(session)
        event.listen(database, "before_cursor_execute", capture)
        event.listen(session, "loaded_as_persistent", observe)
        try:
            with pytest.raises(QuoteConflictError, match=r"^order_effect_payload_limit$"):
                QuoteRepository(session).apply(creation(), recorded_at=NOW)
        finally:
            event.remove(session, "loaded_as_persistent", observe)
            event.remove(database, "before_cursor_execute", capture)
        assert totals(session) == (0, 0, 0, 0)
    assert materialized == []
    assert any("pg_catalog.octet_length(service_orders.diagnosis)" in sql for sql in statements)
    assert not any(" AS admitted" in sql for sql in statements)
    assert not any(
        sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "SAVEPOINT"))
        for sql in statements
    )
    with database.connect() as connection:
        assert connection.execute(snapshot).one() == before
    assert connection.closed


def test_compressed_json_sql_pair_refuses_with_both_guarded_values_null(
    database, actors, monkeypatch
):
    with Session(database) as session:
        execute(session, actors, creation())
        applied = execute(session, actors, decision())
    original = _retained_pair(database)
    payload = json.loads(original["change"]["raw_json"])
    prepared = encode_order_projection(payload | {"diagnosis": "é" * 4096})
    assert prepared.raw_octets < 10_240
    with database.begin() as connection:
        connection.execute(text("ALTER TABLE sync_changes ALTER payload SET COMPRESSION pglz"))
        connection.execute(text("ALTER TABLE outbox_events ALTER payload SET COMPRESSION pglz"))
        for side in ("change", "outbox"):
            _replace_raw(connection, side, prepared.raw_json)
    before = _retained_pair(database)
    for row in before.values():
        assert row["raw_json"] == prepared.raw_json
        assert row["raw_octets"] == prepared.raw_octets
        assert row["compression"] == "pglz"
        assert row["stored_octets"] < row["raw_octets"]
        assert row["raw_octets"] > 1024
    _assert_replay(database, actors, applied["receipt"])
    guarded = _assert_guarded_raw_refusal(database, actors, monkeypatch, 1024)
    for side in ("change", "outbox"):
        assert guarded[f"{side}_octets"] == prepared.raw_octets
    assert _retained_pair(database) == before


@pytest.mark.parametrize("oversized_side", ["change", "outbox"])
def test_asymmetric_sql_count_guard_nulls_both_raw_values(
    database, actors, monkeypatch, oversized_side
):
    with Session(database) as session:
        execute(session, actors, creation())
        applied = execute(session, actors, decision())
    original = _retained_pair(database)
    assert original["change"]["raw_json"] == original["outbox"]["raw_json"]
    limit = original["change"]["raw_octets"]
    assert limit == original["outbox"]["raw_octets"]
    raw = original[oversized_side]["raw_json"] + " " * 64
    with database.begin() as connection:
        _replace_raw(connection, oversized_side, raw)
    before = _retained_pair(database)
    assert before[oversized_side]["raw_json"] == raw
    assert before[oversized_side]["raw_octets"] == limit + 64
    other_side = "outbox" if oversized_side == "change" else "change"
    assert before[other_side] == original[other_side]
    assert {side for side, row in before.items() if row["raw_octets"] > limit} == {oversized_side}
    _assert_replay(database, actors, applied["receipt"])
    guarded = _assert_guarded_raw_refusal(database, actors, monkeypatch, limit)
    assert guarded[f"{oversized_side}_octets"] == limit + 64
    assert guarded[f"{other_side}_octets"] == limit
    assert _retained_pair(database) == before
