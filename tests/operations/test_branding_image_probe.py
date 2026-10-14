from __future__ import annotations

import ast
import json
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

    process = SimpleNamespace(pid=321, returncode=0)
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
    workflow = (ROOT / ".github/workflows/local-runtime.yml").read_text()
    arm = workflow.split("  arm64-build:\n", 1)[1]
    for expected in (
        "matrix.image != 'platform.local'",
        "matrix.image == 'platform.local'",
        "outputs: type=cacheonly",
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
        "if: always() && matrix.image == 'platform.local'",
    ):
        assert expected in arm
    assert "--user" not in arm  # Prove the image's configured non-root identity.
    assert "--volume" not in arm
    assert "--mount" not in arm
    assert "continue-on-error" not in arm


def mock_installed_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    from cycling_workshop.branding import images

    monkeypatch.setattr(probe, "runtime_identity", lambda: {"machine": "aarch64", "uid": 10001})
    monkeypatch.setattr(probe.sys, "prefix", str(Path(images.__file__).resolve().parent))
    monkeypatch.setattr(probe.importlib.metadata, "version", lambda name: "12.3.0")


def test_mocked_full_success_records_no_png_and_does_not_change_limits(
    monkeypatch: pytest.MonkeyPatch,
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
    factory = Mock(return_value=SimpleNamespace(pid=321, returncode=0))
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
    result = probe.run_probe(SHA, IMAGE_ID, "linux/arm64")
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
