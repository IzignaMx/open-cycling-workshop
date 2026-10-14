"""Starter bundles are snapshots, never an authorization shortcut."""

from __future__ import annotations

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
CAPABILITIES = BUSINESS_CAPABILITIES | ADMIN_CAPABILITIES
ROLE_BUNDLES: dict[str, frozenset[str]] = {
    "Owner": CAPABILITIES,
    "Administrator": CAPABILITIES - {"locations.create"},
    "Manager": BUSINESS_CAPABILITIES | {"locations.read"},
    "Mechanic": BUSINESS_CAPABILITIES - {"customers.write", "inventory.write"} | {"locations.read"},
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


def concrete_capabilities(values: frozenset[str] | list[str]) -> frozenset[str]:
    """Resolve legacy wildcard authority only over the implemented catalog."""
    return CAPABILITIES if "*" in values else frozenset(values)
