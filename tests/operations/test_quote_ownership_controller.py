"""Pure/fake contained controller integration; no Docker/process/SQL actions."""

from contextlib import suppress
from pathlib import Path

import pytest
from test_quote_ownership_measurement import identity as identity
from test_quote_ownership_worker import FakeRuntime

from scripts.ci.quote_ownership_measurement import container_args, supervise_measurement
from scripts.ci.quote_ownership_worker import WorkerRefusal, run_owner


def test_fixed_container_args_preserve_full_envelope_and_disposable_initializer(identity):
    db = container_args("db", identity["pg_image"], identity["nonce"], Path("owned.json"))
    worker = container_args(
        "worker", identity["worker_image"], identity["nonce"], Path("owned.json"), "f" * 64
    )
    assert db[db.index("--memory") + 1] == "1024m"
    assert worker[worker.index("--memory") + 1] == "768m"
    assert "POSTGRES_USER=postgres" in db and "POSTGRES_DB=postgres" in db
    assert "POSTGRES_USER=ocwp" not in db
    assert "--privileged" not in db + worker and "--mount" not in db + worker
    assert worker[worker.index("--network") + 1] == "container:" + "f" * 64


class FakeHost:
    def __init__(self, identity, *, source_fail=False, cleanup_fail=False):
        self.expected = identity
        self.events = []
        self.source_fail, self.cleanup_fail = source_fail, cleanup_fail
        self.report = None
        self.clock = 0

    def now(self):
        return self.clock

    def source(self, deadline):
        self.events.append("source")
        if self.source_fail:
            raise WorkerRefusal("identity")

    def setup(self, deadline):
        self.events.append("setup")

    def observe(self, deadline):
        self.events.append("observe")
        worker = FakeRuntime()
        result = run_owner(worker, self.expected, deadline)
        self.clock = worker.time
        return result, {
            "worker_peak_bytes": 100,
            "pg_peak_bytes": 200,
            "worker_processes": 4,
            "pg_processes": 6,
            "pressure_events": 0,
        }

    def cleanup(self, deadline):
        self.events.append("cleanup")
        if self.cleanup_fail:
            raise WorkerRefusal("cleanup_unknown")
        return not self.source_fail

    def save(self, report):
        self.report = report


@pytest.mark.parametrize("source_fail,cleanup_fail", [(False, False), (True, False), (False, True)])
def test_mock_host_owner_result_cleanup_chain_preserves_failure(
    identity, source_fail, cleanup_fail
):
    host = FakeHost(identity, source_fail=source_fail, cleanup_fail=cleanup_fail)
    report = supervise_measurement(host, 65_000_000_000)
    assert host.events[-1] == "cleanup"
    if source_fail:
        assert host.events == ["source", "cleanup"]
    if source_fail or cleanup_fail:
        assert report["status"] == "failed"
        assert report["failure"] is not None
    else:
        assert report["status"] == "pending_cleanup"
        assert report["primary_cleanup"] == "verified_absent"
        assert report["independent_cleanup"] == "pending"
        assert report["cases"][0]["status"] == report["cases"][1]["status"] == "passed"
    assert host.report == report


def test_closed_writer_refuses_hardlink_before_mutating_target(tmp_path):
    import os

    from scripts.ci.quote_ownership_measurement import _write_closed

    original = tmp_path / "original"
    original.write_text("unchanged")
    alias = tmp_path / "alias"
    os.link(original, alias)
    with pytest.raises(WorkerRefusal):
        _write_closed(alias, {"schema": 1})
    assert original.read_text() == "unchanged"


@pytest.mark.parametrize("failed,absent", [(False, True), (True, True), (False, False)])
def test_independent_seal_preserves_failed_measurement(identity, failed, absent):
    from scripts.ci.quote_ownership_measurement import seal_receipt

    host = FakeHost(identity)
    report = supervise_measurement(host, 65_000_000_000)
    if failed:
        report.update(status="failed", failure="observer_unknown")
    result = seal_receipt(report, identity, absent)
    assert result["status"] == ("passed" if absent and not failed else "failed")
    assert result["independent_cleanup"] == ("verified_absent" if absent else "unknown")
    if failed and absent:
        assert result["failure"] == "observer_unknown"


def test_closed_reader_refuses_symlink_ancestor(tmp_path):
    from scripts.ci.quote_ownership_measurement import _read_closed

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "record.json").write_text('{"schema":1}')
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises((WorkerRefusal, OSError, ValueError)):
        _read_closed(tmp_path / "linked/record.json")


def test_early_finalizer_dangling_owner_is_unknown(tmp_path):
    import json

    from scripts.ci.quote_ownership_measurement import _early_cleanup_record

    owned = tmp_path / "owned.json"
    owned.with_suffix(".owner.json").symlink_to(tmp_path / "missing")
    _early_cleanup_record(
        {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1"},
        owned,
        tmp_path / "receipt.json",
    )
    result = json.loads((tmp_path / "cleanup.json").read_text())
    assert result["owner_manifest_present"] is True
    assert result["outcome"] == "unknown"


@pytest.mark.parametrize("source_fail,cleanup_fail", [(False, False), (True, False), (False, True)])
def test_complete_mock_owner_primary_independent_receipt_chain(
    identity, tmp_path, source_fail, cleanup_fail
):
    import hashlib
    import json

    from scripts.ci.quote_ownership_measurement import _write_closed, finalize_measurement

    class FinalHost(FakeHost):
        def __init__(self):
            super().__init__(identity)
            self.owned = tmp_path / "owned.json"
            self.evidence = tmp_path / "receipt.json"
            self.owned.with_suffix(".owner.json").write_text("{}")

        def cleanup(self, deadline):
            self.events.append("cleanup")
            if self.cleanup_fail:
                raise WorkerRefusal("cleanup_unknown")
            return True

        def save(self, report):
            super().save(report)
            _write_closed(self.evidence, report)

    host = FinalHost()
    supervise_measurement(host, 65_000_000_000)
    host.source_fail, host.cleanup_fail = source_fail, cleanup_fail
    cleanup = finalize_measurement(host)
    final = json.loads(host.evidence.read_text())
    if cleanup_fail:
        assert cleanup["outcome"] == "unknown"
        assert final["status"] != "passed"
    else:
        assert cleanup["outcome"] == "verified_absent"
        assert final["status"] == ("failed" if source_fail else "passed")
        assert cleanup["receipt_sha256"] == hashlib.sha256(host.evidence.read_bytes()).hexdigest()


def test_closed_writer_parent_swap_refuses_without_touching_new_target(tmp_path, monkeypatch):
    from scripts.ci import quote_ownership_actions_adapter as adapter
    from scripts.ci.quote_ownership_measurement import _write_closed

    parent = tmp_path / "parent"
    parent.mkdir()
    target = parent / "record.json"
    target.write_text("old")
    original = adapter._write_at

    def swap(directory, name, value):
        original(directory, name, value)
        parent.rename(tmp_path / "old-parent")
        parent.mkdir()
        target.write_text("untouched")

    monkeypatch.setattr(adapter, "_write_at", swap)
    with pytest.raises((WorkerRefusal, ValueError, OSError)):
        _write_closed(target, {"schema": 1})
    assert target.read_text() == "untouched"


def test_cleanup_never_switches_authority_after_owner_file_swap(identity, tmp_path):
    import json

    from scripts.ci.quote_ownership_measurement import HostRuntime

    host = object.__new__(HostRuntime)
    host.expected = identity
    host.worker_image, host.pg_image = identity["worker_image"], identity["pg_image"]
    host.owned = tmp_path / "owned.json"
    host.host_child = None
    host.now = lambda: 0
    owner = host.owned.with_suffix(".owner.json")
    owner.write_text(json.dumps(host._manifest()))
    foreign = "d" * 32
    cid = "e" * 64
    calls = []

    def execute(args, **kwargs):
        calls.append(args)
        if args[:2] == ["docker", "ps"]:
            owner.write_text(json.dumps({**host._manifest(), "token": foreign}))
            return (
                cid if "--filter" not in args or f"label=ocwp.quote-micro={foreign}" in args else ""
            )
        if args[:2] == ["docker", "inspect"]:
            return f"{host.worker_image}|{foreign}|/ocwp-quote-{foreign}-worker"
        return ""

    host.client = lambda deadline: execute
    with suppress(WorkerRefusal):
        host.cleanup(55_000_000_000)
    assert not any(call[:2] == ["docker", "rm"] and cid in call for call in calls)


def test_early_finalizer_missing_owner_with_cid_hint_is_unknown(tmp_path):
    import json

    from scripts.ci.quote_ownership_measurement import _early_cleanup_record

    owned = tmp_path / "owned.json"
    owned.with_suffix(".db.cid").write_text("partial")
    _early_cleanup_record(
        {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1"},
        owned,
        tmp_path / "receipt.json",
    )
    assert json.loads((tmp_path / "cleanup.json").read_text())["outcome"] == "unknown"


def test_finalizer_late_after_sealing_never_leaves_qualifying_receipt(identity, tmp_path):
    import json

    from scripts.ci.quote_ownership_measurement import _write_closed, finalize_measurement

    class LateHost(FakeHost):
        def __init__(self):
            super().__init__(identity)
            self.owned, self.evidence = tmp_path / "owned.json", tmp_path / "receipt.json"
            self.owned.with_suffix(".owner.json").write_text("{}")
            self.late = False

        def save(self, report):
            _write_closed(self.evidence, report)
            if self.late:
                self.clock += 56_000_000_000

    host = LateHost()
    supervise_measurement(host, 65_000_000_000)
    host.late = True
    result = finalize_measurement(host)
    assert result["outcome"] == "unknown"
    assert json.loads(host.evidence.read_text())["status"] != "passed"
