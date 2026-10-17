"""Valid quote-only 0012 history survives 0013 and disabled-command replay.

Prepared, unexecuted PostgreSQL specimen. Legacy rows are built from current
pure codecs and inserted through reflected 0012 tables, never newer mapped rows
or old application source. This is neither a restore nor a DDL-failure test.
"""

import json
from datetime import UTC, datetime

import pytest
from alembic import command as migrate
from cycling_workshop.identity.cutover import WriteAdmission
from cycling_workshop.identity.domain import Principal
from cycling_workshop.quotes.commands import (
    CreateQuoteCommand,
    RecordQuoteDecisionCommand,
    command_from_proof,
    operation_proof,
)
from cycling_workshop.quotes.decisions import DecisionCommand, DecisionEvidence
from cycling_workshop.quotes.domain import LaborLine
from cycling_workshop.quotes.reconstruction import (
    advance,
    event_payload,
    event_type,
    logical_record,
)
from cycling_workshop.quotes.service import QuoteDeadline, QuoteService
from cycling_workshop.quotes.storage import (
    decode_entry,
    decode_quote,
    encode_entry,
    encode_lines,
    encode_quote,
    validate_history_bytes,
)
from sqlalchemy import JSON, MetaData, Table, Text, func, select, text
from sqlalchemy import cast as sql_cast
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_schema import seed_base

pytestmark = pytest.mark.parametrize("identity_migration_database", ["postgres"], indirect=True)

NOW = datetime(2026, 10, 17, 12, tzinfo=UTC)
GRANTS = frozenset(
    {"orders.read", "orders.write", "quotes.read", "quotes.write", "quotes.authorize"}
)
TABLE_NAMES = (
    "quote_lineages",
    "quote_revisions",
    "quote_lines",
    "quote_line_targets",
    "quote_decisions",
    "quote_operations",
    "outbox_events",
    "service_orders",
    "service_order_events",
    "sync_changes",
)


def uid(number):
    return f"019a0000-0000-7000-8000-{number:012x}"


def commands():
    created = CreateQuoteCommand(
        operation_id=uid(200),
        quote_id=uid(1),
        organization_id="a",
        location_id="location-a",
        order_id="order-a",
        actor_id="actor-a",
        expected_order_version=1,
        currency="MXN",
        lines=(LaborLine(uid(10), "Synthetic labor", 60, 120),),
    )
    decided = RecordQuoteDecisionCommand(
        DecisionCommand(
            decision_id=uid(100),
            organization_id="a",
            location_id="location-a",
            order_id="order-a",
            lineage_id=created.lineage_id,
            quote_id=created.quote_id,
            quote_version=1,
            expected_head_id=created.quote_id,
            expected_head_version=1,
            expected_decision_sequence=0,
            recorded_by_actor_id="actor-a",
            mode="initial",
            outcome="APPROVE",
            approved_line_ids=(uid(10),),
            evidence=DecisionEvidence("customer", "customer-a", "phone", NOW),
        ),
        expected_order_version=1,
    )
    return created, decided


def legacy_snapshot(connection, tables):
    """Read only pre-upgrade columns, preserving raw JSON rather than decoding."""
    result = {}
    for name, table in tables.items():
        columns = [
            sql_cast(column, Text).label(column.name)
            if isinstance(column.type, JSON)
            else column
            for column in table.columns
        ]
        result[name] = [
            dict(row)
            for row in connection.execute(
                select(*columns).order_by(*table.primary_key.columns)
            ).mappings()
        ]
    return result


def seed_valid_0012_history(connection, tables):
    created, decided = commands()
    first = advance(None, created, NOW)
    final = advance(first, decided, NOW)
    logical = [logical_record(created, first), logical_record(decided, final)]
    validate_history_bytes(logical)
    for operation, record in zip((created, decided), logical, strict=True):
        assert record["proof"] == operation_proof(operation)
        assert command_from_proof(record["proof"]) == operation

    head = final.history.head
    quote_document = encode_quote(head)
    entry = final.entries[-1]
    entry_document = encode_entry(entry)
    assert decode_quote(quote_document) == head
    assert decode_entry(entry_document) == entry
    assert logical[0]["result"] == quote_document
    assert logical[1]["result"] == {
        key: value for key, value in entry_document.items() if key != "command"
    }

    connection.execute(
        tables["quote_lineages"].insert().values(
            lineage_id=created.lineage_id,
            organization_id=created.organization_id,
            location_id=created.location_id,
            order_id=created.order_id,
            currency=created.currency,
            root_quote_id=created.quote_id,
            head_quote_id=head.quote_id,
            head_version=head.version,
            decision_sequence=final.sequence,
        )
    )
    connection.execute(
        tables["quote_revisions"].insert().values(
            quote_id=head.quote_id,
            lineage_id=created.lineage_id,
            organization_id=head.organization_id,
            version=head.version,
            predecessor_id=None,
            created_at=head.created_at,
            actor_id=created.actor_id,
            subtotal_minor=head.totals.subtotal_minor,
            discount_minor=head.totals.discount_minor,
            tax_minor=head.totals.tax_minor,
            total_minor=head.totals.total_minor,
            line_amounts=quote_document["totals"]["line_amounts"],
        )
    )
    connection.execute(
        tables["quote_lines"].insert().values(
            revision_id=head.quote_id,
            lineage_id=created.lineage_id,
            organization_id=head.organization_id,
            position=0,
            **encode_lines(head.lines)[0],
        )
    )
    connection.execute(
        tables["quote_decisions"].insert().values(
            decision_id=decided.operation_id,
            lineage_id=decided.lineage_id,
            organization_id=decided.organization_id,
            quote_id=decided.quote_id,
            quote_version=decided.command.quote_version,
            sequence=entry.sequence,
            actor_id=decided.actor_id,
            recorded_at=NOW,
            reason=decided.command.reason,
            supersedes_entry_id=decided.command.supersedes_entry_id,
            line_decisions=entry_document["line_decisions"],
            pricing=entry_document["pricing"],
        )
    )
    for operation, ledger, record, outbox_id in zip(
        (created, decided), (first, final), logical, (uid(300), uid(301)), strict=True
    ):
        connection.execute(
            tables["outbox_events"].insert().values(
                event_id=outbox_id,
                event_type=event_type(operation),
                aggregate_type="quote",
                aggregate_id=operation.lineage_id,
                organization_id=operation.organization_id,
                location_id=operation.location_id,
                payload=event_payload(operation, ledger),
                occurred_at=NOW,
                published_at=None,
                attempts=0,
            )
        )
        connection.execute(
            tables["quote_operations"].insert().values(
                organization_id=operation.organization_id,
                operation_id=operation.operation_id,
                lineage_id=operation.lineage_id,
                kind=record["proof"]["kind"],
                quote_id=ledger.history.head.quote_id,
                quote_version=ledger.history.head.version,
                resulting_decision_sequence=ledger.sequence,
                ordinal=ledger.history.head.version + ledger.sequence,
                decision_id=operation.operation_id
                if isinstance(operation, RecordQuoteDecisionCommand)
                else None,
                proof_version=1,
                proof=record["proof"],
                actor_id=operation.actor_id,
                recorded_at=NOW,
                quote_outbox_id=outbox_id,
                order_event_id=None,
                resulting_order_version=None,
                change_cursor=None,
                order_outbox_id=None,
            )
        )
    return decided, {
        "operation_id": decided.operation_id,
        "kind": "decision",
        "ordinal": 2,
        "quote_id": head.quote_id,
        "quote_version": head.version,
        "decision_id": decided.operation_id,
        "decision_sequence": entry.sequence,
        "recorded_at": NOW.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "recorded_by_actor_id": decided.actor_id,
        "totals": {
            "subtotal_minor": entry.pricing.subtotal_minor,
            "discount_minor": entry.pricing.discount_minor,
            "tax_minor": entry.pricing.tax_minor,
            "total_minor": entry.pricing.total_minor,
        },
        "effects": {
            "kind": "quote_only",
            "quote_outbox_id": uid(301),
            "order_event_id": None,
            "resulting_order_version": None,
            "change_cursor": None,
            "order_outbox_id": None,
        },
    }


def test_valid_quote_only_0012_upgrade_replays_without_inventing_transition(
    identity_migration_database,
):
    config, engine = identity_migration_database
    assert engine.dialect.name == "postgresql" and engine.dialect.driver == "psycopg"
    migrate.upgrade(config, "0012")
    seed_base(engine)
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0012"
        assert 180000 <= int(connection.scalar(text("SHOW server_version_num"))) < 190000
        assert connection.scalar(text("SHOW server_encoding")) == "UTF8"
        assert connection.scalar(text("SHOW client_encoding")) == "UTF8"
        tables = {
            name: Table(name, MetaData(), autoload_with=connection, resolve_fks=False)
            for name in TABLE_NAMES
        }
        assert "order_effect_version" not in tables["quote_operations"].c
        for name in ("sync_changes", "outbox_events"):
            assert "order_payload_raw_octets" not in tables[name].c
        users = Table("users", MetaData(), autoload_with=connection, resolve_fks=False)
        organizations = Table(
            "organizations", MetaData(), autoload_with=connection, resolve_fks=False
        )
        connection.execute(
            users.update().where(users.c.id == "actor-a").values(capabilities=sorted(GRANTS))
        )
        connection.execute(
            organizations.update().where(organizations.c.id == "a").values(minimum_write_protocol=1)
        )
        decided, expected_receipt = seed_valid_0012_history(connection, tables)
        before = legacy_snapshot(connection, tables)
    assert len(before["quote_operations"]) == 2
    assert len(before["outbox_events"]) == 2
    assert before["service_order_events"] == before["sync_changes"] == []
    assert all(
        row[key] is None
        for row in before["quote_operations"]
        for key in ("order_event_id", "resulting_order_version", "change_cursor", "order_outbox_id")
    )

    migrate.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0013"
        assert legacy_snapshot(connection, tables) == before
        versions = connection.scalars(
            text("SELECT order_effect_version FROM quote_operations ORDER BY ordinal")
        ).all()
        assert versions == [None, None]
        persisted = connection.execute(
            select(users.c.session_version, users.c.capabilities, organizations.c.dataset_incarnation)
            .select_from(
                users.join(organizations, users.c.organization_id == organizations.c.id)
            )
            .where(users.c.id == "actor-a", organizations.c.id == "a")
        ).one()
        assert frozenset(persisted.capabilities) == GRANTS
        principal = Principal(
            "actor-a",
            "a",
            "location-a",
            GRANTS,
            session_version=persisted.session_version,
            dataset_incarnation=persisted.dataset_incarnation,
        )

    # No Session/ORM state from the old schema exists. The actual service must
    # reauthorize, reconstruct the full history and recognize the exact retry.
    with Session(engine) as session:
        assert not session.in_transaction()
        replay = json.loads(
            QuoteService(session, commands_enabled=False, now=lambda: NOW).execute(
                decided,
                principal=principal,
                admission=WriteAdmission.for_fixtures(1, enabled=True),
                deadline=QuoteDeadline.start(),
            )
        )
        assert replay["delivery"] == "replayed"
        assert replay["receipt"] == expected_receipt
        assert replay["order"]["state"] == "DIAGNOSIS" and replay["order"]["version"] == 1
        assert replay["current_decision"]["decision_id"] == decided.operation_id
        assert replay["current_decision"]["outcome"] == "APPROVE"
        assert not session.in_transaction()

    with engine.connect() as connection:
        assert legacy_snapshot(connection, tables) == before
        assert tuple(
            connection.scalar(select(func.count()).select_from(tables[name]))
            for name in (
                "quote_operations",
                "service_order_events",
                "sync_changes",
                "outbox_events",
            )
        ) == (2, 0, 0, 2)
        versions = connection.scalars(
            text("SELECT order_effect_version FROM quote_operations ORDER BY ordinal")
        ).all()
        assert versions == [None, None]
        counts = connection.scalars(
            text("SELECT order_payload_raw_octets FROM outbox_events ORDER BY event_id")
        ).all()
        assert counts == [None, None]
