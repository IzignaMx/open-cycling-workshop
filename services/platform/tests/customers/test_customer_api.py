from cycling_workshop.app import create_app
from cycling_workshop.db.base import Base
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.security import SessionTokenService
from cycling_workshop.settings import Settings
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


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


def test_normalized_email_overflow_is_safe_422_without_customer_or_change():
    from cycling_workshop.customers.models import CustomerRecord
    from cycling_workshop.sync.models import ChangeRecord
    from sqlalchemy import func, select

    client, service = build_client()
    token = token_for(service, capabilities={"customers.write"})
    value = "İ" * 158 + "@x.co"
    response = client.post(
        "/api/v1/customers",
        headers={"Authorization": f"Bearer {token}"},
        json={"location_id": "loc-1", "display_name": "Public", "email": value},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid customer request"}
    assert value not in response.text
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(CustomerRecord)) == 0
        assert session.scalar(select(func.count()).select_from(ChangeRecord)) == 0


def test_rest_raw_caps_remain_and_supplementary_codepoints_fit_exact_boundary():
    client, service = build_client()
    token = token_for(service, capabilities={"customers.write"})
    headers = {"Authorization": f"Bearer {token}"}
    valid = {
        "location_id": "loc-1",
        "display_name": "🚲" * 200,
        "email": "a" * 314 + "@x.com",
        "phone": "1" * 64,
    }
    accepted = client.post("/api/v1/customers", headers=headers, json=valid)
    assert accepted.status_code == 201
    assert all(
        accepted.json()[field] == valid[field] for field in ("display_name", "email", "phone")
    )
    for field in ("display_name", "email", "phone"):
        rejected = client.post(
            "/api/v1/customers", headers=headers, json={**valid, field: " " + valid[field]}
        )
        assert rejected.status_code == 422
