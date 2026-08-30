from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from cycling_workshop.app import create_app
from cycling_workshop.db.base import Base
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.security import SessionTokenService
from cycling_workshop.settings import Settings
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord


def build_client() -> tuple[TestClient, SessionTokenService]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add(OrganizationRecord(id="org-1", name="Taller Uno"))
        session.add(LocationRecord(id="loc-1", organization_id="org-1", name="Principal"))
        session.add(
            UserRecord(
                id="user-1",
                organization_id="org-1",
                location_id="loc-1",
                username="test-user",
                display_name="Test User",
                password_hash="unused-in-token-tests",
                capabilities=["customers.read", "customers.write", "sync.pull", "sync.push"],
                is_active=True,
                session_version=1,
            )
        )
        session.commit()

    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        log_level="WARNING",
        auth_secret="test-secret-that-is-long-enough-for-tests",
    )
    app = create_app(settings=settings, session_factory=factory)
    return TestClient(app), app.state.session_tokens


def token_for(service: SessionTokenService, *, capabilities: set[str]) -> str:
    return service.issue(
        Principal(
            user_id="user-1",
            organization_id="org-1",
            location_id="loc-1",
            capabilities=frozenset(capabilities),
        )
    )


def test_create_and_get_customer_with_matching_capabilities() -> None:
    client, service = build_client()
    token = token_for(service, capabilities={"customers.read", "customers.write"})

    created = client.post(
        "/api/v1/customers",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "location_id": "loc-1",
            "display_name": "Ana Rivera",
            "email": "ANA@example.com",
        },
    )

    assert created.status_code == 201
    payload = created.json()
    assert payload["display_name"] == "Ana Rivera"
    assert payload["email"] == "ana@example.com"

    loaded = client.get(
        f"/api/v1/customers/{payload['customer_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert loaded.status_code == 200
    assert loaded.json()["customer_id"] == payload["customer_id"]


def test_customer_create_is_denied_without_write_capability() -> None:
    client, service = build_client()
    token = token_for(service, capabilities={"customers.read"})

    response = client.post(
        "/api/v1/customers",
        headers={"Authorization": f"Bearer {token}"},
        json={"location_id": "loc-1", "display_name": "Ana Rivera"},
    )

    assert response.status_code == 403


def test_customer_get_is_denied_without_read_capability() -> None:
    client, service = build_client()
    writer = token_for(service, capabilities={"customers.write"})
    created = client.post(
        "/api/v1/customers",
        headers={"Authorization": f"Bearer {writer}"},
        json={"location_id": "loc-1", "display_name": "Ana Rivera"},
    )
    assert created.status_code == 201

    response = client.get(
        f"/api/v1/customers/{created.json()['customer_id']}",
        headers={"Authorization": f"Bearer {writer}"},
    )
    assert response.status_code == 403
