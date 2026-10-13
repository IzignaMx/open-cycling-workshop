from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.db.dependencies import get_session
from cycling_workshop.identity.dependencies import require_capability
from cycling_workshop.identity.domain import Principal
from cycling_workshop.inventory.domain import Product
from cycling_workshop.inventory.repository import SqlAlchemyInventoryRepository
from cycling_workshop.inventory.schemas import (
    MovementCreateRequest,
    MovementResponse,
    ProductCreateRequest,
    ProductResponse,
    StockResponse,
)
from cycling_workshop.inventory.service import authorize_location, record_movement, scoped_product
from cycling_workshop.shared.ids import new_id
from cycling_workshop.tenancy.models import LocationRecord

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


def _require_location(session: Session, principal: Principal, location_id: str) -> None:
    found = session.scalar(
        select(LocationRecord.id).where(
            LocationRecord.id == location_id,
            LocationRecord.organization_id == principal.organization_id,
        )
    )
    if found is None:
        raise ApiError(404, "location_not_found", "location not found")


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreateRequest,
    principal: Annotated[Principal, Depends(require_capability("inventory.write"))],
    session: Annotated[Session, Depends(get_session)],
) -> ProductResponse:
    authorize_location(principal, "inventory.write", payload.location_id)
    _require_location(session, principal, payload.location_id)
    product = Product.create(
        product_id=payload.product_id or new_id(),
        organization_id=principal.organization_id,
        location_id=payload.location_id,
        sku=payload.sku,
        name=payload.name,
        unit=payload.unit,
    )
    try:
        SqlAlchemyInventoryRepository(session).add_product(product)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ApiError(409, "product_conflict", "product identifier or SKU already exists") from exc
    return ProductResponse.model_validate(product)


@router.get("/products", response_model=list[ProductResponse])
def list_products(
    principal: Annotated[Principal, Depends(require_capability("inventory.read"))],
    session: Annotated[Session, Depends(get_session)],
    location_id: Annotated[str, Query(min_length=1, max_length=36, pattern=r"^[^\x00]+$")],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0, le=2147483647)] = 0,
) -> list[ProductResponse]:
    authorize_location(principal, "inventory.read", location_id)
    _require_location(session, principal, location_id)
    products = SqlAlchemyInventoryRepository(session).list_products(
        organization_id=principal.organization_id,
        location_id=location_id,
        limit=limit,
        offset=offset,
    )
    return [ProductResponse.model_validate(product) for product in products]


@router.get("/products/{product_id}/stock", response_model=StockResponse)
def get_stock(
    product_id: Annotated[str, Path(min_length=1, max_length=36, pattern=r"^[^\x00]+$")],
    principal: Annotated[Principal, Depends(require_capability("inventory.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> StockResponse:
    repository = SqlAlchemyInventoryRepository(session)
    product = scoped_product(repository, principal, product_id, capability="inventory.read")
    return StockResponse(
        product_id=product.product_id,
        organization_id=product.organization_id,
        location_id=product.location_id,
        available_quantity=repository.available_quantity(
            product_id=product.product_id,
            organization_id=product.organization_id,
            location_id=product.location_id,
        ),
    )


@router.post("/movements", response_model=MovementResponse, status_code=status.HTTP_201_CREATED)
def create_movement(
    payload: MovementCreateRequest,
    principal: Annotated[Principal, Depends(require_capability("inventory.write"))],
    session: Annotated[Session, Depends(get_session)],
) -> MovementResponse:
    try:
        movement = record_movement(session, principal, payload)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ApiError(
            409,
            "inventory_conflict",
            "movement identifier or reservation already finalized",
        ) from exc
    return MovementResponse.model_validate(movement)
