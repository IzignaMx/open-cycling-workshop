"""Cap raw JSON while streaming before parser, image work or database locks."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from cycling_workshop.branding.schemas import BODY_LIMIT


def branding_path(path: str) -> bool:
    parts = path.rstrip("/").split("/")
    return (
        len(parts) >= 6 and parts[:4] == ["", "api", "v1", "locations"] and parts[5] == "branding"
    )


class BrandingBodyLimit:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not branding_path(scope["path"]):
            await self.app(scope, receive, send)
            return
        buffer = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(buffer) + len(chunk) > BODY_LIMIT:
                await JSONResponse(
                    status_code=413,
                    content={"detail": "branding request exceeds limit"},
                    headers={"Cache-Control": "no-store"},
                )(scope, receive, send)
                return
            buffer.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(buffer), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
