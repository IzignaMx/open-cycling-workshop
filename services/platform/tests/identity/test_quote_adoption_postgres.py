"""Synthetic quote grant adoption CAS/atomicity on actual PostgreSQL only."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from cycling_workshop.api.errors import ApiError
from cycling_workshop.identity import quote_cli
from cycling_workshop.identity.roles import LEGACY_WILDCARD_CAPABILITIES, QUOTE_CAPABILITIES
from sqlalchemy.exc import SQLAlchemyError
from test_administration_postgres import administration_postgres as administration_postgres


def test_quote_adoption_observed_lock_wait_has_one_cas_winner(administration_postgres):
    db = administration_postgres
    actor = db.seed(owner=True, capabilities=LEGACY_WILDCARD_CAPABILITIES)

    def adopt():
        try:
            return quote_cli.adopt_quotes(
                db.app.state.settings,
                organization_id=db.organization_id,
                owner_id=actor,
                expected_version=1,
            )
        except ApiError as exc:
            return exc.code

    with db.factory() as blocker, ThreadPoolExecutor(max_workers=2) as executor:
        db.lock_organization(blocker)
        futures = [executor.submit(adopt) for _ in range(2)]
        try:
            assert len(db.wait_for_lock_waiters(futures)) == 2
        finally:
            blocker.rollback()
        results = [future.result(timeout=25) for future in futures]
    assert sum(isinstance(result, dict) and result["changed"] for result in results) == 1
    assert results.count("stale_user_version") == 1
    assert db.user(actor).version == db.user(actor).session_version == 2
    assert set(db.user(actor).capabilities) == LEGACY_WILDCARD_CAPABILITIES | QUOTE_CAPABILITIES
    assert len(db.audits()) == 1 and db.audits()[0].action == "user.quotes_adopted"


def test_quote_adoption_postgres_audit_failure_is_atomic(administration_postgres, monkeypatch):
    db = administration_postgres
    actor = db.seed(owner=True, capabilities=LEGACY_WILDCARD_CAPABILITIES)
    original = quote_cli.append_audit
    reached = []

    def fail_after_audit(*args, **kwargs):
        original(*args, **kwargs)
        reached.append(True)
        raise SQLAlchemyError("synthetic audit failure")

    monkeypatch.setattr(quote_cli, "append_audit", fail_after_audit)
    with pytest.raises(SQLAlchemyError):
        quote_cli.adopt_quotes(
            db.app.state.settings,
            organization_id=db.organization_id,
            owner_id=actor,
            expected_version=1,
        )
    assert reached == [True]
    assert db.user(actor).version == db.user(actor).session_version == 1
    assert set(db.user(actor).capabilities) == LEGACY_WILDCARD_CAPABILITIES
    assert db.audits() == []
