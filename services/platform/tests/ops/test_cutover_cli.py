"""Operator controls use only disposable installation fixtures."""

import json
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from cycling_workshop.api.errors import ApiError
from cycling_workshop.cli import main
from cycling_workshop.identity.audit import IdentityAuditRecord, append_audit
from cycling_workshop.identity.cutover_cli import activate_cutover, cutover_status, recover_cutover
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.settings import Settings
from cycling_workshop.tenancy.models import OrganizationRecord
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session


@pytest.fixture
def installation(tmp_path, monkeypatch):
    url = f"sqlite+pysqlite:///{tmp_path / 'cutover.sqlite3'}"
    engine = create_engine(url)
    monkeypatch.delenv("OCWP_DATABASE_URL", raising=False)
    monkeypatch.delenv("OCWP_DATABASE_URL_FILE", raising=False)
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "0010")
    with Session(engine) as session:
        session.add_all([OrganizationRecord(id=name, name=name) for name in ("org", "other")])
        session.flush()
        session.add(
            UserRecord(
                id="user",
                organization_id="org",
                location_id=None,
                username="user",
                display_name="Synthetic",
                password_hash="preserve-fixture",
                capabilities=["*"],
                is_active=True,
                is_owner=True,
                version=7,
                session_version=9,
            )
        )
        session.commit()
    monkeypatch.setenv("OCWP_DATABASE_URL", url)
    monkeypatch.setenv("OCWP_ENVIRONMENT", "test")
    monkeypatch.setenv("OCWP_CUTOVER_ENABLED", "true")
    yield engine, Settings(environment="test", database_url=url, cutover_enabled=True)
    engine.dispose()


def audit_rows(engine):
    with Session(engine) as session:
        return list(session.scalars(select(IdentityAuditRecord)))


def test_activation_is_explicit_enabled_and_idempotent_with_honest_audit(installation):
    engine, settings = installation
    initial = cutover_status(settings, organization_id="org")
    assert initial["minimum_write_protocol"] == 0
    with pytest.raises(ApiError) as denied:
        activate_cutover(replace(settings, cutover_enabled=False), organization_id="org")
    assert denied.value.code == "cutover_composition_disabled"
    assert audit_rows(engine) == []
    result = activate_cutover(settings, organization_id="org")
    assert result["changed"] is True and result["minimum_write_protocol"] == 1
    assert result["dataset_incarnation"] == initial["dataset_incarnation"]
    assert activate_cutover(settings, organization_id="org")["changed"] is False
    rows = audit_rows(engine)
    assert len(rows) == 1
    assert rows[0].target_type == "organization" and rows[0].target_id is None
    assert rows[0].actor_id is None
    assert rows[0].before["minimum_write_protocol"] == 0
    assert rows[0].after["minimum_write_protocol"] == 1
    assert cutover_status(settings, organization_id="other")["minimum_write_protocol"] == 0


def test_recovery_requires_active_floor_and_exact_precondition(installation):
    engine, settings = installation
    initial = cutover_status(settings, organization_id="org")["dataset_incarnation"]
    with pytest.raises(ApiError) as refused:
        recover_cutover(settings, organization_id="org", expected_incarnation=initial)
    assert refused.value.code == "cutover_not_active"
    activate_cutover(settings, organization_id="org")
    with pytest.raises(ApiError) as refused:
        recover_cutover(settings, organization_id="org", expected_incarnation=str(uuid4()))
    assert refused.value.code == "incarnation_precondition_failed"
    with Session(engine) as session:
        user = session.get(UserRecord, "user")
        before = {
            column.name: getattr(user, column.name) for column in UserRecord.__table__.columns
        }
    other = cutover_status(settings, organization_id="other")
    recovered = recover_cutover(settings, organization_id="org", expected_incarnation=initial)
    assert recovered["dataset_incarnation"] != initial
    assert str(UUID(recovered["dataset_incarnation"])) == recovered["dataset_incarnation"]
    assert recovered["minimum_write_protocol"] == 1
    with pytest.raises(ApiError) as refused:
        recover_cutover(settings, organization_id="org", expected_incarnation=initial)
    assert refused.value.code == "incarnation_precondition_failed"
    assert len(audit_rows(engine)) == 2
    with Session(engine) as session:
        user = session.get(UserRecord, "user")
        assert {
            column.name: getattr(user, column.name) for column in UserRecord.__table__.columns
        } == before
    assert cutover_status(settings, organization_id="other") == other
    assert (
        cutover_status(settings, organization_id="org")["latest_maintenance_audit"]["action"]
        == "organization.dataset_recovered"
    )


def test_recovery_audit_failure_rolls_back_rotation(installation, monkeypatch):
    engine, settings = installation
    active = activate_cutover(settings, organization_id="org")

    def fail(*args, **kwargs):
        append_audit(*args, **kwargs)
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr("cycling_workshop.identity.cutover_cli.append_audit", fail)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        recover_cutover(
            settings, organization_id="org", expected_incarnation=active["dataset_incarnation"]
        )
    assert (
        cutover_status(settings, organization_id="org")["dataset_incarnation"]
        == active["dataset_incarnation"]
    )
    assert len(audit_rows(engine)) == 1


def test_cli_reports_status_and_requires_recovery_precondition(installation, capsys):
    assert main(["cutover", "status", "--organization-id", "org"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["minimum_write_protocol"] == 0
    with pytest.raises(SystemExit) as failure:
        main(["cutover", "recover", "--organization-id", "org"])
    assert failure.value.code == 2
    assert main(["cutover", "activate", "--organization-id", "missing"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "compatibility_state_invalid"


@pytest.mark.parametrize(
    "value",
    [
        None,
        "not-a-uuid",
        "11111111111111111111111111111111",
        "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA",
    ],
)
def test_recovery_rejects_noncanonical_precondition_without_changes(installation, value):
    engine, settings = installation
    active = activate_cutover(settings, organization_id="org")
    with pytest.raises(ApiError) as failure:
        recover_cutover(settings, organization_id="org", expected_incarnation=value)
    assert failure.value.code == "invalid_incarnation"
    assert (
        cutover_status(settings, organization_id="org")["dataset_incarnation"]
        == active["dataset_incarnation"]
    )
    assert len(audit_rows(engine)) == 1


def test_recovery_uuid_collision_refuses_without_a_second_audit(installation, monkeypatch):
    engine, settings = installation
    active = activate_cutover(settings, organization_id="org")
    monkeypatch.setattr(
        "cycling_workshop.identity.cutover_cli.uuid4", lambda: UUID(active["dataset_incarnation"])
    )
    with pytest.raises(ApiError) as failure:
        recover_cutover(
            settings, organization_id="org", expected_incarnation=active["dataset_incarnation"]
        )
    assert failure.value.code == "incarnation_collision"
    assert len(audit_rows(engine)) == 1


def test_activation_audit_failure_rolls_back_floor(installation, monkeypatch):
    engine, settings = installation

    def fail(*args, **kwargs):
        append_audit(*args, **kwargs)
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr("cycling_workshop.identity.cutover_cli.append_audit", fail)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        activate_cutover(settings, organization_id="org")
    assert cutover_status(settings, organization_id="org")["minimum_write_protocol"] == 0
    assert audit_rows(engine) == []


def test_cutover_cli_refuses_fallback_database_configuration(monkeypatch, capsys):
    monkeypatch.delenv("OCWP_DATABASE_URL", raising=False)
    monkeypatch.delenv("OCWP_DATABASE_URL_FILE", raising=False)

    def reject_connection(*args, **kwargs):
        raise AssertionError("No database connection should be attempted")

    monkeypatch.setattr("cycling_workshop.identity.cutover_cli.build_engine", reject_connection)
    assert main(["cutover", "status", "--organization-id", "org"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "database_configuration_required"


@pytest.mark.parametrize("revision", [None, "0009", "0011"])
def test_operator_refuses_unqualified_schema_without_effects(installation, revision):
    engine, settings = installation
    with engine.begin() as connection:
        if revision is None:
            connection.execute(text("DROP TABLE alembic_version"))
        else:
            connection.execute(
                text("UPDATE alembic_version SET version_num=:revision"), {"revision": revision}
            )
    with Session(engine) as session:
        incarnation = session.get(OrganizationRecord, "org").dataset_incarnation
    for action in (
        lambda: cutover_status(settings, organization_id="org"),
        lambda: activate_cutover(settings, organization_id="org"),
        lambda: recover_cutover(settings, organization_id="org", expected_incarnation=incarnation),
    ):
        with pytest.raises(ApiError) as failure:
            action()
        assert failure.value.code == "cutover_schema_incompatible"
    assert audit_rows(engine) == []
    with Session(engine) as session:
        org = session.get(OrganizationRecord, "org")
        assert org.dataset_incarnation == incarnation and org.minimum_write_protocol == 0
