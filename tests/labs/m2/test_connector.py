"""Actual local ASGI/authority integration; malformed cases are protocol-only."""

import importlib

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from tests.labs.m2.application import PATH, create_lab_app
from tests.labs.m2.authority import LabAuthority


@pytest.fixture
def fixture():
    authority = LabAuthority()
    credential = authority.issue()
    with authority.read(credential.authorization()) as (scope, _session):
        pass
    with TestClient(create_lab_app(authority)) as client:
        yield authority, credential, scope, client
    authority.close()


def connector_type():
    return importlib.import_module("tests.labs.m2.connector").LabConnector


def test_actual_fetch_closed_projection_and_disposal(fixture):
    _authority, credential, scope, client = fixture
    connector = connector_type()(client, credential, scope)
    rows = connector.fetch()
    assert len(rows) == 3
    assert all(set(row) == {"product_id", "sku", "name", "unit", "version"} for row in rows)
    assert all(row["sku"].startswith("LAB-A-1-") for row in rows)
    assert connector.row_count == 3
    assert connector.binding == scope
    plaintext_leaked = credential._secret in repr(connector)
    assert not plaintext_leaked
    connector.close()
    assert connector.closed and connector.row_count == 0
    assert connector.disposal_verified and not connector.cleanup_failed
    connector.close()


def test_revocation_stops_without_stale_projection(fixture):
    authority, credential, scope, client = fixture
    connector = connector_type()(client, credential, scope)
    authority.revoke(credential.credential_id)
    with pytest.raises(Exception, match="Laboratory connector stopped"):
        connector.fetch()
    assert connector.closed and connector.row_count == 0


def test_one_shot_has_no_retry_or_refresh(fixture):
    _authority, credential, scope, client = fixture
    connector = connector_type()(client, credential, scope)
    connector.fetch()
    with pytest.raises(Exception, match="Laboratory connector stopped"):
        connector.fetch()
    assert connector.closed and connector.row_count == 0


def test_actual_other_location_is_not_primary(fixture):
    authority, _credential, _scope, client = fixture
    credential = authority.issue("other_location")
    with authority.read(credential.authorization()) as (scope, _session):
        pass
    connector = connector_type()(client, credential, scope)
    try:
        assert all(row["sku"].startswith("LAB-A-2-") for row in connector.fetch())
    finally:
        connector.close()


@pytest.mark.parametrize(
    "payload",
    [
        {"items": [], "next_offset": 0},
        {"items": [], "next_offset": 201},
        {"items": [], "next_offset": True},
        {"items": [], "next_offset": None, "secret": "not-a-secret"},
        {"items": [{"product_id": "x"}], "next_offset": None},
    ],
)
def test_scripted_malformed_protocol_is_not_authentication_evidence(fixture, payload):
    _authority, credential, scope, _client = fixture
    app = FastAPI()
    calls = []

    @app.get(PATH)
    def malformed():
        calls.append(1)
        return JSONResponse(payload)

    with TestClient(app) as client:
        connector = connector_type()(client, credential, scope)
        with pytest.raises(Exception, match="Laboratory connector stopped"):
            connector.fetch()
        assert connector.closed and connector.row_count == 0
        assert len(calls) == 1


def test_rejects_network_client_without_request(fixture):
    _authority, credential, scope, _client = fixture
    with pytest.raises(Exception, match="Laboratory connector stopped"):
        connector_type()(object(), credential, scope)


def test_scripted_four_page_cap_purges_partial_store(fixture):
    _authority, credential, scope, _client = fixture
    app = FastAPI()
    calls = []

    @app.get(PATH)
    def page(offset: int = 0):
        calls.append(offset)
        return {
            "items": [
                {
                    "product_id": str(offset + i),
                    "sku": "LAB",
                    "name": "Synthetic",
                    "unit": "pieza",
                    "version": 1,
                }
                for i in range(50)
            ],
            "next_offset": offset + 50,
        }

    with TestClient(app) as client:
        connector = connector_type()(client, credential, scope)
        with pytest.raises(Exception, match="Laboratory connector stopped"):
            connector.fetch()
        assert calls == [0, 50, 100, 150]
        assert connector.closed and connector.row_count == 0


def test_scripted_oversized_response_stops(fixture):
    _authority, credential, scope, _client = fixture
    app = FastAPI()

    @app.get(PATH)
    def oversized():
        return {"items": [], "next_offset": None, "padding": "x" * 65536}

    with TestClient(app) as client:
        connector = connector_type()(client, credential, scope)
        with pytest.raises(Exception, match="Laboratory connector stopped"):
            connector.fetch()
        assert connector.closed and connector.row_count == 0


def test_scripted_reentrant_fetch_refuses_second_request_and_stops_owner(fixture):
    _authority, credential, scope, _client = fixture
    app = FastAPI()
    calls = []

    @app.get(PATH)
    def reentrant():
        calls.append(1)
        with pytest.raises(Exception, match="Laboratory connector stopped"):
            connector.fetch()
        return {"items": [], "next_offset": None}

    with TestClient(app) as client:
        connector = connector_type()(client, credential, scope)
        with pytest.raises(Exception, match="Laboratory connector stopped"):
            connector.fetch()
        assert calls == [1]
        assert connector.closed and connector.row_count == 0


def test_projection_contains_no_credential(fixture):
    _authority, credential, scope, client = fixture
    connector = connector_type()(client, credential, scope)
    try:
        connector.fetch()
        dump = "\n".join(connector._store.iterdump())
        plaintext_leaked = credential._secret in dump or credential._secret in repr(connector)
        assert not plaintext_leaked
    finally:
        connector.close()


@pytest.mark.parametrize("stage", ["delete", "close"])
def test_cleanup_failure_is_sanitized_not_verified_disposal(fixture, stage):
    authority, credential, scope, client = fixture
    connector = connector_type()(client, credential, scope)
    real_store = connector._store
    close_attempts = []

    class FailingCleanup:
        def execute(self, sql):
            if stage == "delete":
                raise RuntimeError("cleanup-private-canary")
            return real_store.execute(sql)

        def commit(self):
            real_store.commit()

        def close(self):
            close_attempts.append(1)
            real_store.close()
            if stage == "close":
                raise RuntimeError("cleanup-private-canary")

    connector._store = FailingCleanup()
    authority.revoke(credential.credential_id)
    with pytest.raises(Exception) as failure:
        connector.fetch()
    assert str(failure.value) == "Laboratory connector stopped"
    assert close_attempts == [1]
    assert connector.cleanup_failed and not connector.disposal_verified
    with pytest.raises(Exception, match="Laboratory connector stopped"):
        _ = connector.row_count
    with pytest.raises(Exception, match="Laboratory connector stopped"):
        connector.close()
    assert not connector.disposal_verified


@pytest.mark.parametrize(
    "field,limit", [("product_id", 36), ("sku", 80), ("name", 200), ("unit", 30)]
)
def test_scripted_field_exceeding_core_bound_is_refused(fixture, field, limit):
    _authority, credential, scope, _client = fixture
    app = FastAPI()
    item = {
        "product_id": "synthetic-id",
        "sku": "LAB",
        "name": "Synthetic",
        "unit": "pieza",
        "version": 1,
    }
    item[field] = "x" * (limit + 1)

    @app.get(PATH)
    def oversized_field():
        return {"items": [item], "next_offset": None}

    with TestClient(app) as client:
        connector = connector_type()(client, credential, scope)
        try:
            with pytest.raises(Exception, match="Laboratory connector stopped"):
                connector.fetch()
            assert connector.closed and connector.row_count == 0
        finally:
            connector.close()
