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


# The service guard delta below is authored but unexecuted. Run only in the
# separately reviewed bootstrap container, never via the service business mode.
def postgres_identity(node, index=0, revision="0013"):
    schema = "ocwp_identity_migration_" + f"{index:032x}"
    return dict(
        node=node,
        dialect="postgresql",
        driver="psycopg",
        driver_version="3.3.4",
        database="ocwp_quote_micro_test",
        schema=schema,
        search_path=schema,
        server_version_num=180004,
        server_encoding="UTF8",
        client_encoding="UTF8",
        schema_revision=revision,
        probe_connection_closed=True,
    )


def postgres_receipt(node, index=0):
    return postgres_identity(node, index) | {
        "upgrade_revisions": list(module.SERVICE_REVISIONS[module.SERVICE_NODES.index(node)])
    }


def service_items():
    from types import SimpleNamespace

    return [
        SimpleNamespace(
            nodeid=node,
            path=PATH.parents[2] / node.split("::")[0],
            originalname=node.split("::")[1].removesuffix("[postgres]"),
            callspec=SimpleNamespace(params={"identity_migration_database": "postgres"}),
        )
        for node in module.SERVICE_NODES
    ]


def service_report():
    return dict(
        schema=1,
        nodes=list(module.SERVICE_NODES),
        postgres_identities=[
            postgres_receipt(node, index) for index, node in enumerate(module.SERVICE_NODES)
        ],
        collection_count=4,
        collection_errors=0,
        unhandled_errors=0,
        protocol_errors=0,
        session_finished=True,
        session_exitstatus=0,
        reports=[
            dict(node=node, when=when, outcome="passed", seconds=0.001)
            for node in module.SERVICE_NODES
            for when in ("setup", "call", "teardown")
        ],
    )


def test_service_selection_is_closed_and_environment_is_empty(monkeypatch):
    monkeypatch.setenv("OCWP_TEST_DATABASE_URL", "untrusted")
    monkeypatch.setenv("PGHOST", "untrusted.invalid")
    args = module.service_argv("a" * 64)
    assert args[:5] == ["docker", "exec", "a" * 64, "env", "-i"]
    assert args[-4:] == list(module.SERVICE_NODES)
    assert len(set(args[-4:])) == 4
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1" in args
    assert "--maxfail=1" in args and "--capture=fd" in args and "addopts=" in args
    assert "no:cacheprovider" in args and "scripts.ci.quote_capacity_micro" in args
    assert "--tb=short" in args and "--no-showlocals" in args
    assert "--show-capture=no" in args and "--tb=no" not in args
    assert [arg for arg in args if arg.startswith("OCWP_TEST_DATABASE_URL=")] == [
        "OCWP_TEST_DATABASE_URL=postgresql+psycopg://ocwp:ocwp-synthetic"
        "@127.0.0.1:5432/ocwp_quote_micro_test"
    ]
    assert not any(
        any(value in arg for value in ("PASSWORD", "PYTEST_ADDOPTS", "PGHOST"))
        or "untrusted" in arg
        for arg in args
    )
    with pytest.raises(module.ProofFailure):
        module.service_argv("arbitrary-name")


def test_service_report_requires_every_protocol_and_finish():
    import copy
    import json

    good = service_report()
    assert module.service_result(json.dumps(good)) == good
    for field, wrong in (
        ("schema", True),
        ("collection_count", 3),
        ("collection_errors", 1),
        ("unhandled_errors", 1),
        ("protocol_errors", 1),
        ("session_finished", False),
        ("session_exitstatus", 1),
    ):
        with pytest.raises(module.ProofFailure):
            module.service_result(json.dumps(good | {field: wrong}))
    for index in (0, 1, 2):
        for outcome in ("failed", "skipped", "xfailed", "xpassed"):
            bad = copy.deepcopy(good)
            bad["reports"][index]["outcome"] = outcome
            with pytest.raises(module.ProofFailure):
                module.service_result(json.dumps(bad))
    for rows in (
        good["reports"][:-1],
        [*good["reports"], good["reports"][0]],
        [good["reports"][0], good["reports"][0], *good["reports"][2:]],
        good["reports"][::3],
        list(reversed(good["reports"])),
    ):
        with pytest.raises(module.ProofFailure):
            module.service_result(json.dumps(good | {"reports": rows}))
    for nodes in (good["nodes"][:-1], list(reversed(good["nodes"])), [good["nodes"][0]] * 4):
        with pytest.raises(module.ProofFailure):
            module.service_result(json.dumps(good | {"nodes": nodes}))


def test_service_report_rejects_duplicate_unknown_nonfinite_and_oversize_fields():
    import copy
    import json

    good = service_report()
    raw = json.dumps(good)
    for bad in (
        raw.replace('"schema": 1', '"schema": 1, "schema": 1'),
        raw.replace('"seconds": 0.001', '"seconds": 0.001, "seconds": 0.001', 1),
        json.dumps(good | {"raw_error": "private"}),
        " " * module.LIMIT,
    ):
        with pytest.raises((module.ProofFailure, ValueError)):
            module.service_result(bad)
    for seconds in (True, -1, 20, float("nan"), float("inf"), -float("inf")):
        bad = copy.deepcopy(good)
        bad["reports"][0]["seconds"] = seconds
        with pytest.raises(module.ProofFailure):
            module.service_result(json.dumps(bad))
    for field in ("captured", "longrepr", "wasxfail"):
        bad = copy.deepcopy(good)
        bad["reports"][0][field] = "private"
        with pytest.raises(module.ProofFailure):
            module.service_result(json.dumps(bad))


def test_service_hook_refuses_collection_mismatch_before_fixtures():
    from types import SimpleNamespace

    good = service_items()
    hook = module.ServiceReportHook()
    hook.pytest_collection_finish(SimpleNamespace(items=good))
    assert hook.value["nodes"] == list(module.SERVICE_NODES)
    for bad in (good[:-1], list(reversed(good)), good[:1] * 4, good + good[:1]):
        hook = module.ServiceReportHook()
        with pytest.raises(pytest.UsageError, match="service_selection"):
            hook.pytest_collection_finish(SimpleNamespace(items=bad))
        assert hook.value["protocol_errors"] == 1
        assert hook.value["nodes"] == []


@pytest.mark.parametrize(
    "fault", ["path", "name", "missing_callspec", "extra", "missing", "sqlite", "bool", "type"]
)
def test_postgres_collection_rejects_wrong_source_or_actual_parameters(fault):
    from types import SimpleNamespace

    items = service_items()
    item = items[0]
    if fault == "path":
        item.path = PATH
    elif fault == "name":
        item.originalname = "test_substituted"
    elif fault == "missing_callspec":
        del item.callspec
    elif fault == "extra":
        item.callspec.params["other"] = 0
    elif fault == "missing":
        item.callspec.params = {}
    elif fault == "sqlite":
        item.callspec.params["identity_migration_database"] = "sqlite"
    elif fault == "bool":
        item.callspec.params["identity_migration_database"] = True
    elif fault == "type":
        item.callspec.params = []
    hook = module.ServiceReportHook()
    with pytest.raises(pytest.UsageError, match="service_selection"):
        hook.pytest_collection_finish(SimpleNamespace(items=items))
    assert hook.value["protocol_errors"] == 1
    assert hook.value["nodes"] == []


def test_postgres_report_requires_exact_closed_ordered_distinct_identities():
    import copy
    import json

    good = service_report()
    identities = good["postgres_identities"]
    for wrong in (None, identities[:-1], identities + identities[:1], list(reversed(identities))):
        with pytest.raises(module.ProofFailure):
            module.service_result(json.dumps(good | {"postgres_identities": wrong}))
    for change in (
        {"node": module.SERVICE_NODES[1]},
        {"dialect": "sqlite"},
        {"driver": "psycopg2"},
        {"driver_version": "3.3.3"},
        {"database": "other_test"},
        {"schema": "public", "search_path": "public"},
        {"search_path": "pg_catalog"},
        {"server_version_num": 180003},
        {"server_version_num": True},
        {"server_encoding": "LATIN1"},
        {"client_encoding": "LATIN1"},
        {"schema_revision": "0012"},
        {"probe_connection_closed": False},
        {"probe_connection_closed": 1},
        {"upgrade_revisions": ["0013"]},
        {"upgrade_revisions": ["0013", "0012"]},
        {"upgrade_revisions": ["0012", "0013", "0013"]},
        {"upgrade_revisions": [12, 13]},
        {"upgrade_revisions": None},
        {"url": "private"},
    ):
        bad = copy.deepcopy(good)
        bad["postgres_identities"][0].update(change)
        with pytest.raises(module.ProofFailure):
            module.service_result(json.dumps(bad))
    for field in identities[0]:
        bad = copy.deepcopy(good)
        del bad["postgres_identities"][0][field]
        with pytest.raises(module.ProofFailure):
            module.service_result(json.dumps(bad))
    bad = copy.deepcopy(good)
    for field in ("schema", "search_path"):
        bad["postgres_identities"][1][field] = bad["postgres_identities"][0][field]
    with pytest.raises(module.ProofFailure):
        module.service_result(json.dumps(bad))


def test_postgres_report_fits_unchanged_cap_and_refuses_exact_limit():
    import json

    good = service_report()
    raw = json.dumps(good, sort_keys=True, allow_nan=False)
    assert module.service_result(raw + " " * (module.LIMIT - len(raw) - 1)) == good
    with pytest.raises(module.ProofFailure, match="service_report_limit"):
        module.service_result(raw + " " * (module.LIMIT - len(raw)))
    # All four exact IDs exceed the prior pure-only 128-byte allowance.
    assert all(128 < len(node) <= 155 for node in module.SERVICE_NODES)
    upper = good | {
        "reports": [
            dict(node=row["node"], when="teardown", outcome="passed", seconds="x" * 32)
            for row in good["reports"]
        ],
    }
    assert len(json.dumps(upper, sort_keys=True, allow_nan=False).encode("ascii")) < 8 * 1024
    assert module.LIMIT == 16 * 1024
    assert module.STATIC_FAILURE_LIMIT == 24 * 1024
    assert module.SERVICE_OUTPUT_LIMIT == 32 * 1024


def test_service_hook_only_retains_closed_bounded_fields(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace

    hook = module.ServiceReportHook()
    hook.pytest_collection_finish(SimpleNamespace(items=service_items()))
    good = service_report()
    for row in good["reports"]:
        identity = good["postgres_identities"][module.SERVICE_NODES.index(row["node"])]
        hook.pytest_runtest_logreport(
            SimpleNamespace(
                nodeid=row["node"],
                when=row["when"],
                outcome=row["outcome"],
                duration=row["seconds"],
                user_properties=[("ocwp_postgres_identity", identity)],
                longrepr="private",
                capstdout="private",
            )
        )
    target = tmp_path / "closed.json"
    monkeypatch.setattr(module, "SERVICE_REPORT", str(target))
    hook.pytest_sessionfinish(SimpleNamespace(), 0)
    assert module.service_result(target.read_text()) == good
    assert "private" not in target.read_text()
    assert len(target.read_bytes()) < module.LIMIT
    for change in (
        {"nodeid": "private"},
        {"when": "private"},
        {"duration": float("nan")},
        {"wasxfail": "private"},
    ):
        hook.pytest_runtest_logreport(
            SimpleNamespace(
                **(
                    dict(
                        nodeid=module.SERVICE_NODES[0], when="call", outcome="passed", duration=0.1
                    )
                    | change
                )
            )
        )
    hook.pytest_collectreport(SimpleNamespace(outcome="failed", longrepr="private"))
    hook.pytest_collectreport(SimpleNamespace(outcome="skipped", longrepr="private"))
    hook.pytest_internalerror()
    hook.pytest_keyboard_interrupt()
    hook.pytest_sessionfinish(SimpleNamespace(), 1)
    result = json.loads(target.read_text())
    assert result["protocol_errors"] == 4
    assert result["collection_errors"] == result["unhandled_errors"] == 2
    assert len(result["reports"]) == 12
    assert "private" not in target.read_text()
    with pytest.raises(module.ProofFailure):
        module.service_result(target.read_text())


@pytest.mark.parametrize("fault", ["missing", "duplicate", "name", "foreign", "extra", "repeat"])
def test_postgres_hook_rejects_bad_teardown_properties(fault):
    from types import SimpleNamespace

    node = module.SERVICE_NODES[0]
    pair = ("ocwp_postgres_identity", postgres_receipt(node))
    properties = [pair]
    if fault == "missing":
        properties = []
    elif fault == "duplicate":
        properties = [pair, pair]
    elif fault == "name":
        properties = [("other", pair[1])]
    elif fault == "foreign":
        properties = [(pair[0], postgres_receipt(module.SERVICE_NODES[1]))]
    elif fault == "extra":
        properties = [(pair[0], pair[1] | {"payload": "private"})]
    hook = module.ServiceReportHook()
    hook.pytest_collection_finish(SimpleNamespace(items=service_items()))
    row = SimpleNamespace(
        nodeid=node, when="teardown", outcome="failed", duration=0.1, user_properties=properties
    )
    hook.pytest_runtest_logreport(row)
    if fault == "repeat":
        hook.pytest_runtest_logreport(row)
    assert hook.value["protocol_errors"] == 1
    assert hook.failure_stage == 4


@pytest.mark.parametrize("index", range(4))
def test_postgres_observer_never_migrates_and_preserves_forwarding(index, monkeypatch):
    import sys
    from types import SimpleNamespace

    node = module.SERVICE_NODES[index]
    config, engine, result = object(), object(), object()
    request = SimpleNamespace(node=SimpleNamespace(nodeid=node, user_properties=[]))
    calls, probes = [], []
    committed = [None]

    def upgrade(*args, **kwargs):
        calls.append((args, kwargs))
        committed[0] = "0013" if args[1] == "head" else args[1]
        return result

    command = SimpleNamespace(upgrade=upgrade)
    monkeypatch.setitem(sys.modules, "alembic", SimpleNamespace(command=command))

    def observe(actual_engine, actual_node):
        assert actual_engine is engine and actual_node == node
        assert committed[0] is not None
        probes.append(committed[0])
        return postgres_identity(node, index, committed[0])

    monkeypatch.setattr(module, "probe_postgres_identity", observe)
    fixture = module.observe_postgres((config, engine), request, monkeypatch)
    next(fixture)
    assert calls == probes == []
    revisions = module.SERVICE_REVISIONS[index]
    requested = ["0012", "head"] if len(revisions) == 2 else ["head"]
    for revision in requested:
        assert command.upgrade(config, revision, sql=False, tag="synthetic") is result
        assert len(probes) == len(calls)
    with pytest.raises(StopIteration):
        next(fixture)
    assert calls == [
        ((config, revision), {"sql": False, "tag": "synthetic"}) for revision in requested
    ]
    assert probes == [*revisions, "0013"]
    assert request.node.user_properties == [
        ("ocwp_postgres_identity", postgres_receipt(node, index))
    ]


def test_postgres_observer_propagates_original_exception_without_probe(monkeypatch):
    import sys
    from types import SimpleNamespace

    failure = RuntimeError("synthetic original")
    config, engine = object(), object()
    calls = []

    def upgrade(*args, **kwargs):
        calls.append((args, kwargs))
        raise failure

    command = SimpleNamespace(upgrade=upgrade)
    monkeypatch.setitem(sys.modules, "alembic", SimpleNamespace(command=command))
    monkeypatch.setattr(
        module, "probe_postgres_identity", lambda *_: pytest.fail("probe after failed upgrade")
    )
    request = SimpleNamespace(
        node=SimpleNamespace(nodeid=module.SERVICE_NODES[1], user_properties=[])
    )
    fixture = module.observe_postgres((config, engine), request, monkeypatch)
    next(fixture)
    with pytest.raises(RuntimeError) as caught:
        command.upgrade(config=config, revision="head", sql=False)
    assert caught.value is failure
    with pytest.raises(module.ProofFailure, match="service_postgres_chronology"):
        command.upgrade(config, "head")
    assert calls == [((), {"config": config, "revision": "head", "sql": False})]
    fixture.close()
    assert request.node.user_properties == []


@pytest.mark.parametrize("fault", ["foreign", "extra", "missing", "revision", "schema", "final"])
def test_postgres_observer_refuses_wrong_chronology_or_target(fault, monkeypatch):
    import sys
    from types import SimpleNamespace

    node = module.SERVICE_NODES[1]
    config, engine = object(), object()
    calls = []
    command = SimpleNamespace(upgrade=lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setitem(sys.modules, "alembic", SimpleNamespace(command=command))
    probes = [postgres_identity(node), postgres_identity(node)]
    if fault == "revision":
        probes[0]["schema_revision"] = "0012"
    elif fault == "schema":
        probes[1] = postgres_identity(node, 1)
    elif fault == "final":
        probes[1]["schema_revision"] = "0012"
    monkeypatch.setattr(module, "probe_postgres_identity", lambda *_: probes.pop(0))
    request = SimpleNamespace(node=SimpleNamespace(nodeid=node, user_properties=[]))
    fixture = module.observe_postgres((config, engine), request, monkeypatch)
    next(fixture)
    with pytest.raises(module.ProofFailure):
        if fault == "foreign":
            command.upgrade(object(), "head")
        elif fault == "missing":
            next(fixture)
        else:
            command.upgrade(config, "head")
            if fault == "extra":
                command.upgrade(config, "head")
            else:
                next(fixture)
    assert len(calls) == (0 if fault in {"foreign", "missing"} else 1)
    fixture.close()
    assert request.node.user_properties == []


@pytest.mark.parametrize("failure", [False, True])
def test_postgres_probe_closes_its_independent_connection(failure, monkeypatch):
    import sys
    from types import SimpleNamespace

    class DriverConnection:
        pass

    closed = []

    class Connection:
        def __init__(self):
            self.closed = False
            self.connection = SimpleNamespace(driver_connection=DriverConnection())

        def __enter__(self):
            assert not self.closed
            return self

        def __exit__(self, *_):
            self.closed = True
            closed.append(True)

        def execute(self, _statement):
            if failure:
                raise RuntimeError("synthetic query failure")
            return SimpleNamespace(
                one=lambda: (
                    "ocwp_quote_micro_test",
                    "ocwp_identity_migration_" + "0" * 32,
                    "ocwp_identity_migration_" + "0" * 32,
                    180004,
                    "UTF8",
                    "UTF8",
                    "0013",
                )
            )

    monkeypatch.setitem(
        sys.modules, "psycopg", SimpleNamespace(Connection=DriverConnection, __version__="3.3.4")
    )
    monkeypatch.setitem(
        sys.modules, "sqlalchemy", SimpleNamespace(text=lambda statement: statement)
    )
    engine = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql", driver="psycopg"), connect=Connection
    )
    node = module.SERVICE_NODES[0]
    if failure:
        with pytest.raises(RuntimeError, match="synthetic query failure"):
            module.probe_postgres_identity(engine, node)
    else:
        assert module.probe_postgres_identity(engine, node) == postgres_identity(node)
    assert closed == [True]


def test_service_hook_requires_explicit_contained_context(monkeypatch):
    from types import SimpleNamespace

    calls = []
    config = SimpleNamespace(
        pluginmanager=SimpleNamespace(register=lambda *args: calls.append(args))
    )
    monkeypatch.delenv("OCWP_QUOTE_SERVICE_INITIAL", raising=False)
    with pytest.raises(module.ProofFailure, match="service_hook_context"):
        module.pytest_configure(config)
    assert calls == []
    monkeypatch.setenv("OCWP_QUOTE_SERVICE_INITIAL", "contained")
    module.pytest_configure(config)
    assert len(calls) == 2 and isinstance(calls[0][0], module.ServiceReportHook)
    assert calls[1][1] == "quote-postgres-observer"


def test_service_cancellation_signals_both_before_stopped_state_readback():
    calls = []
    ids = ["a" * 64, "b" * 64]

    def execute(args, **kwargs):
        calls.append((args, kwargs))
        if args[1] == "kill":
            raise module.ProofFailure("command_failed")
        return "\n".join(f"{cid}|false" for cid in reversed(ids))

    module.cancel_runtime(ids, execute)
    assert calls[0][0] == ["docker", "kill", "--signal", "KILL", *reversed(ids)]
    assert calls[0][1]["timeout"] == 2
    assert calls[1][0][1] == "inspect" and calls[1][1]["timeout"] == 3
    for answer in (
        "",
        f"{ids[1]}|true\n{ids[0]}|false",
        f"{ids[1]}|false",
        f"{ids[0]}|false\n{ids[1]}|false",
    ):
        with pytest.raises(module.ProofFailure):
            module.cancel_runtime(ids, lambda *args, answer=answer, **kwargs: answer)
    for bad in ([], ["foreign"], [*ids, "c" * 64], [ids[0], ids[0]]):
        with pytest.raises(module.ProofFailure):
            module.cancel_runtime(bad, lambda *a, **kw: pytest.fail("docker called"))


def test_service_inspection_inherits_the_stage_executor():
    calls = []
    cid, image, token = "a" * 64, "sha256:" + "b" * 64, "c" * 32

    def execute(args, **kwargs):
        calls.append(args)
        return (
            "tmpfs /tmp"
            if "range .Mounts" in args[3]
            else "|".join((cid, image, token, "none", "false", "1", "true"))
        )

    module.inspect_owned(cid, image, token, "none", execute)
    assert len(calls) == 2
    with pytest.raises(module.ProofFailure, match="wall_budget"):
        module.inspect_owned(
            cid,
            image,
            token,
            "none",
            lambda *a, **kw: (_ for _ in ()).throw(module.ProofFailure("wall_budget")),
        )


def test_service_bounded_client_cancels_before_reap_and_respects_reap_deadline(monkeypatch):
    from types import SimpleNamespace

    calls = []
    clock = [0.0]
    child = SimpleNamespace(pid=123, returncode=None, poll=lambda: None)

    def wait(*, timeout):
        calls.append(("wait", timeout))
        raise module.subprocess.TimeoutExpired("synthetic", timeout)

    child.wait = wait
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(module.time, "sleep", lambda seconds: clock.__setitem__(0, 1.0))
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **kw: child)
    monkeypatch.setattr(module.os, "killpg", lambda *a: calls.append("client_kill"))
    with pytest.raises(module.ProofFailure, match="client_reap_unverified"):
        module.run(
            ["synthetic"],
            timeout=0.1,
            deadline=0.1,
            before_reap=lambda: calls.append("container_kill"),
        )
    assert calls == ["container_kill", "client_kill", ("wait", 0)]


def test_service_mode_conflict_refuses_before_tools(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "run", lambda *a, **kw: pytest.fail("tool called"))
    with pytest.raises(module.ProofFailure, match="mode_conflict"):
        module.supervise(
            "worker",
            "pg",
            "c" * 40,
            tmp_path / "report.json",
            tmp_path / "owned.json",
            single_record=True,
            service_initial=True,
        )


def test_service_supervisor_closed_scenarios(tmp_path, monkeypatch):
    """Finite mocked paths. No Docker, business imports or DB setup."""
    import json
    from contextlib import contextmanager
    from types import SimpleNamespace

    scenarios = (
        "success",
        "source",
        "preflight",
        "setup_deadline",
        "fixture_exit",
        "workload_deadline",
        "mid_probe",
        "final_deadline",
        "invalid_report",
        "cancellation_unknown",
        "cleanup",
        "create_timeout",
        "diagnostic_missing",
        "diagnostic_duplicate",
        "diagnostic_invalid",
        "diagnostic_parser_error",
        "diagnostic_exact_limit",
        "diagnostic_truncated",
        "client_reap_unknown",
        "output_limit",
    )
    for fault in scenarios:
        with monkeypatch.context() as patch:
            folder = tmp_path / fault
            folder.mkdir()
            clock, calls, containers, launches = [0.0], [], {}, []
            commit, tree, image = "c" * 40, "d" * 40, "sha256:" + "e" * 64
            patch.setattr(module.time, "monotonic", lambda clock=clock: clock[0])
            patch.setattr(module.time, "sleep", lambda seconds: None)
            patch.setattr(
                module.os, "killpg", lambda *a, calls=calls: calls.append(["client_kill"])
            )
            patch.setattr(module.signal, "signal", lambda *a: None)
            temporary_file = module.tempfile.TemporaryFile

            @contextmanager
            def traced_spool(*, temporary_file=temporary_file, calls=calls):
                with temporary_file() as output:

                    def read(limit):
                        calls.append(["spool_read"])
                        assert limit == module.SERVICE_OUTPUT_LIMIT
                        return output.read(limit)

                    yield SimpleNamespace(
                        fileno=output.fileno,
                        write=output.write,
                        flush=output.flush,
                        seek=output.seek,
                        read=read,
                    )

            patch.setattr(module.tempfile, "TemporaryFile", traced_spool)

            def popen(args, *, launches=launches, fault=fault, calls=calls, clock=clock, **kwargs):
                assert kwargs["preexec_fn"] is module.service_output_limit
                launches.append(args)
                child = SimpleNamespace(pid=123, returncode=0)
                active = fault in {
                    "workload_deadline",
                    "mid_probe",
                    "cancellation_unknown",
                    "client_reap_unknown",
                }
                failed = fault == "fixture_exit" or fault.startswith("diagnostic_")
                child.returncode = None if active else (4 if failed else 0)
                child.poll = lambda: child.returncode
                marker = service_failure_marker()
                if fault == "diagnostic_missing":
                    marker = b""
                elif fault == "diagnostic_duplicate":
                    marker *= 2
                elif fault == "diagnostic_invalid":
                    marker = marker.replace(b'"stage":1', b'"stage":"private"')
                output = b"private\xff\n" + marker
                if fault == "output_limit":
                    output = b"x" * module.SERVICE_OUTPUT_LIMIT
                elif fault == "diagnostic_exact_limit":
                    output += b"x" * (module.LIMIT - len(output))
                elif fault == "diagnostic_truncated":
                    output += b"x" * module.LIMIT
                kwargs["stdout"].write(output)
                kwargs["stdout"].flush()

                def wait(*, timeout):
                    calls.append(["client_wait"])
                    if fault == "client_reap_unknown":
                        raise module.subprocess.TimeoutExpired("synthetic", timeout)
                    child.returncode = -9
                    return -9

                child.wait = wait
                if fault in {"workload_deadline", "client_reap_unknown"}:
                    clock[0] = 21.0
                return child

            patch.setattr(module.subprocess, "Popen", popen)

            def execute(
                args,
                *,
                calls=calls,
                fault=fault,
                commit=commit,
                tree=tree,
                image=image,
                containers=containers,
                launches=launches,
                clock=clock,
                **kwargs,
            ):
                calls.append(args)
                if args[:3] == ["git", "--no-optional-locks", "rev-parse"]:
                    return (
                        ("x" * 40 if fault == "source" else commit) if args[-1] == "HEAD" else tree
                    )
                if args[:3] == ["git", "--no-optional-locks", "status"]:
                    return ""
                if args[:3] == ["docker", "image", "inspect"]:
                    return tree if "ocwp.source-tree" in args[4] else image
                if args[:2] == ["docker", "create"]:
                    role = args[args.index("--name") + 1].rsplit("-", 1)[1]
                    cid = {"canary": "a", "db": "b", "worker": "c"}[role] * 64
                    containers[cid] = role
                    Path(args[args.index("--cidfile") + 1]).write_text(cid)
                    if fault == "create_timeout":
                        raise module.ProofFailure("command_timeout")
                    return cid
                if args[:2] == ["docker", "start"]:
                    return ""
                if args[:2] == ["docker", "inspect"]:
                    if "State.Running" in args[3]:
                        return "\n".join(
                            f"{cid}|{'true' if fault == 'cancellation_unknown' else 'false'}"
                            for cid in args[4:]
                        )
                    if fault == "setup_deadline":
                        clock[0] = 30.0
                    if "range .Mounts" in args[3]:
                        return "tmpfs /tmp"
                    cid, role = args[-1], containers[args[-1]]
                    token = next(
                        row[row.index("--label") + 1].split("=")[1]
                        for row in calls
                        if row[:2] == ["docker", "create"]
                    )
                    network = "container:" + "b" * 64 if role == "worker" else "none"
                    return "|".join((cid, image, token, network, "false", "1", "true"))
                if args[:2] == ["docker", "kill"]:
                    return "\n".join(args[4:])
                if args[:2] == ["docker", "exec"]:
                    if args[3] == "pg_isready":
                        return ""
                    if args[3] == "cat":
                        return "{}" if fault == "invalid_report" else json.dumps(service_report())
                    if fault == "preflight":
                        return "missing"
                    if launches and fault in {"mid_probe", "cancellation_unknown"}:
                        kwargs["before_reap"]()
                        raise module.ProofFailure("command_timeout")
                    if launches and fault == "final_deadline":
                        clock[0] = 5.0
                    raw = probe()
                    return (
                        raw.replace("536870912", "805306368").replace(
                            "---pids.max---\n64", "---pids.max---\n128"
                        )
                        if containers[args[2]] == "db"
                        else raw
                    )
                if args[:2] == ["docker", "rm"]:
                    if fault == "cleanup":
                        raise module.ProofFailure("command_failed")
                    containers.pop(args[-1], None)
                    return ""
                if args[:2] == ["docker", "ps"]:
                    return "\n".join(containers)
                raise AssertionError(args)

            def canary(cid, execute, *, containers=containers, **kwargs):
                containers.pop(cid)
                return {"cpu_usec": 100, "memory_peak": 8192}

            def reconcile(owned, execute, *, calls=calls, containers=containers):
                calls.append(["reconcile"])
                return list(containers)

            patch.setattr(module, "run", execute)
            patch.setattr(module, "cancellation_canary", canary)
            patch.setattr(
                module,
                "effective_privileges",
                lambda *a: {
                    "uid": 10001,
                    "effective_capabilities": 0,
                    "no_new_privileges": True,
                },
            )
            patch.setattr(module, "reconcile_owned", reconcile)
            parser = module.service_failure_diagnostic

            def diagnostic(raw, *, returncode, calls=calls, fault=fault, parser=parser):
                assert any(row[:2] == ["docker", "kill"] for row in calls)
                stopped = [
                    row
                    for row in calls
                    if row[:2] == ["docker", "inspect"] and "State.Running" in row[3]
                ]
                assert stopped and fault != "cancellation_unknown"
                if fault in {"workload_deadline", "mid_probe"}:
                    assert ["client_wait"] in calls
                calls.append(["diagnostic"])
                if fault == "diagnostic_parser_error":
                    raise RuntimeError("private parser failure")
                return parser(raw, returncode=returncode)

            patch.setattr(module, "service_failure_diagnostic", diagnostic)
            evidence, owned = folder / "report.json", folder / "owned.json"
            if fault == "success":
                module.supervise("worker", "pg", commit, evidence, owned, service_initial=True)
            else:
                with pytest.raises(module.ProofFailure, match="service_unqualified"):
                    module.supervise("worker", "pg", commit, evidence, owned, service_initial=True)
            result = json.loads(evidence.read_text())
            expected_launches = (
                0 if fault in {"source", "preflight", "setup_deadline", "create_timeout"} else 1
            )
            assert len(launches) == expected_launches, fault
            if launches:
                assert launches[0] == module.service_argv("c" * 64)
                if fault == "client_reap_unknown":
                    assert result["specimen_client_reap"] == "unverified"
                else:
                    assert type(result["specimen_returncode"]) is int
                    assert result["specimen_client_reap"] == "verified"
            assert result["status"] == (
                "postgresql0013_four_passed_not_capacity"
                if fault == "success"
                else "failed"
            ), fault
            assert result["cleanup"] == (
                "failed" if fault in {"cleanup", "create_timeout"} else "verified_absent"
            )
            if fault in {
                "fixture_exit",
                "workload_deadline",
                "mid_probe",
                "final_deadline",
                "invalid_report",
                "cancellation_unknown",
            }:
                kill = next(i for i, row in enumerate(calls) if row[:2] == ["docker", "kill"])
                assert calls[kill] == ["docker", "kill", "--signal", "KILL", "c" * 64, "b" * 64]
                assert kill < calls.index(["reconcile"])
                if ["client_wait"] in calls:
                    assert kill < calls.index(["client_wait"])
                assert result["cancellation"] == (
                    "unverified" if fault == "cancellation_unknown" else "verified_stopped"
                )
            if fault == "success":
                assert result["observed_workload_cpu_usec"] == 0
                assert result["lifetime_cpu_usec"] == 200
                assert result["environment_overhead_before_workload_cpu_usec"] == {
                    "db": 100,
                    "worker": 100,
                }
                assert result["specimen_returncode"] == 0
                assert not any(row[:2] == ["docker", "kill"] for row in calls)
                assert "service_failure_diagnostic" not in result
            if fault == "fixture_exit" or fault.startswith("diagnostic_"):
                assert result["failure"] == "micro_failed"
                assert result["client_returncode"] == result["specimen_returncode"] == 4
                assert result["service_failure_diagnostic"] == (
                    service_failure_summary()
                    if fault in {"fixture_exit", "diagnostic_exact_limit", "diagnostic_truncated"}
                    else "unavailable_or_invalid"
                )
            if fault in {"cancellation_unknown", "client_reap_unknown", "output_limit"}:
                assert result["service_failure_diagnostic"] == "unavailable_or_invalid"
            if fault in {"success", "cancellation_unknown", "client_reap_unknown"}:
                assert "service_failure_output" not in result
                assert ["diagnostic"] not in calls
                assert ["spool_read"] not in calls
            if fault == "fixture_exit" or fault.startswith("diagnostic_"):
                assert ["diagnostic"] in calls
                retained = result["service_failure_output"]
                decoded = module.base64.b64decode(retained["output_base64"], validate=True)
                assert len(decoded) == retained["output_bytes"] <= module.LIMIT
                assert type(retained["output_truncated"]) is bool
                assert retained["output_truncated"] == (fault == "diagnostic_truncated")
                assert decoded.startswith(b"private\xff\n")
                if fault in {"diagnostic_exact_limit", "diagnostic_truncated"}:
                    assert len(decoded) == module.LIMIT
            if ["spool_read"] in calls:
                stopped = next(
                    i
                    for i, row in enumerate(calls)
                    if row[:2] == ["docker", "inspect"] and "State.Running" in row[3]
                )
                assert stopped < calls.index(["spool_read"]) < calls.index(["diagnostic"])
                if ["client_wait"] in calls:
                    assert calls.index(["client_wait"]) < calls.index(["spool_read"])
            if ["diagnostic"] in calls:
                assert calls.index(["diagnostic"]) < calls.index(["reconcile"])
                assert not any(
                    row[:3] == ["docker", "exec", "c" * 64] and row[3] == "cat" for row in calls
                )
            assert "private" not in evidence.read_text()


def test_service_canary_respects_remaining_setup_deadline(monkeypatch):
    from types import SimpleNamespace

    clock, calls = [29.9], []
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(module.time, "sleep", lambda seconds: calls.append("slept"))
    monkeypatch.setattr(module.os, "killpg", lambda *args: calls.append("client_killed"))
    monkeypatch.setattr(
        module.subprocess,
        "Popen",
        lambda *a, **kw: SimpleNamespace(
            pid=123, poll=lambda: -9, wait=lambda **kw: calls.append("client_reaped")
        ),
    )

    def execute(args, **kwargs):
        assert kwargs["timeout"] <= 0.101
        clock[0] = 30.0
        raise module.ProofFailure("command_timeout")

    with pytest.raises(module.ProofFailure, match="canary_readiness"):
        module.cancellation_canary("a" * 64, execute, aggregate_deadline=30.0)
    assert "slept" not in calls


def test_service_hook_rejects_each_untrusted_event_without_retaining_it():
    from types import SimpleNamespace

    for change in (
        {"nodeid": "private"},
        {"when": "private"},
        {"duration": float("nan")},
        {"duration": True},
        {"wasxfail": "private"},
        {"outcome": "xpassed"},
    ):
        hook = module.ServiceReportHook()
        hook.pytest_collection_finish(SimpleNamespace(items=service_items()))
        hook.pytest_runtest_logreport(
            SimpleNamespace(
                **(
                    dict(
                        nodeid=module.SERVICE_NODES[0], when="call", outcome="passed", duration=0.1
                    )
                    | change
                )
            )
        )
        assert hook.value["protocol_errors"] == 1
        assert hook.value["reports"] == []
        assert "private" not in str(hook.value)


def test_service_workflow_is_one_fixed_push_and_one_business_invocation():
    workflow = PATH.parents[2] / ".github/workflows/quote-service-contained.yml"
    text = workflow.read_text()
    assert "branches: [codex/quote-service-contained-initial]" in text
    assert "github.run_number == 1 && github.run_attempt == 1" in text
    assert 'test "$GITHUB_RUN_NUMBER" = 1' in text
    assert 'test "$GITHUB_RUN_ATTEMPT" = 1' in text
    assert "quote-service-contained.yml@$GITHUB_REF" in text
    assert text.count("--service-initial") == 1
    assert "--single-record-feasibility" not in text
    for forbidden in (
        "pull_request:",
        "workflow_dispatch:",
        "workflow_run:",
        "schedule:",
        "workflow_call:",
        "matrix:",
        "--collect-only",
        "uv run pytest",
    ):
        assert forbidden not in text
    assert "if: always()" in text and "quote-service-independent-cleanup.json" in text
    assert "--quiet" in text and "timeout=seconds + 5" in text
    assert text.index('test "$GITHUB_RUN_NUMBER" = 1') < text.index("git archive HEAD")


def test_service_rejects_all_controller_pressure_boundaries():
    for old, new in (
        ("0::/", "0::/other"),
        ("536870912", "max"),
        ("100000 100000", "max 100000"),
        ("---pids.max---\n64", "---pids.max---\nmax"),
        ("---memory.swap.max---\n0", "---memory.swap.max---\n1"),
        ("usage_usec 100", "usage_usec -1"),
        ("usage_usec 100", "usage_usec nope"),
        ("oom_kill 0", "oom_kill 1"),
        ("---cpu.stat---", "MISSING"),
        ("8192", "536870913"),
        ("---pids.events---\nmax 0", "---pids.events---\nmax 1"),
    ):
        with pytest.raises(module.ProofFailure):
            module.parse_probe(probe().replace(old, new), 512, 64)


# Failure-diagnostic regressions were authored before implementation. RED/GREEN
# are unexecuted; execute only in a separately reviewed bounded containment.
def service_failure_summary():
    return dict(
        schema=1,
        stage=1,
        session_exitstatus=4,
        collection_count=0,
        collection_errors=1,
        unhandled_errors=0,
        protocol_errors=1,
        report_count=0,
        setup_reports=0,
        call_reports=0,
        teardown_reports=0,
        failed_reports=0,
        skipped_reports=0,
    )


def service_failure_marker(value=None):
    import json

    value = service_failure_summary() if value is None else value
    return (
        b"OCWP_SERVICE_FAILURE_V1:"
        + json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
        + b"\n"
    )


def test_service_failure_diagnostic_retains_only_closed_numbers():
    good = service_failure_summary()
    marker = service_failure_marker(good)
    assert len(marker) <= 512
    assert (
        module.service_failure_diagnostic(
            b"private\xff output\n" + marker + b"private exception\n", returncode=4
        )
        == good
    )
    boundary = good | {
        "stage": 4,
        "collection_count": 100,
        "collection_errors": 100,
        "unhandled_errors": 100,
        "protocol_errors": 100,
        "report_count": 18,
        "setup_reports": 6,
        "call_reports": 6,
        "teardown_reports": 6,
        "failed_reports": 17,
        "skipped_reports": 1,
    }
    assert (
        module.service_failure_diagnostic(service_failure_marker(boundary), returncode=4)
        == boundary
    )


def test_service_failure_diagnostic_rejects_untrusted_fields_and_ranges():
    good = service_failure_summary()
    changes = (
        {"schema": True},
        {"schema": 2},
        {"stage": "private"},
        {"stage": -1},
        {"stage": 5},
        {"session_exitstatus": 0},
        {"session_exitstatus": 6},
        {"session_exitstatus": 1},
        {"collection_count": True},
        {"collection_count": -1},
        {"collection_count": 101},
        {"collection_errors": 101},
        {"unhandled_errors": 0.0},
        {"protocol_errors": None},
        {"report_count": 19},
        {"setup_reports": 1},
        {"call_reports": -1},
        {"teardown_reports": 19},
        {"failed_reports": 1},
        {"skipped_reports": 1},
        {"nodes": ["private"]},
        {"raw_error": "private"},
    )
    for change in changes:
        with pytest.raises(module.ProofFailure):
            module.service_failure_diagnostic(service_failure_marker(good | change), returncode=4)
    for key in good:
        with pytest.raises(module.ProofFailure):
            module.service_failure_diagnostic(
                service_failure_marker({k: v for k, v in good.items() if k != key}),
                returncode=4,
            )
    for returncode in (True, 0, -9, 1, 6, None):
        with pytest.raises(module.ProofFailure):
            module.service_failure_diagnostic(service_failure_marker(), returncode=returncode)


def test_service_failure_diagnostic_rejects_bad_framing_and_duplicate_keys():
    marker = service_failure_marker()
    for raw in (
        b"",
        b"private",
        marker * 2,
        marker[:-1],
        b"prefix" + marker,
        marker.replace(b'"stage":1', b'"stage":1,"stage":1'),
        marker.replace(b'"stage":1', b'"stage":NaN'),
        marker.replace(b'"stage":1', b'"stage":Infinity'),
        marker.replace(b'"stage":1', b'"stage":1e0'),
        marker.replace(b'"stage":1', b'"stage":true'),
        marker.replace(b'"stage":1', b'"stage":"\xff"'),
        marker.replace(b"{", b"{ "),
        marker[:-1] + b" private\n",
        b"OCWP_SERVICE_FAILURE_V1:" + b" " * 512 + b"\n",
        marker + b"x" * module.SERVICE_OUTPUT_LIMIT,
        marker + b"OCWP_SERVICE_FAILURE_V1:incomplete",
        marker.decode("ascii"),
    ):
        with pytest.raises(module.ProofFailure):
            module.service_failure_diagnostic(raw, returncode=4)


def test_service_failure_hook_emits_once_outside_capture_without_raw_text(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace

    calls = []

    @contextmanager
    def disabled():
        calls.append("capture_disabled")
        yield
        calls.append("capture_restored")

    def write(fd, raw):
        assert fd == 1 and calls[-1] == "capture_disabled"
        calls.append(raw)
        return len(raw)

    capture = SimpleNamespace(global_and_fixture_disabled=disabled)
    session = SimpleNamespace(
        config=SimpleNamespace(
            pluginmanager=SimpleNamespace(
                getplugin=lambda name: capture if name == "capturemanager" else None,
            )
        )
    )
    monkeypatch.setattr(module.os, "write", write)
    monkeypatch.setattr(module, "SERVICE_REPORT", str(tmp_path / "report.json"))
    hook = module.ServiceReportHook()
    hook.pytest_collectreport(SimpleNamespace(outcome="failed", longrepr="private"))
    with pytest.raises(pytest.UsageError):
        hook.pytest_collection_finish(SimpleNamespace(items=[]))
    hook.pytest_sessionfinish(session, 4)
    hook.pytest_sessionfinish(session, 4)
    assert calls == ["capture_disabled", b"\n" + service_failure_marker(), "capture_restored"]
    assert module.service_failure_diagnostic(calls[1], returncode=4) == service_failure_summary()
    assert "private" not in repr(calls)


def test_service_failure_hook_counts_first_failed_stage_and_ignores_emission_errors(
    tmp_path, monkeypatch
):
    from contextlib import nullcontext
    from types import SimpleNamespace

    emitted = []
    capture = SimpleNamespace(global_and_fixture_disabled=nullcontext)
    session = SimpleNamespace(
        config=SimpleNamespace(
            pluginmanager=SimpleNamespace(
                getplugin=lambda name: capture,
            )
        )
    )
    monkeypatch.setattr(module, "SERVICE_REPORT", str(tmp_path / "report.json"))
    monkeypatch.setattr(module.os, "write", lambda fd, raw: emitted.append(raw) or len(raw))
    for when, stage in (("setup", 2), ("call", 3), ("teardown", 4)):
        hook = module.ServiceReportHook()
        hook.pytest_collection_finish(SimpleNamespace(items=service_items()))
        for phase in ("setup", "call", "teardown"):
            hook.pytest_runtest_logreport(
                SimpleNamespace(
                    nodeid=module.SERVICE_NODES[0],
                    when=phase,
                    outcome="failed" if phase == when else "passed",
                    duration=0.001,
                    capstdout="private",
                    longrepr="private",
                )
            )
        hook.pytest_sessionfinish(session, 1)
        value = module.service_failure_diagnostic(emitted[-1], returncode=1)
        assert value["stage"] == stage and value["failed_reports"] == 1
        assert value["setup_reports"] == value["call_reports"] == value["teardown_reports"] == 1
        assert value["report_count"] == 3 and "private" not in repr(value)
    success = module.ServiceReportHook()
    success.pytest_sessionfinish(session, 0)
    assert len(emitted) == 3

    def broken_write(*args):
        raise OSError("private emitter failure")

    monkeypatch.setattr(module.os, "write", broken_write)
    module.ServiceReportHook().pytest_sessionfinish(session, 4)
    monkeypatch.setattr(module, "SERVICE_REPORT", str(tmp_path / "absent" / "report.json"))
    with pytest.raises(FileNotFoundError):
        module.ServiceReportHook().pytest_sessionfinish(session, 4)


# Review-only additions for a future ordinary contained test selection. These are
# deliberately not extra execution nodes in the six-tool static/contracts gate.
def static_failure_summary():
    import base64

    output = b"public source tool diagnostic\n"
    return {
        "schema": 2,
        "tool": 1,
        "kind": 1,
        "returncode": 1,
        "output_bytes": len(output),
        "output_truncated": False,
        "output_base64": base64.b64encode(output).decode("ascii"),
    }


def static_protocol_summary(tool=1):
    protocols = tool + 1
    return {
        "schema": 1,
        "stage": 3,
        "session_exitstatus": 1,
        "collection_count": 6,
        "collection_errors": 0,
        "unhandled_errors": 0,
        "protocol_errors": 0,
        "report_count": protocols * 3,
        "setup_reports": protocols,
        "call_reports": protocols,
        "teardown_reports": protocols,
        "failed_reports": 1,
        "skipped_reports": 0,
    }


def static_failure_marker(value=None):
    import json

    value = static_failure_summary() if value is None else value
    return (
        module.STATIC_FAILURE_MARKER
        + json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
        + b"\n"
    )


def test_static_failure_marker_is_closed_and_matches_first_failed_protocol():
    good = static_failure_summary()
    protocol = static_protocol_summary()
    assert module.static_failure_diagnostic(static_failure_marker(), failure=protocol) == good
    for change in (
        {"stage": 2},
        {"call_reports": 1},
        {"teardown_reports": 1},
        {"failed_reports": 2},
        {"collection_count": 5},
        {"session_exitstatus": 2},
        {"protocol_errors": 1},
        {"unhandled_errors": 1},
        {"schema": True},
    ):
        with pytest.raises(module.ProofFailure):
            module.static_failure_diagnostic(static_failure_marker(), failure=protocol | change)
    for change in (
        {"schema": True},
        {"schema": 1},
        {"tool": -1},
        {"tool": 6},
        {"tool": True},
        {"kind": 0},
        {"kind": 5},
        {"returncode": 0},
        {"returncode": True},
        {"returncode": None},
        {"returncode": 256},
        {"output_bytes": module.LIMIT},
        {"output_bytes": module.LIMIT + 1},
        {"output_bytes": -1},
        {"output_bytes": True},
        {"output_bytes": 0},
        {"output_truncated": True},
        {"output_truncated": 0},
        {"output_base64": None},
        {"output_base64": "!"},
        {"output_base64": "é"},
        {"output_base64": good["output_base64"] + "\n"},
        {"output_base64": good["output_base64"] + "="},
        {"output_base64": "A" * (4 * ((module.LIMIT + 2) // 3) + 4)},
        {"output_base64": "YR==", "output_bytes": 1},  # Nonzero padding bits.
        {"output_base64": "YQ==YQ==", "output_bytes": 2},
        {"message": "unexpected field"},
    ):
        with pytest.raises(module.ProofFailure):
            module.static_failure_diagnostic(static_failure_marker(good | change), failure=protocol)
    for key in good:
        with pytest.raises(module.ProofFailure):
            module.static_failure_diagnostic(
                static_failure_marker({k: v for k, v in good.items() if k != key}),
                failure=protocol,
            )


def test_static_failure_marker_rejects_duplicate_nonfinite_truncated_and_oversize_bytes():
    marker = static_failure_marker()
    for bad in (
        b"",
        marker + marker,
        marker[:-1],
        b"x" + marker,
        marker.replace(b'"schema":2', b'"schema":2,"schema":2'),
        marker.replace(b'"schema":2', b'"schema":NaN'),
        marker.replace(b'"schema":2', b'"schema":Infinity'),
        marker.replace(b'"schema":2', b'"schema":2.0'),
        marker.replace(b'"schema":2', b'"schema": 2'),
        marker[:-1] + b"{}\n",
        module.STATIC_FAILURE_MARKER + b" " * module.STATIC_FAILURE_LIMIT + b"\n",
        b" " * module.SERVICE_OUTPUT_LIMIT + marker,
        marker.decode("ascii"),
    ):
        with pytest.raises(module.ProofFailure):
            module.static_failure_diagnostic(bad, failure=static_protocol_summary())


def test_static_failure_marker_distinguishes_cap_timeout_and_launch_failure():
    import base64

    good = static_failure_summary()
    protocol = static_protocol_summary()
    for change in (
        {"kind": 2, "returncode": -9},
        {
            "kind": 3,
            "returncode": -25,
            "output_bytes": module.LIMIT,
            "output_truncated": True,
            "output_base64": base64.b64encode(b"x" * module.LIMIT).decode("ascii"),
        },
        {"kind": 4, "returncode": None, "output_bytes": 0, "output_base64": ""},
    ):
        value = good | change
        assert (
            module.static_failure_diagnostic(static_failure_marker(value), failure=protocol)
            == value
        )
    for change in (
        {"kind": 3},
        {"kind": 4},
        {"kind": 4, "returncode": None},
    ):
        with pytest.raises(module.ProofFailure):
            module.static_failure_diagnostic(static_failure_marker(good | change), failure=protocol)


def test_all_six_static_tools_retain_exact_bytes_with_numeric_marker_at_full_cap():
    import base64

    output = bytes(range(256)) * 64
    assert len(output) == module.LIMIT
    for tool in range(6):
        value = static_failure_summary() | {
            "tool": tool,
            "kind": 3,
            "returncode": -25,
            "output_bytes": len(output),
            "output_truncated": True,
            "output_base64": base64.b64encode(output).decode("ascii"),
        }
        protocol = static_protocol_summary(tool)
        marker = static_failure_marker(value)
        spool = marker + service_failure_marker(protocol)
        assert module.LIMIT < len(marker) <= module.STATIC_FAILURE_LIMIT
        assert len(spool) < module.SERVICE_OUTPUT_LIMIT
        assert module.service_failure_diagnostic(spool, returncode=1) == protocol
        retained = module.static_failure_diagnostic(spool, failure=protocol)
        assert retained == value
        assert base64.b64decode(retained["output_base64"], validate=True) == output
        with pytest.raises(module.ProofFailure):
            module.static_failure_diagnostic(spool, failure=static_protocol_summary((tool + 1) % 6))


def test_service_spool_and_ordinary_output_limits_remain_separate(monkeypatch):
    calls = []
    monkeypatch.setattr(module.resource, "setrlimit", lambda *args: calls.append(args))
    module.output_limit()
    module.service_output_limit()
    assert calls == [
        (module.resource.RLIMIT_FSIZE, (16 * 1024, 16 * 1024)),
        (module.resource.RLIMIT_FSIZE, (32 * 1024, 32 * 1024)),
    ]


def test_static_wrapper_retains_verbatim_public_output_without_changing_failure(monkeypatch):
    import base64
    from contextlib import nullcontext
    from types import SimpleNamespace

    wrapper_path = PATH.parents[2] / "tests/operations/test_quote_service_static_contracts.py"
    wrapper_spec = importlib.util.spec_from_file_location(
        "static_contract_test_wrapper",
        wrapper_path,
    )
    wrapper = importlib.util.module_from_spec(wrapper_spec)
    wrapper_spec.loader.exec_module(wrapper)
    monkeypatch.setattr(wrapper, "ROOT", Path("/app"))
    monkeypatch.setenv("OCWP_QUOTE_SERVICE_INITIAL", "contained")
    emitted = []
    monkeypatch.setattr(wrapper.os, "write", lambda fd, raw: emitted.append(raw) or len(raw))
    outputs = (
        b"--- a/scripts/ci/quote_guard_bootstrap.py\n+++ b/scripts/ci/quote_guard_bootstrap.py\n"
        b"@@ -1 +1 @@\n-old public source\n+new public source\n\x1b[0m\xff",
        bytes(range(256)) * 64,
    )
    for tool in range(6):
        for output in outputs:

            def fake_popen(*args, output=output, **kwargs):
                kwargs["stdout"].write(output)
                kwargs["stdout"].flush()
                assert kwargs["preexec_fn"] is wrapper._limit_output
                return SimpleNamespace(wait=lambda timeout: 1)

            monkeypatch.setattr(wrapper.subprocess, "Popen", fake_popen)
            with pytest.raises(pytest.fail.Exception):
                wrapper._check(tool, SimpleNamespace(disabled=nullcontext))
            marker = emitted[-1]
            assert len(marker) <= module.STATIC_FAILURE_LIMIT + 1
            value = module.static_failure_diagnostic(marker, failure=static_protocol_summary(tool))
            assert value["output_bytes"] == len(output)
            assert value["output_truncated"] == (len(output) == module.LIMIT)
            assert value["kind"] == (3 if len(output) == module.LIMIT else 1)
            assert value["returncode"] == 1
            assert base64.b64decode(value["output_base64"], validate=True) == output
