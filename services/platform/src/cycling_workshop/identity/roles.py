"""Starter bundles are snapshots, never an authorization shortcut."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

BUSINESS_CAPABILITIES = frozenset(
    {
        "customers.read",
        "customers.write",
        "bicycles.read",
        "bicycles.write",
        "orders.read",
        "orders.write",
        "inventory.read",
        "inventory.write",
        "sync.pull",
        "sync.push",
    }
)
ADMIN_CAPABILITIES = frozenset(
    {
        "users.read",
        "users.write",
        "users.grants.write",
        "users.sessions.revoke",
        "users.credentials.reset",
        "locations.read",
        "locations.create",
    }
)
# This literal snapshot is immutable. Never derive wildcard authority from a
# growing catalog: existing accounts and old tokens must acquire no new grants.
LEGACY_WILDCARD_CAPABILITIES = frozenset(
    {
        "customers.read",
        "customers.write",
        "bicycles.read",
        "bicycles.write",
        "orders.read",
        "orders.write",
        "inventory.read",
        "inventory.write",
        "sync.pull",
        "sync.push",
        "users.read",
        "users.write",
        "users.grants.write",
        "users.sessions.revoke",
        "users.credentials.reset",
        "locations.read",
        "locations.create",
    }
)
BRANDING_CAPABILITIES = frozenset({"branding.read", "branding.write"})
# Quote grants are explicit-only; never extend the frozen business/legacy sets.
QUOTE_CAPABILITIES = frozenset({"quotes.read", "quotes.write", "quotes.authorize"})
CAPABILITIES = LEGACY_WILDCARD_CAPABILITIES | BRANDING_CAPABILITIES | QUOTE_CAPABILITIES
LEGACY_ROLE_BUNDLES: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "Owner": LEGACY_WILDCARD_CAPABILITIES,
        "Administrator": LEGACY_WILDCARD_CAPABILITIES - {"locations.create"},
        "Manager": BUSINESS_CAPABILITIES | {"locations.read"},
        "Mechanic": BUSINESS_CAPABILITIES - {"customers.write", "inventory.write"}
        | {"locations.read"},
        "Reception": BUSINESS_CAPABILITIES - {"inventory.write"} | {"locations.read"},
        "Sales": BUSINESS_CAPABILITIES - {"orders.write", "inventory.write"} | {"locations.read"},
        "Viewer": frozenset(
            {
                "customers.read",
                "bicycles.read",
                "orders.read",
                "inventory.read",
                "sync.pull",
                "locations.read",
            }
        ),
        "TechnicalAdmin": frozenset(),
    }
)


# New clients select these starter snapshots and submit explicit literals.
ROLE_BUNDLES: dict[str, frozenset[str]] = {
    name: grants
    | (
        {"branding.read", "branding.write"}
        if name in {"Owner", "Administrator"}
        else {"branding.read"}
        if name != "TechnicalAdmin"
        else set()
    )
    | (QUOTE_CAPABILITIES if name == "Owner" else frozenset())
    for name, grants in LEGACY_ROLE_BUNDLES.items()
}


def concrete_capabilities(values: frozenset[str] | list[str]) -> frozenset[str]:
    """Resolve known explicit literals plus the fixed historical wildcard set."""
    literals = frozenset(values) & CAPABILITIES
    return literals | LEGACY_WILDCARD_CAPABILITIES if "*" in values else literals
