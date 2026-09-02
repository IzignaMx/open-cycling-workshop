from datetime import UTC, datetime

from cycling_workshop.db.base import Base
from cycling_workshop.inventory.domain import InventoryMovement, Product
from cycling_workshop.inventory.repository import SqlAlchemyInventoryRepository
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def _build_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def _seed(session: Session) -> None:
    session.add(OrganizationRecord(id="org-1", name="Taller"))
    session.add(OrganizationRecord(id="org-2", name="Ajeno"))
    session.add(LocationRecord(id="loc-1", organization_id="org-1", name="Principal"))
    session.add(LocationRecord(id="loc-2", organization_id="org-2", name="Ajena"))
    session.commit()


def _product(
    product_id: str, organization_id: str = "org-1", location_id: str = "loc-1"
) -> Product:
    return Product.create(
        product_id=product_id,
        organization_id=organization_id,
        location_id=location_id,
        sku=f"SKU-{product_id}",
        name="Pastilla de freno",
        now=NOW,
    )


def _movement(
    movement_id: str,
    product_id: str,
    *,
    kind: str = "ADJUST",
    quantity: int = 10,
    order_id: str | None = None,
    reference: str | None = None,
    organization_id: str = "org-1",
    location_id: str = "loc-1",
) -> InventoryMovement:
    return InventoryMovement.record(
        movement_id=movement_id,
        product_id=product_id,
        organization_id=organization_id,
        location_id=location_id,
        kind=kind,
        quantity=quantity,
        order_id=order_id,
        reference_movement_id=reference,
        actor_id="user-1",
        now=NOW,
    )


def test_stock_is_derived_from_the_append_only_ledger() -> None:
    session = _build_session()
    try:
        _seed(session)
        repository = SqlAlchemyInventoryRepository(session)
        repository.add_product(_product("product-1"))
        repository.record(_movement("m1", "product-1", kind="ADJUST", quantity=10))  # stock 10
        reservation = repository.record(
            _movement("m2", "product-1", kind="RESERVE", quantity=4, order_id="order-1")
        )  # available 6
        repository.record(
            _movement(
                "m3",
                "product-1",
                kind="CONSUME",
                quantity=4,
                order_id="order-1",
                reference=reservation.movement_id,
            )
        )  # hold finalized; the physical outflow follows as a deduction
        repository.record(_movement("m4", "product-1", quantity=-4))
        session.commit()

        stock = repository.available_quantity(product_id="product-1", organization_id="org-1")

        assert stock == 6
    finally:
        session.close()


def test_ledger_queries_are_tenant_scoped() -> None:
    session = _build_session()
    try:
        _seed(session)
        repository = SqlAlchemyInventoryRepository(session)
        repository.add_product(_product("product-1"))
        repository.add_product(_product("product-x", organization_id="org-2", location_id="loc-2"))
        repository.record(_movement("m1", "product-1", quantity=5))
        repository.record(
            _movement("m2", "product-x", quantity=99, organization_id="org-2", location_id="loc-2")
        )
        session.commit()

        assert repository.available_quantity(product_id="product-1", organization_id="org-2") == 0
        movements = repository.list_by_product(product_id="product-1", organization_id="org-1")
        assert [movement.movement_id for movement in movements] == ["m1"]
    finally:
        session.close()


def test_list_by_order_returns_order_movements_only() -> None:
    session = _build_session()
    try:
        _seed(session)
        repository = SqlAlchemyInventoryRepository(session)
        repository.add_product(_product("product-1"))
        repository.record(
            _movement("m1", "product-1", kind="RESERVE", quantity=2, order_id="order-9")
        )
        repository.record(_movement("m2", "product-1", quantity=50))
        session.commit()

        by_order = repository.list_by_order(order_id="order-9", organization_id="org-1")

        assert [movement.movement_id for movement in by_order] == ["m1"]
    finally:
        session.close()


def test_repository_rejects_cross_tenant_product_reads() -> None:
    session = _build_session()
    try:
        _seed(session)
        repository = SqlAlchemyInventoryRepository(session)
        repository.add_product(_product("product-1"))
        session.commit()

        assert repository.get_product(product_id="product-1", organization_id="org-2") is None
        found = repository.get_product(product_id="product-1", organization_id="org-1")
        assert found is not None
        assert found.sku == "SKU-PRODUCT-1"
    finally:
        session.close()
