#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CheckpointArtifacts:
    source_zip: Path
    bundle: Path


def run_git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, text=True, capture_output=True)


def package_checkpoint(
    *, repo: Path, output_dir: Path, artifact_stem: str, branch: str
) -> CheckpointArtifacts:
    repo = repo.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    source_zip = output_dir / f"{artifact_stem}-source.zip"
    bundle = output_dir / f"{artifact_stem}.git.bundle"

    run_git(
        repo,
        "archive",
        "--format=zip",
        f"--prefix={artifact_stem}/",
        f"--output={source_zip}",
        "HEAD",
    )
    run_git(repo, "bundle", "create", str(bundle), "HEAD", f"refs/heads/{branch}")
    run_git(repo, "bundle", "verify", str(bundle))

    return CheckpointArtifacts(source_zip=source_zip, bundle=bundle)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--artifact-stem", required=True)
    parser.add_argument("--branch", required=True)
    args = parser.parse_args()
    artifacts = package_checkpoint(
        repo=args.repo,
        output_dir=args.output_dir,
        artifact_stem=args.artifact_stem,
        branch=args.branch,
    )
    print(artifacts.source_zip)
    print(artifacts.bundle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
