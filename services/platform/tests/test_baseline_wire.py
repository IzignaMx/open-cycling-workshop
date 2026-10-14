import pytest
from cycling_workshop.api.errors import ApiError
from cycling_workshop.sync.baseline_codec import BaselineCodec, reference_hash, token_hash
from cycling_workshop.sync.baseline_schemas import StartRequest, validate_record
from pydantic import ValidationError


def customer():
    return {
        "entity_type": "customer",
        "entity_id": "Customer-A",
        "entity_version": 1,
        "payload": {
            "customer_id": "Customer-A",
            "organization_id": "org",
            "location_id": "loc",
            "display_name": "ñ" * 4001,
            "email": None,
            "phone": None,
            "created_at": "2026-01-01T01:00:00+01:00",
            "updated_at": "2026-01-01T00:00:00Z",
            "version": 1,
        },
    }


def test_codec_roundtrip_and_hashes():
    codec = BaselineCodec("test-only-secret")
    reference = codec.new_reference()
    assert len(reference) == 32
    token = codec.encode(reference, 0, "scan")
    decoded = codec.decode(token)
    assert (decoded.reference, decoded.sequence, decoded.purpose) == (reference, 0, "scan")
    assert len(reference_hash(reference)) == len(token_hash(token)) == 64
    for changed in [
        token + "=",
        token.replace(".0.", ".00."),
        token.replace(".scan.", ".delta."),
        token.replace("b1.", "eyJ.", 1),
        "é",
        "",
        token + "\n",
    ]:
        with pytest.raises(ApiError) as error:
            codec.decode(changed)
        assert (error.value.status_code, error.value.code) == (422, "cursor_invalid")
    with pytest.raises(ApiError):
        BaselineCodec("other-test-secret").decode(token)


@pytest.mark.parametrize("sequence", [True, -1, 2**53, 1.5, "1"])
def test_invalid_sequences(sequence):
    codec = BaselineCodec("test-only-secret")
    with pytest.raises(ApiError):
        codec.encode(codec.new_reference(), sequence, "scan")


def test_record_normalizes_and_preserves_text():
    result = validate_record(customer(), "org", "loc")
    assert result["payload"]["created_at"] == "2026-01-01T00:00:00Z"
    assert len(result["payload"]["display_name"]) == 4001


@pytest.mark.parametrize("mutation", ["extra", "missing", "version_bool", "scope", "id", "naive"])
def test_record_rejects_inconsistent_or_open_payload(mutation):
    value = customer()
    payload = value["payload"]
    if mutation == "extra":
        payload["unexpected"] = None
    if mutation == "missing":
        del payload["phone"]
    if mutation == "version_bool":
        value["entity_version"] = True
    if mutation == "scope":
        payload["organization_id"] = "other"
    if mutation == "id":
        value["entity_id"] = "different"
    if mutation == "naive":
        payload["created_at"] = "2026-01-01T00:00:00"
    with pytest.raises(ApiError):
        validate_record(value, "org", "loc")


def test_start_uuid_and_protocol_strictness():
    value = dict(
        protocol=1,
        selected_location_id="loc",
        authorization_epoch="epoch",
        request_id="12345678-1234-4234-9234-123456789abc",
    )
    assert StartRequest(**value).request_id == value["request_id"]
    for bad in [True, 1.0, "1", 2]:
        with pytest.raises(ValidationError):
            StartRequest(**(value | {"protocol": bad}))
    for bad in [value["request_id"].upper(), "not-a-uuid"]:
        with pytest.raises(ValidationError):
            StartRequest(**(value | {"request_id": bad}))


@pytest.mark.parametrize("purpose", ["scan", "finalize", "delta", "checkpoint"])
def test_codec_boundary_and_domain_separation(purpose):
    import base64
    import hmac

    codec = BaselineCodec("test-only-secret")
    token = codec.encode(codec.new_reference(), 2**53 - 1, purpose)
    assert codec.decode(token).sequence == 2**53 - 1
    prefix = token.rsplit(".", 1)[0]
    raw_mac = base64.urlsafe_b64encode(hmac.digest(b"test-only-secret", prefix.encode(), "sha256"))
    with pytest.raises(ApiError):
        codec.decode(prefix + "." + raw_mac.decode().rstrip("="))


@pytest.mark.parametrize(
    "bad", [None, 123, "x" * 513, "b1." + "A" * 32 + ".9007199254740992.scan." + "A" * 43]
)
def test_codec_rejects_invalid_runtime_inputs(bad):
    with pytest.raises(ApiError):
        BaselineCodec("test-only-secret").decode(bad)


@pytest.mark.parametrize("version", [True, 1.0, 0, -1, 2**53, "1"])
def test_both_versions_are_strict(version):
    value = customer()
    value["payload"]["version"] = version
    with pytest.raises(ApiError):
        validate_record(value, "org", "loc")


@pytest.mark.parametrize(
    "state",
    [
        "INTAKE",
        "DIAGNOSIS",
        "AUTHORIZED",
        "REJECTED",
        "IN_PROGRESS",
        "WAITING_FOR_PARTS",
        "READY",
        "CLOSED",
        "CANCELLED",
    ],
)
def test_order_states_and_long_stored_text(state):
    value = customer()
    payload = value["payload"]
    del payload["display_name"], payload["email"], payload["phone"]
    payload.update(
        order_id="order",
        bicycle_id=None,
        state=state,
        reported_problem="text" * 2000,
        intake_condition=None,
        accessories=None,
        priority="custom",
        diagnosis=None,
    )
    value.update(entity_type="service_order", entity_id="order")
    assert validate_record(value, "org", "loc")["payload"]["state"] == state
    payload["state"] = "unknown"
    with pytest.raises(ApiError):
        validate_record(value, "org", "loc")


def test_bicycle_projection_exact_nullable_keys():
    value = customer()
    payload = value["payload"]
    del payload["display_name"], payload["email"], payload["phone"]
    payload.update(
        bicycle_id="bike",
        brand="brand",
        model=None,
        bicycle_type=None,
        wheel_size=None,
        notes="large" * 4001,
    )
    value.update(entity_type="bicycle", entity_id="bike")
    assert validate_record(value, "org", "loc")["payload"]["notes"] == payload["notes"]
    del payload["model"]
    with pytest.raises(ApiError):
        validate_record(value, "org", "loc")


def test_dto_closure_record_count_and_completion():
    from cycling_workshop.sync.baseline_schemas import DeltaPage, PageRequest, ScanPage

    token = BaselineCodec("test-only-secret").encode("A" * 32, 0, "scan")
    base = dict(
        protocol=1,
        baseline_id="12345678-1234-4234-9234-123456789abc",
        authorization_epoch="epoch",
        page_id="page",
        predecessor=token,
        continuation=token,
        records=[],
    )
    assert ScanPage(**base, phase="scan").records == []
    for change in [{"records": [customer()] * 101}, {"unknown": None}, {"phase": "wrong"}]:
        with pytest.raises(ValidationError):
            ScanPage(**(base | {"phase": "scan"} | change))
    completion = dict(
        baseline_id=base["baseline_id"], authorization_epoch="epoch", checkpoint=token
    )
    assert DeltaPage(**base, phase="complete", completion=completion).completion is not None
    for change in [
        {"completion": None},
        {"completion": completion | {"checkpoint": "wrong"}},
        {"completion": completion | {"baseline_id": None}},
        {"completion": completion | {"authorization_epoch": "wrong"}},
        {"phase": "catching_up"},
    ]:
        with pytest.raises(ValidationError):
            DeltaPage(**(base | {"phase": "complete", "completion": completion} | change))
    for bad in ["é", "a" * 513, "", 1]:
        with pytest.raises(ValidationError):
            PageRequest(protocol=1, continuation=bad)


@pytest.mark.parametrize("secret", ["", None, 123])
def test_codec_rejects_empty_or_non_string_key(secret):
    with pytest.raises(ApiError):
        BaselineCodec(secret)
