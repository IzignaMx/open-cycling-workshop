"""Executable cutover admission and restore-resistant session contracts."""

from dataclasses import replace
from uuid import UUID, uuid4

import jwt
import pytest
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.shared.ids import new_id
from cycling_workshop.tenancy.models import OrganizationRecord
from sqlalchemy import func, select
from test_auth_api import build_client

SECRET = "test-secret-that-is-long-enough-for-tests"


def login(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "organization_id": "org-1",
            "username": "admin",
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def configure(client, floor=0, enabled=True):
    client.app.state.settings = replace(client.app.state.settings, cutover_enabled=enabled)
    with client.app.state.session_factory.begin() as session:
        org = session.get(OrganizationRecord, "org-1")
        org.minimum_write_protocol = floor
        return org.dataset_incarnation


def test_login_binds_signed_dataset_incarnation_and_context_agrees():
    client = build_client()
    token = login(client)
    claim = jwt.decode(token, SECRET, algorithms=["HS256"], issuer="ocwp")
    assert str(UUID(claim["di"])) == claim["di"]
    response = client.get("/api/v1/auth/context", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["dataset_incarnation"] == claim["di"]
    assert response.json()["policy_revision"] == "ocwp-access-baseline-2"
    assert response.json()["snapshot_protocol"] is None


@pytest.mark.parametrize("floor", [0, 1])
@pytest.mark.parametrize("kind", ["missing", "current", "mismatch", "malformed"])
def test_token_incarnation_matrix_all_authenticated_reads(floor, kind):
    client = build_client()
    configure(client, floor)
    with client.app.state.session_factory.begin() as session:
        actor = session.get(UserRecord, "user-1")
        actor.capabilities = [*actor.capabilities, "users.read", "inventory.read"]
    token = login(client)
    claims = jwt.decode(token, SECRET, algorithms=["HS256"], issuer="ocwp")
    if kind == "missing":
        claims.pop("di")
    elif kind == "mismatch":
        claims["di"] = str(uuid4())
    elif kind == "malformed":
        claims["di"] = "not-a-uuid"
    token = jwt.encode(claims, SECRET, algorithm="HS256")
    expected = 200 if kind == "current" or (kind == "missing" and floor == 0) else 401
    for path in [
        "/api/v1/auth/me",
        "/api/v1/auth/context",
        "/api/v1/sync/changes",
        "/api/v1/admin/users",
        "/api/v1/inventory/products?location_id=loc-1",
    ]:
        assert (
            client.get(path, headers={"Authorization": f"Bearer {token}"}).status_code == expected
        )
    baseline = client.post(
        "/api/v1/sync/baselines/start",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "protocol": 1,
            "selected_location_id": "loc-1",
            "authorization_epoch": "stale",
            "request_id": new_id(),
        },
    )
    assert baseline.status_code == (409 if expected == 200 else 401)


@pytest.mark.parametrize("value", [None, "0", "1", "2", "01", " 1", "1,1"])
@pytest.mark.parametrize("floor", [0, 1])
def test_direct_writer_floor_exact_header_and_zero_effects(floor, value):
    client = build_client()
    configure(client, floor)
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}
    if value is not None:
        headers["X-OCWP-Write-Protocol"] = value
    response = client.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "customer_id": new_id(),
            "display_name": "Disposable fixture",
            "location_id": "loc-1",
        },
    )
    permitted = value in (None, "0", "1") and (floor == 0 or value == "1")
    assert response.status_code == (201 if permitted else 409), response.text
    if not permitted:
        assert response.json()["error"]["code"] == "client_upgrade_required"
        with client.app.state.session_factory() as session:
            assert session.scalar(select(func.count()).select_from(CustomerRecord)) == 0


def test_enabled_floor1_advertisement_is_real_and_support_changes_epoch():
    client = build_client()
    configure(client, 1)
    headers = {"Authorization": f"Bearer {login(client)}"}
    enabled = client.get("/api/v1/auth/context", headers=headers).json()
    assert enabled["snapshot_protocol"] == "baseline-v1"
    configure(client, 1, enabled=False)
    disabled = client.get("/api/v1/auth/context", headers=headers).json()
    assert disabled["snapshot_protocol"] is None
    assert disabled["authorization_epoch"] != enabled["authorization_epoch"]


def test_rotation_does_not_collide_with_restored_session_counter():
    client = build_client()
    configure(client, 1)
    with client.app.state.session_factory.begin() as session:
        session.get(UserRecord, "user-1").session_version = 2
    old_token = login(client)
    # Disposable logical restore of v1 followed by explicit incarnation rotation.
    with client.app.state.session_factory.begin() as session:
        session.get(UserRecord, "user-1").session_version = 1
        session.get(OrganizationRecord, "org-1").dataset_incarnation = str(uuid4())
    # Even a later v2 counter must never re-admit the original v2 token.
    with client.app.state.session_factory.begin() as session:
        session.get(UserRecord, "user-1").session_version = 2
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {login(client)}"}
        ).status_code
        == 200
    )


def command_item():
    return {
        "mutation_id": new_id(),
        "entity_type": "customer",
        "entity_id": new_id(),
        "operation": "create",
        "organization_id": "org-1",
        "location_id": "loc-1",
        "base_version": None,
        "occurred_at": "2026-10-14T00:00:00.123456Z",
        "payload": {"display_name": "Disposable strict command"},
    }


def test_strict_sync_epoch_receipt_and_legacy_overlap_matrix():
    client = build_client()
    configure(client, 0)
    headers = {"Authorization": f"Bearer {login(client)}", "X-OCWP-Write-Protocol": "1"}
    epoch = client.get("/api/v1/auth/context", headers=headers).json()["authorization_epoch"]
    body = {"mutations": [command_item()]}
    for epoch_value in [None, "stale"]:
        sent = dict(headers)
        if epoch_value is not None:
            sent["X-OCWP-Authorization-Epoch"] = epoch_value
        response = client.post("/api/v1/sync/mutations", headers=sent, json=body)
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "authorization_context_changed"
    headers["X-OCWP-Authorization-Epoch"] = epoch
    first = client.post("/api/v1/sync/mutations", headers=headers, json=body)
    assert first.status_code == 200, first.text
    assert first.json()["results"][0]["status"] == "applied"
    legacy = {"Authorization": headers["Authorization"]}
    assert client.post("/api/v1/sync/mutations", headers=legacy, json=body).json() == first.json()
    body["mutations"][0]["payload"]["display_name"] = "Altered"
    changed = client.post("/api/v1/sync/mutations", headers=legacy, json=body)
    assert changed.json()["results"][0]["error_code"] == "receipt_proof_conflict"
    configure(client, 1)
    refused = client.post("/api/v1/sync/mutations", headers=legacy, json=body)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "client_upgrade_required"


def test_null_disabled_support_refuses_strict_writes_and_duplicate_headers():
    client = build_client()
    configure(client, 0, enabled=False)
    headers = {"Authorization": f"Bearer {login(client)}", "X-OCWP-Write-Protocol": "1"}
    body = {"display_name": "Fixture", "location_id": "loc-1"}
    assert client.post("/api/v1/customers", headers=headers, json=body).status_code == 409
    configure(client, 0, enabled=True)
    for pair in [("0", "0"), ("1", "1"), ("0", "1")]:
        repeated = [("Authorization", headers["Authorization"])] + [
            ("X-OCWP-Write-Protocol", value) for value in pair
        ]
        assert client.post("/api/v1/customers", headers=repeated, json=body).status_code == 409


def test_strict_sync_mixed_location_and_duplicate_epoch_are_whole_request_refusals():
    client = build_client()
    configure(client, 1)
    headers = {"Authorization": f"Bearer {login(client)}", "X-OCWP-Write-Protocol": "1"}
    epoch = client.get("/api/v1/auth/context", headers=headers).json()["authorization_epoch"]
    items = [command_item(), command_item()]
    items[1]["location_id"] = "other"
    headers["X-OCWP-Authorization-Epoch"] = epoch
    assert (
        client.post(
            "/api/v1/sync/mutations", headers=headers, json={"mutations": items}
        ).status_code
        == 409
    )
    repeated = [*headers.items(), ("X-OCWP-Authorization-Epoch", epoch)]
    assert (
        client.post(
            "/api/v1/sync/mutations", headers=repeated, json={"mutations": [items[0]]}
        ).status_code
        == 409
    )
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(CustomerRecord)) == 0


def test_genuine_context_start_activation_agree_and_disabled_change_invalidates_checkpoint():
    client = build_client()
    configure(client, 1)
    client.headers.update({"Authorization": f"Bearer {login(client)}"})
    context = client.get("/api/v1/auth/context").json()
    start = client.post(
        "/api/v1/sync/baselines/start",
        json={
            "protocol": 1,
            "selected_location_id": "loc-1",
            "authorization_epoch": context["authorization_epoch"],
            "request_id": new_id(),
        },
    )
    assert start.status_code == 200, start.text
    page = client.post(
        "/api/v1/sync/baselines/page",
        json={
            "protocol": 1,
            "continuation": start.json()["continuation"],
        },
    )
    assert page.status_code == 200, page.text
    assert page.json()["phase"] == "scan_complete"
    final = client.post(
        "/api/v1/sync/baselines/finalize",
        json={
            "protocol": 1,
            "continuation": page.json()["continuation"],
        },
    )
    assert final.status_code == 200, final.text
    delta = client.post(
        "/api/v1/sync/deltas/page",
        json={
            "protocol": 1,
            "continuation": final.json()["continuation"],
        },
    )
    assert delta.status_code == 200, delta.text
    assert delta.json()["phase"] == "complete"
    activation_body = {"protocol": 1, "checkpoint": delta.json()["continuation"]}
    activated = client.post("/api/v1/sync/baselines/validate-activation", json=activation_body)
    assert activated.status_code == 200, activated.text
    for key in (
        "dataset_incarnation",
        "policy_revision",
        "authorization_epoch",
        "snapshot_protocol",
    ):
        assert start.json()["context"][key] == activated.json()["context"][key] == context[key]
    assert context["snapshot_protocol"] == "baseline-v1"
    configure(client, 1, enabled=False)
    assert (
        client.post("/api/v1/sync/baselines/validate-activation", json=activation_body).status_code
        == 409
    )


def test_write_expiry_immediately_before_commit_rolls_back_all_effects(monkeypatch):
    from datetime import UTC, datetime, timedelta

    import cycling_workshop.customers.router as customers_router
    from cycling_workshop.identity.security import SessionTokenService

    client = build_client()
    configure(client, 1)
    now = [datetime.now(UTC)]
    client.app.state.session_tokens = SessionTokenService(
        secret=SECRET, clock=lambda: now[0], ttl=timedelta(minutes=1)
    )
    headers = {"Authorization": f"Bearer {login(client)}", "X-OCWP-Write-Protocol": "1"}
    original = customers_router.append_change

    def delayed(*args, **kwargs):
        original(*args, **kwargs)
        now[0] += timedelta(minutes=2)

    monkeypatch.setattr(customers_router, "append_change", delayed)
    response = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"display_name": "Fixture", "location_id": "loc-1"},
    )
    assert response.status_code == 401
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(CustomerRecord)) == 0


def test_receipt_collision_integrity_error_is_classified_after_item_savepoint(monkeypatch):
    from cycling_workshop.sync.service import SyncService
    from sqlalchemy.exc import IntegrityError

    client = build_client()
    configure(client, 0)
    headers = {"Authorization": f"Bearer {login(client)}"}
    existing = command_item()
    assert (
        client.post(
            "/api/v1/sync/mutations", headers=headers, json={"mutations": [existing]}
        ).status_code
        == 200
    )
    original = SyncService.apply

    def simulate_unique_wait(self, mutation, *, context=None):
        if mutation.mutation_id == existing["mutation_id"]:
            raise IntegrityError("synthetic receipt collision", {}, Exception("synthetic"))
        return original(self, mutation, context=context)

    monkeypatch.setattr(SyncService, "apply", simulate_unique_wait)
    response = client.post(
        "/api/v1/sync/mutations", headers=headers, json={"mutations": [command_item(), existing]}
    )
    assert response.status_code == 200, response.text
    assert [result["status"] for result in response.json()["results"]] == ["applied", "conflict"]
    assert response.json()["results"][1]["error_code"] == "sync_conflict"
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(CustomerRecord)) == 2
