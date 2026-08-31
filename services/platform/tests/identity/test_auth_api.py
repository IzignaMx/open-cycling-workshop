from __future__ import annotations

from cycling_workshop.app import create_app
from cycling_workshop.db.base import Base
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.security import PasswordService
from cycling_workshop.settings import Settings
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_client(*, active: bool = True, username: str = "Admin") -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    password_hash = PasswordService().hash("correct horse battery staple")
    with factory() as session:
        session.add(OrganizationRecord(id="org-1", name="Taller Uno"))
        session.add(LocationRecord(id="loc-1", organization_id="org-1", name="Principal"))
        session.add(
            UserRecord(
                id="user-1",
                organization_id="org-1",
                location_id="loc-1",
                username=username.lower(),
                display_name="Administración",
                password_hash=password_hash,
                capabilities=["customers.read", "customers.write", "sync.pull", "sync.push"],
                is_active=active,
            )
        )
        session.commit()

    app = create_app(
        settings=Settings(
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
            log_level="WARNING",
            auth_secret="test-secret-that-is-long-enough-for-tests",
        ),
        session_factory=factory,
    )
    return TestClient(app)


def test_login_returns_bearer_token_and_me_reflects_persisted_scope() -> None:
    client = build_client()

    login = client.post(
        "/api/v1/auth/login",
        json={
            "organization_id": "org-1",
            "username": "  ADMIN ",
            "password": "correct horse battery staple",
        },
    )

    assert login.status_code == 200
    payload = login.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {payload['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json() == {
        "user_id": "user-1",
        "organization_id": "org-1",
        "location_id": "loc-1",
        "display_name": "Administración",
        "capabilities": ["customers.read", "customers.write", "sync.pull", "sync.push"],
    }


def test_login_rejects_wrong_password_with_generic_credentials_error() -> None:
    client = build_client()

    response = client.post(
        "/api/v1/auth/login",
        json={
            "organization_id": "org-1",
            "username": "admin",
            "password": "definitely wrong password",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid credentials"


def test_inactive_user_cannot_login() -> None:
    client = build_client(active=False)

    response = client.post(
        "/api/v1/auth/login",
        json={
            "organization_id": "org-1",
            "username": "admin",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid credentials"


def test_logout_all_invalidates_the_current_session_version() -> None:
    client = build_client()
    login = client.post(
        "/api/v1/auth/login",
        json={
            "organization_id": "org-1",
            "username": "admin",
            "password": "correct horse battery staple",
        },
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    revoked = client.post("/api/v1/auth/logout-all", headers=headers)

    assert revoked.status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_persisted_capability_revocation_takes_effect_before_token_expiry() -> None:
    client = build_client()
    login = client.post(
        "/api/v1/auth/login",
        json={
            "organization_id": "org-1",
            "username": "admin",
            "password": "correct horse battery staple",
        },
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    factory = client.app.state.session_factory
    with factory() as session:
        account = session.get(UserRecord, "user-1")
        assert account is not None
        account.capabilities = ["customers.read"]
        session.commit()

    response = client.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "customer_id": "018f0000-0000-7000-8000-000000000999",
            "display_name": "No autorizado",
            "location_id": "loc-1",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "capability denied"
