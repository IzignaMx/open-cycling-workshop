from __future__ import annotations

import json
from pathlib import Path

from scripts.benchmarks.run_indexeddb_native_benchmark import detect_url_block_policy


def test_detect_url_block_policy_reports_managed_block_all(tmp_path: Path) -> None:
    policy = tmp_path / "managed.json"
    policy.write_text(json.dumps({"URLBlocklist": ["*"]}), encoding="utf-8")

    assert detect_url_block_policy(tmp_path) == str(policy)


def test_detect_url_block_policy_ignores_nonblocking_policy(tmp_path: Path) -> None:
    (tmp_path / "managed.json").write_text(
        json.dumps({"URLBlocklist": ["https://blocked.example/*"]}), encoding="utf-8"
    )

    assert detect_url_block_policy(tmp_path) is None
