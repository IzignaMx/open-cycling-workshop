"""Tiny exact-byte oracles for locked reconstruction reuse."""

from dataclasses import fields, replace

import pytest
from cycling_workshop.quotes import reconstruction, repository, storage
from cycling_workshop.quotes.reconstruction import QuoteSnapshot
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_repository import admitted, counts, creation, decision, revision
from test_quote_repository import database as database
from test_quote_storage import NOW, uid


@pytest.mark.parametrize("records", [[], [{"text": 'café 🚲\n"'}], [{"a": 1}, {"b": "ñ"}]])
def test_count_matches_canonical_array_and_exact_boundary(monkeypatch, records):
    size = len(storage.canonical_bytes(records))
    monkeypatch.setattr(storage, "MAX_HISTORY_BYTES", size)
    assert storage._history_byte_count(records) == size
    assert storage.validate_history_bytes(records) is None
    monkeypatch.setattr(storage, "MAX_HISTORY_BYTES", size - 1)
    with pytest.raises(ValueError, match=r"^quote storage complete-history byte limit exceeded$"):
        storage._history_byte_count(records)


def test_public_snapshot_shape_is_unchanged():
    assert [field.name for field in fields(QuoteSnapshot)] == ["ledger", "receipts"]


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
def test_locked_count_matches_operation_time_oracle_and_avoids_second_replay(database, monkeypatch):
    commands = [
        creation(),
        revision(),
        revision(
            operation_id=uid(202), quote_id=uid(3), expected_head_id=uid(2), expected_head_version=2
        ),
    ]
    commands[0] = replace(
        commands[0],
        lines=tuple(replace(line, description="Revisión café 🚲") for line in commands[0].lines),
    )
    replay_calls = []
    replay_advance = reconstruction.advance
    monkeypatch.setattr(
        reconstruction, "advance", lambda *args: (replay_calls.append(1), replay_advance(*args))[1]
    )
    calls = []
    original = repository.advance
    monkeypatch.setattr(repository, "advance", lambda *args: (calls.append(1), original(*args))[1])
    with Session(database) as session:
        admitted(session)
        repo = repository.QuoteRepository(session)
        for command in commands:
            replay_before = len(replay_calls)
            before = len(calls)
            repo.apply(command, recorded_at=NOW)
            assert len(calls) - before == 1
            assert len(replay_calls) - replay_before == 0
        snapshot, size = repo._load_with_bytes(repo._lineage("a", "order-a"))
        prefix = None
        logical = []
        for receipt in snapshot.receipts:
            prefix = reconstruction.advance(prefix, receipt.command, receipt.recorded_at)
            logical.append(reconstruction.logical_record(receipt.command, prefix))
        assert size == len(storage.canonical_bytes(logical))
        assert repo.load("a", "location-a", "order-a") == snapshot
        assert repo.apply(commands[0], recorded_at=NOW).replayed
        assert counts(session) == (1, 3, 3, 3)


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
def test_candidate_byte_boundary_preserves_error_and_rows(database, monkeypatch):
    first = creation()
    second = revision()
    prefix = reconstruction.advance(None, first, NOW)
    first_record = reconstruction.logical_record(first, prefix)
    ledger = reconstruction.advance(prefix, second, NOW)
    candidate = reconstruction.logical_record(second, ledger)
    exact = len(storage.canonical_bytes([first_record, candidate]))
    with Session(database) as session:
        admitted(session)
        repo = repository.QuoteRepository(session)
        repo.apply(first, recorded_at=NOW)
        monkeypatch.setattr(storage, "MAX_HISTORY_BYTES", exact - 1)
        with pytest.raises(
            ValueError, match=r"^quote storage complete-history byte limit exceeded$"
        ):
            repo.apply(second, recorded_at=NOW)
        assert counts(session) == (1, 1, 1, 1)
        monkeypatch.setattr(storage, "MAX_HISTORY_BYTES", exact)
        repo.apply(second, recorded_at=NOW)
        assert counts(session) == (1, 2, 2, 2)
        session.rollback()
    with Session(database) as session:
        assert counts(session) == (0, 0, 0, 0)


@pytest.mark.parametrize(
    "error_type", [ValueError, TypeError, AttributeError, KeyError, OverflowError]
)
def test_private_and_public_reconstruction_normalize_same_errors(monkeypatch, error_type):
    def invalid(*args):
        raise error_type("synthetic malformed stored data")

    monkeypatch.setattr(reconstruction, "_reconstruct", invalid)
    for reconstruct in (reconstruction.reconstruct, reconstruction._reconstruct_with_bytes):
        with pytest.raises(
            reconstruction.QuoteIntegrityError, match=r"^stored quote history is invalid$"
        ) as failure:
            reconstruct(None, [], [], [], [], [], [])
        assert type(failure.value.__cause__) is error_type


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
def test_decision_correction_withdrawal_count_matches_joined_oracle(database):
    commands = [
        creation(),
        decision(),
        decision(
            decision_id=uid(101),
            mode="record_correction",
            expected_decision_sequence=1,
            supersedes_entry_id=uid(100),
            reason="Corrección café 🚲",
        ),
        decision(
            decision_id=uid(102),
            mode="withdraw_record",
            outcome="WITHDRAW",
            approved_line_ids=(),
            evidence=None,
            expected_decision_sequence=2,
            supersedes_entry_id=uid(101),
            reason="Retiro café 🚲",
        ),
    ]
    with Session(database) as session:
        admitted(session)
        repo = repository.QuoteRepository(session)
        prefix = None
        logical = []
        receipts = []
        for command in commands:
            receipts.append(repo.apply(command, recorded_at=NOW).receipt)
            prefix = reconstruction.advance(prefix, command, NOW)
            logical.append(reconstruction.logical_record(command, prefix))
            snapshot, size = repo._load_with_bytes(repo._lineage("a", "order-a"))
            assert size == len(storage.canonical_bytes(logical))
            assert snapshot.ledger == prefix
        for command, receipt in zip(commands, receipts, strict=True):
            result = repo.apply(command, recorded_at=NOW)
            assert result.replayed and result.receipt == receipt
            assert result.ledger == prefix
        assert counts(session) == (1, 1, 4, 4)


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
def test_later_revision_does_not_replace_historical_decision_result(database):
    commands = [creation(), decision(), revision(expected_decision_sequence=1)]
    with Session(database) as session:
        admitted(session)
        repo = repository.QuoteRepository(session)
        prefix = None
        logical = []
        for command in commands:
            repo.apply(command, recorded_at=NOW)
            prefix = reconstruction.advance(prefix, command, NOW)
            logical.append(reconstruction.logical_record(command, prefix))
        snapshot, size = repo._load_with_bytes(repo._lineage("a", "order-a"))
        assert len(snapshot.receipts) == 3
        assert size == len(storage.canonical_bytes(logical))
        assert snapshot.ledger.projection.outcome == "NO_CURRENT_DECISION"
        assert repo.apply(commands[1], recorded_at=NOW).replayed


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
def test_candidate_keeps_history_array_nesting_validation(database, monkeypatch):
    nested = "leaf"
    for _ in range(12):
        nested = {"node": nested}
    assert storage.canonical_bytes(nested)
    with pytest.raises(ValueError, match="JSON exceeds depth limit"):
        storage.canonical_bytes([nested])
    monkeypatch.setattr(repository, "logical_record", lambda *_: nested)
    with Session(database) as session:
        admitted(session)
        with pytest.raises(ValueError, match="JSON exceeds depth limit"):
            repository.QuoteRepository(session).apply(creation(), recorded_at=NOW)
        assert counts(session) == (0, 0, 0, 0)
