"""Small fail-closed tests; never launch Docker or build a quote history."""

import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / "scripts/ci/quote_capacity_micro.py"
spec = importlib.util.spec_from_file_location("quote_capacity_micro", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def probe():
    values = [
        "536870912",
        "0",
        "100000 100000",
        "64",
        "4096",
        "8192",
        "usage_usec 100\nuser_usec 80\nsystem_usec 20",
        "oom 0\noom_kill 0\nmax 0",
        "max 0",
    ]
    return "0::/" + "".join(
        f"\n---{key}---\n{value}" for key, value in zip(module.FIELDS, values, strict=True)
    )


def test_exact_enforced_limits_and_numeric_counters():
    assert module.parse_probe(probe(), 512, 64) == {"cpu_usec": 100, "memory_peak": 8192}


def test_full_route_stops_worker_before_reaping_failed_exec_client(monkeypatch):
    from types import SimpleNamespace

    events = []
    clock = iter([0.0, 1.0])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(module.os, "killpg", lambda *args: events.append("client_kill"))
    client = SimpleNamespace(
        pid=1234, poll=lambda: None, wait=lambda **kwargs: events.append("client_reap")
    )
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: client)
    with pytest.raises(module.ProofFailure, match="command_timeout"):
        module.full_client(
            ["docker", "exec", "a" * 64, "fixed-reader"],
            timeout=0.05,
            abort=lambda: events.append("worker_verified_stopped"),
        )
    assert events == ["worker_verified_stopped", "client_kill", "client_reap"]


def test_full_route_unverified_stop_stays_failure_even_after_client_hygiene(monkeypatch):
    from types import SimpleNamespace

    events = []
    clock = iter([0.0, 1.0])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(module.os, "killpg", lambda *args: events.append("client_kill"))
    client = SimpleNamespace(
        pid=1234, poll=lambda: None, wait=lambda **kwargs: events.append("client_reap")
    )
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: client)

    def abort():
        events.extend(["stop_unverified", "owned_reconciliation_attempted"])
        raise module.ProofFailure("worker_stop_unverified")

    with pytest.raises(module.ProofFailure, match="worker_stop_unverified"):
        module.full_client(["docker", "exec", "a" * 64, "fixed-reader"], timeout=0.05, abort=abort)
    assert events == [
        "stop_unverified",
        "owned_reconciliation_attempted",
        "client_kill",
        "client_reap",
    ]


def test_full_diagnostic_retains_only_the_bounded_host_spool(tmp_path):
    import json
    import tempfile

    with tempfile.TemporaryFile() as output:
        output.write(b"x" * (module.FULL_SPOOL_LIMIT + 1))
        output.flush()
        module.full_save_diagnostic(output, tmp_path / "receipt.json")
    assert (tmp_path / "diagnostic.txt").stat().st_size == module.FULL_SPOOL_LIMIT
    assert json.loads((tmp_path / "diagnostic.json").read_text()) == {
        "schema": 1,
        "available": True,
        "retained_bytes": module.FULL_SPOOL_LIMIT,
        "at_limit_or_truncated": True,
    }


@pytest.mark.parametrize(
    "fault", [None, "nonzero", "cap", "timeout", "reap", "spawn", "nonzero_reap"]
)
def test_preparation_client_retains_only_reaped_bounded_output(tmp_path, monkeypatch, fault):
    import json
    from types import SimpleNamespace

    events = []
    raw = b"build diagnostic" if fault != "cap" else b"x" * module.LIMIT
    clock = iter([0.0, 1.0] if fault == "timeout" else [0.0, 0.0])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(module.os, "killpg", lambda *args: events.append("client_kill"))

    def launch(args, **kwargs):
        assert args == ["docker", "build", "--quiet"]
        if fault == "spawn":
            raise OSError("unavailable synthetic client")
        kwargs["stdout"].write(raw)
        kwargs["stdout"].flush()
        client = SimpleNamespace(
            pid=1234,
            returncode=7 if fault in {"nonzero", "nonzero_reap"} else 0,
            poll=lambda: None if fault == "timeout" else 0,
        )

        def wait(**kwargs):
            events.append("client_reap")
            if fault in {"reap", "nonzero_reap"}:
                raise module.subprocess.TimeoutExpired("fixed", 2)
            if fault == "timeout":
                client.returncode = -9
            return client.returncode

        client.wait = wait
        return client

    monkeypatch.setattr(module.subprocess, "Popen", launch)
    original = module.full_preparation_diagnostic

    def save(output, *args, **kwargs):
        if output is not None and args[-1]:
            assert events[-1] == "client_reap"
        original(output, *args, **kwargs)

    monkeypatch.setattr(module, "full_preparation_diagnostic", save)
    arguments = {"timeout": 0.5, "preparation": (tmp_path, "image_build")}
    if fault:
        error = {
            "reap": module.subprocess.TimeoutExpired,
            "nonzero_reap": module.subprocess.TimeoutExpired,
            "spawn": OSError,
        }.get(fault, module.ProofFailure)
        with pytest.raises(error):
            module.full_client(["docker", "build", "--quiet"], **arguments)
    else:
        assert module.full_client(["docker", "build", "--quiet"], **arguments) == raw.decode()
    record = json.loads((tmp_path / "preparation.json").read_text())
    assert record["stage"] == "image_build"
    assert record["limit_bytes"] == module.LIMIT
    assert record["qualification"] == "not_a_receipt"
    assert record["build_resource_cleanup"] == "not_assessed"
    available = fault not in {"reap", "spawn", "nonzero_reap"}
    assert record["client_reaped"] is available
    assert record["available"] is available
    assert record["returncode"] == {
        "nonzero": 7,
        "timeout": -9,
        "reap": None,
        "spawn": None,
        "nonzero_reap": None,
    }.get(fault, 0)
    assert (
        record["failure"]
        == {
            None: None,
            "nonzero": "command_failed",
            "cap": "command_failed",
            "timeout": "command_timeout",
            "reap": "client_reap_unverified",
            "spawn": "tool_unavailable",
            "nonzero_reap": "command_failed",
        }[fault]
    )
    assert record["at_limit_or_truncated"] is (fault == "cap" if available else None)
    assert record["retained_bytes"] == (len(raw) if available else 0)
    assert (tmp_path / "preparation.txt").read_bytes() == (raw if available else b"")
    assert not (tmp_path / "receipt.json").exists()


@pytest.mark.parametrize("fault", [None, "nonzero", "cap", "running_cap", "nonzero_reap"])
def test_fixed_build_spool_retains_tail_and_preserves_failure(tmp_path, monkeypatch, fault):
    import json
    from types import SimpleNamespace

    events = []
    raw = b"discarded progress\n" + b"z" * module.LIMIT + b"final build diagnostic\n"
    if fault in {"cap", "running_cap"}:
        raw = b"x" * (module.FULL_BUILD_SPOOL_LIMIT - module.LIMIT) + raw[-module.LIMIT :]
    monkeypatch.setattr(module.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(module.os, "killpg", lambda *args: events.append("client_kill"))
    monkeypatch.setattr(module.resource, "setrlimit", lambda key, value: events.append(value))

    def launch(args, **kwargs):
        assert args == ["docker", "build", "--progress=plain"]
        kwargs["preexec_fn"]()
        kwargs["stdout"].write(raw)
        kwargs["stdout"].flush()
        client = SimpleNamespace(
            pid=1234,
            returncode=1 if fault in {"nonzero", "nonzero_reap"} else 0,
            poll=lambda: None if fault == "running_cap" else 0,
        )

        def wait(**kwargs):
            events.append("client_reap")
            if fault == "nonzero_reap":
                raise module.subprocess.TimeoutExpired("fixed", 2)
            if fault == "running_cap":
                client.returncode = -9
            return client.returncode

        client.wait = wait
        return client

    monkeypatch.setattr(module.subprocess, "Popen", launch)
    original = module.full_preparation_diagnostic

    def save(output, *args, **kwargs):
        if output is not None and args[-1]:
            assert events[-1] == "client_reap"
        original(output, *args, **kwargs)

    monkeypatch.setattr(module, "full_preparation_diagnostic", save)
    arguments = {
        "limit": module.FULL_BUILD_SPOOL_LIMIT,
        "preparation": (tmp_path, "image_build"),
    }
    if fault:
        error = module.subprocess.TimeoutExpired if fault == "nonzero_reap" else module.ProofFailure
        with pytest.raises(error):
            module.full_client(["docker", "build", "--progress=plain"], **arguments)
    else:
        assert (
            module.full_client(["docker", "build", "--progress=plain"], **arguments)
            == raw.decode().strip()
        )
    available = fault != "nonzero_reap"
    record = json.loads((tmp_path / "preparation.json").read_text())
    assert record["schema"] == 2
    assert record["capture"] == "tail"
    assert record["limit_bytes"] == module.LIMIT
    assert record["spool_limit_bytes"] == module.FULL_BUILD_SPOOL_LIMIT
    assert record["observed_bytes"] == (len(raw) if available else None)
    assert record["retained_bytes"] == (module.LIMIT if available else 0)
    assert record["dropped_prefix_bytes"] == (len(raw) - module.LIMIT if available else None)
    assert record["retention_truncated"] is (True if available else None)
    assert record["at_spool_limit"] is (fault in {"cap", "running_cap"} if available else None)
    assert record["client_reaped"] is available
    assert (
        record["failure"]
        == {
            None: None,
            "nonzero": "command_failed",
            "cap": "command_failed",
            "running_cap": "output_limit",
            "nonzero_reap": "command_failed",
        }[fault]
    )
    assert record["returncode"] == {"nonzero": 1, "nonzero_reap": None, "running_cap": -9}.get(
        fault, 0
    )
    assert record["qualification"] == "not_a_receipt"
    assert record["build_resource_cleanup"] == "not_assessed"
    assert events[0] == (module.FULL_BUILD_SPOOL_LIMIT, module.FULL_BUILD_SPOOL_LIMIT)
    assert (tmp_path / "preparation.txt").read_bytes() == (
        raw[-module.LIMIT :] if available else b""
    )
    assert not (tmp_path / "receipt.json").exists()


@pytest.mark.parametrize("fault", ["no_preparation", "other_stage", "quiet", "abort"])
def test_build_spool_cannot_expand_other_clients(tmp_path, monkeypatch, fault):
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("spawned"))
    arguments = {
        "limit": module.FULL_BUILD_SPOOL_LIMIT,
        "preparation": (tmp_path, "image_build"),
    }
    args = ["docker", "build", "--progress=plain"]
    if fault == "no_preparation":
        arguments["preparation"] = None
    elif fault == "other_stage":
        arguments["preparation"] = (tmp_path, "postgres_pull")
    elif fault == "quiet":
        args[-1] = "--quiet"
    else:
        arguments["abort"] = lambda: pytest.fail("abort called")
    with pytest.raises(module.ProofFailure, match="preparation_diagnostic_scope"):
        module.full_client(args, **arguments)


@pytest.mark.parametrize("fault", ["stage", "record_limit", "abort"])
def test_preparation_diagnostics_cannot_expand_the_control_scope(tmp_path, monkeypatch, fault):
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("spawned"))
    arguments = {"preparation": (tmp_path, "image_build")}
    if fault == "stage":
        arguments["preparation"] = (tmp_path, "arbitrary")
    elif fault == "record_limit":
        arguments["limit"] = module.FULL_RECORD_LIMIT
    else:
        arguments["abort"] = lambda: pytest.fail("abort called")
    with pytest.raises(module.ProofFailure, match="preparation_diagnostic_scope"):
        module.full_client(["docker", "build", "--quiet"], **arguments)


def test_default_full_client_spawn_failure_does_not_invoke_abort(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("unavailable synthetic client")

    monkeypatch.setattr(module.subprocess, "Popen", fail)
    with pytest.raises(OSError):
        module.full_client(["docker", "exec"], abort=lambda: pytest.fail("abort before spawn"))


def test_full_record_capture_accepts_only_fixed_names_and_typed_pending_marker():
    with pytest.raises(module.ProofFailure, match="record_name"):
        module.full_capture_record("a" * 64, "arbitrary", lambda *args: pytest.fail("spawned"))
    assert (
        module.full_capture_record(
            "a" * 64, "collection", lambda *args, **kwargs: '{"pending":true}'
        )
        is None
    )
    assert module.full_capture_record(
        "a" * 64, "collection", lambda *args, **kwargs: '{"pending":1}'
    ) == {"pending": 1}


@pytest.mark.parametrize("final", ["true|123", "false|123", "missing", "false|0"])
def test_full_stop_requires_exact_terminal_state(final):
    calls = []

    def execute(args, **kwargs):
        calls.append(args)
        if args[:2] == ["docker", "kill"]:
            return ""
        return "true|123" if len(calls) == 1 else final

    if final == "false|0":
        module.full_stop_worker("a" * 64, execute)
    else:
        with pytest.raises(module.ProofFailure, match="worker_stop_unverified"):
            module.full_stop_worker("a" * 64, execute)
    assert calls[1] == ["docker", "kill", "--signal", "KILL", "a" * 64]


def full_inspect_value():
    return {
        "id": "a" * 64,
        "image": "sha256:" + "b" * 64,
        "token": "c" * 32,
        "user": "10001:10001",
        "host": {
            "NetworkMode": "none",
            "Privileged": False,
            "ReadonlyRootfs": True,
            "Memory": 512 * 1024 * 1024,
            "MemorySwap": 512 * 1024 * 1024,
            "NanoCpus": 1_000_000_000,
            "PidsLimit": 64,
            "ShmSize": 64 * 1024 * 1024,
            "CgroupnsMode": "private",
            "CapDrop": ["ALL"],
            "IpcMode": "private",
            "PidMode": "",
            "UTSMode": "",
            "PublishAllPorts": False,
            "SecurityOpt": ["no-new-privileges:true"],
            "Tmpfs": module.FULL_TMPFS["worker"],
            "LogConfig": {"Type": "none", "Config": {}},
        },
        "mounts": [],
    }


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "shm",
        "memory",
        "exec_root",
        "bind",
        "extra_mount",
        "host_mount",
        "mount_shape",
        "tmpfs",
    ],
)
def test_full_boundary_has_fixed_memory_shm_and_only_declared_scratch(fault):
    import json

    value = full_inspect_value()
    if fault == "shm":
        value["host"]["ShmSize"] *= 2
    elif fault == "memory":
        value["host"]["Memory"] *= 2
    elif fault == "exec_root":
        value["host"]["ReadonlyRootfs"] = False
    elif fault == "bind":
        value["host"]["Binds"] = ["/host:/app"]
    elif fault == "extra_mount":
        value["mounts"].append({"Type": "volume", "Destination": "/other"})
    elif fault == "host_mount":
        value["host"]["Mounts"] = [{"Type": "tmpfs", "Target": "/other"}]
    elif fault == "mount_shape":
        value["mounts"] = None
    elif fault == "tmpfs":
        value["host"]["Tmpfs"] = {}

    def execute(*args, **kwargs):
        return json.dumps(value)

    if fault:
        with pytest.raises(module.ProofFailure) as caught:
            module.full_inspect("a" * 64, "sha256:" + "b" * 64, "c" * 32, "none", "canary", execute)
        assert (
            caught.value.check
            == {
                "shm": "ShmSize",
                "memory": "Memory",
                "exec_root": "ReadonlyRootfs",
                "bind": "attachments",
                "extra_mount": "Mounts",
                "host_mount": "HostConfig.Mounts",
                "mount_shape": "Mounts",
                "tmpfs": "Tmpfs",
            }[fault]
        )
    else:
        module.full_inspect("a" * 64, "sha256:" + "b" * 64, "c" * 32, "none", "canary", execute)


def full_scratch_value(role):
    paths = module.FULL_TMPFS[role] | {"/dev/shm": "size=64m,mode=1777"}
    stats, mounts = [], []
    for path, raw in paths.items():
        canonical = "/run/postgresql" if path == "/var/run/postgresql" else path
        options = dict(part.split("=", 1) if "=" in part else (part, "") for part in raw.split(","))
        blocks = int(options["size"][:-1]) * 256
        inodes = int(options.get("nr_inodes", "1024"))
        stats.extend(
            [
                f"{path}|tmpfs|4096|{blocks}|{blocks - 1}|{inodes}|{inodes - 1}",
                f"{path}|{options.get('uid', '0')}|{options.get('gid', '0')}|"
                f"{options['mode'].lstrip('0')}",
                f"{path}|{canonical}",
            ]
        )
        flags = "rw,nosuid,nodev" + ("" if path == "/tmp/ocwp-tests" else ",noexec")
        mounts.append(f"1 0 0:1 / {canonical} {flags} - tmpfs tmpfs rw")
    return "\n".join(stats) + "\n---mounts---\n" + "\n".join(mounts)


@pytest.mark.parametrize("role", ["worker", "db"])
@pytest.mark.parametrize(
    "fault",
    [
        None,
        "bytes",
        "inodes",
        "space",
        "flags",
        "canonical",
        "mount_missing",
        "mount_duplicate",
        "ownership",
    ],
)
def test_full_scratch_uses_kernel_bytes_inodes_permissions_and_flags(role, fault):
    raw = full_scratch_value(role)
    if fault == "bytes":
        raw = raw.replace("|4096|", "|8192|", 1)
    elif fault == "inodes":
        lines = raw.splitlines()
        values = lines[0].split("|")
        values[5:7] = ["32768", "32767"]
        lines[0] = "|".join(values)
        raw = "\n".join(lines)
    elif fault == "space":
        raw = raw.replace("|16384|16383|", "|16384|0|", 1)
    elif fault == "flags":
        raw = raw.replace("rw,nosuid,nodev,noexec", "rw,nosuid,nodev", 1)
    elif fault == "ownership":
        raw = raw.replace("/tmp|0|0|1777\n", "/tmp|1|0|1777\n", 1)
    elif fault == "canonical":
        original = "/var/run/postgresql|/run/postgresql" if role == "db" else "/tmp|/tmp"
        raw = raw.replace(original, original.rsplit("|", 1)[0] + "|/unexpected", 1)
    elif fault == "mount_missing":
        raw = raw.rsplit("\n", 1)[0]
    elif fault == "mount_duplicate":
        stats, mounts = raw.split("\n---mounts---\n")
        rows = mounts.splitlines()
        rows[-1] = rows[0]
        raw = stats + "\n---mounts---\n" + "\n".join(rows)

    def execute(args, **kwargs):
        assert args[:5] == ["docker", "exec", "a" * 64, "sh", "-c"]
        command = args[5]
        assert "readlink -e -- /tmp;" in command
        if role == "db":
            assert "readlink -e -- /var/run/postgresql;" in command
            assert '$5 == "/run/postgresql"' in command
            assert '$5 == "/var/run/postgresql"' not in command
        return raw

    if fault:
        with pytest.raises(module.ProofFailure) as error:
            module.full_scratch("a" * 64, role, execute)
        check, path, wanted, observed = {
            "bytes": ("scratch_bytes", "/tmp", 67108864, 134217728),
            "inodes": ("scratch_inodes", "/tmp", 16384, 32768),
            "space": ("scratch_free_blocks", "/tmp", [1, 16384], 0),
            "flags": ("scratch_mount_noexec", "/tmp", True, False),
            "canonical": (
                "scratch_realpath",
                "/var/run/postgresql" if role == "db" else "/tmp",
                "/run/postgresql" if role == "db" else "/tmp",
                "mismatch",
            ),
            "mount_missing": ("scratch_mount_rows", None, 4, 3),
            "mount_duplicate": ("scratch_mount_identity", "/tmp", 1, 2),
            "ownership": ("scratch_uid", "/tmp", 0, 1),
        }[fault]
        assert error.value.check == check
        assert error.value.scratch == {
            "path": path,
            "check": check,
            "expected": wanted,
            "observed": observed,
        }
    else:
        module.full_scratch("a" * 64, role, execute)


def test_full_preflight_failure_has_no_candidate_launch_and_cannot_qualify(tmp_path, monkeypatch):
    import json

    def fail(*args, **kwargs):
        raise module.ProofFailure("source_not_exact_clean_commit")

    monkeypatch.setattr(module, "full_identity", fail)
    monkeypatch.setattr(module, "full_reconcile", lambda *args: None)
    monkeypatch.setattr(module.signal, "signal", lambda *args: None)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("spawned"))
    receipt = tmp_path / "receipt.json"
    with pytest.raises(module.ProofFailure, match="full_python_unqualified"):
        module.supervise_python("worker", "postgres", "c" * 40, receipt, tmp_path / "owned.json")
    value = json.loads(receipt.read_text())
    assert value["failure"] == "source_identity"
    assert value["status"] == "failed"
    assert value["collection"] is value["result"] is None
    assert value["primary_cleanup"] == "verified_absent"
    assert value["independent_cleanup"] == "pending"


def test_independent_absence_cannot_promote_failed_or_missing_proof(tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(module, "full_reconcile", lambda *args: None)
    monkeypatch.setattr(module, "full_identity", lambda *args: {})
    receipt = tmp_path / "receipt.json"
    (tmp_path / "owned.owner.json").write_text("{}")
    receipt.write_text(json.dumps({"status": "failed", "failure": "wall_budget"}))
    with pytest.raises(module.ProofFailure, match="full_python_unqualified"):
        module.finalize_python("worker", "postgres", "c" * 40, receipt, tmp_path / "owned.json")
    assert json.loads(receipt.read_text())["status"] == "failed"
    assert json.loads(receipt.read_text())["failure"] == "wall_budget"
    assert (
        json.loads((tmp_path / "independent-cleanup.json").read_text())["outcome"]
        == "verified_absent"
    )


@pytest.mark.parametrize("fault", ["owner", "image", "receipt", "cleanup"])
def test_finalizer_retains_cleanup_evidence_without_qualification(tmp_path, monkeypatch, fault):
    import json

    receipt = tmp_path / "receipt.json"
    owned = tmp_path / "owned.json"
    if fault != "owner":
        owned.with_suffix(".owner.json").write_text("{}")

    def reconcile(*args):
        if fault == "cleanup":
            raise module.ProofFailure("cleanup_failed")

    def identity(*args):
        assert fault not in {"owner", "cleanup"}
        cleanup = json.loads((tmp_path / "independent-cleanup.json").read_text())
        assert cleanup["outcome"] == "verified_absent"
        if fault == "image":
            raise module.ProofFailure("image_identity")
        return {}

    monkeypatch.setattr(module, "full_reconcile", reconcile)
    monkeypatch.setattr(module, "full_identity", identity)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("spawned"))
    with pytest.raises(module.ProofFailure, match="full_python_unqualified"):
        module.finalize_python("worker", "postgres", "c" * 40, receipt, owned)
    cleanup = json.loads((tmp_path / "independent-cleanup.json").read_text())
    assert cleanup["outcome"] == {"owner": "no_ownership_manifest", "cleanup": "failed"}.get(
        fault, "verified_absent"
    )
    assert cleanup["owner_manifest_present"] is (fault != "owner")
    assert cleanup["qualification"] == "not_a_receipt"
    assert cleanup["build_resource_cleanup"] == "not_assessed"
    assert cleanup["expected_commit"] == "c" * 40
    assert not receipt.exists()


def test_finalizer_still_requires_both_receipt_validations(tmp_path, monkeypatch):
    import json

    from scripts.ci import verify_v01

    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"status": "failed", "failure": "independent_cleanup_pending"}))
    owned = tmp_path / "owned.json"
    owned.with_suffix(".owner.json").write_text("{}")
    calls = []
    monkeypatch.setattr(module, "full_reconcile", lambda *args: None)
    monkeypatch.setattr(module, "full_identity", lambda *args: {"exact": True})

    def validate(report, identity, *, allow_pending_cleanup=False):
        assert identity == {"exact": True}
        assert report["status"] == ("failed" if allow_pending_cleanup else "passed")
        calls.append(allow_pending_cleanup)

    monkeypatch.setattr(verify_v01, "validate_full_python_receipt", validate)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("spawned"))
    module.finalize_python("worker", "postgres", "c" * 40, receipt, owned)
    assert calls == [True, False]
    assert json.loads(receipt.read_text())["status"] == "passed"
    assert (
        json.loads((tmp_path / "independent-cleanup.json").read_text())["qualification"]
        == "not_a_receipt"
    )


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "workload",
        "workload_storage_timeout",
        "workload_deadline",
        "memory_oom",
        "memory_malformed",
        "memory_timeout",
        "memory_unavailable",
        "memory_fast_exit",
        "memory_stop",
        "memory_live_deadline",
        "canary_absence",
        "stop",
        "cleanup",
        "create",
        "inspect",
        "scratch",
        "inspect_cleanup",
    ],
)
def test_full_supervisor_terminal_paths_require_stop_and_both_cleanups(
    tmp_path, monkeypatch, fault
):
    import json
    from types import SimpleNamespace

    from scripts.ci import verify_v01

    events = []
    created = []
    allocations = []
    identity = {"image_id": "sha256:" + "b" * 64, "pg_image_id": "sha256:" + "c" * 64}
    monkeypatch.setattr(module, "full_identity", lambda *args: identity)
    monkeypatch.setattr(module.signal, "signal", lambda *args: None)

    def inspect(*args):
        if fault in {"inspect", "inspect_cleanup"}:
            raise module.ProofFailure("container_boundary", check="Memory")

    def scratch(*args):
        if fault == "scratch":
            raise module.ProofFailure("scratch_allocation")

    monkeypatch.setattr(module, "full_inspect", inspect)
    monkeypatch.setattr(module, "full_scratch", scratch)
    monkeypatch.setattr(module, "effective_privileges", lambda *args: None)

    def canary(*args):
        assert len(created) == 1 and allocations == [512]
        if fault == "canary_absence":
            raise module.ProofFailure("cleanup_failed")
        events.append("canary_absent")
        allocations.append(0)
        return {"cpu_usec": 100, "memory_peak": 8192}

    monkeypatch.setattr(module, "cancellation_canary", canary)
    monkeypatch.setattr(verify_v01, "validate_full_python_result", lambda *args: {})
    monkeypatch.setattr(verify_v01, "validate_full_python_collection", lambda *args: {})

    def execute(args, **kwargs):
        if args[:2] == ["docker", "create"]:
            if fault == "create":
                raise module.ProofFailure("command_timeout")
            role = ("canary", "db", "worker")[len(created)]
            memory, pids = {"canary": (512, 64), "db": (1024, 128), "worker": (768, 64)}[role]
            assert args[args.index("--memory") + 1] == f"{memory}m"
            assert args[args.index("--memory-swap") + 1] == f"{memory}m"
            assert args[args.index("--pids-limit") + 1] == str(pids)
            assert args[args.index("--cpus") + 1] == "1"
            if role != "canary":
                assert "canary_absent" in events
            allocations.append(memory + (allocations[-1] if allocations else 0))
            cid = str(len(created) + 1) * 64
            created.append(cid)
            Path(args[args.index("--cidfile") + 1]).write_text(cid)
            return cid
        if args[:2] == ["docker", "start"]:
            return ""
        if args[:2] == ["docker", "exec"]:
            if "pg_ls_waldir" in args[-1]:
                events.append("storage")
                if fault == "workload_storage_timeout":
                    raise module.ProofFailure("command_timeout")
                return "4096|131072|100000|12345\n33554432|83886080\n"
            if args[-1] == module.PROBE:
                # No observation may postpone stop after exec exit is known.
                assert "pytest_exit" not in events
                role = (
                    "worker"
                    if len(created) == 3 and args[2] == created[2]
                    else "db"
                    if len(created) > 1 and args[2] == created[1]
                    else "canary"
                )
                events.append("probe_" + role)
                if role == "worker" and "pytest" in events:
                    raw = (
                        probe()
                        .replace("536870912", "805306368")
                        .replace("---memory.current---\n4096", "---memory.current---\n8192")
                    )
                    raw = raw.replace("---memory.peak---\n8192", "---memory.peak---\n16384")
                    if events.count("probe_worker") == 3:
                        if fault == "memory_timeout":
                            kwargs["abort"]()
                            raise module.ProofFailure("command_timeout")
                        if fault == "memory_unavailable":
                            raise OSError("synthetic private error")
                        if fault == "memory_malformed":
                            return "synthetic private output"
                        if fault == "memory_oom":
                            return (
                                raw.replace("oom 0\noom_kill 0\nmax 0", "oom 2\noom_kill 1\nmax 9")
                                .replace(
                                    "---memory.current---\n8192", "---memory.current---\n524288000"
                                )
                                .replace("---memory.peak---\n16384", "---memory.peak---\n536870912")
                            )
                    return raw
                if len(created) > 1 and args[2] == created[1]:
                    return (
                        probe()
                        .replace("536870912", "1073741824")
                        .replace("---pids.max---\n64", "---pids.max---\n128")
                    )
                return probe().replace("536870912", "805306368") if role == "worker" else probe()
            if "pg_isready" in args:
                return ""
            if args[-2] == "-c":
                events.append("capture")
                return "{}"
        raise AssertionError(args)

    def stop(*args):
        events.append("stop")
        if fault in {"stop", "memory_stop"}:
            raise module.ProofFailure("worker_stop_unverified")

    def reconcile(*args):
        events.append("cleanup")
        if fault in {"cleanup", "inspect_cleanup"}:
            raise module.ProofFailure("cleanup_failed")

    def launch(args, **kwargs):
        events.append("pytest")
        if fault in {"workload_deadline", "memory_live_deadline"}:
            expired = module.time.monotonic() + module.FULL_SECONDS + 1
            monkeypatch.setattr(module.time, "monotonic", lambda: expired)
        assert args[-len(verify_v01.FULL_PYTHON_ARGS) :] == list(verify_v01.FULL_PYTHON_ARGS)
        assert "OCWP_QUOTE_MICRO=contained" not in args
        polls = []

        def poll():
            if fault and fault.startswith("memory_"):
                if "stop" in events:
                    return 137
                if fault == "memory_live_deadline":
                    return None
                polls.append(True)
                count = 1 if fault in {"memory_fast_exit", "memory_stop"} else 2
                if len(polls) <= count:
                    return None
                events.append("pytest_exit")
                return 137
            return 0

        return SimpleNamespace(
            returncode=137
            if fault and fault.startswith("memory_")
            else (1 if fault and fault.startswith("workload") else 0),
            poll=poll,
            wait=lambda **kwargs: events.append("reap"),
        )

    monkeypatch.setattr(module, "full_client", execute)
    monkeypatch.setattr(module, "full_stop_worker", stop)
    monkeypatch.setattr(module, "full_reconcile", reconcile)
    monkeypatch.setattr(module.subprocess, "Popen", launch)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    receipt = tmp_path / "receipt.json"
    if fault:
        with pytest.raises(module.ProofFailure, match="full_python_unqualified"):
            module.supervise_python("worker", "pg", "d" * 40, receipt, tmp_path / "owned.json")
    else:
        module.supervise_python("worker", "pg", "d" * 40, receipt, tmp_path / "owned.json")
    value = json.loads(receipt.read_text())
    assert value["policy"]["worker_memory_mib"] == 768
    if len(created) == 3:
        assert allocations == [512, 0, 1024, 1792]
        assert max(allocations) == 1792
    if fault == "canary_absence":
        assert len(created) == 1
        assert "pytest" not in events
        assert "canary_absent" not in events
    assert value["status"] == "failed"
    assert value["independent_cleanup"] == "pending"
    if fault is None:
        assert value["failure"] == "independent_cleanup_pending"
        assert events.index("capture") < events.index("stop") < events.index("reap")
        assert value["primary_cleanup"] == "verified_absent"
    else:
        assert value["failure"] != "independent_cleanup_pending"
    if fault in {"workload", "workload_storage_timeout", "workload_deadline", "create"}:
        assert "capture" not in events
    if fault in {"workload", "workload_storage_timeout", "workload_deadline"}:
        assert value["failure"] == "worker_failed"
        assert value["primary_cleanup"] == "verified_absent"
        diagnostic = json.loads((tmp_path / "diagnostic.json").read_text())
        expected = "captured" if fault == "workload" else "unavailable"
        assert diagnostic["postgres_storage"]["status"] == expected
        if fault == "workload_deadline":
            assert "storage" not in events
        else:
            assert events.index("reap") < events.index("storage") < events.index("cleanup")
    if fault and fault.startswith("memory_"):
        diagnostic = json.loads((tmp_path / "diagnostic.json").read_text())["memory"]
        assert diagnostic["qualification"] == "not_a_receipt"
        assert diagnostic["atomic"] is False
        assert diagnostic["terminal_observation"] == "not_taken"
        successful = diagnostic["last_successful"]["worker"]
        observed = diagnostic["last_observed"]["worker"]
        phase = "preflight" if fault == "memory_live_deadline" else "workload_poll"
        assert successful == {
            "phase": phase,
            "status": "captured",
            "memory_current_bytes": 4096 if phase == "preflight" else 8192,
            "memory_peak_bytes": 8192 if phase == "preflight" else 16384,
            "memory_max_bytes": 805306368,
            "memory_events": {"max": 0, "oom": 0, "oom_kill": 0},
        }
        if fault == "memory_oom":
            assert observed == successful | {
                "memory_current_bytes": 524288000,
                "memory_peak_bytes": 536870912,
                "memory_events": {"max": 9, "oom": 2, "oom_kill": 1},
            }
        elif fault in {"memory_malformed", "memory_timeout", "memory_unavailable"}:
            assert observed == {
                "phase": "workload_poll",
                "status": "unavailable",
                "reason": "invalid_output" if fault == "memory_malformed" else "probe_incomplete",
            }
        else:
            assert observed == successful
        assert (
            value["failure"]
            == {
                "memory_oom": "resource_pressure",
                "memory_malformed": "containment_failed",
                "memory_timeout": "containment_failed",
                "memory_unavailable": "invalid_evidence",
                "memory_fast_exit": "worker_failed",
                "memory_stop": "worker_stop_unverified",
                "memory_live_deadline": "wall_budget",
            }[fault]
        )
        exited = fault in {"memory_fast_exit", "memory_stop"}
        polls = 0 if fault == "memory_live_deadline" else 1 if exited else 2
        assert events.count("probe_worker") == events.count("probe_db") == polls + 1
        assert value["containment"]["resource_samples"] == {
            "worker": 1 if polls == 0 else 2,
            "db": polls + 1,
        }
        assert value["containment"]["worker_exit"] == (137 if exited else None)
        assert value["containment"]["final_probe"] == "pending"
        assert value["result"] is None
        if exited:
            assert events[events.index("pytest_exit") + 1] == "stop"
        assert events.index("stop") < events.index("reap")
        if fault == "memory_stop":
            assert events.index("stop") < events.index("cleanup") < events.index("reap")
        else:
            assert events.index("reap") < events.index("cleanup")
        assert "synthetic private" not in json.dumps(diagnostic)
    if fault in {"inspect", "scratch", "inspect_cleanup", "create"}:
        assert "pytest" not in events
        diagnostic = json.loads((tmp_path / "diagnostic.json").read_text())
        assert diagnostic["kind"] == "ocwp.full_python.preflight_failure"
        assert diagnostic["qualification"] == "not_a_receipt"
        assert diagnostic["status"] == "unqualified"
        assert diagnostic["identity"] == identity
        assert diagnostic["role"] == "canary"
        assert (
            diagnostic["stage"]
            == {
                "inspect": "inspect",
                "inspect_cleanup": "inspect",
                "scratch": "scratch",
                "create": "create",
            }[fault]
        )
        assert (
            diagnostic["failure"]
            == {
                "inspect": "container_boundary",
                "inspect_cleanup": "container_boundary",
                "scratch": "scratch_allocation",
                "create": "command_timeout",
            }[fault]
        )
        assert diagnostic["failed_field"] == (
            "Memory" if fault in {"inspect", "inspect_cleanup"} else None
        )
        assert diagnostic["returncode"] is None
        assert value["primary_cleanup"] == (
            "failed" if fault == "inspect_cleanup" else "verified_absent"
        )
        assert value["collection"] is value["result"] is None
    if fault == "stop":
        assert not (tmp_path / "diagnostic.txt").exists()
        assert json.loads((tmp_path / "diagnostic.json").read_text())["available"] is False
    if "reap" in events:
        assert events.index("stop") < events.index("reap")


def test_preflight_diagnostic_is_closed_bounded_and_not_raw_output(tmp_path):
    import json

    evidence = tmp_path / "receipt.json"
    module.full_preflight_diagnostic(
        evidence, None, "start", "canary", module.ProofFailure("command_failed", returncode=-25)
    )
    assert json.loads((tmp_path / "diagnostic.json").read_text())["returncode"] == -25
    for check in (
        "scratch_stat_rows",
        "scratch_mount_rows",
        "scratch_realpath",
        "scratch_stat_shape",
        "scratch_bytes",
        "scratch_free_blocks",
        "scratch_free_inodes",
        "scratch_inodes",
        "scratch_ownership_shape",
        "scratch_ownership_identity",
        "scratch_uid",
        "scratch_gid",
        "scratch_mode",
        "scratch_mount_identity",
        "scratch_mount_type",
        "scratch_mount_rw",
        "scratch_mount_nosuid",
        "scratch_mount_nodev",
        "scratch_mount_noexec",
        "scratch_format",
    ):
        module.full_preflight_diagnostic(
            evidence, None, "scratch", "db", module.ProofFailure("scratch_readback", check=check)
        )
        value = json.loads((tmp_path / "diagnostic.json").read_text())
        assert value["failed_field"] == check
        assert value["status"] == "unqualified"
        assert value["qualification"] == "not_a_receipt"
    detail = {"path": "/tmp", "check": "scratch_uid", "expected": 0, "observed": 1}
    module.full_preflight_diagnostic(
        evidence,
        None,
        "scratch",
        "db",
        module.ProofFailure("scratch_allocation", check="scratch_uid", scratch=detail),
    )
    assert json.loads((tmp_path / "diagnostic.json").read_text())["scratch"] == detail
    interval = {
        "path": "/tmp",
        "check": "scratch_free_blocks",
        "expected": [1, 16384],
        "observed": 0,
    }
    module.full_preflight_diagnostic(
        evidence,
        None,
        "scratch",
        "db",
        module.ProofFailure("scratch_allocation", check="scratch_free_blocks", scratch=interval),
    )
    assert json.loads((tmp_path / "diagnostic.json").read_text())["scratch"] == interval
    for bad in (
        detail | {"path": "/untrusted"},
        detail | {"check": "untrusted"},
        detail | {"observed": "untrusted"},
        detail | {"observed": 2**128},
        detail | {"extra": True},
        interval | {"expected": [True, 16384]},
    ):
        check = (
            "scratch_free_blocks" if bad.get("check") == "scratch_free_blocks" else "scratch_uid"
        )
        module.full_preflight_diagnostic(
            evidence,
            None,
            "scratch",
            "db",
            module.ProofFailure("scratch_allocation", check=check, scratch=bad),
        )
        value = json.loads((tmp_path / "diagnostic.json").read_text())
        assert "scratch" not in value
        assert value["failure"] == "scratch_allocation"
        assert value["failed_field"] == check
        assert value["status"] == "unqualified"
    module.full_preflight_diagnostic(
        evidence,
        None,
        "untrusted-stage",
        "untrusted-role",
        module.ProofFailure("untrusted-output", check="untrusted-field", returncode=2**32),
    )
    raw = (tmp_path / "diagnostic.json").read_text()
    value = json.loads(raw)
    assert "untrusted" not in raw
    assert value["stage"] == "unavailable"
    assert value["failure"] == "invalid_evidence"
    assert value["role"] is value["failed_field"] is value["returncode"] is None
    assert len(raw.encode("utf-8")) < module.LIMIT
    with pytest.raises(module.ProofFailure, match="preflight_diagnostic_limit"):
        module.full_preflight_diagnostic(
            evidence, "x" * module.LIMIT, "inspect", "canary", ValueError()
        )
    assert (tmp_path / "diagnostic.json").read_text() == raw


@pytest.mark.parametrize(
    "old,new",
    [
        ("0::/", "0::/other"),
        ("536870912", "max"),
        ("100000 100000", "max 100000"),
        ("---pids.max---\n64", "---pids.max---\nmax"),
        ("usage_usec 100", "usage_usec -1"),
        ("usage_usec 100", "usage_usec nope"),
        ("oom_kill 0", "oom_kill 1"),
        ("---cpu.stat---", "MISSING"),
        ("8192", "536870913"),
    ],
)
def test_missing_or_wrong_containment_fails_closed(old, new):
    with pytest.raises(module.ProofFailure):
        module.parse_probe(probe().replace(old, new), 512, 64)


def test_cpu_counters_cannot_go_backwards_or_exceed_budget():
    with pytest.raises(module.ProofFailure):
        module.cpu_delta({"worker": 100}, {"worker": 99}, 600)
    with pytest.raises(module.ProofFailure):
        module.cpu_delta({"worker": 0, "db": 0}, {"worker": 400_000_000, "db": 201_000_000}, 600)
    assert module.cpu_delta({"worker": 100}, {"worker": 300}, 600) == 200


def test_cleanup_failure_is_not_absence():
    calls = []

    def failed(*args, **kwargs):
        calls.append(args)
        raise module.ProofFailure("command_failed")

    with pytest.raises(module.ProofFailure):
        module.remove_owned(["a" * 64], failed)
    assert calls


def test_cleanup_requires_successful_listing_and_absence():
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return "a" * 64 if args[:2] == ["docker", "ps"] else ""

    with pytest.raises(module.ProofFailure):
        module.remove_owned(["a" * 64], run)
    assert calls[0] == ["docker", "rm", "--force", "a" * 64]


def test_cleanup_success_reverses_creation_order():
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return ""

    module.remove_owned(["a" * 64, "b" * 64], run)
    assert calls[:2] == [
        ["docker", "rm", "--force", "b" * 64],
        ["docker", "rm", "--force", "a" * 64],
    ]


def test_invalid_container_id_never_reaches_docker():
    with pytest.raises(module.ProofFailure):
        module.remove_owned(["unrelated-container"], lambda *args, **kwargs: pytest.fail("spawned"))


def test_failed_preflight_never_launches_specimen(tmp_path, monkeypatch):
    commit, tree = "c" * 40, "d" * 40
    calls = []

    def fake(args, **kwargs):
        calls.append(args)
        if args == ["git", "--no-optional-locks", "rev-parse", "HEAD"]:
            return commit
        if args == ["git", "--no-optional-locks", "status", "--porcelain"]:
            return ""
        if args == ["git", "--no-optional-locks", "rev-parse", "HEAD^{tree}"]:
            return tree
        if args[:3] == ["docker", "image", "inspect"]:
            return tree if "ocwp.source-tree" in args[4] else "sha256:" + "e" * 64
        if args[:2] == ["docker", "create"]:
            return "a" * 64
        if args[:2] == ["docker", "start"]:
            return ""
        if args[:2] == ["docker", "ps"]:
            return ""
        if args[:2] == ["docker", "exec"]:
            return "missing controller"
        raise AssertionError(args)

    monkeypatch.setattr(module, "run", fake)
    monkeypatch.setattr(module, "inspect_owned", lambda *args: None)
    cleaned = []
    monkeypatch.setattr(module, "remove_owned", lambda ids: cleaned.extend(ids))
    monkeypatch.setattr(
        module.subprocess, "Popen", lambda *a, **kw: pytest.fail("specimen spawned")
    )
    with pytest.raises(module.ProofFailure):
        module.supervise(
            "worker", "postgres", commit, tmp_path / "report.json", tmp_path / "owned.json"
        )
    assert cleaned == ["a" * 64]
    import json

    report = json.loads((tmp_path / "report.json").read_text())
    assert report["status"] == "failed"
    assert report["cleanup"] == "verified_absent"
    assert report["maximum_capacity_qualified"] is False


def test_bounded_client_rejects_output_overflow():
    import sys

    with pytest.raises(module.ProofFailure):
        module.run([sys.executable, "-c", 'print("x" * 17000)'])


def test_bounded_client_terminates_sleeping_process_group():
    import sys

    started = __import__("time").monotonic()
    with pytest.raises(module.ProofFailure):
        module.run([sys.executable, "-c", "import time; time.sleep(2)"], timeout=0.05)
    assert __import__("time").monotonic() - started < 1


def test_actual_shell_probe_delimiters(tmp_path):
    raw = probe()
    sections = __import__("re").split(r"\n---([a-z.]+)---\n", raw)
    (tmp_path / "cgroup").write_text("0::/\n")
    for key, value in zip(sections[1::2], sections[2::2], strict=True):
        (tmp_path / key).write_text(value + "\n")
    shell = module.PROBE.replace("/proc/self/cgroup", str(tmp_path / "cgroup")).replace(
        "/sys/fs/cgroup/", str(tmp_path) + "/"
    )
    result = module.run(["sh", "-c", shell])
    assert module.parse_probe(result, 512, 64)["cpu_usec"] == 100


def test_closed_micro_report_rejects_raw_proof_and_nonfinite_timings():
    import json

    record = dict(
        new_operations=3,
        revisions=2,
        decisions=1,
        lines_per_revision=4,
        lock_timeout_ms=15000,
        statement_timeout_ms=20000,
        maximum_capacity_qualified=False,
        process_cpu_seconds=0.1,
        operation_seconds={
            key: 0.1 for key in ("create", "revise", "decision", "fresh_load", "exact_retry")
        },
    )
    assert module.micro_result(json.dumps(record)) == record
    with pytest.raises(module.ProofFailure):
        module.micro_result(json.dumps(record | {"proof": "private"}))
    record["process_cpu_seconds"] = float("nan")
    with pytest.raises(module.ProofFailure):
        module.micro_result(json.dumps(record))


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "cleanup",
        "late_exit",
        "create_timeout",
        "mid_probe",
        "fixture_exit",
        "post_success_invalid",
    ],
)
@pytest.mark.parametrize("single_record", [False, True])
def test_supervisor_success_and_terminal_failures_are_closed(
    tmp_path, monkeypatch, fault, single_record
):
    import json
    from types import SimpleNamespace

    commit, tree = "c" * 40, "d" * 40
    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    containers = []
    calls = []
    specimens = []
    polls = []

    def popen(args, **kwargs):
        specimens.append(args)
        if fault == "late_exit":
            clock[0] = 21.0

        def poll():
            polls.append(1)
            return None if fault == "mid_probe" and len(polls) == 1 else 0

        return SimpleNamespace(poll=poll, returncode=1 if fault == "fixture_exit" else 0)

    monkeypatch.setattr(module.subprocess, "Popen", popen)
    micro = dict(
        new_operations=3,
        revisions=2,
        decisions=1,
        lines_per_revision=4,
        lock_timeout_ms=15000,
        statement_timeout_ms=20000,
        maximum_capacity_qualified=False,
        process_cpu_seconds=0.00001,
        operation_seconds={
            key: 0.1 for key in ("create", "revise", "decision", "fresh_load", "exact_retry")
        },
    )

    if single_record:
        micro = feasibility_result()

    def execute(args, **kwargs):
        calls.append(args)
        if args[:3] == ["git", "--no-optional-locks", "rev-parse"]:
            return commit if args[-1] == "HEAD" else tree
        if args[:3] == ["git", "--no-optional-locks", "status"]:
            return ""
        if args[:3] == ["docker", "image", "inspect"]:
            return tree if "ocwp.source-tree" in args[4] else "sha256:" + "e" * 64
        if args[:2] == ["docker", "create"]:
            cid = ("a" if not containers else "b") * 64
            containers.append(cid)
            Path(args[args.index("--cidfile") + 1]).write_text(cid)
            if fault == "create_timeout":
                raise module.ProofFailure("command_timeout")
            return cid
        if args[:2] == ["docker", "start"]:
            return ""
        if args[:2] == ["docker", "inspect"]:
            cid = args[-1]
            if "range .Mounts" in args[3]:
                return "tmpfs /tmp"
            label = next(
                row[row.index("--label") + 1].split("=")[1]
                for row in calls
                if row[:2] == ["docker", "create"]
            )
            network = "none" if cid == "a" * 64 else "container:" + "a" * 64
            return "|".join((cid, "sha256:" + "e" * 64, label, network, "false", "1", "true"))
        if args[:2] == ["docker", "exec"]:
            if args[3] == "pg_isready":
                return ""
            if args[3] == "cat":
                if args[-1] == "/tmp/quote-record-diagnostic.json":
                    return json.dumps(
                        dict(
                            stage="create_decode",
                            failure_type="request_error",
                            byte_counts=dict(raw_create_bytes=100),
                        )
                    )
                if fault == "post_success_invalid":
                    clock[0] = 21.0
                    return "{}"
                return json.dumps(micro)
            if fault == "mid_probe" and specimens:
                clock[0] = 21.0
            return (
                probe()
                if args[2] == "b" * 64
                or (
                    not specimens
                    and len(containers) == 1
                    and len([c for c in calls if c[:2] == ["docker", "create"]]) == 1
                )
                else probe()
                .replace("536870912", "805306368")
                .replace("---pids.max---\n64", "---pids.max---\n128")
            )
        if args[:2] == ["docker", "rm"]:
            if fault == "cleanup":
                raise module.ProofFailure("command_failed")
            containers.remove(args[-1])
            return ""
        if args[:2] == ["docker", "ps"]:
            return "\n".join(containers)
        raise AssertionError(args)

    def canary(cid, execute):
        containers.remove(cid)
        return {"cpu_usec": 100, "memory_peak": 8192}

    monkeypatch.setattr(module, "cancellation_canary", canary)
    monkeypatch.setattr(
        module,
        "effective_privileges",
        lambda *args: {"uid": 10001, "effective_capabilities": 0, "no_new_privileges": True},
    )
    monkeypatch.setattr(module, "reconcile_owned", lambda *args: list(containers))
    original_remove = module.remove_owned
    monkeypatch.setattr(module, "run", execute)
    monkeypatch.setattr(module, "remove_owned", lambda ids: original_remove(ids, execute))
    target = tmp_path / "report.json"
    if fault == "none":
        module.supervise(
            "worker",
            "postgres",
            commit,
            target,
            tmp_path / "owned.json",
            single_record=single_record,
        )
    else:
        with pytest.raises(module.ProofFailure):
            module.supervise(
                "worker",
                "postgres",
                commit,
                target,
                tmp_path / "owned.json",
                single_record=single_record,
            )
    report = json.loads(target.read_text())
    assert report["status"] == ("micro_passed_not_capacity" if fault == "none" else "failed")
    assert report["cleanup"] == (
        "failed" if fault in {"cleanup", "create_timeout"} else "verified_absent"
    )
    assert len(specimens) == (0 if fault == "create_timeout" else 1)
    if fault == "fixture_exit":
        assert report["client_returncode"] == 1
        if single_record:
            assert report["record_diagnostic"]["stage"] == "create_decode"
            assert report["failure_final_probe"] == "passed"
            assert set(report["failure_final_containers"]) == {"db", "worker"}
    if single_record and fault in {"late_exit", "mid_probe", "post_success_invalid"}:
        assert report["record_diagnostic"] == "unavailable_or_invalid"
        assert report["failure_final_probe"] == "wall_budget"
        assert not any(c[-1] == "/tmp/quote-record-diagnostic.json" for c in calls)
    if fault == "none":
        assert report["identities"][2]["network"] == "container:" + "a" * 64
        assert report["identities"][2]["memory_max"] == 536870912
        assert report["lifetime_cpu_usec"] == 200
        assert specimens[0][-1] == (
            "services/platform/tests/quotes/test_quote_record_feasibility_postgres.py"
            if single_record
            else "services/platform/tests/quotes/test_quote_capacity_micro_postgres.py"
        )


@pytest.mark.parametrize(
    "status",
    [
        "Uid:\t0 0 0 0\nCapEff:\t0000000000000000\nNoNewPrivs:\t1",
        "Uid:\t10001 10001 10001 10001\nCapEff:\t0000000000000001\nNoNewPrivs:\t1",
        "Uid:\t10001 10001 10001 10001\nCapEff:\t0000000000000000\nNoNewPrivs:\t0",
        "Uid:\t10002 10002 10002 10002\nCapEff:\t0000000000000000\nNoNewPrivs:\t1",
        "Uid:\t10001 10001 10001 10001",
    ],
)
def test_effective_privileges_fail_closed(status):
    with pytest.raises(module.ProofFailure):
        module.effective_privileges("a" * 64, True, lambda *a, **kw: status)


def test_effective_privileges_are_observed():
    result = module.effective_privileges(
        "a" * 64,
        True,
        lambda *a, **kw: "Uid:\t10001 10001 10001 10001\nCapEff:\t0000000000000000\nNoNewPrivs:\t1",
    )
    assert result == dict(uid=10001, effective_capabilities=0, no_new_privileges=True)


@pytest.mark.parametrize(
    "manifest",
    [
        {},
        {"token": False, "images": {}},
        {"token": "a" * 32, "images": {"db": "secret"}},
        [],
        {"token": "a" * 32, "images": {}, "extra": "private"},
    ],
)
def test_invalid_ownership_manifest_never_calls_docker(tmp_path, manifest):
    import json

    owned = tmp_path / "owned.json"
    owned.with_suffix(".owner.json").write_text(json.dumps(manifest))
    with pytest.raises(module.ProofFailure):
        module.reconcile_owned(owned, lambda *a, **kw: pytest.fail("docker called"))


def test_owner_discovery_checks_image_and_label_before_removal(tmp_path):
    import json

    owned = tmp_path / "owned.json"
    token, image = "a" * 32, "sha256:" + "b" * 64
    owned.with_suffix(".owner.json").write_text(
        json.dumps({"token": token, "images": dict(db=image, worker=image, canary=image)})
    )

    def execute(args, **kwargs):
        return "c" * 64 if args[1] == "ps" else f"{image}|{token}|/ocwp-quote-{token}-worker"

    assert module.reconcile_owned(owned, execute) == ["c" * 64]
    with pytest.raises(module.ProofFailure):
        module.reconcile_owned(owned, lambda args, **kw: "c" * 64 if args[1] == "ps" else "foreign")


@pytest.mark.parametrize(
    "tree,valid",
    [
        ("PID PPID\n10 1\n11 10\n12 11", True),
        ("PID PPID\n10 1\n11 1", False),
        ("PID PPID\n0 1\n1 0\n2 1", False),
        ("PID PPID\n10 1\n11 10\n12 11\n12 11", False),
        ("PID PPID\n10 1\nmalformed", False),
    ],
)
def test_canary_kills_client_then_requires_descendant_chain_and_removal(monkeypatch, tree, valid):
    from types import SimpleNamespace

    calls = []
    monkeypatch.setattr(
        module.subprocess,
        "Popen",
        lambda *a, **kw: SimpleNamespace(
            pid=123, wait=lambda **kw: calls.append("client_reaped"), poll=lambda: -9
        ),
    )
    monkeypatch.setattr(module.os, "killpg", lambda *args: calls.append("client_killed"))

    def execute(args, **kwargs):
        calls.append(args)
        if args[1] == "top":
            return tree
        return probe() if args[3:4] == ["sh"] else ""

    monkeypatch.setattr(module, "remove_owned", lambda ids, run: calls.append("container_removed"))
    if valid:
        assert module.cancellation_canary("a" * 64, execute)["observed_processes"] == 3
        assert calls.index("client_killed") < calls.index("container_removed")
    else:
        with pytest.raises(module.ProofFailure):
            module.cancellation_canary("a" * 64, execute)
        assert "container_removed" not in calls


def test_source_status_never_refreshes_large_index(tmp_path, monkeypatch):
    import os
    import subprocess

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True, timeout=3
        )

    git("init", "-q")
    for i in range(240):
        (tmp_path / f"fixture-{i:04d}.txt").write_text("tiny\n")
    git("add", ".")
    git("-c", "user.name=Codex", "-c", "user.email=codex@openai.com", "commit", "-qm", "fixture")
    for path in tmp_path.glob("fixture-*"):
        os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 1_000_000_000))
    index = tmp_path / ".git/index"
    before = index.read_bytes()
    assert len(before) > module.LIMIT
    monkeypatch.chdir(tmp_path)
    with pytest.raises(module.ProofFailure):
        module.run(["git", "status", "--porcelain"])
    assert index.read_bytes() == before
    # Failed optional refresh can leave a lock; readonly source checks must not need it.
    assert module.source_query("status") == ""
    assert index.read_bytes() == before
    (tmp_path / "fixture-0000.txt").write_text("changed\n")
    assert module.source_query("status")
    assert index.read_bytes() == before


def test_failed_client_retains_only_numeric_returncode():
    import sys

    with pytest.raises(module.ProofFailure) as error:
        module.run([sys.executable, "-c", 'import sys; print("private"); sys.exit(7)'])
    assert error.value.returncode == 7
    assert str(error.value) == "command_failed"


def test_source_failure_records_closed_stage_and_returncode(tmp_path, monkeypatch):
    import json

    def execute(args, **kwargs):
        if args == ["git", "--no-optional-locks", "rev-parse", "HEAD"]:
            return "c" * 40
        if args == ["git", "--no-optional-locks", "status", "--porcelain"]:
            raise module.ProofFailure("command_failed", returncode=-25)
        assert args[:2] == ["docker", "ps"]
        return ""

    monkeypatch.setattr(module, "run", execute)
    evidence = tmp_path / "evidence.json"
    with pytest.raises(module.ProofFailure, match="micro_unqualified"):
        module.supervise("worker", "pg", "c" * 40, evidence, tmp_path / "owned.json")
    result = json.loads(evidence.read_text())
    assert result["command_stage"] == "source_status"
    assert result["client_returncode"] == -25
    assert result["cleanup"] == "verified_absent"
    assert result["failure"] == "command_failed"


def feasibility_result():
    return dict(
        new_operations=2,
        revisions=1,
        decisions=1,
        lines_per_revision=100,
        lock_timeout_ms=15000,
        statement_timeout_ms=20000,
        maximum_capacity_qualified=False,
        process_cpu_seconds=0.00001,
        operation_seconds=dict(create=0.1, decision=0.1, fresh_load=0.1, exact_retry=0.1),
        record_feasibility=dict(
            target_edges=1000,
            labor_lines=80,
            discount_lines=10,
            tax_lines=10,
            approved_charges=80,
            discount_allocations=500,
            tax_targets=500,
            description_codepoints=500,
            description_utf8_bytes=500,
            note_codepoints=2000,
            note_utf8_bytes=2000,
            source_reference_codepoints=200,
            source_reference_utf8_bytes=200,
            subtotal_minor=800000,
            discount_minor=500,
            tax_minor=499500,
            total_minor=1299000,
            raw_create_bytes=100,
            raw_decision_bytes=100,
            revision_logical_bytes=200,
            decision_logical_bytes=200,
            two_record_history_bytes=403,
        ),
    )


def test_fixed_feasibility_schema_accepts_only_reviewed_specimen():
    import json

    result = feasibility_result()
    assert module.micro_result(json.dumps(result), single_record=True) == result


@pytest.mark.parametrize(
    "field,value",
    [
        ("target_edges", 999),
        ("raw_create_bytes", 131073),
        ("revision_logical_bytes", 262145),
        ("two_record_history_bytes", 404),
        ("raw_decision_bytes", True),
        ("unknown", 1),
    ],
)
def test_fixed_feasibility_metrics_fail_closed(field, value):
    import json

    result = feasibility_result()
    result["record_feasibility"][field] = value
    with pytest.raises(module.ProofFailure):
        module.micro_result(json.dumps(result), single_record=True)


def test_record_failure_diagnostic_is_closed():
    import json

    value = dict(
        stage="create_decode", failure_type="value_error", byte_counts=dict(raw_create_bytes=100)
    )
    assert module.record_diagnostic(json.dumps(value)) == value


@pytest.mark.parametrize(
    "change",
    [
        dict(stage="private input"),
        dict(failure_type="private exception"),
        dict(byte_counts={"proof": 100}),
        dict(byte_counts={"raw_create_bytes": True}),
        dict(byte_counts={"raw_create_bytes": -1}),
        dict(exception="private"),
    ],
)
def test_record_failure_diagnostic_refuses_unclosed_fields(change):
    import json

    value = dict(stage="create_decode", failure_type="value_error", byte_counts={}) | change
    with pytest.raises(module.ProofFailure):
        module.record_diagnostic(json.dumps(value))


@pytest.mark.parametrize("memory_mib", [768, 1024, 2048])
def test_full_postgres_inspection_accepts_only_fixed_one_gib(memory_mib):
    import json

    value = full_inspect_value()
    value["user"] = "postgres"
    value["host"].update(
        Memory=memory_mib * 1024 * 1024,
        MemorySwap=memory_mib * 1024 * 1024,
        PidsLimit=128,
        Tmpfs=module.FULL_TMPFS["db"],
    )

    def execute(*args, **kwargs):
        return json.dumps(value)

    if memory_mib == 1024:
        module.full_inspect("a" * 64, "sha256:" + "b" * 64, "c" * 32, "none", "db", execute)
    else:
        with pytest.raises(module.ProofFailure, match="container_boundary"):
            module.full_inspect("a" * 64, "sha256:" + "b" * 64, "c" * 32, "none", "db", execute)


def test_full_postgres_storage_budget_preserves_other_containment():
    from scripts.ci.verify_v01 import FULL_POLICY

    assert module.FULL_TMPFS["db"]["/var/lib/postgresql"] == (
        "rw,noexec,nosuid,nodev,size=512m,nr_inodes=32768,mode=1777"
    )
    assert FULL_POLICY["postgres_tmpfs_bytes"] == [67108864, 536870912, 16777216]
    assert FULL_POLICY["postgres_memory_mib"] == 1024
    assert FULL_POLICY["worker_memory_mib"] == 768
    assert FULL_POLICY["workload_seconds"] == module.FULL_SECONDS == 900
    assert FULL_POLICY["postgres_cpu"] == FULL_POLICY["worker_cpu"] == 1


def test_full_postgres_checkpoint_trigger_leaves_microfixture_unchanged():
    import inspect

    from scripts.ci.verify_v01 import FULL_POLICY, FULL_POSTGRES_SETTINGS

    assert FULL_POSTGRES_SETTINGS == {
        "max_wal_size": "128MB",
        "min_wal_size": "80MB",
        "checkpoint_timeout": "5min",
        "checkpoint_completion_target": "0.9",
        "fsync": "on",
        "full_page_writes": "on",
        "synchronous_commit": "on",
        "wal_level": "replica",
    }
    assert FULL_POLICY["postgres_wal_checkpoint_trigger_mib"] == 128
    assert '"max_wal_size=" + FULL_POSTGRES_SETTINGS["max_wal_size"]' in inspect.getsource(
        module.supervise_python
    )
    assert "max_wal_size" not in inspect.getsource(module.supervise)


@pytest.mark.parametrize(
    "raw", ["", "private text", "1|2|3|4\n5|6", "4096|100|101|20\n1|2", "4096|100|80|20\n1|-2"]
)
def test_postgres_storage_diagnostic_rejects_untrusted_or_invalid_scalars(raw):
    with pytest.raises((module.ProofFailure, ValueError)):
        module.full_postgres_storage("a" * 64, lambda *args, **kwargs: raw)


def test_postgres_storage_diagnostic_is_fixed_bounded_and_nonqualifying():
    calls = []

    def execute(args, **kwargs):
        calls.append((args, kwargs))
        return "4096|131072|100000|12345\n33554432|83886080\n"

    observed = module.full_postgres_storage("a" * 64, execute)
    assert observed == {
        "status": "captured",
        "phase": "post_worker_stop",
        "atomic": False,
        "qualification": "not_a_receipt",
        "data_mount_bytes": 536870912,
        "data_mount_free_bytes": 409600000,
        "data_mount_free_inodes": 12345,
        "database_bytes": 33554432,
        "wal_bytes": 83886080,
    }
    assert calls[0][1] == {"timeout": 3, "limit": module.LIMIT}
    assert calls[0][0][:5] == ["docker", "exec", "a" * 64, "sh", "-c"]
    assert "pg_ls_waldir" in calls[0][0][-1]
    assert "CHECKPOINT" not in calls[0][0][-1] and "VACUUM" not in calls[0][0][-1]


@pytest.mark.parametrize("oversized", [False, True])
def test_postgres_storage_diagnostic_composes_with_real_client(monkeypatch, oversized):
    from types import SimpleNamespace

    events = []
    raw = b"4096|131072|100000|12345\n33554432|83886080"
    if oversized:
        raw += b"0" * 1024

    def launch(args, **kwargs):
        events.append("spawn")
        assert args[:5] == ["docker", "exec", "a" * 64, "sh", "-c"]
        kwargs["stdout"].write(raw)
        kwargs["stdout"].flush()
        return SimpleNamespace(
            returncode=0, poll=lambda: 0, wait=lambda **kwargs: events.append("reap")
        )

    monkeypatch.setattr(module.subprocess, "Popen", launch)
    if oversized:
        with pytest.raises(module.ProofFailure, match="storage_diagnostic_size"):
            module.full_postgres_storage("a" * 64, module.full_client)
    else:
        assert module.full_postgres_storage("a" * 64, module.full_client)["status"] == "captured"
    assert events == ["spawn", "reap"]


def test_memory_observation_keeps_pressure_without_weakening_qualification():
    raw = probe().replace("oom 0\noom_kill 0\nmax 0", "oom 2\noom_kill 1\nmax 9")
    assert module.full_memory_observation(raw) == {
        "memory_current_bytes": 4096,
        "memory_peak_bytes": 8192,
        "memory_max_bytes": 536870912,
        "memory_events": {"max": 9, "oom": 2, "oom_kill": 1},
    }
    with pytest.raises(module.ProofFailure, match="resource_pressure"):
        module.parse_probe(raw, 512, 64)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "private output",
        probe().replace("0::/", "0::/private"),
        probe().replace("oom 0", "oom -1"),
        probe().replace("oom 0", "oom 0\noom 0"),
        probe().replace("oom_kill 0", "missing 0"),
        probe().replace("oom_kill 0", "oom_kill 0 private"),
        probe().replace("8192", str(2**64)),
        probe().replace("4096", "-1"),
        probe().replace("536870912", "max"),
        probe() + "x" * module.LIMIT,
    ],
    ids=[
        "empty",
        "private",
        "wrong_cgroup",
        "negative_event",
        "duplicate_event",
        "missing_event",
        "malformed_event",
        "overflow",
        "negative_current",
        "non_numeric_max",
        "oversized",
    ],
)
def test_memory_observation_rejects_malformed_or_unbounded_values(raw):
    with pytest.raises(ValueError):
        module.full_memory_observation(raw)


@pytest.mark.parametrize(
    "role,memory_mib,swap_mib",
    [
        ("worker", 768, 768),
        ("worker", 512, 512),
        ("worker", 1024, 1024),
        ("worker", 768, 512),
        ("worker", 768, 1024),
        ("canary", 512, 512),
        ("canary", 768, 768),
        ("db", 1024, 1024),
        ("db", 768, 768),
    ],
)
def test_full_worker_budget_inspection_is_role_specific(role, memory_mib, swap_mib):
    import json

    value = full_inspect_value()
    value["host"].update(Memory=memory_mib * 1024**2, MemorySwap=swap_mib * 1024**2)
    if role == "db":
        value["user"] = "postgres"
        value["host"].update(PidsLimit=128, Tmpfs=module.FULL_TMPFS["db"])
    expected = {"canary": 512, "db": 1024, "worker": 768}[role]

    def execute(*args, **kwargs):
        return json.dumps(value)

    if memory_mib == swap_mib == expected:
        module.full_inspect("a" * 64, "sha256:" + "b" * 64, "c" * 32, "none", role, execute)
    else:
        with pytest.raises(module.ProofFailure, match="container_boundary"):
            module.full_inspect("a" * 64, "sha256:" + "b" * 64, "c" * 32, "none", role, execute)


@pytest.mark.parametrize("memory_mib", [512, 768, 1024])
def test_full_worker_budget_cgroup_probe_is_exact(memory_mib):
    assert module.full_role_limits("worker") == (768, 64)
    assert module.full_role_limits("canary") == (512, 64)
    assert module.full_role_limits("db") == (1024, 128)
    raw = probe().replace("536870912", str(memory_mib * 1024**2))
    if memory_mib == 768:
        assert module.parse_probe(raw, *module.full_role_limits("worker"))["memory_peak"] == 8192
    else:
        with pytest.raises(module.ProofFailure, match="limits_not_enforced"):
            module.parse_probe(raw, *module.full_role_limits("worker"))


def test_full_role_limits_reject_unknown_role():
    with pytest.raises(module.ProofFailure, match="container_role"):
        module.full_role_limits("other")
