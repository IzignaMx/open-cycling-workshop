"""Small source-backed read contracts; no HTTP/grants/capacity qualification."""

import json
from datetime import timedelta

import pytest
from cycling_workshop.identity.cutover import WriteAdmission
from cycling_workshop.identity.domain import Principal
from cycling_workshop.quotes.domain import LaborLine
from cycling_workshop.quotes.reads import (
    ERROR_LIMIT,
    PAGE_LIMIT,
    RESPONSE_LIMIT,
    QuoteReadError,
    RevisionDetail,
    RevisionMetadataPage,
    encode_read_error,
    encode_read_response,
    project_revision,
    project_revision_page,
)
from cycling_workshop.quotes.repository import QuoteIntegrityError, QuoteRepository
from cycling_workshop.quotes.storage import MAX_SAFE_INTEGER
from cycling_workshop.sync.writes import lock_writer
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_repository import counts, creation, decision, revision
from test_quote_repository import database as database
from test_quote_storage import NOW, uid


def admitted(session, suffix="a", location=None):
    # Exercise protocol 1, without fabricating a quote grant or exposing a service.
    return lock_writer(
        session,
        Principal(f"actor-{suffix}", suffix, location or f"location-{suffix}", frozenset()),
        WriteAdmission.for_fixtures(protocol=1, enabled=True),
    )


@pytest.fixture
def snapshots(database):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        repo.apply(creation(), recorded_at=NOW)
        before = repo.load("a", "location-a", "order-a")
        repo.apply(decision(), recorded_at=NOW)
        repo.apply(revision(expected_decision_sequence=1), recorded_at=NOW + timedelta(seconds=1))
        after = repo.load("a", "location-a", "order-a")
        assert before is not None and after is not None
        yield before, after


def test_detail_preserves_immutable_financial_revision_and_current_lineage(snapshots):
    before, after = snapshots
    original = project_revision(before, uid(1))
    historical = project_revision(after, uid(1))
    assert historical.revision == original.revision
    assert historical.current.head_quote_id == uid(2)
    assert historical.current.head_version == 2
    assert historical.current.decision_sequence == 1
    assert historical.current.lineage_id == uid(1)
    assert [line.kind for line in historical.revision.lines] == ["labor", "part", "discount", "tax"]
    assert historical.revision.totals.line_amounts[2].amount_minor == -20
    assert historical.revision.lines[0].description == "Labor snapshot"
    assert historical.revision.created_at == "2026-10-15T12:00:00.000000Z"
    raw = encode_read_response(historical)
    assert RevisionDetail.model_validate_json(raw) == historical
    for forbidden in (
        b"Private note",
        b"customer-a",
        b"proof",
        b"command",
        b"evidence",
        b"source",
        b"recorded_by",
        b"outbox",
        b"superseded_at",
        b"superseded_by",
    ):
        assert forbidden not in raw
    assert len(raw) < RESPONSE_LIMIT


def test_metadata_pages_are_bounded_scoped_and_immutable(snapshots):
    _, snapshot = snapshots
    first = project_revision_page(snapshot, limit=1)
    assert len(first.items) == 1 and first.items[0].quote_id == uid(1)
    assert first.next_cursor is not None and len(first.next_cursor) == 64
    assert first.next_cursor.isascii()
    second = project_revision_page(snapshot, limit=1, cursor=first.next_cursor)
    assert [item.quote_id for item in second.items] == [uid(2)]
    assert second.next_cursor is None and second.current == first.current
    assert RevisionMetadataPage.model_validate_json(encode_read_response(first)) == first
    assert "lines" not in first.items[0].model_dump()
    assert "line_amounts" not in first.items[0].totals.model_dump()
    with pytest.raises(ValidationError):
        first.items[0].version = 9


def test_default_page_limit_is_25_with_small_one_line_revisions(database):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        lines = (LaborLine(uid(10), "Small", 1, 1),)
        repo.apply(creation(lines=lines), recorded_at=NOW)
        for version in range(2, 27):
            repo.apply(
                revision(
                    operation_id=uid(200 + version),
                    quote_id=uid(version),
                    expected_head_id=uid(version - 1),
                    expected_head_version=version - 1,
                    lines=lines,
                ),
                recorded_at=NOW,
            )
        snapshot = repo.load("a", "location-a", "order-a")
        page = project_revision_page(snapshot)
        assert PAGE_LIMIT == 25 and len(page.items) == 25
        tail = project_revision_page(snapshot, cursor=page.next_cursor)
        assert [item.version for item in tail.items] == [26] and tail.next_cursor is None


@pytest.mark.parametrize("limit", [True, 1.0, "1", 0, -1, 26, MAX_SAFE_INTEGER + 1])
def test_page_limit_rejects_coercion_and_out_of_bounds(snapshots, limit):
    with pytest.raises(QuoteReadError, match="invalid_quote_page"):
        project_revision_page(snapshots[1], limit=limit)


@pytest.mark.parametrize("cursor", ["", "0" * 64, "x" * 65, "é", 1, True, {}, "f" * 10000])
def test_invalid_cursor_has_bounded_generic_error(snapshots, cursor):
    with pytest.raises(QuoteReadError) as caught:
        project_revision_page(snapshots[1], cursor=cursor)
    raw = encode_read_error(caught.value)
    assert json.loads(raw) == {"code": "invalid_quote_cursor"}
    assert len(raw) <= ERROR_LIMIT == 8192


def test_cursor_is_bound_to_current_scope_and_head(database):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        repo.apply(creation(), recorded_at=NOW)
        repo.apply(revision(), recorded_at=NOW)
        old = repo.load("a", "location-a", "order-a")
        cursor = project_revision_page(old, limit=1).next_cursor
        assert project_revision_page(old, cursor=cursor).items[0].quote_id == uid(2)
        repo.apply(
            revision(
                operation_id=uid(202),
                quote_id=uid(3),
                expected_head_id=uid(2),
                expected_head_version=2,
            ),
            recorded_at=NOW,
        )
        fresh = repo.load("a", "location-a", "order-a")
        with pytest.raises(QuoteReadError, match="invalid_quote_cursor"):
            project_revision_page(fresh, cursor=cursor)
        session.commit()
    with Session(database) as session:
        admitted(session, "b")
        repo = QuoteRepository(session)
        repo.apply(
            creation(
                operation_id=uid(220),
                quote_id=uid(20),
                organization_id="b",
                location_id="location-b",
                order_id="order-b",
                actor_id="actor-b",
                lines=(LaborLine(uid(10), "Small", 1, 1),),
            ),
            recorded_at=NOW,
        )
        repo.apply(
            revision(
                operation_id=uid(221),
                quote_id=uid(21),
                organization_id="b",
                location_id="location-b",
                order_id="order-b",
                actor_id="actor-b",
                lineage_id=uid(20),
                expected_head_id=uid(20),
                lines=(LaborLine(uid(10), "Small", 1, 1),),
            ),
            recorded_at=NOW,
        )
        other = repo.load("b", "location-b", "order-b")
        other_cursor = project_revision_page(other, limit=1).next_cursor
        assert other_cursor is not None
        assert project_revision_page(other, cursor=other_cursor).items[0].quote_id == uid(21)
        with pytest.raises(QuoteReadError, match="invalid_quote_cursor"):
            project_revision_page(other, cursor=cursor)
        with pytest.raises(QuoteReadError, match="invalid_quote_cursor"):
            project_revision_page(old, cursor=other_cursor)
        mutated = ("0" if cursor[0] != "0" else "1") + cursor[1:]
        with pytest.raises(QuoteReadError, match="invalid_quote_cursor"):
            project_revision_page(old, cursor=mutated)


@pytest.mark.parametrize("quote_id", [uid(99), "foreign", "bad id", True])
def test_unknown_or_malformed_detail_is_non_disclosing(snapshots, quote_id):
    with pytest.raises(QuoteReadError) as caught:
        project_revision(snapshots[1], quote_id)
    assert encode_read_error(caught.value) == b'{"code":"quote_revision_not_found"}'


@pytest.mark.parametrize("value", [True, 1.0, "1", MAX_SAFE_INTEGER + 1, -1])
def test_closed_detail_refuses_unsafe_or_coerced_money(snapshots, value):
    document = project_revision(snapshots[1], uid(1)).model_dump(mode="json")
    document["revision"]["totals"]["total_minor"] = value
    with pytest.raises(ValidationError):
        RevisionDetail.model_validate(document)


def test_safe_integer_extrema_round_trip_through_source(database):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        repo.apply(
            creation(lines=(LaborLine(uid(10), "Exact", 60, MAX_SAFE_INTEGER),)), recorded_at=NOW
        )
        snapshot = repo.load("a", "location-a", "order-a")
        detail = project_revision(snapshot, uid(1))
        assert (
            json.loads(encode_read_response(detail))["revision"]["totals"]["total_minor"]
            == MAX_SAFE_INTEGER
        )


@pytest.mark.parametrize("path", [(), ("revision",), ("revision", "totals"), ("current",)])
def test_unknown_fields_refused_at_every_object(snapshots, path):
    document = project_revision(snapshots[1], uid(1)).model_dump(mode="json")
    target = document
    for key in path:
        target = target[key]
    target["proof"] = "private"
    with pytest.raises(ValidationError):
        RevisionDetail.model_validate(document)


def test_byte_limit_checks_actual_utf8_payload_and_revalidates_copies(snapshots, monkeypatch):
    import cycling_workshop.quotes.reads as reads

    detail = project_revision(snapshots[1], uid(1))
    raw = encode_read_response(detail)
    assert RESPONSE_LIMIT == 1048576
    monkeypatch.setattr(reads, "RESPONSE_LIMIT", len(raw))
    assert encode_read_response(detail) == raw
    monkeypatch.setattr(reads, "RESPONSE_LIMIT", len(raw) - 1)
    with pytest.raises(QuoteReadError, match="quote_response_too_large"):
        encode_read_response(detail)
    invalid = detail.model_copy(update={"revision": {"secret": "do not echo"}})
    with pytest.raises(QuoteReadError, match="invalid_quote_projection"):
        encode_read_response(invalid)


@pytest.mark.parametrize("projection", ["page", "detail"])
@pytest.mark.parametrize(
    "table,mutation",
    [
        ("quote_revisions", "UPDATE quote_revisions SET total_minor = 1 WHERE version = 2"),
        ("quote_operations", "UPDATE quote_operations SET proof = '{}' WHERE ordinal = 2"),
        (None, "UPDATE outbox_events SET event_type = 'invalid'"),
    ],
)
def test_repository_validates_corruption_outside_requested_page_or_detail(
    database, projection, table, mutation
):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        repo.apply(creation(), recorded_at=NOW)
        repo.apply(revision(), recorded_at=NOW)
        session.commit()
    # Restore-corruption simulation on the disposable SQLite fixture only.
    if database.dialect.name != "sqlite":
        pytest.skip("SQLite-only corruption injection; not PostgreSQL restore evidence")
    with database.begin() as connection:
        if table is not None:
            connection.execute(text(f"DROP TRIGGER trg_{table}_no_update"))
        connection.execute(text(mutation))
    with Session(database) as session:
        admitted(session)
        with pytest.raises(QuoteIntegrityError):
            snapshot = QuoteRepository(session).load("a", "location-a", "order-a")
            if projection == "page":
                project_revision_page(snapshot, limit=1)
            else:
                project_revision(snapshot, uid(1))


def test_load_requires_current_transaction_and_scope_before_projection(database):
    with Session(database) as session:
        repo = QuoteRepository(session)
        with pytest.raises(PermissionError):
            repo.load("a", "location-a", "order-a")
        admitted(session)
        repo.apply(creation(), recorded_at=NOW)
        session.commit()
        with pytest.raises(PermissionError):
            repo.load("a", "location-a", "order-a")
        admitted(session)
        with pytest.raises(PermissionError):
            repo.load("b", "location-b", "order-b")
        with pytest.raises(PermissionError):
            repo.load("a", "other-location-a", "order-a")
        assert repo.load("a", "location-a", "order-a") is not None


@pytest.mark.parametrize(
    "field,value",
    [
        ("description", "x" * 501),
        ("description", "\x00"),
        ("description", "\ud800"),
        ("description", "   "),
        ("minutes", True),
        ("minutes", 1.0),
        ("minutes", "1"),
        ("minutes", 1_000_001),
        ("minutes", 0),
        ("hourly_rate_minor", MAX_SAFE_INTEGER + 1),
        ("hourly_rate_minor", -1),
        ("unknown", "secret"),
    ],
)
def test_line_schema_bounds_and_exactness(snapshots, field, value):
    document = project_revision(snapshots[1], uid(1)).model_dump(mode="json")
    document["revision"]["lines"][0][field] = value
    with pytest.raises(ValidationError):
        RevisionDetail.model_validate(document)


@pytest.mark.parametrize("value", ["\x00", "\ud800", "bad id", "x" * 37, ""])
def test_context_identifier_rejects_invalid_text(snapshots, value):
    document = project_revision(snapshots[1], uid(1)).model_dump(mode="json")
    document["current"]["order_id"] = value
    with pytest.raises(ValidationError):
        RevisionDetail.model_validate(document)


def test_exponent_integer_lexeme_is_not_coerced(snapshots):
    raw = encode_read_response(project_revision(snapshots[1], uid(1)))
    raw = raw.replace(b'"total_minor":232', b'"total_minor":2.32e2')
    assert b"2.32e2" in raw
    with pytest.raises(ValidationError):
        RevisionDetail.model_validate_json(raw)


def test_decision_sequence_invalidates_cursor_without_changing_financial_revision(database):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        repo.apply(creation(), recorded_at=NOW)
        repo.apply(revision(), recorded_at=NOW)
        before = repo.load("a", "location-a", "order-a")
        cursor = project_revision_page(before, limit=1).next_cursor
        repo.apply(
            decision(
                quote_id=uid(2), quote_version=2, expected_head_id=uid(2), expected_head_version=2
            ),
            recorded_at=NOW,
        )
        after = repo.load("a", "location-a", "order-a")
        assert project_revision(before, uid(2)).revision == project_revision(after, uid(2)).revision
        with pytest.raises(QuoteReadError, match="invalid_quote_cursor"):
            project_revision_page(after, cursor=cursor)


def test_unicode_bytes_read_only_effects_and_incoming_principal_narrowing(database, monkeypatch):
    import cycling_workshop.quotes.reads as reads
    from cycling_workshop.identity.models import UserRecord

    with Session(database) as session:
        actor = session.get(UserRecord, "actor-a")
        actor.capabilities = ["orders.read", "orders.write"]
        session.flush()
        effective = lock_writer(
            session,
            Principal("actor-a", "a", "location-a", frozenset({"orders.read"})),
            WriteAdmission.for_fixtures(protocol=1, enabled=True),
        )
        assert effective.capabilities == frozenset({"orders.read"})
        repo = QuoteRepository(session)
        repo.apply(creation(lines=(LaborLine(uid(10), "á🚲", 60, 1),)), recorded_at=NOW)
        before = counts(session)
        snapshot = repo.load("a", "location-a", "order-a")
        detail = project_revision(snapshot, uid(1))
        page = project_revision_page(snapshot)
        raw = encode_read_response(detail)
        assert len(raw) > len(raw.decode("utf-8"))
        monkeypatch.setattr(reads, "RESPONSE_LIMIT", len(raw.decode("utf-8")))
        with pytest.raises(QuoteReadError, match="quote_response_too_large"):
            encode_read_response(detail)
        assert counts(session) == before and page.current.head_version == 1


def test_error_codes_cannot_echo_arbitrary_input():
    with pytest.raises(ValidationError):
        QuoteReadError("private note")


@pytest.mark.parametrize("field", ["lines", "line_amounts", "items", "targets"])
def test_read_array_limits_are_enforced(snapshots, field):
    detail = project_revision(snapshots[1], uid(1)).model_dump(mode="json")
    if field == "items":
        page = project_revision_page(snapshots[1]).model_dump(mode="json")
        page["items"] = [page["items"][0]] * 26
        with pytest.raises(ValidationError):
            RevisionMetadataPage.model_validate(page)
        return
    if field == "lines":
        detail["revision"]["lines"] = [detail["revision"]["lines"][0]] * 101
    elif field == "line_amounts":
        detail["revision"]["totals"]["line_amounts"] *= 26
    else:
        detail["revision"]["lines"][2]["scope_line_ids"] = [uid(10)] * 101
    with pytest.raises(ValidationError):
        RevisionDetail.model_validate(detail)


def test_error_byte_budget_is_enforced(monkeypatch):
    import cycling_workshop.quotes.reads as reads

    error = QuoteReadError("invalid_quote_cursor")
    raw = encode_read_error(error)
    monkeypatch.setattr(reads, "ERROR_LIMIT", len(raw))
    assert encode_read_error(error) == raw
    monkeypatch.setattr(reads, "ERROR_LIMIT", len(raw) - 1)
    with pytest.raises(ValueError, match="byte limit"):
        encode_read_error(error)
