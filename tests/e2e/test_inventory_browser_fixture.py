from __future__ import annotations

import re
from functools import partial
from pathlib import Path

import pytest
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.inventory.models import InventoryMovementRecord, ProductRecord
from cycling_workshop.tenancy.models import OrganizationRecord
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from scripts.e2e import inventory_fixtures as inventory
from scripts.e2e import prepare_e2e_database as preparation


def test_inventory_fixture_refuses_operator_targets_before_connection() -> None:
    for url in (
        "postgresql://user@127.0.0.1/operator",
        "postgresql://user@remote.example/ocwp_test",
        "sqlite:///operator.sqlite3",
    ):
        with pytest.raises(RuntimeError, match="dedicated local test database"):
            inventory.seed_inventory_identities(url)


def test_inventory_cases_and_retries_have_disjoint_finite_ids() -> None:
    ids = {
        inventory.inventory_fixture_id(index, retry, entity)
        for index in range(len(inventory.INVENTORY_CASES))
        for retry in range(2)
        for entity in range(600)
    }
    assert len(ids) == len(inventory.INVENTORY_CASES) * 2 * 600
    assert preparation.E2E_ORGANIZATION_ID not in ids
    assert all(len(value) == 36 for value in ids)
    with pytest.raises(ValueError):
        inventory.inventory_fixture_id(0, 2, 0)


def test_inventory_seed_keeps_partial_grants_and_immutable_signed_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Functional fixture proof only. PostgreSQL/browser qualification is separate.
    url = f"sqlite+pysqlite:///{tmp_path / 'inventory-fixture.sqlite3'}"
    monkeypatch.setenv("OCWP_DATABASE_URL", url)
    monkeypatch.delenv("OCWP_DATABASE_URL_FILE", raising=False)
    validated: list[str] = []
    monkeypatch.setattr(preparation, "validate_e2e_database_url", validated.append)
    preparation.run_migrations(url)
    validated.clear()
    inventory.seed_inventory_identities(url)
    assert validated == [url]
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            organizations = list(session.scalars(select(OrganizationRecord)))
            assert len(organizations) == len(inventory.INVENTORY_CASES) * 2
            for retry in range(2):
                for index, case in enumerate(inventory.INVENTORY_CASES):
                    identity = partial(inventory.inventory_fixture_id, index, retry)
                    organization = session.get(OrganizationRecord, identity(0))
                    assert organization is not None
                    assert organization.minimum_write_protocol == (0 if case == "floor-zero" else 1)
                    reader = session.get(UserRecord, identity(3))
                    directory = session.get(UserRecord, identity(5))
                    writer = session.get(UserRecord, identity(6))
                    workshop = session.get(UserRecord, identity(4))
                    assert workshop is not None
                    assert ("sync.push" in workshop.capabilities) is (case != "preservation")
                    assert {"inventory.read", "customers.write", "sync.pull"} <= set(
                        workshop.capabilities
                    )
                    assert reader is not None and directory is not None and writer is not None
                    assert reader.capabilities == ["inventory.read"]
                    assert reader.location_id == identity(1)
                    assert directory.location_id is None
                    assert set(directory.capabilities) == {"inventory.read", "locations.read"}
                    assert writer.capabilities == ["inventory.write"]
                    products = list(
                        session.scalars(
                            select(ProductRecord).where(
                                ProductRecord.organization_id == identity(0)
                            )
                        )
                    )
                    if case == "empty":
                        assert not products
                        continue
                    assert len(products) == 53
                    ledger = list(
                        session.scalars(
                            select(InventoryMovementRecord)
                            .where(InventoryMovementRecord.product_id == identity(100))
                            .order_by(
                                InventoryMovementRecord.occurred_at.desc(),
                                InventoryMovementRecord.movement_id.desc(),
                            )
                        )
                    )
                    assert len(ledger) == 54
                    assert sum(row.quantity for row in ledger) == 148
                    assert ledger[49].kind == "CONSUME" and ledger[49].quantity == 4
                    assert ledger[50].kind == "ADJUST" and ledger[50].quantity == -4
                    assert ledger[49].occurred_at == ledger[50].occurred_at
                    assert ledger[51].kind == "CONSUME" and ledger[51].reference_movement_id is None
                    assert all(row.note == inventory.PRIVATE_CANARY for row in ledger)
    finally:
        engine.dispose()


def test_inventory_seed_and_browser_case_order_are_identical() -> None:
    root = Path(__file__).resolve().parents[2]
    browser = (root / "apps/web/e2e/inventory.spec.ts").read_text()
    cases = browser.split("const CASES = [", 1)[1].split("] as const", 1)[0]
    assert tuple(re.findall(r"'([^']+)'", cases)) == inventory.INVENTORY_CASES
    assert "trace: 'off', video: 'off', screenshot: 'off'" in browser
    assert "new URL(request.url()).pathname" in browser
    assert (
        "seed_inventory_identities(database_url)"
        in (root / "scripts/e2e/prepare_e2e_database.py").read_text()
    )
