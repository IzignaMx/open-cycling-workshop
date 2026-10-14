"""Bounded baseline lifecycle; SQLite proves behavior, not row-lock serialization."""

from datetime import UTC, datetime, timedelta

import pytest
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.security import SessionTokenService
from cycling_workshop.shared.ids import new_id
from test_sync_api import build_client

NOW = datetime(2026, 10, 14, 13, tzinfo=UTC)
ROOT = "/api/v1/sync"


def baseline_client():
    client = build_client()
    now = [NOW]
    client.app.state.session_tokens = SessionTokenService(
        secret="test-secret-that-is-long-enough-for-tests", clock=lambda: now[0]
    )
    grants = frozenset({"sync.pull", "customers.read"})
    with client.app.state.session_factory.begin() as session:
        session.get(UserRecord, "user-1").capabilities = sorted(grants)
    token = client.app.state.session_tokens.issue(Principal("user-1", "org-1", "loc-1", grants))
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client, now


def start_body(client):
    context = client.get("/api/v1/auth/context").json()
    return dict(
        protocol=1,
        selected_location_id="loc-1",
        authorization_epoch=context["authorization_epoch"],
        request_id=new_id(),
    )


def post(client, path, token):
    return client.post(f"{ROOT}/{path}", json={"protocol": 1, "continuation": token})


def complete(client, body=None):
    body = body or start_body(client)
    start = client.post(f"{ROOT}/baselines/start", json=body)
    assert start.status_code == 200, start.text
    page = post(client, "baselines/page", start.json()["continuation"])
    records = []
    while True:
        assert page.status_code == 200, page.text
        records += page.json()["records"]
        if page.json()["phase"] == "scan_complete":
            break
        page = post(client, "baselines/page", page.json()["continuation"])
    final = post(client, "baselines/finalize", page.json()["continuation"])
    assert final.status_code == 200, final.text
    delta = post(client, "deltas/page", final.json()["continuation"])
    while True:
        assert delta.status_code == 200, delta.text
        records += delta.json()["records"]
        if delta.json()["phase"] == "complete":
            break
        delta = post(client, "deltas/page", delta.json()["continuation"])
    return start, delta, records


def test_baseline_includes_historical_rows_without_feed_and_exact_start_replay():
    client, _ = baseline_client()
    with client.app.state.session_factory.begin() as session:
        session.add(
            CustomerRecord(
                id="historic",
                organization_id="org-1",
                location_id="loc-1",
                display_name="Historical",
                created_at=NOW,
                updated_at=NOW,
                version=1,
            )
        )
    body = start_body(client)
    start, delta, records = complete(client, body)
    assert [r["entity_id"] for r in records] == ["historic"]
    assert client.post(f"{ROOT}/baselines/start", json=body).content == start.content
    checkpoint = delta.json()["continuation"]
    activation = {"protocol": 1, "checkpoint": checkpoint}
    for _ in range(2):
        response = client.post(f"{ROOT}/baselines/validate-activation", json=activation)
        assert response.status_code == 200, response.text
        assert response.json()["checkpoint"] == checkpoint
        assert response.headers["cache-control"] == "no-store"


def test_two_slots_do_not_slide_expiry_and_third_has_safe_retry():
    client, now = baseline_client()
    first = client.post(f"{ROOT}/baselines/start", json=start_body(client))
    second = client.post(f"{ROOT}/baselines/start", json=start_body(client))
    assert first.status_code == second.status_code == 200
    body = start_body(client)
    blocked = client.post(f"{ROOT}/baselines/start", json=body)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "baseline_in_progress"
    assert int(blocked.headers["retry-after"]) > 0
    assert first.json()["continuation"] not in blocked.text
    now[0] += timedelta(minutes=31)
    assert client.post(f"{ROOT}/baselines/start", json=body).status_code == 200


def test_checkpoint_family_is_bounded_and_deadline_never_slides():
    from cycling_workshop.sync.baseline_models import BaselineFamily
    from sqlalchemy import func, select

    client, now = baseline_client()
    _, delta, _ = complete(client)
    original_checkpoint = delta.json()["continuation"]
    with client.app.state.session_factory() as session:
        deadline = session.scalar(select(BaselineFamily.family_expires_at))
    now[0] += timedelta(minutes=31)
    # Completed proof outlives the scan deadline.
    activation = {"protocol": 1, "checkpoint": original_checkpoint}
    assert client.post(f"{ROOT}/baselines/validate-activation", json=activation).status_code == 200
    token = original_checkpoint
    for _ in range(1000):
        response = post(client, "deltas/page", token)
        assert response.status_code == 200, response.text
        assert response.json()["records"] == []
        assert response.json()["completion"]["baseline_id"] is None
        token = response.json()["continuation"]
    assert client.post(f"{ROOT}/baselines/validate-activation", json=activation).status_code == 409
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(BaselineFamily)) == 1
        assert session.scalar(select(BaselineFamily.family_expires_at)) == deadline
    now[0] = NOW + timedelta(hours=8)
    # Renewed bearer cannot renew the family's immutable deadline.
    grants = frozenset({"sync.pull", "customers.read"})
    token_auth = client.app.state.session_tokens.issue(
        Principal("user-1", "org-1", "loc-1", grants)
    )
    client.headers["Authorization"] = f"Bearer {token_auth}"
    assert post(client, "deltas/page", token).status_code == 410


def test_global_user_family_quota_counts_completed_families_and_epochs():
    client, _ = baseline_client()
    for _ in range(8):
        complete(client)
    response = client.post(f"{ROOT}/baselines/start", json=start_body(client))
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "baseline_capacity"
    assert int(response.headers["retry-after"]) > 0


def test_cached_progress_reauthorizes_and_does_not_disclose_after_revocation():
    client, _ = baseline_client()
    start = client.post(f"{ROOT}/baselines/start", json=start_body(client)).json()
    predecessor = start["continuation"]
    first = post(client, "baselines/page", predecessor)
    assert first.status_code == 200
    assert post(client, "baselines/page", predecessor).content == first.content
    with client.app.state.session_factory.begin() as session:
        session.get(UserRecord, "user-1").session_version += 1
    denied = post(client, "baselines/page", predecessor)
    assert denied.status_code == 401
    assert predecessor not in denied.text
    assert denied.headers["cache-control"] == "no-store"


def test_wrong_endpoint_stale_tokens_and_lost_completion_response():
    client, _ = baseline_client()
    start = client.post(f"{ROOT}/baselines/start", json=start_body(client)).json()
    assert post(client, "baselines/finalize", start["continuation"]).status_code == 422
    page = post(client, "baselines/page", start["continuation"]).json()
    final = post(client, "baselines/finalize", page["continuation"])
    assert post(client, "baselines/finalize", page["continuation"]).content == final.content
    assert post(client, "baselines/page", start["continuation"]).status_code == 409
    delta = post(client, "deltas/page", final.json()["continuation"])
    assert post(client, "deltas/page", final.json()["continuation"]).content == delta.content
    next_run = post(client, "deltas/page", delta.json()["continuation"])
    assert next_run.status_code == 200
    assert post(client, "deltas/page", final.json()["continuation"]).status_code == 409


def test_restart_uses_durable_state_not_process_cache():
    from cycling_workshop.app import create_app
    from fastapi.testclient import TestClient

    client, _ = baseline_client()
    body = start_body(client)
    start = client.post(f"{ROOT}/baselines/start", json=body)
    page = post(client, "baselines/page", start.json()["continuation"])
    second_app = create_app(
        client.app.state.settings, session_factory=client.app.state.session_factory
    )
    second_app.state.session_tokens = client.app.state.session_tokens
    second = TestClient(second_app)
    second.headers.update(client.headers)
    assert second.post(f"{ROOT}/baselines/start", json=body).content == start.content
    assert post(second, "baselines/page", start.json()["continuation"]).content == page.content
    assert post(second, "baselines/finalize", page.json()["continuation"]).status_code == 200


def test_lexical_insert_and_scan_update_races_equal_frozen_h():
    from cycling_workshop.sync.models import ChangeRecord

    client, _ = baseline_client()
    with client.app.state.session_factory.begin() as session:
        for index in range(102):
            session.add(
                CustomerRecord(
                    id=f"m{index:03}",
                    organization_id="org-1",
                    location_id="loc-1",
                    display_name="Before",
                    created_at=NOW,
                    updated_at=NOW,
                    version=1,
                )
            )
    start = client.post(f"{ROOT}/baselines/start", json=start_body(client)).json()
    page = post(client, "baselines/page", start["continuation"]).json()
    assert len(page["records"]) == 100 and page["phase"] == "scan"

    def change(identifier, version, name):
        with client.app.state.session_factory.begin() as session:
            row = session.get(CustomerRecord, identifier)
            if row is None:
                row = CustomerRecord(
                    id=identifier,
                    organization_id="org-1",
                    location_id="loc-1",
                    display_name=name,
                    created_at=NOW,
                    updated_at=NOW,
                    version=version,
                )
                session.add(row)
            else:
                row.version, row.display_name = version, name
            payload = {
                "customer_id": identifier,
                "organization_id": "org-1",
                "location_id": "loc-1",
                "display_name": name,
                "email": None,
                "phone": None,
                "version": version,
                "created_at": NOW.isoformat(),
                "updated_at": NOW.isoformat(),
            }
            session.add(
                ChangeRecord(
                    organization_id="org-1",
                    location_id="loc-1",
                    entity_type="customer",
                    entity_id=identifier,
                    entity_version=version,
                    operation="update",
                    occurred_at=NOW,
                    payload=payload,
                )
            )

    change("aaa", 1, "Below scanned cursor")
    change("zzz", 1, "Above captured bound")
    change("m000", 2, "At H")
    second = post(client, "baselines/page", page["continuation"]).json()
    assert second["phase"] == "scan_complete"
    final = post(client, "baselines/finalize", second["continuation"]).json()
    change("m000", 3, "After H")
    delta = post(client, "deltas/page", final["continuation"]).json()
    merged = {}
    for record in page["records"] + second["records"] + delta["records"]:
        if record["entity_version"] >= merged.get(record["entity_id"], {}).get("entity_version", 0):
            merged[record["entity_id"]] = record
    assert len(merged) == 104
    assert merged["m000"]["entity_version"] == 2
    assert merged["aaa"]["payload"]["display_name"] == "Below scanned cursor"
    incremental = post(client, "deltas/page", delta["continuation"]).json()
    assert [record["entity_version"] for record in incremental["records"]] == [3]


def test_oversized_projection_rolls_back_without_loading_body(monkeypatch):
    from cycling_workshop.sync.baseline_models import BaselineFamily
    from cycling_workshop.sync.baseline_queries import BaselineQueries
    from sqlalchemy import select

    client, _ = baseline_client()
    # SQLite permits an oversized historic String; the same gate covers PostgreSQL Text/JSON.
    with client.app.state.session_factory.begin() as session:
        session.add(
            CustomerRecord(
                id="oversized",
                organization_id="org-1",
                location_id="loc-1",
                display_name="x" * 2_000_000,
                created_at=NOW,
                updated_at=NOW,
                version=1,
            )
        )
    start = client.post(f"{ROOT}/baselines/start", json=start_body(client)).json()

    def forbidden_load(*args, **kwargs):
        raise AssertionError("oversized body must not cross the database boundary")

    monkeypatch.setattr(BaselineQueries, "load", forbidden_load)
    response = post(client, "baselines/page", start["continuation"])
    assert response.status_code == 413
    with client.app.state.session_factory() as session:
        family = session.scalar(select(BaselineFamily))
        assert family.sequence == 0 and family.response_json is None


def test_control_body_limit_is_before_auth_and_json_parsing():
    client, _ = baseline_client()
    client.headers.pop("Authorization")
    response = client.post(f"{ROOT}/baselines/start", content=b"x" * 16385)
    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("phase", ["scan", "delta"])
@pytest.mark.parametrize(
    "length,expected",
    [(1_045_000, 200), (1_047_500, 200), (1_047_700, 200), (1_047_750, 200), (1_048_576, 413)],
)
def test_exact_wire_budget_accepts_large_valid_text_and_rejects_overflow(phase, length, expected):
    from cycling_workshop.service_orders.models import ServiceOrderRecord
    from cycling_workshop.sync.models import ChangeRecord

    if phase == "delta" and length == 1_047_750:
        expected = 413
    client, _ = baseline_client()
    grants = frozenset({"sync.pull", "orders.read"})
    with client.app.state.session_factory.begin() as session:
        session.get(UserRecord, "user-1").capabilities = sorted(grants)
        session.add(
            CustomerRecord(
                id="customer",
                organization_id="org-1",
                location_id="loc-1",
                display_name="Synthetic",
                created_at=NOW,
                updated_at=NOW,
                version=1,
            )
        )
    token = client.app.state.session_tokens.issue(Principal("user-1", "org-1", "loc-1", grants))
    client.headers["Authorization"] = f"Bearer {token}"
    if phase == "delta":
        start = client.post(f"{ROOT}/baselines/start", json=start_body(client)).json()
        page = post(client, "baselines/page", start["continuation"]).json()
    with client.app.state.session_factory.begin() as session:
        session.add(
            ServiceOrderRecord(
                id="order",
                organization_id="org-1",
                location_id="loc-1",
                customer_id="customer",
                state="INTAKE",
                reported_problem="x" * length,
                priority="normal",
                created_at=NOW,
                updated_at=NOW,
                version=1,
            )
        )
        payload = dict(
            order_id="order",
            customer_id="customer",
            bicycle_id=None,
            organization_id="org-1",
            location_id="loc-1",
            state="INTAKE",
            reported_problem="x" * length,
            intake_condition=None,
            accessories=None,
            priority="normal",
            diagnosis=None,
            created_at=NOW.isoformat(),
            updated_at=NOW.isoformat(),
            version=1,
        )
        session.add(
            ChangeRecord(
                organization_id="org-1",
                location_id="loc-1",
                entity_type="service_order",
                entity_id="order",
                entity_version=1,
                operation="create",
                occurred_at=NOW,
                payload=payload,
            )
        )
    if phase == "scan":
        start = client.post(f"{ROOT}/baselines/start", json=start_body(client)).json()
        response = post(client, "baselines/page", start["continuation"])
    else:
        final = post(client, "baselines/finalize", page["continuation"]).json()
        response = post(client, "deltas/page", final["continuation"])
    assert response.status_code == expected, response.text[:300]
    assert len(response.content) <= 1_048_576
    if expected == 200:
        assert response.json()["records"][0]["payload"]["reported_problem"] == "x" * length
        if phase == "scan" and response.json()["phase"] == "scan":
            following = post(client, "baselines/page", response.json()["continuation"])
            assert following.status_code == 200
            assert following.json()["phase"] == "scan_complete"
            assert following.json()["records"] == []
        if phase == "delta" and response.json()["phase"] == "catching_up":
            following = post(client, "deltas/page", response.json()["continuation"])
            assert following.status_code == 200
            assert following.json()["phase"] == "complete"
            assert following.json()["records"] == []


def test_foreign_actor_cannot_lookup_family_and_changed_authority_cannot_replay():
    client, _ = baseline_client()
    start = client.post(f"{ROOT}/baselines/start", json=start_body(client)).json()
    grants = frozenset({"sync.pull", "customers.read"})
    with client.app.state.session_factory.begin() as session:
        session.add(
            UserRecord(
                id="other",
                organization_id="org-1",
                location_id="loc-1",
                username="other",
                display_name="Other",
                password_hash="synthetic-unused",
                capabilities=sorted(grants),
                is_active=True,
            )
        )
    other_token = client.app.state.session_tokens.issue(
        Principal("other", "org-1", "loc-1", grants)
    )
    original = client.headers["Authorization"]
    client.headers["Authorization"] = f"Bearer {other_token}"
    denied = post(client, "baselines/page", start["continuation"])
    assert denied.status_code == 422 and denied.json()["error"]["code"] == "cursor_invalid"
    assert start["baseline_id"] not in denied.text
    client.headers["Authorization"] = original
    with client.app.state.session_factory.begin() as session:
        session.get(UserRecord, "user-1").capabilities = ["sync.pull"]
    changed = post(client, "baselines/page", start["continuation"])
    assert changed.status_code == 409 and changed.json()["error"]["code"] == "context_changed"


def test_no_read_types_complete_empty_and_no_sync_pull_is_denied():
    client, _ = baseline_client()
    with client.app.state.session_factory.begin() as session:
        session.get(UserRecord, "user-1").capabilities = ["sync.pull"]
    token = client.app.state.session_tokens.issue(
        Principal("user-1", "org-1", "loc-1", frozenset({"sync.pull"}))
    )
    client.headers["Authorization"] = f"Bearer {token}"
    _, delta, records = complete(client)
    assert records == [] and delta.json()["phase"] == "complete"
    with client.app.state.session_factory.begin() as session:
        session.get(UserRecord, "user-1").capabilities = []
    assert client.post(f"{ROOT}/baselines/start", json=start_body(client)).status_code == 403


def test_expiry_immediately_before_commit_rolls_back_start(monkeypatch):
    from cycling_workshop.sync.baseline_models import BaselineFamily
    from sqlalchemy import event, func, select

    client, now = baseline_client()
    body = start_body(client)
    factory = client.app.state.session_factory

    def expire(session, context, instances):
        now[0] = NOW + timedelta(hours=8)

    event.listen(factory, "before_flush", expire)
    try:
        response = client.post(f"{ROOT}/baselines/start", json=body)
    finally:
        event.remove(factory, "before_flush", expire)
    assert response.status_code == 401
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(BaselineFamily)) == 0
