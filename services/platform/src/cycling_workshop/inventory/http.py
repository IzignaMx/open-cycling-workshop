"""The private inventory namespace, without similarly prefixed unrelated paths."""

from __future__ import annotations


def inventory_path(path: str) -> bool:
    return path == "/api/v1/inventory" or path.startswith("/api/v1/inventory/")
