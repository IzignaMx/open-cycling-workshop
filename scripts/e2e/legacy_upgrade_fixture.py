#!/usr/bin/env python3
"""Bounded synthetic-tenant controls for the exact old App/SW acceptance journey."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from types import ModuleType

from cycling_workshop.identity.cutover_cli import activate_cutover, recover_cutover
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.settings import Settings
from cycling_workshop.tenancy.models import OrganizationRecord
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from scripts.e2e.prepare_e2e_database import E2E_LEGACY_ORGANIZATION_ID, validate_e2e_database_url

ROOT = Path(__file__).resolve().parents[2]
PIN = "714342c60f4163c7b4c1ebec8433995dccbeea01"
# Independently verified Git provenance; runtime checks the exact archived blob bytes.
PIN_TREE = "fbf5e5678188a97b8b9709e6f91cb6b250e20c9f"
PIN_SOURCE = "services/platform/src/cycling_workshop/identity/security.py"
PIN_BLOB = "0a13a1ac154f0b982589dfa09c470cf4aa61c4e0"
PIN_SOURCE_BYTES = 4549
PIN_SOURCE_SHA256 = "95613b4278c0a966ecdd68445c8d5197e5d874f1678a35f8be930720811b87c6"
PIN_SOURCE_FIXTURE = ROOT / "tests/fixtures/legacy-714342c6/security.py.source"


def legacy_security_source() -> str:
    """Load only the unchanged pinned codec, including in a source-only archive."""
    try:
        with PIN_SOURCE_FIXTURE.open("rb") as handle:
            source = handle.read(PIN_SOURCE_BYTES + 1)
    except OSError as exc:
        raise RuntimeError("Pinned legacy security source unavailable") from exc
    if len(source) != PIN_SOURCE_BYTES or hashlib.sha256(source).hexdigest() != PIN_SOURCE_SHA256:
        raise RuntimeError("Pinned legacy security source identity mismatch")
    return source.decode("utf-8")


def legacy_fixture_session(settings: Settings) -> str:
    """Issue with the unchanged pinned pre-B token codec, never fake an auth context."""
    engine = create_engine(settings.database_url)
    try:
        with Session(engine) as session:
            organization = session.get(OrganizationRecord, E2E_LEGACY_ORGANIZATION_ID)
            user = session.get(UserRecord, "00000000-0000-7000-8000-000000000103")
            if organization is None or organization.minimum_write_protocol != 0 or user is None:
                raise RuntimeError(
                    "Legacy fixture requires its dedicated floor-zero synthetic tenant"
                )
            principal = Principal(
                user_id=user.id,
                organization_id=organization.id,
                location_id=user.location_id,
                capabilities=frozenset(user.capabilities),
                session_version=user.session_version,
            )
        source = legacy_security_source()
        module = ModuleType("_ocwp_pinned_legacy_security")
        sys.modules[module.__name__] = module
        try:
            exec(compile(source, f"{PIN}/identity/security.py", "exec"), module.__dict__)
            return module.SessionTokenService(secret=settings.auth_secret).issue(principal)
        finally:
            sys.modules.pop(module.__name__, None)
    finally:
        engine.dispose()


def recover_legacy_fixture(settings: Settings, expected_incarnation: str) -> dict[str, object]:
    """Only the dedicated synthetic tenant may rotate in this browser fixture."""
    return recover_cutover(
        settings,
        organization_id=E2E_LEGACY_ORGANIZATION_ID,
        expected_incarnation=expected_incarnation,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["legacy-session", "activate", "recover"])
    parser.add_argument("--expected-incarnation")
    args = parser.parse_args()
    action = args.action
    if (action == "recover") != (args.expected_incarnation is not None):
        parser.error("recover requires exactly one expected incarnation")
    url = os.environ.get("OCWP_E2E_DATABASE_URL", "")
    validate_e2e_database_url(url)
    settings = Settings(
        database_url=url,
        cutover_enabled=True,
        auth_secret=os.environ.get(
            "OCWP_AUTH_SECRET", "e2e-only-secret-00000000000000000000000000000000"
        ),
    )
    if action == "legacy-session":
        # Captured by the browser runner only; never upload credentials as artifacts.
        print(json.dumps({"token": legacy_fixture_session(settings)}))
    elif action == "activate":
        print(json.dumps(activate_cutover(settings, organization_id=E2E_LEGACY_ORGANIZATION_ID)))
    else:
        print(json.dumps(recover_legacy_fixture(settings, args.expected_incarnation)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
