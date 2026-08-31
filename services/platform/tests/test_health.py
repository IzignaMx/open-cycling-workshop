from cycling_workshop.app import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_liveness_endpoint_is_available() -> None:
    client = TestClient(create_app())
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_endpoint_is_available_when_database_is_reachable() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    factory = sessionmaker(bind=engine)
    client = TestClient(create_app(session_factory=factory))
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    engine.dispose()


def test_request_id_is_generated_and_returned() -> None:
    client = TestClient(create_app())
    response = client.get("/health/live")
    request_id = response.headers["X-Request-ID"]
    assert request_id
    assert len(request_id) >= 16


def test_request_id_is_preserved_when_client_supplies_one() -> None:
    client = TestClient(create_app())
    response = client.get("/health/live", headers={"X-Request-ID": "req-test-123"})
    assert response.headers["X-Request-ID"] == "req-test-123"


def test_readiness_is_unavailable_without_a_database_session_factory() -> None:
    client = TestClient(create_app())
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
