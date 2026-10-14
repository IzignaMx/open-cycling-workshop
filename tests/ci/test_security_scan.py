import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts.ci import security_scan


def test_secret_gate_runs_checked_owner_matched_history_scan() -> None:
    workflow = Path(".github/workflows/security.yml").read_text()
    assert "fetch-depth: 0" in workflow
    assert "persist-credentials: false" in workflow
    assert "python scripts/ci/security_scan.py secrets" in workflow
    assert "uses: docker://zricethezav/gitleaks" not in workflow
    assert "continue-on-error" not in workflow


def test_dependency_gate_requires_project_lock_input_and_saved_evidence() -> None:
    workflow = Path(".github/workflows/security.yml").read_text()
    assert "python scripts/ci/security_scan.py dependencies" in workflow
    assert "run: uvx pip-audit" not in workflow
    assert "name: security-coverage-${{ github.sha }}" in workflow
    assert "path: artifacts/security/" in workflow
    assert "if: always()" in workflow


GOOD_LOG = "12:00PM INF 9 commits scanned.\n12:00PM INF scanned ~2048 bytes (2.05 KB) in 10ms\n"


@pytest.mark.parametrize(
    "output,exit_code",
    [
        (GOOD_LOG, 1),
        ("ERR [git] fatal: detected dubious ownership\n" + GOOD_LOG, 0),
        ("ERR failed to scan Git repository\n" + GOOD_LOG, 0),
        ("0 commits scanned.\nscanned ~0 bytes (0) in 1ms\nno leaks found", 0),
        ("9 commits scanned.\nscanned ~0 bytes (0) in 1ms\nno leaks found", 0),
        ("no leaks found", 0),
        ("9 commits scanned.\n", 0),
        ("scanned ~2048 bytes (2.05 KB) in 1ms\n", 0),
        (GOOD_LOG + "FTL aborted\n", 0),
        (GOOD_LOG + "fatal: aborted\n", 0),
        (GOOD_LOG + GOOD_LOG, 0),
        ("9 commits scanned.\nscanned ~2048 bytes (2.05 KB)\npartial scan completed", 0),
    ],
)
def test_gitleaks_rejects_failed_empty_or_unproven_scan(output: str, exit_code: int) -> None:
    with pytest.raises(security_scan.CoverageError):
        security_scan.validate_gitleaks(output, exit_code)


def test_gitleaks_accepts_nonempty_error_free_scan() -> None:
    assert security_scan.validate_gitleaks(GOOD_LOG, 0) == {
        "commits_scanned": 9,
        "bytes_scanned": 2048,
    }


def test_container_runs_as_owner_without_trust_exception_or_credentials(tmp_path: Path) -> None:
    command = security_scan.container_command(tmp_path, "git", ["rev-parse", "HEAD"])
    import os

    assert command[command.index("--user") + 1] == f"{os.getuid()}:{os.getgid()}"
    assert f"type=bind,src={tmp_path},dst=/repo,readonly" in command
    assert "GIT_CONFIG_GLOBAL=/dev/null" in command
    assert "GIT_CONFIG_NOSYSTEM=1" in command
    assert "--read-only" in command
    assert command[command.index("--network") + 1] == "none"
    assert "safe.directory" not in " ".join(command)
    assert "docker.sock" not in " ".join(command)
    assert "GITHUB_TOKEN" not in " ".join(command)
    assert "@sha256:" in security_scan.GITLEAKS_IMAGE


def test_scan_preflight_and_scanner_cover_all_refs_detached_head_and_merges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    runner = Mock(
        side_effect=[
            subprocess.CompletedProcess([], 0, "pulled"),
            subprocess.CompletedProcess([], 0, "a" * 40 + "\n12\n"),
            subprocess.CompletedProcess([], 0, "[]", GOOD_LOG),
        ]
    )
    monkeypatch.setattr(security_scan.subprocess, "run", runner)
    evidence = security_scan.scan_secrets(tmp_path, tmp_path / "evidence")
    preflight = runner.call_args_list[1].args[0]
    scanner = runner.call_args_list[2].args[0]
    assert "--is-shallow-repository" in preflight[-1]
    assert "git log -p -U0 " + security_scan.GIT_LOG_OPTIONS in preflight[-1]
    assert security_scan.GIT_LOG_OPTIONS == "--full-history --all HEAD -m --no-ext-diff"
    assert "--log-opts=" + security_scan.GIT_LOG_OPTIONS in scanner
    assert "--redact=100" in scanner
    assert "--verbose" not in scanner
    assert evidence["git_sha"] == "a" * 40
    assert evidence["reachable_commits"] == 12
    assert evidence["commits_scanned"] == 9


def test_failed_preflight_never_runs_scanner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    runner = Mock(
        side_effect=[
            subprocess.CompletedProcess([], 0, "pulled"),
            subprocess.CompletedProcess([], 128, "fatal: unreadable object"),
        ]
    )
    monkeypatch.setattr(security_scan.subprocess, "run", runner)
    with pytest.raises(security_scan.CoverageError):
        security_scan.scan_secrets(tmp_path, tmp_path / "evidence")
    assert runner.call_count == 2


def test_secret_scan_rejects_external_worktree_gitdir(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text("gitdir: /not/mounted")
    with pytest.raises(security_scan.CoverageError, match="standalone"):
        security_scan.scan_secrets(tmp_path, tmp_path / "evidence")


def write_lock(root: Path) -> None:
    (root / "uv.lock").write_text(
        '[[package]]\nname = "fastapi"\nversion = "1.0.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        '[[package]]\nname = "colorama"\nversion = "0.4.6"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        '[[package]]\nname = "local-project"\nversion = "0.1.0"\n'
        'source = { editable = "services/platform" }\n'
    )


EXPORT = (
    "fastapi==1.0.0 \\\n    --hash=sha256:abc\n"
    "colorama==0.4.6 ; sys_platform == 'win32' \\\n    --hash=sha256:def\n"
)


@pytest.mark.parametrize(
    "export", ["", "# empty\n", "fastapi==1.0.0\n", EXPORT.replace("1.0.0", "9.0.0")]
)
def test_export_rejects_empty_incomplete_or_drifted_graph(tmp_path: Path, export: str) -> None:
    write_lock(tmp_path)
    with pytest.raises(security_scan.CoverageError):
        security_scan.validate_export(tmp_path / "uv.lock", export)


def test_dependency_audit_exports_locked_workspace_and_supplies_that_exact_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_lock(tmp_path)
    commands = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[0] == "uv":
            Path(command[command.index("--output-file") + 1]).write_text(EXPORT)
        else:
            Path(command[command.index("--output") + 1]).write_text(
                json.dumps({"dependencies": [{"name": "fastapi", "version": "1.0.0", "vulns": []}]})
            )
        return subprocess.CompletedProcess(command, 0, "")

    monkeypatch.setattr(security_scan.subprocess, "run", run)
    result = security_scan.audit_dependencies(tmp_path, tmp_path / "evidence")
    export, audit = commands
    for flag in (
        "--locked",
        "--all-packages",
        "--all-groups",
        "--all-extras",
        "--no-emit-workspace",
    ):
        assert flag in export
    assert audit[audit.index("--requirement") + 1] == export[export.index("--output-file") + 1]
    for flag in ("--require-hashes", "--disable-pip", "--strict"):
        assert flag in audit
    assert "pip-audit==2.9.0" in audit
    import sys

    assert audit[audit.index("--python") + 1] == sys.executable
    assert "--fix" not in audit
    assert result["locked_packages"] == 2
    assert result["audited_packages"] == 1
    assert result["audited_package_versions"] == ["fastapi==1.0.0"]
    assert result["marker_excluded_package_versions"] == ["colorama==0.4.6"]
    assert result["marker_environment"]["sys_platform"] == "linux"
    assert (
        result["uv_lock_sha256"] == hashlib.sha256((tmp_path / "uv.lock").read_bytes()).hexdigest()
    )


@pytest.mark.parametrize(
    "dependencies",
    [
        [],
        [None],
        [{"name": "fastapi", "version": 123, "vulns": []}],
        [{"name": "pip-audit", "version": "2.9.0", "vulns": []}],
        [{"name": "fastapi", "skip_reason": "missing"}],
        [{"name": "fastapi", "version": "9.0.0", "vulns": []}],
        [{"name": "fastapi", "version": "1.0.0", "vulns": [{"id": "synthetic"}]}],
        [{"name": "colorama", "version": "0.4.6", "vulns": []}],
    ],
)
def test_audit_report_rejects_empty_ambient_skipped_vulnerable_or_missing_graph(
    dependencies: list,
) -> None:
    with pytest.raises(security_scan.CoverageError):
        security_scan.validate_audit(
            {"dependencies": dependencies},
            {("fastapi", "1.0.0"), ("colorama", "0.4.6")},
            {("fastapi", "1.0.0")},
        )


def test_history_options_include_root_side_branch_merge_only_and_detached_head(
    tmp_path: Path,
) -> None:
    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True)

    def commit(filename: str) -> None:
        (tmp_path / filename).write_text(f"synthetic coverage marker in {filename}\n")
        git("add", filename)
        git("commit", "-m", filename)

    git("init", "-b", "main")
    git("config", "user.name", "Synthetic Test")
    git("config", "user.email", "test@example.invalid")
    commit("root.txt")
    git("checkout", "-b", "side")
    commit("side.txt")
    git("checkout", "main")
    commit("main.txt")
    git("merge", "--no-ff", "--no-commit", "side")
    commit("merge-only.txt")
    git("checkout", "--detach")
    commit("detached.txt")
    patches = git("log", "-p", "-U0", *security_scan.GIT_LOG_OPTIONS.split())
    for filename in ("root.txt", "side.txt", "main.txt", "merge-only.txt", "detached.txt"):
        assert f"+synthetic coverage marker in {filename}" in patches


@pytest.mark.parametrize(
    "failure", ["export_exit", "lock_changed", "missing_package", "audit_exit"]
)
def test_dependency_failures_cannot_be_reported_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    write_lock(tmp_path)
    commands = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[0] == "uv":
            if failure == "export_exit":
                return subprocess.CompletedProcess(command, 2, "stale lock")
            Path(command[command.index("--output-file") + 1]).write_text(
                "" if failure == "missing_package" else EXPORT
            )
            if failure == "lock_changed":
                with (tmp_path / "uv.lock").open("a") as lock:
                    lock.write("\n# changed\n")
            return subprocess.CompletedProcess(command, 0, "")
        return subprocess.CompletedProcess(command, 1, "vulnerabilities or audit failure")

    monkeypatch.setattr(security_scan.subprocess, "run", run)
    with pytest.raises(security_scan.CoverageError):
        security_scan.audit_dependencies(tmp_path, tmp_path / "evidence")
    assert len(commands) == (2 if failure == "audit_exit" else 1)


def test_active_environment_marker_is_required_in_audit_report(tmp_path: Path) -> None:
    write_lock(tmp_path)
    exported, active = security_scan.validate_export(
        tmp_path / "uv.lock", EXPORT.replace("sys_platform == 'win32'", "python_version >= '3.0'")
    )
    assert active == exported
    with pytest.raises(security_scan.CoverageError):
        security_scan.validate_audit(
            {"dependencies": [{"name": "fastapi", "version": "1.0.0", "vulns": []}]},
            exported,
            active,
        )
