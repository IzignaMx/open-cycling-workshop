from pathlib import Path


def test_development_compose_contains_isolated_database_api_and_worker() -> None:
    compose = Path('infra/compose/docker-compose.dev.yml').read_text()

    assert 'postgres:' in compose
    assert 'api:' in compose
    assert 'worker:' in compose
    assert '5432:5432' not in compose
    assert 'healthcheck:' in compose
    assert 'OCWP_AUTH_SECRET_FILE' in compose
    assert 'ocwp_api' not in compose  # service names stay generic and override-friendly
