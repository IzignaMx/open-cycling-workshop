"""Restricted PostgreSQL plus immutable workshop-logo recovery generations.

Checksums establish integrity, never provenance. Restore only operator-trusted
archives into isolated fresh targets; authenticated application proof is separate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from cycling_workshop.identity.cutover_cli import recover_cutover
from cycling_workshop.settings import Settings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from scripts.database import backup_postgres as postgres

MANIFEST_NAME = "branding-manifest.json"
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_PROFILES = 2048
MAX_ORGANIZATIONS = 2048
MAX_ASSET_BYTES = 262144
SCOPE = "postgresql-and-branding-assets"
EXCLUDES = ["other-external-blob-payloads", "client-indexeddb", "configuration-and-secrets"]
PALETTES = {
    "bosque",
    "arcilla",
    "tinta",
    "cobalto",
    "petroleo",
    "indigo",
    "malva",
    "frambuesa",
    "jade",
    "lima",
    "hielo",
    "lavanda",
}
PROFILE_FIELDS = {
    "organization_id",
    "location_id",
    "schema_version",
    "version",
    "display_name",
    "palette_id",
    "logo_key",
    "logo_sha256",
    "logo_byte_count",
    "logo_width",
    "logo_height",
    "updated_at",
    "updated_by",
}
ORGANIZATION_FIELDS = {"organization_id", "dataset_incarnation", "minimum_write_protocol"}
MANIFEST_FIELDS = {
    "format_version",
    "scope",
    "created_at",
    "postgres_manifest_sha256",
    "organizations",
    "profiles",
    "restore_tested",
    "excludes",
}
DIGEST = re.compile(r"[a-f0-9]{64}")


def _require(condition: object) -> None:
    if not condition:
        raise ValueError("unsupported field")


def _identifier(value: object) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 36
        and value.strip() == value
        and all(not unicodedata.category(char).startswith("C") for char in value)
    )


def _timestamp(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 40:
        return False
    parsed = datetime.fromisoformat(value)
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _validate_snapshot(value: dict[str, Any]) -> None:
    organizations, profiles = value["organizations"], value["profiles"]
    _require(isinstance(organizations, list) and len(organizations) <= MAX_ORGANIZATIONS)
    _require(isinstance(profiles, list) and len(profiles) <= MAX_PROFILES)
    organization_ids = []
    for organization in organizations:
        _require(isinstance(organization, dict) and set(organization) == ORGANIZATION_FIELDS)
        _require(_identifier(organization["organization_id"]))
        incarnation = organization["dataset_incarnation"]
        _require(isinstance(incarnation, str) and str(UUID(incarnation)) == incarnation)
        protocol = organization["minimum_write_protocol"]
        _require(type(protocol) is int and protocol in (0, 1))
        organization_ids.append(organization["organization_id"])
    _require(organization_ids == sorted(set(organization_ids)))
    profile_ids = []
    for profile in profiles:
        _require(isinstance(profile, dict) and set(profile) == PROFILE_FIELDS)
        _require(profile["organization_id"] in organization_ids)
        _require(_identifier(profile["location_id"]) and _identifier(profile["updated_by"]))
        _require(type(profile["schema_version"]) is int and profile["schema_version"] == 1)
        _require(type(profile["version"]) is int and 1 <= profile["version"] <= 2**63 - 1)
        name = profile["display_name"]
        _require(isinstance(name, str) and 1 <= len(name) <= 160)
        _require(name == name.strip() == unicodedata.normalize("NFC", name))
        _require(len(name.encode("utf-8")) <= 640)
        _require(all(not unicodedata.category(char).startswith("C") for char in name))
        _require(isinstance(profile["palette_id"], str) and profile["palette_id"] in PALETTES)
        _require(_timestamp(profile["updated_at"]))
        logo = [
            profile[field]
            for field in ("logo_key", "logo_sha256", "logo_byte_count", "logo_width", "logo_height")
        ]
        if any(field is not None for field in logo):
            key, digest, size, width, height = logo
            _require(isinstance(digest, str) and DIGEST.fullmatch(digest))
            _require(key == f"{digest[:2]}/{digest}")
            _require(type(size) is int and 1 <= size <= MAX_ASSET_BYTES)
            _require(type(width) is int and 1 <= width <= 512)
            _require(type(height) is int and 1 <= height <= 512)
        profile_ids.append((profile["organization_id"], profile["location_id"]))
    _require(profile_ids == sorted(set(profile_ids)))


def _snapshot_metadata(connection: Connection) -> dict[str, Any]:
    """Read bounded profile references AND incarnation preconditions in caller's snapshot."""
    organizations = [
        dict(row)
        for row in connection.execute(
            text(
                "SELECT id AS organization_id, dataset_incarnation, minimum_write_protocol "
                "FROM public.organizations ORDER BY id LIMIT :limit"
            ),
            {"limit": MAX_ORGANIZATIONS + 1},
        ).mappings()
    ]
    profiles = [
        dict(row)
        for row in connection.execute(
            text(
                "SELECT organization_id, location_id, schema_version, version, display_name, "
                "palette_id, logo_key, logo_sha256, logo_byte_count, logo_width, logo_height, "
                "updated_at, updated_by FROM public.workshop_brand_profiles "
                "ORDER BY organization_id, location_id LIMIT :limit"
            ),
            {"limit": MAX_PROFILES + 1},
        ).mappings()
    ]
    for profile in profiles:
        when = profile["updated_at"]
        if not isinstance(when, datetime) or when.tzinfo is None:
            raise postgres.BackupError("branding snapshot timestamp is invalid")
        profile["updated_at"] = when.astimezone(UTC).isoformat()
    result = {"organizations": organizations, "profiles": profiles}
    try:
        _validate_snapshot(result)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise postgres.BackupError(
            "branding snapshot is invalid or exceeds bounded limits"
        ) from None
    return result


@contextmanager
def _directory(path: Path) -> Iterator[int]:
    """Walk from / without following symlinks, including intermediate components."""
    path = path.absolute()
    if ".." in path.parts:
        raise postgres.BackupError("unsafe directory path")
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        mode = os.fstat(descriptor).st_mode
        if mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise postgres.BackupError(
                "unsafe writable directory; restrict its ownership/permissions"
            )
        yield descriptor
    except OSError:
        raise postgres.BackupError(
            "directory is missing or unsafe; symlinks are forbidden"
        ) from None
    finally:
        os.close(descriptor)


def _new_directory(path: Path) -> None:
    with _directory(path.absolute().parent) as parent:
        try:
            os.mkdir(path.name, 0o700, dir_fd=parent)
        except FileExistsError:
            raise postgres.BackupError("generation already exists; use a fresh directory") from None
        os.fsync(parent)


def _read_file(path: Path, limit: int) -> bytes:
    with _directory(path.parent) as parent:
        try:
            descriptor = os.open(
                path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
            with os.fdopen(descriptor, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit:
                    raise postgres.BackupError("manifest is empty, unsafe or oversized")
                data = stream.read(limit + 1)
                if len(data) != info.st_size or len(data) > limit:
                    raise postgres.BackupError("manifest changed or exceeds bounded limits")
                return data
        except OSError:
            raise postgres.BackupError("manifest is missing or unsafe") from None


def _publish_manifest(path: Path, manifest: dict[str, Any]) -> None:
    payload = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if len(payload) > MAX_MANIFEST_BYTES:
        raise postgres.BackupError("branding manifest exceeds bounded limits")
    with _directory(path) as directory:
        # Publish the complete, fsynced manifest last, atomically without replacement.
        descriptor = os.open(
            ".branding-manifest.pending",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(
            ".branding-manifest.pending",
            MANIFEST_NAME,
            src_dir_fd=directory,
            dst_dir_fd=directory,
            follow_symlinks=False,
        )
        os.unlink(".branding-manifest.pending", dir_fd=directory)
        os.fsync(directory)


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate manifest key")
        result[key] = value
    return result


def _manifest(directory: Path) -> dict[str, Any]:
    raw = _read_file(directory / MANIFEST_NAME, MAX_MANIFEST_BYTES)
    try:
        value = json.loads(raw, object_pairs_hook=_unique_pairs)
        _require(isinstance(value, dict) and set(value) == MANIFEST_FIELDS)
        _require(type(value["format_version"]) is int and value["format_version"] == 1)
        _require(value["scope"] == SCOPE and value["restore_tested"] is False)
        _require(value["excludes"] == EXCLUDES)
        _require(_timestamp(value["created_at"]))
        _require(isinstance(value["postgres_manifest_sha256"], str))
        _require(DIGEST.fullmatch(value["postgres_manifest_sha256"]))
        _validate_snapshot(value)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
        raise postgres.BackupError("branding manifest is invalid or unsupported") from None
    return dict(value)


def _asset_bytes(root: Path, profile: dict[str, Any]) -> bytes:
    from cycling_workshop.branding.assets import BrandingAssetStore
    from cycling_workshop.branding.images import inspect_canonical_png

    try:
        data = BrandingAssetStore(root).read(
            profile["organization_id"],
            profile["logo_key"],
            sha256=profile["logo_sha256"],
            byte_count=profile["logo_byte_count"],
        )
        dimensions = inspect_canonical_png(data)
        if (
            dimensions != (profile["logo_width"], profile["logo_height"])
            or len(data) != profile["logo_byte_count"]
            or hashlib.sha256(data).hexdigest() != profile["logo_sha256"]
        ):
            raise ValueError("dimension mismatch")
        return data
    except (ValueError, OSError):
        raise postgres.BackupError(
            "branding asset integrity failure: missing, unsafe or corrupt bytes"
        ) from None


def _copy_assets(source: Path, target: Path, profiles: list[dict[str, Any]]) -> int:
    # Modules are lazy: database-only operations do not require the image pipeline.
    count = 0
    for profile in profiles:
        if profile["logo_key"] is None:
            continue
        from cycling_workshop.branding.assets import BrandingAssetStore
        from cycling_workshop.branding.images import CanonicalLogo

        data = _asset_bytes(source, profile)
        logo = CanonicalLogo(
            data=data,
            sha256=profile["logo_sha256"],
            byte_count=profile["logo_byte_count"],
            width=profile["logo_width"],
            height=profile["logo_height"],
        )
        key = BrandingAssetStore(target).put(profile["organization_id"], logo)
        if key != profile["logo_key"] or _asset_bytes(target, profile) != data:
            raise postgres.BackupError("copied branding asset differs; isolate the target")
        count += 1
    return count


def create_branding_bundle(
    database_url: str,
    directory: Path,
    *,
    asset_root: Path,
    runner: postgres.Runner = postgres._run,
    engine_factory: postgres.EngineFactory = create_engine,
) -> Path:
    """Copy exactly the immutable references observed inside pg_dump's snapshot."""
    postgres._libpq_env(database_url)
    directory = directory.absolute()
    _new_directory(directory)
    retained: dict[str, Any] = {}

    def observe(connection: Connection) -> None:
        retained.update(_snapshot_metadata(connection))

    try:
        postgres.create_backup_bundle(
            database_url,
            directory / "postgres",
            runner=runner,
            engine_factory=engine_factory,
            snapshot_observer=observe,
        )
        _validate_snapshot(retained)
        _new_directory(directory / "assets")
        _copy_assets(asset_root, directory / "assets", retained["profiles"])
        manifest = {
            "format_version": 1,
            "scope": SCOPE,
            "created_at": datetime.now(UTC).isoformat(),
            "postgres_manifest_sha256": hashlib.sha256(
                _read_file(
                    directory / "postgres" / postgres.MANIFEST_NAME, postgres.MAX_MANIFEST_BYTES
                )
            ).hexdigest(),
            **retained,
            "restore_tested": False,
            "excludes": EXCLUDES,
        }
        # Nested dump/manifest files are fsynced by the PostgreSQL tool, but its
        # directory entries must also be durable before the outer completion marker.
        with _directory(directory / "postgres") as nested_directory:
            os.fsync(nested_directory)
        _publish_manifest(directory, manifest)
    except postgres.BackupError:
        raise
    except Exception:
        raise postgres.BackupError(
            "branding backup failed; incomplete generation must not be used"
        ) from None
    return directory


def verify_branding_bundle(
    directory: Path, *, runner: postgres.Runner = postgres._run
) -> dict[str, Any]:
    """Validate the complete bounded manifest and all exact bytes; never claim recovery."""
    manifest = _manifest(directory)
    raw = _read_file(directory / "postgres" / postgres.MANIFEST_NAME, postgres.MAX_MANIFEST_BYTES)
    if hashlib.sha256(raw).hexdigest() != manifest["postgres_manifest_sha256"]:
        raise postgres.BackupError("nested PostgreSQL manifest integrity failure")
    with _directory(directory / "assets"):
        for profile in manifest["profiles"]:
            if profile["logo_key"] is not None:
                _asset_bytes(directory / "assets", profile)
    checked = postgres.verify_backup_bundle(directory / "postgres", runner=runner)
    return {
        "status": "branding_integrity_checked_not_restored",
        "manifest": manifest,
        "postgres_manifest": checked["manifest"],
    }


def _reserve_assets(root: Path, digest: str) -> None:
    if not root.exists():
        _new_directory(root)
    with _directory(root) as directory:
        if os.listdir(directory):
            raise postgres.BackupError("asset restore target is not empty; use a fresh volume")
        descriptor = os.open(
            ".ocwp-branding-restore",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        with os.fdopen(descriptor, "w") as stream:
            stream.write(digest + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(directory)


def restore_branding_bundle(
    directory: Path,
    target_url: str,
    *,
    asset_root: Path,
    confirm_empty_target: bool = False,
    runner: postgres.Runner = postgres._run,
    engine_factory: postgres.EngineFactory = create_engine,
) -> dict[str, Any]:
    """Restore isolated fresh SQL/assets, compare content, then rotate exact incarnations.

    Failure after SQL commit or any rotation requires quarantining both new targets.
    The caller must keep all API/worker/edge clients away throughout the operation.
    """
    if not confirm_empty_target:
        raise postgres.BackupError("explicit confirm_empty_target is required")
    postgres._libpq_env(target_url)
    directory, asset_root = directory.absolute(), asset_root.absolute()
    if asset_root.is_relative_to(directory) or directory.is_relative_to(asset_root):
        raise postgres.BackupError("asset target must be separate from the backup generation")
    checked = verify_branding_bundle(directory, runner=runner)
    manifest = checked["manifest"]
    if any(row["minimum_write_protocol"] != 1 for row in manifest["organizations"]):
        raise postgres.BackupError(
            "branding recovery requires floor-1 organizations; keep targets isolated"
        )
    digest = hashlib.sha256(_read_file(directory / MANIFEST_NAME, MAX_MANIFEST_BYTES)).hexdigest()
    started = datetime.now(UTC)
    try:
        _reserve_assets(asset_root.absolute(), digest)
        copied = _copy_assets(directory / "assets", asset_root, manifest["profiles"])
        postgres.restore_backup_bundle(
            directory / "postgres",
            target_url,
            confirm_empty_target=True,
            runner=runner,
            engine_factory=engine_factory,
        )
        engine = postgres._engine(target_url, engine_factory)
        try:
            with engine.connect() as connection:
                connection = connection.execution_options(isolation_level="REPEATABLE READ")
                with connection.begin():
                    connection.execute(text("SET TRANSACTION READ ONLY"))
                    connection.execute(text("SET LOCAL row_security = off"))
                    connection.execute(text("SET LOCAL statement_timeout = '1h'"))
                    restored = _snapshot_metadata(connection)
            if any(restored[key] != manifest[key] for key in ("organizations", "profiles")):
                raise postgres.BackupError(
                    "restored branding metadata differ; isolate both targets"
                )
            for profile in restored["profiles"]:
                if profile["logo_key"] is not None and (
                    _asset_bytes(asset_root, profile) != _asset_bytes(directory / "assets", profile)
                ):
                    raise postgres.BackupError(
                        "restored branding bytes differ; isolate both targets"
                    )
        finally:
            engine.dispose()
        for organization in manifest["organizations"]:
            recover_cutover(
                Settings(database_url=target_url),
                organization_id=organization["organization_id"],
                expected_incarnation=organization["dataset_incarnation"],
            )
    except postgres.BackupError:
        raise
    except Exception:
        raise postgres.BackupError(
            "branding restore/check/rotation failed; isolate both targets; no recovery claimed"
        ) from None
    finished = datetime.now(UTC)
    return {
        "status": "branding_restore_checked",
        "scope": SCOPE,
        "branding_manifest_sha256": digest,
        "backup_sha256": checked["postgres_manifest"]["archive"]["sha256"],
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "elapsed_seconds": (finished - started).total_seconds(),
        "profiles_checked": len(manifest["profiles"]),
        "asset_references_checked": copied,
        "incarnations_rotated": len(manifest["organizations"]),
        "application_smoke_tested": False,
        "client_pending_mutations_checked": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in ("backup", "verify", "restore"):
        command = commands.add_parser(name)
        command.add_argument("directory", type=Path)
        if name != "verify":
            command.add_argument("--asset-root", type=Path, required=True)
        if name == "restore":
            command.add_argument("--confirm-empty-target", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.operation == "backup":
            create_branding_bundle(
                postgres._url_from_environment("OCWP_DATABASE_URL"),
                args.directory,
                asset_root=args.asset_root,
            )
            result = {"status": "branding_backup_created_not_restored", "scope": SCOPE}
        elif args.operation == "verify":
            checked = verify_branding_bundle(args.directory)
            result = {"status": checked["status"], "scope": SCOPE}
        else:
            result = restore_branding_bundle(
                args.directory,
                postgres._url_from_environment("OCWP_RESTORE_DATABASE_URL"),
                asset_root=args.asset_root,
                confirm_empty_target=args.confirm_empty_target,
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except postgres.BackupError as error:
        print(str(error), file=sys.stderr)
    except Exception:
        print(
            "operation failed; no successful branding backup or recovery is claimed",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
