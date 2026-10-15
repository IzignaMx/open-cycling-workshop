"""Corrupt stored rows fail closed even if a restore bypassed database guards."""

from copy import deepcopy

import pytest
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.quotes.models import (
    QuoteDecisionRecord,
    QuoteLineageRecord,
    QuoteLineRecord,
    QuoteLineTargetRecord,
    QuoteOperationRecord,
    QuoteRevisionRecord,
)
from cycling_workshop.quotes.reconstruction import QuoteIntegrityError, reconstruct
from cycling_workshop.quotes.repository import QuoteRepository
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_repository import admitted, creation, decision, revision
from test_quote_repository import database as database
from test_quote_storage import NOW, uid


@pytest.fixture
def records(database):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        repo.apply(creation(), recorded_at=NOW)
        repo.apply(decision(), recorded_at=NOW)
        repo.apply(revision(expected_decision_sequence=1), recorded_at=NOW)
        data = [
            session.scalar(select(QuoteLineageRecord)),
            list(
                session.scalars(select(QuoteRevisionRecord).order_by(QuoteRevisionRecord.version))
            ),
            list(session.scalars(select(QuoteLineRecord))),
            list(session.scalars(select(QuoteLineTargetRecord))),
            list(session.scalars(select(QuoteDecisionRecord))),
            list(
                session.scalars(select(QuoteOperationRecord).order_by(QuoteOperationRecord.ordinal))
            ),
            list(session.scalars(select(OutboxRecord))),
        ]
        session.expunge_all()
    return data


def test_complete_rows_reconstruct_in_operation_order(records):
    result = reconstruct(*records)
    assert result.ledger.history.head.version == 2
    assert result.ledger.sequence == 1
    assert tuple(receipt.ordinal for receipt in result.receipts) == (1, 2, 3)
    assert result.ledger.projection.outcome == "NO_CURRENT_DECISION"


@pytest.mark.parametrize(
    "target,field,value",
    [
        ("lineage", "root_quote_id", uid(9)),
        ("lineage", "head_quote_id", uid(1)),
        ("lineage", "head_version", 1),
        ("lineage", "decision_sequence", 0),
        ("lineage", "currency", "USD"),
        ("lineage", "location_id", "other-location-a"),
        ("revision", "actor_id", "actor-b"),
        ("revision", "total_minor", 1),
        ("revision", "version", 2),
        ("revision", "organization_id", "b"),
        ("revision", "line_amounts", [[uid(10), True]]),
        ("line", "position", 99),
        ("line", "organization_id", "b"),
        ("line", "quantity", 1),
        ("line", "description", "Changed snapshot"),
        ("target", "source_line_id", uid(10)),
        ("target", "target_line_id", uid(99)),
        ("decision", "actor_id", "actor-b"),
        ("decision", "reason", "Changed"),
        ("decision", "sequence", 2),
        ("decision", "quote_version", 2),
        ("decision", "supersedes_entry_id", uid(999)),
        ("operation", "actor_id", "actor-b"),
        ("operation", "kind", "revise"),
        ("operation", "ordinal", 2),
        ("operation", "proof_version", 2),
        ("operation", "quote_version", 2),
        ("operation", "resulting_decision_sequence", 1),
        ("operation", "operation_id", uid(999)),
        ("operation", "lineage_id", uid(999)),
        ("operation", "decision_id", uid(100)),
        ("operation", "quote_outbox_id", uid(999)),
        ("operation", "order_event_id", "unactivated-event"),
        ("outbox", "aggregate_id", uid(9)),
        ("outbox", "organization_id", "b"),
        ("outbox", "location_id", "other-location-a"),
        ("outbox", "event_type", "quote.revised"),
    ],
)
def test_corrupt_result_or_receipt_is_rejected(records, target, field, value):
    indices = {
        "lineage": 0,
        "revision": 1,
        "line": 2,
        "target": 3,
        "decision": 4,
        "operation": 5,
        "outbox": 6,
    }
    item = records[indices[target]]
    if isinstance(item, list):
        item = item[0]
    setattr(item, field, value)
    with pytest.raises(QuoteIntegrityError):
        reconstruct(*records)


@pytest.mark.parametrize("index", [1, 2, 3, 4, 5, 6])
def test_missing_financial_evidence_or_receipt_rows_are_rejected(records, index):
    records[index].pop(0)
    with pytest.raises(QuoteIntegrityError):
        reconstruct(*records)


@pytest.mark.parametrize("index", [1, 2, 3, 4, 5, 6])
def test_duplicate_financial_evidence_or_receipt_rows_are_rejected(records, index):
    records[index].append(deepcopy(records[index][0]))
    with pytest.raises(QuoteIntegrityError):
        reconstruct(*records)


def test_reordered_operations_are_not_sorted_into_a_different_history(records):
    records[5][0], records[5][1] = records[5][1], records[5][0]
    with pytest.raises(QuoteIntegrityError):
        reconstruct(*records)


def test_altered_proof_does_not_rewrite_financial_history(records):
    records[5][0].proof = deepcopy(records[5][0].proof)
    records[5][0].proof["lines"][0]["hourly_rate_minor"] += 1
    with pytest.raises(QuoteIntegrityError):
        reconstruct(*records)


def test_unknown_proof_field_and_bool_result_are_refused(records):
    records[5][1].proof = deepcopy(records[5][1].proof)
    records[5][1].proof["command"]["unknown"] = None
    with pytest.raises(QuoteIntegrityError):
        reconstruct(*records)


@pytest.mark.parametrize(
    "field", ["proof_version", "ordinal", "quote_version", "resulting_decision_sequence"]
)
def test_boolean_operation_numbers_cannot_equal_integer_receipt_fields(records, field):
    operation = records[5][0]
    setattr(operation, field, bool(getattr(operation, field)))
    with pytest.raises(QuoteIntegrityError):
        reconstruct(*records)
