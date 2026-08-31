from __future__ import annotations

import os
import subprocess
import zipfile
from pathlib import Path

from scripts.release.package_checkpoint import package_checkpoint


def hermetic_git_env(tmp_path: Path) -> dict[str, str]:
    """Isolate test repositories from developer-global git configuration.

    Machine-level settings such as ``commit.gpgsign`` must not leak into
    disposable test repositories: they can hang commits in non-interactive
    runs or fail them outright. Pointing ``GIT_CONFIG_GLOBAL`` and
    ``GIT_CONFIG_SYSTEM`` at an empty file keeps the repositories hermetic.
    """
    empty_config = tmp_path / "git-config-empty"
    empty_config.write_text("", encoding="utf-8")
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = str(empty_config)
    env["GIT_CONFIG_SYSTEM"] = str(empty_config)
    return env


def git(repo: Path, *args: str, env: dict[str, str]) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=True, env=env
    )
    return result.stdout.strip()


def test_package_checkpoint_creates_cloneable_bundle_and_clean_source_zip(tmp_path: Path) -> None:
    env = hermetic_git_env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", env=env)
    git(repo, "config", "user.email", "test@example.invalid", env=env)
    git(repo, "config", "user.name", "Checkpoint Test", env=env)
    git(repo, "checkout", "-q", "-b", "bootstrap/v0.1", env=env)
    (repo / "README.md").write_text("checkpoint\n", encoding="utf-8")
    git(repo, "add", "README.md", env=env)
    git(repo, "commit", "-q", "-m", "test: seed checkpoint", env=env)
    expected_head = git(repo, "rev-parse", "HEAD", env=env)

    output_dir = tmp_path / "out"
    artifacts = package_checkpoint(
        repo=repo,
        output_dir=output_dir,
        artifact_stem="ocwp-checkpoint-test",
        branch="bootstrap/v0.1",
    )

    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "-q", str(artifacts.bundle), str(clone)],
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    assert git(clone, "rev-parse", "HEAD", env=env) == expected_head
    assert git(clone, "branch", "--show-current", env=env) == "bootstrap/v0.1"

    with zipfile.ZipFile(artifacts.source_zip) as archive:
        listing = archive.namelist()
    assert listing == ["ocwp-checkpoint-test/", "ocwp-checkpoint-test/README.md"]
    assert all("/.git/" not in path for path in listing)
