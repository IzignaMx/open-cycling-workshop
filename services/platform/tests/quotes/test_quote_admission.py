"""Real unmounted adapter with controlled ASGI fixtures, never wire/DB proof."""

import asyncio
import time
from contextlib import suppress

import pytest
from cycling_workshop.quotes.admission import QuoteAdmissionError, read_quote_body
from cycling_workshop.quotes.requests import MAX_REQUEST_BYTES, decode_request_document
from cycling_workshop.quotes.service import QuoteDeadline


class Receiver:
    def __init__(self, events):
        self.events = iter(events)
        self.calls = 0

    async def __call__(self):
        self.calls += 1
        return next(self.events)


def run(events, headers=None, deadline=None):
    receive = Receiver(events)
    result = asyncio.run(
        read_quote_body(receive, headers=headers or [], deadline=deadline or QuoteDeadline.start())
    )
    return result, receive.calls


@pytest.mark.parametrize("size", [0, 1, MAX_REQUEST_BYTES - 1, MAX_REQUEST_BYTES])
@pytest.mark.parametrize("split", [False, True])
def test_actual_bytes_at_boundary(size, split):
    body = b"x" * size
    events = (
        [
            {"type": "http.request", "body": body[:1], "more_body": True},
            {"type": "http.request", "body": body[1:]},
        ]
        if split
        else [{"type": "http.request", "body": body}]
    )
    result, calls = run(events)
    assert result == body and type(result) is bytes
    assert calls == len(events)


@pytest.mark.parametrize(
    "events",
    [
        [{"type": "http.request", "body": b"x" * (MAX_REQUEST_BYTES + 1)}],
        [
            {"type": "http.request", "body": b"x" * MAX_REQUEST_BYTES, "more_body": True},
            {"type": "http.request", "body": b"x"},
        ],
    ],
)
def test_excess_bytes_stop_before_next_receive(events):
    receive = Receiver([*events, {"type": "must_not_read"}])
    with pytest.raises(QuoteAdmissionError, match=r"^too_large$"):
        asyncio.run(read_quote_body(receive, headers=[], deadline=QuoteDeadline.start()))
    assert receive.calls == len(events)


@pytest.mark.parametrize(
    "headers",
    [
        [],
        [(b"Content-Encoding", b" \tIDENTITY\t ")],
        [(b"content-length", b"0")],
        [(b"content-length", b"invalid")],
        [(b"content-length", b"1"), (b"Content-Length", b"999999999999999999999999999")],
    ],
)
def test_header_policy_does_not_trust_length(headers):
    result, calls = run([{"type": "http.request", "body": b"actual"}], headers)
    assert result == b"actual" and calls == 1


@pytest.mark.parametrize(
    "headers",
    [
        [(b"content-encoding", value)]
        for value in [
            b"gzip",
            b"deflate",
            b"",
            b"identity,identity",
            b"identity,gzip",
            b"\nidentity",
            b"identity\r",
            b"\xffidentity",
        ]
    ]
    + [[(b"Content-Encoding", b"identity"), (b"content-encoding", b"identity")]],
)
def test_unsupported_encoding_before_receive(headers):
    receive = Receiver([])
    with pytest.raises(QuoteAdmissionError, match=r"^unsupported_encoding$"):
        asyncio.run(read_quote_body(receive, headers=headers, deadline=QuoteDeadline.start()))
    assert receive.calls == 0


@pytest.mark.parametrize(
    "headers", [[(b"x", "secret-canary")], [("x", b"x")], [(b"x",)], [None], None]
)
def test_malformed_headers_fixed_failure_before_receive(headers):
    receive = Receiver([])
    with pytest.raises(QuoteAdmissionError, match=r"^invalid_transport$"):
        asyncio.run(read_quote_body(receive, headers=headers, deadline=QuoteDeadline.start()))
    assert receive.calls == 0


@pytest.mark.parametrize(
    "event",
    [
        None,
        [],
        {},
        {"type": "websocket.receive"},
        {"type": "http.request", "body": "secret-canary"},
        {"type": "http.request", "body": bytearray()},
        {"type": "http.request", "more_body": 1},
        {"type": "http.request", "more_body": None},
    ],
)
def test_malformed_events_are_fixed_failures(event):
    receive = Receiver([event, {"type": "must_not_read"}])
    with pytest.raises(QuoteAdmissionError, match=r"^invalid_transport$"):
        asyncio.run(read_quote_body(receive, headers=[], deadline=QuoteDeadline.start()))
    assert receive.calls == 1


def test_optional_fields_empty_chunks_and_no_read_ahead():
    result, calls = run(
        [
            {"type": "http.request", "more_body": True},
            {"type": "http.request", "body": b"", "more_body": True},
            {"type": "http.request", "extension": "ignored"},
            {"type": "http.disconnect"},
        ]
    )
    assert result == b"" and calls == 3


@pytest.mark.parametrize(
    "prefix", [[], [{"type": "http.request", "body": b"{", "more_body": True}]]
)
def test_disconnect_stops_without_partial_return(prefix):
    receive = Receiver([*prefix, {"type": "http.disconnect"}, {"type": "must_not_read"}])
    with pytest.raises(QuoteAdmissionError, match=r"^disconnected$"):
        asyncio.run(read_quote_body(receive, headers=[], deadline=QuoteDeadline.start()))
    assert receive.calls == len(prefix) + 1


def test_raw_utf8_is_not_decoded_until_canonical_decoder():
    raw = '{"name":"é"}'.encode()
    split = raw.index(b"\xc3") + 1
    body, _ = run(
        [
            {"type": "http.request", "body": raw[:split], "more_body": True},
            {"type": "http.request", "body": raw[split:]},
        ]
    )
    assert decode_request_document([body]) == {"name": "é"}
    assert run([{"type": "http.request", "body": b"\xff"}])[0] == b"\xff"


@pytest.mark.parametrize("expires", [0.0, 0.0009])
def test_expired_deadline_never_receives(expires):
    receive = Receiver([])
    with pytest.raises(QuoteAdmissionError, match=r"^deadline_expired$"):
        asyncio.run(
            read_quote_body(receive, headers=[], deadline=QuoteDeadline(expires, lambda: 0.0))
        )
    assert receive.calls == 0


def test_immediate_empty_chunks_consume_original_deadline():
    now = 0.0
    calls = 0

    async def receive():
        nonlocal now, calls
        calls += 1
        now += 1.0
        return {"type": "http.request", "more_body": True}

    with pytest.raises(QuoteAdmissionError, match=r"^deadline_expired$"):
        asyncio.run(read_quote_body(receive, headers=[], deadline=QuoteDeadline(8.0, lambda: now)))
    assert calls == 8


def test_terminal_receive_after_deadline_is_not_returned():
    now = 0.0

    async def receive():
        nonlocal now
        now = 8.0
        return {"type": "http.request", "body": b"complete"}

    with pytest.raises(QuoteAdmissionError, match=r"^deadline_expired$"):
        asyncio.run(read_quote_body(receive, headers=[], deadline=QuoteDeadline(8.0, lambda: now)))


@pytest.mark.parametrize("exception", [ValueError("secret-canary"), TimeoutError("secret-canary")])
def test_receiver_exception_sanitized_not_misclassified(exception):
    async def receive():
        raise exception

    with pytest.raises(QuoteAdmissionError, match=r"^receive_failed$") as caught:
        asyncio.run(read_quote_body(receive, headers=[], deadline=QuoteDeadline.start()))
    assert caught.value.code == "receive_failed"
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


def test_owned_timeout_cancels_receive_in_same_task():
    async def scenario():
        reaped = False
        owner = asyncio.current_task()

        async def receive():
            nonlocal reaped
            assert asyncio.current_task() is owner
            try:
                await asyncio.Event().wait()
            finally:
                reaped = True

        with pytest.raises(QuoteAdmissionError, match=r"^deadline_expired$"):
            await read_quote_body(
                receive, headers=[], deadline=QuoteDeadline(time.monotonic() + 0.02)
            )
        assert reaped

    asyncio.run(scenario())


@pytest.mark.parametrize("immediate", [False, True])
def test_external_cancel_propagates_and_receive_has_no_orphan(immediate):
    async def scenario():
        calls = 0
        reaped = False
        started = asyncio.Event()

        async def receive():
            nonlocal calls, reaped
            calls += 1
            started.set()
            try:
                if not immediate:
                    await asyncio.Event().wait()
                return {"type": "http.request", "more_body": True}
            finally:
                reaped = True

        task = asyncio.create_task(
            read_quote_body(receive, headers=[], deadline=QuoteDeadline.start())
        )
        await asyncio.wait_for(started.wait(), timeout=0.5)
        task.cancel("external")
        with pytest.raises(asyncio.CancelledError):
            await task
        count = calls
        await asyncio.sleep(0)
        assert reaped and calls == count and task.cancelled()

    asyncio.run(scenario())


def test_event_type_requires_exact_string():
    class EventType(str):
        pass

    with pytest.raises(QuoteAdmissionError, match=r"^invalid_transport$"):
        run([{"type": EventType("http.request")}])


def test_wait_budgets_decrease_without_replacing_original_clock(monkeypatch):
    now = 0.0
    budgets = []
    original = asyncio.timeout

    def record(delay):
        budgets.append(delay)
        return original(delay)

    monkeypatch.setattr(asyncio, "timeout", record)

    async def receive():
        nonlocal now
        now += 1.0
        return {"type": "http.request", "more_body": now < 3.0}

    deadline = QuoteDeadline(8.0, lambda: now)
    assert asyncio.run(read_quote_body(receive, headers=[], deadline=deadline)) == b""
    assert budgets == [8.0, 7.0, 6.0]
    assert deadline.expires_at == 8.0


@pytest.mark.parametrize("external", [False, True])
def test_receive_cleanup_cancellation_race_is_not_hidden(external):
    async def scenario():
        owner = asyncio.current_task()
        assert owner is not None

        async def receive():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                if external:
                    owner.cancel("external-during-timeout-cleanup")
                # Cooperative completion after cleanup, not an infinite suppressor.
                return {"type": "http.request", "body": b"late"}

        exception = asyncio.CancelledError if external else QuoteAdmissionError
        with pytest.raises(exception) as caught:
            await read_quote_body(
                receive, headers=[], deadline=QuoteDeadline(time.monotonic() + 0.02)
            )
        if not external:
            assert str(caught.value) == "deadline_expired"
        # Deliver a still-pending external cancellation before ending the fixture.
        if external:
            with suppress(asyncio.CancelledError):
                await asyncio.sleep(0)

    asyncio.run(scenario())


def test_terminal_copy_checks_original_deadline_before_return(monkeypatch):
    from cycling_workshop.quotes import admission

    now = 0.0

    class SlowCopy(bytearray):
        def __bytes__(self):
            nonlocal now
            now = 9.0
            return memoryview(self).tobytes()

    monkeypatch.setattr(admission, "bytearray", SlowCopy, raising=False)
    with pytest.raises(QuoteAdmissionError, match=r"^deadline_expired$"):
        run(
            [{"type": "http.request", "body": b"complete"}],
            deadline=QuoteDeadline(8.0, lambda: now),
        )
