"""Synthetic PNG fixtures only; no customer images."""

from __future__ import annotations

import base64
import struct
import zlib

import pytest
from cycling_workshop.branding.images import InvalidLogo, canonicalize_logo, inspect_canonical_png


def chunk(kind: bytes, data: bytes = b"") -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def png(width: int = 2, height: int = 2, *, raw: bytes | None = None) -> bytes:
    raw = raw if raw is not None else (b"\0" + b"\x10\x40\x80\xff" * width) * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND")
    )


def encoded(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def test_actual_decode_and_canonical_round_trip() -> None:
    logo = canonicalize_logo(encoded(png()))
    assert inspect_canonical_png(logo.data) == (2, 2)
    assert logo.width == logo.height == 2
    assert logo.byte_count == len(logo.data)
    assert canonicalize_logo(encoded(logo.data)) == logo


@pytest.mark.parametrize(
    "data", [png() + b"html", png()[:-1], png(513), png(raw=b"nonsense"), png(raw=b"\0" * 1000000)]
)
def test_rejects_framing_dimensions_and_decoding_abuse(data: bytes) -> None:
    with pytest.raises(InvalidLogo):
        canonicalize_logo(encoded(data))


def test_rejects_animation_and_metadata() -> None:
    for kind in (b"acTL", b"tEXt", b"iCCP", b"zTXt"):
        data = png()[:33] + chunk(kind, b"synthetic") + png()[33:]
        with pytest.raises(InvalidLogo):
            canonicalize_logo(encoded(data))


def test_strips_permitted_color_chunks_and_preserves_pixels() -> None:
    import io

    from PIL import Image

    data = (
        png()[:33] + chunk(b"gAMA", struct.pack(">I", 45455)) + chunk(b"sRGB", b"\0") + png()[33:]
    )
    logo = canonicalize_logo(encoded(data))
    assert b"gAMA" not in logo.data and b"sRGB" not in logo.data
    with Image.open(io.BytesIO(logo.data)) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0)) == (16, 64, 128, 255)


@pytest.mark.parametrize(
    "value", ["", "%%%", "data:image/png;base64,AAAA", "AAAA\n", "é", "A" * 349529]
)
def test_strict_bounded_base64(value: str) -> None:
    with pytest.raises(InvalidLogo, match=r"^invalid logo PNG$"):
        canonicalize_logo(value)


def test_rejects_invalid_crc_and_excess_chunks_before_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cycling_workshop.branding.images as images

    def no_process(*args: object, **kwargs: object) -> None:
        pytest.fail("invalid framing allocated a decoder")

    monkeypatch.setattr(images.subprocess, "Popen", no_process)
    corrupted = bytearray(png())
    corrupted[-1] ^= 1
    too_many = png()[:33] + chunk(b"IDAT") * 1023 + png()[33:]
    oversized_ancillary = png()[:33] + chunk(b"cHRM", b"x" * 8193) + png()[33:]
    for data in (bytes(corrupted), too_many, oversized_ancillary, png() + b"<svg/>", b"<svg/>"):
        with pytest.raises(InvalidLogo):
            canonicalize_logo(encoded(data))


@pytest.mark.parametrize("raw", [b"\x05" + b"\0" * 16 + b"\0", b"\0" * 17, b"\0" * 19])
def test_invalid_filter_or_scanline_length(raw: bytes) -> None:
    with pytest.raises(InvalidLogo):
        canonicalize_logo(encoded(png(raw=raw)))


def test_rejects_extra_deflate_stream_and_truncated_stream() -> None:
    header = png()[:33]
    raw = (b"\0" + b"\0" * 8) * 2
    for compressed in (zlib.compress(raw) + zlib.compress(b"hidden"), zlib.compress(raw)[:-2]):
        with pytest.raises(InvalidLogo):
            canonicalize_logo(encoded(header + chunk(b"IDAT", compressed) + chunk(b"IEND")))


def test_palette_png_is_fully_decoded_to_rgba() -> None:
    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 3, 0, 0, 0))
        + chunk(b"PLTE", b"\x11\x22\x33")
        + chunk(b"tRNS", b"\x44")
        + chunk(b"IDAT", zlib.compress(b"\0\0"))
        + chunk(b"IEND")
    )
    logo = canonicalize_logo(encoded(data))
    assert inspect_canonical_png(logo.data) == (1, 1)
    assert b"PLTE" not in logo.data and b"tRNS" not in logo.data
    with pytest.raises(InvalidLogo):
        inspect_canonical_png(data)


def test_accepts_full_side_limit_and_very_wide_transparency() -> None:
    for width, height in ((512, 512), (512, 1), (1, 512)):
        logo = canonicalize_logo(encoded(png(width, height)))
        assert (logo.width, logo.height) == (width, height)


def test_no_waiting_decode_queue() -> None:
    import cycling_workshop.branding.images as images

    assert images._DECODER_SLOT.acquire(blocking=False)
    try:
        with pytest.raises(images.DecoderBusy):
            canonicalize_logo(encoded(png()))
    finally:
        images._DECODER_SLOT.release()
    assert canonicalize_logo(encoded(png())).width == 2


def test_timeout_kills_reaps_and_releases_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess
    import sys
    import time

    import cycling_workshop.branding.images as images

    real_popen = subprocess.Popen
    children = []

    def delayed(args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        child = real_popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(images.subprocess, "Popen", delayed)
    started = time.monotonic()
    with pytest.raises(images.DecoderUnavailable, match="deadline"):
        canonicalize_logo(encoded(png()))
    assert 1.7 <= time.monotonic() - started < 4
    assert children[0].returncode is not None
    monkeypatch.setattr(images.subprocess, "Popen", real_popen)
    assert canonicalize_logo(encoded(png())).width == 2


def test_child_enforces_real_memory_and_file_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess
    import sys

    import cycling_workshop.branding.images as images

    real_popen = subprocess.Popen
    script = """import runpy, sys, resource
worker = runpy.run_path(sys.argv[1])
from PIL import Image
original = Image.open
def checked(*args, **kwargs):
    assert resource.getrlimit(resource.RLIMIT_AS) == (134217728, 134217728)
    assert resource.getrlimit(resource.RLIMIT_FSIZE) == (262144, 262144)
    try:
        bytearray(150 * 1024 * 1024)
    except MemoryError:
        pass
    else:
        raise RuntimeError('memory ceiling not enforced')
    return original(*args, **kwargs)
Image.open = checked
sys.exit(worker['_worker_main']())
"""

    def instrumented(args: list[str], **kwargs: object) -> subprocess.Popen[bytes]:
        return real_popen([sys.executable, "-I", "-c", script, args[-1]], **kwargs)

    monkeypatch.setattr(images.subprocess, "Popen", instrumented)
    assert canonicalize_logo(encoded(png())).width == 2


def test_canonical_output_expansion_refused() -> None:
    import io
    import random

    from PIL import Image

    image = Image.frombytes("P", (400, 400), random.Random(10).randbytes(160000))
    image.putpalette(random.Random(11).randbytes(768))
    output = io.BytesIO()
    image.save(output, format="PNG")
    assert len(output.getvalue()) < 262144
    with pytest.raises(InvalidLogo):
        canonicalize_logo(encoded(output.getvalue()))


def test_interlaced_input_is_reencoded_without_interlace() -> None:
    # A one-pixel Adam7 image uses only the first pass.
    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 1))
        + chunk(b"IDAT", zlib.compress(b"\0\x11\x22\x33\xff"))
        + chunk(b"IEND")
    )
    logo = canonicalize_logo(encoded(data))
    assert logo.data[28] == 0
    assert inspect_canonical_png(logo.data) == (1, 1)


def test_bounded_parallel_load_starts_only_one_process(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess
    import sys
    import threading
    from concurrent.futures import ThreadPoolExecutor

    import cycling_workshop.branding.images as images

    real_popen = subprocess.Popen
    started = threading.Event()
    children = []
    script = (
        "import runpy,sys,time; time.sleep(0.7); "
        "w=runpy.run_path(sys.argv[1]); sys.exit(w['_worker_main']())"
    )

    def delayed(args: list[str], **kwargs: object) -> subprocess.Popen[bytes]:
        child = real_popen([sys.executable, "-I", "-c", script, args[-1]], **kwargs)
        children.append(child)
        started.set()
        return child

    monkeypatch.setattr(images.subprocess, "Popen", delayed)
    with ThreadPoolExecutor(max_workers=8) as executor:
        active = executor.submit(canonicalize_logo, encoded(png()))
        assert started.wait(1)
        for _ in range(31):
            with pytest.raises(images.DecoderBusy):
                executor.submit(canonicalize_logo, encoded(png())).result(timeout=0.2)
        assert active.result(timeout=3).width == 2
    assert len(children) == 1 and children[0].returncode == 0


def test_decoder_launch_failure_and_unexpected_output_are_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess
    import sys

    import cycling_workshop.branding.images as images

    real_popen = subprocess.Popen

    def failed(*args: object, **kwargs: object) -> None:
        raise OSError("private input and installation details must not escape")

    monkeypatch.setattr(images.subprocess, "Popen", failed)
    with pytest.raises(images.DecoderUnavailable, match=r"^logo decoder unavailable$"):
        canonicalize_logo(encoded(png()))

    def invalid(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        return real_popen(
            [sys.executable, "-c", "import sys; sys.stdout.write('not a PNG')"], **kwargs
        )

    monkeypatch.setattr(images.subprocess, "Popen", invalid)
    with pytest.raises(InvalidLogo):
        canonicalize_logo(encoded(png()))
    monkeypatch.setattr(images.subprocess, "Popen", real_popen)
    assert canonicalize_logo(encoded(png())).width == 2


def test_standalone_worker_entry_excludes_api_only_imports_and_state() -> None:
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    import cycling_workshop.branding.images as images

    # Stop at the real worker entry in a fresh isolated interpreter, before any
    # Pillow work. runpy/trace overhead is not a production timing measurement.
    script = """import json, runpy, sys
worker = sys.argv[1]
api_names = (
    'base64', 'binascii', 'hashlib', 'os', 'subprocess', 'tempfile',
    'threading', 'time', 'dataclass', 'Path', 'CanonicalLogo', '_DECODER_SLOT'
)
api_modules = ('base64', 'hashlib', 'subprocess', 'dataclasses', 'inspect', 'ast', 'dis', 'pathlib')
def trace(frame, event, arg):
    if (event == 'call' and frame.f_code.co_filename == worker
            and frame.f_code.co_name == '_worker_main'):
        print(json.dumps({
            'api_globals': [name for name in api_names if name in frame.f_globals],
            'api_modules': [name for name in api_modules if name in sys.modules],
            'has_parser': callable(frame.f_globals['_inspect']),
            'has_scanline_check': callable(frame.f_globals['_validate_scanlines']),
            'isolated': sys.flags.isolated,
        }))
        raise SystemExit(0)
    return None
sys.settrace(trace)
runpy.run_path(worker, run_name='__main__')
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(Path(images.__file__).absolute())],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        close_fds=True,
        env={"PATH": os.defpath},
        timeout=2,
        check=True,
        text=True,
    )
    assert result.stderr == ""
    assert json.loads(result.stdout) == {
        "api_globals": [],
        "api_modules": [],
        "has_parser": True,
        "has_scanline_check": True,
        "isolated": 1,
    }


def test_private_png_record_retains_typed_field_order_and_immutability() -> None:
    from typing import get_type_hints

    import cycling_workshop.branding.images as images

    expected_types = {
        "width": int,
        "height": int,
        "depth": int,
        "color": int,
        "interlace": int,
        "compressed": bytes,
        "chunks": frozenset[bytes],
    }
    parsed = images._inspect(png())
    assert isinstance(parsed, tuple)
    assert parsed._fields == tuple(expected_types)
    assert get_type_hints(images._Png) == expected_types
    assert (parsed.width, parsed.height, parsed.depth, parsed.color, parsed.interlace) == (
        2,
        2,
        8,
        6,
        0,
    )
    assert zlib.decompress(parsed.compressed) == (b"\0" + b"\x10\x40\x80\xff" * 2) * 2
    assert parsed.chunks == frozenset((b"IHDR", b"IDAT", b"IEND"))
    for name in ("width", "new_attribute"):
        with pytest.raises(AttributeError):
            setattr(parsed, name, 99)


def test_normal_api_import_keeps_frozen_logo_dataclass_and_one_shared_lock() -> None:
    import dataclasses
    import importlib

    import cycling_workshop.branding.images as images

    logo = images.CanonicalLogo(b"synthetic", "synthetic-digest", 9, 2, 2)
    assert dataclasses.is_dataclass(logo)
    assert [field.name for field in dataclasses.fields(logo)] == [
        "data",
        "sha256",
        "byte_count",
        "width",
        "height",
    ]
    attribute = "width"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(logo, attribute, 99)
    lock = images._DECODER_SLOT
    assert lock.acquire(blocking=False)
    try:
        again = importlib.import_module("cycling_workshop.branding.images")
        assert again._DECODER_SLOT is lock
        assert not again._DECODER_SLOT.acquire(blocking=False)
        assert again.canonicalize_logo is canonicalize_logo
        assert again.CanonicalLogo is images.CanonicalLogo
        assert again.InvalidLogo is InvalidLogo
    finally:
        lock.release()
