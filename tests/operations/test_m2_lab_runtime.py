"""Fake-executor orchestration tests; no Docker, OpenSSL or credentials executed."""

import importlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

from scripts.ci import m2_lab_hosted as hosted


def module():
    assert importlib.util.find_spec("scripts.ci.m2_lab_runtime") is not None, "runtime missing"
    return importlib.import_module("scripts.ci.m2_lab_runtime")


class FakeExecutor:
    def __init__(self, plan, owned, runtime):
        self.plan, self.owned, self.runtime = plan, owned, runtime
        self.calls = []
        self.rows = {}
        self.problem = ""

    def status(self, phase):
        p = self.plan
        value = {
            "schema": 2,
            "nonce": p.nonce,
            "source_commit": p.commit,
            "source_tree": p.tree,
            "phase": phase,
            "stage": "database_cleanup" if phase == "stopped" else "serving",
            "checks": dict.fromkeys(hosted.SERVICE_CHECKS, True),
            "database_cleanup_complete": phase == "stopped",
        }
        if self.problem == "schema_bool":
            value["schema"] = True
        if self.problem == "status_source":
            value["source_tree"] = "0" * 40
        if self.problem == "missing_check":
            value["checks"].pop("scope")
        if self.problem == "cleanup":
            value["database_cleanup_complete"] = False
        path = p.root / "credential/api-status.json"
        path.write_text(json.dumps(value))
        path.chmod(0o600)

    def __call__(self, args, *, timeout=5):
        assert 0 < timeout <= 120
        self.calls.append(args)
        p = self.plan
        if args[0] == "git":
            if "HEAD^{tree}" in args:
                return "0" * 40 if self.problem == "tree" else p.tree
            return "" if "status" in args else p.commit
        if args[:3] == ["docker", "image", "inspect"]:
            image = args[-1]
            return json.dumps(
                {
                    "Id": image,
                    "Config": {
                        "Labels": {
                            "org.opencontainers.image.revision": p.commit,
                            "org.opencontainers.image.tree": "0" * 40
                            if self.problem == "image"
                            else p.tree,
                        }
                    },
                }
            )
        if args[0] == "openssl":
            saved = json.loads(self.owned.read_text())
            assert saved["root_identity"]["ino"] == p.root.stat().st_ino
            assert set(saved["directories"]) == set(self.runtime.DIRECTORIES)
            for flag in ("-out", "-keyout"):
                if flag in args:
                    Path(args[args.index(flag) + 1]).write_text("SYNTHETIC-NON-KEY-FIXTURE")
            return ""
        if args[:2] == ["docker", "ps"]:
            return "9" * 64 if self.problem == "collision" else ""
        if args[:2] == ["docker", "create"]:
            role = args[args.index("--name") + 1].rsplit("-", 1)[1]
            cid = {"db": "1", "api": "2", "connector": "3"}[role] * 64
            mem, cpu, pids = {
                "db": (768, 1000000000, 128),
                "api": (512, 1000000000, 64),
                "connector": (128, 500000000, 32),
            }[role]
            self.rows[cid] = {
                "Id": cid,
                "Image": p.image_for(role),
                "Name": "/" + p.name(role),
                "Config": {
                    "Labels": p.labels(role),
                    "User": "postgres" if role == "db" else f"{p.uid}:{p.gid}",
                },
                "HostConfig": {
                    "NetworkMode": "container:" + "1" * 64 if role == "api" else "none",
                    "ReadonlyRootfs": True,
                    "Privileged": False,
                    "CapDrop": ["ALL"],
                    "SecurityOpt": ["no-new-privileges:true"],
                    "LogConfig": {"Type": "none"},
                    "Memory": mem * 1024**2,
                    "MemorySwap": mem * 1024**2,
                    "NanoCpus": cpu,
                    "PidsLimit": pids,
                    "IpcMode": "private",
                    "CgroupnsMode": "private",
                    "Tmpfs": dict(
                        args[i + 1].split(":", 1) for i, arg in enumerate(args) if arg == "--tmpfs"
                    ),
                },
                "Mounts": [
                    {"Type": "bind", "Source": a, "Destination": b, "RW": not c}
                    for a, b, c in hosted.mount_specs(p, role)
                ],
                "State": {"Running": True, "ExitCode": 0},
            }
            return cid
        if args[:2] == ["docker", "inspect"]:
            row = self.rows[args[-1]]
            if self.problem == "containment":
                row["HostConfig"]["Privileged"] = True
            return json.dumps(row)
        if args[:2] == ["docker", "start"]:
            cid = args[-1]
            if cid == "2" * 64:
                self.status("ready")
            if "--attach" in args:
                self.rows[cid]["State"]["Running"] = self.problem == "still_running"
                if self.problem == "duplicate":
                    return (
                        '{"status":"refused","status":"ok","item_count":3,'
                        '"projection_disposed":true,"tls_negative":{"wrong_hostname":true,'
                        '"wrong_ca":true},"isolation_verified":true,"network_namespace":"net:[2]"}'
                    )
                return json.dumps(
                    {
                        "status": "ok",
                        "item_count": 3,
                        "projection_disposed": True,
                        "tls_negative": {"wrong_hostname": True, "wrong_ca": True},
                        "isolation_verified": True,
                        "network_namespace": "net:[1]"
                        if self.problem == "namespace"
                        else "net:[2]",
                        **({"extra": "not allowed"} if self.problem == "client" else {}),
                    }
                )
            return cid
        if args[:2] == ["docker", "exec"]:
            if "readlink" in args:
                return "net:[1]"
            if self.problem == "health_command":
                raise hosted.LabFailure("command")
            return "0"
        if args[:2] == ["docker", "stop"]:
            self.status("stopped")
            self.rows[args[-1]]["State"]["Running"] = False
            return args[-1]
        raise AssertionError(f"unexpected fake command: {args}")


def setup(tmp_path, monkeypatch):
    runtime = module()
    monkeypatch.setattr(hosted, "ROOT", tmp_path)
    monkeypatch.setattr(runtime.secrets, "token_hex", lambda _size: "f" * 64)
    plan = hosted.RunPlan(
        "a" * 32,
        "b" * 40,
        "c" * 40,
        "sha256:" + "d" * 64,
        "sha256:" + "e" * 64,
        os.getuid(),
        os.getgid(),
    )
    owned, evidence = tmp_path / "owned.json", tmp_path / "result.json"
    return runtime, plan, owned, evidence, FakeExecutor(plan, owned, runtime)


def test_run_requires_all_observed_checks_and_records_before_private_inputs(tmp_path, monkeypatch):
    runtime, plan, owned, evidence, execute = setup(tmp_path, monkeypatch)
    result = runtime.run(plan, owned, evidence, execute=execute)
    assert set(result) == set(hosted.SERVICE_CHECKS) | {
        "network_isolation",
        "tls_hostname",
        "tls_trust",
        "projection_disposed",
        "containment",
        "database_cleanup",
    }
    assert all(value is True for value in result.values())
    manifest = json.loads(owned.read_text())
    assert manifest["containers"] == {"db": "1" * 64, "api": "2" * 64, "connector": "3" * 64}
    assert plan.root.joinpath("pg-password").stat().st_mode & 0o777 == 0o444
    assert plan.root.joinpath("api-private/pg-password").stat().st_mode & 0o777 == 0o400
    assert not evidence.exists(), "CLI, not runtime, owns final combined evidence"
    assert not any("rm" in call for call in execute.calls)


@pytest.mark.parametrize(
    "problem",
    [
        "tree",
        "image",
        "status_source",
        "schema_bool",
        "missing_check",
        "cleanup",
        "containment",
        "namespace",
        "client",
        "duplicate",
        "still_running",
    ],
)
def test_runtime_refuses_unproven_boundary(tmp_path, monkeypatch, problem):
    runtime, plan, owned, evidence, execute = setup(tmp_path, monkeypatch)
    execute.problem = problem
    with pytest.raises(hosted.LabFailure):
        runtime.run(plan, owned, evidence, execute=execute)
    assert not evidence.exists()
    assert not any("rm" in call for call in execute.calls)


def test_existing_root_is_not_adopted_or_modified(tmp_path, monkeypatch):
    runtime, plan, owned, evidence, execute = setup(tmp_path, monkeypatch)
    plan.root.mkdir()
    marker = plan.root / "foreign"
    marker.write_text("keep")
    with pytest.raises(hosted.LabFailure):
        runtime.run(plan, owned, evidence, execute=execute)
    assert marker.read_text() == "keep"
    assert not any(call[0] == "openssl" for call in execute.calls)


def test_existing_owned_manifest_is_not_overwritten(tmp_path, monkeypatch):
    runtime, plan, owned, evidence, execute = setup(tmp_path, monkeypatch)
    owned.write_text("foreign")
    with pytest.raises(hosted.LabFailure):
        runtime.run(plan, owned, evidence, execute=execute)
    assert owned.read_text() == "foreign"


def test_torn_ready_status_is_pending_not_failure_or_success(tmp_path, monkeypatch):
    runtime, plan, owned, evidence, execute = setup(tmp_path, monkeypatch)
    original_status = execute.status

    def partial_status(phase):
        if phase == "ready":
            path = plan.root / "credential/api-status.json"
            path.write_text("{")
            path.chmod(0o600)
        else:
            original_status(phase)

    execute.status = partial_status
    sleeps = []

    def advance(_seconds):
        sleeps.append(True)
        original_status("ready")

    monkeypatch.setattr(runtime.time, "sleep", advance)
    assert all(runtime.run(plan, owned, evidence, execute=execute).values())
    assert sleeps == [True]


def test_name_collision_fails_before_any_create(tmp_path, monkeypatch):
    runtime, plan, owned, evidence, execute = setup(tmp_path, monkeypatch)
    execute.problem = "collision"
    with pytest.raises(hosted.LabFailure):
        runtime.run(plan, owned, evidence, execute=execute)
    assert not any(call[:2] == ["docker", "create"] for call in execute.calls)


def test_health_command_failure_is_never_retried(tmp_path, monkeypatch):
    runtime, plan, owned, evidence, execute = setup(tmp_path, monkeypatch)
    execute.problem = "health_command"
    clock = iter(range(0, 5000, 10))
    monkeypatch.setattr(runtime.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(runtime.time, "sleep", lambda _seconds: None)
    with pytest.raises(hosted.LabFailure):
        runtime.run(plan, owned, evidence, execute=execute)
    calls = [call for call in execute.calls if call[:2] == ["docker", "exec"]]
    assert len(calls) == 1


def test_internal_runtime_reserves_cleanup_inside_outer_timeout():
    runtime = module()
    assert getattr(runtime, "RUNTIME_SECONDS", None) == 760
    assert runtime.RUNTIME_SECONDS + 90 + 30 == 880


def test_ready_poll_cannot_outlive_global_runtime_deadline(tmp_path, monkeypatch):
    runtime, plan, owned, evidence, execute = setup(tmp_path, monkeypatch)
    now = [0.0]
    sleeps = []
    monkeypatch.setattr(runtime.time, "monotonic", lambda: now[0])

    def advance(_seconds):
        sleeps.append(True)
        assert len(sleeps) <= 1, "poll continued after global deadline"
        now[0] += 11

    def pending(args, *, timeout=5):
        result = execute(args, timeout=timeout)
        if args == ["docker", "start", "2" * 64]:
            now[0] = 750
            (plan.root / "credential/api-status.json").write_text("{")
        return result

    monkeypatch.setattr(runtime.time, "sleep", advance)
    with pytest.raises(hosted.LabFailure) as error:
        runtime.run(plan, owned, evidence, execute=pending)
    assert error.value.reason == "deadline"
    assert sleeps == [True]


def test_source_status_does_not_refresh_large_disposable_git_index(tmp_path, monkeypatch):
    """Only public Git fixture commands execute; Docker/OpenSSL remain fake."""
    import hashlib
    import subprocess
    from dataclasses import replace

    runtime, plan, owned, evidence, _execute = setup(tmp_path, monkeypatch)
    fixture = tmp_path / "public-git"
    fixture.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=fixture, check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "-q")
    git("config", "core.fsmonitor", "false")
    for number in range(700):
        (fixture / f"public-{number:04d}.txt").write_text(f"Public synthetic fixture {number}\n")
    git("add", ".")
    git(
        "-c",
        "user.name=Public Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "public fixture",
    )
    plan = replace(plan, commit=git("rev-parse", "HEAD"), tree=git("rev-parse", "HEAD^{tree}"))
    execute = FakeExecutor(plan, owned, runtime)
    index = fixture / ".git/index"
    before = hashlib.sha256(index.read_bytes()).hexdigest()
    assert index.stat().st_size > 16384
    for path in fixture.glob("public-*.txt"):
        info = path.stat()
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
    monkeypatch.chdir(fixture)
    actual_git_calls = []

    def execute_public_git_only(args, *, timeout=5):
        if args[0] == "git":
            actual_git_calls.append(args)
            return runtime.bounded_command(args, timeout=timeout)
        return execute(args, timeout=timeout)

    assert all(runtime.run(plan, owned, evidence, execute=execute_public_git_only).values())
    assert len(actual_git_calls) == 3
    assert all(args[1] == "--no-optional-locks" for args in actual_git_calls)
    assert hashlib.sha256(index.read_bytes()).hexdigest() == before
    assert not (fixture / ".git/index.lock").exists()


@pytest.mark.parametrize(
    "stage,expected",
    [
        ("source", "source"),
        ("image", "identity"),
        ("ownership", "ownership"),
        ("private", "private_input"),
        ("container", "containment"),
        ("serving", "runtime"),
    ],
)
def test_unexpected_execution_failure_has_closed_stage_reason(
    tmp_path, monkeypatch, stage, expected
):
    runtime, plan, owned, evidence, execute = setup(tmp_path, monkeypatch)
    original_save = runtime._save_owned

    def save(*args, **kwargs):
        if stage == "ownership":
            raise OSError("DO-NOT-EXPOSE-PRIVATE-DIAGNOSTIC")
        return original_save(*args, **kwargs)

    monkeypatch.setattr(runtime, "_save_owned", save)

    def fail_at_stage(args, *, timeout=5):
        trigger = (
            (stage == "source" and args[0] == "git")
            or (stage == "image" and args[:3] == ["docker", "image", "inspect"])
            or (stage == "private" and args[0] == "openssl")
            or (stage == "container" and args[:2] == ["docker", "create"])
            or (stage == "serving" and args[:2] == ["docker", "start"] and "--attach" in args)
        )
        if trigger:
            raise OSError("DO-NOT-EXPOSE-PRIVATE-DIAGNOSTIC")
        return execute(args, timeout=timeout)

    with pytest.raises(hosted.LabFailure) as error:
        runtime.run(plan, owned, evidence, execute=fail_at_stage)
    assert error.value.reason == expected
    assert str(error.value) == expected
    assert "PRIVATE-DIAGNOSTIC" not in str(error.value)
    assert not evidence.exists()


SUPERVISOR_STAGES = (
    "source",
    "images",
    "workspace",
    "private_inputs",
    "db_create",
    "db_start",
    "db_ready",
    "api_create",
    "api_start",
    "api_ready",
    "namespace",
    "connector_create",
    "connector_run",
    "connector_result",
    "api_stop",
    "database_disposal",
)


@pytest.mark.parametrize("boundary", SUPERVISOR_STAGES)
def test_each_boundary_retains_only_completed_prefix(tmp_path, monkeypatch, boundary):
    runtime, plan, owned, evidence, execute = setup(tmp_path, monkeypatch)
    progress = hosted.Progress()
    original = progress.enter

    def enter(stage):
        original(stage)
        if stage == boundary:
            raise hosted.LabFailure("command")

    monkeypatch.setattr(progress, "enter", enter)
    with pytest.raises(hosted.LabFailure):
        runtime.run(plan, owned, evidence, execute=execute, progress=progress)
    value = progress.value()
    assert value["stage"] == boundary
    assert value["completed"] == list(SUPERVISOR_STAGES[: SUPERVISOR_STAGES.index(boundary)])
    assert not evidence.exists()


def test_completed_progress_and_valid_snapshot_are_distinct_from_pass(tmp_path, monkeypatch):
    runtime, plan, owned, evidence, execute = setup(tmp_path, monkeypatch)
    progress = hosted.Progress()
    checks = runtime.run(plan, owned, evidence, execute=execute, progress=progress)
    runtime.snapshot(plan, progress)
    value = progress.value()
    assert value["stage"] == "completed" and value["completed"] == list(SUPERVISOR_STAGES)
    assert value["api"]["observation"] == "valid"
    assert value["api"]["snapshot"]["phase"] == "stopped"
    assert set(checks) == hosted.CHECKS and all(checks.values())


@pytest.mark.parametrize(
    "problem",
    [
        "absent",
        "torn",
        "duplicate",
        "unknown",
        "nonce",
        "tree",
        "commit",
        "mode",
        "symlink",
        "hardlink",
        "fifo",
        "oversized",
        "schema",
        "stage",
        "check",
        "boolean",
    ],
)
def test_api_snapshot_rejects_untrusted_payload_without_copying_it(tmp_path, monkeypatch, problem):
    runtime, plan, _owned, _evidence, execute = setup(tmp_path, monkeypatch)
    plan.root.mkdir(mode=0o700)
    (plan.root / "credential").mkdir(mode=0o700)
    execute.status("ready")
    path = plan.root / "credential/api-status.json"
    value = json.loads(path.read_text())
    canary = "PRIVATE-CANARY-NEVER-EXPORT"
    if problem == "absent":
        path.unlink()
    elif problem == "torn":
        path.write_text("{" + canary)
    elif problem == "duplicate":
        path.write_text('{"schema":2,"schema":2}')
    elif problem == "unknown":
        value[canary] = canary
    elif problem in ("nonce", "tree", "commit"):
        value[{"nonce": "nonce", "tree": "source_tree", "commit": "source_commit"}[problem]] = (
            "0"
            * len(
                value[{"nonce": "nonce", "tree": "source_tree", "commit": "source_commit"}[problem]]
            )
        )
    elif problem == "mode":
        path.chmod(0o644)
    elif problem == "symlink":
        path.rename(path.with_suffix(".saved"))
        path.symlink_to(path.with_suffix(".saved"))
    elif problem == "hardlink":
        path.with_suffix(".link").hardlink_to(path)
    elif problem == "fifo":
        path.unlink()
        os.mkfifo(path)
    elif problem == "oversized":
        path.write_text(" " * 65537)
    elif problem == "schema":
        value["schema"] = True
    elif problem == "stage":
        value["stage"] = canary
    elif problem == "check":
        value["checks"][canary] = True
    elif problem == "boolean":
        value["checks"]["scope"] = 1
    if problem in ("unknown", "nonce", "tree", "commit", "schema", "stage", "check", "boolean"):
        path.write_text(json.dumps(value))
    progress = hosted.Progress()
    runtime.snapshot(plan, progress)
    result = progress.value()["api"]
    assert result["observation"] not in ("valid", "not_observed")
    assert result["snapshot"] is None
    leaked = canary in json.dumps(progress.value())
    assert not leaked


def test_snapshot_cannot_read_after_reserved_deadline(tmp_path, monkeypatch):
    runtime, plan, _owned, _evidence, _execute = setup(tmp_path, monkeypatch)
    now = [0.0]
    monkeypatch.setattr(hosted.time, "monotonic", lambda: now[0])
    progress = hosted.Progress()
    now[0] = 760
    monkeypatch.setattr(runtime, "read_json", lambda *a, **k: pytest.fail("expired snapshot read"))
    runtime.snapshot(plan, progress)
    assert progress.value()["api"] == {"observation": "unavailable", "snapshot": None}


@pytest.mark.parametrize("kind", ["foreign_owner", "unexpected_file", "directory_mode"])
def test_snapshot_rejects_unsafe_private_directory(tmp_path, monkeypatch, kind):
    runtime, plan, _owned, _evidence, execute = setup(tmp_path, monkeypatch)
    plan.root.mkdir(mode=0o700)
    directory = plan.root / "credential"
    directory.mkdir(mode=0o700)
    execute.status("ready")
    if kind == "unexpected_file":
        (directory / "not-in-inventory").write_text("canary")
    elif kind == "directory_mode":
        directory.chmod(0o755)
    else:
        from types import SimpleNamespace

        original = Path.lstat

        def info(path, *args, **kwargs):
            value = original(path, *args, **kwargs)
            if path == directory:
                return SimpleNamespace(st_mode=value.st_mode, st_uid=os.getuid() + 1)
            return value

        monkeypatch.setattr(Path, "lstat", info)
    progress = hosted.Progress()
    runtime.snapshot(plan, progress)
    assert progress.value()["api"] == {"observation": "filesystem", "snapshot": None}


def test_snapshot_read_overtime_does_not_claim_valid(tmp_path, monkeypatch):
    runtime, plan, _owned, _evidence, _execute = setup(tmp_path, monkeypatch)
    now = [0.0]
    monkeypatch.setattr(hosted.time, "monotonic", lambda: now[0])
    progress = hosted.Progress()

    def value(_plan):
        now[0] = 761
        return {
            "phase": "ready",
            "stage": "serving",
            "checks": dict.fromkeys(hosted.SERVICE_CHECKS, True),
            "database_cleanup_complete": False,
        }

    monkeypatch.setattr(runtime, "_api_value", value)
    runtime.snapshot(plan, progress)
    assert progress.value()["api"] == {"observation": "unavailable", "snapshot": None}


@pytest.mark.parametrize("boundary", SUPERVISOR_STAGES)
def test_actual_operation_failure_preserves_only_observed_prefix(tmp_path, monkeypatch, boundary):
    runtime, plan, owned, evidence, execute = setup(tmp_path, monkeypatch)
    progress = hosted.Progress()
    save = runtime._save_owned
    status = runtime._status
    triggered = []

    def fail():
        triggered.append(True)
        raise OSError("SYNTHETIC-PRIVATE-CANARY")

    def save_owned(*args, **kwargs):
        if boundary == "workspace":
            fail()
        return save(*args, **kwargs)

    def read_status(p, phase):
        if (boundary == "api_ready" and phase == "ready") or (
            boundary == "database_disposal" and phase == "stopped"
        ):
            fail()
        return status(p, phase)

    def command(args, *, timeout=5):
        role = (
            args[args.index("--name") + 1].rsplit("-", 1)[1]
            if args[:2] == ["docker", "create"]
            else None
        )
        target = (
            (boundary == "source" and args[0] == "git")
            or (boundary == "images" and args[:3] == ["docker", "image", "inspect"])
            or (boundary == "private_inputs" and args[0] == "openssl")
            or (boundary.endswith("_create") and role == boundary.removesuffix("_create"))
            or (boundary == "db_start" and args == ["docker", "start", "1" * 64])
            or (
                boundary == "db_ready" and args[:3] == ["docker", "exec", "1" * 64] and "sh" in args
            )
            or (boundary == "api_start" and args == ["docker", "start", "2" * 64])
            or (boundary == "namespace" and "readlink" in args)
            or (boundary == "connector_run" and args[:3] == ["docker", "start", "--attach"])
            or (boundary == "api_stop" and args[:2] == ["docker", "stop"])
        )
        if target:
            fail()
        result = execute(args, timeout=timeout)
        if boundary == "connector_result" and args[:3] == ["docker", "start", "--attach"]:
            triggered.append(True)
            return '{"status":"SYNTHETIC-PRIVATE-CANARY"}'
        return result

    monkeypatch.setattr(runtime, "_save_owned", save_owned)
    monkeypatch.setattr(runtime, "_status", read_status)
    with pytest.raises(hosted.LabFailure):
        runtime.run(plan, owned, evidence, execute=command, progress=progress)
    assert triggered == [True]
    assert progress.value()["stage"] == boundary
    assert progress.value()["completed"] == list(
        SUPERVISOR_STAGES[: SUPERVISOR_STAGES.index(boundary)]
    )
    leaked = "SYNTHETIC-PRIVATE-CANARY" in json.dumps(progress.value())
    assert not leaked


def test_root_ca_command_is_hermetic_and_explicitly_strict_compatible(tmp_path, monkeypatch):
    """Command contract only; fake executor never generates keys or uses OpenSSL."""
    runtime, plan, owned, evidence, execute = setup(tmp_path, monkeypatch)
    runtime.run(plan, owned, evidence, execute=execute)
    commands = [call for call in execute.calls if call[0] == "openssl"]
    assert len(commands) == 3
    assert commands[0] == [
        "openssl",
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-days",
        "1",
        "-subj",
        "/CN=OCWP-M2-Ephemeral",
        "-keyout",
        str(plan.root / "ca/ca.key"),
        "-out",
        str(plan.root / "ca/ca.crt"),
        "-config",
        "/dev/null",
        "-addext",
        "basicConstraints=critical,CA:TRUE",
        "-addext",
        "keyUsage=critical,keyCertSign,cRLSign",
        "-addext",
        "subjectKeyIdentifier=hash",
        "-addext",
        "authorityKeyIdentifier=keyid:always",
    ]
