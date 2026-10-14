"""Commit-order guarantees require PostgreSQL, never a SQLite substitute.

Every test owns a fresh migrated schema on a validated loopback test database.
Server-observed lock waits establish the interleaving; sleeps do not assert it.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from cycling_workshop.api.errors import ApiError
from cycling_workshop.app import create_app
from cycling_workshop.identity.cutover import WriteAdmission
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.security import PasswordService
from cycling_workshop.settings import Settings
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.domain import ChangePage, MutationEnvelope
from cycling_workshop.sync.models import ChangeRecord
from cycling_workshop.sync.service import SyncService
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema
from test_postgres_integration import postgres_url


@dataclass
class FeedDatabase:
    engine: Engine
    factory: sessionmaker[Session]
    url: str = field(repr=False)
    application_name: str

    def mutation(self, organization: str = "org-a") -> MutationEnvelope:
        return MutationEnvelope(
            mutation_id=new_id(),
            entity_type="customer",
            entity_id=new_id(),
            operation="create",
            organization_id=organization,
            location_id=f"{organization}-location",
            base_version=None,
            occurred_at=datetime.now(UTC),
            payload={"display_name": "Synthetic customer"},
        )

    def apply(self, mutation: MutationEnvelope) -> int:
        with self.factory.begin() as session:
            SyncService.for_fixtures(session).apply(mutation)
            return cursor_for(session, mutation.entity_id)

    def page(self, organization: str = "org-a", after: int = 0) -> ChangePage:
        with self.factory() as session:
            return SyncService.for_fixtures(session).pull_changes(
                organization_id=organization,
                location_id=None,
                capabilities=frozenset({"customers.read"}),
                after_cursor=after,
                limit=1,
            )

    def wait_for_blocked_writer(self, future: Future[Any]) -> None:
        deadline = time.monotonic() + 10
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
            while time.monotonic() < deadline:
                waiting = observer.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE application_name = :name AND wait_event_type = 'Lock' "
                        "AND query ILIKE '%organizations%' AND query ILIKE '%FOR UPDATE%' "
                        "AND cardinality(pg_blocking_pids(pid)) > 0"
                    ),
                    {"name": self.application_name},
                )
                if waiting:
                    assert not future.done()
                    return
                if future.done():
                    future.result()  # Surface unexpected errors before the ordering assertion.
                    pytest.fail("Writer completed instead of waiting behind the organization lock")
                time.sleep(0.01)
        pytest.fail("No PostgreSQL organization-lock waiter observed")


def cursor_for(session: Session, entity_id: str) -> int:
    cursor = session.scalar(select(ChangeRecord.cursor).where(ChangeRecord.entity_id == entity_id))
    assert cursor is not None
    return cursor


@pytest.fixture
def feed_database(monkeypatch: pytest.MonkeyPatch) -> Iterator[FeedDatabase]:
    url = make_url(postgres_url())  # Shared production-target rejection before any connection.
    routing = {
        "PGHOST",
        "PGHOSTADDR",
        "PGPORT",
        "PGDATABASE",
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGSYSCONFDIR",
        "PGOPTIONS",
    }
    if any(os.getenv(key) for key in routing):
        raise ValueError("PostgreSQL ordering tests reject ambient libpq connection overrides")
    for key in tuple(os.environ):
        if key.startswith("PG") or key in {"OCWP_DATABASE_URL", "OCWP_DATABASE_URL_FILE"}:
            monkeypatch.delenv(key, raising=False)
    schema = f"ocwp_feed_{uuid4().hex}"
    application_name = f"ocwp-feed-{uuid4().hex}"
    isolated = url.update_query_dict(
        {
            "options": f"-csearch_path={schema} -clock_timeout=15000 -cstatement_timeout=20000",
            "application_name": application_name,
            "connect_timeout": "5",
        }
    )
    admin = create_engine(
        url,
        connect_args={"options": "-csearch_path=pg_catalog", "connect_timeout": 5},
        hide_parameters=True,
    )
    engine = create_engine(isolated, hide_parameters=True, pool_size=6, max_overflow=0)
    created = False
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        created = True
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == schema
            assert connection.scalar(text("SELECT current_database()")) == url.database
        root = Path(__file__).resolve().parents[2]
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "migrations"))
        config.set_main_option("prepend_sys_path", str(root / "src"))
        config.set_main_option(
            "sqlalchemy.url", isolated.render_as_string(hide_password=False).replace("%", "%%")
        )
        command.upgrade(config, "head")
        factory = sessionmaker(engine, expire_on_commit=False)
        with factory.begin() as session:
            for organization in ("org-a", "org-b"):
                session.add(OrganizationRecord(id=organization, name="Synthetic workshop"))
            session.flush()
            for organization in ("org-a", "org-b"):
                session.add(
                    LocationRecord(
                        id=f"{organization}-location",
                        organization_id=organization,
                        name="Synthetic location",
                    )
                )
        yield FeedDatabase(
            engine, factory, isolated.render_as_string(hide_password=False), application_name
        )
    finally:
        engine.dispose()
        try:
            if created:
                with admin.begin() as connection:
                    connection.execute(DropSchema(schema, cascade=True))
        finally:
            admin.dispose()


@pytest.mark.parametrize("rollback_first", [False, True])
def test_same_organization_cursor_allocation_waits_for_commit_or_rollback(
    feed_database: FeedDatabase,
    rollback_first: bool,
) -> None:
    db = feed_database
    first, second = db.mutation(), db.mutation()
    with ThreadPoolExecutor(max_workers=1) as executor:
        with db.factory() as writer_a:
            SyncService.for_fixtures(writer_a).apply(first)
            first_cursor = cursor_for(writer_a, first.entity_id)
            future = executor.submit(db.apply, second)
            try:
                db.wait_for_blocked_writer(future)
                # A has allocated its cursor but is paused before commit; B cannot publish.
                before = db.page()
                assert before.items == [] and before.next_cursor == 0
            finally:
                if rollback_first:
                    writer_a.rollback()
                else:
                    writer_a.commit()
        second_cursor = future.result(timeout=25)
    assert second_cursor > first_cursor
    page = db.page()
    if rollback_first:
        assert [item.entity_id for item in page.items] == [second.entity_id]
        assert page.next_cursor == second_cursor  # Sequence gaps are safe and not reused.
    else:
        assert [item.entity_id for item in page.items] == [first.entity_id]
        assert page.next_cursor == first_cursor
        page = db.page(after=page.next_cursor)
        assert [item.entity_id for item in page.items] == [second.entity_id]
        assert page.next_cursor == second_cursor
    assert db.page(after=page.next_cursor).items == []


def test_other_organization_commits_while_first_cursor_is_uncommitted(
    feed_database: FeedDatabase,
) -> None:
    db = feed_database
    first, other = db.mutation(), db.mutation("org-b")
    with ThreadPoolExecutor(max_workers=1) as executor, db.factory() as writer_a:
        SyncService.for_fixtures(writer_a).apply(first)
        first_cursor = cursor_for(writer_a, first.entity_id)
        future = executor.submit(db.apply, other)
        try:
            other_cursor = future.result(timeout=10)
            assert other_cursor > first_cursor
            assert db.page().items == []
            assert [item.entity_id for item in db.page("org-b").items] == [other.entity_id]
        finally:
            writer_a.commit()
    assert [item.entity_id for item in db.page().items] == [first.entity_id]


def seed_actor(db: FeedDatabase) -> Principal:
    user_id = new_id()
    with db.factory.begin() as session:
        session.add(
            UserRecord(
                id=user_id,
                organization_id="org-a",
                location_id=None,
                username=user_id,
                display_name="Synthetic writer",
                password_hash=PasswordService().hash("synthetic-password"),
                capabilities=["customers.read", "customers.write"],
                is_active=True,
                is_owner=False,
                version=1,
                session_version=1,
            )
        )
    return Principal(user_id, "org-a", None, frozenset({"customers.read", "customers.write"}))


@pytest.mark.parametrize("change", ["grants", "session", "location", "deactivate"])
def test_waiting_writer_reloads_actor_authority(
    feed_database: FeedDatabase,
    change: str,
) -> None:
    from cycling_workshop.sync.writes import lock_organization, lock_writer

    db = feed_database
    principal = seed_actor(db)

    def waiting_writer() -> Principal:
        with db.factory.begin() as session:
            stale = session.get(UserRecord, principal.user_id)
            assert stale is not None and "customers.write" in stale.capabilities
            return lock_writer(session, principal, WriteAdmission.for_fixtures())

    with ThreadPoolExecutor(max_workers=1) as executor:
        with db.factory() as administrator:
            lock_organization(administrator, "org-a")
            future = executor.submit(waiting_writer)
            try:
                db.wait_for_blocked_writer(future)
                actor = administrator.get(UserRecord, principal.user_id)
                assert actor is not None
                if change == "session":
                    actor.session_version += 1
                elif change == "location":
                    actor.location_id = "org-a-location"
                elif change == "deactivate":
                    actor.is_active = False
                else:
                    actor.capabilities = ["customers.read"]
            finally:
                administrator.commit()
        if change in {"session", "deactivate"}:
            with pytest.raises(ApiError) as error:
                future.result(timeout=25)
            assert error.value.status_code == 401
        elif change == "location":
            assert future.result(timeout=25).location_id == "org-a-location"
        else:
            assert future.result(timeout=25).capabilities == frozenset({"customers.read"})
    assert db.page().items == []


def test_rest_writer_waits_behind_sync_transaction(feed_database: FeedDatabase) -> None:
    db = feed_database
    principal = seed_actor(db)
    app = create_app(
        Settings(
            environment="test",
            database_url=db.url,
            auth_secret="synthetic-feed-secret-at-least-thirty-two-characters",
        ),
        session_factory=db.factory,
    )
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={
                "organization_id": "org-a",
                "username": principal.user_id,
                "password": "synthetic-password",
            },
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    first, second = db.mutation(), db.mutation()

    def rest_writer() -> int:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/customers",
                headers=headers,
                json={
                    "customer_id": second.entity_id,
                    "location_id": second.location_id,
                    "display_name": "Synthetic REST customer",
                },
            )
        assert response.status_code == 201, response.text
        with db.factory() as session:
            return cursor_for(session, second.entity_id)

    with ThreadPoolExecutor(max_workers=1) as executor:
        with db.factory() as writer_a:
            SyncService.for_fixtures(writer_a).apply(first)
            first_cursor = cursor_for(writer_a, first.entity_id)
            future = executor.submit(rest_writer)
            try:
                db.wait_for_blocked_writer(future)
                assert db.page().items == []
            finally:
                writer_a.commit()
        assert future.result(timeout=25) > first_cursor
    first_page = db.page()
    assert [item.entity_id for item in first_page.items] == [first.entity_id]
    assert [item.entity_id for item in db.page(after=first_page.next_cursor).items] == [
        second.entity_id
    ]


def test_identical_concurrent_mutation_replays_only_after_first_commit(
    feed_database: FeedDatabase,
) -> None:
    from cycling_workshop.customers.models import CustomerRecord
    from cycling_workshop.events.models import OutboxRecord
    from cycling_workshop.sync.models import MutationReceiptRecord

    db = feed_database
    mutation = db.mutation()
    with ThreadPoolExecutor(max_workers=1) as executor:
        with db.factory() as writer_a:
            SyncService.for_fixtures(writer_a).apply(mutation)
            first_cursor = cursor_for(writer_a, mutation.entity_id)
            future = executor.submit(db.apply, mutation)
            try:
                db.wait_for_blocked_writer(future)
                assert db.page().items == []
            finally:
                writer_a.commit()
        assert future.result(timeout=25) == first_cursor
    with db.factory() as session:
        for model in (CustomerRecord, MutationReceiptRecord, ChangeRecord, OutboxRecord):
            rows = list(session.scalars(select(model)))
            assert len(rows) == 1, model.__tablename__
        receipt = session.get(MutationReceiptRecord, mutation.mutation_id)
        assert receipt is not None and receipt.entity_id == mutation.entity_id
        assert receipt.status == "applied"
    assert [item.entity_id for item in db.page().items] == [mutation.entity_id]
    assert db.page(after=first_cursor).items == []


def test_http_writer_denied_after_grants_revoked_during_administration_wait(
    feed_database: FeedDatabase,
) -> None:
    from cycling_workshop.customers.models import CustomerRecord
    from cycling_workshop.events.models import OutboxRecord
    from cycling_workshop.identity.administration import AdministrationService
    from cycling_workshop.sync.models import MutationReceiptRecord

    db = feed_database
    principal = seed_actor(db)
    app = create_app(
        Settings(
            environment="test",
            database_url=db.url,
            auth_secret="synthetic-feed-secret-at-least-thirty-two-characters",
        ),
        session_factory=db.factory,
    )
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={
                "organization_id": "org-a",
                "username": principal.user_id,
                "password": "synthetic-password",
            },
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    mutation = db.mutation()

    def rest_writer() -> int:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/customers",
                headers=headers,
                json={
                    "customer_id": mutation.entity_id,
                    "location_id": mutation.location_id,
                    "display_name": "Must not be created",
                },
            )
        return response.status_code

    with ThreadPoolExecutor(max_workers=1) as executor:
        with db.factory() as administrator:
            actor, _ = AdministrationService.for_fixtures(administrator).lock_actor(principal)
            future = executor.submit(rest_writer)
            try:
                # The dependency authorized the old grants; the request is now
                # waiting at its transactional organization lock before effects.
                db.wait_for_blocked_writer(future)
                actor.capabilities = ["customers.read"]
                # Deliberately retain session_version to isolate grant refresh
                # from the independent invalid-session rejection path.
            finally:
                administrator.commit()
        assert future.result(timeout=25) == 403
    with db.factory() as session:
        for model in (CustomerRecord, MutationReceiptRecord, ChangeRecord, OutboxRecord):
            assert list(session.scalars(select(model))) == [], model.__tablename__
    assert db.page().items == []
