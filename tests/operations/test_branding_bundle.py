"""Snapshot/coherence and refusal tests; mocks are not PostgreSQL restore proof."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.database import backup_postgres as postgres
from scripts.database import branding_bundle as branding


def metadata() -> dict[str, object]:
    return {
        "postgres_version_num": 180004,
        "schema_revisions": postgres._schema_heads(),
        "tables": [
            {"schema": "public", "name": "alembic_version", "rows": 1},
            {"schema": "public", "name": "workshop_brand_profiles", "rows": 1},
        ],
    }


def snapshot() -> dict[str, object]:
    return {
        "organizations": [
            {
                "organization_id": "synthetic-org",
                "dataset_incarnation": "00000000-0000-4000-8000-000000000001",
                "minimum_write_protocol": 1,
            }
        ],
        "profiles": [
            {
                "organization_id": "synthetic-org",
                "location_id": "synthetic-location",
                "schema_version": 1,
                "version": 2,
                "display_name": "Synthetic workshop",
                "palette_id": "bosque",
                "logo_key": None,
                "logo_sha256": None,
                "logo_byte_count": None,
                "logo_width": None,
                "logo_height": None,
                "updated_at": "2026-10-14T12:00:00+00:00",
                "updated_by": "synthetic-owner",
            }
        ],
    }


class Runner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, command: list[str], *, env: dict[str, str]) -> None:
        self.calls.append(command)
        if command[0] == "pg_dump":
            Path(command[command.index("--file") + 1]).write_bytes(b"PGDMP synthetic archive")


@pytest.fixture
def bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execution_options.return_value = connection
    connection.execute.return_value.scalar_one.return_value = "00000003-00000001-1"
    monkeypatch.setattr(postgres, "_database_metadata", lambda connection: metadata())
    monkeypatch.setattr(branding, "_snapshot_metadata", lambda connection: snapshot())
    return branding.create_branding_bundle(
        "postgresql://user@localhost/source",
        tmp_path / "generation",
        asset_root=tmp_path / "source-assets",
        runner=Runner(),
        engine_factory=lambda *args, **kwargs: engine,
    )


def test_branding_manifest_last_and_postgres_compatibility(bundle: Path) -> None:
    manifest = branding.verify_branding_bundle(bundle, runner=Runner())["manifest"]
    assert manifest["scope"] == "postgresql-and-branding-assets"
    assert manifest["profiles"] == snapshot()["profiles"]
    assert manifest["restore_tested"] is False
    assert (
        manifest["postgres_manifest_sha256"]
        == hashlib.sha256((bundle / "postgres" / "manifest.json").read_bytes()).hexdigest()
    )
    db_only = postgres.verify_backup_bundle(bundle / "postgres", runner=Runner())
    assert db_only["manifest"]["scope"] == "postgresql-only"


@pytest.mark.parametrize(
    "change",
    [
        {"format_version": True},
        {"scope": "all-data"},
        {"restore_tested": True},
        {"unexpected": "not supported"},
        {"postgres_manifest_sha256": "../outside"},
        {"organizations": []},
        {"profiles": [{"organization_id": "../outside"}]},
    ],
)
def test_closed_manifest_refuses_invalid_before_pg_commands(
    bundle: Path, change: dict[str, object]
) -> None:
    path = bundle / branding.MANIFEST_NAME
    manifest = json.loads(path.read_text())
    manifest.update(change)
    path.write_text(json.dumps(manifest))
    runner = Runner()
    with pytest.raises(postgres.BackupError, match="manifest"):
        branding.verify_branding_bundle(bundle, runner=runner)
    assert not runner.calls


def test_manifest_rejects_duplicate_keys(bundle: Path) -> None:
    path = bundle / branding.MANIFEST_NAME
    raw = path.read_text()
    path.write_text(raw.replace('"format_version": 1', '"format_version": 1, "format_version": 1'))
    with pytest.raises(postgres.BackupError, match="manifest"):
        branding.verify_branding_bundle(bundle, runner=Runner())


def test_manifest_symlinks_and_parent_symlinks_are_refused(bundle: Path, tmp_path: Path) -> None:
    alias = tmp_path / "alias"
    alias.symlink_to(bundle, target_is_directory=True)
    with pytest.raises(postgres.BackupError, match="unsafe"):
        branding.verify_branding_bundle(alias, runner=Runner())
    path = bundle / branding.MANIFEST_NAME
    outside = tmp_path / "outside-manifest.json"
    path.rename(outside)
    path.symlink_to(outside)
    with pytest.raises(postgres.BackupError, match="unsafe"):
        branding.verify_branding_bundle(bundle, runner=Runner())


def test_changed_nested_manifest_refused_before_pg_commands(bundle: Path) -> None:
    path = bundle / "postgres" / "manifest.json"
    path.write_text(path.read_text() + "\n")
    runner = Runner()
    with pytest.raises(postgres.BackupError, match="integrity"):
        branding.verify_branding_bundle(bundle, runner=runner)
    assert not runner.calls


def test_restore_refuses_populated_assets_before_restoring_sql(
    bundle: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "target-assets"
    root.mkdir()
    (root / "preserved").write_bytes(b"existing data")
    restore = MagicMock()
    monkeypatch.setattr(postgres, "restore_backup_bundle", restore)
    with pytest.raises(postgres.BackupError, match=r"fresh|empty"):
        branding.restore_branding_bundle(
            bundle,
            "postgresql://user@localhost/target",
            asset_root=root,
            confirm_empty_target=True,
            runner=Runner(),
        )
    assert not restore.called
    assert (root / "preserved").read_bytes() == b"existing data"


def test_restore_profile_mismatch_never_rotates_incarnation(
    bundle: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(postgres, "restore_backup_bundle", lambda *a, **kw: {})
    changed = copy.deepcopy(snapshot())
    changed["profiles"][0]["display_name"] = "Wrong restored value"
    monkeypatch.setattr(branding, "_snapshot_metadata", lambda connection: changed)
    rotate = MagicMock()
    monkeypatch.setattr(branding, "recover_cutover", rotate)
    with pytest.raises(postgres.BackupError, match=r"metadata.*differ"):
        branding.restore_branding_bundle(
            bundle,
            "postgresql://user@localhost/target",
            asset_root=tmp_path / "target-assets",
            confirm_empty_target=True,
            runner=Runner(),
            engine_factory=lambda *args, **kwargs: MagicMock(),
        )
    assert not rotate.called


def test_restore_verifies_metadata_before_exact_incarnation_rotation(
    bundle: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(postgres, "restore_backup_bundle", lambda *a, **kw: {})
    rotate = MagicMock(return_value={"changed": True})
    monkeypatch.setattr(branding, "recover_cutover", rotate)
    result = branding.restore_branding_bundle(
        bundle,
        "postgresql://user@localhost/target",
        asset_root=tmp_path / "target-assets",
        confirm_empty_target=True,
        runner=Runner(),
        engine_factory=lambda *args, **kwargs: MagicMock(),
    )
    assert result["status"] == "branding_restore_checked"
    assert result["application_smoke_tested"] is False
    assert result["incarnations_rotated"] == 1
    assert rotate.call_args.kwargs == {
        "organization_id": "synthetic-org",
        "expected_incarnation": "00000000-0000-4000-8000-000000000001",
    }
    assert rotate.call_args.args[0].database_url == "postgresql://user@localhost/target"


def test_sql_restore_failure_cannot_claim_success_or_rotate(
    bundle: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        postgres, "restore_backup_bundle", MagicMock(side_effect=postgres.BackupError("isolate"))
    )
    rotate = MagicMock()
    monkeypatch.setattr(branding, "recover_cutover", rotate)
    with pytest.raises(postgres.BackupError):
        branding.restore_branding_bundle(
            bundle,
            "postgresql://user@localhost/target",
            asset_root=tmp_path / "target-assets",
            confirm_empty_target=True,
            runner=Runner(),
        )
    assert not rotate.called


def synthetic_png(color: bytes = b"\x10\x40\x80\xff") -> bytes:
    import struct
    import zlib

    def chunk(kind: bytes, payload: bytes = b"") -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0" + color))
        + chunk(b"IEND")
    )


def with_logo(root: Path, profile: dict[str, object], data: bytes) -> dict[str, object]:
    from cycling_workshop.branding.assets import BrandingAssetStore
    from cycling_workshop.branding.images import CanonicalLogo

    digest = hashlib.sha256(data).hexdigest()
    key = BrandingAssetStore(root).put(
        profile["organization_id"], CanonicalLogo(data, digest, len(data), 1, 1)
    )
    return profile | {
        "logo_key": key,
        "logo_sha256": digest,
        "logo_byte_count": len(data),
        "logo_width": 1,
        "logo_height": 1,
    }


@pytest.fixture
def asset_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, bytes]:
    state = snapshot()
    data = synthetic_png()
    root = tmp_path / "source-assets"
    state["profiles"][0] = with_logo(root, state["profiles"][0], data)
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execution_options.return_value = connection
    connection.execute.return_value.scalar_one.return_value = "00000003-00000001-1"
    monkeypatch.setattr(postgres, "_database_metadata", lambda connection: metadata())
    monkeypatch.setattr(branding, "_snapshot_metadata", lambda connection: copy.deepcopy(state))
    directory = tmp_path / "asset-generation"
    branding.create_branding_bundle(
        "postgresql://user@localhost/source",
        directory,
        asset_root=root,
        runner=Runner(),
        engine_factory=lambda *args, **kwargs: engine,
    )
    return directory, data


def asset_path(directory: Path) -> Path:
    manifest = json.loads((directory / branding.MANIFEST_NAME).read_text())
    profile = manifest["profiles"][0]
    namespace = hashlib.sha256(profile["organization_id"].encode()).hexdigest()
    return directory / "assets" / namespace / profile["logo_key"]


def test_every_asset_verified_and_corruption_refused_before_commands(
    asset_bundle: tuple[Path, bytes],
) -> None:
    directory, data = asset_bundle
    assert asset_path(directory).read_bytes() == data
    assert branding.verify_branding_bundle(directory, runner=Runner())["status"] == (
        "branding_integrity_checked_not_restored"
    )
    asset_path(directory).write_bytes(b"x" * len(data))
    runner = Runner()
    with pytest.raises(postgres.BackupError, match="integrity"):
        branding.verify_branding_bundle(directory, runner=runner)
    assert not runner.calls


@pytest.mark.parametrize("change", ["missing", "symlink", "oversized", "directory"])
def test_unsafe_asset_refused(
    asset_bundle: tuple[Path, bytes], change: str, tmp_path: Path
) -> None:
    directory, data = asset_bundle
    path = asset_path(directory)
    path.unlink()
    if change == "symlink":
        outside = tmp_path / "outside-logo"
        outside.write_bytes(data)
        path.symlink_to(outside)
    elif change == "oversized":
        path.write_bytes(b"x" * (branding.MAX_ASSET_BYTES + 1))
    elif change == "directory":
        path.mkdir()
    with pytest.raises(postgres.BackupError, match="integrity"):
        branding.verify_branding_bundle(directory, runner=Runner())


def test_changed_dimensions_refused_even_with_valid_digest(
    asset_bundle: tuple[Path, bytes],
) -> None:
    directory, _data = asset_bundle
    path = directory / branding.MANIFEST_NAME
    manifest = json.loads(path.read_text())
    manifest["profiles"][0]["logo_width"] = 2
    path.write_text(json.dumps(manifest))
    with pytest.raises(postgres.BackupError, match="integrity"):
        branding.verify_branding_bundle(directory, runner=Runner())


@pytest.mark.parametrize("key", ["../outside", "/absolute", "ff/" + "0" * 64, "ab/../outside"])
def test_manifest_cannot_select_arbitrary_asset_paths(
    asset_bundle: tuple[Path, bytes], key: str
) -> None:
    directory, _data = asset_bundle
    path = directory / branding.MANIFEST_NAME
    manifest = json.loads(path.read_text())
    manifest["profiles"][0]["logo_key"] = key
    path.write_text(json.dumps(manifest))
    with pytest.raises(postgres.BackupError, match="manifest"):
        branding.verify_branding_bundle(directory, runner=Runner())


def test_later_live_update_cannot_change_snapshot_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "live-assets"
    before, later = synthetic_png(), synthetic_png(b"\xff\0\0\xff")
    state = snapshot()
    state["profiles"][0] = with_logo(root, state["profiles"][0], before)
    original = copy.deepcopy(state)
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execution_options.return_value = connection
    connection.execute.return_value.scalar_one.return_value = "00000003-00000001-1"
    observations: list[object] = []

    def observe(current: object) -> dict[str, object]:
        observations.append(current)
        assert not connection.begin.return_value.__exit__.called
        return copy.deepcopy(state)

    monkeypatch.setattr(postgres, "_database_metadata", lambda connection: metadata())
    monkeypatch.setattr(branding, "_snapshot_metadata", observe)
    normal_runner = Runner()

    def write_after_snapshot(command: list[str], *, env: dict[str, str]) -> None:
        if command[0] == "pg_dump":
            assert observations == [connection]
            state["profiles"][0] = with_logo(root, state["profiles"][0], later)
            state["profiles"][0]["version"] = 3
        normal_runner(command, env=env)

    directory = branding.create_branding_bundle(
        "postgresql://user@localhost/source",
        tmp_path / "snapshot",
        asset_root=root,
        runner=write_after_snapshot,
        engine_factory=lambda *args, **kwargs: engine,
    )
    manifest = branding.verify_branding_bundle(directory, runner=Runner())["manifest"]
    assert manifest["profiles"] == original["profiles"]
    assert observations == [connection]
    assert asset_path(directory).read_bytes() == before
    assert before != later


def test_missing_source_bytes_leave_no_branding_completion_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = snapshot()
    root = tmp_path / "live-assets"
    state["profiles"][0] = with_logo(root, state["profiles"][0], synthetic_png())
    digest = state["profiles"][0]["logo_sha256"]
    (root / hashlib.sha256(b"synthetic-org").hexdigest() / digest[:2] / digest).unlink()
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execution_options.return_value = connection
    connection.execute.return_value.scalar_one.return_value = "00000003-00000001-1"
    monkeypatch.setattr(postgres, "_database_metadata", lambda connection: metadata())
    monkeypatch.setattr(branding, "_snapshot_metadata", lambda connection: copy.deepcopy(state))
    directory = tmp_path / "incomplete"
    with pytest.raises(postgres.BackupError, match="integrity"):
        branding.create_branding_bundle(
            "postgresql://user@localhost/source",
            directory,
            asset_root=root,
            runner=Runner(),
            engine_factory=lambda *args, **kwargs: engine,
        )
    assert not (directory / branding.MANIFEST_NAME).exists()
    assert (directory / "postgres" / postgres.MANIFEST_NAME).exists()
    with pytest.raises(postgres.BackupError, match="manifest"):
        branding.verify_branding_bundle(directory, runner=Runner())


def test_restored_asset_bytes_match_and_rotation_follows_checks(
    asset_bundle: tuple[Path, bytes], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory, data = asset_bundle
    manifest = branding.verify_branding_bundle(directory, runner=Runner())["manifest"]
    monkeypatch.setattr(postgres, "restore_backup_bundle", lambda *a, **kw: {})
    target = tmp_path / "restored-assets"

    def rotate(*args: object, **kwargs: object) -> dict[str, object]:
        assert branding._asset_bytes(target, manifest["profiles"][0]) == data
        return {"changed": True}

    monkeypatch.setattr(branding, "recover_cutover", rotate)
    result = branding.restore_branding_bundle(
        directory,
        "postgresql://user@localhost/target",
        asset_root=target,
        confirm_empty_target=True,
        runner=Runner(),
        engine_factory=lambda *args, **kwargs: MagicMock(),
    )
    assert result["asset_references_checked"] == 1
    assert result["profiles_checked"] == 1
    with pytest.raises(postgres.BackupError, match="not empty"):
        branding.restore_branding_bundle(
            directory,
            "postgresql://user@localhost/target",
            asset_root=target,
            confirm_empty_target=True,
            runner=Runner(),
        )


def test_restore_cannot_write_inside_backup(bundle: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    restore = MagicMock()
    monkeypatch.setattr(postgres, "restore_backup_bundle", restore)
    with pytest.raises(postgres.BackupError, match="separate"):
        branding.restore_branding_bundle(
            bundle,
            "postgresql://user@localhost/target",
            asset_root=bundle / "assets",
            confirm_empty_target=True,
            runner=Runner(),
        )
    assert not restore.called


def test_fsynced_manifest_publication_failure_is_not_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "incomplete"
    directory.mkdir()
    monkeypatch.setattr(branding.os, "link", MagicMock(side_effect=OSError("disk failure")))
    with pytest.raises(postgres.BackupError):
        branding._publish_manifest(directory, {"synthetic": True})
    assert not (directory / branding.MANIFEST_NAME).exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("version", 0),
        ("schema_version", 2),
        ("display_name", " x "),
        ("display_name", "x\x00"),
        ("display_name", "e\u0301"),
        ("display_name", "x" * 161),
        ("palette_id", "arbitrary-css"),
        ("updated_at", "2026-10-14"),
        ("organization_id", "unknown-tenant"),
        ("logo_key", "aa/" + "a" * 64),
    ],
)
def test_profile_metadata_is_closed_and_bounded(bundle: Path, field: str, value: object) -> None:
    path = bundle / branding.MANIFEST_NAME
    manifest = json.loads(path.read_text())
    manifest["profiles"][0][field] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(postgres.BackupError, match="manifest"):
        branding.verify_branding_bundle(bundle, runner=Runner())


def test_oversized_and_duplicate_profile_manifests_are_refused(bundle: Path) -> None:
    path = bundle / branding.MANIFEST_NAME
    manifest = json.loads(path.read_text())
    manifest["profiles"] *= 2
    path.write_text(json.dumps(manifest))
    with pytest.raises(postgres.BackupError, match="manifest"):
        branding.verify_branding_bundle(bundle, runner=Runner())
    path.write_bytes(b" " * (branding.MAX_MANIFEST_BYTES + 1))
    with pytest.raises(postgres.BackupError, match="oversized"):
        branding.verify_branding_bundle(bundle, runner=Runner())


def test_floor_zero_restore_refused_before_target_creation(bundle: Path, tmp_path: Path) -> None:
    path = bundle / branding.MANIFEST_NAME
    manifest = json.loads(path.read_text())
    manifest["organizations"][0]["minimum_write_protocol"] = 0
    path.write_text(json.dumps(manifest))
    target = tmp_path / "never-created"
    with pytest.raises(postgres.BackupError, match="floor-1"):
        branding.restore_branding_bundle(
            bundle,
            "postgresql://user@localhost/target",
            asset_root=target,
            confirm_empty_target=True,
            runner=Runner(),
        )
    assert not target.exists()


def test_failed_incarnation_rotation_cannot_claim_completion(
    bundle: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(postgres, "restore_backup_bundle", lambda *a, **kw: {})
    monkeypatch.setattr(branding, "recover_cutover", MagicMock(side_effect=ValueError("secret")))
    with pytest.raises(postgres.BackupError, match="isolate both targets") as caught:
        branding.restore_branding_bundle(
            bundle,
            "postgresql://user@localhost/target",
            asset_root=tmp_path / "new-target",
            confirm_empty_target=True,
            runner=Runner(),
            engine_factory=lambda *args, **kwargs: MagicMock(),
        )
    assert "secret" not in str(caught.value)


def test_restore_requires_explicit_confirmation_before_any_work(bundle: Path) -> None:
    runner = Runner()
    with pytest.raises(postgres.BackupError, match="confirm_empty_target"):
        branding.restore_branding_bundle(
            bundle,
            "postgresql://user@localhost/target",
            asset_root=bundle.parent / "target",
            runner=runner,
        )
    assert not runner.calls


def test_cli_redacts_failures_and_uses_separate_target_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = tmp_path / "synthetic-url-secret"
    secret.write_text("postgresql://user:private-synthetic@localhost/target")
    monkeypatch.delenv("OCWP_RESTORE_DATABASE_URL", raising=False)
    monkeypatch.setenv("OCWP_RESTORE_DATABASE_URL_FILE", str(secret))
    restore = MagicMock(side_effect=RuntimeError("private-synthetic"))
    monkeypatch.setattr(branding, "restore_branding_bundle", restore)
    assert (
        branding.main(
            [
                "restore",
                str(tmp_path / "bundle"),
                "--asset-root",
                str(tmp_path / "assets"),
                "--confirm-empty-target",
            ]
        )
        == 1
    )
    assert restore.call_args.args[1] == secret.read_text()
    assert restore.call_args.kwargs["confirm_empty_target"] is True
    out = capsys.readouterr()
    assert "private-synthetic" not in out.out + out.err


def test_postgres_directory_is_durable_before_outer_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    directory = tmp_path / "durable-generation"
    nested = directory / "postgres"
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execution_options.return_value = connection
    connection.execute.return_value.scalar_one.return_value = "00000003-00000001-1"
    monkeypatch.setattr(postgres, "_database_metadata", lambda connection: metadata())
    monkeypatch.setattr(branding, "_snapshot_metadata", lambda connection: snapshot())
    events: list[str] = []
    original_fsync, original_publish = os.fsync, branding._publish_manifest

    def fsync(descriptor: int) -> None:
        if nested.exists() and os.path.samestat(os.fstat(descriptor), nested.stat()):
            assert (nested / postgres.DUMP_NAME).is_file()
            assert (nested / postgres.MANIFEST_NAME).is_file()
            events.append("postgres-directory-durable")
        original_fsync(descriptor)

    def publish(path: Path, manifest: dict[str, object]) -> None:
        events.append("outer-completion")
        assert events == ["postgres-directory-durable", "outer-completion"]
        original_publish(path, manifest)

    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr(branding, "_publish_manifest", publish)
    branding.create_branding_bundle(
        "postgresql://user@localhost/source",
        directory,
        asset_root=tmp_path / "assets",
        runner=Runner(),
        engine_factory=lambda *args, **kwargs: engine,
    )
    assert events == ["postgres-directory-durable", "outer-completion"]


def test_failed_postgres_directory_fsync_never_publishes_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    directory = tmp_path / "failed-durability"
    nested = directory / "postgres"
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execution_options.return_value = connection
    connection.execute.return_value.scalar_one.return_value = "00000003-00000001-1"
    monkeypatch.setattr(postgres, "_database_metadata", lambda connection: metadata())
    monkeypatch.setattr(branding, "_snapshot_metadata", lambda connection: snapshot())
    original_fsync = os.fsync

    def fsync(descriptor: int) -> None:
        if nested.exists() and os.path.samestat(os.fstat(descriptor), nested.stat()):
            raise OSError("synthetic directory durability failure")
        original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", fsync)
    with pytest.raises(postgres.BackupError):
        branding.create_branding_bundle(
            "postgresql://user@localhost/source",
            directory,
            asset_root=tmp_path / "assets",
            runner=Runner(),
            engine_factory=lambda *args, **kwargs: engine,
        )
    assert not (directory / branding.MANIFEST_NAME).exists()


def test_writable_ancestor_refused_before_archive_commands(bundle: Path, tmp_path: Path) -> None:
    ancestor = tmp_path / "untrusted-ancestor"
    ancestor.mkdir(mode=0o777)
    ancestor.chmod(0o777)
    private = ancestor / "operator-owned"
    private.mkdir(mode=0o700)
    relocated = private / "generation"
    bundle.rename(relocated)
    runner = Runner()
    with pytest.raises(postgres.BackupError, match="unsafe"):
        branding.verify_branding_bundle(relocated, runner=runner)
    assert not runner.calls


@pytest.mark.parametrize(
    "relative", [branding.MANIFEST_NAME, "postgres/manifest.json", "postgres/database.dump"]
)
def test_writable_regular_sources_refused_before_archive_commands(
    bundle: Path, relative: str
) -> None:
    (bundle / relative).chmod(0o666)
    runner = Runner()
    with pytest.raises(postgres.BackupError, match="unsafe"):
        branding.verify_branding_bundle(bundle, runner=runner)
    assert not runner.calls


@pytest.mark.parametrize(
    "relative", [".", "postgres", branding.MANIFEST_NAME, "postgres/database.dump"]
)
def test_foreign_owned_sources_refused_before_archive_commands(
    bundle: Path, relative: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    original = os.fstat
    untrusted = (bundle / relative).stat()

    def fstat(descriptor: int) -> os.stat_result:
        details = original(descriptor)
        if os.path.samestat(details, untrusted):
            values = list(details)
            values[4] = os.geteuid() + 10000
            return os.stat_result(values)
        return details

    monkeypatch.setattr(os, "fstat", fstat)
    runner = Runner()
    with pytest.raises(postgres.BackupError, match="unsafe"):
        branding.verify_branding_bundle(bundle, runner=runner)
    assert not runner.calls


def mixed_snapshot() -> dict[str, object]:
    state = snapshot()
    state["organizations"][0]["minimum_write_protocol"] = 0
    state["organizations"] += [
        {
            "organization_id": "synthetic-org-b",
            "minimum_write_protocol": 1,
            "dataset_incarnation": "00000000-0000-4000-8000-000000000002",
        },
        {
            "organization_id": "synthetic-org-c",
            "minimum_write_protocol": 0,
            "dataset_incarnation": "00000000-0000-4000-8000-000000000003",
        },
    ]
    return state


def legacy_pairs() -> tuple[str, ...]:
    return (
        "synthetic-org=00000000-0000-4000-8000-000000000001",
        "synthetic-org-c=00000000-0000-4000-8000-000000000003",
    )


@pytest.fixture
def mixed_bundle(bundle: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    state = mixed_snapshot()
    path = bundle / branding.MANIFEST_NAME
    manifest = json.loads(path.read_text())
    manifest.update(state)
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(branding, "_snapshot_metadata", lambda connection: copy.deepcopy(state))
    return bundle


@pytest.mark.parametrize(
    "pairs,acknowledged",
    [
        ((), False),
        ((), True),
        (legacy_pairs(), False),
        (legacy_pairs()[:1], True),
        (legacy_pairs() + legacy_pairs()[:1], True),
        ((*legacy_pairs(), "extra=00000000-0000-4000-8000-000000000004"), True),
        ((legacy_pairs()[0], "synthetic-org-c=00000000-0000-4000-8000-000000000004"), True),
        ((legacy_pairs()[0], "synthetic-org-c=invalid"), True),
        ((legacy_pairs()[0], "synthetic-org-c=00000000-0000-4000-8000-00000000000A"), True),
    ],
)
def test_exact_legacy_consent_refused_before_any_target_change(
    mixed_bundle: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pairs: tuple[str, ...],
    acknowledged: bool,
) -> None:
    restore = MagicMock()
    monkeypatch.setattr(postgres, "restore_backup_bundle", restore)
    target = tmp_path / "unmodified-target"
    with pytest.raises(postgres.BackupError, match=r"legacy|floor-1"):
        branding.restore_branding_bundle(
            mixed_bundle,
            "postgresql://user@localhost/target",
            asset_root=target,
            confirm_empty_target=True,
            confirm_legacy_cutover=pairs,
            confirm_legacy_prerequisites=acknowledged,
            runner=Runner(),
        )
    assert not target.exists()
    assert not restore.called


def test_explicit_mixed_legacy_activation_follows_metadata_checks(
    mixed_bundle: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[tuple[str, str]] = []
    monkeypatch.setattr(postgres, "restore_backup_bundle", lambda *a, **kw: {})

    def observed_snapshot(connection: object) -> dict[str, object]:
        events.append(("metadata", "checked"))
        return mixed_snapshot()

    def activate(
        settings: object, *, organization_id: str, expected_incarnation: str
    ) -> dict[str, object]:
        assert settings.cutover_enabled is True
        assert settings.database_url == "postgresql://user@localhost/target"
        assert events[0] == ("metadata", "checked")
        assert f"{organization_id}={expected_incarnation}" in legacy_pairs()
        events.append(("activate", organization_id))
        return {"changed": True}

    def recover(
        settings: object, *, organization_id: str, expected_incarnation: str
    ) -> dict[str, object]:
        expected = {
            row["organization_id"]: row["dataset_incarnation"]
            for row in mixed_snapshot()["organizations"]
        }
        assert expected_incarnation == expected[organization_id]
        events.append(("recover", organization_id))
        return {"changed": True}

    monkeypatch.setattr(branding, "_snapshot_metadata", observed_snapshot)
    monkeypatch.setattr(branding, "activate_cutover", activate)
    monkeypatch.setattr(branding, "recover_cutover", recover)
    result = branding.restore_branding_bundle(
        mixed_bundle,
        "postgresql://user@localhost/target",
        asset_root=tmp_path / "target",
        confirm_empty_target=True,
        confirm_legacy_cutover=legacy_pairs(),
        confirm_legacy_prerequisites=True,
        runner=Runner(),
        engine_factory=lambda *args, **kwargs: MagicMock(),
    )
    assert events == [
        ("metadata", "checked"),
        ("activate", "synthetic-org"),
        ("recover", "synthetic-org"),
        ("recover", "synthetic-org-b"),
        ("activate", "synthetic-org-c"),
        ("recover", "synthetic-org-c"),
    ]
    assert result["legacy_organizations_activated"] == 2
    assert result["incarnations_rotated"] == 3
    assert result["status"] == "branding_restore_checked_with_explicit_legacy_cutover"


def test_legacy_activation_failure_quarantines_partial_recovery(
    mixed_bundle: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(postgres, "restore_backup_bundle", lambda *a, **kw: {})
    activate = MagicMock(side_effect=[{"changed": True}, ValueError("private fault")])
    recover = MagicMock(return_value={"changed": True})
    monkeypatch.setattr(branding, "activate_cutover", activate)
    monkeypatch.setattr(branding, "recover_cutover", recover)
    target = tmp_path / "quarantined-target"
    with pytest.raises(postgres.BackupError, match="isolate both targets"):
        branding.restore_branding_bundle(
            mixed_bundle,
            "postgresql://user@localhost/target",
            asset_root=target,
            confirm_empty_target=True,
            confirm_legacy_cutover=legacy_pairs(),
            confirm_legacy_prerequisites=True,
            runner=Runner(),
            engine_factory=lambda *args, **kwargs: MagicMock(),
        )
    assert recover.call_count == 2
    assert (target / ".ocwp-branding-restore").is_file()


def test_readonly_legacy_consent_listing_is_explicit(
    mixed_bundle: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    actual_verify = branding.verify_branding_bundle
    monkeypatch.setattr(
        branding,
        "verify_branding_bundle",
        lambda directory: actual_verify(directory, runner=Runner()),
    )
    assert branding.main(["verify", str(mixed_bundle), "--show-legacy-cutover"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["legacy_cutover_required"] == list(legacy_pairs())
    assert result["legacy_cutover_prerequisites"]
    assert branding.main(["verify", str(mixed_bundle)]) == 0
    assert "legacy_cutover_required" not in json.loads(capsys.readouterr().out)


def test_legacy_identifier_with_equals_is_preserved_and_not_uuid_coerced() -> None:
    organization = {
        "organization_id": "legacy=taller",
        "minimum_write_protocol": 0,
        "dataset_incarnation": "00000000-0000-4000-8000-000000000001",
    }
    pairs = ("legacy=taller=00000000-0000-4000-8000-000000000001",)
    assert branding._confirm_legacy_cutover([organization], pairs, True) == 1
    assert branding._legacy_pairs([organization]) == list(pairs)


@pytest.mark.parametrize(
    "incarnation_race", [False, True], ids=["completed", "changed-after-checks"]
)
def test_explicit_legacy_transition_refuses_old_sessions_checkpoints_and_clients(
    mixed_bundle: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, incarnation_race: bool
) -> None:
    """Real SQLite maintenance/auth, mocked dump restoration: not PG restore proof."""
    from dataclasses import replace

    from cycling_workshop.app import create_app
    from cycling_workshop.db.base import Base
    from cycling_workshop.db.registry import register_models
    from cycling_workshop.identity.audit import IdentityAuditRecord
    from cycling_workshop.identity.domain import Principal
    from cycling_workshop.identity.models import UserRecord
    from cycling_workshop.settings import Settings
    from cycling_workshop.shared.ids import new_id
    from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, select, text
    from sqlalchemy.orm import sessionmaker

    url = f"sqlite+pysqlite:///{tmp_path / 'synthetic-cutover.db'}"
    engine = create_engine(url)
    register_models()
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('0011')"))
    factory = sessionmaker(engine, expire_on_commit=False)
    grants = ["customers.read", "customers.write", "sync.pull", "branding.read", "branding.write"]
    state = mixed_snapshot()
    with factory.begin() as session:
        for row in state["organizations"]:
            session.add(
                OrganizationRecord(
                    id=row["organization_id"],
                    name="Synthetic",
                    dataset_incarnation=row["dataset_incarnation"],
                    minimum_write_protocol=row["minimum_write_protocol"],
                )
            )
        session.flush()
        session.add(
            LocationRecord(
                id="synthetic-location", organization_id="synthetic-org", name="Synthetic"
            )
        )
        session.add(
            UserRecord(
                id="synthetic-owner",
                organization_id="synthetic-org",
                location_id=None,
                username="synthetic",
                display_name="Preserved account",
                password_hash="synthetic-preserved-hash",
                capabilities=grants,
                is_active=True,
                is_owner=False,
                version=7,
                session_version=3,
            )
        )
    with engine.connect() as connection:
        before_accounts = [
            dict(row) for row in connection.execute(select(UserRecord.__table__)).mappings()
        ]
    settings = Settings(
        environment="test",
        database_url=url,
        cutover_enabled=True,
        auth_secret="synthetic-legacy-recovery-test-secret-at-least32",
    )
    app = create_app(settings, session_factory=factory)
    principal = Principal(
        "synthetic-owner",
        "synthetic-org",
        None,
        frozenset(grants),
        session_version=3,
        dataset_incarnation=state["organizations"][0]["dataset_incarnation"],
    )
    stale = app.state.session_tokens.issue(principal)
    legacy = app.state.session_tokens.issue(replace(principal, dataset_incarnation=None))
    headers = {"Authorization": f"Bearer {stale}", "X-OCWP-Write-Protocol": "1"}
    actual_activate, actual_recover = branding.activate_cutover, branding.recover_cutover
    monkeypatch.setattr(postgres, "restore_backup_bundle", lambda *a, **kw: {})

    def activate_after_checks(_settings: object, **kwargs: str) -> dict[str, object]:
        if incarnation_race:
            # Simulate a committed change after the restored metadata comparison,
            # before the existing maintenance transaction acquires its org lock.
            with factory.begin() as session:
                session.get(
                    OrganizationRecord, kwargs["organization_id"]
                ).dataset_incarnation = new_id()
        return actual_activate(settings, **kwargs)

    monkeypatch.setattr(branding, "activate_cutover", activate_after_checks)
    monkeypatch.setattr(
        branding, "recover_cutover", lambda _settings, **kw: actual_recover(settings, **kw)
    )
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
            assert (
                client.get(
                    "/api/v1/auth/me", headers={"Authorization": f"Bearer {legacy}"}
                ).status_code
                == 200
            )
            context = client.get(
                "/api/v1/auth/context?selected_location_id=synthetic-location", headers=headers
            )
            assert context.status_code == 200, context.text
            baseline = client.post(
                "/api/v1/sync/baselines/start",
                headers=headers,
                json={
                    "protocol": 1,
                    "selected_location_id": "synthetic-location",
                    "authorization_epoch": context.json()["authorization_epoch"],
                    "request_id": new_id(),
                },
            )
            assert baseline.status_code == 200, baseline.text
            continuation = baseline.json()["continuation"]

            def restore() -> dict[str, object]:
                return branding.restore_branding_bundle(
                    mixed_bundle,
                    "postgresql://user@localhost/synthetic-target",
                    asset_root=tmp_path / "fresh-assets",
                    confirm_empty_target=True,
                    confirm_legacy_cutover=legacy_pairs(),
                    confirm_legacy_prerequisites=True,
                    runner=Runner(),
                    engine_factory=lambda *args, **kwargs: MagicMock(),
                )

            if incarnation_race:
                with pytest.raises(postgres.BackupError, match="isolate both targets"):
                    restore()
                with factory() as session:
                    assert (
                        session.get(OrganizationRecord, "synthetic-org").minimum_write_protocol == 0
                    )
                    assert session.scalars(select(IdentityAuditRecord)).all() == []
                with engine.connect() as connection:
                    assert [
                        dict(row)
                        for row in connection.execute(select(UserRecord.__table__)).mappings()
                    ] == before_accounts
                assert (tmp_path / "fresh-assets" / ".ocwp-branding-restore").is_file()
                return
            result = restore()
            assert result["legacy_organizations_activated"] == 2
            for old in (stale, legacy):
                assert (
                    client.get(
                        "/api/v1/auth/me", headers={"Authorization": f"Bearer {old}"}
                    ).status_code
                    == 401
                )
            with factory() as session:
                current = session.get(OrganizationRecord, "synthetic-org")
                fresh = app.state.session_tokens.issue(
                    replace(principal, dataset_incarnation=current.dataset_incarnation)
                )
            fresh_headers = {"Authorization": f"Bearer {fresh}", "X-OCWP-Write-Protocol": "1"}
            page = client.post(
                "/api/v1/sync/baselines/page",
                headers=fresh_headers,
                json={"protocol": 1, "continuation": continuation},
            )
            assert page.status_code == 409 and page.json()["error"]["code"] == "context_changed"
            old_client = client.post(
                "/api/v1/customers",
                headers={"Authorization": f"Bearer {fresh}"},
                json={
                    "customer_id": new_id(),
                    "display_name": "Never created",
                    "location_id": "synthetic-location",
                },
            )
            assert (
                old_client.status_code == 409
                and old_client.json()["error"]["code"] == "client_upgrade_required"
            )
        with engine.connect() as connection:
            after_accounts = [
                dict(row) for row in connection.execute(select(UserRecord.__table__)).mappings()
            ]
            actions = connection.execute(
                select(IdentityAuditRecord.organization_id, IdentityAuditRecord.action)
            ).all()
            organizations = connection.execute(
                select(
                    OrganizationRecord.id,
                    OrganizationRecord.minimum_write_protocol,
                    OrganizationRecord.dataset_incarnation,
                ).order_by(OrganizationRecord.id)
            ).all()
        assert after_accounts == before_accounts
        assert sorted(actions) == sorted(
            [
                ("synthetic-org", "organization.cutover_activated"),
                ("synthetic-org", "organization.dataset_recovered"),
                ("synthetic-org-b", "organization.dataset_recovered"),
                ("synthetic-org-c", "organization.cutover_activated"),
                ("synthetic-org-c", "organization.dataset_recovered"),
            ]
        )
        assert all(
            floor == 1 and incarnation != original["dataset_incarnation"]
            for (org, floor, incarnation), original in zip(
                organizations, state["organizations"], strict=True
            )
        )
    finally:
        engine.dispose()
