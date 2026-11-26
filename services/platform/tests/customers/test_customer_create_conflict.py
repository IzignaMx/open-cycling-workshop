"""REST identifier conflicts are permanent and never change existing customer data."""

import pytest
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.shared.ids import new_id
from sqlalchemy.exc import IntegrityError, OperationalError

from services.platform.tests.customers.test_create_location_validation import (
    client as client,
)
from services.platform.tests.customers.test_create_location_validation import (
    credentials,
    snapshot,
)


def body(identifier, **overrides):
    return {
        "customer_id": identifier,
        "location_id": "local",
        "display_name": "Synthetic original",
        "email": "synthetic@example.invalid",
        **overrides,
    }


def assert_conflict(response):
    assert response.status_code == 409, response.text
    assert "no-store" in response.headers["cache-control"]
    error = response.json()["error"]
    assert error["code"] == "customer_conflict"
    assert error["message"] == "customer identifier already exists"
    assert error["details"] == {}
    assert isinstance(error["request_id"], str)


@pytest.mark.parametrize("changed", [False, True])
def test_duplicate_identifier_preserves_original_and_feed_and_connection(client, changed):
    identifier = new_id()
    first = client.post("/api/v1/customers", json=body(identifier))
    assert first.status_code == 201
    before = snapshot(client)
    duplicate = body(identifier, display_name="Replacement") if changed else body(identifier)
    response = client.post("/api/v1/customers", json=duplicate)
    assert_conflict(response)
    assert snapshot(client) == before
    assert client.get(f"/api/v1/customers/{identifier}").json() == first.json()
    assert client.post("/api/v1/customers", json=body(new_id())).status_code == 201


@pytest.mark.parametrize("scope", ["other_location", "other_organization"])
def test_collision_does_not_disclose_existing_scope_or_private_fields(client, scope):
    identifier = new_id()
    headers = {}
    location = "second"
    if scope == "other_organization":
        with client.app.state.session_factory.begin() as session:
            session.add(
                UserRecord(
                    id="foreign-actor",
                    organization_id="other",
                    location_id="foreign",
                    username="foreign-synthetic",
                    display_name="Synthetic foreign actor",
                    password_hash="unused-token-fixture",
                    capabilities=["customers.write"],
                    is_active=True,
                    session_version=1,
                )
            )
        token = client.app.state.session_tokens.issue(
            Principal("foreign-actor", "other", "foreign", frozenset({"customers.write"}))
        )
        headers = {"Authorization": f"Bearer {token}"}
        location = "foreign"
    first = client.post(
        "/api/v1/customers", headers=headers, json=body(identifier, location_id=location)
    )
    assert first.status_code == 201
    client.headers.update(credentials(client, account_location="local", token_location="local"))
    before = snapshot(client)
    response = client.post("/api/v1/customers", json=body(identifier))
    assert_conflict(response)
    assert snapshot(client) == before
    for value in [
        identifier,
        "Synthetic original",
        "synthetic@example.invalid",
        "second",
        "foreign",
    ]:
        assert value not in response.text


@pytest.mark.parametrize("denial", ["authentication", "capability", "location"])
def test_authority_denial_precedes_existing_identifier(client, denial):
    identifier = new_id()
    assert client.post("/api/v1/customers", json=body(identifier)).status_code == 201
    before = snapshot(client)
    if denial == "authentication":
        client.headers.pop("Authorization")
    elif denial == "capability":
        client.headers.update(credentials(client, capabilities=frozenset({"customers.read"})))
    else:
        client.headers.update(
            credentials(client, account_location="second", token_location="second")
        )
    response = client.post("/api/v1/customers", json=body(identifier))
    assert response.status_code == (401 if denial == "authentication" else 403)
    assert snapshot(client) == before


@pytest.mark.parametrize("failure", [IntegrityError, OperationalError])
@pytest.mark.parametrize("stage", ["append_change", "commit_admitted"])
def test_later_database_failure_remains_503_and_rolls_back_new_customer(
    client, monkeypatch, failure, stage
):
    before = snapshot(client)

    def unavailable(*_args, **_kwargs):
        raise failure("private SQL", {"private": "parameter"}, RuntimeError("private failure"))

    monkeypatch.setattr(f"cycling_workshop.customers.router.{stage}", unavailable)
    response = client.post("/api/v1/customers", json=body(new_id()))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_command_failed"
    assert "private" not in response.text
    assert snapshot(client) == before


def test_unrelated_insert_unique_failure_is_not_reported_as_identifier_conflict(client):
    # Test-only constraint: prove the conflict target is id, not every unique index.
    # No application schema or production uniqueness policy is changed.
    with client.app.state.session_factory.begin() as session:
        session.connection().exec_driver_sql(
            "CREATE UNIQUE INDEX synthetic_customer_email_unique ON customers (email)"
        )
    assert client.post("/api/v1/customers", json=body(new_id())).status_code == 201
    before = snapshot(client)
    response = client.post("/api/v1/customers", json=body(new_id()))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_command_failed"
    assert "synthetic" not in response.text
    assert snapshot(client) == before
