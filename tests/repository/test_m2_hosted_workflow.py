"""Static admission contracts; these do not execute or qualify the laboratory."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def workflow() -> str:
    path = ROOT / ".github/workflows/m2-laboratory.yml"
    assert path.is_file(), "bounded M2 workflow is missing"
    return path.read_text()


def check_admission(doc: str) -> None:
    assert "types: [opened, synchronize, reopened]" in doc
    assert "workflow_dispatch:" in doc
    assert "github.event.repository.private == false" in doc
    assert "github.event.pull_request.head.repo.full_name == github.repository" in doc
    assert "github.event_name == 'workflow_dispatch'" in doc
    assert "github.ref == 'refs/heads/main'" in doc
    assert "\npermissions:\n  contents: read\n" in doc
    assert "runs-on: ubuntu-latest" in doc
    assert "timeout-minutes: 30" in doc
    for forbidden in (
        "pull_request_target",
        "\n  push:",
        "secrets.",
        "self-hosted",
        "write",
        "actions/cache",
        "docker push",
    ):
        assert forbidden not in doc


def check_source(doc: str) -> None:
    assert "ref: ${{ github.sha }}" in doc
    assert "persist-credentials: false" in doc
    assert 'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"' in doc
    assert 'tree="$(git rev-parse HEAD^{tree})"' in doc
    assert 'git archive HEAD | tar -x -C "$context"' in doc
    assert "docker build --pull --target build" in doc
    assert "infra/docker/platform.local.Dockerfile" in doc
    assert "RUN uv sync --locked --all-packages --group dev" in doc
    assert "COPY tests /app/tests" in doc and "COPY scripts /app/scripts" in doc
    assert "org.opencontainers.image.revision=$GITHUB_SHA" in doc
    assert "org.opencontainers.image.tree=$tree" in doc
    assert "docker pull postgres:18.4-trixie" in doc
    assert doc.count("docker image inspect --format '{{.Id}}'") == 3
    assert "command -v openssl" in doc
    actions = re.findall(r"uses: ([^\n]+)", doc)
    assert len(actions) == 2
    assert all(re.fullmatch(r"actions/[a-z-]+@[0-9a-f]{40} # v4", item) for item in actions)


def check_bounds(doc: str) -> None:
    assert "timeout-minutes: 9" in doc
    assert "# v4\n        timeout-minutes: 1\n        with:" in doc
    assert "timeout-minutes: 15" in doc
    assert "timeout-minutes: 2" in doc
    assert "timeout-minutes: 1" in doc
    assert (
        "timeout --signal=TERM --kill-after=10s 880s python scripts/ci/m2_lab_hosted.py run" in doc
    )
    assert '--image "$IMAGE_ID" --pg-image "$PG_IMAGE_ID"' in doc
    assert '--commit "$GITHUB_SHA" --tree "$SOURCE_TREE"' in doc
    assert doc.count('--owned "$RUNNER_TEMP/m2-owned.json"') == 2
    cleanup = doc.split("- name: Independent cleanup", 1)[1]
    assert cleanup.startswith("\n        if: ${{ always() }}")
    assert "m2_lab_hosted.py cleanup" in cleanup
    assert "--evidence artifacts/m2-hosted/cleanup.json" in cleanup
    assert "m2_lab_hosted.py evidence --directory artifacts/m2-hosted" in doc
    assert "if: ${{ always() && steps.evidence.outcome == 'success' }}" in doc
    assert "retention-days: 1" in doc
    assert "if-no-files-found: error" in doc
    assert "include-hidden-files: false" in doc
    upload = doc.split("uses: actions/upload-artifact@", 1)[1]
    assert (
        "path: |\n            artifacts/m2-hosted/result.json\n"
        "            artifacts/m2-hosted/cleanup.json" in upload
    )
    assert "1048576" in doc


def test_admission_has_no_production_or_fork_authority() -> None:
    check_admission(workflow())


def test_build_is_exact_source_locked_and_immutable() -> None:
    check_source(workflow())


def test_runtime_cleanup_and_upload_are_separately_bounded() -> None:
    check_bounds(workflow())


@pytest.mark.parametrize(
    ("original", "replacement", "check"),
    [
        ("contents: read", "contents: write", check_admission),
        ("github.event.repository.private == false", "true", check_admission),
        (
            "github.event.pull_request.head.repo.full_name == github.repository",
            "true",
            check_admission,
        ),
        ("persist-credentials: false", "persist-credentials: true", check_source),
        ("docker build --pull --target build", "docker build --target build", check_source),
        ("timeout-minutes: 15", "timeout-minutes: 60", check_bounds),
        ("if: ${{ always() }}", "if: ${{ success() }}", check_bounds),
        ("retention-days: 1", "retention-days: 90", check_bounds),
        (
            "artifacts/m2-hosted/result.json\n            artifacts/m2-hosted/cleanup.json",
            "artifacts/",
            check_bounds,
        ),
    ],
)
def test_policy_checks_reject_security_regressions(original, replacement, check) -> None:
    doc = workflow()
    assert original in doc
    with pytest.raises(AssertionError):
        check(doc.replace(original, replacement))


def test_preparation_storage_checkpoints_and_final_image_limit():
    doc = workflow()
    assert "'scripts/ci/m2_lab_*.py'" in doc
    assert "'tests/operations/test_m2_*.py'" in doc
    assert doc.count("          check_disk\n") == 2
    assert 'df --output=avail -B1 "$RUNNER_TEMP"' in doc
    assert 'test "$free_bytes" -ge 4294967296' in doc
    assert 'test "$((image_bytes + pg_bytes))" -le 4294967296' in doc
    assert doc.count("docker image inspect --format '{{.Size}}'") == 2
    assert "not a peak disk quota" in doc
