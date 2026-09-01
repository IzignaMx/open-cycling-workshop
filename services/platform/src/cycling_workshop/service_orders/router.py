from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from cycling_workshop.bicycles.repository import SqlAlchemyBicycleRepository
from cycling_workshop.customers.repository import SqlAlchemyCustomerRepository
from cycling_workshop.db.dependencies import get_session
from cycling_workshop.identity.dependencies import require_capability
from cycling_workshop.identity.domain import Principal, authorize
from cycling_workshop.service_orders.domain import (
    InvalidStateTransitionError,
    ServiceOrder,
    UnknownActionError,
)
from cycling_workshop.service_orders.repository import SqlAlchemyServiceOrderRepository
from cycling_workshop.service_orders.schemas import (
    OrderTransitionRequest,
    ServiceOrderCreateRequest,
    ServiceOrderEventResponse,
    ServiceOrderResponse,
)
from cycling_workshop.shared.ids import new_id

router = APIRouter(prefix="/api/v1/service-orders", tags=["service-orders"])


def _response(order: ServiceOrder) -> ServiceOrderResponse:
    return ServiceOrderResponse(
        order_id=order.order_id,
        customer_id=order.customer_id,
        bicycle_id=order.bicycle_id,
        organization_id=order.organization_id,
        location_id=order.location_id,
        state=order.state,
        reported_problem=order.reported_problem,
        intake_condition=order.intake_condition,
        accessories=order.accessories,
        priority=order.priority,
        diagnosis=order.diagnosis,
        created_at=order.created_at,
        updated_at=order.updated_at,
        version=order.version,
    )


@router.post("", response_model=ServiceOrderResponse, status_code=status.HTTP_201_CREATED)
def create_service_order(
    payload: ServiceOrderCreateRequest,
    principal: Annotated[Principal, Depends(require_capability("orders.write"))],
    session: Annotated[Session, Depends(get_session)],
) -> ServiceOrderResponse:
    authorize(
        principal,
        capability="orders.write",
        organization_id=principal.organization_id,
        location_id=payload.location_id,
    )
    customers = SqlAlchemyCustomerRepository(session)
    if (
        customers.get(customer_id=payload.customer_id, organization_id=principal.organization_id)
        is None
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="customer not found")
    if payload.bicycle_id is not None:
        bicycles = SqlAlchemyBicycleRepository(session)
        if (
            bicycles.get(bicycle_id=payload.bicycle_id, organization_id=principal.organization_id)
            is None
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="bicycle not found")
    order = ServiceOrder.create(
        order_id=payload.order_id or new_id(),
        customer_id=payload.customer_id,
        organization_id=principal.organization_id,
        location_id=payload.location_id,
        reported_problem=payload.reported_problem,
        bicycle_id=payload.bicycle_id,
        intake_condition=payload.intake_condition,
        accessories=payload.accessories,
        priority=payload.priority,
    )
    repository = SqlAlchemyServiceOrderRepository(session)
    repository.add(order)
    session.commit()
    return _response(order)


@router.get("/{order_id}", response_model=ServiceOrderResponse)
def get_service_order(
    order_id: str,
    principal: Annotated[Principal, Depends(require_capability("orders.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> ServiceOrderResponse:
    repository = SqlAlchemyServiceOrderRepository(session)
    order = repository.get(order_id=order_id, organization_id=principal.organization_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")
    authorize(
        principal,
        capability="orders.read",
        organization_id=order.organization_id,
        location_id=order.location_id,
    )
    return _response(order)


@router.post("/{order_id}/transitions", response_model=ServiceOrderResponse)
def transition_service_order(
    order_id: str,
    payload: OrderTransitionRequest,
    principal: Annotated[Principal, Depends(require_capability("orders.write"))],
    session: Annotated[Session, Depends(get_session)],
) -> ServiceOrderResponse:
    repository = SqlAlchemyServiceOrderRepository(session)
    order = repository.get(order_id=order_id, organization_id=principal.organization_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")
    authorize(
        principal,
        capability="orders.write",
        organization_id=order.organization_id,
        location_id=order.location_id,
    )
    try:
        result = order.transition(payload.action, actor_id=principal.user_id, note=payload.note)
    except InvalidStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except UnknownActionError as exc:  # pragma: no cover - schema Literal already filters
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    repository.save(result.order)
    repository.add_event(result.event)
    session.commit()
    return _response(result.order)


@router.get("/{order_id}/events", response_model=list[ServiceOrderEventResponse])
def list_service_order_events(
    order_id: str,
    principal: Annotated[Principal, Depends(require_capability("orders.read"))],
    session: Annotated[Session, Depends(get_session)],
) -> list[ServiceOrderEventResponse]:
    repository = SqlAlchemyServiceOrderRepository(session)
    order = repository.get(order_id=order_id, organization_id=principal.organization_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")
    authorize(
        principal,
        capability="orders.read",
        organization_id=order.organization_id,
        location_id=order.location_id,
    )
    return [
        ServiceOrderEventResponse(
            event_id=event.event_id,
            order_id=event.order_id,
            from_state=event.from_state,
            to_state=event.to_state,
            action=event.action,
            actor_id=event.actor_id,
            note=event.note,
            occurred_at=event.occurred_at,
        )
        for event in repository.list_events(
            order_id=order_id, organization_id=principal.organization_id
        )
    ]
