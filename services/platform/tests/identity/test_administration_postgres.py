"""Real PostgreSQL administration contention in exclusively owned test schemas.

These tests never fall back to SQLite. Without an explicit, safe
OCWP_TEST_DATABASE_URL, PostgreSQL behavior remains unverified. The URL guard is
shared with migration tests so connection-routing restrictions cannot diverge.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from cycling_workshop.api.errors import ApiError
from cycling_workshop.app import create_app
from cycling_workshop.identity.admin_cli import create_first_owner
from cycling_workshop.identity.audit import IdentityAuditRecord
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.roles import CAPABILITIES
from cycling_workshop.identity.security import PasswordService
from cycling_workshop.settings import Settings
from cycling_workshop.shared.ids import new_id
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema
from test_identity_migration import safe_access_postgres_url

ADMIN = "/api/v1/admin/users"
PASSWORD = "synthetic-postgres-test-password"
NEW_PASSWORD = "synthetic-postgres-replacement-password"


def _configured_postgres_url(monkeypatch: pytest.MonkeyPatch) -> URL:
    configured = os.getenv("OCWP_TEST_DATABASE_URL")
    if not configured:
        pytest.skip("OCWP_TEST_DATABASE_URL not configured; PostgreSQL concurrency unverified")
    # Validate BEFORE clearing: do not silently ignore a requested redirect.
    url = safe_access_postgres_url(configured)
    for variable in tuple(os.environ):
        if variable.startswith("PG") or variable in {
            "OCWP_DATABASE_URL",
            "OCWP_DATABASE_URL_FILE",
            "OCWP_E2E_DATABASE_URL",
            "OCWP_TEST_DATABASE_URL",
        }:
            monkeypatch.delenv(variable, raising=False)
    return url


def _migration_config(url: URL) -> Config:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("prepend_sys_path", str(root / "src"))
    config.set_main_option(
        "sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%")
    )
    config.set_main_option("sqlalchemy.hide_parameters", "true")
    return config


@dataclass(frozen=True)
class HttpCommand:
    method: str
    path: str
    headers: dict[str, str]
    payload: dict[str, Any] | None = None


@dataclass
class AdministrationPostgres:
    app: FastAPI
    engine: Engine
    factory: sessionmaker[Session]
    application_name: str
    organization_id: str
    location_id: str
    other_location_id: str
    foreign_organization_id: str
    foreign_location_id: str
    password_hash: str

    def seed(
        self,
        *,
        owner: bool = False,
        location_id: str | None = None,
        organization_id: str | None = None,
        capabilities: frozenset[str] = CAPABILITIES,
    ) -> str:
        user_id = new_id()
        with self.factory.begin() as session:
            session.add(
                UserRecord(
                    id=user_id,
                    organization_id=organization_id or self.organization_id,
                    location_id=location_id,
                    username=f"synthetic-{user_id}",
                    display_name="Synthetic PostgreSQL identity",
                    password_hash=self.password_hash,
                    capabilities=sorted(capabilities),
                    is_active=True,
                    is_owner=owner,
                    version=1,
                    session_version=1,
                )
            )
        return user_id

    def headers(self, user_id: str, *, organization_id: str | None = None) -> dict[str, str]:
        response = self.request(
            HttpCommand(
                "POST",
                "/api/v1/auth/login",
                {},
                {
                    "organization_id": organization_id or self.organization_id,
                    "username": f"synthetic-{user_id}",
                    "password": PASSWORD,
                },
            )
        )
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def request(self, command: HttpCommand) -> Response:
        # Independent ASGI clients and real request sessions for every caller.
        with TestClient(self.app, raise_server_exceptions=False) as client:
            return client.request(
                command.method, command.path, headers=command.headers, json=command.payload
            )

    def user(self, user_id: str) -> UserRecord:
        with self.factory() as session:
            user = session.get(UserRecord, user_id)
            assert user is not None
            return user

    def audits(self) -> list[IdentityAuditRecord]:
        with self.factory() as session:
            return list(
                session.scalars(select(IdentityAuditRecord).order_by(IdentityAuditRecord.id))
            )

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        with self.engine.connect() as connection:
            return {
                model.__tablename__: [
                    dict(row)
                    for row in connection.execute(
                        select(model.__table__).order_by(model.__table__.c.id)
                    ).mappings()
                ]
                for model in (UserRecord, LocationRecord, IdentityAuditRecord)
            }

    def lock_organization(self, blocker: Session) -> None:
        assert (
            blocker.scalar(
                select(OrganizationRecord)
                .where(OrganizationRecord.id == self.organization_id)
                .with_for_update()
            )
            is not None
        )

    def wait_for_lock_waiters(self, futures: Sequence[Future[Any]]) -> set[int]:
        """Observe real server lock waits, rather than assuming thread timing."""
        deadline = time.monotonic() + 10
        waiting: set[int] = set()
        # Each query gets a fresh statistics snapshot. This connection shares
        # only our schema/application name, never another test's table namespace.
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
            while time.monotonic() < deadline:
                waiting = set(
                    observer.scalars(
                        text(
                            "SELECT pid FROM pg_stat_activity "
                            "WHERE application_name = :application_name "
                            "AND state = 'active' AND wait_event_type = 'Lock' "
                            "AND query ILIKE '%organizations%' "
                            "AND query ILIKE '%FOR UPDATE%' "
                            "AND cardinality(pg_blocking_pids(pid)) > 0"
                        ),
                        {"application_name": self.application_name},
                    )
                )
                if len(waiting) == len(futures) or any(future.done() for future in futures):
                    break
                time.sleep(0.02)
        return waiting

    def race(self, first: HttpCommand, second: HttpCommand) -> list[Response]:
        with self.factory() as blocker, ThreadPoolExecutor(max_workers=2) as executor:
            self.lock_organization(blocker)
            futures = [executor.submit(self.request, command) for command in (first, second)]
            try:
                waiting = self.wait_for_lock_waiters(futures)
            finally:
                # Even an assertion or observer failure must release the lock.
                blocker.rollback()
            responses = [future.result(timeout=25) for future in futures]
        assert len(waiting) == 2, (
            "Both requests must wait in distinct PostgreSQL sessions on the organization lock; "
            f"observed={len(waiting)}, statuses={[response.status_code for response in responses]}"
        )
        return responses


@pytest.fixture
def administration_postgres(monkeypatch: pytest.MonkeyPatch) -> Iterator[AdministrationPostgres]:
    url = _configured_postgres_url(monkeypatch)
    schema = f"ocwp_access_{uuid4().hex}"
    application_name = f"ocwp-access-{uuid4().hex}"
    admin = create_engine(
        url,
        hide_parameters=True,
        connect_args={"options": "-csearch_path=pg_catalog", "connect_timeout": 5},
    )
    isolated_url = url.update_query_dict(
        {
            "options": f"-csearch_path={schema} -clock_timeout=15000 -cstatement_timeout=20000",
            "application_name": application_name,
            "connect_timeout": "5",
        }
    )
    engine = create_engine(isolated_url, hide_parameters=True, pool_size=8, max_overflow=0)
    created = False
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        created = True
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == schema
            assert connection.scalar(text("SHOW search_path")) == schema
            assert connection.scalar(text("SELECT current_database()")) == url.database
            assert int(connection.scalar(text("SHOW server_version_num"))) >= 180000
        command.upgrade(_migration_config(isolated_url), "head")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0013"
        factory = sessionmaker(engine, expire_on_commit=False)
        organization, location, other_location, foreign_organization, foreign_location = (
            new_id() for _ in range(5)
        )
        with factory.begin() as session:
            session.add_all(
                [
                    OrganizationRecord(id=organization, name="Synthetic access workshop"),
                    OrganizationRecord(id=foreign_organization, name="Synthetic foreign workshop"),
                ]
            )
            session.flush()
            session.add_all(
                [
                    LocationRecord(id=location, organization_id=organization, name="Synthetic A"),
                    LocationRecord(
                        id=other_location, organization_id=organization, name="Synthetic B"
                    ),
                    LocationRecord(
                        id=foreign_location,
                        organization_id=foreign_organization,
                        name="Synthetic foreign",
                    ),
                ]
            )
        settings = Settings(
            environment="test",
            database_url=isolated_url.render_as_string(hide_password=False),
            log_level="WARNING",
            auth_secret="synthetic-access-postgres-session-secret-at-least-32",
        )
        yield AdministrationPostgres(
            create_app(settings, session_factory=factory),
            engine,
            factory,
            application_name,
            organization,
            location,
            other_location,
            foreign_organization,
            foreign_location,
            PasswordService().hash(PASSWORD),
        )
    finally:
        engine.dispose()
        try:
            if created:
                # Append-only audit guards intentionally reject DELETE/TRUNCATE.
                # Drop only this fixture's unpredictable, exclusively owned schema.
                with admin.begin() as connection:
                    connection.execute(DropSchema(schema, cascade=True))
        finally:
            admin.dispose()


def test_two_last_owners_cannot_both_demote_themselves(
    administration_postgres: AdministrationPostgres,
) -> None:
    db = administration_postgres
    owners = [db.seed(owner=True) for _ in range(2)]
    commands = [
        HttpCommand(
            "PATCH",
            f"{ADMIN}/{owner}",
            db.headers(owner),
            {"expected_version": 1, "is_owner": False},
        )
        for owner in owners
    ]

    responses = db.race(*commands)

    assert sorted(response.status_code for response in responses) == [200, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["error"]["code"] == "last_owner"
    users = [db.user(owner) for owner in owners]
    assert sum(user.is_active and user.is_owner for user in users) == 1
    assert sorted(user.version for user in users) == [1, 2]
    assert sorted(user.session_version for user in users) == [1, 2]
    winner = users[responses.index(next(r for r in responses if r.status_code == 200))]
    audit = db.audits()
    assert len(audit) == 1
    assert audit[0].actor_id == audit[0].target_id == winner.id
    assert audit[0].action == "user.updated"


def test_first_owner_commands_race_without_promoting_legacy_accounts(
    administration_postgres: AdministrationPostgres,
    tmp_path: Path,
) -> None:
    db = administration_postgres
    legacy = db.seed(location_id=db.location_id, capabilities=frozenset({"*"}))
    before = db.snapshot()["users"]
    password_file = tmp_path / "synthetic-owner-password"
    password_file.write_text(PASSWORD + "\n", encoding="utf-8")
    password_file.chmod(0o600)

    def establish(username: str) -> tuple[bool, str]:
        try:
            result = create_first_owner(
                db.app.state.settings,
                organization_id=db.organization_id,
                username=username,
                display_name="Synthetic explicit owner",
                password_file=password_file,
            )
        except ApiError as error:
            assert error.status_code == 409
            return False, error.code
        return True, str(result["user_id"])

    with db.factory() as blocker, ThreadPoolExecutor(max_workers=2) as executor:
        db.lock_organization(blocker)
        futures = [executor.submit(establish, f"synthetic-owner-{index}") for index in range(2)]
        try:
            waiting = db.wait_for_lock_waiters(futures)
        finally:
            blocker.rollback()
        outcomes = [future.result(timeout=25) for future in futures]

    assert len(waiting) == 2, "Both CLI transactions must wait on the same Organization row"
    assert sorted(success for success, _ in outcomes) == [False, True]
    assert (
        next(detail for success, detail in outcomes if not success) == "owner_already_established"
    )
    owner_id = next(detail for success, detail in outcomes if success)
    with db.factory() as session:
        owners = list(session.scalars(select(UserRecord).where(UserRecord.is_owner.is_(True))))
    assert len(owners) == 1
    assert owners[0].id == owner_id
    assert owners[0].is_active and owners[0].location_id is None
    assert set(owners[0].capabilities) == CAPABILITIES
    assert (owners[0].version, owners[0].session_version) == (1, 1)
    assert PasswordService().verify(owners[0].password_hash, PASSWORD)
    assert [row for row in db.snapshot()["users"] if row["id"] == legacy] == before
    audit = db.audits()
    assert len(audit) == 1
    assert audit[0].target_id == owner_id and audit[0].actor_id is None
    assert audit[0].action == "user.first_owner_created"


def test_same_target_stale_versions_cannot_both_commit(
    administration_postgres: AdministrationPostgres,
) -> None:
    db = administration_postgres
    actor = db.seed(owner=True)
    target = db.seed(capabilities=frozenset({"customers.read"}))
    headers = db.headers(actor)
    commands = [
        HttpCommand(
            "PATCH",
            f"{ADMIN}/{target}",
            headers,
            {"expected_version": 1, "display_name": name},
        )
        for name in ("Synthetic first", "Synthetic second")
    ]

    responses = db.race(*commands)

    assert sorted(response.status_code for response in responses) == [200, 409]
    success = next(response for response in responses if response.status_code == 200)
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["error"]["code"] == "stale_user_version"
    target_user = db.user(target)
    assert target_user.display_name == success.json()["display_name"]
    assert (target_user.version, target_user.session_version) == (2, 1)
    assert len(db.audits()) == 1
    assert db.audits()[0].target_id == target


def test_normalized_duplicate_creation_has_one_account_and_one_audit(
    administration_postgres: AdministrationPostgres,
) -> None:
    db = administration_postgres
    owner = db.seed(owner=True)
    headers = db.headers(owner)
    commands = [
        HttpCommand(
            "POST",
            ADMIN,
            headers,
            {
                "username": username,
                "display_name": "Synthetic mechanic",
                "location_id": db.location_id,
                "capabilities": ["customers.read", "orders.read"],
                "password": PASSWORD,
            },
        )
        for username in ("  SyNtHeTiC-MeChAnIc  ", "synthetic-mechanic")
    ]

    responses = db.race(*commands)

    assert sorted(response.status_code for response in responses) == [201, 409]
    success = next(response for response in responses if response.status_code == 201)
    assert success.json()["username"] == "synthetic-mechanic"
    assert success.json()["capabilities"] == ["customers.read", "orders.read"]
    with db.factory() as session:
        users = list(
            session.scalars(
                select(UserRecord).where(
                    UserRecord.organization_id == db.organization_id,
                    UserRecord.username == "synthetic-mechanic",
                )
            )
        )
    assert len(users) == 1
    assert (users[0].version, users[0].session_version) == (1, 1)
    assert PasswordService().verify(users[0].password_hash, PASSWORD)
    assert len(db.audits()) == 1
    assert db.audits()[0].target_id == users[0].id


@pytest.mark.parametrize(
    ("change", "expected_status"),
    [("grants", 403), ("session", 401), ("deactivate", 401), ("scope", 403)],
)
def test_actor_authority_is_reloaded_after_organization_lock_wait(
    administration_postgres: AdministrationPostgres,
    change: str,
    expected_status: int,
) -> None:
    db = administration_postgres
    actor = db.seed()
    target = db.seed(location_id=db.location_id, capabilities=frozenset({"customers.read"}))
    request = HttpCommand(
        "PATCH",
        f"{ADMIN}/{target}",
        db.headers(actor),
        {"expected_version": 1, "display_name": "Must never be written"},
    )
    before_target = db.user(target)
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        db.lock_organization(blocker)
        future = executor.submit(db.request, request)
        try:
            waiting = db.wait_for_lock_waiters([future])
            assert len(waiting) == 1, "Request must authenticate before waiting on the org lock"
            actor_row = blocker.get(UserRecord, actor)
            assert actor_row is not None
            # Direct fixture writes isolate each reload check. In particular,
            # grants/scope change without a session bump must still be denied.
            if change == "grants":
                actor_row.capabilities = sorted(CAPABILITIES - {"users.write"})
            elif change == "session":
                actor_row.session_version += 1
            elif change == "deactivate":
                actor_row.is_active = False
            else:
                actor_row.location_id = db.other_location_id
            actor_row.version += 1
            blocker.commit()
        finally:
            blocker.rollback()
        response = future.result(timeout=25)

    assert response.status_code == expected_status
    target_user = db.user(target)
    assert (target_user.display_name, target_user.version, target_user.session_version) == (
        before_target.display_name,
        1,
        1,
    )
    assert target_user.password_hash == before_target.password_hash
    assert db.audits() == []


@pytest.mark.parametrize("change", ["session", "deactivate", "scope", "grants", "widen"])
def test_current_user_revalidates_after_organization_lock_wait(
    administration_postgres: AdministrationPostgres, change: str
) -> None:
    db = administration_postgres
    actor = db.seed(capabilities=frozenset({"customers.read", "sync.pull"}))
    token = db.app.state.session_tokens.issue(
        Principal(actor, db.organization_id, db.location_id, frozenset({"customers.read"}))
    )
    request = HttpCommand("GET", "/api/v1/auth/me", {"Authorization": f"Bearer {token}"})
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        db.lock_organization(blocker)
        future = executor.submit(db.request, request)
        try:
            waiting = db.wait_for_lock_waiters([future])
            assert len(waiting) == 1, "Current-user read must wait behind administration"
            account = blocker.get(UserRecord, actor)
            assert account is not None
            if change == "session":
                account.session_version += 1
            elif change == "deactivate":
                account.is_active = False
            elif change == "scope":
                account.location_id = db.other_location_id
            elif change == "grants":
                account.capabilities = []
            else:
                account.capabilities = sorted(CAPABILITIES)
            blocker.commit()
        finally:
            blocker.rollback()
        response = future.result(timeout=25)

    if change in {"session", "deactivate", "scope"}:
        assert response.status_code == 401
        assert response.json()["detail"] == "invalid session"
    else:
        assert response.status_code == 200
        assert response.json()["capabilities"] == ([] if change == "grants" else ["customers.read"])
        assert response.json()["location_id"] == db.location_id
    assert db.audits() == []


def test_concurrent_logout_and_admin_revoke_preserve_every_successful_increment(
    administration_postgres: AdministrationPostgres,
) -> None:
    db = administration_postgres
    owner = db.seed(owner=True)
    target = db.seed(capabilities=frozenset({"customers.read"}))
    admin_headers, target_headers = db.headers(owner), db.headers(target)
    logout = HttpCommand("POST", "/api/v1/auth/logout-all", target_headers)
    revoke = HttpCommand(
        "POST", f"{ADMIN}/{target}/revoke-sessions", admin_headers, {"expected_version": 1}
    )

    logout_response, revoke_response = db.race(logout, revoke)

    # PostgreSQL does not promise which waiter runs first. Either the logout
    # invalidates the expected version or revocation invalidates the session.
    assert (logout_response.status_code, revoke_response.status_code) in {(204, 409), (401, 200)}
    target_user = db.user(target)
    assert (target_user.version, target_user.session_version) == (2, 2)
    assert len(db.audits()) == 1
    assert db.request(HttpCommand("GET", "/api/v1/auth/me", target_headers)).status_code == 401
    # Retry the rejected intent with fresh authority/preconditions; both
    # successful mutations must remain represented rather than overwrite one.
    if revoke_response.status_code == 409:
        retry = HttpCommand("POST", revoke.path, admin_headers, {"expected_version": 2})
        assert db.request(retry).status_code == 200
    else:
        retry = HttpCommand("POST", logout.path, db.headers(target))
        assert db.request(retry).status_code == 204
    target_user = db.user(target)
    assert (target_user.version, target_user.session_version) == (3, 3)
    audit = db.audits()
    assert len(audit) == 2
    assert all(event.target_id == target for event in audit)
    assert [event.before["session_version"] for event in audit] == [1, 2]
    assert [event.after["session_version"] for event in audit] == [2, 3]


@pytest.mark.parametrize(
    "operation", ["create", "patch", "reset", "revoke", "logout", "password", "location"]
)
def test_failed_audit_insert_rolls_back_every_mutation(
    administration_postgres: AdministrationPostgres,
    operation: str,
) -> None:
    db = administration_postgres
    actor = db.seed(owner=True)
    target = db.seed(location_id=db.location_id, capabilities=frozenset({"customers.read"}))
    headers = db.headers(actor)
    requests = {
        "create": HttpCommand(
            "POST",
            ADMIN,
            headers,
            {
                "username": "synthetic-rollback",
                "display_name": "Synthetic rollback",
                "location_id": db.location_id,
                "role": "TechnicalAdmin",
                "password": PASSWORD,
            },
        ),
        "patch": HttpCommand(
            "PATCH",
            f"{ADMIN}/{target}",
            headers,
            {
                "expected_version": 1,
                "display_name": "Must roll back",
                "is_active": False,
            },
        ),
        "reset": HttpCommand(
            "POST",
            f"{ADMIN}/{target}/reset-password",
            headers,
            {
                "expected_version": 1,
                "new_password": NEW_PASSWORD,
            },
        ),
        "revoke": HttpCommand(
            "POST",
            f"{ADMIN}/{target}/revoke-sessions",
            headers,
            {
                "expected_version": 1,
            },
        ),
        "logout": HttpCommand("POST", "/api/v1/auth/logout-all", headers),
        "password": HttpCommand(
            "POST",
            "/api/v1/auth/change-password",
            headers,
            {
                "current_password": PASSWORD,
                "new_password": NEW_PASSWORD,
            },
        ),
        "location": HttpCommand(
            "POST",
            "/api/v1/locations",
            headers,
            {
                "name": "Must roll back",
            },
        ),
    }
    before = db.snapshot()
    with db.engine.begin() as connection:
        connection.execute(
            text(
                "CREATE FUNCTION reject_test_audit_insert() RETURNS trigger LANGUAGE plpgsql "
                "AS $$ BEGIN RAISE EXCEPTION 'synthetic audit failure' "
                "USING ERRCODE = '23514'; END; $$"
            )
        )
        connection.execute(
            text(
                "CREATE TRIGGER reject_test_audit_insert BEFORE INSERT ON identity_audit_events "
                "FOR EACH STATEMENT EXECUTE FUNCTION reject_test_audit_insert()"
            )
        )

    response = db.request(requests[operation])

    assert response.status_code == 503
    assert PASSWORD not in response.text and NEW_PASSWORD not in response.text
    assert "synthetic audit failure" not in response.text
    assert db.snapshot() == before
    assert db.request(HttpCommand("GET", "/api/v1/auth/me", headers)).status_code == 200
    assert PasswordService().verify(db.user(actor).password_hash, PASSWORD)
    assert PasswordService().verify(db.user(target).password_hash, PASSWORD)
    assert not PasswordService().verify(db.user(actor).password_hash, NEW_PASSWORD)
    assert not PasswordService().verify(db.user(target).password_hash, NEW_PASSWORD)


def test_scoped_reads_and_exact_grant_replacement_on_postgres(
    administration_postgres: AdministrationPostgres,
) -> None:
    db = administration_postgres
    actor = db.seed(location_id=db.location_id)
    visible = db.seed(location_id=db.location_id, capabilities=frozenset({"customers.read"}))
    db.seed(location_id=db.other_location_id)
    db.seed(owner=True)
    db.seed(organization_id=db.foreign_organization_id, location_id=db.foreign_location_id)
    headers = db.headers(actor)

    page = db.request(HttpCommand("GET", ADMIN, headers))
    locations = db.request(HttpCommand("GET", "/api/v1/locations", headers))

    assert page.status_code == locations.status_code == 200
    assert {row["user_id"] for row in page.json()["items"]} == {actor, visible}
    assert page.json()["next_cursor"] is None
    assert [row["location_id"] for row in locations.json()["items"]] == [db.location_id]
    replacement = db.request(
        HttpCommand(
            "PATCH",
            f"{ADMIN}/{visible}",
            headers,
            {
                "expected_version": 1,
                "capabilities": ["orders.read"],
            },
        )
    )
    assert replacement.status_code == 200
    assert replacement.json()["capabilities"] == ["orders.read"]
    user = db.user(visible)
    assert user.capabilities == ["orders.read"]
    assert (user.version, user.session_version) == (2, 2)
    event = db.audits()[0]
    assert event.before["capabilities"] == ["customers.read"]
    assert event.after["capabilities"] == ["orders.read"]


@pytest.mark.parametrize(
    "violation", ["old_grants", "new_grants", "old_scope", "new_scope", "foreign_tenant"]
)
def test_old_and_new_target_scope_and_grants_are_enforced_on_postgres(
    administration_postgres: AdministrationPostgres,
    violation: str,
) -> None:
    db = administration_postgres
    actor = db.seed(
        location_id=db.location_id,
        capabilities=frozenset(
            {
                "users.read",
                "users.write",
                "users.grants.write",
                "customers.read",
            }
        ),
    )
    target = db.seed(
        organization_id=db.foreign_organization_id if violation == "foreign_tenant" else None,
        location_id=(
            db.foreign_location_id
            if violation == "foreign_tenant"
            else db.other_location_id
            if violation == "old_scope"
            else db.location_id
        ),
        capabilities=frozenset({"orders.read" if violation == "old_grants" else "customers.read"}),
    )
    payload: dict[str, Any] = {"expected_version": 1, "display_name": "Must not change"}
    if violation == "new_grants":
        payload["capabilities"] = ["orders.read"]
    if violation == "new_scope":
        payload["location_id"] = db.other_location_id
    before = db.snapshot()

    response = db.request(HttpCommand("PATCH", f"{ADMIN}/{target}", db.headers(actor), payload))

    assert response.status_code == (404 if violation == "foreign_tenant" else 403)
    assert db.snapshot() == before


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://localhost/workshop",
        "postgresql://db.example/workshop_test",
        "postgresql://localhost/workshop_test?host=db.example",
        "postgresql://localhost/workshop_test?options=-csearch_path%3Dpublic",
        "postgresql://localhost/workshop_test?service=production",
        "sqlite:///workshop_test",
    ],
)
def test_administration_fixture_rejects_unsafe_targets_before_connection(
    monkeypatch: pytest.MonkeyPatch,
    url: str,
) -> None:
    monkeypatch.setenv("OCWP_TEST_DATABASE_URL", url)
    with pytest.raises(ValueError, match="loopback PostgreSQL"):
        _configured_postgres_url(monkeypatch)
    assert os.environ["OCWP_TEST_DATABASE_URL"] == url


@pytest.mark.parametrize(
    "variable",
    [
        "PGHOST",
        "PGHOSTADDR",
        "PGPORT",
        "PGDATABASE",
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGSYSCONFDIR",
        "PGOPTIONS",
    ],
)
def test_administration_fixture_rejects_ambient_routing_before_clearing_it(
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
) -> None:
    monkeypatch.setenv("OCWP_TEST_DATABASE_URL", "postgresql://localhost/ocwp_e2e")
    monkeypatch.setenv(variable, "unsafe-synthetic-routing")
    with pytest.raises(ValueError, match="ambient libpq connection overrides"):
        _configured_postgres_url(monkeypatch)
    assert os.environ[variable] == "unsafe-synthetic-routing"


def test_administration_fixture_clears_ambient_credentials_and_application_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable in tuple(os.environ):
        if variable.startswith("PG"):
            monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("OCWP_TEST_DATABASE_URL", "postgresql://localhost/ocwp_e2e")
    monkeypatch.setenv("PGPASSWORD", "synthetic-password")
    monkeypatch.setenv("PGPASSFILE", "synthetic-file")
    monkeypatch.setenv("PGUSER", "synthetic-user")
    monkeypatch.setenv("OCWP_DATABASE_URL", "postgresql://db.example/production")
    monkeypatch.setenv("OCWP_E2E_DATABASE_URL", "postgresql://db.example/production")

    url = _configured_postgres_url(monkeypatch)

    assert url.database == "ocwp_e2e"
    assert not any(variable.startswith("PG") for variable in os.environ)
    assert all(
        variable not in os.environ
        for variable in (
            "OCWP_DATABASE_URL",
            "OCWP_E2E_DATABASE_URL",
            "OCWP_TEST_DATABASE_URL",
        )
    )


def test_administration_fixture_clears_file_backed_application_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable in tuple(os.environ):
        if variable.startswith("PG"):
            monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("OCWP_TEST_DATABASE_URL", "postgresql://localhost/ocwp_e2e")
    monkeypatch.setenv("OCWP_DATABASE_URL_FILE", "/synthetic/production-database-url")
    _configured_postgres_url(monkeypatch)
    assert "OCWP_DATABASE_URL_FILE" not in os.environ
