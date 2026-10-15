"""Paired immutable-image proof must establish, not assume, the file-cap mismatch."""

import json
from unittest.mock import MagicMock

import pytest

from scripts.ci import inventory_edge_probe as probe

HASH = "a" * 64
RAW_ID = "sha256:" + "b" * 64
WEB_ID = "sha256:" + "c" * 64
PRIVATE = "private-unexpected-output"


def fake_docker(calls, *, raw_code=126, raw_hint="Operation not permitted", web_hash=HASH):
    def docker(*args, **kwargs):
        calls.append((args, kwargs))
        if args[:2] == ("image", "inspect"):
            return RAW_ID if args[-1] == probe.IMAGE else WEB_ID
        if args[0] == "run":
            return "container"
        if args[0] == "wait":
            return str(raw_code if "-raw-" in args[1] else 0)
        if args[0] == "logs":
            if "-raw-" in args[1]:
                return (
                    f"{HASH}  /usr/bin/caddy\n/usr/bin/caddy cap_net_bind_service=ep\n"
                    f"sh: caddy: {raw_hint}\n"
                )
            return f"{web_hash}  /usr/bin/caddy\nv2.11.7 h1:synthetic\n"
        return "synthetic"

    return docker


def test_existing_production_recipe_and_identical_immutable_launches(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(probe, "docker", fake_docker(calls))
    monkeypatch.setattr(probe.os, "getuid", lambda: 1001)
    monkeypatch.setattr(probe.os, "getgid", lambda: 1002)
    evidence = {}
    image = probe.prepare_images("synthetic-tag", tmp_path, evidence)
    assert image == WEB_ID
    assert evidence["launch_controls"]["equal_binary_sha256"] is True
    raw, web = (evidence["launch_controls"][key] for key in ("raw", "production"))
    assert raw["binary_sha256"] == web["binary_sha256"] == HASH
    assert raw["file_capability"] == "cap_net_bind_service=ep"
    assert web["file_capability"] == "none"
    assert raw["exit_code"] == 126 and raw["operation_not_permitted"] is True
    assert web["exit_code"] == 0 and web["version"] == "v2.11.7"
    builds = [(args, kwargs) for args, kwargs in calls if args[0] == "build"]
    assert len(builds) == 1 and builds[0][1]["timeout"] == 600
    assert builds[0][0] == (
        "build",
        "--quiet",
        "--file",
        str(probe.ROOT / "infra/docker/web.Dockerfile"),
        "--tag",
        "synthetic-tag",
        str(probe.ROOT),
    )
    runs = [args for args, _ in calls if args[0] == "run"]
    assert len(runs) == 2
    assert runs[0][-4] == RAW_ID and runs[1][-4] == WEB_ID
    assert (
        runs[0][-3:]
        == runs[1][-3:]
        == (
            "sh",
            "-c",
            "sha256sum /usr/bin/caddy && getcap /usr/bin/caddy && /usr/bin/caddy version",
        )
    )
    assert runs[0][4:-4] == runs[1][4:-4]
    for run in runs:
        assert run[run.index("--user") + 1] == "1001:1002"
        assert "--read-only" in run
        assert run[run.index("--cap-drop") + 1] == "ALL"
        assert run[run.index("--security-opt") + 1] == "no-new-privileges"
    assert len([args for args, _ in calls if args[0] == "rm"]) == 2


@pytest.mark.parametrize(
    "override",
    [
        {"raw_code": 0},
        {"raw_hint": PRIVATE},
        {"web_hash": "d" * 64},
    ],
)
def test_contradictory_control_cannot_qualify(tmp_path, monkeypatch, override):
    calls = []
    monkeypatch.setattr(probe, "docker", fake_docker(calls, **override))
    with pytest.raises(probe.EdgeProbeFailure) as caught:
        probe.prepare_images("synthetic-tag", tmp_path, {})
    assert caught.value.evidence["phase"] == "launch_controls"
    assert PRIVATE not in json.dumps(caught.value.evidence)
    assert any(args[0] == "rm" for args, _ in calls)


@pytest.mark.parametrize("raw", [True, False])
@pytest.mark.parametrize(
    "metadata",
    [
        PRIVATE,
        f"{HASH}  /other/binary\n",
        f"{HASH}  /usr/bin/caddy\n/usr/bin/caddy cap_sys_admin=ep\n",
    ],
)
def test_control_rejects_unexpected_metadata_safely(tmp_path, monkeypatch, raw, metadata):
    def docker(*args, **kwargs):
        if args[0] == "logs":
            return metadata
        if args[0] == "wait":
            return "126" if raw else "0"
        return "synthetic"

    monkeypatch.setattr(probe, "docker", docker)
    with pytest.raises(probe.EdgeProbeFailure) as caught:
        probe.launch_control(RAW_ID, "raw" if raw else "production", tmp_path)
    assert PRIVATE not in json.dumps(caught.value.evidence)
    assert caught.value.evidence["cleanup"]["container"] is True


def test_control_original_failure_survives_cleanup_failure(tmp_path, monkeypatch):
    def docker(*args, **kwargs):
        if args[0] == "wait":
            raise probe.CommandFailure("timeout")
        if args[0] == "rm":
            raise probe.CommandFailure("exit", 9)
        return "synthetic"

    monkeypatch.setattr(probe, "docker", docker)
    with pytest.raises(probe.EdgeProbeFailure) as caught:
        probe.launch_control(RAW_ID, "raw", tmp_path)
    failure = caught.value.evidence
    assert failure["reason"] == "timeout"
    assert failure["cleanup"]["container"] is False
    assert failure["cleanup"]["container_error"]["exit_code"] == 9


def test_main_retains_probe_failure_and_image_cleanup_failure(tmp_path, monkeypatch):
    for name in probe.SOURCE_PATHS:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic")
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(probe.os, "getuid", lambda: 1001)
    monkeypatch.setattr(probe, "prepare_images", MagicMock(return_value=WEB_ID))
    monkeypatch.setattr(probe, "docker", MagicMock(side_effect=probe.CommandFailure("exit", 7)))
    monkeypatch.setattr(
        probe,
        "probe",
        MagicMock(
            side_effect=probe.EdgeProbeFailure(
                {
                    "phase": "readiness",
                    "error": "assertion",
                    "cleanup": {"container": True},
                }
            )
        ),
    )
    with pytest.raises(SystemExit):
        probe.main()
    evidence = json.loads(
        (tmp_path / "artifacts/inventory-read/edge-runtime-evidence.json").read_text()
    )
    assert evidence["status"] == "failed" and evidence["failure"]["phase"] == "readiness"
    assert evidence["failure"]["cleanup"]["image"] is False
    assert evidence["failure"]["cleanup"]["image_error"]["exit_code"] == 7
    assert probe.probe.call_args.kwargs["image"] == WEB_ID


def test_unexpected_raw_success_retains_safe_observation(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(probe, "docker", fake_docker(calls, raw_code=0))
    with pytest.raises(probe.EdgeProbeFailure) as caught:
        probe.launch_control(RAW_ID, "raw", tmp_path)
    failure = caught.value.evidence
    assert failure["stage"] == "expected_outcome"
    assert failure["observation"]["exit_code"] == 0
    assert failure["observation"]["binary_sha256"] == HASH
    assert failure["observation"]["file_capability"] == "cap_net_bind_service=ep"


@pytest.mark.parametrize("identity", [PRIVATE, "sha256:" + "z" * 64])
def test_invalid_image_identity_rejected_before_launch(tmp_path, monkeypatch, identity):
    calls = []

    def docker(*args, **kwargs):
        calls.append(args)
        return identity

    monkeypatch.setattr(probe, "docker", docker)
    with pytest.raises(probe.EdgeProbeFailure) as caught:
        probe.prepare_images("synthetic-tag", tmp_path, {})
    assert caught.value.evidence["phase"] == "image_identity"
    assert not any(args[0] == "run" for args in calls)
    assert PRIVATE not in json.dumps(caught.value.evidence)


def test_root_host_is_blocked_before_docker_and_invalidates_old_success(tmp_path, monkeypatch):
    for name in probe.SOURCE_PATHS:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic")
    destination = tmp_path / "artifacts/inventory-read/edge-runtime-evidence.json"
    destination.parent.mkdir(parents=True)
    destination.write_text('{"status":"complete"}')
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(probe.os, "getuid", lambda: 0)
    command = MagicMock()
    monkeypatch.setattr(probe, "docker", command)
    with pytest.raises(SystemExit, match="nonroot"):
        probe.main()
    command.assert_not_called()
    assert json.loads(destination.read_text())["status"] == "incomplete"


@pytest.mark.parametrize("role", ["raw", "production"])
def test_version_and_eperm_contradiction_rejected(tmp_path, monkeypatch, role):
    def docker(*args, **kwargs):
        if args[0] == "wait":
            return "126" if role == "raw" else "0"
        if args[0] == "logs":
            cap = "/usr/bin/caddy cap_net_bind_service=ep\n" if role == "raw" else ""
            return f"{HASH}  /usr/bin/caddy\n{cap}v2.11.7 operation not permitted\n"
        return "synthetic"

    monkeypatch.setattr(probe, "docker", docker)
    with pytest.raises(probe.EdgeProbeFailure) as caught:
        probe.launch_control(RAW_ID, role, tmp_path)
    assert caught.value.evidence["stage"] == "expected_outcome"


def test_unrecognized_file_capability_is_not_reported_as_absent(tmp_path, monkeypatch):
    def docker(*args, **kwargs):
        if args[0] == "wait":
            return "1"
        if args[0] == "logs":
            return f"{HASH}  /usr/bin/caddy\n/usr/bin/caddy cap_sys_admin=ep\n"
        return "synthetic"

    monkeypatch.setattr(probe, "docker", docker)
    with pytest.raises(probe.EdgeProbeFailure) as caught:
        probe.launch_control(RAW_ID, "raw", tmp_path)
    assert caught.value.evidence["stage"] == "capability_metadata"
    assert "file_capability" not in caught.value.evidence["observation"]
