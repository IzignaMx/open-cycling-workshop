"""Actual Playwright reporter regression without a browser, account or app server."""

from __future__ import annotations

import base64
import io
import json
import os
import re
import shutil
import subprocess
import uuid
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "apps/web"


def test_failed_inventory_native_http_never_enters_nested_html_steps(tmp_path: Path) -> None:
    node = shutil.which("node")
    package = WEB / "node_modules/@playwright/test"
    if not node or not package.exists():
        pytest.skip("Installed Node/Playwright required for actual report-only privacy regression")
    module = str(package.resolve())
    helper = (WEB / "e2e/helpers/inventory-http.mjs").as_uri()
    config = tmp_path / "playwright.config.cjs"
    config.write_text(
        "const { defineConfig } = require(" + json.dumps(module) + ");\n"
        "module.exports = defineConfig({testDir: __dirname, testMatch: 'privacy.spec.cjs', "
        "workers: 1, retries: 0, timeout: 5000, outputDir: "
        + json.dumps(str(tmp_path / "results"))
        + ", reporter: [['line'], ['json', {outputFile: "
        + json.dumps(str(tmp_path / "report.json"))
        + "}], ['html', {open: 'never', outputFolder: "
        + json.dumps(str(tmp_path / "html"))
        + "}]], use: {trace: 'off', video: 'off', screenshot: 'off'}});\n"
    )
    (tmp_path / "privacy.spec.cjs").write_text(
        "const { test } = require(" + json.dumps(module) + ");\n"
        "test('safe native fixture failure without browser', async () => {\n"
        "const { fixtureHttp } = await import(" + json.dumps(helper) + ");\n"
        "await fixtureHttp('http://127.0.0.1:1', '/api/v1/auth/login', {method: 'POST', "
        "headers: {Authorization: 'Bearer ' + process.env.OCWP_REPORT_CANARY}, "
        "body: JSON.stringify({password: process.env.OCWP_REPORT_CANARY})});\n});\n"
    )
    canary = uuid.uuid4().hex
    result = subprocess.run(
        [node, str(package / "cli.js"), "test", "--config", str(config)],
        cwd=WEB,
        env={**os.environ, "OCWP_REPORT_CANARY": canary},
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 1, "Expected exactly one safe synthetic fixture failure"
    assert b"Inventory fixture HTTP failed" in result.stdout + result.stderr
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["stats"]["unexpected"] == 1
    html = (tmp_path / "html/index.html").read_text()
    embedded = re.search(r"data:application/zip;base64,([A-Za-z0-9+/=]+)", html)
    assert embedded, "Actual HTML report ZIP was not inspected"
    emitted = [result.stdout, result.stderr, json.dumps(report).encode(), html.encode()]
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(embedded.group(1)))) as archive:
        emitted.extend(archive.read(name) for name in archive.namelist())
    # Check boolean only: a failed regression must not echo the runtime canary.
    assert not any(canary.encode() in output for output in emitted), (
        "Private fixture data in report"
    )
