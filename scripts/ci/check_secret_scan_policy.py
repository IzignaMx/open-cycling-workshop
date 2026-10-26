#!/usr/bin/env python3
"""Exercise exact false-positive exceptions against the pinned real scanner."""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

if __package__:
    from .security_scan import (
        GITLEAKS_IMAGE,
        CoverageError,
        container_command,
        execute,
        execute_gitleaks,
        require_success,
    )
else:
    from security_scan import (
        GITLEAKS_IMAGE,
        CoverageError,
        container_command,
        execute,
        execute_gitleaks,
        require_success,
    )


def qualify_policy(root: Path, output: Path, binary: Path | None = None) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    if binary:
        version = subprocess.check_output([str(binary), "version"], text=True).strip()
        if version != "8.30.1":
            raise CoverageError("Policy qualification requires Gitleaks 8.30.1")
    else:
        require_success(
            execute(["docker", "pull", GITLEAKS_IMAGE], root, output / "policy-image.log"),
            "Policy scanner image pull",
        )
    policy = root / ".gitleaks.toml"
    fixture_path = "tests/operations/test_local_compose_runtime.py"
    # Assemble invalid synthetic input at runtime; never introduce a usable key.
    parts = [
        base64.urlsafe_b64encode(value).rstrip(b"=").decode()
        for value in (b'{"alg":"HS256"}', b'{"sub":"a"}')
    ]
    token = ".".join([*parts, "signature"])
    prose = next(
        line for line in (root / "README.md").read_text().splitlines() if "signed/revocable" in line
    )
    execution_state_path = "docs/10-spec-development/execution-state.yaml"
    execution_state_prose = next(
        line
        for line in (root / execution_state_path).read_text().splitlines()
        if line.strip().startswith("json_escaping:")
    )
    cases = [
        ("exact_invalid_fixture", fixture_path, f'token = "{token}"\n', None),
        ("changed_fixture", fixture_path, f'token = "{token}x"\n', "generic-api-key"),
        ("fixture_other_path", "src/other.py", f'token = "{token}"\n', "generic-api-key"),
        ("exact_documentation", "README.md", prose + "\n", None),
        (
            "changed_documentation",
            "README.md",
            prose.replace("signed/revocable", "signed/revocablex") + "\n",
            "generic-api-key",
        ),
        ("documentation_other_path", "OTHER.md", prose + "\n", "generic-api-key"),
        (
            "exact_execution_state_prose",
            execution_state_path,
            execution_state_prose + "\n",
            None,
        ),
        (
            "changed_execution_state_prose",
            execution_state_path,
            execution_state_prose + "x\n",
            "generic-api-key",
        ),
        (
            "execution_state_prose_other_path",
            "docs/10-spec-development/OTHER.yaml",
            execution_state_prose + "\n",
            "generic-api-key",
        ),
        (
            "default_other_rule",
            "src/other.py",
            'value = "' + "ghp_" + "AbcD0123456789" * 2 + "AbCd012345" + '"\n',
            "github-pat",
        ),
    ]
    for name, path, content, expected_rule in cases:
        with tempfile.TemporaryDirectory(prefix="ocwp-secret-policy-") as directory:
            fixture = Path(directory)
            target = fixture / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            shutil.copyfile(policy, fixture / ".gitleaks.toml")
            if binary:
                command = [str(binary), "dir", "."]
            else:
                command = container_command(fixture, "gitleaks", ["dir", "."])
            command.extend(["--exit-code=1", "--no-banner", "--no-color"])
            result, findings = execute_gitleaks(command, fixture, fixture)
            actual = {(finding["rule"], finding["path"]) for finding in findings}
            expected = {(expected_rule, path)} if expected_rule else set()
            if result.returncode != (1 if expected_rule else 0) or actual != expected:
                raise CoverageError(f"Secret policy canary failed: {name}")
            print(f"Secret policy canary passed: {name}", flush=True)
    evidence = {"status": "passed", "cases": len(cases), "scanner": GITLEAKS_IMAGE}
    (output / "policy-coverage.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--binary", type=Path, help="Optional verified native 8.30.1 binary for local QA"
    )
    args = parser.parse_args()
    root = Path.cwd().resolve()
    output = root / "artifacts" / "security"
    try:
        qualify_policy(root, output, args.binary)
    except (CoverageError, OSError, ValueError, subprocess.SubprocessError) as error:
        output.mkdir(parents=True, exist_ok=True)
        (output / "policy-coverage.json").write_text(
            json.dumps({"status": "failed", "error": str(error)}, indent=2) + "\n"
        )
        print(f"Secret policy qualification failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
