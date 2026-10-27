"""Redact quote queries in Uvicorn access records, never the forwarded request."""

from __future__ import annotations

import logging
from urllib.parse import unquote

from cycling_workshop.quotes.http import quote_path


class QuoteAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Uvicorn supplies client, method, re-quoted ASGI path/query, version and
        # status. Undo that formatter quoting once, not recursive URL decoding.
        # A literal percent escape left in ASGI scope.path must stay literal.
        args = record.args
        if (
            record.name == "uvicorn.access"
            and isinstance(args, tuple)
            and len(args) == 5
            and isinstance(args[2], str)
        ):
            path, separator, _query = args[2].partition("?")
            if separator and quote_path(unquote(path)):
                record.args = (*args[:2], path, *args[3:])
        return True


_quote_access_filter = QuoteAccessFilter()


def install_quote_access_filter() -> None:
    # addFilter deduplicates this exact instance; preserve logger configuration.
    logging.getLogger("uvicorn.access").addFilter(_quote_access_filter)
