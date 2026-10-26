import json
import os
import subprocess
import tomllib
from pathlib import Path

import pytest

from scripts.ci import security_scan


def test_policy_extends_defaults_and_only_uses_conjunctive_exact_exceptions() -> None:
    policy = tomllib.loads(Path(".gitleaks.toml").read_text())
    assert policy["extend"] == {"useDefault": True}
    assert set(policy) == {"title", "extend", "rules"}
    assert len(policy["rules"]) == 1
    rule = policy["rules"][0]
    assert rule["id"] == "generic-api-key"
    assert set(rule) == {"id", "allowlists"}
    assert len(rule["allowlists"]) == 3
    assert {(entry["paths"][0], entry["regexes"][0]) for entry in rule["allowlists"]} == {
        (
            r"^tests/operations/test_local_compose_runtime\.py$",
            r"^eyJhbGciOiJIUzI1NiJ9\.eyJzdWIiOiJhIn0\.signature$",
        ),
        (r"^README\.md$", r"^signed/revocable$"),
        (
            r"^docs/10-spec-development/execution-state\.yaml$",
            r"^may_expand_beyond_retained_utf8_bytes$",
        ),
    }
    for entry in rule["allowlists"]:
        assert entry["condition"] == "AND"
        assert entry["regexTarget"] == "secret"
        assert len(entry["paths"]) == len(entry["regexes"]) == 1
        assert entry["paths"][0].startswith("^") and entry["paths"][0].endswith("$")
        assert entry["regexes"][0].startswith("^") and entry["regexes"][0].endswith("$")
        assert set(entry) == {"description", "condition", "paths", "regexTarget", "regexes"}


def test_hosted_security_requires_actual_policy_canaries() -> None:
    workflow = Path(".github/workflows/security.yml").read_text()
    assert "python scripts/ci/check_secret_scan_policy.py" in workflow
    assert workflow.index("check_secret_scan_policy.py") < workflow.index(
        "security_scan.py secrets"
    )


def test_gitleaks_report_only_persists_content_free_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    unsafe = "NEVER_EMIT_MATCH_SECRET_CONTEXT"
    report = [
        {
            "RuleID": "generic-api-key",
            "File": "src/example.py",
            "StartLine": 4,
            "EndLine": 4,
            "Commit": "a" * 40,
            "Fingerprint": unsafe,
            "Secret": unsafe,
            "Match": unsafe,
            "Message": unsafe,
            "Author": unsafe,
            "Email": unsafe,
            "Context": unsafe,
        }
    ]

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert kwargs["capture_output"] is True
        assert "--report-format=json" in command
        assert "--report-path=-" in command
        assert "--redact=100" in command
        return subprocess.CompletedProcess(command, 1, json.dumps(report), "WRN leaks found: 1\n")

    monkeypatch.setattr(security_scan.subprocess, "run", run)
    result, findings = security_scan.execute_gitleaks(["gitleaks"], tmp_path, tmp_path)
    assert result.returncode == 1
    saved = (tmp_path / "gitleaks-findings.json").read_text()
    assert unsafe not in saved + (tmp_path / "gitleaks.log").read_text() + capsys.readouterr().out
    assert findings == [
        {
            "rule": "generic-api-key",
            "path": "src/example.py",
            "start_line": 4,
            "end_line": 4,
            "commit": "a" * 40,
            "fingerprint": "a" * 40 + ":src/example.py:generic-api-key:4",
        }
    ]
    assert set(p.name for p in tmp_path.iterdir()) == {"gitleaks-findings.json", "gitleaks.log"}


@pytest.mark.parametrize("report", ["not json", "{}", "[null]", '[{"RuleID":"bad\\nrule"}]'])
def test_malformed_report_fails_without_dumping_raw_data(report: str) -> None:
    with pytest.raises(security_scan.CoverageError):
        security_scan.safe_gitleaks_findings(report)


def test_actual_pinned_scanner_rejects_near_misses_and_other_paths(tmp_path: Path) -> None:
    from scripts.ci.check_secret_scan_policy import qualify_policy

    binary = os.environ.get("OCWP_GITLEAKS_BINARY")
    if not binary:
        pytest.skip("Actual scanner canaries are mandatory in the hosted Security workflow")
    evidence = qualify_policy(Path.cwd(), tmp_path, Path(binary))
    assert evidence["status"] == "passed"
    assert evidence["cases"] == 10


@pytest.mark.parametrize("exit_code", [0, 1])
def test_findings_remain_failure_after_safe_metadata_is_saved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_code: int
) -> None:
    from unittest.mock import Mock

    (tmp_path / ".git").mkdir()
    report = [
        {
            "RuleID": "generic-api-key",
            "File": "src/example.py",
            "StartLine": 4,
            "EndLine": 4,
            "Commit": "a" * 40,
            "Secret": "private-context",
        }
    ]
    runner = Mock(
        side_effect=[
            subprocess.CompletedProcess([], 0, "pulled"),
            subprocess.CompletedProcess([], 0, "a" * 40 + "\n12\n"),
            subprocess.CompletedProcess(
                [],
                exit_code,
                json.dumps(report),
                "INF 9 commits scanned.\nINF scanned ~2048 bytes (2.05 KB) in 1ms\n",
            ),
        ]
    )
    monkeypatch.setattr(security_scan.subprocess, "run", runner)
    output = tmp_path / "evidence"
    with pytest.raises(security_scan.CoverageError):
        security_scan.scan_secrets(tmp_path, output)
    assert "private-context" not in (output / "gitleaks-findings.json").read_text()
    assert (
        json.loads((output / "gitleaks-findings.json").read_text())[0]["path"] == "src/example.py"
    )


@pytest.mark.parametrize(
    "mutation", ["remove_exceptions", "condition_or", "broaden_path", "broaden_value"]
)
def test_actual_scanner_canaries_reject_broadened_or_missing_exceptions(
    tmp_path: Path, mutation: str
) -> None:
    from scripts.ci.check_secret_scan_policy import qualify_policy

    binary = os.environ.get("OCWP_GITLEAKS_BINARY")
    if not binary:
        pytest.skip("Actual scanner canaries are mandatory in the hosted Security workflow")
    original_policy = Path(".gitleaks.toml").read_text()
    header, *blocks = original_policy.split("[[rules.allowlists]]")
    entries = tomllib.loads(original_policy)["rules"][0]["allowlists"]
    (tmp_path / "README.md").write_text(Path("README.md").read_text())
    state_path = Path("docs/10-spec-development/execution-state.yaml")
    (tmp_path / state_path).parent.mkdir(parents=True)
    (tmp_path / state_path).write_text(state_path.read_text())
    # Mutate each exception independently without adding skipped test cases to
    # the full-Python verifier's exact five-case scanner skip contract.
    for index, entry in enumerate(entries):
        mutated_blocks = blocks.copy()
        if mutation == "remove_exceptions":
            del mutated_blocks[index]
        elif mutation == "condition_or":
            mutated_blocks[index] = blocks[index].replace('condition = "AND"', 'condition = "OR"')
        elif mutation == "broaden_path":
            mutated_blocks[index] = blocks[index].replace(entry["paths"][0], ".*", 1)
        else:
            mutated_blocks[index] = blocks[index].replace(entry["regexes"][0], ".*", 1)
        policy = header + "".join("[[rules.allowlists]]" + block for block in mutated_blocks)
        (tmp_path / ".gitleaks.toml").write_text(policy)
        with pytest.raises(security_scan.CoverageError, match="canary failed"):
            qualify_policy(tmp_path, tmp_path / "evidence", Path(binary))
