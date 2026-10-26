"""Direct matrix setup preserves isolation without constructing unused HTTP state."""

from unittest.mock import Mock

import pytest
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.db.base import Base
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.sync import writes
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from sqlalchemy import event, inspect, select
from sqlalchemy.pool import StaticPool

from services.platform.tests.sync import test_writer_reauthorization as matrix
from services.platform.tests.sync.test_writer_reauthorization import (
    writer_matrix_factory as writer_matrix_factory,
)


def test_matrix_calls_real_writer_without_constructing_http(writer_matrix_factory, monkeypatch):
    def forbid_http(*args, **kwargs):
        raise AssertionError("direct writer matrix must not construct HTTP state")

    monkeypatch.setattr(matrix, "build_client", forbid_http)
    original = writes.lock_writer
    calls = []

    def capture(session, principal, admission):
        calls.append((session.get_bind(), principal, admission))
        return original(session, principal, admission)

    monkeypatch.setattr(writes, "lock_writer", capture)
    matrix.test_waiting_writer_preserves_literal_intersection_matrix(
        frozenset({"*", "customers.write"}),
        frozenset({"customers.read", "customers.write"}),
        frozenset({"*"}),
        writer_matrix_factory,
    )
    assert len(calls) == 1
    engine, principal, admission = calls[0]
    assert engine is writer_matrix_factory.kw["bind"]
    assert principal.capabilities == frozenset({"customers.write"})
    assert admission.protocol == 0


def test_matrix_factory_preserves_engine_schema_and_session_configuration(monkeypatch):
    create = Mock(wraps=matrix.create_engine)
    seed = Mock(wraps=matrix._ensure_seed)
    monkeypatch.setattr(matrix, "create_engine", create)
    monkeypatch.setattr(matrix, "_ensure_seed", seed)
    fixture = matrix.writer_matrix_factory.__wrapped__()
    factory = next(fixture)
    engine = factory.kw["bind"]
    disposed = []
    event.listen(engine, "engine_disposed", lambda _: disposed.append(True))
    try:
        create.assert_called_once_with(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        seed.assert_called_once_with(engine)
        assert isinstance(engine.pool, StaticPool)
        assert factory.kw["expire_on_commit"] is False
        assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables)
        with factory() as session:
            assert session.get(OrganizationRecord, "org-1").name == "Taller Uno"
            assert session.get(LocationRecord, "loc-1").organization_id == "org-1"
            assert session.get(CustomerRecord, "customer-1").display_name == "Ana Rivera"
            actor = session.get(UserRecord, "user-1")
            assert actor.capabilities == matrix.FULL_CAPABILITIES
            assert actor.is_active is True
            assert actor.session_version == 1
            assert actor.password_hash == "unused-in-token-tests"
    finally:
        fixture.close()
    assert disposed == [True]


def test_matrix_factory_has_fresh_committed_state_for_each_invocation():
    first = matrix.writer_matrix_factory.__wrapped__()
    first_factory = next(first)
    try:
        with first_factory.begin() as session:
            actor = session.get(UserRecord, "user-1")
            actor.capabilities = []
            actor.is_active = False
            actor.session_version = 7
            session.add(OrganizationRecord(id="other", name="Previous case"))
    finally:
        first.close()

    second = matrix.writer_matrix_factory.__wrapped__()
    second_factory = next(second)
    try:
        assert second_factory.kw["bind"] is not first_factory.kw["bind"]
        with second_factory() as session:
            actor = session.get(UserRecord, "user-1")
            assert actor.capabilities == matrix.FULL_CAPABILITIES
            assert actor.is_active is True
            assert actor.session_version == 1
            assert list(session.scalars(select(OrganizationRecord.id))) == ["org-1"]
    finally:
        second.close()


def test_matrix_factory_disposes_engine_when_seed_fails(monkeypatch):
    original = matrix.create_engine
    disposed = []

    def create(*args, **kwargs):
        engine = original(*args, **kwargs)
        event.listen(engine, "engine_disposed", lambda _: disposed.append(True))
        return engine

    def fail_seed(_engine):
        raise RuntimeError("synthetic seed failure")

    monkeypatch.setattr(matrix, "create_engine", create)
    monkeypatch.setattr(matrix, "_ensure_seed", fail_seed)
    with pytest.raises(RuntimeError, match="synthetic seed failure"):
        next(matrix.writer_matrix_factory.__wrapped__())
    assert disposed == [True]
