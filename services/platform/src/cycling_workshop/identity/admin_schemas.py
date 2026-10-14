from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StrictBool,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema

from cycling_workshop.identity.roles import CAPABILITIES, LEGACY_ROLE_BUNDLES

NON_NUL_PATTERN = r"^[^\x00]*$"

Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200, pattern=NON_NUL_PATTERN),
]
Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=160, pattern=NON_NUL_PATTERN),
]
ScopeId = Annotated[str, StringConstraints(min_length=1, max_length=36, pattern=NON_NUL_PATTERN)]
NewPassword = Annotated[SecretStr, Field(min_length=12, max_length=1024)]
Version = Annotated[int, Field(strict=True, ge=1)]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class GrantSelection(StrictRequest):
    role: str | None = None
    capabilities: list[str] | None = Field(default=None, max_length=len(CAPABILITIES))

    def resolved_grants(self) -> frozenset[str]:
        if (self.role is None) == (self.capabilities is None):
            raise ValueError("choose exactly one role or capability snapshot")
        if self.role is not None:
            if self.role not in LEGACY_ROLE_BUNDLES:
                raise ValueError("unknown role")
            return LEGACY_ROLE_BUNDLES[self.role]
        grants = frozenset(self.capabilities or [])
        if not grants <= CAPABILITIES:
            raise ValueError("only implemented concrete capabilities may be granted")
        return grants


class CreateUserRequest(GrantSelection):
    username: Username
    display_name: Name
    location_id: ScopeId | None
    password: NewPassword
    is_owner: bool = Field(default=False, strict=True)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        # Normalize before max_length: Unicode lowercase can expand characters.
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_grants(self) -> Self:
        self.resolved_grants()
        return self


class PatchUserRequest(GrantSelection):
    expected_version: Version
    display_name: Name | SkipJsonSchema[None] = None
    location_id: ScopeId | None = None
    is_active: StrictBool | SkipJsonSchema[None] = None
    is_owner: StrictBool | SkipJsonSchema[None] = None

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        changes = self.model_fields_set - {"expected_version"}
        if not changes:
            raise ValueError("at least one change is required")
        for field in ("display_name", "is_active", "is_owner"):
            if field in changes and getattr(self, field) is None:
                raise ValueError("a non-null value is required")
        if changes & {"role", "capabilities"}:
            self.resolved_grants()
        return self


class VersionRequest(StrictRequest):
    expected_version: Version


class ResetPasswordRequest(VersionRequest):
    new_password: NewPassword


class ChangePasswordRequest(StrictRequest):
    current_password: Annotated[SecretStr, Field(min_length=1, max_length=1024)]
    new_password: NewPassword


class UserResponse(BaseModel):
    user_id: str
    organization_id: str
    location_id: str | None
    username: str
    display_name: str
    capabilities: list[str]
    is_active: bool
    is_owner: bool
    version: int


class UserPage(BaseModel):
    items: list[UserResponse]
    next_cursor: str | None


class RoleResponse(BaseModel):
    name: str
    capabilities: list[str]


class RoleCatalogResponse(BaseModel):
    roles: list[RoleResponse]
    capabilities: list[str]


class RoleCatalogV2Response(RoleCatalogResponse):
    model_config = ConfigDict(extra="forbid")
    catalog_version: Literal[2]
    legacy_wildcard_capabilities: list[str] = Field(min_length=17, max_length=17)


class CreateLocationRequest(StrictRequest):
    name: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=160, pattern=NON_NUL_PATTERN
        ),
    ]


class LocationResponse(BaseModel):
    location_id: str
    organization_id: str
    name: str


class LocationPage(BaseModel):
    items: list[LocationResponse]
    next_cursor: str | None
