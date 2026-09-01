from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from cycling_workshop.bicycles.domain import Bicycle
from cycling_workshop.bicycles.repository import SqlAlchemyBicycleRepository
from cycling_workshop.bicycles.schemas import BicycleCreateRequest, BicycleResponse
from cycling_workshop.customers.repository import SqlAlchemyCustomerRepository
from cycling_workshop.db.dependencies import get_session
from cycling_workshop.identity.dependencies import require_capability
from cycling_workshop.identity.domain import Principal, authorize
from cycling_workshop.shared.ids import new_id

router = APIRouter(tags=["bicycles"])


def _response(bicycle: Bicycle) -> BicycleResponse:
    return BicycleResponse(
        bicycle_id=bicycle.bicycle_id,
        customer_id=bicycle.customer_id,
        organization_id=bicycle.organization_id,
        location_id=bicycle.location_id,
        brand=bicycle.brand,
        model=bicycle.model,
        bicycle_type=bicycle.bicycle_type,
        wheel_size=bicycle.wheel_size,
        notes=bicycle.notes,
        created_at=bicycle.created_at,
        updated_at=bicycle.updated_at,
        version=bicycle.version,
    )


@router.post(
    "/api/v1/bicycles", response_model=BicycleResponse, status_code=status.HTTP_201_CREATED
)
def create_bicycle(
    payload: BicycleCreateRequest,
    principal: Annotated[Principal, Depends(require_capability("bicycles.write"))],
    session: Annotated[Session, Depends(get_session)],
) -> BicycleResponse:
    authorize(
        principal,
        capability="bicycles.write",
        organization_id=principal.organization_id,
        location_id=payload.location_id,
    )
    customers = SqlAlchemyCustomerRepository(session)
    if (
        customers.get(customer_id=payload.customer_id, organization_id=principal.organization_id)
        is None
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="customer not found")
    bicycle = Bicycle.create(
        bicycle_id=payload.bicycle_id or new_id(),
        customer_id=payload.customer_id,
        organization_id=principal.organization_id,
        location_id=payload.location_id,
        brand=payload.brand,
        model=payload.model,
        bicycle_type=payload.bicycle_type,
        wheel_size=payload.wheel_size,
        notes=payload.notes,
    )
    repository = SqlAlchemyBicycleRepository(session)
    repository.add(bicycle)
    session.commit()
    return _response(bicycle)


@router.get("/api/v1/bicycles/{bicycle_id}", response_model=BicycleResponse)
def get_bicycle(
    bicycle_id: str,
    principal: Annotated[Principal, Depends(require_capability("bicycles.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> BicycleResponse:
    repository = SqlAlchemyBicycleRepository(session)
    bicycle = repository.get(bicycle_id=bicycle_id, organization_id=principal.organization_id)
    if bicycle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="bicycle not found")
    authorize(
        principal,
        capability="bicycles.read",
        organization_id=bicycle.organization_id,
        location_id=bicycle.location_id,
    )
    return _response(bicycle)


@router.get("/api/v1/customers/{customer_id}/bicycles", response_model=list[BicycleResponse])
def list_customer_bicycles(
    customer_id: str,
    principal: Annotated[Principal, Depends(require_capability("bicycles.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> list[BicycleResponse]:
    customers = SqlAlchemyCustomerRepository(session)
    customer = customers.get(customer_id=customer_id, organization_id=principal.organization_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="customer not found")
    authorize(
        principal,
        capability="bicycles.read",
        organization_id=customer.organization_id,
        location_id=customer.location_id,
    )
    repository = SqlAlchemyBicycleRepository(session)
    bicycles = repository.list_by_customer(
        customer_id=customer_id, organization_id=principal.organization_id
    )
    return [_response(bicycle) for bicycle in bicycles]
