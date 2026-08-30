import json

from cycling_workshop.app import create_app
from cycling_workshop.settings import Settings


def test_openapi_is_deterministic_and_contains_customer_contract() -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        log_level="WARNING",
        auth_secret="test-secret-that-is-long-enough-for-tests",
    )
    first = json.dumps(create_app(settings=settings).openapi(), sort_keys=True, separators=(",", ":"))
    second = json.dumps(create_app(settings=settings).openapi(), sort_keys=True, separators=(",", ":"))

    assert first == second
    assert '"/api/v1/customers"' in first
    assert '"/api/v1/customers/{customer_id}"' in first


def test_readiness_openapi_declares_ready_and_unavailable_contracts() -> None:
    settings = Settings(
        environment='test',
        database_url='sqlite+pysqlite:///:memory:',
        log_level='WARNING',
        auth_secret='test-secret-that-is-long-enough-for-tests',
    )
    schema = create_app(settings=settings).openapi()
    responses = schema['paths']['/health/ready']['get']['responses']

    assert responses['200']['content']['application/json']['schema']['$ref'].endswith('/HealthReadyResponse')
    assert responses['503']['content']['application/json']['schema']['$ref'].endswith('/HealthUnavailableResponse')
