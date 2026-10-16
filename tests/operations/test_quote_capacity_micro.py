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
