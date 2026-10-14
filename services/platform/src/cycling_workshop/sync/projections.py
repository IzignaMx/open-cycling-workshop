from __future__ import annotations

from cycling_workshop.bicycles.domain import Bicycle
from cycling_workshop.customers.domain import Customer
from cycling_workshop.service_orders.domain import ServiceOrder


def customer_payload(customer: Customer) -> dict[str, object]:
    return {
        "customer_id": customer.customer_id,
        "organization_id": customer.organization_id,
        "location_id": customer.location_id,
        "display_name": customer.display_name,
        "email": customer.email,
        "phone": customer.phone,
        "created_at": customer.created_at.isoformat(),
        "updated_at": customer.updated_at.isoformat(),
        "version": customer.version,
    }


def bicycle_payload(bicycle: Bicycle) -> dict[str, object]:
    return {
        "bicycle_id": bicycle.bicycle_id,
        "customer_id": bicycle.customer_id,
        "organization_id": bicycle.organization_id,
        "location_id": bicycle.location_id,
        "brand": bicycle.brand,
        "model": bicycle.model,
        "bicycle_type": bicycle.bicycle_type,
        "wheel_size": bicycle.wheel_size,
        "notes": bicycle.notes,
        "created_at": bicycle.created_at.isoformat(),
        "updated_at": bicycle.updated_at.isoformat(),
        "version": bicycle.version,
    }


def order_payload(order: ServiceOrder) -> dict[str, object]:
    return {
        "order_id": order.order_id,
        "customer_id": order.customer_id,
        "bicycle_id": order.bicycle_id,
        "organization_id": order.organization_id,
        "location_id": order.location_id,
        "state": order.state,
        "reported_problem": order.reported_problem,
        "intake_condition": order.intake_condition,
        "accessories": order.accessories,
        "priority": order.priority,
        "diagnosis": order.diagnosis,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
        "version": order.version,
    }
