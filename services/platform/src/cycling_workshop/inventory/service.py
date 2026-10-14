from __future__ import annotations

from dataclasses import replace

from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.identity.domain import Principal, authorize
from cycling_workshop.inventory.domain import InventoryMovement, MovementKind, Product
from cycling_workshop.inventory.repository import SqlAlchemyInventoryRepository
from cycling_workshop.inventory.schemas import MovementCreateRequest
from cycling_workshop.service_orders.repository import SqlAlchemyServiceOrderRepository
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.writes import lock_writer


def authorize_location(principal: Principal, capability: str, location_id: str | None) -> None:
    try:
        authorize(
            principal,
            capability=capability,
            organization_id=principal.organization_id,
            location_id=location_id,
        )
    except PermissionError as exc:
        raise ApiError(403, "scope_denied", "location scope denied") from exc


def scoped_product(
    repository: SqlAlchemyInventoryRepository,
    principal: Principal,
    product_id: str,
    *,
    capability: str,
    for_update: bool = False,
) -> Product:
    product = repository.get_product(
        product_id=product_id,
        organization_id=principal.organization_id,
        for_update=for_update,
    )
    if product is None:
        raise ApiError(404, "product_not_found", "product not found")
    authorize_location(principal, capability, product.location_id)
    return product


def _conflict(message: str) -> ApiError:
    return ApiError(409, "inventory_conflict", message)


def record_movement(
    session: Session,
    principal: Principal,
    payload: MovementCreateRequest,
) -> InventoryMovement:
    # Refresh the detached HTTP principal under org→actor locks before touching
    # the product. Keep those locks through the caller's commit/rollback so an
    # administration change cannot commit between authorization and ledger write.
    principal = lock_writer(session, principal)
    authorize_location(principal, "inventory.write", principal.location_id)
    repository = SqlAlchemyInventoryRepository(session)
    # All public ledger writes acquire the same product lock. The idempotency,
    # stock and finalization reads MUST occur after it, in this transaction.
    product = scoped_product(
        repository,
        principal,
        payload.product_id,
        capability="inventory.write",
        for_update=True,
    )
    candidate = InventoryMovement.record(
        movement_id=payload.movement_id,
        product_id=product.product_id,
        organization_id=principal.organization_id,
        location_id=product.location_id,
        kind=payload.kind,
        quantity=payload.quantity,
        actor_id=principal.user_id,
        order_id=payload.order_id,
        reference_movement_id=payload.reference_movement_id,
        note=payload.note,
    )
    existing = repository.get_movement(
        movement_id=payload.movement_id,
        organization_id=principal.organization_id,
    )
    if existing is not None:
        if replace(candidate, occurred_at=existing.occurred_at) != existing:
            raise _conflict("movement identifier already used by a different command")
        return existing

    if payload.order_id is not None:
        order = SqlAlchemyServiceOrderRepository(session).get(
            order_id=payload.order_id,
            organization_id=principal.organization_id,
        )
        if order is None or order.location_id != product.location_id:
            raise ApiError(404, "order_not_found", "order not found in product location")

    if payload.kind == MovementKind.RESERVE:
        stock = repository.available_quantity(
            product_id=product.product_id,
            organization_id=principal.organization_id,
            location_id=product.location_id,
        )
        if stock < payload.quantity:
            raise _conflict("insufficient available stock")

    if payload.reference_movement_id is not None:
        reservation = repository.get_movement(
            movement_id=payload.reference_movement_id,
            organization_id=principal.organization_id,
        )
        if reservation is None or reservation.location_id != product.location_id:
            raise ApiError(404, "reservation_not_found", "reservation not found")
        if (
            reservation.kind != MovementKind.RESERVE
            or reservation.product_id != product.product_id
            or reservation.order_id != payload.order_id
            or -reservation.quantity != payload.quantity
        ):
            raise _conflict("reference must match the full product and order reservation")
        if repository.released_reservation_ids(
            organization_id=principal.organization_id,
            reference_movement_id=reservation.movement_id,
        ):
            raise _conflict("reservation already finalized")

    repository.record(candidate)
    if payload.kind == MovementKind.CONSUME:
        # Preserve the shipped ledger convention: CONSUME releases the hold;
        # its inseparable ADJUST records physical outflow. Neither can commit
        # alone, so consuming never replenishes or double-deducts availability.
        repository.record(
            InventoryMovement.record(
                movement_id=new_id(),
                product_id=product.product_id,
                organization_id=principal.organization_id,
                location_id=product.location_id,
                kind=MovementKind.ADJUST,
                quantity=-payload.quantity,
                actor_id=principal.user_id,
                order_id=payload.order_id,
                reference_movement_id=payload.reference_movement_id,
                note=f"Physical issue for consumption {candidate.movement_id}",
                now=candidate.occurred_at,
            )
        )
    session.flush()
    return candidate
