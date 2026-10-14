"""Execute only the safe JSON evidence validator, never Docker or recovery."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def proofs() -> list[dict[str, object]]:
    common = {
        "authenticated_profile_smoke_tested": True,
        "stale_sessions_and_checkpoint_refused": True,
        "profiles": [{"expected_sha256": "a" * 64, "actual_sha256": "a" * 64}] * 3,
    }
    return [
        {
            **common,
            "status": "branding_restore_checked",
            "legacy_organizations_activated": 0,
            "incarnations_rotated": 2,
        },
        {
            **common,
            "status": "branding_restore_checked_with_explicit_legacy_cutover",
            "legacy_organizations_activated": 2,
            "incarnations_rotated": 3,
        },
    ]


def validate(
    tmp_path: Path, values: list[dict[str, object]], *, stale: bool = False
) -> subprocess.CompletedProcess[str]:
    for index, proof in enumerate(values):
        directory = tmp_path / "artifacts/branding-recovery" / str(index)
        directory.mkdir(parents=True)
        (directory / "branding-recovery-evidence.json").write_text(json.dumps(proof))
    script = (ROOT / "scripts/ci/run_branding_recovery.sh").read_text()
    validator = script.split("uv run python - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    return subprocess.run(
        [sys.executable, "-c", validator],
        cwd=tmp_path,
        env={**os.environ, "BRANDING_RECOVERY_STARTED_NS": str(2**63 - 1 if stale else 0)},
        capture_output=True,
        text=True,
        check=False,
    )


def test_ci_requires_both_distinct_current_floor_variants(tmp_path: Path) -> None:
    result = validate(tmp_path, proofs())
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "duplicate",
        "extra",
        "bad-status",
        "bad-activation",
        "bad-rotation",
        "bad-hash",
        "stale",
    ],
)
def test_ci_refuses_incomplete_wrong_or_stale_proof(tmp_path: Path, failure: str) -> None:
    values = proofs()
    if failure == "missing":
        values.pop()
    elif failure == "duplicate":
        values[1] = values[0]
    elif failure == "extra":
        values.append(values[0])
    elif failure == "bad-status":
        values[1]["status"] = "pending"
    elif failure == "bad-activation":
        values[1]["legacy_organizations_activated"] = 0
    elif failure == "bad-rotation":
        values[1]["incarnations_rotated"] = 2
    elif failure == "bad-hash":
        values[1]["profiles"] = [{"expected_sha256": "a" * 64, "actual_sha256": "b" * 64}] * 3
    result = validate(tmp_path, values, stale=failure == "stale")
    assert result.returncode != 0


def run_stubbed_wrapper(
    tmp_path: Path, *, parent: str = "absent", pytest_fails: bool = False
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Run shell ordering for real; never run Docker, SQL, or the recovery tests."""
    checkout = tmp_path / "checkout"
    script = checkout / "scripts/ci/run_branding_recovery.sh"
    script.parent.mkdir(parents=True)
    script.write_text((ROOT / "scripts/ci/run_branding_recovery.sh").read_text())
    if parent == "symlink":
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("untouched")
        (checkout / "artifacts").symlink_to(outside, target_is_directory=True)
    elif parent == "checkout-writable":
        checkout.chmod(0o777)
    elif parent != "absent":
        (checkout / "artifacts").mkdir(mode=0o700)
        if parent == "writable":
            (checkout / "artifacts").chmod(0o777)
        elif parent == "base-symlink":
            outside = tmp_path / "outside"
            outside.mkdir()
            (outside / "keep.txt").write_text("untouched")
            (checkout / "artifacts/branding-recovery").symlink_to(outside, target_is_directory=True)
        elif parent == "existing-public":
            (checkout / "artifacts").chmod(0o755)
    tools = tmp_path / "tools"
    tools.mkdir()
    docker = tools / "docker"
    docker.write_text(
        '#!/bin/sh\ncase "$1" in\n'
        'pull) exit 0;;\nrun) printf "pg_dump (PostgreSQL) 18.4\\n";;\n*) exit 64;;\nesac\n'
    )
    docker.chmod(0o700)
    uv = tools / "uv"
    uv.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\nfrom pathlib import Path\n"
        "if sys.argv[1:3] == ['run', 'pytest']:\n"
        "    Path('pytest-invoked').touch()\n"
        "    base = Path('artifacts/branding-recovery')\n"
        "    base.mkdir(mode=0o700)  # pytest's explicit basetemp does not create parents\n"
        f"    if {pytest_fails!r}: sys.exit(1)\n"
        f"    for index, proof in enumerate({proofs()!r}):\n"
        "        directory = base / str(index)\n"
        "        directory.mkdir()\n"
        "        (directory / 'branding-recovery-evidence.json').write_text(json.dumps(proof))\n"
        "    sys.exit(0)\n"
        "if sys.argv[1:3] == ['run', 'python']:\n"
        "    os.execv(sys.executable, [sys.executable, *sys.argv[3:]])\n"
        "sys.exit(64)\n"
    )
    uv.chmod(0o700)
    result = subprocess.run(
        ["bash", str(script)],
        cwd=checkout,
        env={
            **os.environ,
            "PATH": str(tools) + os.pathsep + os.environ["PATH"],
            "PYTHONPATH": os.pathsep.join((str(ROOT), str(ROOT / "services/platform/src"))),
            "OCWP_TEST_DATABASE_URL": "stubbed-disposable-test-only",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return result, checkout


def test_wrapper_prepares_private_artifact_parent_on_clean_checkout_before_pytest(
    tmp_path: Path,
) -> None:
    result, checkout = run_stubbed_wrapper(tmp_path)
    assert result.returncode == 0, result.stderr
    assert (checkout / "artifacts").stat().st_mode & 0o777 == 0o700
    assert (checkout / "pytest-invoked").exists()
    assert "Confirmed floor-1 and mixed-floor" in result.stdout


@pytest.mark.parametrize("parent", ["symlink", "writable", "base-symlink", "checkout-writable"])
def test_wrapper_refuses_untrusted_artifact_parent_before_pytest(
    tmp_path: Path, parent: str
) -> None:
    result, checkout = run_stubbed_wrapper(tmp_path, parent=parent)
    assert result.returncode != 0
    assert not (checkout / "pytest-invoked").exists()
    if parent in {"symlink", "base-symlink"}:
        assert (tmp_path / "outside/keep.txt").read_text() == "untouched"
        assert not (tmp_path / "outside/branding-recovery").exists()
    elif parent == "writable":
        assert (checkout / "artifacts").stat().st_mode & 0o777 == 0o777
    else:
        assert not (checkout / "artifacts").exists()


def test_wrapper_preserves_trusted_existing_parent_and_test_failure_gating(tmp_path: Path) -> None:
    result, checkout = run_stubbed_wrapper(tmp_path, parent="existing", pytest_fails=True)
    assert result.returncode != 0
    assert (checkout / "artifacts").stat().st_mode & 0o777 == 0o700
    assert (checkout / "pytest-invoked").exists()
    assert "Confirmed floor-1 and mixed-floor" not in result.stdout
    assert not list(checkout.rglob("branding-recovery-evidence.json"))


def test_wrapper_preserves_safe_existing_artifact_parent_mode(tmp_path: Path) -> None:
    result, checkout = run_stubbed_wrapper(tmp_path, parent="existing-public")
    assert result.returncode == 0, result.stderr
    assert (checkout / "artifacts").stat().st_mode & 0o777 == 0o755
