"""Permanent enrollment fence for legacy writers, not quote authorization.

Call after the existing organization/actor barrier and before any product lock.
The organization lock also serializes the absent-lineage case with enrollment.
Only bounded scalar columns are read; denied legacy writes never hydrate Text.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from cycling_workshop.quotes.models import QuoteLineageRecord
from cycling_workshop.service_orders.models import ServiceOrderRecord

MANAGED_ORDER_MESSAGE = "quote-managed order requires a supported quote command"


@dataclass(frozen=True, slots=True)
class LegacyOrderFence:
    location_id: str
    managed: bool


def lock_legacy_order(
    session: Session, *, organization_id: str, order_id: str
) -> LegacyOrderFence | None:
    location = session.scalar(
        select(ServiceOrderRecord.location_id)
        .where(
            ServiceOrderRecord.organization_id == organization_id,
            ServiceOrderRecord.id == order_id,
        )
        .with_for_update()
    )
    if location is None:
        return None
    # Never condition membership on quote grants, head state or reconstruction.
    # Even malformed retained quote history cannot restore a legacy bypass.
    lineage = session.scalar(
        select(QuoteLineageRecord.lineage_id)
        .where(
            QuoteLineageRecord.organization_id == organization_id,
            QuoteLineageRecord.order_id == order_id,
        )
        .with_for_update()
    )
    return LegacyOrderFence(location, lineage is not None)
