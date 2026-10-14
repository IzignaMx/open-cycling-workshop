from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from cycling_workshop.customers.domain import Customer
from cycling_workshop.customers.repository import SqlAlchemyCustomerRepository
from cycling_workshop.customers.schemas import CustomerCreateRequest, CustomerResponse
from cycling_workshop.db.dependencies import get_session
from cycling_workshop.identity.dependencies import require_capability
from cycling_workshop.identity.domain import Principal, authorize
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.projections import customer_payload
from cycling_workshop.sync.writes import append_change, lock_writer

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


def _response(customer: Customer) -> CustomerResponse:
    return CustomerResponse(
        customer_id=customer.customer_id,
        organization_id=customer.organization_id,
        location_id=customer.location_id,
        display_name=customer.display_name,
        email=customer.email,
        phone=customer.phone,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
        version=customer.version,
    )


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreateRequest,
    principal: Annotated[Principal, Depends(require_capability("customers.write"))],
    session: Annotated[Session, Depends(get_session)],
) -> CustomerResponse:
    principal = lock_writer(session, principal)
    try:
        authorize(
            principal,
            capability="customers.write",
            organization_id=principal.organization_id,
            location_id=payload.location_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    customer = Customer.create(
        customer_id=payload.customer_id or new_id(),
        organization_id=principal.organization_id,
        location_id=payload.location_id,
        display_name=payload.display_name,
        email=payload.email,
        phone=payload.phone,
    )
    repository = SqlAlchemyCustomerRepository(session)
    repository.add(customer)
    append_change(
        session,
        organization_id=customer.organization_id,
        location_id=customer.location_id,
        entity_type="customer",
        entity_id=customer.customer_id,
        operation="create",
        entity_version=customer.version,
        occurred_at=customer.updated_at,
        payload=customer_payload(customer),
    )
    session.commit()
    return _response(customer)


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: str,
    principal: Annotated[Principal, Depends(require_capability("customers.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> CustomerResponse:
    repository = SqlAlchemyCustomerRepository(session)
    customer = repository.get(customer_id=customer_id, organization_id=principal.organization_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="customer not found")
    authorize(
        principal,
        capability="customers.read",
        organization_id=customer.organization_id,
        location_id=customer.location_id,
    )
    return _response(customer)
