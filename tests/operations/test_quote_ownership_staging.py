"""Filesystem-only staging; fake closed validators, no network/process/DB."""

import json
from pathlib import Path

import pytest

from scripts.ci import quote_ownership_staging as stage


def validators():
    def valid(raw):
        assert json.loads(raw) == {"ok": True}

    return {name: valid for name in stage.JSON_FILES}


def tree(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    temp = tmp_path / "runner"
    temp.mkdir()
    (source / "guard-prebuild.json").write_text('{"ok":true}')
    return source, temp


def test_fixed_whitelist_only_and_fresh_stage(tmp_path):
    source, temp = tree(tmp_path)
    root, okay = stage.stage_evidence(source, temp, validators())
    assert okay and root.parent == temp
    assert json.loads((root / "guard-prebuild.json").read_text()) == {"ok": True}
    assert set(p.name for p in root.iterdir()) == {"guard-prebuild.json", "staging.json"}


@pytest.mark.parametrize(
    "kind",
    ["root_symlink", "receipt_symlink", "extra", "fifo", "hardlink", "oversize", "bad_schema"],
)
def test_unsafe_source_stages_only_fixed_refusal_no_outside_bytes(tmp_path, kind):
    source, temp = tree(tmp_path)
    outside = tmp_path / "private"
    outside.write_text("PRIVATE_CANARY")
    if kind == "root_symlink":
        source.rename(tmp_path / "original")
        source.symlink_to(tmp_path / "original", target_is_directory=True)
    if kind == "receipt_symlink":
        (source / "receipt.json").symlink_to(outside)
    if kind == "extra":
        (source / "arbitrary.json").write_text("PRIVATE_CANARY")
    if kind == "fifo":
        import os

        os.mkfifo(source / "receipt.json")
    if kind == "hardlink":
        (source / "receipt.json").hardlink_to(outside)
    if kind == "oversize":
        (source / "receipt.json").write_bytes(b"x" * 16385)
    if kind == "bad_schema":
        (source / "receipt.json").write_text('{"raw":"PRIVATE_CANARY"}')
    root, okay = stage.stage_evidence(source, temp, validators())
    assert not okay and [p.name for p in root.iterdir()] == ["staging.json"]
    text = (root / "staging.json").read_text()
    assert "PRIVATE_CANARY" not in text
    assert json.loads(text)["status"] == "unsafe_source"
    assert outside.read_text() == "PRIVATE_CANARY"


def test_known_raw_build_log_is_checked_but_never_copied(tmp_path):
    source, temp = tree(tmp_path)
    prep = source / "preparation"
    prep.mkdir()
    (prep / "preparation.txt").write_text("LOCAL_ONLY_RAW_CANARY")
    root, okay = stage.stage_evidence(source, temp, validators())
    assert okay and "LOCAL_ONLY_RAW_CANARY" not in "".join(p.read_text() for p in root.iterdir())


def test_symlink_in_ignored_raw_log_refuses(tmp_path):
    source, temp = tree(tmp_path)
    prep = source / "preparation"
    prep.mkdir()
    (prep / "preparation.txt").symlink_to(tmp_path / "outside")
    root, okay = stage.stage_evidence(source, temp, validators())
    assert not okay and [p.name for p in root.iterdir()] == ["staging.json"]


def test_root_swapped_during_validation_refuses_without_leaking(tmp_path):
    source, temp = tree(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "receipt.json").write_text("PRIVATE_CANARY")
    checks = validators()

    def swap(raw):
        source.rename(tmp_path / "original")
        source.symlink_to(outside, target_is_directory=True)

    checks["guard-prebuild.json"] = swap
    root, okay = stage.stage_evidence(source, temp, checks)
    assert not okay and [p.name for p in root.iterdir()] == ["staging.json"]


def test_unsafe_runner_parent_never_receives_files(tmp_path):
    source, temp = tree(tmp_path)
    actual = tmp_path / "actual"
    actual.mkdir()
    temp.rmdir()
    temp.symlink_to(actual, target_is_directory=True)
    with pytest.raises(stage.StagingRefusal):
        stage.stage_evidence(source, temp, validators())
    assert not list(actual.iterdir())


def test_real_guard_validator_closed_and_source_bound():
    from test_quote_ownership_actions_adapter import environment

    env = environment()
    checks = stage.validators_for_environment(env)
    valid = {"schema": 1, "phase": "prebuild", "status": "unknown_spent"}
    checks["guard-prebuild.json"](json.dumps(valid).encode())
    for change in ({"raw": "PRIVATE"}, {"schema": True}, {"phase": "setup"}):
        with pytest.raises(ValueError):
            checks["guard-prebuild.json"](json.dumps(valid | change).encode())


def test_bundle_rejects_unlinked_cleanup_digest():
    with pytest.raises(ValueError):
        stage.validate_bundle({"cleanup.json": b'{"receipt_sha256":"bad"}'})


def test_bundle_accepts_exact_copied_receipt_and_rejects_changed_bytes():
    import hashlib

    raw = b'{"receipt":"synthetic"}'
    cleanup = json.dumps({"receipt_sha256": hashlib.sha256(raw).hexdigest()}).encode()
    stage.validate_bundle({"receipt.json": raw, "cleanup.json": cleanup})
    with pytest.raises(ValueError):
        stage.validate_bundle({"receipt.json": raw + b" ", "cleanup.json": cleanup})


def test_early_cleanup_source_identity_cannot_come_from_result():
    from test_quote_ownership_actions_adapter import environment

    env = environment()
    value = dict(
        schema=1,
        kind="ocwp.quote_ownership.independent_cleanup",
        identity=None,
        expected_commit=env["GITHUB_SHA"],
        run_id=env["GITHUB_RUN_ID"],
        run_attempt=1,
        owner_manifest_present=False,
        owner_token=None,
        outcome="not_started",
        elapsed_ns=0,
        receipt_sha256=None,
    )
    check = stage.validators_for_environment(env)["cleanup.json"]
    check(json.dumps(value).encode())
    for change in (
        {"expected_commit": "c" * 40},
        {"run_id": "999"},
        {"run_attempt": 2},
        {"outcome": "verified_absent"},
        {"raw": "private"},
    ):
        with pytest.raises(ValueError):
            check(json.dumps(value | change).encode())


def test_real_receipt_uses_environment_identity():
    from test_quote_ownership_actions_adapter import environment
    from test_quote_ownership_measurement import receipt

    from scripts.ci.quote_ownership_evidence import identity_from_environment

    env = environment() | dict(
        OCWP_OWNERSHIP_WORKER_IMAGE_ID="sha256:" + "c" * 64,
        OCWP_OWNERSHIP_PG_IMAGE_ID="sha256:" + "d" * 64,
        OCWP_OWNERSHIP_NONCE="e" * 32,
    )
    expected = identity_from_environment(env)
    value = receipt.__wrapped__(expected)
    value.update(schema=2, owner_observation="accepted")
    check = stage.validators_for_environment(env)["receipt.json"]
    check(json.dumps(value).encode())
    value["identity"]["run_id"] = "999"
    with pytest.raises(ValueError):
        check(json.dumps(value).encode())


def test_workflow_uploads_only_generated_stage_not_source_tree():
    workflow = (
        Path(__file__).resolve().parents[2] / ".github/workflows/quote-ownership-measurement.yml"
    ).read_text()
    assert "path: ${{ steps.evidence.outputs.directory }}" in workflow
    assert "path: artifacts/quote-ownership/" not in workflow
    assert 'exit "$staging_status"' in workflow
    assert "continue-on-error" not in workflow


def test_directory_enumeration_stops_at_fixed_cap(monkeypatch):
    class Entries:
        count = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def __iter__(self):
            return self

        def __next__(self):
            self.count += 1
            assert self.count <= 7, "unbounded evidence enumeration"
            return type("Entry", (), {"name": str(self.count)})()

    entries = Entries()
    monkeypatch.setattr(stage.os, "scandir", lambda fd: entries)
    with pytest.raises(ValueError):
        stage._entries(42, 6)
    assert entries.count == 7


@pytest.mark.parametrize("change", ["missing", "unknown", "null_digest", "wrong_identity"])
def test_passed_receipt_requires_coherent_verified_independent_cleanup(change):
    import hashlib

    receipt = json.dumps({"status": "passed", "identity": {"run_id": "1"}}).encode()
    cleanup = {
        "outcome": "verified_absent",
        "identity": {"run_id": "1"},
        "receipt_sha256": hashlib.sha256(receipt).hexdigest(),
    }
    stage.validate_bundle({"receipt.json": receipt, "cleanup.json": json.dumps(cleanup).encode()})
    data = {"receipt.json": receipt}
    if change != "missing":
        if change == "unknown":
            cleanup["outcome"] = "unknown"
        if change == "null_digest":
            cleanup["receipt_sha256"] = None
        if change == "wrong_identity":
            cleanup["identity"] = {"run_id": "2"}
        data["cleanup.json"] = json.dumps(cleanup).encode()
    with pytest.raises(ValueError):
        stage.validate_bundle(data)
