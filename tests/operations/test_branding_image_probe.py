from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.ci import branding_image_probe as probe

ROOT = Path(__file__).parents[2]
SHA = "a" * 40
IMAGE_ID = "sha256:" + "b" * 64


def test_synthetic_png_has_removable_metadata_and_tiny_pixels() -> None:
    from cycling_workshop.branding.images import _inspect, _validate_scanlines

    data = probe.synthetic_png()
    parsed = _inspect(data)
    _validate_scanlines(parsed)
    assert (parsed.width, parsed.height) == (2, 2)
    assert parsed.chunks == {b"IHDR", b"gAMA", b"sRGB", b"IDAT", b"IEND"}
    assert len(data) < 256


@pytest.mark.parametrize("order,marker", [("little", 1), ("big", 2)])
def test_elf_machine_is_read_from_executable_not_host_uname(order: str, marker: int) -> None:
    header = bytearray(20)
    header[:6] = b"\x7fELF\x02" + bytes([marker])
    header[18:20] = (183).to_bytes(2, order)
    assert probe.elf_machine(bytes(header)) == 183
    header[18:20] = (62).to_bytes(2, order)
    assert probe.elf_machine(bytes(header)) == 62


@pytest.mark.parametrize("header", [b"", b"not an ELF image" * 2, b"\x7fELF\x01\x01" + b"\0" * 14])
def test_bad_executable_header_fails_closed(header: bytes) -> None:
    with pytest.raises(probe.ProbeFailure, match="executable_architecture"):
        probe.elf_machine(header)


def worker_source() -> str:
    source = (ROOT / "services/platform/src/cycling_workshop/branding/images.py").read_text()
    node = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == "_worker_main"
    )
    return ast.unparse(node)


def test_installed_worker_contract_preserves_real_limits_before_pillow_import() -> None:
    limits = probe.worker_limits(
        worker_source(), memory=128 * 1024 * 1024, seconds=2.0, size=262144
    )
    assert limits == {
        "evidence_basis": "installed_worker_source_checked",
        "address_space_bytes": 134217728,
        "cpu_seconds": 2,
        "wall_seconds": 2.0,
        "output_file_bytes": 262144,
        "core_bytes": 0,
        "open_files": 32,
    }


@pytest.mark.parametrize(
    "source,memory,seconds,size",
    [
        (worker_source().replace("(2, 2)", "(20, 20)"), 134217728, 2.0, 262144),
        (
            worker_source().replace("import resource", "import PIL\n    import resource"),
            134217728,
            2.0,
            262144,
        ),
        (worker_source(), 256 * 1024 * 1024, 2.0, 262144),
        (worker_source(), 134217728, 20.0, 262144),
        (worker_source(), 134217728, 2.0, 524288),
    ],
)
def test_relaxed_or_reordered_decoder_limits_are_refused(
    source: str, memory: int, seconds: float, size: int
) -> None:
    with pytest.raises(probe.ProbeFailure, match="decoder_limit_contract"):
        probe.worker_limits(source, memory=memory, seconds=seconds, size=size)


def test_spawn_witness_forwards_unchanged_real_subprocess_arguments(tmp_path: Path) -> None:
    from cycling_workshop.branding import images

    process = SimpleNamespace(pid=321, returncode=0, communicate=Mock())
    real_popen = Mock(return_value=process)
    witness = probe.SpawnWitness(real_popen, "/app/.venv/bin/python", "/installed/images.py")
    with (tmp_path / "output").open("wb") as output:
        kwargs = {
            "stdin": images.subprocess.PIPE,
            "stdout": output,
            "stderr": images.subprocess.DEVNULL,
            "close_fds": True,
            "env": {"PATH": images.os.defpath},
        }
        args = ["/app/.venv/bin/python", "-I", "/installed/images.py"]
        assert witness(args, **kwargs) is process
        real_popen.assert_called_once_with(args, **kwargs)
        assert witness.completed() == {
            "children": 1,
            "isolated_python": True,
            "environment_path_only": True,
            "close_fds": True,
            "diagnostics_discarded": True,
            "exit_code": 0,
            "same_executable": True,
        }


@pytest.mark.parametrize("field,value", [("env", {"SECRET": "never expose"}), ("close_fds", False)])
def test_spawn_witness_refuses_weakened_process_isolation(field: str, value: object) -> None:
    factory = Mock()
    witness = probe.SpawnWitness(factory, "/python", "/images.py")
    kwargs = {"env": {"PATH": probe.os.defpath}, "close_fds": True}
    kwargs[field] = value
    with pytest.raises(probe.ProbeFailure, match="decoder_process_contract"):
        witness(["/python", "-I", "/images.py"], **kwargs)
    factory.assert_not_called()


def test_spawn_witness_requires_one_successful_child() -> None:
    witness = probe.SpawnWitness(Mock(), "/python", "/images.py")
    with pytest.raises(probe.ProbeFailure, match="decoder_process_contract"):
        witness.completed()


def test_failure_json_is_closed_and_never_copies_exception_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail() -> dict[str, object]:
        raise RuntimeError("private image base64 and credentials must never appear")

    monkeypatch.setattr(probe, "runtime_identity", fail)
    result = probe.run_probe(SHA, IMAGE_ID, "linux/arm64")
    assert result == {
        "schema_version": 1,
        "execution": "qemu-emulated-linux-arm64",
        "fixture": "synthetic-2x2-rgba-metadata-png",
        "physical_device_qualified": False,
        "commit": SHA,
        "image_id": IMAGE_ID,
        "image_platform": "linux/arm64",
        "status": "failed",
        "failure": "unexpected_probe_failure",
    }
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize(
    "commit,image_id,image_platform",
    [
        ("raw-secret", IMAGE_ID, "linux/arm64"),
        (SHA, "raw-secret", "linux/arm64"),
        (SHA, IMAGE_ID, "linux/amd64"),
    ],
)
def test_identity_failure_never_echoes_unvalidated_arguments(
    commit: str, image_id: str, image_platform: str
) -> None:
    result = probe.run_probe(commit, image_id, image_platform)
    assert result["status"] == "failed"
    assert result["failure"] == "image_identity"
    assert "raw-secret" not in json.dumps(result)


def test_workflow_loads_only_ephemeral_api_image_and_runs_hardened_arm_probe() -> None:
    workflow = (ROOT / ".github/workflows/branding-arm64-qemu-diagnostic.yml").read_text()
    for expected in (
        "load: true",
        "push: false",
        "docker image inspect",
        "--platform linux/arm64",
        "--network none",
        "--read-only",
        "--cap-drop ALL",
        "--security-opt no-new-privileges:true",
        "--tmpfs /tmp:rw,noexec,nosuid,size=64m",
        "--pull never",
        "--entrypoint python",
        "-I -",
        "scripts/ci/branding_image_probe.py",
        "git rev-parse HEAD",
        "branding-arm64-emulated-${{ github.sha }}",
        "if: always()",
        "--validate-emulated-report",
        "--probe-exit-code",
    ):
        assert expected in workflow
    assert "--user" not in workflow  # Prove the image's configured non-root identity.
    assert "--volume" not in workflow
    assert "--mount" not in workflow
    assert "continue-on-error" not in workflow


def mock_installed_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    from cycling_workshop.branding import images

    monkeypatch.setattr(
        probe,
        "runtime_identity",
        lambda: {
            "machine": "aarch64",
            "executable_elf_machine": 183,
            "uid": 10001,
            "gid": 10001,
            "isolated_python": True,
            "no_new_privileges": True,
            "effective_capabilities": 0,
            "python": "3.13.14",
        },
    )
    monkeypatch.setattr(probe.sys, "prefix", str(Path(images.__file__).resolve().parent))
    monkeypatch.setattr(probe.importlib.metadata, "version", lambda name: "12.3.0")
    monkeypatch.setattr(probe, "run_diagnostic", Mock(return_value={"diagnostic_only": True}))


@pytest.mark.parametrize("native", [False, True])
def test_mocked_full_success_records_no_png_and_does_not_change_limits(
    monkeypatch: pytest.MonkeyPatch,
    native: bool,
) -> None:
    import hashlib
    import struct
    import tempfile

    from cycling_workshop.branding import images

    mock_installed_runtime(monkeypatch)
    fixture = probe.synthetic_png()
    canonical = fixture[:8]
    offset = 8
    while offset < len(fixture):
        length = struct.unpack_from(">I", fixture, offset)[0]
        if fixture[offset + 4 : offset + 8] not in (b"gAMA", b"sRGB"):
            canonical += fixture[offset : offset + 12 + length]
        offset += 12 + length
    factory = Mock(return_value=SimpleNamespace(pid=321, returncode=0, communicate=Mock()))
    monkeypatch.setattr(probe.subprocess, "Popen", factory)

    def mock_canonicalize(encoded: str) -> images.CanonicalLogo:
        assert encoded == probe.base64.b64encode(fixture).decode("ascii")
        with tempfile.TemporaryFile() as output:
            images.subprocess.Popen(
                [probe.sys.executable, "-I", str(Path(images.__file__).resolve())],
                stdin=probe.subprocess.PIPE,
                stdout=output,
                stderr=probe.subprocess.DEVNULL,
                close_fds=True,
                env={"PATH": probe.os.defpath},
            )
        return images.CanonicalLogo(
            canonical, hashlib.sha256(canonical).hexdigest(), len(canonical), 2, 2
        )

    monkeypatch.setattr(images, "canonicalize_logo", mock_canonicalize)
    result = probe.run_probe(SHA, IMAGE_ID, "linux/arm64", *([NATIVE, HOST] if native else []))
    if native:
        worker_sha = hashlib.sha256(Path(images.__file__).read_bytes()).hexdigest()
        assert (
            json.loads(
                probe.validate_native_report(
                    json.dumps(result).encode(), 0, SHA, IMAGE_ID, worker_sha, HOST
                )
            )
            == result
        )
        assert result["execution"] == NATIVE
        assert "native_elapsed_seconds" in result and "diagnostic" not in result
    assert result["status"] == "passed"
    assert result["physical_device_qualified"] is False
    assert result["canonical_output"] == {
        "width": 2,
        "height": 2,
        "byte_count": len(canonical),
        "sha256": hashlib.sha256(canonical).hexdigest(),
        "metadata_removed": True,
        "pixels_verified": True,
        "chunks": ["IHDR", "IDAT", "IEND"],
    }
    assert result["decoder_process"]["children"] == 1
    assert images.DECODER_SECONDS == 2.0
    assert images.DECODER_MEMORY_BYTES == 128 * 1024 * 1024
    assert factory.call_count == 1
    assert len(json.dumps(result)) < 4096
    assert probe.base64.b64encode(fixture).decode("ascii") not in json.dumps(result)


def test_emulation_refusal_fails_without_retry_or_native_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cycling_workshop.branding import images

    mock_installed_runtime(monkeypatch)
    decoder = Mock(side_effect=images.DecoderUnavailable("never emit this raw diagnostic"))
    monkeypatch.setattr(images, "canonicalize_logo", decoder)
    result = probe.run_probe(SHA, IMAGE_ID, "linux/arm64")
    assert result["status"] == "failed"
    assert result["failure"] == "decoder_unavailable_under_emulation"
    assert "canonical_output" not in result
    assert "raw diagnostic" not in json.dumps(result)
    decoder.assert_called_once()


def test_invalid_cli_arguments_emit_only_safe_failure_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(probe.sys, "argv", ["probe", "--unknown", "raw-secret"])
    assert probe.main() == 1
    output = capsys.readouterr()
    assert output.err == ""
    assert "raw-secret" not in output.out
    assert json.loads(output.out)["failure"] == "probe_arguments"


@pytest.mark.parametrize(
    "raw", [(b"\0" + b"\0\0\0\xff" * 2) * 2, b"\0" * 1000], ids=["wrong-pixels", "oversized"]
)
def test_valid_png_with_wrong_or_unbounded_pixels_is_refused(raw: bytes) -> None:
    with pytest.raises(probe.ProbeFailure, match="canonical_output"):
        probe.verify_fixture_pixels(probe.zlib.compress(raw))


@pytest.mark.parametrize("filter_kind", range(5))
def test_all_png_filters_preserve_the_exact_synthetic_pixels(filter_kind: int) -> None:
    # Independently derived filter bytes for two identical 2-pixel RGBA rows.
    color = b"\x34\x78\xab\xff"
    first = {
        0: color * 2,
        1: color + b"\0" * 4,
        2: color * 2,
        3: color + bytes(value - value // 2 for value in color),
        4: color + b"\0" * 4,
    }[filter_kind]
    second = {
        0: color * 2,
        1: color + b"\0" * 4,
        2: b"\0" * 8,
        3: bytes(value - value // 2 for value in color) + b"\0" * 4,
        4: b"\0" * 8,
    }[filter_kind]
    probe.verify_fixture_pixels(
        probe.zlib.compress(bytes([filter_kind]) + first + bytes([filter_kind]) + second)
    )


def test_runtime_identity_rejects_native_x86_even_if_uname_claims_arm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "python"
    header = bytearray(20)
    header[:6] = b"\x7fELF\x02\x01"
    header[18:20] = (62).to_bytes(2, "little")
    executable.write_bytes(header)
    monkeypatch.setattr(probe.sys, "executable", str(executable))
    monkeypatch.setattr(probe.platform, "machine", lambda: "aarch64")
    with pytest.raises(probe.ProbeFailure, match="executable_architecture"):
        probe.runtime_identity()


def test_probe_refuses_host_source_instead_of_installed_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(probe, "runtime_identity", lambda: {"machine": "aarch64"})
    monkeypatch.setattr(probe.sys, "prefix", "/app/.venv")
    result = probe.run_probe(SHA, IMAGE_ID, "linux/arm64")
    assert result["status"] == "failed"
    assert result["failure"] == "installed_decoder"
    assert "canonical_output" not in result


def test_oversized_report_never_leaves_main(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        probe.sys,
        "argv",
        ["probe", "--commit", SHA, "--image-id", IMAGE_ID, "--image-platform", "linux/arm64"],
    )
    monkeypatch.setattr(probe, "run_probe", lambda *args: {"status": "passed", "bad": "x" * 4096})
    assert probe.main() == 1
    output = capsys.readouterr()
    assert output.err == ""
    assert len(output.out) < 4096
    assert json.loads(output.out)["failure"] == "unexpected_probe_failure"


def test_qualifying_witness_records_timeout_exit_and_cpu_without_changing_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = SimpleNamespace(
        pid=321,
        returncode=-9,
        communicate=Mock(side_effect=probe.subprocess.TimeoutExpired("private", 2)),
    )
    original_communicate = process.communicate
    factory = Mock(return_value=process)
    monkeypatch.setattr(probe, "child_cpu_usage", Mock(side_effect=[(1.0, 2.0), (1.4, 2.2)]))
    witness = probe.SpawnWitness(factory, "/python", "/images.py")
    with (tmp_path / "output").open("wb") as output:
        kwargs = {
            "stdin": probe.subprocess.PIPE,
            "stdout": output,
            "stderr": probe.subprocess.DEVNULL,
            "close_fds": True,
            "env": {"PATH": probe.os.defpath},
        }
        child = witness(["/python", "-I", "/images.py"], **kwargs)
        with pytest.raises(probe.subprocess.TimeoutExpired):
            child.communicate(b"synthetic-input", timeout=1.9)
    original_communicate.assert_called_once_with(b"synthetic-input", timeout=1.9)
    factory.assert_called_once_with(["/python", "-I", "/images.py"], **kwargs)
    evidence = witness.attempt_evidence()
    assert evidence["outcome"] == "parent_wall_timeout"
    assert evidence["exit_code"] == -9
    assert evidence["child_reaped"] is True
    assert evidence["child_user_cpu_seconds"] == 0.4
    assert evidence["child_system_cpu_seconds"] == 0.2
    assert "private" not in json.dumps(evidence)
    assert "synthetic-input" not in json.dumps(evidence)


def test_phase_parser_accepts_only_fixed_bounded_numeric_markers() -> None:
    parsed = probe.parse_phase_markers(
        b"python_ready 0.100000 0.050000 0.010000\n"
        b"worker_entry 0.300000 0.200000 0.030000\n"
        b"limits_applied 0.310000 0.210000 0.030000\n"
    )
    assert parsed["last_observed_phase"] == "limits_applied"
    assert parsed["marker_stream"] == "valid"
    assert parsed["phase_markers"][0] == {
        "phase": "python_ready",
        "wall_seconds": 0.1,
        "user_cpu_seconds": 0.05,
        "system_cpu_seconds": 0.01,
    }


@pytest.mark.parametrize(
    "bad",
    [
        b"Traceback secret data\n",
        b"\x89PNG\x00\xff\n",
        b"pillow_import_start nan inf -1\n",
        b"private 0.100000 0.100000 0.100000\n",
    ],
)
def test_phase_parser_discards_unknown_lines_without_leaking_them(bad: bytes) -> None:
    parsed = probe.parse_phase_markers(bad + b"python_ready 0.100000 0.050000 0.010000\n")
    assert parsed["last_observed_phase"] == "python_ready"
    assert parsed["marker_stream"] == "unrecognized_discarded"
    assert "secret" not in json.dumps(parsed)
    assert "private" not in json.dumps(parsed)
    assert len(parsed["phase_markers"]) == 1


@pytest.mark.parametrize("raw", [b"x" * 2049, b"python_ready 0.100000 0.050000 0.010000\n" * 13])
def test_phase_parser_discards_oversized_or_excessive_marker_streams(raw: bytes) -> None:
    parsed = probe.parse_phase_markers(raw)
    assert parsed["phase_markers"] == []
    assert parsed["last_observed_phase"] == "not_observed"
    assert parsed["marker_stream"] == "bounds_exceeded"


def test_no_marker_does_not_claim_cold_start_causation() -> None:
    parsed = probe.parse_phase_markers(b"")
    assert parsed["last_observed_phase"] == "not_observed"
    assert parsed["marker_stream"] == "empty"
    assert "cold" not in json.dumps(parsed)


def test_successful_diagnostic_cannot_replace_failed_qualifying_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cycling_workshop.branding import images

    mock_installed_runtime(monkeypatch)
    decoder = Mock(side_effect=images.DecoderUnavailable("never emit this private diagnostic"))
    diagnostic = Mock(return_value={"diagnostic_only": True, "outcome": "completed"})
    monkeypatch.setattr(images, "canonicalize_logo", decoder)
    monkeypatch.setattr(probe, "run_diagnostic", diagnostic)
    result = probe.run_probe(SHA, IMAGE_ID, "linux/arm64")
    assert result["status"] == "failed"
    assert result["failure"] == "decoder_unavailable_under_emulation"
    assert result["diagnostic"]["outcome"] == "completed"
    assert "canonical_output" not in result
    assert "private" not in json.dumps(result)
    decoder.assert_called_once()
    diagnostic.assert_called_once()


def test_diagnostic_source_executes_installed_worker_without_replacing_its_limits() -> None:
    source = probe.DIAGNOSTIC_CHILD
    compile(source, "diagnostic", "exec")
    assert 'runpy.run_path(worker, run_name="__main__")' in source
    assert "setrlimit(" not in source
    assert "sys.settrace(trace)" in source
    assert "except Exception as" not in source
    assert "print(" not in source


def test_diagnostic_exception_does_not_replace_original_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cycling_workshop.branding import images

    mock_installed_runtime(monkeypatch)
    monkeypatch.setattr(images, "canonicalize_logo", Mock(side_effect=images.DecoderUnavailable()))
    monkeypatch.setattr(probe, "run_diagnostic", Mock(side_effect=RuntimeError("private")))
    result = probe.run_probe(SHA, IMAGE_ID, "linux/arm64")
    assert result["status"] == "failed"
    assert result["failure"] == "decoder_unavailable_under_emulation"
    assert result["diagnostic"]["outcome"] == "diagnostic_unavailable"
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize("outcome", ["success", "timeout", "unexpected", "kill_race"])
def test_single_diagnostic_child_is_bounded_reaped_and_does_not_expose_output(
    outcome: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = ROOT / "services/platform/src/cycling_workshop/branding/images.py"
    process = Mock()
    process.returncode = None
    process.poll.side_effect = lambda: process.returncode
    captured: dict[str, object] = {}

    def launch(args: list[str], **kwargs: object) -> object:
        captured.update(args=args, **kwargs)
        probe.os.write(kwargs["pass_fds"][0], b"python_ready 0.100000 0.050000 0.010000\nprivate\n")
        kwargs["stdout"].write(b"secret image bytes")
        return process

    def communicate(data: bytes, timeout: float) -> None:
        assert data == probe.synthetic_png()
        assert 0 < timeout <= 2.0
        if outcome in ("timeout", "kill_race"):
            raise probe.subprocess.TimeoutExpired("private", timeout)
        if outcome == "unexpected":
            raise RuntimeError("private")
        process.returncode = 0

    def kill() -> None:
        if outcome == "kill_race":
            raise ProcessLookupError("private")
        process.returncode = -9

    def wait() -> int:
        if outcome == "kill_race":
            process.returncode = -9
        return process.returncode

    process.communicate.side_effect = communicate
    process.kill.side_effect = kill
    process.wait.side_effect = wait
    factory = Mock(side_effect=launch)
    monkeypatch.setattr(probe.subprocess, "Popen", factory)
    result = probe.run_diagnostic(worker)
    assert factory.call_count == 1
    assert captured["env"] == {"PATH": probe.os.defpath}
    assert captured["close_fds"] is True
    assert captured["stderr"] == probe.subprocess.DEVNULL
    assert len(captured["pass_fds"]) == 1
    assert captured["args"][:3] == [probe.sys.executable, "-I", "-c"]
    assert captured["args"][4] == str(worker)
    assert result["diagnostic_only"] is True
    assert result["qualifying_outcome_unchanged"] is True
    assert result["child_reaped"] is True
    assert result["last_observed_phase"] == "python_ready"
    assert "private" not in json.dumps(result)
    assert "secret image" not in json.dumps(result)
    process.wait.assert_called_once()
    assert process.kill.call_count == int(outcome != "success")


def test_diagnostic_phase_mapping_covers_installed_worker_without_editing_it() -> None:
    worker = ROOT / "services/platform/src/cycling_workshop/branding/images.py"
    original = worker.read_bytes()
    lines = probe.diagnostic_phase_lines(worker)
    assert set(lines.values()) == probe.PHASES - {"python_ready", "worker_entry"}
    assert len(lines) == 9
    assert worker.read_bytes() == original


def test_full_failed_report_with_all_markers_retains_original_failure_under_4k(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from cycling_workshop.branding import images

    mock_installed_runtime(monkeypatch)
    monkeypatch.setattr(
        probe,
        "runtime_identity",
        lambda: {
            "machine": "aarch64",
            "executable_elf_machine": 183,
            "uid": 10001,
            "gid": 10001,
            "isolated_python": True,
            "no_new_privileges": True,
            "effective_capabilities": 0,
            "python": "3.13.14",
        },
    )
    maximum = 3599.999999
    qualifying = {
        "outcome": "parent_wall_timeout",
        "children": 1,
        "spawn_seconds": maximum,
        "exit_code": -9,
        "child_reaped": True,
        "child_user_cpu_seconds": maximum,
        "child_system_cpu_seconds": maximum,
    }
    diagnostic = {
        "diagnostic_only": True,
        "qualifying_outcome_unchanged": True,
        "interpretation": "instrumented_second_child_not_original_attempt",
        "wall_limit_seconds": 2.0,
        "worker_limits_unchanged": True,
        "outcome": "parent_wall_timeout",
        "exit_code": -9,
        "child_reaped": True,
        "elapsed_seconds": maximum,
        "child_user_cpu_seconds": maximum,
        "child_system_cpu_seconds": maximum,
        **probe.parse_phase_markers(
            "".join(
                f"{phase} {maximum:.6f} {maximum:.6f} {maximum:.6f}\n"
                for phase in sorted(probe.PHASES)
            ).encode("ascii")
        ),
    }
    monkeypatch.setattr(probe.SpawnWitness, "attempt_evidence", lambda self: qualifying)
    monkeypatch.setattr(images, "canonicalize_logo", Mock(side_effect=images.DecoderUnavailable()))
    monkeypatch.setattr(probe, "run_diagnostic", Mock(return_value=diagnostic))
    monkeypatch.setattr(
        probe.sys,
        "argv",
        [
            "probe",
            "--commit",
            SHA,
            "--image-id",
            IMAGE_ID,
            "--image-platform",
            "linux/arm64",
        ],
    )
    assert probe.main() == 1
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert output.err == ""
    assert len(output.out) < 4096
    assert result["failure"] == "decoder_unavailable_under_emulation"
    assert result["commit"] == SHA and result["image_id"] == IMAGE_ID
    assert result["qualifying_attempt"] == qualifying
    assert len(result["diagnostic"]["phase_markers"]) == 11


def test_child_signal_without_communicate_timeout_is_not_labelled_wall_timeout(
    tmp_path: Path,
) -> None:
    process = SimpleNamespace(pid=321, returncode=-9, communicate=Mock())
    witness = probe.SpawnWitness(Mock(return_value=process), "/python", "/images.py")
    with (tmp_path / "output").open("wb") as output:
        child = witness(
            ["/python", "-I", "/images.py"],
            stdin=probe.subprocess.PIPE,
            stdout=output,
            stderr=probe.subprocess.DEVNULL,
            close_fds=True,
            env={"PATH": probe.os.defpath},
        )
        child.communicate(b"synthetic-input", timeout=1.9)
    assert witness.attempt_evidence()["outcome"] == "child_exit"
    assert witness.attempt_evidence()["exit_code"] == -9


NATIVE = "native-linux-arm64"
HOST = ("aarch64", "183", "ARM64", "aarch64")


def native_failure_report() -> dict[str, object]:
    return {
        "schema_version": 1,
        "execution": NATIVE,
        "fixture": "synthetic-2x2-rgba-metadata-png",
        "physical_device_qualified": False,
        "commit": SHA,
        "image_id": IMAGE_ID,
        "image_platform": "linux/arm64",
        "host": {
            "evidence_basis": "workflow_validated_host_inputs",
            "machine": "aarch64",
            "python_elf_machine": 183,
            "runner_arch": "ARM64",
            "docker_arch": "aarch64",
        },
        "status": "failed",
        "failure": "decoder_unavailable_on_native_arm64",
    }


@pytest.mark.parametrize("field", range(4))
def test_native_mode_requires_each_host_fact_without_echoing_bad_input(field: int) -> None:
    host = list(HOST)
    host[field] = "private-host-data"
    result = probe.run_probe(SHA, IMAGE_ID, "linux/arm64", NATIVE, tuple(host))
    assert result["execution"] == NATIVE
    assert result["status"] == "failed"
    assert result["failure"] == "native_host_identity"
    assert "private-host-data" not in json.dumps(result)
    assert "runtime" not in result


def test_native_mode_never_infers_host_identity_from_guest_uname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Mock(return_value={"machine": "aarch64"})
    monkeypatch.setattr(probe, "runtime_identity", runtime)
    result = probe.run_probe(SHA, IMAGE_ID, "linux/arm64", NATIVE)
    assert result["failure"] == "native_host_identity"
    runtime.assert_not_called()


def test_native_refusal_retains_failure_without_second_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cycling_workshop.branding import images

    mock_installed_runtime(monkeypatch)
    decoder = Mock(side_effect=images.DecoderUnavailable("private-image-diagnostic"))
    monkeypatch.setattr(images, "canonicalize_logo", decoder)
    diagnostic = Mock()
    monkeypatch.setattr(probe, "run_diagnostic", diagnostic)
    result = probe.run_probe(SHA, IMAGE_ID, "linux/arm64", NATIVE, HOST)
    assert result["status"] == "failed"
    assert result["failure"] == "decoder_unavailable_on_native_arm64"
    assert result["host"] == native_failure_report()["host"]
    assert "native_elapsed_seconds" in result and "emulated_elapsed_seconds" not in result
    assert "diagnostic" not in result and "private-image" not in json.dumps(result)
    assert result["physical_device_qualified"] is False
    assert len(json.dumps(result)) < 4096
    decoder.assert_called_once()
    diagnostic.assert_not_called()


def test_native_report_validator_accepts_closed_failed_report() -> None:
    report = native_failure_report()
    assert (
        json.loads(
            probe.validate_native_report(
                json.dumps(report).encode(), 1, SHA, IMAGE_ID, "c" * 64, HOST
            )
        )
        == report
    )


@pytest.mark.parametrize(
    "alteration",
    [
        {"raw": "private-image-data"},
        {"execution": "qemu-emulated-linux-arm64"},
        {"commit": "c" * 40},
        {"image_id": "sha256:" + "c" * 64},
        {"failure": "private exception"},
        {"diagnostic": {"raw": "private"}},
        {"native_elapsed_seconds": float("inf")},
        {"physical_device_qualified": True},
        {"status": "passed"},
        {"runtime": {"python": "private"}},
        {"worker_source_sha256": "d" * 64},
        {"native_elapsed_seconds": True},
        {"native_elapsed_seconds": 10**1000},
        {"host": {"machine": "aarch64"}},
    ],
)
def test_native_report_validator_rejects_unclosed_or_false_evidence(
    alteration: dict[str, object],
) -> None:
    report = native_failure_report() | alteration
    with pytest.raises(probe.ProbeFailure, match="native_report_invalid"):
        probe.validate_native_report(json.dumps(report).encode(), 1, SHA, IMAGE_ID, "c" * 64, HOST)


@pytest.mark.parametrize(
    "raw", [b"", b"private raw logs", b"{}" + b" " * 4096, b"[]", b"[" * 2000 + b"]" * 2000]
)
def test_native_report_validator_bounds_and_rejects_nonreports(raw: bytes) -> None:
    with pytest.raises(probe.ProbeFailure, match="native_report_invalid"):
        probe.validate_native_report(raw, 1, SHA, IMAGE_ID, "c" * 64, HOST)


def test_native_validation_cli_discards_raw_output_and_preserves_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "report.json"
    report.write_text("private Docker/image/exception output")
    monkeypatch.setattr(
        probe.sys,
        "argv",
        [
            "probe",
            "--commit",
            SHA,
            "--image-id",
            IMAGE_ID,
            "--image-platform",
            "linux/arm64",
            "--execution",
            NATIVE,
            "--validate-native-report",
            str(report),
            "--probe-exit-code",
            "125",
            "--worker-sha256",
            "c" * 64,
            "--host-machine",
            HOST[0],
            "--host-elf-machine",
            HOST[1],
            "--runner-arch",
            HOST[2],
            "--docker-arch",
            HOST[3],
        ],
    )
    assert probe.main() == 125
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert captured.err == "" and "private" not in captured.out
    assert result["execution"] == NATIVE
    assert result["failure"] == "native_report_invalid"
    assert result["commit"] == SHA and result["image_id"] == IMAGE_ID
    assert result["probe_exit_code"] == 125


def test_native_workflow_is_separate_hardened_and_logs_only() -> None:
    workflow = (ROOT / ".github/workflows/local-runtime.yml").read_text()
    native = workflow.split("  arm64-native-decoder:\n", 1)[1].split("  arm64-build:\n", 1)[0]
    for expected in (
        "runs-on: ubuntu-24.04-arm",
        "timeout-minutes:",
        "docker build ",
        "infra/docker/platform.local.Dockerfile",
        "uname -m",
        "RUNNER_ARCH",
        "python3 -I",
        "elf_machine",
        "docker info",
        "docker image inspect",
        "--execution native-linux-arm64",
        "--host-machine",
        "--host-elf-machine",
        "--runner-arch",
        "--docker-arch",
        "--validate-native-report",
        "--probe-exit-code",
        "--platform linux/arm64",
        "--network none",
        "--read-only",
        "--cap-drop ALL",
        "--security-opt no-new-privileges:true",
        "--tmpfs /tmp:rw,noexec,nosuid,size=64m",
        "--pull never",
        "--entrypoint python",
        "-I -",
        "GITHUB_STEP_SUMMARY",
        "git rev-parse HEAD",
        "2>/dev/null",
    ):
        assert expected in native
    for forbidden in (
        "setup-qemu",
        "build-push-action",
        "upload-artifact",
        "cache-to",
        "cache-from",
        "continue-on-error",
        "--push",
        "--user",
        "--volume",
        "--mount",
        "permissions:",
    ):
        assert forbidden not in native


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"private": True},
        {"private": None},
        {"private": 0},
        {"private": "false"},
        {"private": ""},
        {"private": []},
        {"private": {}},
    ],
)
def test_native_public_only_guard_rejects_missing_or_nonboolean_metadata(
    metadata: dict[str, object],
) -> None:
    workflow = (ROOT / ".github/workflows/local-runtime.yml").read_text()
    native = workflow.split("  arm64-native-decoder:\n", 1)[1].split("  arm64-build:\n", 1)[0]
    configuration = [line.strip() for line in native.split("    steps:\n", 1)[0].splitlines()]
    assert configuration == [
        "if: github.event.repository.private == false && "
        "toJSON(github.event.repository.private) == 'false'",
        "runs-on: ubuntu-24.04-arm",
        "timeout-minutes: 20",
    ]
    # toJSON preserves JSON types: only the actual boolean false serializes to false.
    assert json.dumps(metadata.get("private")) != "false"
    assert json.dumps(False) == "false"


@pytest.mark.parametrize("nested", [False, True])
def test_native_report_validator_rejects_duplicate_json_keys(nested: bool) -> None:
    raw = json.dumps(native_failure_report())
    if nested:
        raw = raw.replace('"machine": "aarch64"', '"machine": "private", "machine": "aarch64"')
    else:
        raw = raw.replace('"status": "failed"', '"status": "passed", "status": "failed"')
    with pytest.raises(probe.ProbeFailure, match="native_report_invalid"):
        probe.validate_native_report(raw.encode(), 1, SHA, IMAGE_ID, "c" * 64, HOST)


@pytest.mark.parametrize("exit_code", [0, -1, 256, True, None])
def test_native_failed_report_requires_actual_nonzero_process_exit(exit_code: object) -> None:
    with pytest.raises(probe.ProbeFailure, match="native_report_invalid"):
        probe.validate_native_report(
            json.dumps(native_failure_report()).encode(),
            exit_code,  # type: ignore[arg-type]
            SHA,
            IMAGE_ID,
            "c" * 64,
            HOST,
        )


def native_validation_arguments(report: Path) -> list[str]:
    return [
        "probe",
        "--commit",
        SHA,
        "--image-id",
        IMAGE_ID,
        "--image-platform",
        "linux/arm64",
        "--execution",
        NATIVE,
        "--validate-native-report",
        str(report),
        "--worker-sha256",
        "c" * 64,
        "--host-machine",
        HOST[0],
        "--host-elf-machine",
        HOST[1],
        "--runner-arch",
        HOST[2],
        "--docker-arch",
        HOST[3],
    ]


@pytest.mark.parametrize("exit_code", [None, "-1", "256"])
def test_native_validation_cli_rejects_missing_or_invalid_status(
    exit_code: str | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = tmp_path / "report.json"
    report.write_text(json.dumps(native_failure_report()))
    argv = native_validation_arguments(report)
    if exit_code is not None:
        argv += ["--probe-exit-code", exit_code]
    monkeypatch.setattr(probe.sys, "argv", argv)
    assert probe.main() == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out)["failure"] == "native_report_invalid"


def test_native_cleanup_has_a_hard_kill_deadline() -> None:
    workflow = (ROOT / ".github/workflows/local-runtime.yml").read_text()
    native = workflow.split("  arm64-native-decoder:\n", 1)[1].split("  arm64-build:\n", 1)[0]
    assert 'timeout --signal=TERM --kill-after=5s 10s docker rm --force "$container"' in native


@pytest.mark.parametrize(
    "scenario,expected_code,expected_failure,ran_container",
    [
        ("failure", 1, "decoder_unavailable_on_native_arm64", True),
        ("raw", 125, "native_report_invalid", True),
        ("empty", 124, "native_report_invalid", True),
        ("false_success", 1, "native_report_invalid", True),
        ("host", 1, "native_host_identity", False),
        ("elf", 1, "native_host_identity", False),
        ("runner", 1, "native_host_identity", False),
        ("daemon", 1, "native_host_identity", False),
        ("build", 124, "native_image_build_failed", False),
        ("inspect", 1, "native_image_identity", False),
    ],
)
def test_native_workflow_shell_fails_safely_and_cleans_only_its_container(
    scenario: str,
    expected_code: int,
    expected_failure: str,
    ran_container: bool,
    tmp_path: Path,
) -> None:
    """Execute shell plumbing with synthetic commands, never Docker or ARM evidence."""
    commands = tmp_path / "commands"
    commands.mkdir()
    report = tmp_path / "synthetic-report.json"
    report.write_text(json.dumps(native_failure_report()))
    trace = tmp_path / "commands.jsonl"
    summary = tmp_path / "summary.jsonl"
    fake = (
        "#!"
        + sys.executable
        + "\n"
        + textwrap.dedent(
            r"""
        import json, os, pathlib, sys
        name, args = pathlib.Path(sys.argv[0]).name, sys.argv[1:]
        scenario = os.environ["SCENARIO"]
        with open(os.environ["COMMAND_TRACE"], "a") as trace:
            trace.write(json.dumps([name, *args]) + "\n")
        if name == "uname":
            print("x86_64" if scenario == "host" else "aarch64")
        elif name == "git":
            if args[0] == "rev-parse":
                print("a" * 40)
            else:
                worker = pathlib.Path("services/platform/src/cycling_workshop/branding/images.py")
                print(worker.read_text(), end="")
        elif name == "python3":
            if "-c" in args:
                print(62 if scenario == "elf" else 183)
            else:
                os.execv(sys.executable, [sys.executable, *args])
        elif args[0] == "info":
            print("x86_64" if scenario == "daemon" else "aarch64")
        elif args[0] == "build":
            print("private-build-output")
            print("private-build-diagnostic", file=sys.stderr)
            sys.exit(124 if scenario == "build" else 0)
        elif args[0] == "image":
            if scenario == "inspect":
                print("private-inspect-diagnostic", file=sys.stderr)
                sys.exit(1)
            print("sha256:" + "b" * 64 if args[3] == "{{.Id}}" else "linux/arm64")
        elif args[0] == "run":
            print("private-container-diagnostic", file=sys.stderr)
            if scenario == "raw":
                print("private-image-data")
                sys.exit(125)
            if scenario == "empty":
                sys.exit(124)
            print(pathlib.Path(os.environ["SYNTHETIC_REPORT"]).read_text())
            sys.exit(0 if scenario == "false_success" else 1)
        elif args[0] == "rm":
            print("private-cleanup-output")
            print("private-cleanup-diagnostic", file=sys.stderr)
        else:
            sys.exit(99)
        """
        )
    )
    for name in ("uname", "git", "python3", "docker"):
        path = commands / name
        path.write_text(fake)
        path.chmod(0o700)
    workflow = (ROOT / ".github/workflows/local-runtime.yml").read_text()
    native = workflow.split("  arm64-native-decoder:\n", 1)[1].split("  arm64-build:\n", 1)[0]
    shell = textwrap.dedent(native.split("        run: |\n", 1)[1])
    environment = os.environ | {
        "PATH": str(commands) + os.pathsep + os.defpath,
        "SCENARIO": scenario,
        "COMMAND_TRACE": str(trace),
        "SYNTHETIC_REPORT": str(report),
        "RUNNER_TEMP": str(tmp_path),
        "RUNNER_ARCH": "X64" if scenario == "runner" else "ARM64",
        "GITHUB_STEP_SUMMARY": str(summary),
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "1",
    }
    result = subprocess.run(
        ["bash", "-c", shell],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == expected_code
    assert result.stderr == "" and "private-" not in result.stdout
    assert result.stdout == summary.read_text()
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "failed"
    assert evidence["failure"] == expected_failure
    assert evidence["execution"] == NATIVE
    assert evidence["physical_device_qualified"] is False
    assert len(result.stdout.encode()) < 4096
    calls = [json.loads(line) for line in trace.read_text().splitlines()]
    runs = [call for call in calls if call[:2] == ["docker", "run"]]
    cleanup = [call for call in calls if call[:2] == ["docker", "rm"]]
    assert len(runs) == int(ran_container)
    if ran_container:
        assert IMAGE_ID in runs[0]
        assert "ocwp-branding-native-arm64:" + SHA not in runs[0]
    assert cleanup == (
        [["docker", "rm", "--force", "ocwp-branding-native-123-1"]] if ran_container else []
    )
    assert not list(tmp_path.glob("branding-native.*"))
    if scenario in ("host", "elf", "runner", "daemon"):
        assert not any(call[:2] == ["docker", "build"] for call in calls)


def test_native_workflow_runs_immutable_image_and_binds_worker_to_commit() -> None:
    workflow = (ROOT / ".github/workflows/local-runtime.yml").read_text()
    native = workflow.split("  arm64-native-decoder:\n", 1)[1].split("  arm64-build:\n", 1)[0]
    assert '--init --entrypoint python -i "$image_id" -I -' in native
    assert 'git show "$commit:services/platform/src/cycling_workshop/branding/images.py"' in native
