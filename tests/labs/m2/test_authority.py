"""SQLite functional proof only: not PostgreSQL lock/isolation qualification."""

from collections.abc import Iterator

import pytest
from cycling_workshop.inventory.models import ProductRecord
from sqlalchemy import select

from tests.labs.m2.authority import LabAuthority


@pytest.fixture
def authority() -> Iterator[LabAuthority]:
    lab = LabAuthority()
    try:
        yield lab
    finally:
        if not lab.closed:
            lab.close()


def test_real_machine_read_derives_scope_and_materializes_only_its_fixture(authority):
    credential = authority.issue()
    with authority.read(credential.authorization()) as (scope, session):
        rows = session.scalars(
            select(ProductRecord).where(
                ProductRecord.organization_id == scope.organization_id,
                ProductRecord.location_id == scope.location_id,
            )
        ).all()
        assert len(rows) == 3
        assert {row.sku for row in rows} == {"LAB-A-1-001", "LAB-A-1-002", "LAB-A-1-003"}
        assert all(row.name.startswith("Synthetic A/1 product ") for row in rows)


def test_rotation_and_revoke_are_zero_overlap_and_audited(authority):
    from sqlalchemy.orm import Session

    from tests.labs.m2.authority import LabDenied
    from tests.labs.m2.models import Audit

    old = authority.issue()
    new = authority.rotate(old.credential_id)
    with pytest.raises(LabDenied), authority.read(old.authorization()):
        pass
    with authority.read(new.authorization()):
        pass
    authority.revoke(new.credential_id)
    with pytest.raises(LabDenied), authority.read(new.authorization()):
        pass
    with Session(authority._engine) as session:
        assert session.scalars(select(Audit.action).order_by(Audit.occurred_at)).all() == [
            "issue",
            "rotate",
            "revoke",
        ]


@pytest.mark.parametrize(
    "dimension", ["installation_grant", "machine_grant", "installation_enabled", "machine_enabled"]
)
def test_current_intersection_refuses_reduction_without_reissuing(authority, dimension):
    from tests.labs.m2.authority import LabDenied

    c = authority.issue()
    if "grant" in dimension:
        authority.update_grants(
            c.credential_id,
            installation_read=dimension != "installation_grant",
            machine_read=dimension != "machine_grant",
        )
    else:
        authority.set_enabled(
            c.credential_id,
            installation=dimension != "installation_enabled",
            machine=dimension != "machine_enabled",
        )
    with pytest.raises(LabDenied) as error, authority.read(c.authorization()):
        pass
    assert error.value.status == 403
    with pytest.raises(LabDenied):
        if "grant" in dimension:
            authority.update_grants(c.credential_id, installation_read=True, machine_read=True)
        else:
            authority.set_enabled(c.credential_id, installation=True, machine=True)


@pytest.mark.parametrize(
    "header",
    ["", "Bearer human.jwt.token", "Basic arbitrary", "Bearer m2_bad", "Bearer " + "x" * 129],
)
def test_unknown_or_malformed_authorization_is_generic(authority, header):
    from tests.labs.m2.authority import LabDenied

    with pytest.raises(LabDenied) as error, authority.read(header):
        pass
    assert error.value.status == 401
    assert str(error.value) == "Laboratory access refused"


def test_two_organizations_and_two_locations_remain_disjoint(authority):
    scopes = []
    for fixture in ["primary", "other_location", "other_org"]:
        c = authority.issue(fixture)
        with authority.read(c.authorization()) as (scope, session):
            scopes.append(scope)
            rows = session.scalars(
                select(ProductRecord).where(
                    ProductRecord.organization_id == scope.organization_id,
                    ProductRecord.location_id == scope.location_id,
                )
            ).all()
            assert len(rows) == 3
            assert all(
                row.organization_id == scope.organization_id
                and row.location_id == scope.location_id
                for row in rows
            )
    assert scopes[0].organization_id == scopes[1].organization_id
    assert scopes[0].location_id != scopes[1].location_id
    assert scopes[0].organization_id != scopes[2].organization_id


def test_descriptor_scope_is_frozen_and_credential_repr_redacted(authority):
    from dataclasses import FrozenInstanceError

    c = authority.issue()
    secret = c.authorization()
    assert secret not in repr(c)
    assert secret.removeprefix("Bearer ") not in repr(c)
    with authority.read(secret) as (scope, _session), pytest.raises(FrozenInstanceError):
        scope.location_id = "foreign"


def test_no_plaintext_in_database_and_core_metadata_unmodified(authority):
    from cycling_workshop.db.base import Base
    from sqlalchemy.orm import Session

    from tests.labs.m2.models import LabBase, Machine

    c = authority.issue()
    with Session(authority._engine) as session:
        record = session.get(Machine, c.credential_id)
        assert len(record.verifier) == 64
        plaintext_leaked = c.authorization().removeprefix("Bearer ") in str(record.__dict__)
        assert not plaintext_leaked
        assert not (set(Base.metadata.tables) & set(LabBase.metadata.tables))


def test_audit_failure_rolls_back_revocation(authority):
    from sqlalchemy import event

    from tests.labs.m2.authority import LabDenied
    from tests.labs.m2.models import Audit

    c = authority.issue()

    def fail(*args):
        raise RuntimeError("synthetic audit failure")

    event.listen(Audit, "before_insert", fail)
    try:
        with pytest.raises(LabDenied) as error:
            authority.revoke(c.credential_id)
        assert error.value.status == 503
    finally:
        event.remove(Audit, "before_insert", fail)
    with authority.read(c.authorization()):
        pass


@pytest.mark.parametrize(
    "field",
    [
        "run_id",
        "incarnation",
        "location_id",
        "organization_id",
        "installation_id",
        "generation",
        "issued_at",
    ],
)
def test_tampered_generation_scope_or_future_issue_is_never_adopted(authority, field):
    from sqlalchemy.orm import Session

    from tests.labs.m2.authority import LabDenied
    from tests.labs.m2.models import Machine

    c = authority.issue()
    with Session(authority._engine) as session, session.begin():
        row = session.get(Machine, c.credential_id)
        setattr(
            row,
            field,
            row.issued_at + 10
            if field == "issued_at"
            else 999
            if field == "generation"
            else "foreign",
        )
    with pytest.raises(LabDenied), authority.read(c.authorization()):
        pass


def test_new_run_never_accepts_old_credential_and_close_is_terminal(authority):
    from tests.labs.m2.authority import LabDenied

    c = authority.issue()
    other = LabAuthority()
    try:
        with pytest.raises(LabDenied), other.read(c.authorization()):
            pass
    finally:
        other.close()
    authority.close()
    assert authority.closed
    assert not authority._witnesses
    with pytest.raises(LabDenied), authority.read(c.authorization()):
        pass


@pytest.mark.parametrize("kind", ["utc_rollback", "elapsed_rollback", "nonfinite", "deadline"])
def test_clock_fault_or_deadline_is_sticky_closed(authority, monkeypatch, kind):
    from tests.labs.m2 import authority as module
    from tests.labs.m2.authority import LabDenied

    c = authority.issue()
    utc, elapsed = authority._utc, authority._elapsed
    sample = (
        (utc - 1, elapsed)
        if kind == "utc_rollback"
        else (utc, elapsed - 1)
        if kind == "elapsed_rollback"
        else (utc, float("nan"))
        if kind == "nonfinite"
        else (utc, authority._run_until)
    )
    monkeypatch.setattr(module, "_clock", lambda: sample)
    with pytest.raises(LabDenied), authority.read(c.authorization()):
        pass
    monkeypatch.setattr(module, "_clock", lambda: (utc, elapsed))
    with pytest.raises(LabDenied), authority.read(c.authorization()):
        pass


def test_expiry_during_materialization_does_not_release_success(authority, monkeypatch):
    from tests.labs.m2 import authority as module
    from tests.labs.m2.authority import LabDenied

    c = authority.issue()
    with pytest.raises(LabDenied), authority.read(c.authorization()) as (_scope, session):
        assert len(session.scalars(select(ProductRecord)).all()) == 12
        monkeypatch.setattr(module, "_clock", lambda: (authority._utc, authority._run_until))


def test_audit_captures_installation_reduction_not_only_machine_policy(authority):
    import json

    from sqlalchemy.orm import Session

    from tests.labs.m2.models import Audit

    c = authority.issue()
    authority.update_grants(c.credential_id, installation_read=False, machine_read=True)
    with Session(authority._engine) as session:
        row = session.scalar(select(Audit).where(Audit.action == "grants"))
        assert json.loads(row.policy).get("installation_read") is False
        assert row.actor == "fixture_harness"


def test_database_exception_parameters_are_hidden(authority):
    assert authority._engine.hide_parameters is True


def test_local_read_barrier_finishes_before_revoke_and_later_read_refuses(authority):
    # Functional local serialization only; SQLite does not prove PG row locks.
    import threading

    from tests.labs.m2.authority import LabDenied

    c = authority.issue()
    entered, release, revoked = threading.Event(), threading.Event(), threading.Event()
    outcomes = []

    def reader():
        try:
            with authority.read(c.authorization()) as (scope, session):
                assert session.scalar(
                    select(ProductRecord.id).where(ProductRecord.location_id == scope.location_id)
                )
                entered.set()
                assert release.wait(1)
            outcomes.append("read")
        except Exception:
            outcomes.append("read failed")

    def revoker():
        try:
            authority.revoke(c.credential_id)
            outcomes.append("revoke")
            revoked.set()
        except Exception:
            outcomes.append("revoke failed")

    a = threading.Thread(target=reader)
    b = threading.Thread(target=revoker)
    a.start()
    try:
        assert entered.wait(1)
        b.start()
        assert not revoked.wait(0.02)
    finally:
        release.set()
        a.join(2)
        if b.ident is not None:
            b.join(2)
    assert not a.is_alive() and not b.is_alive()
    assert outcomes == ["read", "revoke"]
    with pytest.raises(LabDenied), authority.read(c.authorization()):
        pass


def test_restored_old_database_rows_do_not_reconstruct_external_run_witness(authority):
    from sqlalchemy.orm import Session

    from tests.labs.m2.authority import LabDenied
    from tests.labs.m2.models import Installation, Machine

    c = authority.issue()
    other = LabAuthority()
    try:
        with Session(authority._engine) as old, Session(other._engine) as new, new.begin():
            for model in (Installation, Machine):
                for row in old.scalars(select(model)).all():
                    new.add(
                        model(
                            **{
                                column.name: getattr(row, column.name)
                                for column in model.__table__.columns
                            }
                        )
                    )
        with pytest.raises(LabDenied), other.read(c.authorization()):
            pass
    finally:
        other.close()


def test_rotation_does_not_extend_original_run_deadline(authority, monkeypatch):
    from tests.labs.m2 import authority as module
    from tests.labs.m2.authority import LabDenied

    c = authority.issue()
    original_until = authority._run_until
    utc, elapsed = authority._utc, authority._elapsed
    monkeypatch.setattr(module, "_clock", lambda: (utc + 100, elapsed + 100))
    replacement = authority.rotate(c.credential_id)
    assert authority._witnesses[c.credential_id].deadline == original_until
    with authority.read(replacement.authorization()):
        pass
    monkeypatch.setattr(module, "_clock", lambda: (utc + 900, original_until))
    with pytest.raises(LabDenied), authority.read(replacement.authorization()):
        pass


def test_audit_failure_does_not_install_replacement_generation(authority):
    from sqlalchemy import event

    from tests.labs.m2.authority import LabDenied
    from tests.labs.m2.models import Audit

    c = authority.issue()
    generation = authority._witnesses[c.credential_id].scope.generation

    def fail(*args):
        raise RuntimeError("synthetic audit failure")

    event.listen(Audit, "before_insert", fail)
    try:
        with pytest.raises(LabDenied):
            authority.rotate(c.credential_id)
    finally:
        event.remove(Audit, "before_insert", fail)
    assert authority._witnesses[c.credential_id].scope.generation == generation
    with authority.read(c.authorization()):
        pass


def test_environment_cannot_select_existing_database(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://synthetic-invalid/not-used")
    lab = LabAuthority()
    try:
        assert str(lab._engine.url) == "sqlite+pysqlite:///:memory:"
    finally:
        lab.close()


def test_close_reports_verified_disposal_separately_from_admission_closed(authority):
    authority.issue()
    authority.close()
    assert authority.closed
    assert authority.cleanup_complete
    authority.close()
    assert authority.cleanup_complete


@pytest.mark.parametrize("field", ["run_id", "incarnation", "location_id", "organization_id"])
def test_installation_identity_tamper_is_refused(authority, field):
    from sqlalchemy.orm import Session

    from tests.labs.m2.authority import LabDenied
    from tests.labs.m2.models import Installation

    c = authority.issue()
    install_id = authority._witnesses[c.credential_id].scope.installation_id
    with Session(authority._engine) as session, session.begin():
        setattr(session.get(Installation, install_id), field, "foreign")
    with pytest.raises(LabDenied), authority.read(c.authorization()):
        pass


def test_incarnation_remains_mandatory_at_legacy_protocol_zero(authority):
    from uuid import uuid4

    from cycling_workshop.tenancy.models import OrganizationRecord
    from sqlalchemy.orm import Session

    from tests.labs.m2.authority import LabDenied

    c = authority.issue()
    scope = authority._witnesses[c.credential_id].scope
    with Session(authority._engine) as session, session.begin():
        org = session.get(OrganizationRecord, scope.organization_id)
        org.minimum_write_protocol = 0
        org.dataset_incarnation = str(uuid4())
    with pytest.raises(LabDenied), authority.read(c.authorization()):
        pass


def test_materialization_budget_is_checked_before_success(authority, monkeypatch):
    from tests.labs.m2 import authority as module
    from tests.labs.m2.authority import LabDenied

    c = authority.issue()
    with pytest.raises(LabDenied) as error, authority.read(c.authorization()):
        utc, elapsed = authority._utc, authority._elapsed
        monkeypatch.setattr(module, "_clock", lambda: (utc + 9, elapsed + 9))
    assert error.value.status == 503


def test_corrupted_organization_protocol_fails_canonical_admission(authority):
    from sqlalchemy import text

    from tests.labs.m2.authority import LabDenied

    c = authority.issue()
    with authority._engine.begin() as connection:
        connection.execute(text("PRAGMA ignore_check_constraints=ON"))
        connection.execute(text("UPDATE organizations SET minimum_write_protocol=99"))
        connection.execute(text("PRAGMA ignore_check_constraints=OFF"))
    with pytest.raises(LabDenied), authority.read(c.authorization()):
        pass


def test_rollback_failure_always_invalidates_and_closes_session(authority, monkeypatch):
    from sqlalchemy.orm import Session

    from tests.labs.m2.authority import LabDenied

    c = authority.issue()
    events = []
    original_close, original_invalidate = Session.close, Session.invalidate

    def failed_rollback(session):
        events.append("rollback")
        raise RuntimeError("synthetic cleanup failure")

    def invalidate(session):
        events.append("invalidate")
        original_invalidate(session)

    def close(session):
        events.append("close")
        original_close(session)

    monkeypatch.setattr(Session, "rollback", failed_rollback)
    monkeypatch.setattr(Session, "invalidate", invalidate)
    monkeypatch.setattr(Session, "close", close)
    with pytest.raises(LabDenied), authority.read(c.authorization()):
        pass
    assert events == ["rollback", "invalidate", "close"]
    assert authority._invalid


def test_audit_events_have_unique_internal_correlation_identifiers(authority):
    from uuid import UUID

    from sqlalchemy.orm import Session

    from tests.labs.m2.models import Audit

    c = authority.issue()
    authority.rotate(c.credential_id)
    with Session(authority._engine) as session:
        events = session.scalars(select(Audit)).all()
        ids = [getattr(row, "request_id", None) for row in events]
        assert all(isinstance(value, str) for value in ids)
        assert len(set(ids)) == 2
        assert all(str(UUID(value)) == value for value in ids)


def test_total_read_budget_includes_time_waiting_for_local_barrier(authority, monkeypatch):
    from contextlib import contextmanager

    from tests.labs.m2 import authority as module
    from tests.labs.m2.authority import LabDenied

    c = authority.issue()
    base_utc, base_elapsed = authority._utc, authority._elapsed
    sample = [base_utc, base_elapsed]
    monkeypatch.setattr(module, "_clock", lambda: tuple(sample))
    original = authority._locked

    @contextmanager
    def delayed_lock():
        sample[:] = [base_utc + 1.5, base_elapsed + 1.5]
        with original() as value:
            yield value

    monkeypatch.setattr(authority, "_locked", delayed_lock)
    with pytest.raises(LabDenied), authority.read(c.authorization()):
        sample[:] = [base_utc + 8.2, base_elapsed + 8.2]


def test_failed_disposal_never_claims_verified_cleanup_even_on_repeat(authority, monkeypatch):
    from tests.labs.m2.authority import LabDenied

    def fail():
        raise RuntimeError("synthetic disposal failure")

    original = authority._engine.dispose
    monkeypatch.setattr(authority._engine, "dispose", fail)
    try:
        with pytest.raises(LabDenied):
            authority.close()
        assert authority.closed
        assert not authority.cleanup_complete
        with pytest.raises(LabDenied):
            authority.close()
        assert not authority.cleanup_complete
    finally:
        original()
