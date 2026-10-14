"""Bounded PNG admission and isolated, killable full image decoding.

Only the standalone child imports Pillow. API workers do framing checks before
reserving the single decoder slot; no image or diagnostic crosses into logs.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import os
import struct
import subprocess
import sys
import tempfile
import threading
import time
import warnings
import zlib
from dataclasses import dataclass
from pathlib import Path

MAX_PNG_BYTES = 262_144
MAX_SIDE = 512
MAX_CHUNKS = 1024
MAX_ANCILLARY_BYTES = 8192
DECODER_SECONDS = 2.0
DECODER_MEMORY_BYTES = 128 * 1024 * 1024
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_ALLOWED = frozenset((b"IHDR", b"PLTE", b"tRNS", b"IDAT", b"IEND", b"sRGB", b"gAMA", b"cHRM"))
_DECODER_SLOT = threading.Lock()


class InvalidLogo(ValueError):
    def __init__(self) -> None:
        super().__init__("invalid logo PNG")


class DecoderBusy(Exception):
    """The API worker already has an active decoder. There is no waiting queue."""


class DecoderUnavailable(Exception):
    """The bounded decoder could not run or exceeded its resource deadline."""


@dataclass(frozen=True)
class CanonicalLogo:
    data: bytes
    sha256: str
    byte_count: int
    width: int
    height: int


@dataclass(frozen=True)
class _Png:
    width: int
    height: int
    depth: int
    color: int
    interlace: int
    compressed: bytes
    chunks: frozenset[bytes]


def _inspect(data: bytes) -> _Png:
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_PNG_BYTES:
        raise InvalidLogo()
    if not data.startswith(_PNG_SIGNATURE):
        raise InvalidLogo()
    offset, count, ancillary, palette_size = 8, 0, 0, 0
    width = height = depth = color = interlace = 0
    seen: set[bytes] = set()
    compressed = bytearray()
    while offset < len(data):
        count += 1
        if count > MAX_CHUNKS or len(data) - offset < 12:
            raise InvalidLogo()
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(data) or kind not in _ALLOWED:
            raise InvalidLogo()
        payload = data[offset + 8 : end - 4]
        crc = struct.unpack_from(">I", data, end - 4)[0]
        if zlib.crc32(kind + payload) != crc or (count == 1 and kind != b"IHDR"):
            raise InvalidLogo()
        if kind != b"IDAT":
            ancillary += length
            if ancillary > MAX_ANCILLARY_BYTES or kind in seen:
                raise InvalidLogo()
        if kind == b"IHDR":
            if count != 1 or length != 13:
                raise InvalidLogo()
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
            if (
                not 1 <= width <= MAX_SIDE
                or not 1 <= height <= MAX_SIDE
                or depth not in depths.get(color, ())
                or compression != 0
                or filtering != 0
                or interlace not in (0, 1)
            ):
                raise InvalidLogo()
        elif kind == b"IDAT":
            if color == 3 and not palette_size:
                raise InvalidLogo()
            compressed.extend(payload)
        elif kind == b"IEND":
            if length or end != len(data) or b"IDAT" not in seen or not compressed:
                raise InvalidLogo()
            return _Png(
                width, height, depth, color, interlace, bytes(compressed), frozenset(seen | {kind})
            )
        else:
            if b"IDAT" in seen:
                raise InvalidLogo()
            if kind == b"PLTE":
                if color in (0, 4) or not 0 < length <= 768 or length % 3 or b"tRNS" in seen:
                    raise InvalidLogo()
                palette_size = length // 3
                if color == 3 and palette_size > 2**depth:
                    raise InvalidLogo()
            elif kind == b"tRNS":
                if not (
                    (color == 0 and length == 2)
                    or (color == 2 and length == 6)
                    or (color == 3 and 0 < length <= palette_size)
                ):
                    raise InvalidLogo()
                if color in (0, 2) and any(
                    v[0] >= 2**depth for v in struct.iter_unpack(">H", payload)
                ):
                    raise InvalidLogo()
            elif kind in (b"gAMA", b"cHRM", b"sRGB"):
                if b"PLTE" in seen or length != {b"gAMA": 4, b"cHRM": 32, b"sRGB": 1}[kind]:
                    raise InvalidLogo()
                if (kind == b"gAMA" and payload == b"\0" * 4) or (
                    kind == b"sRGB" and payload[0] > 3
                ):
                    raise InvalidLogo()
        seen.add(kind)
        offset = end
    raise InvalidLogo()


def inspect_canonical_png(data: bytes) -> tuple[int, int]:
    """Validate bounded framing, CRCs, ordering and dimensions, without native decoding."""
    parsed = _inspect(data)
    if (
        parsed.chunks != frozenset((b"IHDR", b"IDAT", b"IEND"))
        or parsed.depth != 8
        or parsed.color not in (2, 6)
        or parsed.interlace != 0
    ):
        raise InvalidLogo()
    return parsed.width, parsed.height


def _validate_scanlines(parsed: _Png) -> None:
    # Pillow can ignore extra decompressed pixels or compressed trailing streams.
    # Enforce the exact scanline length before the full decoder touches the data.
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[parsed.color]
    passes = (
        ((0, 0, 1, 1),)
        if not parsed.interlace
        else (
            (0, 0, 8, 8),
            (4, 0, 8, 8),
            (0, 4, 4, 8),
            (2, 0, 4, 4),
            (0, 2, 2, 4),
            (1, 0, 2, 2),
            (0, 1, 1, 2),
        )
    )
    rows: list[tuple[int, int]] = []
    for x, y, dx, dy in passes:
        w = max(0, (parsed.width - x + dx - 1) // dx)
        h = max(0, (parsed.height - y + dy - 1) // dy)
        if w and h:
            rows.append(((w * channels * parsed.depth + 7) // 8 + 1, h))
    expected = sum(size * count for size, count in rows)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(parsed.compressed, expected + 1)
    if len(raw) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise InvalidLogo()
    offset = 0
    for size, count in rows:
        for _ in range(count):
            if raw[offset] > 4:
                raise InvalidLogo()
            offset += size


def canonicalize_logo(png_base64: str) -> CanonicalLogo:
    if not isinstance(png_base64, str) or not 0 < len(png_base64) <= 4 * ((MAX_PNG_BYTES + 2) // 3):
        raise InvalidLogo()
    try:
        data = base64.b64decode(png_base64, validate=True)
    except (ValueError, binascii.Error):
        raise InvalidLogo() from None
    if base64.b64encode(data).decode("ascii") != png_base64:
        raise InvalidLogo()
    parsed = _inspect(data)
    dimensions = (parsed.width, parsed.height)
    if sys.platform != "linux":
        raise DecoderUnavailable("bounded logo decoding requires Linux")
    if not _DECODER_SLOT.acquire(blocking=False):
        raise DecoderBusy("logo decoder busy")
    process: subprocess.Popen[bytes] | None = None
    try:
        deadline = time.monotonic() + DECODER_SECONDS
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen(
                [sys.executable, "-I", str(Path(__file__).absolute())],
                stdin=subprocess.PIPE,
                stdout=output,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                env={"PATH": os.defpath},
            )
            try:
                process.communicate(data, timeout=max(0.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise DecoderUnavailable("logo decoder deadline exceeded") from None
            if process.returncode == 2:
                raise InvalidLogo()
            if process.returncode != 0:
                raise DecoderUnavailable("logo decoder unavailable")
            if not 0 < os.fstat(output.fileno()).st_size <= MAX_PNG_BYTES:
                raise InvalidLogo()
            output.seek(0)
            canonical = output.read(MAX_PNG_BYTES + 1)
        width, height = inspect_canonical_png(canonical)
        if (width, height) != dimensions:
            raise InvalidLogo()
        return CanonicalLogo(
            canonical, hashlib.sha256(canonical).hexdigest(), len(canonical), width, height
        )
    except OSError:
        raise DecoderUnavailable("logo decoder unavailable") from None
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        _DECODER_SLOT.release()


def _worker_main() -> int:
    # This fresh interpreter has not loaded application/DB state or Pillow yet.
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (DECODER_MEMORY_BYTES, DECODER_MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_PNG_BYTES, MAX_PNG_BYTES))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    try:
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = MAX_SIDE * MAX_SIDE
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        data = sys.stdin.buffer.read(MAX_PNG_BYTES + 1)
        parsed = _inspect(data)
        _validate_scanlines(parsed)
        with Image.open(io.BytesIO(data), formats=("PNG",)) as source:
            if source.size != (parsed.width, parsed.height) or getattr(source, "n_frames", 1) != 1:
                raise InvalidLogo()
            source.load()
            mode = "RGBA" if "A" in source.getbands() or "transparency" in source.info else "RGB"
            converted = source.convert(mode)
            # Creating from raw pixels discards all source metadata/color chunks.
            clean = Image.frombytes(mode, source.size, converted.tobytes())
            output = io.BytesIO()
            clean.save(output, format="PNG", optimize=False, compress_level=9)
            result = output.getvalue()
        inspect_canonical_png(result)
        sys.stdout.buffer.write(result)
        sys.stdout.buffer.flush()
        return 0
    except (
        InvalidLogo,
        ValueError,
        OSError,
        SyntaxError,
        zlib.error,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return 2


if __name__ == "__main__":
    raise SystemExit(_worker_main())
