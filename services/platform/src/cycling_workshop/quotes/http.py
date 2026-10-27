"""Private quote namespace classification only; no quote routes or body adapter."""

from __future__ import annotations


def quote_path(path: str) -> bool:
    """Classify the once-decoded ASGI path without changing request bytes."""
    if path == "/api/v1/quotes" or path.startswith("/api/v1/quotes/"):
        return True
    prefix = "/api/v1/service-orders/"
    if not path.startswith(prefix):
        return False
    order, separator, rest = path[len(prefix) :].partition("/")
    return bool(order and separator) and (rest == "quotes" or rest.startswith("quotes/"))
