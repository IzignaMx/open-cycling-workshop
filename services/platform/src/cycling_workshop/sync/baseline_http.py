"""Streaming control-request cap before JSON parsing or database locks."""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from cycling_workshop.sync.baseline_schemas import CONTROL_LIMIT


def baseline_path(path: str) -> bool:
    normalized = path.rstrip("/")
    return (
        normalized.startswith("/api/v1/sync/baselines/") or normalized == "/api/v1/sync/deltas/page"
    )


class BaselineBodyLimit:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not baseline_path(scope["path"]):
            await self.app(scope, receive, send)
            return
        body_buffer = bytearray()
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > CONTROL_LIMIT:
                await send(
                    {
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"cache-control", b"no-store"),
                        ],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b'{"error":{"code":"request_too_large",'
                        b'"message":"control request exceeds limit",'
                        b'"details":{},"request_id":null}}',
                    }
                )
                return
            body_buffer.extend(message.get("body", b""))
            if not message.get("more_body", False):
                break
        # At most CONTROL_LIMIT bytes, even with chunked input. Coalesce empty chunks.
        body = bytes(body_buffer)
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
