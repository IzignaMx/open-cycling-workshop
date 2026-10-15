from __future__ import annotations

import hashlib
import itertools
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from scripts.ci import branding_image_probe as probe

ROOT = Path(__file__).parents[2]
SHA = "a" * 40
IMAGE = "sha256:" + "b" * 64
WORKER = "c" * 64
HOST = ("aarch64", "183", "ARM64", "aarch64")
QEMU_WORKFLOW = ROOT / ".github/workflows/branding-arm64-qemu-diagnostic.yml"


def passing_report(native: bool = True) -> dict[str, Any]:
    report = probe.empty_report(probe.NATIVE if native else probe.EMULATED) | {
        "commit": SHA,
        "image_id": IMAGE,
        "image_platform": "linux/arm64",
        "runtime": {
            "machine": "aarch64",
            "executable_elf_machine": 183,
            "uid": 10001,
            "gid": 10001,
            "isolated_python": True,
            "no_new_privileges": True,
            "effective_capabilities": 0,
            "python": "3.13.14",
        },
        "pillow_version": "12.3.0",
        "worker_source_sha256": WORKER,
        "decoder_limits": {
            "evidence_basis": "installed_worker_source_checked",
            "address_space_bytes": 134217728,
            "cpu_seconds": 2,
            "wall_seconds": 2.0,
            "output_file_bytes": 262144,
            "core_bytes": 0,
            "open_files": 32,
        },
        "qualifying_attempt": {
            "outcome": "child_exit",
            "children": 1,
            "spawn_seconds": 0.00049,
            "exit_code": 0,
            "child_reaped": True,
            "child_user_cpu_seconds": 0.2594,
            "child_system_cpu_seconds": 0.015023,
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
            "byte_count": 77,
            "sha256": "d" * 64,
            "metadata_removed": True,
            "pixels_verified": True,
            "chunks": ["IHDR", "IDAT", "IEND"],
        },
        "status": "passed",
    }
    report["native_elapsed_seconds" if native else "emulated_elapsed_seconds"] = 0.314891
    if native:
        report["host"] = probe.native_host_identity(HOST)
    return report


def failed_qemu_report() -> dict[str, Any]:
    report = passing_report(False)
    del report["decoder_process"], report["canonical_output"]
    report.update(
        status="failed",
        failure="decoder_unavailable_under_emulation",
        emulated_elapsed_seconds=2.011278,
    )
    report["qualifying_attempt"].update(
        outcome="parent_wall_timeout",
        exit_code=-9,
        child_user_cpu_seconds=1.971744,
        child_system_cpu_seconds=0.023008,
        spawn_seconds=0.007665,
    )
    report["diagnostic"] = {
        "diagnostic_only": True,
        "qualifying_outcome_unchanged": True,
        "interpretation": "instrumented_second_child_not_original_attempt",
        "wall_limit_seconds": 2.0,
        "worker_limits_unchanged": True,
        "outcome": "parent_wall_timeout",
        "elapsed_seconds": 2.004784,
        "child_user_cpu_seconds": 1.969223,
        "child_system_cpu_seconds": 0.028989,
        "exit_code": -9,
        "child_reaped": True,
        "marker_stream": "valid",
        "last_observed_phase": "pillow_import_start",
        "phase_markers": [
            {
                "phase": "pillow_import_start",
                "wall_seconds": 1.57852,
                "user_cpu_seconds": 1.548754,
                "system_cpu_seconds": 0.025995,
            }
        ],
    }
    return report


@pytest.mark.parametrize(
    "field,value",
    [
        ("native_elapsed_seconds", 3600),
        ("native_elapsed_seconds", 0),
        ("native_elapsed_seconds", 2.100001),
        ("spawn_seconds", 3599),
        ("spawn_seconds", 0.314892),
        ("child_user_cpu_seconds", 3600),
        ("child_user_cpu_seconds", 0.36),
        *itertools.product(
            (
                "native_elapsed_seconds",
                "spawn_seconds",
                "child_user_cpu_seconds",
                "child_system_cpu_seconds",
            ),
            (-1, True, float("inf"), float("nan")),
        ),
    ],
)
def test_native_timing_evidence_rejects_incoherent_values(field: str, value: Any) -> None:
    report = passing_report()
    target = report if field == "native_elapsed_seconds" else report["qualifying_attempt"]
    target[field] = value
    with pytest.raises(probe.ProbeFailure, match="native_report_invalid"):
        probe.validate_native_report(json.dumps(report).encode(), 0, SHA, IMAGE, WORKER, HOST)


@pytest.mark.parametrize(
    "wall,spawn,cpu,valid",
    [
        (0.314891, 0.00049, 0.274423, True),
        (2.1, 2.1, 2.05, True),
        (2.1, 0, 2.050001, False),
        (2.100001, 0, 2.05, False),
        (1.0, 1.0, 1.05, True),
        (1.0, 1.000001, 1.05, False),
        (1.0, 1.0, 1.050001, False),
        (0.000001, 0, 0, True),
    ],
)
def test_native_timing_envelope_boundaries(
    wall: float, spawn: float, cpu: float, valid: bool
) -> None:
    report = passing_report()
    report["native_elapsed_seconds"] = wall
    report["qualifying_attempt"].update(
        spawn_seconds=spawn, child_user_cpu_seconds=cpu, child_system_cpu_seconds=0
    )
    if not valid:
        with pytest.raises(probe.ProbeFailure, match="native_report_invalid"):
            probe.validate_native_report(json.dumps(report).encode(), 0, SHA, IMAGE, WORKER, HOST)
    else:
        assert (
            json.loads(
                probe.validate_native_report(
                    json.dumps(report).encode(), 0, SHA, IMAGE, WORKER, HOST
                )
            )
            == report
        )


@pytest.mark.parametrize("passed", [False, True])
def test_qemu_safe_serialization_preserves_actual_report_values(passed: bool) -> None:
    report = passing_report(False) if passed else failed_qemu_report()
    assert (
        json.loads(
            probe.validate_emulated_report(
                json.dumps(report).encode(), 0 if passed else 1, SHA, IMAGE, WORKER
            )
        )
        == report
    )


@pytest.mark.parametrize(
    "failure",
    [
        "decoder_rejected_fixture",
        "canonical_output",
        "unexpected_probe_failure",
        "decoder_process_contract",
        "runtime_identity",
        "installed_decoder",
    ],
)
def test_qemu_non_timeout_failures_remain_failures(failure: str) -> None:
    report = failed_qemu_report()
    report["failure"] = failure
    del report["diagnostic"]
    report["qualifying_attempt"].update(outcome="child_exit", exit_code=-24)
    assert (
        json.loads(
            probe.validate_emulated_report(json.dumps(report).encode(), 1, SHA, IMAGE, WORKER)
        )
        == report
    )


@pytest.mark.parametrize("phase", sorted(probe.PHASES))
def test_qemu_later_phase_does_not_hide_or_reclassify_failure(phase: str) -> None:
    report = failed_qemu_report()
    report["diagnostic"]["last_observed_phase"] = phase
    report["diagnostic"]["phase_markers"][0]["phase"] = phase
    assert (
        json.loads(
            probe.validate_emulated_report(json.dumps(report).encode(), 1, SHA, IMAGE, WORKER)
        )
        == report
    )


@pytest.mark.parametrize(
    "raw", [b"", b"private raw output", b"[]", b"{}" + b" " * 4096, b"[" * 2000 + b"]" * 2000]
)
def test_qemu_report_rejects_unsafe_output(raw: bytes) -> None:
    with pytest.raises(probe.ProbeFailure, match="emulated_report_invalid"):
        probe.validate_emulated_report(raw, 1, SHA, IMAGE, WORKER)


@pytest.mark.parametrize(
    "path,value",
    [
        (("raw",), "private"),
        (("commit",), "f" * 40),
        (("image_id",), "sha256:" + "f" * 64),
        (("worker_source_sha256",), "f" * 64),
        (("emulated_elapsed_seconds",), True),
        (("emulated_elapsed_seconds",), float("inf")),
        (("status",), "passed"),
        (("diagnostic", "raw"), "private"),
        (("diagnostic", "last_observed_phase"), "private"),
        (("diagnostic", "phase_markers"), [{}] * 12),
        (("diagnostic", "wall_limit_seconds"), 20.0),
        (("diagnostic", "child_reaped"), "true"),
    ],
)
def test_qemu_report_rejects_schema_or_provenance_mismatch(
    path: tuple[str, ...], value: Any
) -> None:
    report = failed_qemu_report()
    target = report
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(probe.ProbeFailure, match="emulated_report_invalid"):
        probe.validate_emulated_report(json.dumps(report).encode(), 1, SHA, IMAGE, WORKER)


def test_qemu_duplicate_keys_are_not_normalized() -> None:
    raw = json.dumps(failed_qemu_report()).replace(
        '"status": "failed"', '"status": "passed", "status": "failed"'
    )
    with pytest.raises(probe.ProbeFailure, match="emulated_report_invalid"):
        probe.validate_emulated_report(raw.encode(), 1, SHA, IMAGE, WORKER)


@pytest.mark.parametrize(
    "passed,exit_code",
    [(True, 1), (False, 0), (False, -1), (False, 256), (False, True), (False, None)],
)
def test_qemu_report_requires_consistent_actual_exit(passed: bool, exit_code: Any) -> None:
    report = passing_report(False) if passed else failed_qemu_report()
    with pytest.raises(probe.ProbeFailure, match="emulated_report_invalid"):
        probe.validate_emulated_report(json.dumps(report).encode(), exit_code, SHA, IMAGE, WORKER)


def test_architecture_requires_native_and_exact_three_builds_from_current_event() -> None:
    workflow = (ROOT / ".github/workflows/local-runtime.yml").read_text()
    assert "image: [platform.local, web, operations]" in workflow
    assert "fail-fast: false" in workflow
    assert "  arm64-qualification:\n" in workflow
    assert "needs: [arm64-build, arm64-native-decoder]" in workflow
    assert "'${{ needs." not in workflow
    assert "branding-arm64-emulated" not in workflow
    for job in ("arm64-build", "arm64-native-decoder"):
        segment = workflow.split(f"  {job}:\n", 1)[1].split("\n  arm64-", 1)[0]
        assert (
            "- uses: actions/checkout@v4\n        with:\n          ref: ${{ github.sha }}"
            in segment
        )
        assert "continue-on-error" not in segment
    native = workflow.split("  arm64-native-decoder:\n", 1)[1].split("  arm64-build:\n", 1)[0]
    assert native.count("if:") == 1  # Only job public guard, never optional validation.


@pytest.mark.parametrize(
    "build,native",
    list(
        itertools.product(("success", "failure", "skipped", "cancelled", "", "pending"), repeat=2)
    ),
)
def test_aggregate_rejects_every_non_success_dependency(
    build: str, native: str, tmp_path: Path
) -> None:
    workflow = (ROOT / ".github/workflows/local-runtime.yml").read_text()
    aggregate = workflow.split("  arm64-qualification:\n", 1)[1]
    assert "    if: always()\n" in aggregate
    assert "      ARM64_BUILD_RESULT: ${{ needs.arm64-build.result }}" in aggregate
    assert "      ARM64_NATIVE_RESULT: ${{ needs.arm64-native-decoder.result }}" in aggregate
    script = textwrap.dedent(aggregate.split("        run: |\n", 1)[1])
    assert "${{" not in script
    result = subprocess.run(
        ["bash", "-c", script],
        env={
            **os.environ,
            "ARM64_BUILD_RESULT": build,
            "ARM64_NATIVE_RESULT": native,
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
        },
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) is (build == native == "success")
    assert "physical Raspberry qualification remains OPEN" in result.stdout


def test_qemu_workflow_is_separate_public_non_qualifying_read_only_diagnostic() -> None:
    workflow = QEMU_WORKFLOW.read_text()
    for token in (
        "NON-QUALIFYING",
        "workflow_dispatch:",
        "pull_request:",
        "branches: [main]",
        "contents: read",
        "runs-on: ubuntu-latest",
        "if: always()",
        "if: github.event.repository.private == false && "
        "toJSON(github.event.repository.private) == 'false'",
        "ref: ${{ github.sha }}",
        "DOCKER_BUILD_RECORD_UPLOAD: 'false'",
        "cache-from: type=gha,scope=local-runtime-platform.local-arm64",
        "if-no-files-found: error",
        "branding-arm64-emulated-exit.json",
    ):
        assert token in workflow
    for forbidden in (
        "cache-to:",
        "continue-on-error",
        "paths:",
        "permissions: write",
        "push: true",
        "type=registry",
        "upload-artifact@v3",
        "|| true",
    ):
        assert forbidden not in workflow


@pytest.mark.parametrize(
    "scenario,process_exit,expected_exit,collection,outcome",
    [
        ("pass", 0, 0, "validated_locally", "passed"),
        ("failure", 1, 1, "validated_locally", "failed"),
        ("failure", 137, 137, "validated_locally", "failed"),
        ("raw", 125, 125, "invalid_report", "unavailable"),
        ("missing", 124, 124, "invalid_report", "unavailable"),
        ("raw", 0, 1, "invalid_report", "unavailable"),
        ("failure", 0, 1, "invalid_report", "unavailable"),
        ("pass", 1, 1, "invalid_report", "unavailable"),
        ("setup_failed", None, 1, "setup_failed", "unavailable"),
        ("image_identity_failed", None, 1, "image_identity_failed", "unavailable"),
    ],
)
def test_qemu_evidence_cli_retains_exit_and_sanitizes_before_publication(
    scenario: str,
    process_exit: int | None,
    expected_exit: int,
    collection: str,
    outcome: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw = tmp_path / "private.raw"
    report = passing_report(False) if scenario == "pass" else failed_qemu_report()
    if scenario != "missing":
        raw.write_text("private raw Docker output" if scenario == "raw" else json.dumps(report))
    output = tmp_path / "artifacts"
    argv = [
        "probe",
        "--commit",
        SHA,
        "--image-id",
        IMAGE,
        "--image-platform",
        "linux/arm64",
        "--worker-sha256",
        WORKER,
        "--validate-emulated-report",
        str(raw),
        "--evidence-directory",
        str(output),
        "--workflow-run-id",
        "123",
        "--workflow-run-attempt",
        "2",
        "--collection-category",
        scenario if scenario in ("setup_failed", "image_identity_failed") else "observed",
    ]
    if process_exit is not None:
        argv += ["--probe-exit-code", str(process_exit)]
    monkeypatch.setattr(probe.sys, "argv", argv)
    assert probe.main() == expected_exit
    published = json.loads((output / "branding-arm64-emulated.json").read_text())
    sidecar = json.loads((output / "branding-arm64-emulated-exit.json").read_text())
    assert sidecar == {
        "schema_version": 1,
        "execution": probe.EMULATED,
        "qualification": "NON-QUALIFYING",
        "commit": SHA,
        "image_id": IMAGE,
        "workflow_run_id": "123",
        "workflow_run_attempt": "2",
        "probe_exit_code": process_exit,
        "decoder_outcome": outcome,
        "evidence_collection": collection,
        "original_cause": "unproven",
        "physical_device_qualified": False,
    }
    if collection == "validated_locally":
        assert published == report
    else:
        assert published["status"] == "unavailable"
    captured = capsys.readouterr()
    assert "NON-QUALIFYING" in captured.out and "original cause unproven" in captured.out
    assert "private" not in captured.out + captured.err + json.dumps(published) + json.dumps(
        sidecar
    )
    assert len(json.dumps(published)) < 4096 and len(json.dumps(sidecar)) < 1024


def test_qemu_publication_failure_cannot_be_reported_as_collected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw = tmp_path / "raw"
    raw.write_text(json.dumps(passing_report(False)))
    output = tmp_path / "not-a-directory"
    output.write_text("private")
    monkeypatch.setattr(
        probe.sys,
        "argv",
        [
            "probe",
            "--commit",
            SHA,
            "--image-id",
            IMAGE,
            "--image-platform",
            "linux/arm64",
            "--worker-sha256",
            WORKER,
            "--validate-emulated-report",
            str(raw),
            "--evidence-directory",
            str(output),
            "--workflow-run-id",
            "123",
            "--workflow-run-attempt",
            "2",
            "--probe-exit-code",
            "0",
        ],
    )
    assert probe.main() == 1
    captured = capsys.readouterr()
    assert "evidence publication FAILED" in captured.out
    assert "validated_locally" not in captured.out and "private" not in captured.out + captured.err


@pytest.mark.parametrize(
    "scenario,expected_exit,outer_exit,ran",
    [
        ("pass", 0, 0, True),
        ("failure", 1, 1, True),
        ("signal", 137, 137, True),
        ("raw", 125, 125, True),
        ("empty", 124, 124, True),
        ("invalid_zero", 1, 0, True),
        ("inconsistent", 1, 0, True),
        ("duplicate", 1, 0, True),
        ("oversized", 1, 0, True),
        ("build", 1, None, False),
        ("skipped", 1, None, False),
        ("inspect", 1, None, False),
        ("cleanup", 1, 0, True),
        ("summary", 1, 0, True),
    ],
)
def test_qemu_workflow_shell_keeps_real_failure_and_bounded_private_evidence(
    scenario: str,
    expected_exit: int,
    outer_exit: int | None,
    ran: bool,
    tmp_path: Path,
) -> None:
    """Only shell/control-flow evidence with synthetic Docker, never ARM execution."""
    commands = tmp_path / "commands"
    commands.mkdir()
    script_path = tmp_path / "scripts/ci/branding_image_probe.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_bytes((ROOT / "scripts/ci/branding_image_probe.py").read_bytes())
    worker = tmp_path / "services/platform/src/cycling_workshop/branding/images.py"
    worker.parent.mkdir(parents=True)
    worker.write_bytes((ROOT / worker.relative_to(tmp_path)).read_bytes())
    report = (
        failed_qemu_report()
        if scenario in ("failure", "signal", "inconsistent")
        else passing_report(False)
    )
    report["worker_source_sha256"] = hashlib.sha256(worker.read_bytes()).hexdigest()
    source = tmp_path / "synthetic.json"
    source.write_text(json.dumps(report))
    summary = tmp_path / "summary"
    if scenario == "summary":
        summary.mkdir()
    trace = tmp_path / "trace.jsonl"
    fake = (
        "#!"
        + sys.executable
        + "\n"
        + textwrap.dedent(r"""
        import json, os, pathlib, sys
        name, args = pathlib.Path(sys.argv[0]).name, sys.argv[1:]
        scenario = os.environ['SCENARIO']
        with open(os.environ['TRACE'], 'a') as stream:
            stream.write(json.dumps([name, *args]) + '\n')
        if name == 'git':
            if args[0] == 'rev-parse':
                print('a' * 40)
            else:
                worker = pathlib.Path('services/platform/src/cycling_workshop/branding/images.py')
                print(worker.read_text(), end='')
        elif args[0] == 'image':
            if scenario == 'inspect':
                print('private-inspection', file=sys.stderr)
                sys.exit(1)
            print('sha256:' + 'b' * 64 if args[3] == '{{.Id}}' else 'linux/arm64')
        elif args[0] == 'run':
            print('private-container-diagnostic', file=sys.stderr)
            if scenario == 'empty':
                sys.exit(124)
            if scenario in ('raw', 'invalid_zero', 'oversized'):
                print('private-output' * (1000 if scenario == 'oversized' else 1))
                sys.exit(125 if scenario == 'raw' else 0)
            raw = pathlib.Path(os.environ['SYNTHETIC']).read_text()
            if scenario == 'duplicate':
                raw = raw.replace('"status": "passed"', '"status": "failed", "status": "passed"')
            print(raw)
            sys.exit(137 if scenario == 'signal' else 1 if scenario == 'failure' else 0)
        elif args[0] == 'rm':
            print('private-cleanup', file=sys.stderr)
            sys.exit(3 if scenario == 'cleanup' else 0)
        else:
            sys.exit(99)
    """)
    )
    for name in ("git", "docker"):
        command = commands / name
        command.write_text(fake)
        command.chmod(0o700)
    (commands / "python3").symlink_to(sys.executable)
    workflow = QEMU_WORKFLOW.read_text()
    script = textwrap.dedent(
        workflow.split("        run: |\n", 1)[1].split("\n      - name:", 1)[0]
    )
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        env=os.environ
        | {
            "PATH": str(commands) + os.pathsep + os.defpath,
            "SCENARIO": scenario,
            "TRACE": str(trace),
            "SYNTHETIC": str(source),
            "BUILD_RESULT": "failure"
            if scenario == "build"
            else "skipped"
            if scenario == "skipped"
            else "success",
            "RUNNER_TEMP": str(tmp_path),
            "GITHUB_STEP_SUMMARY": str(summary),
            "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "2",
        },
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == expected_exit
    assert "private-" not in result.stdout + result.stderr
    sidecar = json.loads((tmp_path / "artifacts/branding-arm64-emulated-exit.json").read_text())
    evidence = json.loads((tmp_path / "artifacts/branding-arm64-emulated.json").read_text())
    assert sidecar["probe_exit_code"] == outer_exit
    assert sidecar["qualification"] == "NON-QUALIFYING"
    if scenario in ("pass", "failure", "signal", "cleanup", "summary"):
        assert evidence == report
        assert sidecar["evidence_collection"] == "validated_locally"
    else:
        assert sidecar["decoder_outcome"] == "unavailable"
    calls = [json.loads(line) for line in trace.read_text().splitlines()]
    runs = [call for call in calls if call[:2] == ["docker", "run"]]
    cleanup = [call for call in calls if call[:2] == ["docker", "rm"]]
    assert len(runs) == int(ran)
    if ran:
        assert IMAGE in runs[0]
        assert "ocwp-branding-qemu:" + SHA not in runs[0]
    assert cleanup == ([["docker", "rm", "--force", "ocwp-branding-qemu-123-2"]] if ran else [])
    assert not list(tmp_path.glob("branding-qemu.*"))
    if scenario != "summary":
        assert summary.read_text() == result.stdout
    assert len(json.dumps(evidence)) < 4096 and len(json.dumps(sidecar)) < 1024


def test_required_workflow_steps_cannot_be_silently_skipped() -> None:
    workflow = (ROOT / ".github/workflows/local-runtime.yml").read_text()
    build = workflow.split("  arm64-build:\n", 1)[1].split("  arm64-qualification:\n", 1)[0]
    assert build.count("uses: docker/build-push-action@v6") == 2
    assert [line.strip() for line in build.splitlines() if "if:" in line] == [
        "if: matrix.image != 'platform.local'",
        "if: matrix.image == 'platform.local'",
    ]
    assert "outputs: type=cacheonly" in build and "load: true" in build
    assert "continue-on-error" not in workflow
    aggregate = workflow.split("  arm64-qualification:\n", 1)[1]
    assert aggregate.count("if:") == 1 and "outputs:" not in aggregate
    assert aggregate.count("needs:") == 1
    native = workflow.split("  arm64-native-decoder:\n", 1)[1].split("  arm64-build:\n", 1)[0]
    assert native.count("--validate-native-report") == 1 and native.count("run: |") == 1
    qemu = QEMU_WORKFLOW.read_text()
    assert qemu.count("uses: docker/build-push-action@v6") == 1
    assert qemu.count("uses: actions/upload-artifact@v4") == 1
    assert qemu.count("if: always()") == 2
    assert "timeout --signal=TERM --kill-after=5s 30s docker run" in qemu
    assert "timeout --signal=TERM --kill-after=5s 10s docker rm" in qemu
    assert "${{" not in qemu.split("        run: |\n", 1)[1].split("\n      - name:", 1)[0]


@pytest.mark.parametrize("partial", [True, False])
def test_qemu_retains_partial_diagnostic_and_all_eleven_safe_phases(partial: bool) -> None:
    report = failed_qemu_report()
    if partial:
        report["diagnostic"] = {"diagnostic_only": True, "outcome": "diagnostic_unavailable"}
    else:
        phases = sorted(probe.PHASES)
        report["diagnostic"]["phase_markers"] = [
            {
                "phase": phase,
                "wall_seconds": 1.0,
                "user_cpu_seconds": 0.9,
                "system_cpu_seconds": 0.1,
            }
            for phase in phases
        ]
        report["diagnostic"]["last_observed_phase"] = phases[-1]
    encoded = probe.validate_emulated_report(json.dumps(report).encode(), 1, SHA, IMAGE, WORKER)
    assert json.loads(encoded) == report
    assert len(encoded.encode()) < 4096


@pytest.mark.parametrize(
    "missing",
    [
        "runtime",
        "worker_source_sha256",
        "decoder_limits",
        "qualifying_attempt",
        "decoder_process",
        "canonical_output",
    ],
)
def test_qemu_passing_report_cannot_omit_required_proof(missing: str) -> None:
    report = passing_report(False)
    del report[missing]
    with pytest.raises(probe.ProbeFailure, match="emulated_report_invalid"):
        probe.validate_emulated_report(json.dumps(report).encode(), 0, SHA, IMAGE, WORKER)
