"""Actual ASGI/parser/service integration, including downgrade attempts."""

import json
from dataclasses import replace

import pytest
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.models import ChangeRecord, MutationReceiptRecord
from cycling_workshop.sync.proof import MUTATION_BODY_LIMIT
from sqlalchemy import func, select
from test_sync_api import build_client


def _command():
    return {
        "mutation_id": new_id(),
        "entity_type": "customer",
        "entity_id": new_id(),
        "operation": "create",
        "organization_id": "org-1",
        "location_id": "loc-1",
        "base_version": None,
        "occurred_at": "2026-10-14T10:00:00.123456Z",
        "payload": {"display_name": "Synthetic customer", "ignored": 0.1},
    }


def _client():
    client = build_client()
    client.app.state.settings = replace(client.app.state.settings, cutover_enabled=True)
    context = client.get("/api/v1/auth/context")
    assert context.status_code == 200
    return client, {
        "X-OCWP-Write-Protocol": "1",
        "X-OCWP-Authorization-Epoch": context.json()["authorization_epoch"],
    }


def _history(client):
    with client.app.state.session_factory() as session:
        return {
            model.__tablename__: [
                dict(row) for row in session.execute(select(model.__table__)).mappings()
            ]
            for model in (CustomerRecord, ChangeRecord, OutboxRecord, MutationReceiptRecord)
        }


@pytest.mark.parametrize("protocol", [0, 1])
@pytest.mark.parametrize("coercion", ["unknown", "root", "duplicate", "timestamp", "decimal"])
def test_changed_raw_input_cannot_be_collapsed_into_bound_receipt(protocol, coercion):
    client, strict = _client()
    command = _command()
    created = client.post("/api/v1/sync/mutations", headers=strict, json={"mutations": [command]})
    assert created.status_code == 200 and created.json()["results"][0]["status"] == "applied"
    before = _history(client)
    raw = json.dumps({"mutations": [command]})
    if coercion == "unknown":
        raw = raw.replace('"base_version": null', '"unknown": true, "base_version": null')
    elif coercion == "root":
        raw = raw.replace('{"mutations":', '{"unknown": true, "mutations":', 1)
    elif coercion == "duplicate":
        raw = raw.replace('"base_version": null', '"base_version": 99, "base_version": null')
    elif coercion == "timestamp":
        raw = raw.replace(".123456Z", ".1234560Z")
    else:
        raw = raw.replace('"ignored": 0.1', '"ignored": 0.10000000000000001')
    headers = {**(strict if protocol else {}), "Content-Type": "application/json"}
    response = client.post("/api/v1/sync/mutations", headers=headers, content=raw)
    if protocol:
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_canonical_command"
    else:
        assert response.status_code == 200, response.text
        assert response.json()["results"][0]["error_code"] == "receipt_integrity_conflict"
    assert _history(client) == before


def test_bound_update_replay_rejects_string_base_version_even_under_legacy_protocol():
    client, strict = _client()
    command = _command()
    client.post("/api/v1/sync/mutations", headers=strict, json={"mutations": [command]})
    updated = {
        **command,
        "mutation_id": new_id(),
        "operation": "update",
        "base_version": 1,
        "payload": {"display_name": "Changed"},
    }
    created = client.post("/api/v1/sync/mutations", headers=strict, json={"mutations": [updated]})
    assert created.json()["results"][0]["status"] == "applied"
    before = _history(client)
    raw = json.dumps({"mutations": [updated]}).replace('"base_version": 1', '"base_version": "1"')
    response = client.post(
        "/api/v1/sync/mutations", headers={"Content-Type": "application/json"}, content=raw
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["error_code"] == "receipt_integrity_conflict"
    assert _history(client) == before


def test_legacy_request_preserves_duplicate_key_behavior_for_unbound_receipt():
    client, _ = _client()
    command = _command()
    first = client.post("/api/v1/sync/mutations", json={"mutations": [command]})
    before = _history(client)
    raw = json.dumps({"mutations": [command]}).replace(
        '"base_version": null', '"base_version": 5, "base_version": null'
    )
    response = client.post(
        "/api/v1/sync/mutations", headers={"Content-Type": "application/json"}, content=raw
    )
    assert response.status_code == 200 and response.json() == first.json()
    assert _history(client) == before


def test_actual_http_mixed_command_conflict_preserves_independent_savepoints():
    client, strict = _client()
    original = _command()
    first = client.post("/api/v1/sync/mutations", headers=strict, json={"mutations": [original]})
    assert first.json()["results"][0]["status"] == "applied"
    changed = {**original, "payload": {"display_name": "Do not apply"}}
    response = client.post(
        "/api/v1/sync/mutations",
        headers=strict,
        json={"mutations": [_command(), changed, _command()]},
    )
    assert response.status_code == 200
    assert [item["status"] for item in response.json()["results"]] == [
        "applied",
        "conflict",
        "applied",
    ]
    assert response.json()["results"][1]["error_code"] == "receipt_proof_conflict"
    assert all(len(rows) == 3 for rows in _history(client).values())


def test_strict_invalid_batch_and_stream_limit_have_zero_effects():
    client, strict = _client()
    invalid = {**_command(), "unknown": True}
    response = client.post(
        "/api/v1/sync/mutations", headers=strict, json={"mutations": [_command(), invalid]}
    )
    assert response.status_code == 422
    for protocol in ("0", "1"):
        headers = {**strict, "X-OCWP-Write-Protocol": protocol, "Content-Type": "application/json"}
        response = client.post(
            "/api/v1/sync/mutations",
            headers=headers,
            content=iter([b" " * MUTATION_BODY_LIMIT, b" "]),
        )
        assert response.status_code == 413
    assert all(rows == [] for rows in _history(client).values())


def test_authorized_second_actor_cannot_replay_bound_receipt_under_protocol_zero():
    client, strict = _client()
    command = _command()
    first = client.post("/api/v1/sync/mutations", headers=strict, json={"mutations": [command]})
    assert first.json()["results"][0]["status"] == "applied"
    with client.app.state.session_factory.begin() as session:
        actor = session.get(UserRecord, "user-1")
        session.add(
            UserRecord(
                id="second-actor",
                organization_id="org-1",
                location_id="loc-1",
                username="second",
                display_name="Synthetic second actor",
                password_hash="unused",
                capabilities=actor.capabilities,
                is_active=True,
                session_version=1,
            )
        )
        principal = Principal("second-actor", "org-1", "loc-1", frozenset(actor.capabilities))
    token = client.app.state.session_tokens.issue(principal)
    before = _history(client)
    response = client.post(
        "/api/v1/sync/mutations",
        headers={"Authorization": f"Bearer {token}"},
        json={"mutations": [command]},
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["error_code"] == "receipt_proof_conflict"
    assert _history(client) == before
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(MutationReceiptRecord)) == 1


def test_actual_http_equivalent_offset_number_spelling_and_key_order_replay_exactly():
    client, strict = _client()
    command = _command()
    first = client.post("/api/v1/sync/mutations", headers=strict, json={"mutations": [command]})
    assert first.json()["results"][0]["status"] == "applied"
    before = _history(client)
    command["occurred_at"] = "2026-10-14T12:30:00.123456+02:30"
    command = dict(reversed(list(command.items())))
    raw = json.dumps({"mutations": [command]}).replace('"ignored": 0.1', '"ignored": 1.000e-1')
    for headers in (strict, {}):
        response = client.post(
            "/api/v1/sync/mutations",
            headers={**headers, "Content-Type": "application/json"},
            content=raw,
        )
        assert response.status_code == 200 and response.json() == first.json()
    assert _history(client) == before
