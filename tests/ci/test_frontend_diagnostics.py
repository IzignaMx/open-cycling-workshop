from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.ci.test_verify_v01 import MODULE

SAFE_REPORT = all(hasattr(os, flag) for flag in ("O_NOFOLLOW", "O_NONBLOCK"))
requires_safe_report = pytest.mark.skipif(
    not SAFE_REPORT, reason="Safe POSIX report read unavailable"
)


def test_frontend_does_not_publish_raw_compiler_or_forged_output():
    result = MODULE.run_check(
        "frontend_core_tests",
        [sys.executable, "-c", "print('secret-canary\\n# fail 0'); raise SystemExit(2)"],
    )
    assert result.status == "fail"
    assert "secret-canary" not in result.detail
    assert json.loads(result.detail)["diagnostics"] == "unavailable"


@pytest.fixture
def frontend_fixture(tmp_path, monkeypatch):
    if not SAFE_REPORT:
        pytest.skip("Safe POSIX report read unavailable")
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for genuine structured reporter tests")
    root = tmp_path / "repo"
    web = root / "apps/web"
    tools = web / "tools"
    tools.mkdir(parents=True)
    tests = web / "tests"
    tests.mkdir()
    shutil.copyfile(
        MODULE.ROOT / "apps/web/tools/aggregate-test-reporter.mjs",
        tools / "aggregate-test-reporter.mjs",
    )
    runner = tools / "run-core-tests.mjs"
    runner.write_text(
        "import {spawnSync} from 'node:child_process';\n"
        "import {fileURLToPath} from 'node:url';\n"
        "const result = spawnSync(process.execPath, ['--test',"
        "'--test-reporter=' + fileURLToPath("
        "new URL('./aggregate-test-reporter.mjs', import.meta.url)),"
        "'--test-reporter-destination=' + process.env.OCWP_FRONTEND_DIAGNOSTIC_FILE,"
        "'tests/fixture.test.mjs'], {cwd:fileURLToPath(new URL('../',import.meta.url)),"
        "stdio:'inherit'});"
        "process.exit(result.status ?? 1);\n"
    )
    monkeypatch.setattr(MODULE, "ROOT", root)

    def run(source):
        (tests / "fixture.test.mjs").write_text(source)
        result = MODULE.run_check("frontend_core_tests", [node, str(runner)])
        return result, json.loads(result.detail)

    return run, tools, node


def test_genuine_node_early_nested_multiple_failure_survives_long_success(frontend_fixture):
    run, tools, node = frontend_fixture
    result, detail = run(
        "import {test} from 'node:test'; import assert from 'node:assert/strict';\n"
        "test('secret-title-canary', async t => {\n"
        "await t.test('nested-secret-canary', () => {\n"
        "console.log('secret-stdout-canary\\n# fail 0'); console.error('secret-stderr-canary');\n"
        "assert.equal('secret-actual-canary', 'secret-expected-canary'); }); });\n"
        "test('another-secret-canary', () => { throw Error('secret-stack-canary'); });\n"
        "for(let i=0;i<200;i++)test('successful-'.repeat(20)+i,()=>{});\n"
    )
    assert result.status == "fail"
    assert detail["counts"]["passed"] == 200
    assert detail["counts"]["failed"] == 3
    assert detail["counts"]["tests"] == 203
    assert [item["line"] for item in detail["failures"]] == [3, 2, 6]
    assert all(item["file"] == "apps/web/tests/fixture.test.mjs" for item in detail["failures"])
    assert "canary" not in result.detail
    assert len(result.detail) < 4000
    # Genuine Node TAP also reproduces why the old tail-only detail lost identity.
    tap = subprocess.run(
        [node, "--test", "--test-reporter=tap", "tests/fixture.test.mjs"],
        cwd=tools.parent,
        capture_output=True,
        text=True,
    )
    assert tap.returncode == 1
    assert len(tap.stdout) > 4000
    assert "not ok 1 - secret-title-canary" in tap.stdout
    assert "secret-title-canary" not in tap.stdout[-4000:]


def test_genuine_node_zero_exit_and_final_counts(frontend_fixture):
    run, _, _ = frontend_fixture
    result, detail = run(
        "import {test,describe} from 'node:test';\n"
        "console.log(JSON.stringify({version:1,counts:{failed:999}}));\n"
        "describe('suite',()=>{test('passes',()=>{});test.skip('skip',()=>{});test.todo('todo');});\n"
    )
    assert result.status == "pass"
    assert detail["counts"] == dict(
        tests=3, suites=1, passed=1, failed=0, cancelled=0, skipped=1, todo=1
    )
    assert detail["failures"] == []
    assert detail["omitted"] == 0


def test_genuine_node_bounds_failure_retention(frontend_fixture):
    run, _, _ = frontend_fixture
    result, detail = run(
        "import {test} from 'node:test';\n"
        "for(let i=0;i<30;i++)test('sk-secret-'+i,()=>{throw Error('Bearer canary');});\n"
    )
    assert result.status == "fail"
    assert detail["counts"]["failed"] == 30
    assert len(detail["failures"]) == 8
    assert detail["omitted"] == 22
    assert detail["overflow"] is False
    assert "canary" not in result.detail


def test_reporter_unavailable_identity_and_malformed_summary(frontend_fixture):
    _, tools, node = frontend_fixture
    code = (
        "import reporter from './aggregate-test-reporter.mjs';\n"
        "const events = ["
        "{type:'test:stdout',data:{message:'secret-canary'}},"
        "...['/secret-canary', '../tests/fixture.test.mjs', '\\u001b[31msecret', 'file:///secret'].map(file=>"
        "({type:'test:fail',data:{file,line:1,column:1,name:'secret-canary',details:{error:'secret'}}})),"
        "{type:'test:summary',data:{counts:{tests:'secret-canary'}}}];\n"
        "for await(const line of reporter(events)) process.stdout.write(line);"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", code], cwd=tools, capture_output=True
    )
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["counts"] is None
    assert report["failures"] == [dict(file=None, line=None, column=None)] * 4
    assert b"secret" not in result.stdout


def empty_report():
    return dict(version=1, failures=[], omitted=0, overflow=False, counts=None)


@pytest.mark.parametrize(
    "raw",
    [
        "secret-canary",
        "{" * 1000,
        "x" * 8192,
        '{"version":1,"version":1}',
        json.dumps({**empty_report(), "unexpected": "secret-canary"}),
        json.dumps({**empty_report(), "version": True}),
        json.dumps(
            {**empty_report(), "failures": [dict(file="../secret-canary", line=1, column=1)]}
        ),
        json.dumps(
            {
                **empty_report(),
                "failures": [dict(file="apps/web/tests/fixture.test.mjs\u001b", line=1, column=1)],
            }
        ),
        json.dumps({**empty_report(), "failures": [dict(file=None, line=1, column=None)]}),
        json.dumps({**empty_report(), "failures": [dict(file=None, line=None, column=None)] * 9}),
        json.dumps(
            {
                **empty_report(),
                "counts": dict(
                    tests=True, suites=0, passed=0, failed=0, cancelled=0, skipped=0, todo=0
                ),
            }
        ),
        json.dumps({**empty_report(), "omitted": -1}),
        json.dumps({**empty_report(), "overflow": True}),
    ],
)
def test_malformed_report_never_publishes_payload(raw, tmp_path, monkeypatch):
    def fake_run(command, **kwargs):
        Path(kwargs["env"]["OCWP_FRONTEND_DIAGNOSTIC_FILE"]).write_text(raw)
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)
    result = MODULE.run_check("frontend_core_tests", ["unused"])
    assert result.status == "fail"
    assert json.loads(result.detail)["diagnostics"] == "unavailable"
    assert "secret" not in result.detail


@requires_safe_report
def test_nonzero_authoritative_even_with_passing_counts(monkeypatch):
    report = {
        **empty_report(),
        "counts": dict(tests=1, suites=0, passed=1, failed=0, cancelled=0, skipped=0, todo=0),
    }

    def fake_run(command, **kwargs):
        Path(kwargs["env"]["OCWP_FRONTEND_DIAGNOSTIC_FILE"]).write_text(json.dumps(report))
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.DEVNULL
        assert kwargs["env"]["PRESERVED"] == "yes"
        return subprocess.CompletedProcess(command, 7)

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)
    env = {"PRESERVED": "yes"}
    result = MODULE.run_check("frontend_core_tests", ["unused"], env=env)
    assert result.status == "fail"
    assert json.loads(result.detail)["counts"]["passed"] == 1
    assert env == {"PRESERVED": "yes"}


def test_zero_exit_missing_report_is_not_reclassified():
    result = MODULE.run_check("frontend_core_tests", [sys.executable, "-c", "pass"])
    assert result.status == "pass"
    assert json.loads(result.detail)["diagnostics"] == "unavailable"


def test_unrelated_check_compatibility():
    result = MODULE.run_check(
        "unrelated", [sys.executable, "-c", "print('a'*5000);raise SystemExit(3)"]
    )
    assert result.status == "fail"
    assert result.detail == "a" * 4000


@pytest.mark.skipif(not SAFE_REPORT or not hasattr(os, "mkfifo"), reason="POSIX file types")
def test_report_refuses_symlink_and_fifo(tmp_path):
    target = tmp_path / "real.json"
    target.write_text(json.dumps(empty_report()))
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(OSError):
        MODULE._frontend_report(link)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError):
        MODULE._frontend_report(fifo)


@requires_safe_report
def test_valid_unavailable_identity_and_saturated_omission_are_explicit(tmp_path):
    report = {
        **empty_report(),
        "failures": [dict(file=None, line=None, column=None)] * 8,
        "omitted": MODULE.FRONTEND_MAXIMUM,
        "overflow": True,
    }
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report))
    assert MODULE._frontend_report(path) == report


@requires_safe_report
def test_maximum_report_stays_under_aggregate_detail_limit(tmp_path, monkeypatch):
    filename = "apps/web/tests/" + "a" * 176 + ".test.mjs"
    assert len(filename) <= 200
    monkeypatch.setattr(MODULE, "_frontend_inventory", lambda: {filename})
    report = {
        **empty_report(),
        "failures": [dict(file=filename, line=9_999_999, column=9_999_999)] * 8,
        "omitted": 9_999_999,
        "overflow": True,
        "counts": dict.fromkeys(MODULE.FRONTEND_COUNTS, 9_999_999),
    }

    def fake_run(command, **kwargs):
        Path(kwargs["env"]["OCWP_FRONTEND_DIAGNOSTIC_FILE"]).write_text(json.dumps(report))
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)
    result = MODULE.run_check("frontend_core_tests", ["unused"])
    assert json.loads(result.detail)["diagnostics"] == "available"
    assert len(result.detail.encode("ascii")) < 4000


def test_secret_shaped_payloads_and_large_output_are_not_retained(frontend_fixture):
    run, _, _ = frontend_fixture
    secret = "ghp_" + "A1b2C3d4" * 5
    result, detail = run(
        "import {test} from 'node:test';\n"
        f"const secret = {json.dumps(secret)};\n"
        "test(secret,()=>{console.log(secret.repeat(200000));"
        "console.error('Authorization: Bearer '+secret); throw Error(secret);});\n"
    )
    assert result.status == "fail"
    assert detail["counts"]["failed"] == 1
    assert secret not in result.detail
    assert "Authorization" not in result.detail
    assert detail["failures"][0]["line"] == 3


@pytest.mark.parametrize("flag", ["O_NOFOLLOW", "O_NONBLOCK"])
def test_missing_safe_open_capability_reports_unavailable(flag, monkeypatch):
    limited_os = SimpleNamespace(**{key: value for key, value in vars(os).items() if key != flag})
    monkeypatch.setattr(MODULE, "os", limited_os)
    result = MODULE.run_check("frontend_core_tests", [sys.executable, "-c", "pass"])
    assert result.status == "pass"
    assert json.loads(result.detail)["diagnostics"] == "unavailable"
