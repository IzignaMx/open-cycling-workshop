"""Pure ownership codec/gate tests: no process, DB, signal or H/S execution."""

import copy
import json

import pytest

from scripts.ci.quote_ownership_evidence import (
    PUBLIC_PROPOSAL_SHA256,
    MeasurementGate,
    OwnershipEvidenceError,
    decode_frame,
    decode_receipt,
    encode_receipt,
)


@pytest.fixture
def identity():
    return {
        "commit": "a" * 40,
        "tree": "b" * 40,
        "worker_image": "sha256:" + "c" * 64,
        "pg_image": "sha256:" + "d" * 64,
        "authorization": PUBLIC_PROPOSAL_SHA256,
        "nonce": "e" * 32,
        "run_id": "123",
        "workflow_id": "456",
        "run_number": 1,
        "run_attempt": 1,
        "repository": "IzignaMx/open-cycling-workshop",
        "repository_id": 1327018760,
        "workflow_path": ".github/workflows/quote-ownership-measurement.yml",
        "ref": "refs/heads/main",
        "database": "synthetic",
        "role": "mock_pending_role",
    }


def backend(identity):
    return {
        "pid": 1234,
        "start_us": 123456789,
        "database": identity["database"],
        "role": identity["role"],
    }


@pytest.fixture
def receipt(identity):
    def case(name, start, ready, stop, reap, absent):
        return {
            "name": name,
            "status": "passed",
            "backend": {**backend(identity), "start_us": 123456789 + (name == "S")},
            "process": {
                "pid": 100 + (name == "S"),
                "start_ticks": 99 + (name == "S"),
                "pidfd_owned": True,
            },
            "start_ns": start,
            "ready_ns": ready,
            "stop_ns": stop,
            "reaped_ns": reap,
            "absent_ns": absent,
            "read_only": True,
            "clean_session": True,
            "same_backend": True,
        }

    return {
        "schema": 1,
        "kind": "ocwp.quote_ownership.receipt",
        "identity": identity,
        "status": "passed",
        "failure": None,
        "setup_ns": 1_000_000_000,
        "elapsed_ns": 12_000_000_000,
        "observer": {
            **dict.fromkeys(
                ["reserved", "read_only", "transaction_idle", "closed", "reaped"], True
            ),
            "process": {"pid": 90, "start_ticks": 80, "pidfd_owned": True},
            "reserved_setup_ns": 900_000_000,
            "closed_ns": 11_000_000_001,
            "reaped_ns": 11_000_000_002,
        },
        "cases": [
            case("H", 0, 1, 2, 3, 4),
            case("S", 1_000_000_000, 2_000_000_000, 9_000_000_000, 10_000_000_000, 11_000_000_000),
        ],
        "resources": {
            "worker_peak_bytes": 123,
            "pg_peak_bytes": 456,
            "worker_processes": 4,
            "pg_processes": 7,
            "pressure_events": 0,
        },
        "primary_cleanup": "verified_absent",
        "independent_cleanup": "verified_absent",
    }


def frame(identity, event="GO", sender="host", case="setup", payload=None):
    return {
        "schema": 1,
        "kind": "ocwp.ownership.frame",
        "identity": identity,
        "sender": sender,
        "case": case,
        "sequence": 1,
        "event": event,
        "payload": {} if payload is None else payload,
    }


def wire(value):
    body = json.dumps(value, separators=(",", ":")).encode()
    return len(body).to_bytes(4, "big") + body


def test_closed_receipt_round_trip_is_only_validation_of_claims(identity, receipt):
    raw = encode_receipt(receipt, identity)
    assert len(raw) <= 16384
    assert decode_receipt(raw, identity) == receipt
    # These are synthetic claims, never measured runtime proof.


@pytest.mark.parametrize(
    "path,value",
    [
        (("unexpected",), "private canary"),
        (("schema",), True),
        (("identity", "commit"), "f" * 40),
        (("identity", "run_attempt"), 2),
        (("identity", "run_number"), True),
        (("status",), "success"),
        (("setup_ns",), 65_000_000_001),
        (("elapsed_ns",), 26_000_000_001),
        (("elapsed_ns",), 5),
        (("observer", "closed"), False),
        (("observer", "reaped"), False),
        (("observer", "read_only"), False),
        (("observer", "transaction_idle"), False),
        (("resources", "pressure_events"), 1),
        (("resources", "worker_peak_bytes"), 768 * 1024**2 + 1),
        (("resources", "pg_processes"), 129),
        (("primary_cleanup",), "pending"),
        (("independent_cleanup",), "unknown"),
        (("failure",), "private exception"),
        (("cases", 0, "absent_ns"), 8_000_000_001),
        (("cases", 0, "reaped_ns"), None),
        (("cases", 0, "same_backend"), False),
        (("cases", 0, "backend", "role"), "bootstrap"),
        (("cases", 0, "backend", "pid"), True),
        (("cases", 0, "status"), "failed"),
        (("cases", 1, "stop_ns"), 8_999_999_999),
        (("cases", 1, "absent_ns"), 14_000_000_001),
        (("cases", 1, "ready_ns"), 9_000_000_000),
        (("cases", 1, "start_ns"), 0),
    ],
)
def test_receipt_refuses_invented_or_late_success(identity, receipt, path, value):
    changed = copy.deepcopy(receipt)
    current = changed
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] = value
    with pytest.raises(OwnershipEvidenceError) as caught:
        encode_receipt(changed, identity)
    assert str(caught.value) == "invalid_ownership_evidence"
    assert "private" not in str(caught.value)


def test_failure_cannot_be_promoted_by_cleanup(identity, receipt):
    receipt["status"] = "failed"
    receipt["failure"] = "observer_unknown"
    receipt["cases"][1]["status"] = "failed"
    receipt["cases"][1]["absent_ns"] = None
    assert decode_receipt(encode_receipt(receipt, identity), identity) == receipt
    receipt["status"] = "passed"
    with pytest.raises(OwnershipEvidenceError):
        encode_receipt(receipt, identity)


def test_failed_h_requires_skipped_s(identity, receipt):
    receipt["status"] = "failed"
    receipt["failure"] = "case_deadline"
    receipt["cases"][0]["status"] = "failed"
    with pytest.raises(OwnershipEvidenceError):
        encode_receipt(receipt, identity)
    receipt["cases"][1] = {
        "name": "S",
        "status": "skipped",
        "backend": None,
        "process": None,
        **dict.fromkeys(["start_ns", "ready_ns", "stop_ns", "reaped_ns", "absent_ns"]),
        **dict.fromkeys(["read_only", "clean_session", "same_backend"], False),
    }
    encode_receipt(receipt, identity)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b'{"x":1.2}',
        b'{"x":12345678901234567890}',
        b"[]",
        b"\xff",
        b"{" * 16385,
    ],
)
def test_decode_refuses_unsafe_json_without_echo(identity, raw):
    with pytest.raises(OwnershipEvidenceError):
        decode_receipt(raw, identity)


def test_frame_closed_shape_and_prefix(identity):
    assert decode_frame(wire(frame(identity)), identity)["event"] == "GO"
    for raw in (b"", wire(frame(identity))[:-1], wire(frame(identity)) + b"x", b"x" * 4097):
        with pytest.raises(OwnershipEvidenceError):
            decode_frame(raw, identity)


@pytest.mark.parametrize(
    "change",
    [
        {"sender": "child"},
        {"case": "H"},
        {"sequence": True},
        {"sequence": 521},
        {"payload": {"url": "private"}},
        {"event": "DISPATCH"},
    ],
)
def test_frame_refuses_wrong_sender_stage_or_open_payload(identity, change):
    value = frame(identity)
    value.update(change)
    with pytest.raises(OwnershipEvidenceError):
        decode_frame(wire(value), identity)


def test_readonly_backend_frame(identity):
    value = frame(
        identity,
        "READY",
        "child",
        "H",
        {
            "backend": backend(identity),
            "read_only": True,
            "clean_session": True,
            "same_backend": True,
        },
    )
    assert decode_frame(wire(value), identity) == value
    value["payload"]["read_only"] = False
    with pytest.raises(OwnershipEvidenceError):
        decode_frame(wire(value), identity)


def test_fake_clock_gate_h_then_s_and_observer_close():
    gate = MeasurementGate(0)
    gate.reserve(1)
    gate.go(2)
    assert gate.admit("H", 3) == 8_000_000_003
    gate.finish("H", True, 4)
    assert gate.admit("S", 5) == 8_000_000_005
    gate.finish("S", True, 8_000_000_006)
    gate.close_observer(8_000_000_007)
    with pytest.raises(OwnershipEvidenceError):
        gate.admit("H", 8_000_000_008)


@pytest.mark.parametrize(
    "scenario",
    [
        "no_reserve",
        "late_reserve",
        "late_go",
        "duplicate_go",
        "s_first",
        "h_late",
        "s_after_h_failure",
        "clock_backwards",
        "observer_late",
    ],
)
def test_fake_gate_refuses_deadline_or_order_violations(scenario):
    gate = MeasurementGate(0)
    with pytest.raises(OwnershipEvidenceError):
        if scenario == "no_reserve":
            gate.go(1)
        if scenario == "late_reserve":
            gate.reserve(65_000_000_001)
        gate.reserve(1)
        gate.go(65_000_000_001 if scenario == "late_go" else 2)
        if scenario == "duplicate_go":
            gate.go(3)
        if scenario == "clock_backwards":
            gate.admit("H", 1)
        gate.admit("S" if scenario == "s_first" else "H", 3)
        gate.finish(
            "H", scenario != "s_after_h_failure", 8_000_000_004 if scenario == "h_late" else 4
        )
        gate.admit("S", 5)
        gate.finish("S", True, 8_000_000_006)
        gate.close_observer(26_000_000_003)
    with pytest.raises(OwnershipEvidenceError):
        gate.admit("H", 30_000_000_000)


def test_stream_replay_wrong_owner_and_failed_stream_refuse(identity):
    from scripts.ci.quote_ownership_evidence import FrameStream

    stream = FrameStream(identity, "host", "setup")
    message = wire(frame(identity))
    stream.accept(message)
    with pytest.raises(OwnershipEvidenceError):
        stream.accept(message)
    later = frame(identity)
    later["sequence"] = 2
    with pytest.raises(OwnershipEvidenceError):
        stream.accept(wire(later))
    with pytest.raises(OwnershipEvidenceError):
        FrameStream(identity, "observer", "setup").accept(message)


def test_stream_poll_bound_and_exact_backend_start(identity):
    from scripts.ci.quote_ownership_evidence import FrameStream

    expected = backend(identity)
    stream = FrameStream(identity, "observer", "H", backend=expected)
    message = frame(
        identity,
        "OBSERVED",
        "observer",
        "H",
        {"backend": expected, "present": False, "read_only": True, "transaction_idle": True},
    )
    for sequence in range(1, 257):
        message["sequence"] = sequence
        stream.accept(wire(message))
    message["sequence"] = 257
    with pytest.raises(OwnershipEvidenceError):
        stream.accept(wire(message))
    message["sequence"] = 1
    message["payload"]["backend"] = {**expected, "start_us": expected["start_us"] + 1}
    with pytest.raises(OwnershipEvidenceError):
        FrameStream(identity, "observer", "H", backend=expected).accept(wire(message))


def test_single_event_cannot_repeat_with_new_sequence(identity):
    from scripts.ci.quote_ownership_evidence import FrameStream

    stream = FrameStream(identity, "host", "setup")
    stream.accept(wire(frame(identity)))
    second = frame(identity)
    second["sequence"] = 2
    with pytest.raises(OwnershipEvidenceError):
        stream.accept(wire(second))


def test_receipt_pending_cleanup_is_not_passed(identity, receipt):
    receipt["status"] = "pending_cleanup"
    receipt["independent_cleanup"] = "pending"
    assert (
        decode_receipt(encode_receipt(receipt, identity), identity)["status"] == "pending_cleanup"
    )


def test_valid_receipt_duplicate_key_is_rejected_before_dict_construction(identity, receipt):
    raw = encode_receipt(receipt, identity)
    duplicate = raw.replace(b'"schema":1', b'"schema":1,"schema":1')
    with pytest.raises(OwnershipEvidenceError):
        decode_receipt(duplicate, identity)
    payload = wire(frame(identity))[4:].replace(b'"schema":1', b'"schema":1,"schema":1')
    with pytest.raises(OwnershipEvidenceError):
        decode_frame(len(payload).to_bytes(4, "big") + payload, identity)


def test_success_requires_different_h_and_s_backend_incarnations(identity, receipt):
    receipt["cases"][1]["backend"] = copy.deepcopy(receipt["cases"][0]["backend"])
    with pytest.raises(OwnershipEvidenceError):
        encode_receipt(receipt, identity)


def test_failure_frame_is_terminal_for_owned_stream(identity):
    from scripts.ci.quote_ownership_evidence import FrameStream

    stream = FrameStream(identity, "host", "setup")
    failure = frame(identity, "FAIL", "host", "setup", {"code": "protocol"})
    assert stream.accept(wire(failure))["event"] == "FAIL"
    go = frame(identity)
    go["sequence"] = 2
    with pytest.raises(OwnershipEvidenceError):
        stream.accept(wire(go))


def test_child_cannot_close_before_ready(identity):
    from scripts.ci.quote_ownership_evidence import FrameStream

    stream = FrameStream(identity, "child", "H")
    with pytest.raises(OwnershipEvidenceError):
        stream.accept(wire(frame(identity, "CLOSED", "child", "H")))


@pytest.mark.parametrize(
    "path,value",
    [
        (("cases", 0, "process", "pidfd_owned"), False),
        (("cases", 0, "process", "pid"), True),
        (("cases", 0, "process", "start_ticks"), 0),
        (("observer", "process", "pidfd_owned"), False),
        (("observer", "closed_ns"), 26_000_000_001),
        (("observer", "closed_ns"), 1),
        (("observer", "reaped_ns"), None),
        (("observer", "reserved_setup_ns"), 65_000_000_001),
    ],
)
def test_os_identity_and_observer_deadline_claims_fail_closed(identity, receipt, path, value):
    node = receipt
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value
    with pytest.raises(OwnershipEvidenceError):
        encode_receipt(receipt, identity)


def test_child_cannot_be_observer_or_reused_process(identity, receipt):
    receipt["cases"][0]["process"] = copy.deepcopy(receipt["observer"]["process"])
    with pytest.raises(OwnershipEvidenceError):
        encode_receipt(receipt, identity)


@pytest.mark.parametrize("comm", [b"python", b"with spaces", b"a (b) c", b"x) y) (z", b"x\ny"])
def test_proc_start_ticks_parser_handles_comm_without_retaining_it(comm):
    from scripts.ci.quote_ownership_evidence import parse_process_identity

    # Fields3..21 followed by field22; numeric zeros are merely mocked metadata.
    raw = b"123 (" + comm + b") S " + b"0 " * 18 + b"456 0 0\n"
    assert parse_process_identity(raw, 123) == {"pid": 123, "start_ticks": 456}


@pytest.mark.parametrize(
    "raw,pid",
    [
        (b"123 (name) S 0", 123),
        (b"123 (name) S " + b"0 " * 18 + b"456", 124),
        (b"123 (name) S " + b"0 " * 18 + b"0", 123),
        (b"123 (name) S " + b"0 " * 18 + b"456", True),
        (b"x" * 4097, 123),
        (b"123 name S " + b"0 " * 18 + b"456", 123),
    ],
)
def test_proc_identity_refuses_wrong_truncated_or_oversized_claim(raw, pid):
    from scripts.ci.quote_ownership_evidence import parse_process_identity

    with pytest.raises(OwnershipEvidenceError) as caught:
        parse_process_identity(raw, pid)
    assert str(caught.value) == "invalid_ownership_evidence"


def test_owner_result_is_closed_lifecycle_only_not_cleanup_receipt(identity, receipt):
    observation = {
        k: receipt[k] for k in ("failure", "setup_ns", "elapsed_ns", "observer", "cases")
    }
    observation["status"] = "observed"
    result = frame(identity, "RESULT", "owner", "teardown", observation)
    assert decode_frame(wire(result), identity)["payload"] == observation
    result["payload"]["primary_cleanup"] = "verified_absent"
    with pytest.raises(OwnershipEvidenceError):
        decode_frame(wire(result), identity)


def test_expected_identity_is_constructed_from_context_not_receipt(identity):
    from scripts.ci.quote_ownership_evidence import identity_from_environment

    env = {
        "GITHUB_SHA": identity["commit"],
        "OCWP_EXPECTED_SOURCE_SHA": identity["commit"],
        "OCWP_EXPECTED_TREE_SHA": identity["tree"],
        "OCWP_EXPECTED_WORKFLOW_ID": identity["workflow_id"],
        "GITHUB_REPOSITORY": identity["repository"],
        "GITHUB_REPOSITORY_ID": "1327018760",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_NUMBER": "1",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_RUN_ID": identity["run_id"],
        "OCWP_OWNERSHIP_NONCE": identity["nonce"],
        "OCWP_OWNERSHIP_WORKER_IMAGE_ID": identity["worker_image"],
        "OCWP_OWNERSHIP_PG_IMAGE_ID": identity["pg_image"],
    }
    assert identity_from_environment(env) == {**identity, "database": "ocwp", "role": "ocwp"}
    env["GITHUB_RUN_ATTEMPT"] = "2"
    with pytest.raises(OwnershipEvidenceError):
        identity_from_environment(env)


def test_closed_cleanup_cannot_turn_unknown_into_absence(identity):
    from scripts.ci.quote_ownership_evidence import validate_cleanup

    value = {
        "schema": 1,
        "kind": "ocwp.quote_ownership.independent_cleanup",
        "identity": identity,
        "expected_commit": identity["commit"],
        "run_id": identity["run_id"],
        "run_attempt": 1,
        "owner_manifest_present": True,
        "owner_token": identity["nonce"],
        "outcome": "verified_absent",
        "elapsed_ns": 1,
        "receipt_sha256": "f" * 64,
    }
    validate_cleanup(value, identity)
    value["owner_manifest_present"] = False
    with pytest.raises(OwnershipEvidenceError):
        validate_cleanup(value, identity)
    value.update(identity=None, owner_token=None, outcome="not_started", receipt_sha256=None)
    validate_cleanup(value, None)


def test_fixture_metadata_binds_base_and_exact_file_hashes(identity):
    from scripts.ci.quote_ownership_evidence import validate_fixture_preparation

    value = {
        "schema": 1,
        "kind": "ocwp.quote_ownership.fixture_preparation",
        "identity": identity,
        "pg_base_image": "sha256:" + "f" * 64,
        "pg_base_reference": "postgres@sha256:" + "a" * 64,
        "files": dict.fromkeys(["dockerfile", "initializer", "public_fixture"], "b" * 64),
    }
    validate_fixture_preparation(value, identity)
    value["files"]["sql"] = "private"
    with pytest.raises(OwnershipEvidenceError):
        validate_fixture_preparation(value, identity)
