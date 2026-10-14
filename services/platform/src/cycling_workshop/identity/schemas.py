from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, SecretStr

from cycling_workshop.identity.admin_schemas import ScopeId, Username


class LoginRequest(BaseModel):
    organization_id: ScopeId
    username: Username
    password: Annotated[SecretStr, Field(min_length=1, max_length=1024)]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    user_id: str
    organization_id: str
    location_id: str | None
    display_name: str
    capabilities: list[str]
