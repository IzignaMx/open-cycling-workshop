"""Fail-closed actual PostgreSQL inventory race/budget/plan qualification.

This guard prevents developer-friendly skips or stale artifacts from qualifying
an exact source. It operates only on the repository's dedicated local test DB.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    "services/platform/src/cycling_workshop/inventory/read_guard.py",
    "services/platform/src/cycling_workshop/inventory/read_repository.py",
    "services/platform/src/cycling_workshop/inventory/cursor.py",
    "services/platform/src/cycling_workshop/inventory/router.py",
    "services/platform/tests/inventory/test_inventory_read_postgres.py",
}


def check_evidence(directory: Path, root: Path, started: str, sources: set[str] = SOURCES) -> None:
    proof = json.loads((directory / "backend-postgres-evidence.json").read_text())
    assert proof["status"] == "complete", "PostgreSQL evidence is incomplete or skipped"
    assert datetime.fromisoformat(proof["started_at"]) >= datetime.fromisoformat(started), (
        "Stale PostgreSQL evidence"
    )
    assert len(proof["cases"]) == len(proof["expected_cases"]) == 43
    assert set(proof["cases"]) == set(proof["expected_cases"])
    assert set(proof["source_sha256"]) == sources
    for name, digest in proof["source_sha256"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, (
            "Changed PostgreSQL proof source"
        )
    assert (
        hashlib.sha256((directory / "backend-postgres-explain.json").read_bytes()).hexdigest()
        == proof["cases"]["plans"]["explain_sha256"]
    )


def main() -> None:
    started = datetime.now(UTC).isoformat()
    directory = ROOT / "artifacts/inventory-read/pg-direct"
    directory.mkdir(parents=True, exist_ok=True)
    # Invalidate previous success even if database preflight or test collection fails.
    (directory / "backend-postgres-evidence.json").write_text(
        json.dumps({"status": "incomplete", "started_at": started, "cases": {}}) + "\n"
    )
    url = os.getenv("OCWP_TEST_DATABASE_URL")
    if not url:
        raise SystemExit(
            "BLOCKED: OCWP_TEST_DATABASE_URL is required; PostgreSQL proof not executed"
        )
    from scripts.e2e.prepare_e2e_database import validate_e2e_database_url

    validate_e2e_database_url(url)
    env = {**os.environ, "OCWP_INVENTORY_READ_EVIDENCE_DIR": str(directory)}
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "services/platform/tests/inventory/test_inventory_read_postgres.py",
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )
    check_evidence(directory, ROOT, started)
    print(
        "All 43 actual PostgreSQL inventory cases passed with fresh source-bound measured evidence."
    )


if __name__ == "__main__":
    main()
