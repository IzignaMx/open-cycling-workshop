#!/usr/bin/env python3
"""Fail-closed security coverage for the exact hosted checkout and locked graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

# Digest observed for the existing v8.30.1 image in Security job 116015794692.
GITLEAKS_IMAGE = (
    "zricethezav/gitleaks:v8.30.1"
    "@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f"
)
PIP_AUDIT = "pip-audit==2.9.0"
# Include detached PR merge HEAD and merge-only additions, not only branch tips.
GIT_LOG_OPTIONS = "--full-history --all HEAD -m --no-ext-diff"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class CoverageError(RuntimeError):
    """A scan has not established the intended coverage."""


def execute(command: list[str], root: Path, log_path: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900
    )
    log_path.write_text(result.stdout, encoding="utf-8")
    print(result.stdout, end="", flush=True)
    return result


def require_success(result: subprocess.CompletedProcess[str], operation: str) -> None:
    if result.returncode != 0:
        raise CoverageError(f"{operation} failed with exit code {result.returncode}")


def container_command(root: Path, entrypoint: str, arguments: list[str]) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "--read-only",
        "--network",
        "none",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--mount",
        f"type=bind,src={root},dst=/repo,readonly",
        "--workdir",
        "/repo",
        # Do not inherit the image's wildcard trust config, runner credentials,
        # HOME or Docker socket. Matching ownership makes exceptions unnecessary.
        "--env",
        "GIT_CONFIG_GLOBAL=/dev/null",
        "--env",
        "GIT_CONFIG_NOSYSTEM=1",
        "--entrypoint",
        entrypoint,
        GITLEAKS_IMAGE,
        *arguments,
    ]


def validate_gitleaks(output: str, exit_code: int) -> dict[str, int]:
    text = ANSI.sub("", output)
    if exit_code != 0 or re.search(r"\b(?:ERR|FTL)\b|fatal:", text):
        raise CoverageError(
            "Gitleaks failed or logged an error; success/clean text is insufficient"
        )
    commits = re.findall(r"\b(\d+) commits? scanned\.", text)
    scanned_bytes = re.findall(r"\bscanned ~(\d+) bytes \([^\n)]+\) in\b", text)
    if len(commits) != 1 or len(scanned_bytes) != 1:
        raise CoverageError("Gitleaks did not report unambiguous commit and byte coverage")
    if int(commits[0]) <= 0 or int(scanned_bytes[0]) <= 0:
        raise CoverageError("Gitleaks scanned no commits or bytes")
    return {"commits_scanned": int(commits[0]), "bytes_scanned": int(scanned_bytes[0])}


def scan_secrets(root: Path, output: Path) -> dict[str, object]:
    if not (root / ".git").is_dir():
        raise CoverageError(
            "Secret scanning requires a standalone full checkout, not a linked worktree"
        )
    output.mkdir(parents=True, exist_ok=True)
    pull = execute(["docker", "pull", GITLEAKS_IMAGE], root, output / "gitleaks-image.log")
    require_success(pull, "Gitleaks image pull")
    # Traverse the same patches before scanning. Never print patch contents.
    # This catches missing objects, shallow history, unreadable Git ownership,
    # and Git failures even if Gitleaks itself later returns a misleading zero.
    preflight = (
        'test "$(git rev-parse --is-shallow-repository)" = false; '
        "git rev-parse --verify HEAD; git rev-list --count --all HEAD; "
        f"git log -p -U0 {GIT_LOG_OPTIONS} > /dev/null"
    )
    checked = execute(
        container_command(root, "sh", ["-eu", "-c", preflight]),
        root,
        output / "gitleaks-preflight.log",
    )
    require_success(checked, "Full-history Git preflight")
    lines = checked.stdout.strip().splitlines()
    if len(lines) != 2 or not re.fullmatch(r"[0-9a-f]{40}", lines[0]):
        raise CoverageError("Git preflight did not identify the exact checkout")
    if not lines[1].isdigit() or int(lines[1]) <= 0:
        raise CoverageError("Git preflight found no reachable commits")
    result = execute(
        container_command(
            root,
            "gitleaks",
            [
                "git",
                "/repo",
                f"--log-opts={GIT_LOG_OPTIONS}",
                "--redact=100",
                "--exit-code=1",
                "--no-banner",
                "--no-color",
            ],
        ),
        root,
        output / "gitleaks.log",
    )
    return {
        "git_sha": lines[0],
        "image": GITLEAKS_IMAGE,
        "scope": GIT_LOG_OPTIONS,
        "reachable_commits": int(lines[1]),
        **validate_gitleaks(result.stdout, result.returncode),
    }


def canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def validate_export(lock: Path, exported: str) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """Prove lock export completeness and select every environment-active dependency."""
    from packaging.requirements import Requirement

    packages = tomllib.loads(lock.read_text(encoding="utf-8"))["package"]
    locked = set()
    for package in packages:
        source = package["source"]
        if "registry" in source:
            locked.add((canonical_name(package["name"]), package["version"]))
        elif not ("editable" in source or "virtual" in source):
            raise CoverageError(
                "Non-registry dependency requires an explicit audit coverage design"
            )
    exported_packages: set[tuple[str, str]] = set()
    active: set[tuple[str, str]] = set()
    for raw in exported.splitlines():
        line = raw.strip().removesuffix("\\").strip()
        if not line or line.startswith(("#", "--hash=")):
            continue
        requirement = Requirement(line)
        specifiers = list(requirement.specifier)
        if requirement.url or len(specifiers) != 1 or specifiers[0].operator != "==":
            raise CoverageError("Export contains an unpinned or unsupported dependency")
        dependency = (canonical_name(requirement.name), specifiers[0].version)
        exported_packages.add(dependency)
        if requirement.marker is None or requirement.marker.evaluate():
            active.add(dependency)
    if not locked or exported_packages != locked:
        raise CoverageError("Export does not exactly cover the locked third-party package versions")
    return exported_packages, active


def validate_audit(
    report: dict[str, object], exported: set[tuple[str, str]], active: set[tuple[str, str]]
) -> int:
    if not isinstance(report, dict):
        raise CoverageError("pip-audit report is not a JSON object")
    dependencies = report.get("dependencies")
    if not isinstance(dependencies, list) or not dependencies:
        raise CoverageError("pip-audit did not audit any project dependencies")
    audited = set()
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            raise CoverageError("pip-audit dependency entry is malformed")
        if not isinstance(dependency.get("name"), str) or not isinstance(
            dependency.get("version"), str
        ):
            raise CoverageError("pip-audit dependency name/version is missing")
        if dependency.get("skip_reason") or dependency.get("vulns") != []:
            raise CoverageError("pip-audit skipped a dependency or found vulnerabilities")
        audited.add((canonical_name(dependency["name"]), dependency["version"]))
    if audited != active or not audited <= exported:
        raise CoverageError(
            "pip-audit report is incomplete or differs from the exported project graph"
        )
    return len(audited)


def audit_dependencies(root: Path, output: Path) -> dict[str, object]:
    from packaging.markers import default_environment

    output.mkdir(parents=True, exist_ok=True)
    requirements = output / "python-requirements.txt"
    report = output / "pip-audit.json"
    lock = root / "uv.lock"
    lock_hash = hashlib.sha256(lock.read_bytes()).hexdigest()
    export = execute(
        [
            "uv",
            "export",
            "--locked",
            "--all-packages",
            "--all-groups",
            "--all-extras",
            "--no-emit-workspace",
            "--format",
            "requirements-txt",
            "--no-header",
            "--output-file",
            str(requirements),
        ],
        root,
        output / "python-export.log",
    )
    require_success(export, "Locked workspace export")
    if hashlib.sha256(lock.read_bytes()).hexdigest() != lock_hash:
        raise CoverageError("Dependency audit changed uv.lock")
    exported, active = validate_export(lock, requirements.read_text(encoding="utf-8"))
    inputs = {
        "tool": PIP_AUDIT,
        "uv_lock_sha256": lock_hash,
        "requirements_sha256": hashlib.sha256(requirements.read_bytes()).hexdigest(),
        "locked_packages": len(exported),
        "expected_active_package_versions": [
            f"{name}=={version}" for name, version in sorted(active)
        ],
        "marker_excluded_package_versions": [
            f"{name}=={version}" for name, version in sorted(exported - active)
        ],
        "marker_environment": default_environment(),
        "scope": "all workspace packages, groups and extras; current Python/platform markers",
        "python": sys.version.split()[0],
        "platform": sys.platform,
    }
    # Keep intended coverage even when the real audit finds vulnerabilities.
    (output / "dependency-input.json").write_text(
        json.dumps(inputs, indent=2) + "\n", encoding="utf-8"
    )
    audit = execute(
        [
            "uvx",
            "--python",
            sys.executable,
            "--from",
            PIP_AUDIT,
            "pip-audit",
            "--requirement",
            str(requirements),
            "--require-hashes",
            "--disable-pip",
            "--strict",
            "--format",
            "json",
            "--output",
            str(report),
        ],
        root,
        output / "pip-audit.log",
    )
    require_success(audit, "Project dependency audit")
    count = validate_audit(json.loads(report.read_text(encoding="utf-8")), exported, active)
    if hashlib.sha256(lock.read_bytes()).hexdigest() != lock_hash:
        raise CoverageError("Dependency audit changed uv.lock")
    return {
        **inputs,
        "audited_packages": count,
        "audited_package_versions": [f"{name}=={version}" for name, version in sorted(active)],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scan", choices=("secrets", "dependencies"))
    args = parser.parse_args()
    root = Path.cwd().resolve()
    output = root / "artifacts" / "security"
    output.mkdir(parents=True, exist_ok=True)
    evidence: dict[str, object] = {"status": "failed", "scan": args.scan}
    try:
        scan = scan_secrets if args.scan == "secrets" else audit_dependencies
        evidence.update(scan(root, output))
        evidence["status"] = "passed"
    except (CoverageError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        evidence["error"] = str(error)
        print(f"Security coverage failed: {error}", file=sys.stderr)
    (output / f"{args.scan}-coverage.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
