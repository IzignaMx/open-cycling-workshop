"""Reject incomplete, stale or source-mismatched PostgreSQL qualification."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest

from scripts.ci.inventory_read_proof import check_evidence


def test_pg_evidence_requires_fresh_complete_exact_source_and_plan(tmp_path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "read.py").write_text("bounded synthetic source")
    plan = tmp_path / "backend-postgres-explain.json"
    plan.write_text('{"safe":"plan"}')
    proof = {
        "status": "cases_complete",
        "started_at": datetime.now(UTC).isoformat(),
        "expected_cases": [str(i) for i in range(42)] + ["plans"],
        "cases": {str(i): {} for i in range(42)}
        | {"plans": {"explain_sha256": hashlib.sha256(plan.read_bytes()).hexdigest()}},
        "source_sha256": {"read.py": hashlib.sha256((root / "read.py").read_bytes()).hexdigest()},
    }
    path = tmp_path / "backend-postgres-evidence.json"

    def write():
        path.write_text(json.dumps(proof))

    write()
    check_evidence(tmp_path, root, "2000-01-01T00:00:00+00:00", {"read.py"})
    proof["status"] = "incomplete"
    write()
    with pytest.raises(AssertionError):
        check_evidence(tmp_path, root, "2000-01-01T00:00:00+00:00", {"read.py"})
    proof["status"] = "cases_complete"
    write()
    with pytest.raises(AssertionError):
        check_evidence(tmp_path, root, "9999-01-01T00:00:00+00:00", {"read.py"})
    (root / "read.py").write_text("changed source")
    with pytest.raises(AssertionError):
        check_evidence(tmp_path, root, "2000-01-01T00:00:00+00:00", {"read.py"})


def test_failed_pytest_teardown_cannot_leave_complete_or_cases_complete(
    tmp_path, monkeypatch
) -> None:
    import subprocess

    from scripts.ci import inventory_read_proof as runner

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setenv("OCWP_TEST_DATABASE_URL", "postgresql://synthetic@127.0.0.1/inventory_test")
    path = tmp_path / "artifacts/inventory-read/pg-direct/backend-postgres-evidence.json"

    def failed_test(*args, **kwargs):
        path.write_text(json.dumps({"status": "cases_complete", "cases": {"synthetic": {}}}))
        raise subprocess.CalledProcessError(1, ["pytest"])

    monkeypatch.setattr(runner.subprocess, "run", failed_test)
    with pytest.raises(subprocess.CalledProcessError):
        runner.main()
    assert json.loads(path.read_text())["status"] == "failed"
