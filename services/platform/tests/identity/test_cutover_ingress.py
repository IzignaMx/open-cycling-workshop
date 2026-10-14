"""Exact supported writer catalog: floor rejection has zero persisted effects."""

from dataclasses import replace

import pytest
from cycling_workshop.db.base import Base
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.roles import CAPABILITIES
from cycling_workshop.shared.ids import new_id
from cycling_workshop.tenancy.models import OrganizationRecord
from sqlalchemy import select
from test_auth_api import build_client
from test_cutover_http import command_item, login

WRITERS = (
    "sync",
    "customer",
    "bicycle",
    "order",
    "transition",
    "product",
    "movement",
    "create_user",
    "patch_user",
    "revoke",
    "reset",
    "location",
    "logout",
    "password",
)


def snapshot(client):
    with client.app.state.session_factory() as session:
        return {
            table.name: sorted(
                [repr(dict(row)) for row in session.execute(select(table)).mappings()]
            )
            for table in Base.metadata.sorted_tables
        }


def setup_command(kind):
    client = build_client()
    client.app.state.settings = replace(client.app.state.settings, cutover_enabled=True)
    with client.app.state.session_factory.begin() as session:
        actor = session.get(UserRecord, "user-1")
        actor.capabilities = sorted(CAPABILITIES)
        actor.location_id = None
        session.add(
            UserRecord(
                id="target",
                organization_id="org-1",
                location_id="loc-1",
                username="target",
                display_name="Fixture target",
                password_hash=actor.password_hash,
                capabilities=["customers.read"],
                is_active=True,
            )
        )
    headers = {"Authorization": f"Bearer {login(client)}"}
    customer = client.post(
        "/api/v1/customers",
        headers=headers,
        json={
            "display_name": "Fixture customer",
            "location_id": "loc-1",
        },
    ).json()["customer_id"]
    order = client.post(
        "/api/v1/service-orders",
        headers=headers,
        json={
            "customer_id": customer,
            "location_id": "loc-1",
            "reported_problem": "Fixture noise",
        },
    ).json()["order_id"]
    product = client.post(
        "/api/v1/inventory/products",
        headers=headers,
        json={
            "location_id": "loc-1",
            "sku": "fixture-existing",
            "name": "Fixture part",
        },
    ).json()["product_id"]
    commands = {
        "sync": ("POST", "/api/v1/sync/mutations", {"mutations": [command_item()]}),
        "customer": (
            "POST",
            "/api/v1/customers",
            {"display_name": "New fixture", "location_id": "loc-1"},
        ),
        "bicycle": (
            "POST",
            "/api/v1/bicycles",
            {"customer_id": customer, "location_id": "loc-1", "brand": "Fixture"},
        ),
        "order": (
            "POST",
            "/api/v1/service-orders",
            {"customer_id": customer, "location_id": "loc-1", "reported_problem": "Fixture"},
        ),
        "transition": (
            "POST",
            f"/api/v1/service-orders/{order}/transitions",
            {"action": "start_diagnosis"},
        ),
        "product": (
            "POST",
            "/api/v1/inventory/products",
            {"location_id": "loc-1", "sku": "fixture-new", "name": "New fixture"},
        ),
        "movement": (
            "POST",
            "/api/v1/inventory/movements",
            {"movement_id": new_id(), "product_id": product, "kind": "ADJUST", "quantity": 2},
        ),
        "create_user": (
            "POST",
            "/api/v1/admin/users",
            {
                "username": "newfixture",
                "display_name": "Fixture",
                "location_id": "loc-1",
                "role": "Mechanic",
                "password": "synthetic-test-password",
            },
        ),
        "patch_user": (
            "PATCH",
            "/api/v1/admin/users/target",
            {"expected_version": 1, "display_name": "Changed fixture"},
        ),
        "revoke": ("POST", "/api/v1/admin/users/target/revoke-sessions", {"expected_version": 1}),
        "reset": (
            "POST",
            "/api/v1/admin/users/target/reset-password",
            {"expected_version": 1, "new_password": "synthetic-new-password"},
        ),
        "location": ("POST", "/api/v1/locations", {"name": "New fixture"}),
        "logout": ("POST", "/api/v1/auth/logout-all", None),
        "password": (
            "POST",
            "/api/v1/auth/change-password",
            {
                "current_password": "correct horse battery staple",
                "new_password": "synthetic-new-password",
            },
        ),
    }
    return client, headers, commands[kind]


@pytest.mark.parametrize("kind", WRITERS)
@pytest.mark.parametrize(
    "floor,protocol,allowed",
    [
        (0, None, True),
        (0, "0", True),
        (0, "1", True),
        (1, None, False),
        (1, "0", False),
        (1, "1", True),
        (0, "2", False),
        (1, "2", False),
    ],
)
def test_catalogued_writer_admission(kind, floor, protocol, allowed):
    client, headers, (method, path, body) = setup_command(kind)
    with client.app.state.session_factory.begin() as session:
        session.get(OrganizationRecord, "org-1").minimum_write_protocol = floor
    if protocol is not None:
        headers["X-OCWP-Write-Protocol"] = protocol
    if kind == "sync" and protocol == "1":
        context = client.get("/api/v1/auth/context?selected_location_id=loc-1", headers=headers)
        headers["X-OCWP-Authorization-Epoch"] = context.json()["authorization_epoch"]
    before = snapshot(client)
    response = client.request(method, path, headers=headers, json=body)
    if allowed:
        assert response.status_code in (200, 201, 204), response.text
    else:
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "client_upgrade_required"
        assert snapshot(client) == before


def test_protocol_header_never_confers_capabilities():
    client = build_client()
    client.app.state.settings = replace(client.app.state.settings, cutover_enabled=True)
    with client.app.state.session_factory.begin() as session:
        session.get(OrganizationRecord, "org-1").minimum_write_protocol = 1
        session.get(UserRecord, "user-1").capabilities = ["customers.read"]
    headers = {"Authorization": f"Bearer {login(client)}", "X-OCWP-Write-Protocol": "1"}
    before = snapshot(client)
    response = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"display_name": "Fixture", "location_id": "loc-1"},
    )
    assert response.status_code == 403
    assert snapshot(client) == before
