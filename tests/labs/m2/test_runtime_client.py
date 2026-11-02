"""Pure validation/configuration only; no network, TLS keys or runtime file creation."""

import importlib

import pytest


def subject():
    return importlib.import_module("tests.labs.m2.runtime_client")


def item():
    return {
        "product_id": "00000000-0000-4000-8002-000000000111",
        "sku": "LAB-A-1-001",
        "name": "Synthetic A/1 product 1",
        "unit": "pieza",
        "version": 1,
    }


def test_closed_projection():
    rows, next_offset = subject().validate_page({"items": [item()], "next_offset": None}, 0)
    assert rows == [item()] and next_offset is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("version", 0),
        ("name", "x" * 201),
        ("sku", "x" * 81),
        ("unit", "x" * 31),
        ("product_id", "not-uuid"),
    ],
)
def test_invalid_dto(field, value):
    row = item()
    row[field] = value
    with pytest.raises(subject().RuntimeClientRefused):
        subject().validate_page({"items": [row], "next_offset": None}, 0)


@pytest.mark.parametrize("following", [0, 201, True, "50", -1])
def test_bad_pagination(following):
    with pytest.raises(subject().RuntimeClientRefused):
        subject().validate_page({"items": [], "next_offset": following}, 0)


def test_scope_metadata_exact_and_deadline_not_reset():
    scope = {
        key: "00000000-0000-4000-8000-000000000001"
        for key in ["organization_id", "location_id", "dataset_incarnation"]
    }
    scope.update({key: "a" * 32 for key in ["installation_id", "machine_id", "run_id"]})
    scope["generation"] = 1
    parsed, deadline = subject().validate_metadata({"scope": scope, "run_deadline": 300.0}, 200.0)
    assert parsed == scope and deadline == 300.0
    for invalid in (199, 1101, float("nan")):
        with pytest.raises(subject().RuntimeClientRefused):
            subject().validate_metadata({"scope": scope, "run_deadline": invalid}, 200.0)


def test_transport_configuration_is_closed():
    module = subject()
    assert module.ORIGIN == "https://ocwp-m2-api"
    assert str(module.SOCKET_PATH) == "/run/m2-api/catalogue.sock"
    assert module.MAX_PAGES == 4 and module.MAX_BODY == 65536


def test_negative_tls_requires_actual_verification_error_not_connection_refusal():
    import ssl

    module = subject()
    assert module.is_certificate_failure(ConnectionError("public-canary")) is False
    outer = RuntimeError("public-canary")
    outer.__cause__ = ssl.SSLCertVerificationError("public-verification-canary")
    assert module.is_certificate_failure(outer) is True


def test_credential_file_contract_requires_bare_opaque_format():
    module = subject()
    bare = b"m2_" + b"a" * 32 + b"_" + b"x" * 43
    assert bool(module.authorization_header(bare).startswith("Bearer m2_"))
    for invalid in (b"Bearer " + bare, bare + b"\n", b"x" * 129):
        with pytest.raises(module.RuntimeClientRefused):
            module.authorization_header(invalid)


def os_evidence():
    return {
        "status": "Uid:\t1001\t1001\t1001\t1001\nCapEff:\t0000000000000000\nNoNewPrivs:\t1\n",
        "uid": 1001,
        "memory": "134217728",
        "pids": "32",
        "cpu": "50000 100000",
        "interfaces": {"lo"},
        "store_bytes": 16777216,
        "mountinfo": "1 2 0:1 / /run/m2-store rw - tmpfs tmpfs rw\n",
        "namespace": "net:[4026532999]",
    }


def test_effective_os_evidence_parser_not_runtime_proof():
    result = subject().validate_os_evidence(**os_evidence())
    assert result == {"isolation_verified": True, "network_namespace": "net:[4026532999]"}


@pytest.mark.parametrize(
    "field,value",
    [
        ("uid", 0),
        ("memory", "max"),
        ("pids", "max"),
        ("cpu", "100000 100000"),
        ("interfaces", {"lo", "eth0"}),
        ("store_bytes", 16777217),
        ("namespace", "arbitrary"),
        ("mountinfo", "1 2 0:1 / /run/m2-store rw - ext4 dev rw\n"),
        ("status", "Uid: 1001 0 1001 1001\nCapEff: 0\nNoNewPrivs: 1\n"),
        ("status", "Uid: 1001 1001 1001 1001\nCapEff: 1\nNoNewPrivs: 1\n"),
        ("status", "Uid: 1001 1001 1001 1001\nCapEff: 0\nNoNewPrivs: 0\n"),
    ],
)
def test_effective_policy_missing_or_mismatched_refused(field, value):
    evidence = os_evidence()
    evidence[field] = value
    with pytest.raises(subject().RuntimeClientRefused):
        subject().validate_os_evidence(**evidence)
