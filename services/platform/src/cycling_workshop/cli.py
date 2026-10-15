from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.db.session import build_engine
from cycling_workshop.identity.admin_cli import create_first_owner
from cycling_workshop.identity.branding_cli import adopt_branding
from cycling_workshop.identity.cutover_cli import (
    activate_cutover,
    cutover_status,
    recover_cutover,
)
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.repository import (
    SqlAlchemyUserRepository,
    UserAccount,
    normalize_username,
)
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
            # No organization exists to provide the normal row barrier. All
            # supported bootstraps serialize before checking the complete fresh-
            # installation predicate. These are transaction-scoped locks.
            if engine.dialect.name == "postgresql":
                session.execute(text("SELECT pg_advisory_xact_lock(1329813328, 1)"))
            elif engine.dialect.name == "sqlite":
                session.execute(text("BEGIN IMMEDIATE"))
            else:
                raise RuntimeError("bootstrap admin requires a supported database")
            if any(
                session.scalar(select(model.id).limit(1)) is not None
                for model in (OrganizationRecord, LocationRecord, UserRecord)
            ):
                raise RuntimeError("bootstrap admin requires a fresh installation")
            organization = OrganizationRecord(id=organization_id, name=organization_name.strip())
            location = LocationRecord(
                id=location_id, organization_id=organization_id, name=location_name.strip()
            )
            session.add_all([organization, location])
            # Flush tenancy parents before adding the admin user: the unit of
            # work orders mappers by relationship(), and UserRecord has none
            # to tenancy, so PostgreSQL (unlike the SQLite surrogate tests)
            # would otherwise receive the users INSERT before its FK parents.
            session.flush()
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


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        # Even invalid flags must not echo a mistakenly supplied plaintext secret.
        self.exit(2, "Invalid command arguments. Run ocwpctl --help.\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = _SafeArgumentParser(prog="ocwpctl", allow_abbrev=False)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("doctor", help="Run operational health checks")
    subcommands.add_parser("status", help="Show concise operational status")

    bootstrap = subcommands.add_parser("bootstrap", help="Initialize a fresh installation")
    bootstrap_commands = bootstrap.add_subparsers(dest="bootstrap_command", required=True)
    admin = bootstrap_commands.add_parser(
        "admin", help="Create the first organization, location, and administrator"
    )
    admin.add_argument("--organization-name", required=True)
    admin.add_argument("--location-name", required=True)
    admin.add_argument("--username", required=True)
    admin.add_argument("--display-name", required=True)
    admin.add_argument("--password-file", type=Path, required=True)
    access = subcommands.add_parser("access", help="Explicit local access administration")
    access_commands = access.add_subparsers(
        dest="access_command", required=True, parser_class=_SafeArgumentParser
    )
    owner = access_commands.add_parser(
        "create-first-owner",
        allow_abbrev=False,
        help="Create a separate organization-wide owner; never promote an account",
    )
    owner.add_argument("--organization-id", required=True)
    owner.add_argument("--username", required=True)
    owner.add_argument("--display-name", required=True)
    owner.add_argument("--password-file", type=Path, required=True)
    adoption = access_commands.add_parser(
        "adopt-branding",
        allow_abbrev=False,
        help="Explicitly add only branding grants to one active established owner",
    )
    adoption.add_argument("--organization-id", required=True)
    adoption.add_argument("--owner-id", required=True)
    adoption.add_argument("--expected-version", type=int, required=True)
    cutover = subcommands.add_parser("cutover", help="Explicit local cutover maintenance")
    cutover_commands = cutover.add_subparsers(
        dest="cutover_command", required=True, parser_class=_SafeArgumentParser
    )
    for action in ("status", "activate", "recover"):
        operation = cutover_commands.add_parser(action, allow_abbrev=False)
        operation.add_argument("--organization-id", required=True)
        if action == "recover":
            operation.add_argument("--expected-incarnation", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if (
        args.command == "cutover"
        or (args.command == "access" and args.access_command == "adopt-branding")
    ) and not (os.getenv("OCWP_DATABASE_URL") or os.getenv("OCWP_DATABASE_URL_FILE")):
        print(
            json.dumps(
                {"changed": False, "error": "database_configuration_required"}, sort_keys=True
            )
        )
        return 1
    settings = Settings.from_env()
    if args.command == "cutover":
        try:
            if args.cutover_command == "recover":
                report = recover_cutover(
                    settings,
                    organization_id=args.organization_id,
                    expected_incarnation=args.expected_incarnation,
                )
            else:
                operation = (
                    activate_cutover if args.cutover_command == "activate" else cutover_status
                )
                report = operation(settings, organization_id=args.organization_id)
        except ApiError as exc:
            print(json.dumps({"changed": False, "error": exc.code}, sort_keys=True))
            return 1
        except (OSError, UnicodeError, ValidationError, SQLAlchemyError):
            print(
                json.dumps({"changed": False, "error": "cutover_operation_failed"}, sort_keys=True)
            )
            return 1
        print(json.dumps(report, sort_keys=True))
        return 0
    if args.command == "access" and args.access_command == "adopt-branding":
        try:
            report = adopt_branding(
                settings,
                organization_id=args.organization_id,
                owner_id=args.owner_id,
                expected_version=args.expected_version,
            )
        except ApiError as exc:
            print(json.dumps({"changed": False, "error": exc.code}, sort_keys=True))
            return 1
        except (OSError, UnicodeError, ValidationError, SQLAlchemyError):
            print(
                json.dumps({"changed": False, "error": "branding_adoption_failed"}, sort_keys=True)
            )
            return 1
        print(json.dumps(report, sort_keys=True))
        return 0
    if args.command == "access" and args.access_command == "create-first-owner":
        try:
            report = create_first_owner(
                settings,
                organization_id=args.organization_id,
                username=args.username,
                display_name=args.display_name,
                password_file=args.password_file,
            )
        except ApiError as exc:
            print(json.dumps({"created": False, "error": exc.code}, sort_keys=True))
            return 1
        except (OSError, UnicodeError, ValidationError, SQLAlchemyError):
            # Validation/DB exception strings can contain secret inputs, SQL
            # parameters, or credential-bearing connection URLs. Never echo them.
            print(json.dumps({"created": False, "error": "owner_setup_failed"}, sort_keys=True))
            return 1
        print(json.dumps(report, sort_keys=True))
        return 0
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
