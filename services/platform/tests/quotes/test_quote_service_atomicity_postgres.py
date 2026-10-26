"""Reached-write service rollback and synthetic commit ambiguity on PostgreSQL.

Generic change/order-outbox insert seams retain their existing writer5 coverage.
This tiny selection does not simulate real network cancellation or qualify scale.
"""

import json

import pytest
from cycling_workshop.db.base import Base
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.quotes import service
from cycling_workshop.quotes.models import QuoteDecisionRecord, QuoteOperationRecord
from cycling_workshop.quotes.service import QuoteServiceError
from cycling_workshop.service_orders.models import ServiceOrderEventRecord
from sqlalchemy import JSON, Text, cast, select
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_application_service import actors as actors
from test_quote_application_service import execute, totals
from test_quote_application_service_postgres import postgres_identity as postgres_identity
from test_quote_repository import counts, creation, decision
from test_quote_repository import database as database
from test_quote_service_restore_postgres import RETAINED_TABLES
from test_quote_storage import uid

pytestmark = pytest.mark.parametrize("identity_migration_database", ["postgres"], indirect=True)


def _retained_rows(database):
    """Use the restore snapshot's ten tables and raw JSON, in a fresh Session."""
    retained = {}
    with Session(database) as session:
        for name in RETAINED_TABLES:
            table = Base.metadata.tables[name]
            columns = [
                cast(column, Text).label(column.name) if isinstance(column.type, JSON) else column
                for column in table.columns
            ]
            retained[name] = [
                dict(row)
                for row in session.execute(
                    select(*columns).order_by(*table.primary_key.columns)
                ).mappings()
            ]
    return retained


def _assert_one_decision(database, actors, applied, command=None):
    """Fresh replay reconstructs the complete linked tuple without adding effects."""
    command = command or decision()
    effects = applied["receipt"]["effects"]
    assert effects["kind"] == "order_transition"
    assert effects["order_event_id"] == command.operation_id
    assert effects["resulting_order_version"] == 2
    assert effects["quote_outbox_id"] != effects["order_outbox_id"]
    assert applied["order"]["state"] == "AUTHORIZED"
    assert applied["order"]["version"] == 2
    before = _retained_rows(database)
    assert len(before["quote_decisions"]) == 1
    assert before["quote_lineages"][0]["decision_sequence"] == 1
    operations = sorted(before["quote_operations"], key=lambda row: row["ordinal"])
    assert [row["order_effect_version"] for row in operations] == [None, 1]
    assert operations[1]["operation_id"] == command.operation_id
    for field in (
        "quote_outbox_id",
        "order_event_id",
        "resulting_order_version",
        "change_cursor",
        "order_outbox_id",
    ):
        assert operations[1][field] == effects[field]
    with Session(database) as session:
        replay = execute(session, actors, command, enabled=False)
        assert replay["delivery"] == "replayed"
        assert replay["receipt"] == applied["receipt"]
        assert counts(session) == (1, 1, 2, 3)
        assert totals(session) == (2, 1, 1, 3)
    assert _retained_rows(database) == before


@pytest.mark.parametrize(
    "stage",
    [
        "decision_flush",
        "lineage_cas",
        "order_cas",
        "order_event_flush",
        "quote_outbox_flush",
        "receipt_flush",
        "response_serialization",
    ],
)
def test_reached_write_failure_rolls_back_and_fresh_same_id_applies_once(
    database, actors, monkeypatch, stage
):
    with Session(database) as session:
        execute(session, actors, creation())
    baseline = _retained_rows(database)
    reached = []
    flush_targets = {
        "decision_flush": (QuoteDecisionRecord, "decision_id"),
        "order_event_flush": (ServiceOrderEventRecord, "event_id"),
        "quote_outbox_flush": (OutboxRecord, "event_id"),
        "receipt_flush": (QuoteOperationRecord, "operation_id"),
    }

    with Session(database) as session, monkeypatch.context() as patch:
        if stage in flush_targets:
            model, identity = flush_targets[stage]
            original_flush = session.flush

            def flushed_then_fail(*args, **kwargs):
                pending = [record for record in session.new if isinstance(record, model)]
                original_flush(*args, **kwargs)
                if pending:
                    assert len(pending) == 1
                    record = pending[0]
                    value = getattr(record, identity)
                    if isinstance(record, OutboxRecord):
                        assert record.aggregate_type == "quote"
                    else:
                        assert value == uid(100)
                    column = getattr(model, identity)
                    assert session.scalar(select(column).where(column == value)) == value
                    reached.append(stage)
                    raise ValueError(f"synthetic failure after {stage}")

            patch.setattr(session, "flush", flushed_then_fail)
        elif stage in {"lineage_cas", "order_cas"}:
            table, expected = (
                ("quote_lineages", uid(1))
                if stage == "lineage_cas"
                else ("service_orders", "order-a")
            )
            original_execute = session.execute

            def updated_then_fail(statement, *args, **kwargs):
                result = original_execute(statement, *args, **kwargs)
                if getattr(statement, "is_update", False) and statement.table.name == table:
                    assert result.scalar_one() == expected
                    reached.append(stage)
                    raise ValueError(f"synthetic failure after {stage}")
                return result

            patch.setattr(session, "execute", updated_then_fail)
        else:
            original_encode = service.encode_command_response

            def encoded_then_fail(response):
                encoded = original_encode(response)
                assert json.loads(encoded)["receipt"]["operation_id"] == uid(100)
                reached.append(stage)
                raise ValueError("synthetic failure after response serialization")

            patch.setattr(service, "encode_command_response", encoded_then_fail)

        with pytest.raises(QuoteServiceError) as error:
            execute(session, actors, decision())
        assert error.value.code == "quote_integrity_failed"
        assert error.value.outcome_unknown is False
        assert error.value.cleanup_unverified is False
        assert reached == [stage]
        assert not session.in_transaction()

    assert _retained_rows(database) == baseline
    with Session(database) as session:
        applied = execute(session, actors, decision())
        assert applied["delivery"] == "applied"
    _assert_one_decision(database, actors, applied)


def test_synthetic_commit_success_ack_loss_is_unknown_and_fresh_replay_is_exact(
    database, actors, monkeypatch
):
    with Session(database) as session:
        execute(session, actors, creation())
    reached = []
    serialized = []
    with Session(database) as session, monkeypatch.context() as patch:
        original_commit = session.commit
        original_encode = service.encode_command_response

        def capture_response(response):
            encoded = original_encode(response)
            serialized.append(json.loads(encoded))
            return encoded

        def committed_then_lost():
            original_commit()
            reached.append("commit_returned")
            raise OSError("synthetic acknowledgment loss after successful PostgreSQL commit")

        patch.setattr(service, "encode_command_response", capture_response)
        patch.setattr(session, "commit", committed_then_lost)
        with pytest.raises(QuoteServiceError) as error:
            execute(session, actors, decision())
        assert reached == ["commit_returned"]
        assert len(serialized) == 1
        assert serialized[0]["delivery"] == "applied"
        assert error.value.code == "quote_request_unavailable"
        assert error.value.outcome_unknown is True

    # This is an injected post-success exception, not a real network-loss trial.
    _assert_one_decision(database, actors, serialized[0])
