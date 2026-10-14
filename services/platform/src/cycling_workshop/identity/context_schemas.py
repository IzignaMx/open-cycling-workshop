"""Closed wire contract for connected context verification, not activation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from cycling_workshop.identity.admin_schemas import ScopeId


class ContextPrincipal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_realm: None
    organization_id: ScopeId
    user_id: ScopeId


class AccessContextResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: Literal[1]
    principal: ContextPrincipal
    account_location_id: ScopeId | None
    selected_location_id: ScopeId
    capabilities: list[str]
    authorization_epoch: str
    policy_revision: Literal["ocwp-access-baseline-1"]
    verified_at: datetime
    offline_until: datetime
    snapshot_protocol: None
