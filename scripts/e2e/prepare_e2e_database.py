#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from cycling_workshop.db.url import normalize_database_url
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "services/platform"

E2E_ORGANIZATION_ID = "00000000-0000-7000-8000-000000000001"
E2E_LOCATION_ID = "00000000-0000-7000-8000-000000000002"
E2E_USER_ID = "00000000-0000-7000-8000-000000000003"
E2E_SECOND_LOCATION_ID = "00000000-0000-7000-8000-000000000004"
E2E_SECOND_USER_ID = "00000000-0000-7000-8000-000000000005"
E2E_OWNER_ID = "00000000-0000-7000-8000-000000000006"
E2E_LEGACY_ORGANIZATION_ID = "00000000-0000-7000-8000-000000000101"
E2E_LEGACY_LOCATION_ID = "00000000-0000-7000-8000-000000000102"
E2E_USERNAME = "e2e-admin"
E2E_PASSWORD = "ocwp-e2e-password"


def validate_e2e_database_url(database_url: str) -> None:
    parsed = make_url(normalize_database_url(database_url))
    database_name = parsed.database or ""
    if parsed.host not in {"127.0.0.1", "localhost"} or not database_name.endswith(
        ("_test", "_e2e")
    ):
        raise RuntimeError("E2E reset requires a dedicated local test database")


def reset_schema(database_url: str) -> None:
    engine = create_engine(normalize_database_url(database_url))
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()


def run_migrations(database_url: str) -> None:
    config = Config(str(SERVICE / "alembic.ini"))
    config.set_main_option("script_location", str(SERVICE / "migrations"))
    config.set_main_option(
        "sqlalchemy.url", normalize_database_url(database_url).replace("%", "%%")
    )
    command.upgrade(config, "head")


def seed_browser_identity(database_url: str, *, authenticated: bool = False) -> None:
    from cycling_workshop.identity.models import UserRecord
    from cycling_workshop.identity.repository import SqlAlchemyUserRepository, UserAccount
    from cycling_workshop.identity.roles import CAPABILITIES
    from cycling_workshop.identity.security import PasswordService
    from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord

    engine = create_engine(normalize_database_url(database_url))
    try:
        with Session(engine) as session:
            session.add(
                OrganizationRecord(
                    id=E2E_ORGANIZATION_ID,
                    name="OCWP Browser E2E",
                )
            )
            session.add(
                LocationRecord(
                    id=E2E_LOCATION_ID,
                    organization_id=E2E_ORGANIZATION_ID,
                    name="Taller E2E",
                )
            )
            if authenticated:
                session.add(
                    LocationRecord(
                        id=E2E_SECOND_LOCATION_ID,
                        organization_id=E2E_ORGANIZATION_ID,
                        name="Segundo taller E2E",
                    )
                )
            # Flush tenancy parents before adding the user: SQLAlchemy's unit
            # of work orders mappers by relationship(), and UserRecord
            # intentionally has none to tenancy, so without an explicit flush
            # PostgreSQL (which enforces FKs, unlike the SQLite surrogate)
            # would receive the users INSERT before its parents exist.
            session.flush()
            SqlAlchemyUserRepository(session).add(
                UserAccount(
                    user_id=E2E_USER_ID,
                    organization_id=E2E_ORGANIZATION_ID,
                    location_id=E2E_LOCATION_ID,
                    username=E2E_USERNAME,
                    display_name="Admin E2E",
                    password_hash=PasswordService().hash(E2E_PASSWORD),
                    capabilities=frozenset({"*"}),
                    is_active=True,
                    session_version=1,
                )
            )
            if authenticated:
                session.add_all(
                    [
                        UserRecord(
                            id=E2E_SECOND_USER_ID,
                            organization_id=E2E_ORGANIZATION_ID,
                            location_id=E2E_LOCATION_ID,
                            username="e2e-other",
                            display_name="Otra persona E2E",
                            password_hash=PasswordService().hash(E2E_PASSWORD),
                            capabilities=sorted(CAPABILITIES),
                            is_active=True,
                            session_version=1,
                        ),
                        UserRecord(
                            id=E2E_OWNER_ID,
                            organization_id=E2E_ORGANIZATION_ID,
                            location_id=None,
                            username="e2e-owner",
                            display_name="Responsable E2E",
                            password_hash=PasswordService().hash(E2E_PASSWORD),
                            capabilities=sorted(CAPABILITIES),
                            is_owner=True,
                            is_active=True,
                            session_version=1,
                        ),
                    ]
                )
            session.commit()
        if authenticated:
            seed_historical_workshop_records(database_url)
            from cycling_workshop.identity.cutover_cli import activate_cutover
            from cycling_workshop.settings import Settings

            activated = activate_cutover(
                Settings(database_url=database_url, cutover_enabled=True),
                organization_id=E2E_ORGANIZATION_ID,
            )
            assert activated["minimum_write_protocol"] == 1 and activated["changed"] is True
    finally:
        engine.dispose()


def seed_legacy_upgrade_identity(database_url: str) -> None:
    """Separate floor-zero synthetic tenant for the actual pinned old App/SW."""
    from cycling_workshop.identity.models import UserRecord
    from cycling_workshop.identity.roles import CAPABILITIES
    from cycling_workshop.identity.security import PasswordService
    from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord

    engine = create_engine(normalize_database_url(database_url))
    try:
        with Session(engine) as session:
            session.add(
                OrganizationRecord(id=E2E_LEGACY_ORGANIZATION_ID, name="Disposable old App upgrade")
            )
            session.add(
                LocationRecord(
                    id=E2E_LEGACY_LOCATION_ID,
                    organization_id=E2E_LEGACY_ORGANIZATION_ID,
                    name="Taller anterior E2E",
                )
            )
            session.flush()
            session.add(
                UserRecord(
                    id="00000000-0000-7000-8000-000000000103",
                    organization_id=E2E_LEGACY_ORGANIZATION_ID,
                    location_id=E2E_LEGACY_LOCATION_ID,
                    username="e2e-legacy",
                    display_name="Usuario anterior E2E",
                    password_hash=PasswordService().hash(E2E_PASSWORD),
                    capabilities=sorted(CAPABILITIES),
                    is_active=True,
                    session_version=1,
                )
            )
            session.commit()
    finally:
        engine.dispose()


def seed_historical_workshop_records(database_url: str) -> None:
    """Real REST writes while this disposable organization remains at floor 0."""
    from cycling_workshop.app import create_app
    from cycling_workshop.settings import Settings
    from fastapi.testclient import TestClient

    engine = create_engine(normalize_database_url(database_url))
    with TestClient(
        create_app(
            Settings(database_url=database_url, cutover_enabled=True),
            session_factory=sessionmaker(engine),
        )
    ) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={
                "organization_id": E2E_ORGANIZATION_ID,
                "username": "e2e-owner",
                "password": E2E_PASSWORD,
            },
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        for index, location_id in enumerate([E2E_LOCATION_ID, E2E_SECOND_LOCATION_ID], start=1):
            customer = client.post(
                "/api/v1/customers",
                headers=headers,
                json={
                    "location_id": location_id,
                    "display_name": f"Cliente REST histórico {index}",
                },
            )
            assert customer.status_code == 201
            bicycle = client.post(
                "/api/v1/bicycles",
                headers=headers,
                json={
                    "location_id": location_id,
                    "customer_id": customer.json()["customer_id"],
                    "brand": f"Bicicleta REST histórica {index}",
                },
            )
            assert bicycle.status_code == 201
            order = client.post(
                "/api/v1/service-orders",
                headers=headers,
                json={
                    "location_id": location_id,
                    "customer_id": customer.json()["customer_id"],
                    "bicycle_id": bicycle.json()["bicycle_id"],
                    "reported_problem": f"Orden REST histórica {index}",
                },
            )
            assert order.status_code == 201
    engine.dispose()


def main() -> int:
    database_url = os.environ.get("OCWP_E2E_DATABASE_URL")
    if not database_url:
        raise RuntimeError("OCWP_E2E_DATABASE_URL is required")
    validate_e2e_database_url(database_url)
    reset_schema(database_url)
    run_migrations(database_url)
    seed_browser_identity(database_url, authenticated=True)
    seed_legacy_upgrade_identity(database_url)
    print(f"E2E database ready for organization {E2E_ORGANIZATION_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
