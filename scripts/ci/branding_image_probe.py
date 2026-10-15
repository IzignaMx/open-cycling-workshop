#!/usr/bin/env python3
"""Synthetic installed-image smoke; QEMU evidence is not physical ARM qualification.

Feed this script over stdin to the unprivileged, hardened ARM64 API image. Only
closed JSON leaves the container. No decoder limits, input paths or environment
are changed, and there is no retry/native fallback for a failed emulated decode.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import importlib.metadata
import inspect
import json
import math
import os
import platform
import re
import resource
import stat
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path
from typing import Any
from unittest.mock import patch

EMULATED = "qemu-emulated-linux-arm64"
NATIVE = "native-linux-arm64"

FAILURES = frozenset(
    (
        "image_identity",
        "probe_arguments",
        "executable_architecture",
        "runtime_identity",
        "installed_decoder",
        "decoder_limit_contract",
        "decoder_process_contract",
        "decoder_unavailable_under_emulation",
        "decoder_unavailable_on_native_arm64",
        "native_host_identity",
        "native_report_invalid",
        "decoder_rejected_fixture",
        "canonical_output",
        "unexpected_probe_failure",
    )
)


class ProbeFailure(Exception):
    def __init__(self, code: str) -> None:
        self.code = code if code in FAILURES else "unexpected_probe_failure"
        super().__init__(self.code)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ProbeFailure(code)


def synthetic_png() -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 6, 0, 0, 0))
        + chunk(b"gAMA", struct.pack(">I", 45455))
        + chunk(b"sRGB", b"\0")
        + chunk(b"IDAT", zlib.compress((b"\0" + b"\x34\x78\xab\xff" * 2) * 2))
        + chunk(b"IEND", b"")
    )


def verify_fixture_pixels(compressed: bytes) -> None:
    """Verify this fixed 2x2 RGBA output with at most 19 inflated bytes, no Pillow."""
    decoder = zlib.decompressobj()
    raw = decoder.decompress(compressed, 19)
    require(
        len(raw) == 18 and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
        "canonical_output",
    )
    expected = b"\x34\x78\xab\xff" * 2
    previous = b"\0" * 8
    for offset in (0, 9):
        kind = raw[offset]
        require(kind <= 4, "canonical_output")
        encoded = bytearray()
        for index, value in enumerate(expected):
            left = expected[index - 4] if index >= 4 else 0
            up = previous[index]
            corner = previous[index - 4] if index >= 4 else 0
            estimate = left + up - corner
            distances = (abs(estimate - left), abs(estimate - up), abs(estimate - corner))
            paeth = (left, up, corner)[distances.index(min(distances))]
            predictor = (0, left, up, (left + up) // 2, paeth)[kind]
            encoded.append((value - predictor) % 256)
        require(raw[offset + 1 : offset + 9] == encoded, "canonical_output")
        previous = expected


def elf_machine(header: bytes) -> int:
    require(
        len(header) == 20 and header[:5] == b"\x7fELF\x02" and header[5] in (1, 2),
        "executable_architecture",
    )
    return int.from_bytes(header[18:20], "little" if header[5] == 1 else "big")


def worker_limits(source: str, *, memory: int, seconds: float, size: int) -> dict[str, object]:
    """Check installed source declarations, without pretending to measure child RSS."""
    require((memory, seconds, size) == (134217728, 2.0, 262144), "decoder_limit_contract")
    expected = ast.parse(
        "import resource\n"
        "resource.setrlimit(resource.RLIMIT_AS, (DECODER_MEMORY_BYTES, DECODER_MEMORY_BYTES))\n"
        "resource.setrlimit(resource.RLIMIT_CPU, (2, 2))\n"
        "resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_PNG_BYTES, MAX_PNG_BYTES))\n"
        "resource.setrlimit(resource.RLIMIT_CORE, (0, 0))\n"
        "resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))\n"
    ).body
    parsed = ast.parse(source).body
    require(len(parsed) == 1 and isinstance(parsed[0], ast.FunctionDef), "decoder_limit_contract")
    worker = parsed[0]
    assert isinstance(worker, ast.FunctionDef)
    require(
        [ast.dump(node) for node in worker.body[:6]] == [ast.dump(node) for node in expected],
        "decoder_limit_contract",
    )
    # All five unconditional limit calls precede Pillow imports and any input read.
    require(
        sum(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "setrlimit"
            for node in ast.walk(worker)
        )
        == 5,
        "decoder_limit_contract",
    )
    return {
        "evidence_basis": "installed_worker_source_checked",
        "address_space_bytes": memory,
        "cpu_seconds": 2,
        "wall_seconds": seconds,
        "output_file_bytes": size,
        "core_bytes": 0,
        "open_files": 32,
    }


PHASES = frozenset(
    (
        "python_ready",
        "worker_entry",
        "limits_start",
        "limits_applied",
        "pillow_import_start",
        "pillow_import_end",
        "decode_start",
        "decode_complete",
        "encode_start",
        "encode_complete",
        "worker_complete",
    )
)

# The installed worker is executed unchanged. Only this separate diagnostic
# process gets a marker descriptor and line tracer; never the qualifying child.
DIAGNOSTIC_CHILD = r"""
import os, resource, sys, time
worker, descriptor, started = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
seen = set()
def mark(phase):
    if phase in seen or len(seen) >= 11:
        return
    seen.add(phase)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    line = "%s %.6f %.6f %.6f\n" % (
        phase, time.monotonic() - started, usage.ru_utime, usage.ru_stime
    )
    os.write(descriptor, line.encode("ascii"))
mark("python_ready")
import runpy
phase_lines = __PHASE_LINES__
def local_trace(frame, event, arg):
    if event == "line" and frame.f_lineno in phase_lines:
        mark(phase_lines[frame.f_lineno])
    return local_trace
def trace(frame, event, arg):
    if (event == "call" and frame.f_code.co_filename == worker
            and frame.f_code.co_name == "_worker_main"):
        mark("worker_entry")
        return local_trace
    return None
sys.settrace(trace)
try:
    runpy.run_path(worker, run_name="__main__")
finally:
    sys.settrace(None)
"""


def child_cpu_usage() -> tuple[float, float]:
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime, usage.ru_stime


def parse_phase_markers(raw: bytes) -> dict[str, object]:
    result: dict[str, object] = {
        "phase_markers": [],
        "last_observed_phase": "not_observed",
        "marker_stream": "empty",
    }
    if len(raw) > 2048 or len(raw.splitlines()) > 12:
        result["marker_stream"] = "bounds_exceeded"
        return result
    phases: list[dict[str, object]] = []
    seen: set[str] = set()
    discarded = False
    for line in raw.splitlines():
        try:
            parts = line.decode("ascii").split()
            if (
                len(parts) != 4
                or parts[0] not in PHASES
                or parts[0] in seen
                or any(re.fullmatch(r"[0-9]{1,4}\.[0-9]{6}", value) is None for value in parts[1:])
            ):
                discarded = True
                continue
            wall, user, system = (float(value) for value in parts[1:])
            if max(wall, user, system) > 3600:
                discarded = True
                continue
            seen.add(parts[0])
            phases.append(
                {
                    "phase": parts[0],
                    "wall_seconds": wall,
                    "user_cpu_seconds": user,
                    "system_cpu_seconds": system,
                }
            )
        except (UnicodeError, ValueError):
            discarded = True
    result["phase_markers"] = phases
    if phases:
        result["last_observed_phase"] = phases[-1]["phase"]
    result["marker_stream"] = (
        "unrecognized_discarded" if discarded else "valid" if phases else "empty"
    )
    return result


def diagnostic_phase_lines(worker: Path) -> dict[int, str]:
    source = worker.read_text()
    function = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == "_worker_main"
    )
    prefixes = {
        "resource.setrlimit(resource.RLIMIT_AS,": "limits_start",
        "try:": "limits_applied",
        "from PIL import Image": "pillow_import_start",
        "Image.MAX_IMAGE_PIXELS =": "pillow_import_end",
        "with Image.open(": "decode_start",
        "mode =": "decode_complete",
        "clean.save(": "encode_start",
        "inspect_canonical_png(result)": "encode_complete",
        "return 0": "worker_complete",
    }
    mapping = {}
    for number, line in enumerate(source.splitlines(), 1):
        if function.lineno < number <= (function.end_lineno or function.lineno):
            for prefix, phase in prefixes.items():
                if line.strip().startswith(prefix):
                    mapping[number] = phase
    require(set(mapping.values()) == set(prefixes.values()), "decoder_limit_contract")
    require(len(mapping) == len(prefixes), "decoder_limit_contract")
    return mapping


def run_diagnostic(worker: Path) -> dict[str, object]:
    """One post-failure supporting observation, never a qualification retry."""
    result: dict[str, object] = {
        "diagnostic_only": True,
        "qualifying_outcome_unchanged": True,
        "interpretation": "instrumented_second_child_not_original_attempt",
        "wall_limit_seconds": 2.0,
        "worker_limits_unchanged": True,
    }
    process: subprocess.Popen[bytes] | None = None
    started = time.monotonic()
    before = child_cpu_usage()
    try:
        code = DIAGNOSTIC_CHILD.replace("__PHASE_LINES__", repr(diagnostic_phase_lines(worker)))
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as markers:
            started = time.monotonic()
            deadline = started + 2.0
            try:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-I",
                        "-c",
                        code,
                        str(worker),
                        str(markers.fileno()),
                        str(started),
                    ],
                    stdin=subprocess.PIPE,
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                    env={"PATH": os.defpath},
                    pass_fds=(markers.fileno(),),
                )
                process.communicate(
                    synthetic_png(), timeout=max(0.001, deadline - time.monotonic())
                )
                result["outcome"] = "completed" if process.returncode == 0 else "child_nonzero_exit"
            except subprocess.TimeoutExpired:
                result["outcome"] = "parent_wall_timeout"
            except Exception:
                result["outcome"] = "diagnostic_unavailable"
            finally:
                if process is not None:
                    try:
                        if process.poll() is None:
                            process.kill()
                    except ProcessLookupError:
                        pass
                    finally:
                        process.wait()
            markers.seek(0)
            result.update(parse_phase_markers(markers.read(2049)))
            result["exit_code"] = process.returncode if process is not None else None
            result["child_reaped"] = process is not None and process.returncode is not None
    except Exception:
        result["outcome"] = "diagnostic_unavailable"
    after = child_cpu_usage()
    result.update(
        elapsed_seconds=round(time.monotonic() - started, 6),
        child_user_cpu_seconds=round(after[0] - before[0], 6),
        child_system_cpu_seconds=round(after[1] - before[1], 6),
    )
    return result


class SpawnWitness:
    """Observe and forward the production spawn unchanged; never replace its child."""

    def __init__(self, factory: Any, executable: str, worker: str) -> None:
        self.factory = factory
        self.executable = executable
        self.worker = worker
        self.processes: list[Any] = []
        self.spawn_seconds = 0.0
        self.wall_timeout = False
        self.launch_failed = False
        self.cpu_before: tuple[float, float] | None = None

    def __call__(self, args: list[str], **kwargs: Any) -> Any:
        require(
            not self.processes
            and args == [self.executable, "-I", self.worker]
            and set(kwargs) == {"stdin", "stdout", "stderr", "close_fds", "env"}
            and kwargs["stdin"] == subprocess.PIPE
            and kwargs["stderr"] == subprocess.DEVNULL
            and kwargs["close_fds"] is True
            and kwargs["env"] == {"PATH": os.defpath},
            "decoder_process_contract",
        )
        require(
            stat.S_ISREG(os.fstat(kwargs["stdout"].fileno()).st_mode), "decoder_process_contract"
        )
        started = time.monotonic()
        self.cpu_before = child_cpu_usage()
        try:
            child = self.factory(args, **kwargs)
        except OSError:
            self.launch_failed = True
            raise
        finally:
            self.spawn_seconds = round(time.monotonic() - started, 6)
        self.processes.append(child)
        original_communicate = child.communicate

        def communicate(*arguments: Any, **options: Any) -> Any:
            try:
                return original_communicate(*arguments, **options)
            except subprocess.TimeoutExpired:
                self.wall_timeout = True
                raise

        child.communicate = communicate
        return child

    def attempt_evidence(self) -> dict[str, object]:
        after = child_cpu_usage()
        before = self.cpu_before or after
        code = self.processes[0].returncode if self.processes else None
        outcome = (
            "parent_wall_timeout"
            if self.wall_timeout
            else "launch_failed"
            if self.launch_failed
            else "child_exit"
            if code is not None
            else "not_observed"
        )
        return {
            "outcome": outcome,
            "children": len(self.processes),
            "spawn_seconds": self.spawn_seconds,
            "exit_code": code,
            "child_reaped": bool(self.processes) and code is not None,
            "child_user_cpu_seconds": round(after[0] - before[0], 6),
            "child_system_cpu_seconds": round(after[1] - before[1], 6),
        }

    def completed(self) -> dict[str, object]:
        require(
            len(self.processes) == 1
            and self.processes[0].pid != os.getpid()
            and self.processes[0].returncode == 0,
            "decoder_process_contract",
        )
        return {
            "children": 1,
            "isolated_python": True,
            "environment_path_only": True,
            "close_fds": True,
            "diagnostics_discarded": True,
            "exit_code": 0,
            "same_executable": True,
        }


def runtime_identity() -> dict[str, object]:
    with Path(sys.executable).open("rb") as executable:
        machine = elf_machine(executable.read(20))
    require(machine == 183, "executable_architecture")
    status = dict(
        line.split(":", 1)
        for line in Path("/proc/self/status").read_text().splitlines()
        if ":" in line
    )
    require(
        sys.platform == "linux"
        and platform.machine() == "aarch64"
        and os.getuid() == os.geteuid() == 10001
        and os.getgid() == os.getegid() == 10001
        and sys.flags.isolated == 1
        and Path(sys.prefix) == Path("/app/.venv")
        and status.get("NoNewPrivs", "").strip() == "1"
        and int(status.get("CapEff", "-1").strip(), 16) == 0,
        "runtime_identity",
    )
    return {
        "machine": "aarch64",
        "executable_elf_machine": machine,
        "uid": 10001,
        "gid": 10001,
        "isolated_python": True,
        "no_new_privileges": True,
        "effective_capabilities": 0,
        "python": ".".join(str(value) for value in sys.version_info[:3]),
    }


def empty_report(execution: str = EMULATED) -> dict[str, object]:
    return {
        "schema_version": 1,
        "execution": execution if execution in (EMULATED, NATIVE) else EMULATED,
        "fixture": "synthetic-2x2-rgba-metadata-png",
        "physical_device_qualified": False,
    }


def native_host_identity(host: tuple[str, ...] | None) -> dict[str, object]:
    require(
        host in (("aarch64", "183", "ARM64", "aarch64"), ("aarch64", "183", "ARM64", "arm64")),
        "native_host_identity",
    )
    assert host is not None
    return {
        "evidence_basis": "workflow_validated_host_inputs",
        "machine": "aarch64",
        "python_elf_machine": 183,
        "runner_arch": "ARM64",
        "docker_arch": host[3],
    }


def run_probe(
    commit: str,
    image_id: str,
    image_platform: str,
    execution: str = EMULATED,
    host: tuple[str, ...] | None = None,
) -> dict[str, object]:
    result = empty_report(execution)
    try:
        require(execution in (EMULATED, NATIVE), "probe_arguments")
        require(execution == NATIVE or host is None, "probe_arguments")
        require(
            re.fullmatch(r"[a-f0-9]{40}", commit) is not None
            and re.fullmatch(r"sha256:[a-f0-9]{64}", image_id) is not None
            and image_platform == "linux/arm64",
            "image_identity",
        )
        result.update(commit=commit, image_id=image_id, image_platform=image_platform)
        if execution == NATIVE:
            result["host"] = native_host_identity(host)
        result["runtime"] = runtime_identity()
        from cycling_workshop.branding import images

        installed = Path(images.__file__).resolve()
        require(installed.is_relative_to(Path(sys.prefix).resolve()), "installed_decoder")
        require(importlib.metadata.version("Pillow") == "12.3.0", "installed_decoder")
        result["pillow_version"] = "12.3.0"
        result["worker_source_sha256"] = hashlib.sha256(installed.read_bytes()).hexdigest()
        result["decoder_limits"] = worker_limits(
            inspect.getsource(images._worker_main),
            memory=images.DECODER_MEMORY_BYTES,
            seconds=images.DECODER_SECONDS,
            size=images.MAX_PNG_BYTES,
        )
        witness = SpawnWitness(subprocess.Popen, sys.executable, str(installed))
        started = time.monotonic()
        unavailable = False
        try:
            # Only observe the launch; forward identical arguments to the real Popen.
            with patch.object(subprocess, "Popen", witness):
                logo = images.canonicalize_logo(base64.b64encode(synthetic_png()).decode("ascii"))
        except images.DecoderUnavailable:
            unavailable = True
        except images.InvalidLogo:
            raise ProbeFailure("decoder_rejected_fixture") from None
        finally:
            elapsed_key = (
                "native_elapsed_seconds" if execution == NATIVE else "emulated_elapsed_seconds"
            )
            result[elapsed_key] = round(time.monotonic() - started, 6)
            result["qualifying_attempt"] = witness.attempt_evidence()
        if unavailable:
            if execution == NATIVE:
                raise ProbeFailure("decoder_unavailable_on_native_arm64")
            try:
                result["diagnostic"] = run_diagnostic(installed)
            except Exception:
                result["diagnostic"] = {
                    "diagnostic_only": True,
                    "outcome": "diagnostic_unavailable",
                }
            raise ProbeFailure("decoder_unavailable_under_emulation")
        result["decoder_process"] = witness.completed()
        require(
            images.inspect_canonical_png(logo.data) == (2, 2)
            and (logo.width, logo.height) == (2, 2)
            and logo.byte_count == len(logo.data)
            and logo.sha256 == hashlib.sha256(logo.data).hexdigest(),
            "canonical_output",
        )
        parsed = images._inspect(logo.data)
        require(parsed.color == 6, "canonical_output")
        verify_fixture_pixels(parsed.compressed)
        result["canonical_output"] = {
            "width": logo.width,
            "height": logo.height,
            "byte_count": logo.byte_count,
            "sha256": logo.sha256,
            "metadata_removed": True,
            "pixels_verified": True,
            "chunks": ["IHDR", "IDAT", "IEND"],
        }
        result["status"] = "passed"
    except ProbeFailure as error:
        result.update(status="failed", failure=error.code)
    except Exception:
        # Never print exception text, image bytes, environment values or tracebacks.
        result.update(status="failed", failure="unexpected_probe_failure")
    return result


def validate_native_report(
    raw: bytes,
    exit_code: int,
    commit: str,
    image_id: str,
    worker_sha256: str,
    host: tuple[str, ...],
) -> str:
    """Host-side closed-schema filter; never forward arbitrary container stdout."""
    require(0 < len(raw) < 4096, "native_report_invalid")

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            require(key not in result, "native_report_invalid")
            result[key] = value
        return result

    try:
        report = json.loads(raw, object_pairs_hook=unique_object)
    except (ValueError, UnicodeError, RecursionError):
        raise ProbeFailure("native_report_invalid") from None

    def number(value: object) -> bool:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        return 0 <= value <= 3600 and math.isfinite(value)

    def digest(value: object) -> bool:
        return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None

    def matches(value: object, expected: Any) -> bool:
        if callable(expected):
            return bool(expected(value))
        if isinstance(expected, dict):
            return (
                isinstance(value, dict)
                and value.keys() == expected.keys()
                and all(matches(value[key], template) for key, template in expected.items())
            )
        return type(value) is type(expected) and value == expected

    base = empty_report(NATIVE) | {
        "commit": commit,
        "image_id": image_id,
        "image_platform": "linux/arm64",
    }
    schema: dict[str, Any] = base | {
        "host": native_host_identity(host),
        "runtime": {
            "machine": "aarch64",
            "executable_elf_machine": 183,
            "uid": 10001,
            "gid": 10001,
            "isolated_python": True,
            "no_new_privileges": True,
            "effective_capabilities": 0,
            "python": lambda value: (
                isinstance(value, str) and re.fullmatch(r"3\.13\.[0-9]{1,3}", value) is not None
            ),
        },
        "pillow_version": "12.3.0",
        "worker_source_sha256": worker_sha256,
        "decoder_limits": {
            "evidence_basis": "installed_worker_source_checked",
            "address_space_bytes": 134217728,
            "cpu_seconds": 2,
            "wall_seconds": 2.0,
            "output_file_bytes": 262144,
            "core_bytes": 0,
            "open_files": 32,
        },
        "native_elapsed_seconds": number,
        "qualifying_attempt": {
            "outcome": lambda value: (
                value in ("parent_wall_timeout", "launch_failed", "child_exit", "not_observed")
            ),
            "children": lambda value: type(value) is int and value in (0, 1),
            "spawn_seconds": number,
            "exit_code": lambda value: (
                value is None or (type(value) is int and -255 <= value <= 255)
            ),
            "child_reaped": lambda value: type(value) is bool,
            "child_user_cpu_seconds": number,
            "child_system_cpu_seconds": number,
        },
        "decoder_process": {
            "children": 1,
            "isolated_python": True,
            "environment_path_only": True,
            "close_fds": True,
            "diagnostics_discarded": True,
            "exit_code": 0,
            "same_executable": True,
        },
        "canonical_output": {
            "width": 2,
            "height": 2,
            "byte_count": lambda value: type(value) is int and 0 < value <= 262144,
            "sha256": digest,
            "metadata_removed": True,
            "pixels_verified": True,
            "chunks": ["IHDR", "IDAT", "IEND"],
        },
        "status": lambda value: value in ("passed", "failed"),
        "failure": lambda value: (
            isinstance(value, str) and value in FAILURES - {"decoder_unavailable_under_emulation"}
        ),
    }
    require(
        re.fullmatch(r"[a-f0-9]{40}", commit) is not None
        and re.fullmatch(r"sha256:[a-f0-9]{64}", image_id) is not None
        and digest(worker_sha256)
        and type(exit_code) is int
        and 0 <= exit_code <= 255
        and isinstance(report, dict)
        and base.keys() <= report.keys() <= schema.keys()
        and all(matches(value, schema[key]) for key, value in report.items()),
        "native_report_invalid",
    )
    passed = report.get("status") == "passed"
    require(
        (passed and exit_code == 0 and report.keys() == schema.keys() - {"failure"})
        or (
            not passed
            and exit_code != 0
            and report.get("status") == "failed"
            and "failure" in report
        ),
        "native_report_invalid",
    )
    if passed:
        require(
            report["qualifying_attempt"]["outcome"] == "child_exit"
            and report["qualifying_attempt"]["children"] == 1
            and report["qualifying_attempt"]["exit_code"] == 0
            and report["qualifying_attempt"]["child_reaped"] is True,
            "native_report_invalid",
        )
    encoded = json.dumps(report, sort_keys=True, allow_nan=False)
    require(len(encoded) < 4096, "native_report_invalid")
    return encoded


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False, exit_on_error=False, allow_abbrev=False)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--image-platform", required=True)
    parser.add_argument("--execution", default=EMULATED)
    parser.add_argument("--host-machine")
    parser.add_argument("--host-elf-machine")
    parser.add_argument("--runner-arch")
    parser.add_argument("--docker-arch")
    parser.add_argument("--validate-native-report")
    parser.add_argument("--probe-exit-code", type=int)
    parser.add_argument("--worker-sha256")
    try:
        args = parser.parse_args()
        host = (args.host_machine, args.host_elf_machine, args.runner_arch, args.docker_arch)
        if args.validate_native_report is not None:
            status = args.probe_exit_code
            status = status if type(status) is int and 0 <= status <= 255 else 1
            try:
                require(
                    args.execution == NATIVE
                    and args.image_platform == "linux/arm64"
                    and type(args.probe_exit_code) is int
                    and 0 <= args.probe_exit_code <= 255,
                    "native_report_invalid",
                )
                with Path(args.validate_native_report).open("rb") as report:
                    encoded = validate_native_report(
                        report.read(4096),
                        status,
                        args.commit,
                        args.image_id,
                        args.worker_sha256,
                        host,
                    )
            except (OSError, ProbeFailure):
                failure = empty_report(NATIVE)
                failure.update(
                    status="failed", failure="native_report_invalid", probe_exit_code=status
                )
                if re.fullmatch(r"[a-f0-9]{40}", args.commit) and re.fullmatch(
                    r"sha256:[a-f0-9]{64}", args.image_id
                ):
                    failure.update(commit=args.commit, image_id=args.image_id)
                encoded = json.dumps(failure, sort_keys=True)
                status = status or 1
            print(encoded)
            return status
        result = run_probe(
            args.commit,
            args.image_id,
            args.image_platform,
            args.execution,
            host if any(value is not None for value in host) else None,
        )
    except argparse.ArgumentError:
        result = empty_report()
        result.update(status="failed", failure="probe_arguments")
    try:
        encoded = json.dumps(result, sort_keys=True, allow_nan=False)
        require(len(encoded) < 4096, "unexpected_probe_failure")
    except (TypeError, ValueError, ProbeFailure):
        result = empty_report()
        result.update(status="failed", failure="unexpected_probe_failure")
        encoded = json.dumps(result, sort_keys=True)
    print(encoded)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
