"""Preparation-only service contracts; SQLite functional checks are not hosted proof."""

import json

import pytest

from tests.labs.m2.authority import LabAuthority, LabDenied
from tests.labs.m2.runtime_authority import OwnedRun
from tests.labs.m2.runtime_service import functional_checks, status_payload


def test_closed_service_functional_checks_use_actual_sqlite_and_asgi_not_mock_auth():
    authority = LabAuthority()
    try:
        result = functional_checks(authority)
        assert result == {
            "scope": True,
            "current_grants": True,
            "rotation": True,
            "revocation": True,
            "closed_response": True,
        }
    finally:
        authority.close()


def test_status_is_bounded_fixed_counts_and_identity_not_rows_or_exceptions():
    run = OwnedRun("a" * 32, "b" * 40, "c" * 40)
    data = json.loads(status_payload(run, "ready", {"scope": True}, cleanup=False))
    assert data["phase"] == "ready"
    assert data["source_commit"] == "b" * 40
    assert data["checks"] == {"scope": True}
    assert data["database_cleanup_complete"] is False
    assert len(status_payload(run, "ready", {}, cleanup=False)) < 65536


@pytest.mark.parametrize("checks", [{"secret": True}, {"scope": "raw message"}, {"scope": 1}])
def test_status_never_serializes_unknown_or_nonboolean_details(checks):
    with pytest.raises(LabDenied):
        status_payload(OwnedRun("a" * 32, "b" * 40, "c" * 40), "failed", checks, cleanup=False)


def test_timeout_proof_requires_expected_driver_sqlstate_and_measured_bound():
    from tests.labs.m2.runtime_service import timeout_evidence

    assert timeout_evidence("55P03", ["55P03"], 2.0, 1.5, 4.5)
    assert not timeout_evidence("55P03", ["57014"], 2.0, 1.5, 4.5)
    assert not timeout_evidence("25P04", [], 8.0, 7.5, 10.0)
    assert not timeout_evidence("57014", ["57014"], 0.1, 4.5, 7.0)


def test_service_payload_is_consumed_by_exact_runtime_client_without_format_widening():
    from tests.labs.m2.runtime_client import authorization_header
    from tests.labs.m2.runtime_service import credential_payload

    authority = LabAuthority()
    try:
        credential = authority.issue()
        payload = credential_payload(credential)
        is_bare = payload.startswith(b"m2_")
        assert is_bare
        assembled = authorization_header(payload)
        matches = assembled == credential.authorization()
        assert matches
        with authority.read(assembled):
            pass
    finally:
        authority.close()


def test_postgres_receipt_producer_refuses_sqlite_before_claiming_runtime_checks():
    from tests.labs.m2.runtime_service import postgres_checks

    authority = LabAuthority()
    try:
        with pytest.raises(LabDenied):
            postgres_checks(authority)
        assert not authority._witnesses
    finally:
        authority.close()


def test_api_receipt_never_claims_delivery_tls_socket_or_process_cleanup():
    run = OwnedRun("a" * 32, "b" * 40, "c" * 40)
    data = json.loads(status_payload(run, "stopped", {}, cleanup=True))
    assert data.get("database_cleanup_complete") is True
    assert "cleanup_complete" not in data
    assert set(data) == {
        "schema",
        "nonce",
        "source_commit",
        "source_tree",
        "phase",
        "checks",
        "database_cleanup_complete",
    }
