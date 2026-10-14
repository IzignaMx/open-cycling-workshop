from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.db import registry
from cycling_workshop.db.base import Base
from cycling_workshop.service_orders.models import ServiceOrderRecord
from cycling_workshop.sync.baseline_queries import BaselineQueries, Candidate
from cycling_workshop.sync.models import ChangeRecord
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

NOW = datetime(2026, 10, 14, tzinfo=UTC)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    registry.register_models()
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value
    engine.dispose()


def customer(identifier, *, organization="org", location="loc"):
    return CustomerRecord(
        id=identifier,
        organization_id=organization,
        location_id=location,
        display_name="Name",
        email=None,
        phone=None,
        created_at=NOW,
        updated_at=NOW,
        version=1,
    )


def change(cursor, entity_type="customer", *, organization="org", location="loc", payload=None):
    return ChangeRecord(
        cursor=cursor,
        organization_id=organization,
        location_id=location,
        entity_type=entity_type,
        entity_id="a",
        operation="update",
        entity_version=2,
        occurred_at=NOW,
        payload=payload or {"historical": True},
    )


def test_scan_includes_no_feed_rows_and_uses_binary_fixed_bounds(session):
    session.add_all(
        [customer("a"), customer("Z"), customer("b"), customer("foreign", location="else")]
    )
    session.flush()
    queries = BaselineQueries(session, "org", "loc", ["customer"])
    assert queries.watermark() == 0
    assert queries.maxima() == {"customer": "b"}
    candidates = queries.scan_candidates("customer", "Z", "a")
    assert [value.entity_id for value in candidates] == ["a"]
    envelope = queries.load(candidates[0])
    assert envelope["entity_id"] == "a"
    assert envelope["entity_version"] == 1
    assert set(envelope["payload"]) == {
        "customer_id",
        "organization_id",
        "location_id",
        "display_name",
        "email",
        "phone",
        "created_at",
        "updated_at",
        "version",
    }
    assert len(json.dumps(envelope).encode()) <= candidates[0].estimated_bytes


def test_delta_scopes_before_limits_merges_and_retains_history(session):
    session.add(customer("a"))
    session.add_all([change(i, "hidden") for i in range(1, 501)])
    session.add_all(
        [
            change(501),
            change(502, "bicycle"),
            change(503, location="else"),
            change(504, organization="foreign"),
            change(505),
        ]
    )
    session.flush()
    queries = BaselineQueries(session, "org", "loc", ["customer", "bicycle"])
    assert queries.watermark() == 505
    candidates = queries.delta_candidates(0, 502)
    assert [value.position for value in candidates] == [501, 502]
    assert queries.load(candidates[0])["payload"] == {"historical": True}
    assert queries.load(candidates[0])["entity_version"] == 2


def test_candidates_bounded_and_no_payload_selected(session):
    session.add_all([change(i) for i in range(1, 130)])
    session.flush()
    queries = BaselineQueries(session, "org", "loc", ["customer"])
    statements = []
    event.listen(
        session.get_bind(),
        "before_cursor_execute",
        lambda conn, cursor, statement, params, context, many: statements.append(statement),
    )
    assert len(queries.delta_candidates(0, 200)) == 101
    assert "length(CAST(sync_changes.payload AS BLOB))" in statements[-1]
    assert "sync_changes.payload," not in statements[-1]


def test_no_types_no_hidden_reads_and_candidate_authority(session):
    queries = BaselineQueries(session, "org", "loc", [])
    statements = []
    event.listen(
        session.get_bind(), "before_cursor_execute", lambda *args: statements.append(args[2])
    )
    assert queries.maxima() == {}
    assert queries.delta_candidates(0, 100) == []
    assert queries.scan_candidates("customer", None, "z") == []
    with pytest.raises(ValueError):
        queries.load(Candidate("customer", "a", "a", 1))
    assert not statements


def test_oversize_text_is_only_measured_in_metadata(session):
    session.add(
        ServiceOrderRecord(
            id="order",
            organization_id="org",
            location_id="loc",
            customer_id="a",
            state="received",
            reported_problem='😀\\"\n' * 400_000,
            priority="normal",
            created_at=NOW,
            updated_at=NOW,
            version=1,
        )
    )
    session.flush()
    queries = BaselineQueries(session, "org", "loc", ["service_order"])
    session.expunge_all()
    candidate = queries.scan_candidates("service_order", None, "z")[0]
    assert candidate.estimated_bytes > 1024 * 1024
    assert not session.identity_map


def test_preflight_keeps_large_fitting_and_escaped_unicode_records(session):
    value = '😀"\\\n\x01' * 25000
    session.add(
        ServiceOrderRecord(
            id="order",
            organization_id="org",
            location_id="loc",
            customer_id="a",
            state="received",
            reported_problem=value,
            priority="normal",
            created_at=NOW,
            updated_at=NOW,
            version=1,
        )
    )
    session.add(change(1, "service_order", payload={"reported_problem": value}))
    session.flush()
    queries = BaselineQueries(session, "org", "loc", ["service_order"])
    for candidate in [
        *queries.scan_candidates("service_order", None, "z"),
        *queries.delta_candidates(0, 1),
    ]:
        encoded = json.dumps(queries.load(candidate), ensure_ascii=False).encode()
        assert len(encoded) <= candidate.estimated_bytes < 1024 * 1024


def test_each_type_has_its_own_101_limit(session):
    session.add_all([change(i, "customer") for i in range(1, 105)])
    session.add_all([change(i, "bicycle") for i in range(105, 210)])
    session.add_all([change(i, "service_order") for i in range(210, 315)])
    session.flush()
    candidates = BaselineQueries(
        session, "org", "loc", ["customer", "bicycle", "service_order"]
    ).delta_candidates(0, 500)
    assert len(candidates) == 303
    assert [candidate.position for candidate in candidates] == sorted(
        candidate.position for candidate in candidates
    )


def test_load_rechecks_location_and_organization(session):
    session.add_all(
        [customer("foreign", organization="foreign"), customer("elsewhere", location="else")]
    )
    session.add(change(1, location="else"))
    session.flush()
    queries = BaselineQueries(session, "org", "loc", ["customer"])
    for candidate in [
        Candidate("customer", "foreign", "foreign", 100),
        Candidate("customer", "elsewhere", "elsewhere", 100),
        Candidate("customer", "a", 1, 100),
    ]:
        with pytest.raises(ValueError, match="candidate disappeared"):
            queries.load(candidate)
