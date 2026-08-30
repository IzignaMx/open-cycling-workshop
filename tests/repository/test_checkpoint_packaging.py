from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.release.package_checkpoint import package_checkpoint


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def test_package_checkpoint_creates_cloneable_bundle_and_clean_source_zip(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Checkpoint Test")
    git(repo, "checkout", "-q", "-b", "bootstrap/v0.1")
    (repo / "README.md").write_text("checkpoint\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-q", "-m", "test: seed checkpoint")
    expected_head = git(repo, "rev-parse", "HEAD")

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
    )
    assert git(clone, "rev-parse", "HEAD") == expected_head
    assert git(clone, "branch", "--show-current") == "bootstrap/v0.1"

    listing = subprocess.run(
        ["unzip", "-Z1", str(artifacts.source_zip)],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines()
    assert listing == ["ocwp-checkpoint-test/", "ocwp-checkpoint-test/README.md"]
    assert all("/.git/" not in path for path in listing)
