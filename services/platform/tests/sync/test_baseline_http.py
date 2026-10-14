"""Control caps measure transport bytes before JSON parsing, independent of headers."""

import asyncio

import pytest
from cycling_workshop.sync.baseline_http import BaselineBodyLimit


@pytest.mark.parametrize("content_length", [None, b"0", b"1", b"99999999"])
@pytest.mark.parametrize("size", [16384, 16385])
def test_chunked_control_limit_precedes_downstream_materialization(content_length, size):
    called = []
    sent = []
    chunks = [b" " * 8000, b"", b" " * (size - 8000)]
    scope = {
        "type": "http",
        "path": "/api/v1/sync/baselines/start",
        "headers": [] if content_length is None else [(b"content-length", content_length)],
    }

    async def downstream(scope, receive, send):
        message = await receive()
        called.append(message)
        assert message["body"] == b" " * size
        assert message["more_body"] is False

    async def receive():
        chunk = chunks.pop(0)
        return {"type": "http.request", "body": chunk, "more_body": bool(chunks)}

    async def send(message):
        sent.append(message)

    asyncio.run(BaselineBodyLimit(downstream)(scope, receive, send))
    if size > 16384:
        assert called == []
        assert sent[0]["status"] == 413
        assert (b"cache-control", b"no-store") in sent[0]["headers"]
    else:
        assert len(called) == 1 and sent == []
