"""Unmounted ASGI byte admission; no parsing, response, authority or SQL.

Receive cancellation is cooperative, not a hard wall-time cutoff. The caller
owns the original ingress deadline and later canonical decoding/business checks.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal

from starlette.types import Receive

from cycling_workshop.quotes.requests import MAX_REQUEST_BYTES

if TYPE_CHECKING:
    from cycling_workshop.quotes.service import QuoteDeadline


type AdmissionCode = Literal[
    "unsupported_encoding",
    "too_large",
    "disconnected",
    "deadline_expired",
    "invalid_transport",
    "receive_failed",
]


class QuoteAdmissionError(ValueError):
    """Fixed internal category, never a raw receiver/header/body message."""

    def __init__(self, code: AdmissionCode) -> None:
        self.code = code
        super().__init__(code)


def _remaining(deadline: QuoteDeadline) -> float:
    try:
        return deadline.remaining_ms() / 1000
    except TimeoutError:
        raise QuoteAdmissionError("deadline_expired") from None


def _encoding(headers: list[tuple[bytes, bytes]]) -> None:
    if type(headers) is not list:
        raise QuoteAdmissionError("invalid_transport")
    seen = False
    for pair in headers:
        if type(pair) not in (tuple, list) or len(pair) != 2:
            raise QuoteAdmissionError("invalid_transport")
        name, value = pair
        if type(name) is not bytes or type(value) is not bytes:
            raise QuoteAdmissionError("invalid_transport")
        if name.lower() == b"content-encoding":
            if seen or value.strip(b" \t").lower() != b"identity":
                raise QuoteAdmissionError("unsupported_encoding")
            seen = True


async def read_quote_body(
    receive: Receive, *, headers: list[tuple[bytes, bytes]], deadline: QuoteDeadline
) -> bytes:
    """Return at most MAX_REQUEST_BYTES; never read beyond terminal or rejection.

    Content-Length is deliberately ignored. Optional ASGI keys keep their spec
    defaults; supplied fields must have exact types. No receive task is spawned.
    """
    _remaining(deadline)
    _encoding(headers)
    body = bytearray()
    task = asyncio.current_task()
    assert task is not None
    cancellations = task.cancelling()
    while True:
        # An immediate receive (including endless empty chunks) need not yield.
        await asyncio.sleep(0)
        budget = asyncio.timeout(_remaining(deadline))
        try:
            async with budget:
                message = await receive()
        except Exception:
            # CancelledError is BaseException and propagates, not sanitized.
            if task.cancelling() > cancellations:
                raise asyncio.CancelledError from None
            if budget.expired():
                raise QuoteAdmissionError("deadline_expired") from None
            raise QuoteAdmissionError("receive_failed") from None
        if task.cancelling() > cancellations:
            raise asyncio.CancelledError
        if budget.expired():
            raise QuoteAdmissionError("deadline_expired")
        _remaining(deadline)
        if type(message) is not dict or type(message.get("type")) is not str:
            raise QuoteAdmissionError("invalid_transport")
        if message.get("type") == "http.disconnect":
            raise QuoteAdmissionError("disconnected")
        if message.get("type") != "http.request":
            raise QuoteAdmissionError("invalid_transport")
        chunk = message.get("body", b"")
        more = message.get("more_body", False)
        if type(chunk) is not bytes or type(more) is not bool:
            raise QuoteAdmissionError("invalid_transport")
        if len(chunk) > MAX_REQUEST_BYTES - len(body):
            raise QuoteAdmissionError("too_large")
        body.extend(chunk)
        if not more:
            _remaining(deadline)
            result = bytes(body)
            _remaining(deadline)
            return result
