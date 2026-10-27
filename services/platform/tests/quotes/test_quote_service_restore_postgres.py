"""UNEXECUTED candidate: one tiny PostgreSQL service-effect restore and replay.

The existing fixture owns two disposable databases. This case uses real service
admission, dump, restore and explicit target recovery; it does not qualify HTTP,
production-size recovery, concurrency, worker delivery or client reconciliation.
"""

from __future__ import annotations

import json
from hashlib import file_digest
from uuid import UUID

import pytest
from alembic import command as migrate
from cycling_workshop.api.errors import ApiError
from cycling_workshop.db.base import Base
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.identity.cutover import WriteAdmission
from cycling_workshop.identity.cutover_cli import recover_cutover
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.security import SessionTokenService
from cycling_workshop.quotes.service import QuoteDeadline, QuoteService
from cycling_workshop.service_orders.models import ServiceOrderRecord
from cycling_workshop.settings import Settings
from cycling_workshop.tenancy.models import OrganizationRecord
from sqlalchemy import JSON, Text, bindparam, cast, create_engine, select, update
from sqlalchemy.orm import Session
from test_backup_postgres_integration import disposable_databases as disposable_databases
from test_identity_migration import _config
from test_quote_application_service import GRANTS, totals
from test_quote_effect_metadata import assert_generated_schema
from test_quote_repository import creation, decision
from test_quote_schema import seed_base
from test_quote_storage import NOW

from scripts.database.backup_postgres import (
    create_backup_bundle,
    restore_backup_bundle,
    verify_backup_bundle,
)

RETAINED_TABLES = (
    "quote_lineages",
    "quote_revisions",
    "quote_lines",
    "quote_line_targets",
    "quote_decisions",
    "quote_operations",
    "service_orders",
    "service_order_events",
    "sync_changes",
    "outbox_events",
)


def retained_service_rows(engine):
    """Keep all ten tables' columns, including raw JSON and generated metadata."""
    retained = {}
    with engine.connect() as connection:
        for name in RETAINED_TABLES:
            table = Base.metadata.tables[name]
            columns = [
                cast(column, Text).label(column.name) if isinstance(column.type, JSON) else column
                for column in table.columns
            ]
            retained[name] = [
                dict(row)
                for row in connection.execute(
                    select(*columns).order_by(*table.primary_key.columns)
                ).mappings()
            ]
    return retained


def assert_retained_service_effects(rows, created, applied):
    operations = sorted(rows["quote_operations"], key=lambda row: row["ordinal"])
    assert [row["order_effect_version"] for row in operations] == [None, 1]
    assert [row["operation_id"] for row in operations] == [
        created["receipt"]["operation_id"],
        applied["receipt"]["operation_id"],
    ]
    effects = applied["receipt"]["effects"]
    for name in (
        "quote_outbox_id",
        "order_event_id",
        "resulting_order_version",
        "change_cursor",
        "order_outbox_id",
    ):
        assert operations[1][name] == effects[name]
    assert operations[0]["quote_outbox_id"] == created["receipt"]["effects"]["quote_outbox_id"]
    (change,) = rows["sync_changes"]
    (event,) = rows["service_order_events"]
    (order_outbox,) = [
        row for row in rows["outbox_events"] if row["aggregate_type"] == "service_order"
    ]
    assert change["entity_type"] == "service_order"
    assert change["cursor"] == effects["change_cursor"]
    assert event["event_id"] == effects["order_event_id"]
    assert order_outbox["event_id"] == effects["order_outbox_id"]
    raw = change["payload"]
    assert type(raw) is str and "Synthetic é🚲" in raw
    assert raw == order_outbox["payload"]
    for row in (change, order_outbox):
        assert type(row["order_payload_raw_octets"]) is int
        assert row["order_payload_raw_octets"] == len(raw.encode("utf-8"))
    quote_outboxes = [row for row in rows["outbox_events"] if row["aggregate_type"] == "quote"]
    assert len(quote_outboxes) == 2
    assert all(row["order_payload_raw_octets"] is None for row in quote_outboxes)
    original_outbox = next(
        row
        for row in quote_outboxes
        if row["event_id"] == created["receipt"]["effects"]["quote_outbox_id"]
    )
    assert original_outbox["attempts"] == 2 and original_outbox["published_at"] == NOW
    order = next(row for row in rows["service_orders"] if row["id"] == "order-a")
    assert order["state"] == "AUTHORIZED" and order["version"] == 2
    assert order["reported_problem"] == "Synthetic é🚲"


def test_real_restore_preserves_version_one_service_effects_and_fresh_replay(
    disposable_databases, tmp_path
):
    source_url, target_url = disposable_databases
    # The owning fixture clears migration URL overrides before yielding this pair.
    migrate.upgrade(_config(source_url), "head")
    source = create_engine(source_url, hide_parameters=True)
    target = None
    tokens = SessionTokenService(
        secret="synthetic-service-restore-signing-key-for-tests-only", clock=lambda: NOW
    )
    admission = WriteAdmission(protocol=1, enabled=True, tokens=tokens)
    commands = (creation(), decision())
    try:
        seed_base(source)
        with Session(source) as session:
            session.get(UserRecord, "actor-a").capabilities = sorted(GRANTS)
            organization = session.get(OrganizationRecord, "a")
            organization.minimum_write_protocol = 1
            incarnation = organization.dataset_incarnation
            assert str(UUID(incarnation)) == incarnation
            session.get(ServiceOrderRecord, "order-a").reported_problem = "Synthetic é🚲"
            session.commit()
        old_token = tokens.issue(
            Principal("actor-a", "a", "location-a", GRANTS, dataset_incarnation=incarnation)
        )
        old_principal = tokens.decode(old_token)
        original = []
        for command in commands:
            # Each call starts clean and lets the service own its commit.
            with Session(source) as session:
                original.append(
                    json.loads(
                        QuoteService(session, commands_enabled=True, now=lambda: NOW).execute(
                            command,
                            principal=old_principal,
                            admission=admission,
                            deadline=QuoteDeadline.start(),
                        )
                    )
                )
        created, applied = original
        assert created["delivery"] == applied["delivery"] == "applied"
        assert created["receipt"]["effects"]["kind"] == "quote_only"
        effects = applied["receipt"]["effects"]
        assert effects["kind"] == "order_transition"
        assert effects["resulting_order_version"] == 2
        assert effects["quote_outbox_id"] != effects["order_outbox_id"]
        assert applied["order"]["state"] == "AUTHORIZED"
        assert applied["order"]["version"] == 2
        with Session(source) as session:
            assert totals(session) == (2, 1, 1, 3)
            outbox = session.get(OutboxRecord, created["receipt"]["effects"]["quote_outbox_id"])
            outbox.attempts, outbox.published_at = 2, NOW
            organization = session.get(OrganizationRecord, "a")
            assert organization.minimum_write_protocol == 1
            assert organization.dataset_incarnation == incarnation
            session.commit()
        before = retained_service_rows(source)
        assert_retained_service_effects(before, created, applied)
        assert_generated_schema(source)
        source.dispose()

        # No target application engine or connection exists before the real restore.
        bundle = create_backup_bundle(source_url, tmp_path / "service-generation")
        verified = verify_backup_bundle(bundle)
        assert verified["status"] == "integrity_checked_not_restored"
        manifest = verified["manifest"]
        assert manifest["database"]["schema_revisions"] == ["0013"]
        assert manifest["database"]["postgres_version_num"] == 180004
        assert manifest["restore_tested"] is False
        archive = bundle / manifest["archive"]["file"]
        assert 0 < archive.stat().st_size == manifest["archive"]["bytes"]
        with archive.open("rb") as stream:
            assert file_digest(stream, "sha256").hexdigest() == manifest["archive"]["sha256"]
        restored = restore_backup_bundle(bundle, target_url, confirm_empty_target=True)
        assert restored["status"] == "database_restore_checked"
        assert restored["backup_sha256"] == manifest["archive"]["sha256"]
        assert restored["schema_revisions"] == ["0013"]
        assert restored["tables_checked"] == len(manifest["database"]["tables"])
        assert restored["application_smoke_tested"] is False
        assert json.loads((bundle / "manifest.json").read_text(encoding="utf-8")) == manifest

        target = create_engine(target_url, hide_parameters=True)
        assert_generated_schema(target)
        after_restore = retained_service_rows(target)
        assert after_restore == before
        assert_retained_service_effects(after_restore, created, applied)
        with Session(target) as session:
            organization = session.get(OrganizationRecord, "a")
            assert organization.minimum_write_protocol == 1
            assert organization.dataset_incarnation == incarnation
            assert totals(session) == (2, 1, 1, 3)

        # Ordinary SQL corruption in a fully restored retained pair must stop
        # recovery before incarnation/audit changes. The fixture alone restores
        # the exact original bytes afterward; the production gate never repairs.
        effect_outbox_id = applied["receipt"]["effects"]["order_outbox_id"]
        original_raw = next(
            row["payload"] for row in before["outbox_events"] if row["event_id"] == effect_outbox_id
        )
        damaged = json.loads(original_raw)
        damaged["reported_problem"] = "Synthetic retained mismatch"
        with target.begin() as connection:
            connection.execute(
                update(OutboxRecord)
                .where(OutboxRecord.event_id == effect_outbox_id)
                .values(payload=damaged)
            )
        corrupted = retained_service_rows(target)
        with pytest.raises(ApiError) as refused:
            recover_cutover(
                Settings(environment="test", database_url=target_url, cutover_enabled=True),
                organization_id="a",
                expected_incarnation=incarnation,
            )
        assert refused.value.code == "quote_integrity_failed"
        assert retained_service_rows(target) == corrupted
        with Session(target) as session:
            assert session.get(OrganizationRecord, "a").dataset_incarnation == incarnation
        with target.begin() as connection:
            connection.execute(
                update(OutboxRecord)
                .where(OutboxRecord.event_id == effect_outbox_id)
                .values(payload=cast(bindparam("retained_raw", type_=Text), JSON)),
                {"retained_raw": original_raw},
            )
        assert retained_service_rows(target) == before

        # Recovery is explicit and target-only; no prior operation rotates identity.
        recovery = recover_cutover(
            Settings(environment="test", database_url=target_url, cutover_enabled=True),
            organization_id="a",
            expected_incarnation=incarnation,
        )
        fresh_incarnation = recovery["dataset_incarnation"]
        assert recovery["changed"] is True
        assert type(fresh_incarnation) is str
        assert str(UUID(fresh_incarnation)) == fresh_incarnation != incarnation
        assert recovery == {
            "organization_id": "a",
            "minimum_write_protocol": 1,
            "dataset_incarnation": fresh_incarnation,
            "changed": True,
        }
        with Session(target) as session:
            with pytest.raises(ApiError) as stale:
                QuoteService(session, commands_enabled=False, now=lambda: NOW).execute(
                    commands[0],
                    principal=old_principal,
                    admission=admission,
                    deadline=QuoteDeadline.start(),
                )
            assert stale.value.code == "invalid_session"
        fresh_token = tokens.issue(
            Principal("actor-a", "a", "location-a", GRANTS, dataset_incarnation=fresh_incarnation)
        )
        fresh_principal = tokens.decode(fresh_token)
        for command, expected in zip(commands, original, strict=True):
            with Session(target) as session:
                replay = json.loads(
                    QuoteService(session, commands_enabled=False, now=lambda: NOW).execute(
                        command,
                        principal=fresh_principal,
                        admission=admission,
                        deadline=QuoteDeadline.start(),
                    )
                )
            assert replay["delivery"] == "replayed"
            assert replay["receipt"] == expected["receipt"]
            assert replay["current"] == applied["current"]
            assert replay["current_decision"] == applied["current_decision"]
            assert replay["order"] == applied["order"]
        with Session(target) as session:
            assert totals(session) == (2, 1, 1, 3)
            organization = session.get(OrganizationRecord, "a")
            assert organization.minimum_write_protocol == 1
            assert organization.dataset_incarnation == fresh_incarnation
        after_replay = retained_service_rows(target)
        assert after_replay == before
        assert_retained_service_effects(after_replay, created, applied)
        assert retained_service_rows(source) == before
        with Session(source) as session:
            organization = session.get(OrganizationRecord, "a")
            assert organization.minimum_write_protocol == 1
            assert organization.dataset_incarnation == incarnation
    finally:
        source.dispose()
        if target is not None:
            target.dispose()
