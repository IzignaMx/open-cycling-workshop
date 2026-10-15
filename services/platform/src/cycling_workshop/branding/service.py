"""Admitted profile snapshots and CAS writes serialized by tenant then actor."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.branding.assets import BrandingAssetStore
from cycling_workshop.branding.images import (
    CanonicalLogo,
    DecoderBusy,
    DecoderUnavailable,
    InvalidLogo,
    canonicalize_logo,
    inspect_canonical_png,
)
from cycling_workshop.branding.models import WorkshopBrandProfileRecord
from cycling_workshop.branding.schemas import (
    BODY_LIMIT,
    BrandingLogoResponse,
    BrandingProfileResponse,
    BrandingPutRequest,
    PaletteId,
    normalize_display_name,
)
from cycling_workshop.identity.administration import AdministrationService, require
from cycling_workshop.identity.audit import append_audit
from cycling_workshop.identity.cutover import WriteAdmission
from cycling_workshop.identity.domain import Principal
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord


def decode_logo(payload: BrandingPutRequest) -> CanonicalLogo | None:
    if payload.logo_png_base64 is None:
        return None
    try:
        return canonicalize_logo(payload.logo_png_base64)
    except InvalidLogo as exc:
        raise ApiError(422, "invalid_logo", "invalid logo") from exc
    except (DecoderBusy, DecoderUnavailable) as exc:
        raise ApiError(503, "logo_decoder_unavailable", "logo decoder unavailable") from exc


def _audit_snapshot(profile: WorkshopBrandProfileRecord) -> dict[str, object]:
    return {
        "location_id": profile.location_id,
        "version": profile.version,
        "palette_id": profile.palette_id,
        "logo_sha256": profile.logo_sha256,
        "logo_present": profile.logo_key is not None,
    }


class BrandingService:
    def __init__(self, session: Session, admission: WriteAdmission, assets: BrandingAssetStore):
        self.session, self.admission, self.assets = session, admission, assets

    def _lock(
        self, principal: Principal, location_id: str, capability: str
    ) -> tuple[Principal, LocationRecord]:
        if self.admission.protocol != 1:
            raise ApiError(409, "client_upgrade_required", "client upgrade required")
        administration = AdministrationService(self.session, self.admission)
        _, effective = administration.lock_actor(principal)
        require(effective, capability)
        administration.check_location(effective, location_id)
        location = self.session.scalar(
            select(LocationRecord)
            .where(
                LocationRecord.id == location_id,
                LocationRecord.organization_id == effective.organization_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if location is None:
            raise ApiError(403, "branding_denied", "branding scope or capability denied")
        self.admission.check_expiry(effective)
        return effective, location

    def _profile(self, principal: Principal, location_id: str) -> WorkshopBrandProfileRecord | None:
        return self.session.scalar(
            select(WorkshopBrandProfileRecord)
            .where(
                WorkshopBrandProfileRecord.organization_id == principal.organization_id,
                WorkshopBrandProfileRecord.location_id == location_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def read(self, principal: Principal, location_id: str) -> BrandingProfileResponse:
        effective, location = self._lock(principal, location_id, "branding.read")
        response = self._response(effective, location, self._profile(effective, location_id))
        self.admission.check_expiry(effective)
        return response

    def put(
        self,
        principal: Principal,
        location_id: str,
        payload: BrandingPutRequest,
        logo: CanonicalLogo | None,
    ) -> BrandingProfileResponse:
        effective, location = self._lock(principal, location_id, "branding.write")
        profile = self._profile(effective, location_id)
        version = profile.version if profile else 0
        if payload.expected_version != version:
            raise ApiError(409, "branding_version_conflict", "workshop branding has changed")
        before = _audit_snapshot(profile) if profile else None
        changed = [
            field
            for field in ("display_name", "palette_id")
            if profile is None or getattr(profile, field) != getattr(payload, field)
        ]
        if profile is None or profile.logo_sha256 != (logo.sha256 if logo else None):
            changed.append("logo")
        # Durable immutable bytes precede the SQL reference, strictly after
        # fresh authority, scope and CAS checks. Rollback may leave an orphan;
        # it can never leave a committed reference to partial bytes.
        try:
            key = self.assets.put(effective.organization_id, logo) if logo else None
        except (OSError, ValueError) as exc:
            raise ApiError(
                503, "branding_storage_unavailable", "branding storage unavailable"
            ) from exc
        self.admission.check_expiry(effective)
        if profile is None:
            profile = WorkshopBrandProfileRecord(
                organization_id=effective.organization_id, location_id=location.id
            )
            self.session.add(profile)
        profile.schema_version = 1
        profile.version = version + 1
        profile.display_name, profile.palette_id = payload.display_name, payload.palette_id
        profile.logo_key = key
        profile.logo_sha256 = logo.sha256 if logo else None
        profile.logo_byte_count = logo.byte_count if logo else None
        profile.logo_width = logo.width if logo else None
        profile.logo_height = logo.height if logo else None
        profile.updated_at, profile.updated_by = datetime.now(UTC), effective.user_id
        self.session.flush()
        append_audit(
            self.session,
            organization_id=effective.organization_id,
            actor_id=effective.user_id,
            target_id=None,
            target_type="location",
            action="branding.updated",
            before=before,
            after={**_audit_snapshot(profile), "changed_fields": changed},
        )
        response = self._response(effective, location, profile)
        self.admission.check_expiry(effective)
        return response

    def _response(
        self,
        principal: Principal,
        location: LocationRecord,
        profile: WorkshopBrandProfileRecord | None,
    ) -> BrandingProfileResponse:
        organization = self.session.get(OrganizationRecord, principal.organization_id)
        assert organization is not None  # already locked and validated
        if profile is None:
            try:
                display_name = normalize_display_name(location.name)
            except (ValueError, UnicodeError):
                display_name = "Taller"
            return BrandingProfileResponse(
                schema_version=1,
                organization_id=principal.organization_id,
                location_id=location.id,
                dataset_incarnation=UUID(organization.dataset_incarnation),
                version=0,
                display_name=display_name,
                palette_id="bosque",
                logo_state="none",
                logo=None,
                logo_diagnostic=None,
                updated_at=None,
                updated_by=None,
            )
        logo = None
        state: str = "none"
        if profile.logo_key is not None:
            assert profile.logo_sha256 is not None and profile.logo_byte_count is not None
            assert profile.logo_width is not None and profile.logo_height is not None
            encoded = None
            state = "unavailable"
            try:
                data = self.assets.read(
                    principal.organization_id,
                    profile.logo_key,
                    sha256=profile.logo_sha256,
                    byte_count=profile.logo_byte_count,
                )
                if inspect_canonical_png(data) != (profile.logo_width, profile.logo_height):
                    raise ValueError("invalid asset dimensions")
                encoded = base64.b64encode(data).decode("ascii")
                state = "available"
            except (OSError, ValueError):
                pass  # Never expose filesystem paths or reuse old image bytes.
            logo = BrandingLogoResponse(
                mime_type="image/png",
                sha256=profile.logo_sha256,
                byte_count=profile.logo_byte_count,
                width=profile.logo_width,
                height=profile.logo_height,
                png_base64=encoded,
            )
        updated_at = profile.updated_at
        if updated_at.tzinfo is None:  # SQLite surrogate discards timezone information.
            updated_at = updated_at.replace(tzinfo=UTC)
        response = BrandingProfileResponse(
            schema_version=1,
            organization_id=principal.organization_id,
            location_id=location.id,
            dataset_incarnation=UUID(organization.dataset_incarnation),
            version=profile.version,
            display_name=profile.display_name,
            palette_id=cast(PaletteId, profile.palette_id),
            logo_state=cast("Literal['none', 'available', 'unavailable']", state),
            logo=logo,
            logo_diagnostic="asset_unavailable" if state == "unavailable" else None,
            updated_at=updated_at,
            updated_by=profile.updated_by,
        )
        if len(response.model_dump_json().encode("utf-8")) > BODY_LIMIT:
            raise ApiError(503, "branding_unavailable", "branding profile unavailable")
        return response
