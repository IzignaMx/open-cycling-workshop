"""Finite synthetic read-only inventory journeys; no real installation targets."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import partial

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

INVENTORY_CASES = (
    "floor-zero",
    "floor-one",
    "directory",
    "denied",
    "preservation",
    "expiry-idle",
    "expiry-background",
    "scope-race",
    "product-race",
    "logout-race",
    "errors",
    "revocation",
    "empty",
    "visual-banco",
    "visual-plano",
    "visual-ritmo",
    "visual-noche",
)
PRIVATE_CANARY = "PRIVATE_INVENTORY_NOTE_CANARY_NOT_FOR_READ_UI"
PRODUCT_NAME = "P000 Cadena sintética"
LONG_PRODUCT_NAME = "P003 Componente de bicicleta con descripción larga " + "resistente " * 12
WORKSHOP_GRANTS = {
    "customers.read",
    "customers.write",
    "bicycles.read",
    "bicycles.write",
    "orders.read",
    "orders.write",
    "sync.pull",
    "sync.push",
}


def inventory_fixture_id(case_index: int, retry: int, entity: int) -> str:
    if (
        case_index not in range(len(INVENTORY_CASES))
        or retry not in range(2)
        or entity not in range(1000)
    ):
        raise ValueError("inventory fixture index outside the finite fixture")
    return (
        f"00000000-0000-7000-8000-{1_000_000 + retry * 100_000 + case_index * 1000 + entity:012d}"
    )


def _seed_products(session: Session, case_index: int, retry: int) -> None:
    from cycling_workshop.inventory.models import InventoryMovementRecord, ProductRecord

    def identity(entity: int) -> str:
        return inventory_fixture_id(case_index, retry, entity)

    timestamp = datetime(2026, 10, 1, tzinfo=UTC)
    for index in range(52):
        name = (
            PRODUCT_NAME
            if index == 0
            else "P001 Saldo negativo"
            if index == 1
            else "P002 Sin movimientos"
            if index == 2
            else LONG_PRODUCT_NAME
            if index == 3
            else f"P{index:03d} Refacción sintética"
        )
        session.add(
            ProductRecord(
                id=identity(100 + index),
                organization_id=identity(0),
                location_id=identity(1),
                sku=f"SKU-{index:03d}",
                name=name,
                unit="pieza",
                created_at=timestamp,
                updated_at=timestamp,
                version=1,
            )
        )
    session.add(
        ProductRecord(
            id=identity(199),
            organization_id=identity(0),
            location_id=identity(2),
            sku="OTHER-WORKSHOP",
            name="B000 Producto de otro taller",
            unit="caja",
            created_at=timestamp,
            updated_at=timestamp,
            version=1,
        )
    )
    session.flush()

    def movement(
        entity: int,
        kind: str,
        quantity: int,
        second: int,
        reference: str | None = None,
        product: int = 100,
    ) -> None:
        session.add(
            InventoryMovementRecord(
                movement_id=identity(entity),
                organization_id=identity(0),
                location_id=identity(1),
                product_id=identity(product),
                kind=kind,
                quantity=quantity,
                order_id="private-order-canary",
                reference_movement_id=reference,
                actor_id=identity(9),
                note=PRIVATE_CANARY,
                occurred_at=timestamp + timedelta(seconds=second, microseconds=1),
            )
        )

    movement(346, "ADJUST", 100, 0)
    movement(347, "RESERVE", -4, 1)
    movement(348, "CONSUME", 3, 2)  # Honest legacy standalone consumption, not repaired.
    # The immutable same-time pair straddles a page of50. ID DESC puts CONSUME first.
    movement(349, "ADJUST", -4, 3, identity(347))
    movement(350, "CONSUME", 4, 3, identity(347))
    for index in range(49):
        movement(400 + index, "ADJUST", 1, 4 + index)
    movement(450, "ADJUST", -7, 0, product=101)


def seed_inventory_identities(database_url: str) -> None:
    from cycling_workshop.db.url import normalize_database_url
    from cycling_workshop.identity.cutover_cli import activate_cutover, cutover_status
    from cycling_workshop.identity.models import UserRecord
    from cycling_workshop.identity.roles import CAPABILITIES
    from cycling_workshop.identity.security import PasswordService
    from cycling_workshop.settings import Settings
    from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord

    if __package__:
        from .prepare_e2e_database import E2E_PASSWORD, validate_e2e_database_url
    else:
        from prepare_e2e_database import E2E_PASSWORD, validate_e2e_database_url

    validate_e2e_database_url(database_url)
    password_hash = PasswordService().hash(E2E_PASSWORD)
    settings = Settings(database_url=database_url, cutover_enabled=True)
    engine = create_engine(normalize_database_url(database_url))
    try:
        for retry in range(2):
            for case_index, case in enumerate(INVENTORY_CASES):
                identity = partial(inventory_fixture_id, case_index, retry)

                with Session(engine) as session:
                    session.add(
                        OrganizationRecord(
                            id=identity(0), name=f"Disposable inventory {case} {retry}"
                        )
                    )
                    session.flush()
                    session.add_all(
                        LocationRecord(
                            id=identity(entity),
                            organization_id=identity(0),
                            name=f"Taller inventario {letter}",
                        )
                        for entity, letter in ((1, "A"), (2, "B"))
                    )
                    session.flush()
                    # A genuine local-only writer makes pre-existing pending work
                    # deterministic without intercepting delivery or racing timers.
                    workshop_grants = WORKSHOP_GRANTS | {"inventory.read"}
                    if case == "preservation":
                        workshop_grants = workshop_grants - {"sync.push"}
                    variants = (
                        (3, "reader", identity(1), {"inventory.read"}),
                        (4, "workshop", identity(1), workshop_grants),
                        (5, "directory", None, {"inventory.read", "locations.read"}),
                        (6, "writer", identity(1), {"inventory.write"}),
                        (7, "no-directory", None, {"inventory.read"}),
                        (8, "reader-b", identity(2), {"inventory.read"}),
                        (9, "owner", None, CAPABILITIES),
                    )
                    session.add_all(
                        UserRecord(
                            id=identity(entity),
                            organization_id=identity(0),
                            location_id=location,
                            username=f"e2e-inventory-{role}",
                            display_name=f"Inventario {role}",
                            password_hash=password_hash,
                            capabilities=sorted(grants),
                            is_owner=role == "owner",
                            is_active=True,
                            session_version=1,
                        )
                        for entity, role, location, grants in variants
                    )
                    session.flush()
                    if case != "empty":
                        _seed_products(session, case_index, retry)
                    session.commit()
                if case != "floor-zero":
                    activated = activate_cutover(settings, organization_id=identity(0))
                    assert activated["changed"] is True
                    persisted = cutover_status(settings, organization_id=identity(0))
                    assert persisted["minimum_write_protocol"] == 1
                    assert persisted["dataset_incarnation"] == activated["dataset_incarnation"]
    finally:
        engine.dispose()
