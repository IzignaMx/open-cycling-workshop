"""Bounded closed shared-workshop profile contract; never operational identity."""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Annotated, Literal, Self, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cycling_workshop.identity.admin_schemas import ScopeId

BODY_LIMIT = 393216
PNG_LIMIT = 262144
PaletteId = Literal[
    "bosque",
    "arcilla",
    "tinta",
    "cobalto",
    "petroleo",
    "indigo",
    "malva",
    "frambuesa",
    "jade",
    "lima",
    "hielo",
    "lavanda",
]
PALETTE_IDS: tuple[str, ...] = get_args(PaletteId)
DisplayName = Annotated[str, Field(min_length=1, max_length=160)]
PngBase64 = Annotated[str, Field(min_length=1, max_length=349528)]


def normalize_display_name(value: str) -> str:
    value = unicodedata.normalize("NFC", value).strip()
    if not 1 <= len(value) <= 160 or any(
        unicodedata.category(char).startswith("C") for char in value
    ):
        raise ValueError("invalid display name")
    if len(value.encode("utf-8")) > 640:
        raise ValueError("invalid display name")
    return value


class BrandingPutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    expected_version: Annotated[int, Field(strict=True, ge=0)]
    display_name: DisplayName
    palette_id: PaletteId
    logo_png_base64: PngBase64 | None

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return normalize_display_name(value) if isinstance(value, str) else value


class BrandingLogoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    byte_count: Annotated[int, Field(strict=True, ge=1, le=PNG_LIMIT)]
    width: Annotated[int, Field(strict=True, ge=1, le=512)]
    height: Annotated[int, Field(strict=True, ge=1, le=512)]
    mime_type: Literal["image/png"]
    png_base64: PngBase64 | None


class BrandingProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    organization_id: ScopeId
    location_id: ScopeId
    dataset_incarnation: UUID
    version: Annotated[int, Field(strict=True, ge=0)]
    display_name: DisplayName
    palette_id: PaletteId
    logo_state: Literal["none", "available", "unavailable"]
    logo: BrandingLogoResponse | None
    logo_diagnostic: Literal["asset_unavailable"] | None
    updated_at: datetime | None
    updated_by: ScopeId | None

    @field_validator("display_name")
    @classmethod
    def canonical_name(cls, value: str) -> str:
        if normalize_display_name(value) != value:
            raise ValueError("display name is not canonical")
        return value

    @model_validator(mode="after")
    def coherent_state(self) -> Self:
        if self.logo_state == "none":
            valid = self.logo is None and self.logo_diagnostic is None
        elif self.logo_state == "available":
            valid = (
                self.logo is not None
                and self.logo.png_base64 is not None
                and self.logo_diagnostic is None
            )
        else:
            valid = (
                self.logo is not None
                and self.logo.png_base64 is None
                and self.logo_diagnostic == "asset_unavailable"
            )
        if self.version == 0:
            valid = (
                valid
                and self.updated_at is None
                and self.updated_by is None
                and self.logo_state == "none"
                and self.palette_id == "bosque"
            )
        else:
            valid = valid and self.updated_at is not None and self.updated_by is not None
        if not valid:
            raise ValueError("inconsistent branding state")
        return self
