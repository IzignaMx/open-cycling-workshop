"""Synthetic profile API regressions; these do not prove PostgreSQL locks."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from cycling_workshop.identity.audit import IdentityAuditRecord
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.tenancy.models import LocationRecord
from sqlalchemy import select
from test_administration_api import Fixture
from test_administration_api import db as db

PATH = "/api/v1/locations/loc-a/branding"
PAYLOAD = {
    "expected_version": 0,
    "display_name": "  Cafe\u0301 Taller  ",
    "palette_id": "jade",
    "logo_png_base64": None,
}


def ready(db, *, grants=("branding.read", "branding.write"), location="loc-a"):
    db.client.app.state.settings = replace(db.client.app.state.settings, cutover_enabled=True)
    db.seed("brand-actor", capabilities=set(grants), location=location)
    return {**db.headers("brand-actor"), "X-OCWP-Write-Protocol": "1"}


def test_default_and_cas_update_use_workshop_scope_safe_audit_and_no_store(db: Fixture):
    headers = {**ready(db), "X-Request-ID": "private-sentinel"}
    response = db.client.get(PATH, headers=headers)
    assert response.status_code == 200, response.text
    default = response.json()
    assert default["version"] == 0 and default["display_name"] == "A1"
    assert default["logo_state"] == "none" and default["logo"] is None
    assert default["updated_at"] is None and default["updated_by"] is None
    assert default["organization_id"] == "org-a" and default["location_id"] == "loc-a"
    response = db.client.put(PATH, headers=headers, json=PAYLOAD)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["display_name"] == "Café Taller" and saved["version"] == 1
    assert saved["updated_by"] == "brand-actor" and saved["updated_at"]
    assert saved["dataset_incarnation"] == default["dataset_incarnation"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"] != headers["X-Request-ID"]
    assert db.client.put(PATH, headers=headers, json=PAYLOAD).status_code == 409
    assert db.client.get(PATH, headers=headers).json() == saved
    with db.factory() as session:
        audit = session.scalars(select(IdentityAuditRecord)).one()
        assert audit.target_type == "location" and audit.target_id is None
        assert audit.action == "branding.updated" and audit.actor_id == "brand-actor"
        encoded = json.dumps([audit.before, audit.after])
        assert "Café" not in encoded and "private-sentinel" not in encoded
        assert audit.after["location_id"] == "loc-a" and audit.after["version"] == 1
        assert session.get(LocationRecord, "loc-a").name == "A1"


@pytest.mark.parametrize(
    "grants,read,write",
    [
        ([], 403, 403),
        (["*"], 403, 403),
        (["*", "branding.read"], 200, 403),
        (["*", "branding.write"], 403, 200),
        (["*", "branding.read", "branding.write"], 200, 200),
        (["branding.read"], 200, 403),
        (["branding.write"], 403, 200),
        (["branding.read", "branding.write"], 200, 200),
    ],
)
def test_literal_read_write_are_independent(db: Fixture, grants, read, write):
    headers = ready(db, grants=grants)
    assert db.client.get(PATH, headers=headers).status_code == read
    assert db.client.put(PATH, headers=headers, json=PAYLOAD).status_code == write


@pytest.mark.parametrize("target", ["loc-a2", "loc-b", "missing"])
def test_location_bound_actor_cannot_cross_target(db: Fixture, target):
    headers = ready(db)
    path = f"/api/v1/locations/{target}/branding"
    for response in (
        db.client.get(path, headers=headers),
        db.client.put(path, headers=headers, json=PAYLOAD),
    ):
        assert response.status_code == 403 and response.headers["cache-control"] == "no-store"


def test_organization_actor_uses_explicit_authorized_location(db: Fixture):
    headers = ready(db, location=None)
    for target in ("loc-a", "loc-a2"):
        response = db.client.put(
            f"/api/v1/locations/{target}/branding",
            headers=headers,
            json={**PAYLOAD, "display_name": target},
        )
        assert response.status_code == 200 and response.json()["display_name"] == target
    assert db.client.get("/api/v1/locations/loc-b/branding", headers=headers).status_code == 403


@pytest.mark.parametrize(
    "patch",
    [
        {"organization_id": "org-b"},
        {"location_id": "loc-b"},
        {"expected_version": True},
        {"expected_version": -1},
        {"display_name": "\x00private"},
        {"display_name": "a" * 161},
        {"display_name": " "},
        {"palette_id": "custom"},
        {"logo_png_base64": "https://evil.invalid/logo.png"},
    ],
)
def test_closed_profile_input_and_image_errors_are_safe(db: Fixture, patch):
    headers = ready(db)
    response = db.client.put(PATH, headers=headers, json={**PAYLOAD, **patch})
    assert response.status_code == 422, response.text
    assert response.headers["cache-control"] == "no-store"
    assert "private" not in response.text and "evil.invalid" not in response.text


@pytest.mark.parametrize("value", [None, "0", "2"])
def test_both_reads_and_writes_require_current_protocol(db: Fixture, value):
    headers = ready(db)
    if value is None:
        del headers["X-OCWP-Write-Protocol"]
    else:
        headers["X-OCWP-Write-Protocol"] = value
    assert db.client.get(PATH, headers=headers).status_code == 409
    assert db.client.put(PATH, headers=headers, json=PAYLOAD).status_code == 409


def test_oversized_body_rejected_even_without_accurate_content_length(db: Fixture):
    headers = ready(db)
    for content in (b" " * 393217, (b" " * 65536 for _ in range(7))):
        response = db.client.put(
            PATH,
            headers={**headers, "Content-Type": "application/json", "Content-Length": "1"},
            content=content,
        )
        assert response.status_code == 413 and response.headers["cache-control"] == "no-store"


def test_default_name_is_safe_render_only_normalization(db: Fixture):
    headers = ready(db)
    for name, expected in (("  Cafe\u0301  ", "Café"), ("unsafe\x00name", "Taller")):
        with db.factory.begin() as session:
            session.get(LocationRecord, "loc-a").name = name
        response = db.client.get(PATH, headers=headers)
        assert response.status_code == 200 and response.json()["display_name"] == expected
        with db.factory() as session:
            assert session.get(LocationRecord, "loc-a").name == name


def test_current_revoked_actor_cannot_read_or_write(db: Fixture):
    headers = ready(db)
    with db.factory.begin() as session:
        session.get(UserRecord, "brand-actor").session_version += 1
    assert db.client.get(PATH, headers=headers).status_code == 401
    assert db.client.put(PATH, headers=headers, json=PAYLOAD).status_code == 401


def test_actual_canonical_logo_save_read_unavailable_and_explicit_removal(db: Fixture, tmp_path):
    import base64

    from cycling_workshop.branding.models import WorkshopBrandProfileRecord
    from test_images import encoded, png

    headers = ready(db)
    db.client.app.state.settings = replace(
        db.client.app.state.settings, branding_asset_root=str(tmp_path)
    )
    response = db.client.put(
        PATH, headers=headers, json={**PAYLOAD, "logo_png_base64": encoded(png())}
    )
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["logo_state"] == "available" and saved["logo_diagnostic"] is None
    assert saved["logo"]["width"] == 2 and saved["logo"]["height"] == 2
    assert saved["logo"]["mime_type"] == "image/png"
    assert len(base64.b64decode(saved["logo"]["png_base64"])) == saved["logo"]["byte_count"]
    assert set(saved["logo"]) == {
        "sha256",
        "byte_count",
        "width",
        "height",
        "mime_type",
        "png_base64",
    }
    assert len(response.content) <= 393216
    assert db.client.get(PATH, headers=headers).json() == saved
    with db.factory() as session:
        profile = session.get(WorkshopBrandProfileRecord, ("org-a", "loc-a"))
        key = profile.logo_key
    files = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert len(files) == 1 and str(files[0]).endswith(key)
    original = files[0].read_bytes()
    files[0].write_bytes(b"corrupt")
    unavailable = db.client.get(PATH, headers=headers).json()
    assert unavailable["version"] == saved["version"]
    assert (
        unavailable["logo_state"] == "unavailable"
        and unavailable["logo_diagnostic"] == "asset_unavailable"
    )
    assert unavailable["logo"]["png_base64"] is None
    files[0].write_bytes(original)
    removed = db.client.put(PATH, headers=headers, json={**PAYLOAD, "expected_version": 1})
    assert removed.status_code == 200 and removed.json()["logo_state"] == "none"
    assert removed.json()["version"] == 2 and files[0].read_bytes() == original


@pytest.mark.parametrize("change", ["revoke", "disable", "scope", "grants", "incarnation"])
def test_authority_is_checked_again_after_decode_before_publication(
    db: Fixture, monkeypatch, change
):
    from uuid import uuid4

    from cycling_workshop.branding import router
    from cycling_workshop.branding.assets import BrandingAssetStore
    from cycling_workshop.tenancy.models import OrganizationRecord

    headers = ready(db)

    def decode(_payload):
        with db.factory.begin() as session:
            actor = session.get(UserRecord, "brand-actor")
            if change == "revoke":
                actor.session_version += 1
            if change == "disable":
                actor.is_active = False
            if change == "scope":
                actor.location_id = "loc-a2"
            if change == "grants":
                actor.capabilities = []
            if change == "incarnation":
                session.get(OrganizationRecord, "org-a").dataset_incarnation = str(uuid4())
        return None

    def forbidden(*args, **kwargs):
        pytest.fail("unadmitted request published asset bytes")

    monkeypatch.setattr(router, "decode_logo", decode)
    monkeypatch.setattr(BrandingAssetStore, "put", forbidden)
    response = db.client.put(PATH, headers=headers, json=PAYLOAD)
    assert response.status_code == (403 if change == "grants" else 401), response.text
    with db.factory() as session:
        assert list(session.scalars(select(IdentityAuditRecord))) == []


@pytest.mark.parametrize("failure", ["storage", "audit"])
def test_failed_publication_or_audit_preserves_profile_and_audit(
    db: Fixture, monkeypatch, tmp_path, failure
):
    from cycling_workshop.branding.assets import BrandingAssetStore
    from cycling_workshop.branding.models import WorkshopBrandProfileRecord
    from sqlalchemy import event
    from test_images import encoded, png

    headers = ready(db)
    db.client.app.state.settings = replace(
        db.client.app.state.settings, branding_asset_root=str(tmp_path)
    )
    assert db.client.put(PATH, headers=headers, json=PAYLOAD).status_code == 200

    def fail(*args, **kwargs):
        if failure == "storage":
            raise OSError("private-path-sentinel")
        raise RuntimeError("private-audit-sentinel")

    if failure == "storage":
        monkeypatch.setattr(BrandingAssetStore, "put", fail)
    else:
        event.listen(IdentityAuditRecord, "before_insert", fail)
    try:
        response = db.client.put(
            PATH,
            headers=headers,
            json={**PAYLOAD, "expected_version": 1, "logo_png_base64": encoded(png())},
        )
    finally:
        if failure == "audit":
            event.remove(IdentityAuditRecord, "before_insert", fail)
    assert response.status_code == (503 if failure == "storage" else 500)
    assert response.headers["cache-control"] == "no-store" and "sentinel" not in response.text
    with db.factory() as session:
        profile = session.get(WorkshopBrandProfileRecord, ("org-a", "loc-a"))
        assert profile.version == 1 and profile.logo_key is None
        assert len(list(session.scalars(select(IdentityAuditRecord)))) == 1


def test_stale_cas_precedes_asset_publication(db: Fixture, monkeypatch):
    from cycling_workshop.branding.assets import BrandingAssetStore
    from test_images import encoded, png

    headers = ready(db)
    assert db.client.put(PATH, headers=headers, json=PAYLOAD).status_code == 200

    def no_put(*args, **kwargs):
        pytest.fail("stale write published bytes")

    monkeypatch.setattr(BrandingAssetStore, "put", no_put)
    response = db.client.put(
        PATH, headers=headers, json={**PAYLOAD, "logo_png_base64": encoded(png())}
    )
    assert response.status_code == 409


@pytest.mark.parametrize("stage", ["decode", "audit"])
def test_expiry_during_long_work_prevents_commit(db: Fixture, monkeypatch, stage):
    from datetime import UTC, datetime, timedelta

    from cycling_workshop.branding import router, service
    from cycling_workshop.branding.models import WorkshopBrandProfileRecord
    from cycling_workshop.identity.security import SessionTokenService

    now = [datetime.now(UTC)]
    db.client.app.state.session_tokens = SessionTokenService(
        secret=db.client.app.state.settings.auth_secret,
        ttl=timedelta(minutes=1),
        clock=lambda: now[0],
    )
    headers = ready(db)
    if stage == "decode":

        def slow_decode(_payload):
            now[0] += timedelta(minutes=2)
            return None

        monkeypatch.setattr(router, "decode_logo", slow_decode)
    else:
        original = service.append_audit

        def slow_audit(*args, **kwargs):
            original(*args, **kwargs)
            now[0] += timedelta(minutes=2)

        monkeypatch.setattr(service, "append_audit", slow_audit)
    response = db.client.put(PATH, headers=headers, json=PAYLOAD)
    assert response.status_code == 401
    with db.factory() as session:
        assert list(session.scalars(select(WorkshopBrandProfileRecord))) == []
        assert list(session.scalars(select(IdentityAuditRecord))) == []


@pytest.mark.parametrize("field,value", [("logo_sha256", "g" * 64), ("logo_key", "../outside")])
def test_database_rejects_noncanonical_asset_descriptor(db: Fixture, field, value):
    from cycling_workshop.branding.models import WorkshopBrandProfileRecord
    from sqlalchemy.exc import IntegrityError

    headers = ready(db)
    assert db.client.put(PATH, headers=headers, json=PAYLOAD).status_code == 200
    with pytest.raises(IntegrityError), db.factory.begin() as session:
        profile = session.get(WorkshopBrandProfileRecord, ("org-a", "loc-a"))
        profile.logo_sha256 = "a" * 64
        profile.logo_key = "aa/" + "a" * 64
        profile.logo_byte_count = 1
        profile.logo_width = profile.logo_height = 1
        setattr(profile, field, value)


def test_saved_brand_converges_for_second_reader_without_rotating_authority(db: Fixture):
    from cycling_workshop.sync.models import ChangeRecord

    headers = ready(db)
    before = db.client.get("/api/v1/auth/context", headers=headers).json()
    saved = db.client.put(PATH, headers=headers, json=PAYLOAD)
    assert saved.status_code == 200
    after = db.client.get("/api/v1/auth/context", headers=headers).json()
    assert before["authorization_epoch"] == after["authorization_epoch"]
    db.seed("second-reader", capabilities={"branding.read"})
    other = {**db.headers("second-reader"), "X-OCWP-Write-Protocol": "1"}
    assert db.client.get(PATH, headers=other).json() == saved.json()
    with db.factory() as session:
        assert list(session.scalars(select(ChangeRecord))) == []
        assert session.get(UserRecord, "brand-actor").session_version == 1


def test_many_invalid_fields_cannot_amplify_a_bounded_request_into_oversized_error(db: Fixture):
    headers = ready(db)
    payload = {**PAYLOAD, **{f"field-{index}": 0 for index in range(12000)}}
    assert len(json.dumps(payload).encode("utf-8")) < 393216
    response = db.client.put(PATH, headers=headers, json=payload)
    assert response.status_code == 422
    assert len(response.content) <= 393216
    assert response.headers["cache-control"] == "no-store"
