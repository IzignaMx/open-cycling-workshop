from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    organization_id: str = Field(min_length=1, max_length=36)
    username: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    user_id: str
    organization_id: str
    location_id: str | None
    display_name: str
    capabilities: list[str]
