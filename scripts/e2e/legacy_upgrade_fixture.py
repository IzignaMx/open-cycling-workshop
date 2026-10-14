#!/usr/bin/env python3
"""Bounded synthetic-tenant controls for the exact old App/SW acceptance journey."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

from cycling_workshop.identity.cutover_cli import activate_cutover
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.settings import Settings
from cycling_workshop.tenancy.models import OrganizationRecord
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from scripts.e2e.prepare_e2e_database import E2E_LEGACY_ORGANIZATION_ID, validate_e2e_database_url

ROOT = Path(__file__).resolve().parents[2]
PIN = "714342c60f4163c7b4c1ebec8433995dccbeea01"


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
        source = subprocess.run(
            ["git", "show", f"{PIN}:services/platform/src/cycling_workshop/identity/security.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        module = ModuleType("_ocwp_pinned_legacy_security")
        sys.modules[module.__name__] = module
        try:
            exec(compile(source, f"{PIN}/identity/security.py", "exec"), module.__dict__)
            return module.SessionTokenService(secret=settings.auth_secret).issue(principal)
        finally:
            sys.modules.pop(module.__name__, None)
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["legacy-session", "activate"])
    action = parser.parse_args().action
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
    else:
        print(json.dumps(activate_cutover(settings, organization_id=E2E_LEGACY_ORGANIZATION_ID)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
