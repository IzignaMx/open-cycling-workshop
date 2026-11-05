"""Tenant-qualified resource validation within the caller's admitted transaction."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from cycling_workshop.tenancy.models import LocationRecord


def location_exists(session: Session, *, organization_id: str, location_id: str) -> bool:
    """Do not distinguish absent locations from locations owned by another tenant.

    Call after capability/scope authorization. Database failures propagate; foreign
    keys remain the final integrity boundary rather than becoming client errors.
    """
    return (
        session.scalar(
            select(LocationRecord.id).where(
                LocationRecord.id == location_id,
                LocationRecord.organization_id == organization_id,
            )
        )
        is not None
    )
