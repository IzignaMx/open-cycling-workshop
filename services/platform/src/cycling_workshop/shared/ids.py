from __future__ import annotations

import secrets
import threading
import time
import uuid

_lock = threading.Lock()
_last_ms = -1
_sequence = 0


def new_id() -> str:
    """Return a monotonic UUIDv7-compatible identifier as a canonical string."""
    global _last_ms, _sequence

    now_ms = time.time_ns() // 1_000_000
    with _lock:
        if now_ms > _last_ms:
            _last_ms = now_ms
            _sequence = secrets.randbits(12)
        else:
            _sequence += 1
            if _sequence > 0xFFF:
                _last_ms += 1
                _sequence = 0
        timestamp_ms = _last_ms
        rand_a = _sequence

    rand_b = secrets.randbits(62)
    value = (
        (timestamp_ms & ((1 << 48) - 1)) << 80
        | 0x7 << 76
        | (rand_a & 0xFFF) << 64
        | 0b10 << 62
        | rand_b
    )
    return str(uuid.UUID(int=value))
