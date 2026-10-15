"""Redact only inventory query strings before Uvicorn formats access records."""

from __future__ import annotations

import logging

from cycling_workshop.inventory.http import inventory_path


class InventoryAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Uvicorn's h11/httptools protocols supply client, method, quoted path
        # plus query, HTTP version and status as five arguments. The request
        # scope is deliberately untouched; routing and validation see all bytes.
        args = record.args
        if (
            record.name == "uvicorn.access"
            and isinstance(args, tuple)
            and len(args) == 5
            and isinstance(args[2], str)
        ):
            path, separator, _query = args[2].partition("?")
            if separator and inventory_path(path):
                record.args = (*args[:2], path, *args[3:])
        return True


_inventory_access_filter = InventoryAccessFilter()


def install_inventory_access_filter() -> None:
    # Logger.addFilter deduplicates the same instance. Do not replace handlers,
    # formatter, levels or propagation, nor suppress unrelated access records.
    logging.getLogger("uvicorn.access").addFilter(_inventory_access_filter)
