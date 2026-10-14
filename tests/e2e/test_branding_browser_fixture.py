from __future__ import annotations

import re
from pathlib import Path

import pytest
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.roles import CAPABILITIES, LEGACY_WILDCARD_CAPABILITIES
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from scripts.e2e import branding_fixtures as branding
from scripts.e2e import prepare_e2e_database as preparation

ROOT = Path(__file__).resolve().parents[2]


def test_branding_cases_have_exact_browser_seed_parity_and_disjoint_retry_tenants() -> None:
    source = (ROOT / "apps/web/e2e/branding.spec.ts").read_text()
    cases = source.split("const CASES = [", 1)[1].split("] as const", 1)[0]
    assert tuple(re.findall(r"'([^']+)'", cases)) == branding.BRANDING_CASES
    ids = {
        branding.branding_fixture_id(index, retry, entity)
        for retry in range(2)
        for index in range(len(branding.BRANDING_CASES))
        for entity in range(5)
    }
    assert len(ids) == len(branding.BRANDING_CASES) * 2 * 5
    previous = {
        preparation.administration_fixture_id(index, retry, entity)
        for retry in range(2)
        for index in range(len(preparation.ADMINISTRATION_CASES))
        for entity in range(4)
    }
    assert ids.isdisjoint(previous)
    assert preparation.E2E_ORGANIZATION_ID not in ids


def test_branding_fixture_refuses_operator_and_remote_database_targets() -> None:
    for url in (
        "postgresql://user@127.0.0.1/operator",
        "postgresql://user@remote.example/ocwp_test",
        "sqlite:///not-a-browser-fixture.sqlite3",
    ):
        with pytest.raises(RuntimeError, match="dedicated local test database"):
            branding.seed_branding_identities(url)


def test_synthetic_branding_seed_keeps_explicit_grants_and_floor_one_per_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # This fixture-shape test uses disposable SQLite only; it is not PostgreSQL
    # or browser evidence. Production entry points still require local *_test/e2e.
    url = f"sqlite+pysqlite:///{tmp_path / 'branding-fixture.sqlite3'}"
    monkeypatch.setenv("OCWP_DATABASE_URL", url)
    monkeypatch.delenv("OCWP_DATABASE_URL_FILE", raising=False)
    preparation.run_migrations(url)
    validated = []
    monkeypatch.setattr(preparation, "validate_e2e_database_url", validated.append)
    branding.seed_branding_identities(url)
    assert validated == [url]
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            organizations = list(session.scalars(select(OrganizationRecord)))
            assert len(organizations) == 2 * len(branding.BRANDING_CASES)
            assert all(organization.minimum_write_protocol == 1 for organization in organizations)
            locations = list(session.scalars(select(LocationRecord)))
            assert len(locations) == 4 * len(branding.BRANDING_CASES)
            for retry in range(2):
                for index, case in enumerate(branding.BRANDING_CASES):
                    owner = session.get(UserRecord, branding.branding_fixture_id(index, retry, 3))
                    scoped = session.get(UserRecord, branding.branding_fixture_id(index, retry, 4))
                    assert owner is not None and scoped is not None
                    assert owner.is_owner and owner.location_id is None
                    assert set(owner.capabilities) == CAPABILITIES
                    assert scoped.location_id == branding.branding_fixture_id(index, retry, 1)
                    if case == "grants-legacy":
                        assert scoped.capabilities == ["*"]
                    elif case == "grants-legacy-read":
                        assert set(scoped.capabilities) == {"*", "branding.read"}
                    elif case == "grants-legacy-write":
                        assert set(scoped.capabilities) == {"*", "branding.write"}
                    elif case == "grants-concrete-old":
                        assert set(scoped.capabilities) == LEGACY_WILDCARD_CAPABILITIES
                    elif case == "grants-technical":
                        assert scoped.capabilities == []
    finally:
        engine.dispose()
