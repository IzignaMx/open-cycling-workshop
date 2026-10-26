from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/repository/publish-authoritative-bundle.sh"


def resolve_bash() -> str:
    """Return a POSIX bash executable path.

    On Windows, ``bash`` on PATH may resolve to the WSL launcher, which is a
    different environment from Git Bash and can fail to start at all in CI
    sandboxes. Prefer the bash shipped with Git for Windows, derived from the
    resolved git executable, before falling back to PATH lookup.
    """
    if sys.platform != "win32":
        return "bash"
    git_exe = shutil.which("git")
    if git_exe:
        git_bash = Path(git_exe).resolve().parent.parent / "bin" / "bash.exe"
        if git_bash.is_file():
            return str(git_bash)
    program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    candidate = Path(program_files) / "Git" / "bin" / "bash.exe"
    if candidate.is_file():
        return str(candidate)
    return "bash"


def hermetic_git_env(tmp_path: Path) -> dict[str, str]:
    """Isolate test repositories from developer-global git configuration.

    Machine-level settings such as ``commit.gpgsign`` must not leak into
    disposable test repositories: they can hang commits in non-interactive
    runs or fail them outright. Pointing ``GIT_CONFIG_GLOBAL`` and
    ``GIT_CONFIG_SYSTEM`` at an empty file keeps the repositories hermetic.
    The environment also covers git invocations performed inside the
    publish script when passed to its bash process.
    """
    empty_config = tmp_path / "git-config-empty"
    empty_config.write_text("", encoding="utf-8")
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = str(empty_config)
    env["GIT_CONFIG_SYSTEM"] = str(empty_config)
    return env


def run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None):
    try:
        return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=True)
    except subprocess.CalledProcessError as error:
        # Only this module's public synthetic repositories use this helper.
        # text=True already decoded each stream; counts below are re-encoded UTF-8.
        diagnostic: dict[str, object] = {"returncode": error.returncode}
        for name, output in (("stdout", error.stdout), ("stderr", error.stderr)):
            raw = (output or "").encode("utf-8")
            tail = raw[-2048:]
            diagnostic[name] = {
                "available": output is not None,
                "captured_utf8_bytes": len(raw) if output is not None else None,
                "retained_utf8_bytes": len(tail),
                "dropped_prefix_utf8_bytes": len(raw) - len(tail),
                "truncated": len(raw) > len(tail),
                "tail": tail.decode("utf-8", errors="replace"),
            }
        error.add_note("Public synthetic repository command output:\n" + json.dumps(diagnostic))
        raise


@pytest.mark.parametrize(
    "output",
    [None, "public synthetic output", "\u00e9" * 2049],
    ids=["unavailable", "complete", "truncated"],
)
def test_run_preserves_failure_with_bounded_public_output(tmp_path: Path, monkeypatch, output):
    error = subprocess.CalledProcessError(1, ["git", "synthetic"], output=output, stderr=output)
    env = {"SYNTHETIC": "fixture"}

    def fail(args, **kwargs):
        assert args == ("git", "synthetic")
        assert kwargs == {
            "cwd": tmp_path,
            "env": env,
            "text": True,
            "capture_output": True,
            "check": True,
        }
        raise error

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError) as caught:
        run("git", "synthetic", cwd=tmp_path, env=env)
    assert caught.value is error and error.returncode == 1
    assert len(error.__notes__) == 1
    note = json.loads(error.__notes__[0].split("\n", 1)[1])
    raw = (output or "").encode("utf-8")
    assert note["returncode"] == 1
    for name in ("stdout", "stderr"):
        assert note[name] == {
            "available": output is not None,
            "captured_utf8_bytes": len(raw) if output is not None else None,
            "retained_utf8_bytes": min(len(raw), 2048),
            "dropped_prefix_utf8_bytes": max(len(raw) - 2048, 0),
            "truncated": len(raw) > 2048,
            "tail": raw[-2048:].decode("utf-8", errors="replace"),
        }


def test_publish_script_restores_main_and_bootstrap_and_preserves_backup(tmp_path: Path) -> None:
    env = hermetic_git_env(tmp_path)
    source = tmp_path / "source"
    remote = tmp_path / "remote.git"
    bundle = tmp_path / "source.bundle"

    run("git", "init", "-b", "bootstrap/v0.1", str(source), env=env)
    run("git", "config", "user.name", "Test User", cwd=source, env=env)
    run("git", "config", "user.email", "test@example.invalid", cwd=source, env=env)
    required = [
        "README.md",
        "LICENSE",
        "AGENTS.md",
        "MANUAL-ACTIONS-CHECKLIST.md",
        "docs/10-spec-development/execution-state.yaml",
        "docs/10-spec-development/open-cycling-workshop-platform-agent-master-loop-v0.2.md",
        ".github/workflows/ci.yml",
        ".github/workflows/security.yml",
    ]
    for rel in required:
        path = source / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{rel}\n")
    run("git", "add", ".", cwd=source, env=env)
    run("git", "commit", "-m", "authoritative", cwd=source, env=env)
    authoritative = run("git", "rev-parse", "HEAD", cwd=source, env=env).stdout.strip()
    run(
        "git",
        "bundle",
        "create",
        str(bundle),
        "HEAD",
        "refs/heads/bootstrap/v0.1",
        cwd=source,
        env=env,
    )

    run("git", "init", "--bare", str(remote), env=env)
    seed = tmp_path / "seed"
    run("git", "clone", str(remote), str(seed), env=env)
    run("git", "config", "user.name", "Seed User", cwd=seed, env=env)
    run("git", "config", "user.email", "seed@example.invalid", cwd=seed, env=env)
    (seed / "README.md").write_text("partial\n")
    run("git", "add", "README.md", cwd=seed, env=env)
    run("git", "commit", "-m", "partial", cwd=seed, env=env)
    partial = run("git", "rev-parse", "HEAD", cwd=seed, env=env).stdout.strip()
    run("git", "push", "origin", "HEAD:main", cwd=seed, env=env)

    # The script verifies the bundle against its current repository before cloning.
    result = run(resolve_bash(), str(SCRIPT), str(bundle), str(remote), cwd=source, env=env)
    assert "Repository restore verified" in result.stdout

    main = run(
        "git", "--git-dir", str(remote), "rev-parse", "refs/heads/main", env=env
    ).stdout.strip()
    bootstrap = run(
        "git", "--git-dir", str(remote), "rev-parse", "refs/heads/bootstrap/v0.1", env=env
    ).stdout.strip()
    assert main == authoritative
    assert bootstrap == authoritative

    refs = run(
        "git",
        "--git-dir",
        str(remote),
        "for-each-ref",
        "--format=%(refname) %(objectname)",
        "refs/heads/pre-consolidation",
        env=env,
    ).stdout
    assert partial in refs
