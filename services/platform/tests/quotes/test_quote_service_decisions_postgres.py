"""Seven tiny PostgreSQL service decision/admission cases, prepared without execution.

Post-consent refusals cover reachable service behavior with current CAS values;
the transitioned order state also refuses, so they do not isolate the ledger gate.
"""

import json
from dataclasses import replace

import pytest
from cycling_workshop.inventory.models import InventoryMovementRecord
from cycling_workshop.quotes.service import QuoteServiceError
from cycling_workshop.service_orders.models import ServiceOrderRecord
from sqlalchemy import event, select, update
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_application_service import actors as actors
from test_quote_application_service import execute, totals
from test_quote_application_service_postgres import postgres_identity as postgres_identity
from test_quote_repository import counts, creation, decision, revision
from test_quote_repository import database as database
from test_quote_schema import TABLES, insert
from test_quote_service_restore_postgres import retained_service_rows
from test_quote_storage import NOW, uid

pytestmark = pytest.mark.parametrize("identity_migration_database", ["postgres"], indirect=True)


def assert_refused_without_writes(database, actors, command):
    before = retained_service_rows(database)
    inventory_query = select(InventoryMovementRecord.__table__).order_by(
        InventoryMovementRecord.movement_id
    )
    with Session(database) as session:
        inventory = list(session.execute(inventory_query).mappings())
        before_counts, before_totals = counts(session), totals(session)
    writes = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "SAVEPOINT")):
            writes.append(statement)

    event.listen(database, "before_cursor_execute", capture)
    try:
        with Session(database) as session:
            with pytest.raises(QuoteServiceError) as error:
                execute(session, actors, command)
            assert error.value.code == "quote_conflict"
            assert error.value.outcome_unknown is False
            assert error.value.cleanup_unverified is False
    finally:
        event.remove(database, "before_cursor_execute", capture)
    assert writes == []
    assert retained_service_rows(database) == before
    with Session(database) as session:
        assert list(session.execute(inventory_query).mappings()) == inventory
        assert counts(session) == before_counts
        assert totals(session) == before_totals


@pytest.mark.parametrize(
    "outcome,selected,state,action",
    [
        ("APPROVE", (10, 11), "AUTHORIZED", "authorize"),
        ("REJECT", (), "REJECTED", "reject"),
    ],
    ids=["approve", "reject"],
)
def test_service_decision_and_fresh_exact_replay(
    database, actors, outcome, selected, state, action
):
    command = decision(outcome=outcome, approved_line_ids=tuple(uid(value) for value in selected))
    with Session(database) as session:
        created = execute(session, actors, creation())
        assert created["receipt"]["effects"]["kind"] == "quote_only"
    before = retained_service_rows(database)
    with Session(database) as session:
        applied = execute(session, actors, command)
        assert applied["delivery"] == "applied"
        assert applied["order"]["state"] == state
        assert applied["order"]["version"] == 2
        assert applied["current"]["decision_sequence"] == 1
        assert applied["current_decision"] == {
            "decision_id": command.operation_id,
            "quote_id": uid(1),
            "sequence": 1,
            "outcome": outcome,
        }
        assert counts(session) == (1, 1, 2, 3)
        assert totals(session) == (2, 1, 1, 3)
        assert session.execute(select(InventoryMovementRecord.__table__)).all() == []
    after = retained_service_rows(database)
    effects = applied["receipt"]["effects"]
    assert effects["kind"] == "order_transition"
    assert effects["order_event_id"] == command.operation_id
    assert effects["resulting_order_version"] == 2
    assert effects["quote_outbox_id"] != effects["order_outbox_id"]
    operations = sorted(after["quote_operations"], key=lambda row: row["ordinal"])
    assert [row["order_effect_version"] for row in operations] == [None, 1]
    for field in (
        "quote_outbox_id",
        "order_event_id",
        "resulting_order_version",
        "change_cursor",
        "order_outbox_id",
    ):
        assert operations[1][field] == effects[field]
    assert operations[1]["operation_id"] == command.operation_id
    assert operations[1]["resulting_decision_sequence"] == 1
    assert after["service_order_events"] == [
        {
            "event_id": command.operation_id,
            "order_id": "order-a",
            "organization_id": "a",
            "from_state": "DIAGNOSIS",
            "to_state": state,
            "action": action,
            "actor_id": "actor-a",
            "note": None,
            "occurred_at": NOW,
        }
    ]
    assert after["quote_lineages"] == [{**before["quote_lineages"][0], "decision_sequence": 1}]
    assert after["service_orders"] == [
        {**row, "state": state, "version": 2, "updated_at": NOW}
        if row["id"] == "order-a"
        else row
        for row in before["service_orders"]
    ]
    for name in TABLES - {"quote_lineages"} | {"outbox_events"}:
        for row in before[name]:
            assert row in after[name]
    (change,) = after["sync_changes"]
    order_outbox = next(
        row for row in after["outbox_events"] if row["event_id"] == effects["order_outbox_id"]
    )
    quote_outbox = next(
        row for row in after["outbox_events"] if row["event_id"] == effects["quote_outbox_id"]
    )
    assert change["cursor"] == effects["change_cursor"]
    assert change["entity_version"] == 2
    assert change["payload"] == order_outbox["payload"]
    assert json.loads(change["payload"])["state"] == state
    assert order_outbox["event_type"] == "service_order.updated"
    assert quote_outbox["event_type"] == "quote.decision_recorded"
    writes = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "SAVEPOINT")):
            writes.append(statement)

    event.listen(database, "before_cursor_execute", capture)
    try:
        with Session(database) as session:
            replay = execute(session, actors, command, enabled=False)
            assert replay == {**applied, "delivery": "replayed"}
            assert counts(session) == (1, 1, 2, 3)
            assert totals(session) == (2, 1, 1, 3)
    finally:
        event.remove(database, "before_cursor_execute", capture)
    assert writes == []
    assert retained_service_rows(database) == after


@pytest.mark.parametrize("reason", ["prior_inventory", "progressed_history", "non_diagnosis"])
def test_service_enrollment_refuses_and_preserves_baseline(database, actors, reason):
    with database.begin() as connection:
        if reason == "prior_inventory":
            insert(
                connection,
                "inventory_movements",
                movement_id=uid(300),
                organization_id="a",
                location_id="location-a",
                product_id="product-a",
                kind="ADJUST",
                quantity=1,
                order_id="order-a",
                actor_id="actor-a",
                note=" Retained prior stock ",
                occurred_at=NOW,
            )
        elif reason == "progressed_history":
            insert(
                connection,
                "service_order_events",
                event_id=uid(301),
                order_id="order-a",
                organization_id="a",
                from_state="DIAGNOSIS",
                to_state="AUTHORIZED",
                action="authorize",
                actor_id="actor-a",
                note=" Retained progression ",
                occurred_at=NOW,
            )
        else:
            connection.execute(
                update(ServiceOrderRecord)
                .where(ServiceOrderRecord.id == "order-a")
                .values(state="INTAKE")
            )
    with Session(database) as session:
        assert counts(session) == (0, 0, 0, 0)
        assert totals(session) == (0, int(reason == "progressed_history"), 0, 0)
        expected_state = "INTAKE" if reason == "non_diagnosis" else "DIAGNOSIS"
        order = session.get(ServiceOrderRecord, "order-a")
        assert order.state == expected_state
        assert order.version == 1
    assert_refused_without_writes(database, actors, creation())


@pytest.mark.parametrize("kind", ["revision", "decision"])
def test_service_post_consent_refuses_current_cas_without_writes(database, actors, kind):
    with Session(database) as session:
        execute(session, actors, creation())
        applied = execute(session, actors, decision())
        assert applied["order"]["state"] == "AUTHORIZED"
        assert applied["order"]["version"] == 2
        assert applied["current"]["decision_sequence"] == 1
        assert counts(session) == (1, 1, 2, 3)
        assert totals(session) == (2, 1, 1, 3)
    if kind == "revision":
        command = revision(expected_order_version=2, expected_decision_sequence=1)
    else:
        command = replace(
            decision(decision_id=uid(101), expected_decision_sequence=1), expected_order_version=2
        )
    assert_refused_without_writes(database, actors, command)
