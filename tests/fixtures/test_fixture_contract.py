import json
from pathlib import Path


FIXTURES = ('minimal', 'demo-workshop', 'load')


def test_v01_fixtures_are_versioned_and_tenant_scoped() -> None:
    for fixture_name in FIXTURES:
        path = Path('fixtures') / fixture_name / 'fixture.json'
        payload = json.loads(path.read_text())
        assert payload['schema_version'] == 1
        assert payload['organization']['id']
        assert payload['location']['organization_id'] == payload['organization']['id']
        assert payload['location']['id']
        for customer in payload['customers']:
            assert customer['organization_id'] == payload['organization']['id']
            assert customer['location_id'] == payload['location']['id']


def test_load_fixture_is_large_enough_to_exercise_pagination() -> None:
    payload = json.loads(Path('fixtures/load/fixture.json').read_text())
    assert len(payload['customers']) >= 100
