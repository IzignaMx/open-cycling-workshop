from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "services/platform/src"


def test_runtime_registers_all_database_models_in_fresh_process() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SOURCE)
    env["OCWP_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
    code = """
from cycling_workshop.runtime import app  # noqa: F401
from cycling_workshop.db.base import Base
required = {
    'organizations', 'locations', 'customers', 'sync_mutation_receipts',
    'sync_changes', 'outbox_events', 'background_jobs', 'bicycles',
    'service_orders', 'service_order_events', 'products',
    'inventory_movements',
}
missing = sorted(required - set(Base.metadata.tables))
if missing:
    raise SystemExit('missing tables: ' + ', '.join(missing))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
