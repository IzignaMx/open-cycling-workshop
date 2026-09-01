from datetime import UTC, datetime

from cycling_workshop.app import create_app
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.db.base import Base
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.settings import Settings
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

NOW = datetime(2026, 8, 31, tzinfo=UTC)


def _ensure_seed(engine) -> None:
    from sqlalchemy import inspect as sa_inspect

    if sa_inspect(engine).has_table("customers"):
        return
    Base.metadata.create_all(engine)
    with Session(engine) as session:
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
                capabilities=FULL_CAPABILITIES,
                is_active=True,
                session_version=1,
            )
        )
        session.add(
            CustomerRecord(
                id="customer-1",
                organization_id="org-1",
                location_id="loc-1",
                display_name="Ana Rivera",
                created_at=NOW,
                updated_at=NOW,
                version=1,
            )
        )
        session.commit()


FULL_CAPABILITIES = [
    "customers.read",
    "customers.write",
    "bicycles.read",
    "bicycles.write",
    "orders.read",
    "orders.write",
    "sync.pull",
    "sync.push",
]


def build_client(capabilities: list[str] | None = None, *, engine=None) -> TestClient:
    if engine is None:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    _ensure_seed(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        log_level="WARNING",
        auth_secret="test-secret-that-is-long-enough-for-tests",
    )
    app = create_app(settings=settings, session_factory=factory)
    token = app.state.session_tokens.issue(
        Principal(
            user_id="user-1",
            organization_id="org-1",
            location_id="loc-1",
            capabilities=frozenset(capabilities if capabilities is not None else FULL_CAPABILITIES),
        )
    )
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def _create_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "customer_id": "customer-1",
        "location_id": "loc-1",
        "brand": "  Trek   Marlin ",
        "model": "7",
    }
    payload.update(overrides)
    return payload


def test_bicycle_create_normalizes_and_returns_201() -> None:
    client = build_client()

    response = client.post("/api/v1/bicycles", json=_create_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["brand"] == "Trek Marlin"
    assert body["model"] == "7"
    assert body["customer_id"] == "customer-1"
    assert body["version"] == 1
    bicycle_id = body["bicycle_id"]
    assert len(bicycle_id) == 36


def test_bicycle_create_requires_authentication() -> None:
    client = build_client()
    client.headers.pop("Authorization")

    response = client.post("/api/v1/bicycles", json=_create_payload())

    assert response.status_code == 401


def test_bicycle_create_rejects_missing_write_capability() -> None:
    client = build_client(capabilities=[c for c in FULL_CAPABILITIES if c != "bicycles.write"])

    response = client.post("/api/v1/bicycles", json=_create_payload())

    assert response.status_code == 403


def test_bicycle_create_unknown_customer_is_404() -> None:
    client = build_client()

    response = client.post(
        "/api/v1/bicycles", json=_create_payload(customer_id="00000000-0000-7000-8000-000000000099")
    )

    assert response.status_code == 404


def test_bicycle_get_returns_created_and_404_for_unknown() -> None:
    client = build_client()
    created = client.post("/api/v1/bicycles", json=_create_payload()).json()

    found = client.get(f"/api/v1/bicycles/{created['bicycle_id']}")
    assert found.status_code == 200
    assert found.json()["bicycle_id"] == created["bicycle_id"]

    missing = client.get("/api/v1/bicycles/00000000-0000-7000-8000-0000000000ff")
    assert missing.status_code == 404


def test_customer_bicycles_lists_only_that_customer() -> None:
    client = build_client()
    first = client.post("/api/v1/bicycles", json=_create_payload(brand="Cube")).json()
    client.post("/api/v1/bicycles", json=_create_payload(brand="Scott"))

    listing = client.get("/api/v1/customers/customer-1/bicycles")

    assert listing.status_code == 200
    brands = [row["brand"] for row in listing.json()]
    assert brands == ["Cube", "Scott"]
    assert all(row["customer_id"] == "customer-1" for row in listing.json())
    assert first["brand"] == "Cube"
