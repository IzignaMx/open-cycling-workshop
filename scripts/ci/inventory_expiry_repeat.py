"""Require ten fresh, retry-free native expiry passes; preserve failures as failures."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Keep proof/JSON separate from both Playwright-owned output directories: their
# reporters may clear those directories while starting or writing the HTML report.
OUTPUT = Path("apps/web/test-results/inventory-expiry-repeat-proof")
SOURCES = [
    ".github/workflows/ci.yml",
    "apps/web/e2e/inventory.spec.ts",
    "apps/web/e2e/helpers/inventory-observation.mjs",
    "apps/web/playwright.config.ts",
    "scripts/ci/inventory_expiry_repeat.py",
]
TITLES = {
    f"inventory-only display clears on {mode} expiry with no further inventory read"
    for mode in ("idle", "background")
}


def source_hashes(root: Path) -> dict[str, str]:
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCES}


def start(root: Path, sha: str, now: datetime) -> None:
    directory = root / OUTPUT
    directory.mkdir(parents=True, exist_ok=True)
    marker = {
        "source_commit": sha,
        "started_at": now.isoformat(),
        "source_sha256": source_hashes(root),
    }
    (directory / "started.json").write_text(json.dumps(marker, indent=2) + "\n")
    (directory / "evidence.json").write_text('{"status":"incomplete"}\n')


def validate_report(report: dict) -> None:
    assert report["errors"] == []
    assert {
        key: report["stats"][key] for key in ("expected", "unexpected", "flaky", "skipped")
    } == {
        "expected": 10,
        "unexpected": 0,
        "flaky": 0,
        "skipped": 0,
    }
    config = report["config"]
    assert config["workers"] == 1 and len(config["projects"]) == 1
    project = config["projects"][0]
    assert {key: project[key] for key in ("name", "repeatEach", "retries", "timeout")} == {
        "name": "chromium",
        "repeatEach": 5,
        "retries": 0,
        "timeout": 45000,
    }
    assert len(report["suites"]) == 1
    suite = report["suites"][0]
    assert suite["file"] == "inventory.spec.ts" and not suite.get("suites")
    assert 2 <= len(suite["specs"]) <= 10
    counts: Counter[str] = Counter()
    for spec in suite["specs"]:
        assert spec["ok"] is True and spec["file"] == "inventory.spec.ts"
        assert spec["title"] in TITLES and 1 <= len(spec["tests"]) <= 5
        counts[spec["title"]] += len(spec["tests"])
        for test in spec["tests"]:
            assert test["expectedStatus"] == "passed" and test["status"] == "expected"
            assert test["projectName"] == "chromium" and test["timeout"] == 45000
            assert len(test["results"]) == 1
            result = test["results"][0]
            assert result["status"] == "passed" and result["retry"] == 0
            assert result["errors"] == [] and not result.get("error")
    assert counts == {title: 5 for title in TITLES}


def check(root: Path, sha: str, outcome: str) -> None:
    directory = root / OUTPUT
    directory.mkdir(parents=True, exist_ok=True)
    evidence = directory / "evidence.json"
    evidence.write_text('{"status":"incomplete"}\n')
    assert outcome == "success"
    marker = json.loads((directory / "started.json").read_text())
    assert marker["source_commit"] == sha and marker["source_sha256"] == source_hashes(root)
    with (directory / "results.json").open("rb") as stream:
        raw = stream.read(1_048_577)
    assert len(raw) <= 1_048_576
    report = json.loads(raw)
    assert datetime.fromisoformat(report["stats"]["startTime"]) >= datetime.fromisoformat(
        marker["started_at"]
    )
    validate_report(report)
    evidence.write_text(
        json.dumps(
            {
                **marker,
                "status": "complete",
                "passed": 10,
                "retries": 0,
                "workers": 1,
                "report_sha256": hashlib.sha256(raw).hexdigest(),
            },
            indent=2,
        )
        + "\n"
    )


def main() -> None:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=5
        ).strip()
        assert sha == os.environ["GITHUB_SHA"]
        if sys.argv[1:] == ["start"]:
            start(ROOT, sha, datetime.now(UTC))
        else:
            assert len(sys.argv) == 3 and sys.argv[1] == "check"
            check(ROOT, sha, sys.argv[2])
    except (AssertionError, KeyError, ValueError, TypeError, OSError, subprocess.SubprocessError):
        try:
            (ROOT / OUTPUT).mkdir(parents=True, exist_ok=True)
            (ROOT / OUTPUT / "evidence.json").write_text('{"status":"incomplete"}\n')
        except OSError:
            pass
        raise SystemExit(
            "Inventory expiry repetition incomplete; inspect retained evidence"
        ) from None


if __name__ == "__main__":
    main()
