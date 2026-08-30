from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from cycling_workshop.db.session import build_engine
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.repository import SqlAlchemyUserRepository, UserAccount, normalize_username
from cycling_workshop.identity.security import PasswordService
from cycling_workshop.settings import Settings
from cycling_workshop.shared.ids import new_id
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord


def doctor_report(settings: Settings) -> dict[str, object]:
    checks: dict[str, str] = {}
    try:
        engine = build_engine(settings)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        checks["database"] = "ok"
    except Exception as exc:  # operational command must report rather than crash
        checks["database"] = f"error:{type(exc).__name__}"

    checks["auth_secret"] = "ok" if len(settings.auth_secret) >= 32 else "error:too_short"
    ok = all(value == "ok" for value in checks.values())
    return {
        "ok": ok,
        "environment": settings.environment,
        "checks": checks,
    }


def bootstrap_admin(
    settings: Settings,
    *,
    organization_name: str,
    location_name: str,
    username: str,
    display_name: str,
    password_file: Path,
) -> dict[str, object]:
    password = password_file.read_text(encoding="utf-8").rstrip("\r\n")
    password_hash = PasswordService().hash(password)
    organization_id = new_id()
    location_id = new_id()
    user_id = new_id()

    engine = build_engine(settings)
    try:
        with Session(engine) as session:
            if session.scalar(select(UserRecord.id).limit(1)) is not None:
                raise RuntimeError("bootstrap admin refused because a user already exists")
            organization = OrganizationRecord(id=organization_id, name=organization_name.strip())
            location = LocationRecord(id=location_id, organization_id=organization_id, name=location_name.strip())
            session.add_all([organization, location])
            SqlAlchemyUserRepository(session).add(
                UserAccount(
                    user_id=user_id,
                    organization_id=organization_id,
                    location_id=location_id,
                    username=normalize_username(username),
                    display_name=display_name.strip(),
                    password_hash=password_hash,
                    capabilities=frozenset({"*"}),
                    is_active=True,
                    session_version=1,
                )
            )
            session.commit()
    finally:
        engine.dispose()

    return {
        "created": True,
        "organization_id": organization_id,
        "location_id": location_id,
        "user_id": user_id,
        "username": normalize_username(username),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ocwpctl")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("doctor", help="Run operational health checks")
    subcommands.add_parser("status", help="Show concise operational status")

    bootstrap = subcommands.add_parser("bootstrap", help="Initialize a fresh installation")
    bootstrap_commands = bootstrap.add_subparsers(dest="bootstrap_command", required=True)
    admin = bootstrap_commands.add_parser("admin", help="Create the first organization, location, and administrator")
    admin.add_argument("--organization-name", required=True)
    admin.add_argument("--location-name", required=True)
    admin.add_argument("--username", required=True)
    admin.add_argument("--display-name", required=True)
    admin.add_argument("--password-file", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    if args.command in {"doctor", "status"}:
        report = doctor_report(settings)
        print(json.dumps(report, sort_keys=True))
        return 0 if bool(report["ok"]) else 1
    if args.command == "bootstrap" and args.bootstrap_command == "admin":
        report = bootstrap_admin(
            settings,
            organization_name=args.organization_name,
            location_name=args.location_name,
            username=args.username,
            display_name=args.display_name,
            password_file=args.password_file,
        )
        print(json.dumps(report, sort_keys=True))
        return 0
    return 2
