"""Forward-only cutover migration preservation on isolated databases."""

from io import StringIO
from uuid import UUID

import pytest
from alembic import command
from sqlalchemy import MetaData, Table, inspect, select, text
from sqlalchemy.exc import IntegrityError
from test_identity_migration import (
    NOW,
    _audit,
    _insert,
    _revision,
    _seed_tenant,
    _snapshot,
    _table,
    _user,
)
from test_identity_migration import identity_migration_database as identity_migration_database


def test_cutover_initializes_unique_canonical_incarnations_without_changing_tenancy(
    identity_migration_database,
):
    config, engine = identity_migration_database
    command.upgrade(config, "0009")
    _seed_tenant(engine)
    _seed_tenant(engine)
    before = _snapshot(engine, "organizations")
    command.upgrade(config, "head")
    assert _revision(engine) == "0013"
    after = _snapshot(engine, "organizations")
    for old, current in zip(before, after, strict=True):
        assert {key: current[key] for key in old} == old
        assert current["minimum_write_protocol"] == 0
        assert str(UUID(current["dataset_incarnation"])) == current["dataset_incarnation"]
    assert len({row["dataset_incarnation"] for row in after}) == 2


def history(engine):
    result = {}
    for name in inspect(engine).get_table_names():
        table = Table(name, MetaData(), autoload_with=engine)
        with engine.connect() as connection:
            result[name] = sorted(
                (dict(row) for row in connection.execute(select(table)).mappings()),
                key=repr,
            )
    return result


def seed_history(engine):
    org, location = _seed_tenant(engine)
    user = _user(org, location_id=location)
    _insert(engine, "users", user)
    _insert(engine, "identity_audit_events", _audit(org, actor_id=user["id"]))
    _insert(
        engine,
        "customers",
        dict(
            id="customer",
            organization_id=org,
            location_id=location,
            display_name="Preserve exact",
            email="fixture@example.invalid",
            phone=None,
            created_at=NOW,
            updated_at=NOW,
            version=8,
        ),
    )
    _insert(engine, "sync_mutation_receipts", receipt(org, location))
    _insert(
        engine,
        "sync_changes",
        dict(
            organization_id=org,
            location_id=location,
            entity_type="customer",
            entity_id="customer",
            operation="create",
            entity_version=8,
            occurred_at=NOW,
            payload={"display_name": "Preserve exact", "unknown": [1, True]},
        ),
    )
    _insert(
        engine,
        "outbox_events",
        dict(
            event_id="outbox-event",
            event_type="customer.created",
            aggregate_type="customer",
            aggregate_id="customer",
            organization_id=org,
            location_id=location,
            payload={"display_name": "Preserve exact", "unknown": [1, True]},
            occurred_at=NOW,
            published_at=None,
            attempts=3,
        ),
    )
    return org, location


def receipt(org, location, **overrides):
    return (
        dict(
            mutation_id="mutation",
            organization_id=org,
            location_id=location,
            entity_type="customer",
            entity_id="customer",
            operation="create",
            status="applied",
            entity_version=8,
            applied_at=NOW,
        )
        | overrides
    )


def test_upgrade_preserves_every_existing_column_value_and_legacy_receipt(
    identity_migration_database,
):
    config, engine = identity_migration_database
    command.upgrade(config, "0009")
    seed_history(engine)
    before = history(engine)
    command.upgrade(config, "0010")
    after = history(engine)
    for name, old in before.items():
        if name == "alembic_version":
            continue
        assert len(after[name]) == len(old)
        for row, original in zip(after[name], old, strict=True):
            assert {key: row[key] for key in original} == original
    legacy = after["sync_mutation_receipts"][0]
    assert all(legacy[key] is None for key in ("actor_id", "command_digest", "proof_version"))
    assert _revision(engine) == "0010"


@pytest.mark.parametrize("state", ["empty", "legacy", "active"])
def test_downgrade_always_refuses_without_schema_revision_or_history_changes(
    identity_migration_database, state
):
    config, engine = identity_migration_database
    command.upgrade(config, "0009")
    if state != "empty":
        organization_id, _ = seed_history(engine)
    command.upgrade(config, "0010")
    if state == "active":
        with engine.begin() as connection:
            connection.execute(text("UPDATE organizations SET minimum_write_protocol=1"))
            connection.execute(
                text(
                    "UPDATE sync_mutation_receipts SET actor_id='original-actor', "
                    "command_digest=:digest, proof_version=1"
                ),
                {"digest": "a" * 64},
            )
        _insert(
            engine,
            "identity_audit_events",
            _audit(
                organization_id, target_type="organization", action="organization.cutover_activated"
            ),
        )
    before = history(engine)
    columns = {name: inspect(engine).get_columns(name) for name in before}
    with pytest.raises(RuntimeError, match="forward-only"):
        command.downgrade(config, "0009")
    assert history(engine) == before
    assert _revision(engine) == "0010"
    for name in before:
        assert [
            (item["name"], str(item["type"]), item["nullable"], item["default"])
            for item in inspect(engine).get_columns(name)
        ] == [
            (item["name"], str(item["type"]), item["nullable"], item["default"])
            for item in columns[name]
        ]


@pytest.mark.parametrize(
    "bad",
    [
        {"actor_id": "actor"},
        {"command_digest": "a" * 64},
        {"proof_version": 1},
        {"actor_id": "actor", "command_digest": "a" * 64},
        {"actor_id": "actor", "command_digest": "a" * 64, "proof_version": 2},
        {"actor_id": "actor", "command_digest": "A" * 64, "proof_version": 1},
        {"actor_id": "actor", "command_digest": "g" * 64, "proof_version": 1},
        {"actor_id": "actor", "command_digest": "a" * 63, "proof_version": 1},
    ],
)
def test_proof_constraints_refuse_partial_unknown_and_noncanonical_rows(
    identity_migration_database, bad
):
    config, engine = identity_migration_database
    command.upgrade(config, "0010")
    with pytest.raises(IntegrityError):
        _insert(engine, "sync_mutation_receipts", receipt("org", "location", **bad))
    assert history(engine)["sync_mutation_receipts"] == []
    _insert(
        engine,
        "sync_mutation_receipts",
        receipt("org", "location", actor_id="actor", command_digest="a" * 64, proof_version=1),
    )


@pytest.mark.parametrize(
    "invalid",
    [
        {"minimum_write_protocol": -1},
        {"minimum_write_protocol": 2},
        {"minimum_write_protocol": None},
        {"dataset_incarnation": None},
        {"dataset_incarnation": "not-an-incarnation"},
        {"dataset_incarnation": "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"},
        {"dataset_incarnation": "1111111--1111-1111-1111-111111111111"},
    ],
)
def test_metadata_constraints_fail_closed(identity_migration_database, invalid):
    config, engine = identity_migration_database
    command.upgrade(config, "0010")
    with pytest.raises(IntegrityError):
        _insert(
            engine,
            "organizations",
            dict(
                id="org",
                name="Synthetic",
                minimum_write_protocol=0,
                dataset_incarnation="11111111-1111-1111-1111-111111111111",
            )
            | invalid,
        )


def test_organization_audit_and_all_append_only_guards_survive_upgrade(identity_migration_database):
    config, engine = identity_migration_database
    command.upgrade(config, "0009")
    org, _ = seed_history(engine)
    command.upgrade(config, "0010")
    organization_audit = _audit(
        org, target_type="organization", action="organization.cutover_activated"
    )
    _insert(engine, "identity_audit_events", organization_audit)
    before = _snapshot(engine, "identity_audit_events")
    statements = [
        "UPDATE identity_audit_events SET action='rewritten'",
        "DELETE FROM identity_audit_events",
    ]
    if engine.dialect.name == "postgresql":
        statements.append("TRUNCATE identity_audit_events")
    for statement in statements:
        with pytest.raises(IntegrityError, match="append-only"), engine.begin() as connection:
            connection.execute(text(statement))
    if engine.dialect.name == "sqlite":
        with pytest.raises(IntegrityError, match="append-only"), engine.begin() as connection:
            connection.execute(
                _table(engine, "identity_audit_events").insert().prefix_with("OR REPLACE"),
                organization_audit | {"action": "rewrite"},
            )
    assert _snapshot(engine, "identity_audit_events") == before


def test_offline_downgrade_refuses_before_any_ddl(identity_migration_database):
    config, _ = identity_migration_database
    output = StringIO()
    config.output_buffer = output
    with pytest.raises(RuntimeError, match="forward-only"):
        command.downgrade(config, "0010:0009", sql=True)
    assert "ALTER TABLE" not in output.getvalue()
    assert "DROP TABLE" not in output.getvalue()
    assert "DELETE FROM" not in output.getvalue()
