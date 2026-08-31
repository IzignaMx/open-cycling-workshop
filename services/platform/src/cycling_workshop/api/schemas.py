from __future__ import annotations

from pydantic import BaseModel


class HealthReadyResponse(BaseModel):
    status: str = "ready"
    environment: str


class HealthUnavailableResponse(BaseModel):
    status: str = "unavailable"
