from __future__ import annotations

from typing import Annotated
from urllib.parse import unquote_to_bytes

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.db.dependencies import get_session
from cycling_workshop.identity.cutover import WriteAdmission, commit_admitted, write_admission
from cycling_workshop.identity.dependencies import require_capability
from cycling_workshop.identity.domain import Principal
from cycling_workshop.inventory.cursor import decode_cursor, invalid_cursor, valid_read_id
from cycling_workshop.inventory.domain import Product
from cycling_workshop.inventory.read_guard import InventoryRead, inventory_read_dependency
from cycling_workshop.inventory.read_repository import read_movement_page
from cycling_workshop.inventory.repository import SqlAlchemyInventoryRepository
from cycling_workshop.inventory.schemas import (
    InventoryMovementPageResponse,
    MovementCreateRequest,
    MovementResponse,
    ProductCreateRequest,
    ProductResponse,
    StockResponse,
)
from cycling_workshop.inventory.service import authorize_location, record_movement, scoped_product
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.writes import lock_writer
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
    admission: Annotated[WriteAdmission, Depends(write_admission)],
) -> ProductResponse:
    principal = lock_writer(session, principal, admission)
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
        commit_admitted(session, principal, admission)
    except IntegrityError as exc:
        session.rollback()
        raise ApiError(409, "product_conflict", "product identifier or SKU already exists") from exc
    return ProductResponse.model_validate(product)


@router.get("/products", response_model=list[ProductResponse])
def list_products(
    read: Annotated[InventoryRead, Depends(inventory_read_dependency, scope="function")],
    location_id: Annotated[str, Query(min_length=1, max_length=36, pattern=r"^[^\x00]+$")],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0, le=2147483647)] = 0,
) -> list[ProductResponse]:
    authorize_location(read.principal, "inventory.read", location_id)
    _require_location(read.session, read.principal, location_id)
    products = SqlAlchemyInventoryRepository(read.session).list_products(
        organization_id=read.principal.organization_id,
        location_id=location_id,
        limit=limit,
        offset=offset,
    )
    return [ProductResponse.model_validate(product) for product in products]


@router.get("/products/{product_id}/stock", response_model=StockResponse)
def get_stock(
    read: Annotated[InventoryRead, Depends(inventory_read_dependency, scope="function")],
    product_id: Annotated[str, Path(min_length=1, max_length=36, pattern=r"^[^\x00]+$")],
) -> StockResponse:
    repository = SqlAlchemyInventoryRepository(read.session)
    product = scoped_product(repository, read.principal, product_id, capability="inventory.read")
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


@router.get("/products/{product_id}/movements", response_model=InventoryMovementPageResponse)
def get_movements(
    request: Request,
    read: Annotated[InventoryRead, Depends(inventory_read_dependency, scope="function")],
    product_id: Annotated[str, Path(min_length=1, max_length=36, pattern=r"^[^\x00]+$")],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before: Annotated[str | None, Query()] = None,
) -> InventoryMovementPageResponse:
    # Only this additive route rejects unknown/duplicate query keys. Bound the
    # raw query before iterating and never reflect names or supplied values.
    if before is not None and len(before) > 2048:
        raise invalid_cursor()
    if len(request.scope.get("query_string", b"")) > 4096 or not valid_read_id(product_id):
        raise ApiError(422, "invalid_inventory_query", "invalid inventory query")
    try:
        # ASGI servers replace malformed UTF-8 in path. Inspect original bytes
        # so a lone-surrogate encoding cannot become an alias for U+FFFD.
        unquote_to_bytes(request.scope.get("raw_path", b"")).decode("utf-8")
    except UnicodeError:
        raise ApiError(422, "invalid_inventory_query", "invalid inventory query") from None
    keys = [key for key, _value in request.query_params.multi_items()]
    if len(keys) != len(set(keys)) or not set(keys) <= {"limit", "before"}:
        raise ApiError(422, "invalid_inventory_query", "invalid inventory query")
    product = scoped_product(
        SqlAlchemyInventoryRepository(read.session),
        read.principal,
        product_id,
        capability="inventory.read",
    )
    cursor = (
        None
        if before is None
        else decode_cursor(
            before,
            organization_id=product.organization_id,
            location_id=product.location_id,
            product_id=product.product_id,
        )
    )
    return read_movement_page(
        read.session,
        organization_id=product.organization_id,
        location_id=product.location_id,
        product_id=product.product_id,
        limit=limit,
        before=cursor,
    )


@router.post("/movements", response_model=MovementResponse, status_code=status.HTTP_201_CREATED)
def create_movement(
    payload: MovementCreateRequest,
    principal: Annotated[Principal, Depends(require_capability("inventory.write"))],
    session: Annotated[Session, Depends(get_session)],
    admission: Annotated[WriteAdmission, Depends(write_admission)],
) -> MovementResponse:
    try:
        movement = record_movement(session, principal, payload, admission=admission)
        commit_admitted(session, principal, admission)
    except IntegrityError as exc:
        session.rollback()
        raise ApiError(
            409,
            "inventory_conflict",
            "movement identifier or reservation already finalized",
        ) from exc
    return MovementResponse.model_validate(movement)
