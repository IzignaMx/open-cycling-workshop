#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from cycling_workshop.db.url import normalize_database_url
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
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
    try:
        parsed = make_url(normalize_database_url(database_url))
    except (ArgumentError, TypeError, ValueError):
        raise RuntimeError("E2E reset requires a dedicated local test database") from None
    database_name = parsed.database or ""
    if (
        parsed.drivername != "postgresql+psycopg"
        or parsed.host not in {"127.0.0.1", "localhost"}
        or not database_name.endswith(("_test", "_e2e"))
        or parsed.query
        or any(
            name in os.environ
            for name in (
                "PGHOST",
                "PGHOSTADDR",
                "PGPORT",
                "PGDATABASE",
                "PGSERVICE",
                "PGSERVICEFILE",
                "PGSYSCONFDIR",
            )
        )
    ):
        raise RuntimeError("E2E reset requires a dedicated local test database")


def reset_schema(database_url: str) -> None:
    validate_e2e_database_url(database_url)
    engine = create_engine(normalize_database_url(database_url))
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()


def run_migrations(database_url: str) -> None:
    validate_e2e_database_url(database_url)
    normalized = normalize_database_url(database_url)
    config = Config(str(SERVICE / "alembic.ini"))
    config.set_main_option("script_location", str(SERVICE / "migrations"))
    config.set_main_option(
        "sqlalchemy.url", normalize_database_url(database_url).replace("%", "%%")
    )
    # Alembic env.py prefers the environment over sqlalchemy.url. Pin the
    # already-validated target for this call, including when a *_FILE is set.
    previous = os.environ.get("OCWP_DATABASE_URL")
    os.environ["OCWP_DATABASE_URL"] = normalized
    try:
        command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop("OCWP_DATABASE_URL", None)
        else:
            os.environ["OCWP_DATABASE_URL"] = previous


def seed_browser_identity(database_url: str, *, authenticated: bool = False) -> None:
    validate_e2e_database_url(database_url)
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
    validate_e2e_database_url(database_url)
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
    validate_e2e_database_url(database_url)
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


# Stable synthetic tenants for administration journeys. Each case and its one
# configured CI retry owns a separate tenant; no existing workshop fixture is
# mutated by session/password, owner, location or directory experiments.
ADMINISTRATION_CASES = (
    "users",
    "scope",
    "zero",
    "no-sync",
    "empty",
    "logout",
    "password",
    "lost-response",
    "version",
    "owner",
    "themes",
    "selector-secret",
    "workshop-secret",
    "suspended-secret",
    "probe-secret",
    "visual-states",
)


def administration_fixture_id(case_index: int, retry: int, entity: int) -> str:
    return f"00000000-0000-7000-8000-{10000 + retry * 1000 + case_index * 10 + entity:012d}"


def seed_administration_identities(database_url: str) -> None:
    """Dedicated synthetic floor-one accounts, never installation accounts."""
    from cycling_workshop.identity.cutover_cli import activate_cutover, cutover_status
    from cycling_workshop.identity.models import UserRecord
    from cycling_workshop.identity.roles import CAPABILITIES
    from cycling_workshop.identity.security import PasswordService
    from cycling_workshop.settings import Settings
    from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord

    # Keep this entry point guarded even if called without main().
    validate_e2e_database_url(database_url)
    engine = create_engine(normalize_database_url(database_url))
    password_hash = PasswordService().hash(E2E_PASSWORD)
    try:
        for retry in range(2):
            for index, case in enumerate(ADMINISTRATION_CASES):
                organization_id = administration_fixture_id(index, retry, 0)
                with Session(engine) as session:
                    session.add(
                        OrganizationRecord(
                            id=organization_id, name=f"Disposable administration {case} {retry}"
                        )
                    )
                    session.flush()
                    if case != "zero":
                        session.add_all(
                            LocationRecord(
                                id=administration_fixture_id(index, retry, entity),
                                organization_id=organization_id,
                                name=f"Taller administración {letter}",
                            )
                            for entity, letter in ((1, "A"), (2, "B"))
                        )
                        session.flush()
                    session.add(
                        UserRecord(
                            id=administration_fixture_id(index, retry, 3),
                            organization_id=organization_id,
                            location_id=None,
                            username="e2e-administration-owner",
                            display_name="Responsable administración sintética",
                            password_hash=password_hash,
                            capabilities=sorted(CAPABILITIES),
                            is_owner=True,
                            is_active=True,
                            session_version=1,
                        )
                    )
                    session.commit()
                activated = activate_cutover(
                    Settings(database_url=database_url, cutover_enabled=True),
                    organization_id=organization_id,
                )
                assert activated["organization_id"] == organization_id
                assert activated["minimum_write_protocol"] == 1
                assert activated["changed"] is True
                # Re-read the committed per-tenant state rather than relying on
                # the baseline organization's activation or a global switch.
                persisted = cutover_status(
                    Settings(database_url=database_url, cutover_enabled=True),
                    organization_id=organization_id,
                )
                assert persisted["organization_id"] == organization_id
                assert persisted["minimum_write_protocol"] == 1
                assert persisted["cutover_enabled"] is True
                assert persisted["dataset_incarnation"] == activated["dataset_incarnation"]
    finally:
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
    seed_administration_identities(database_url)
    if __package__:
        from .branding_fixtures import seed_branding_identities
    else:
        from branding_fixtures import seed_branding_identities

    seed_branding_identities(database_url)
    if __package__:
        from .inventory_fixtures import seed_inventory_identities
    else:
        from inventory_fixtures import seed_inventory_identities

    seed_inventory_identities(database_url)
    print(f"E2E database ready for organization {E2E_ORGANIZATION_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
