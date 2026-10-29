"""Pure/mock receipt uncertainty regressions; no processes, DB or Docker."""

import copy

import pytest
from test_quote_ownership_controller import FakeHost
from test_quote_ownership_measurement import identity as identity
from test_quote_ownership_measurement import receipt as receipt

from scripts.ci.quote_ownership_evidence import (
    OwnershipEvidenceError,
    decode_receipt,
    encode_receipt,
)
from scripts.ci.quote_ownership_measurement import seal_receipt, supervise_measurement
from scripts.ci.quote_ownership_worker import WorkerRefusal


def test_unavailable_owner_observation_never_claims_skipped_or_zero(identity):
    class LostObservation(FakeHost):
        def observe(self, deadline):
            # The adapter may have advanced arbitrarily before transport refusal;
            # none of those unreturned facts are accepted by the supervisor.
            self.events.append("observe_refused")
            raise WorkerRefusal("protocol")

    host = LostObservation(identity)
    result = supervise_measurement(host, 65_000_000_000)
    assert result["schema"] == 2
    assert result["owner_observation"] == "unavailable"
    assert result["status"] == "failed"
    assert result["failure"] == "protocol"
    assert result["cases"] == [
        {"name": "H", "status": "unknown"},
        {"name": "S", "status": "unknown"},
    ]
    assert all(result[key] is None for key in ("setup_ns", "elapsed_ns", "observer", "resources"))
    assert result["primary_cleanup"] == "verified_absent"
    assert seal_receipt(result, identity, True)["status"] == "failed"


def test_accepted_owner_observation_keeps_existing_success_contract(identity):
    result = supervise_measurement(FakeHost(identity), 65_000_000_000)
    assert result["schema"] == 2
    assert result["owner_observation"] == "accepted"
    assert result["status"] == "pending_cleanup"
    assert seal_receipt(result, identity, True)["status"] == "passed"


def test_legacy_receipt_decodes_but_cannot_be_sealed_as_fresh(identity, receipt):
    raw = encode_receipt(receipt, identity)
    assert decode_receipt(raw, identity) == receipt
    with pytest.raises((OwnershipEvidenceError, WorkerRefusal)):
        seal_receipt(receipt, identity, True)


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "passed"),
        ("status", "pending_cleanup"),
        ("setup_ns", 0),
        ("elapsed_ns", 0),
        ("observer", {}),
        ("resources", {}),
        ("owner_observation", "maybe"),
    ],
)
def test_unavailable_shape_rejects_false_precision_or_success(identity, field, value):
    report = {
        "schema": 2,
        "kind": "ocwp.quote_ownership.receipt",
        "identity": identity,
        "status": "failed",
        "failure": "protocol",
        "owner_observation": "unavailable",
        "setup_ns": None,
        "elapsed_ns": None,
        "observer": None,
        "resources": None,
        "cases": [{"name": "H", "status": "unknown"}, {"name": "S", "status": "unknown"}],
        "primary_cleanup": "verified_absent",
        "independent_cleanup": "pending",
    }
    assert decode_receipt(encode_receipt(report, identity), identity) == report
    changed = copy.deepcopy(report)
    changed[field] = value
    with pytest.raises(OwnershipEvidenceError):
        encode_receipt(changed, identity)


def prego_host(identity, monkeypatch, *, change=None, exit_code=1, late=False):
    """Concrete host receive uses real closed codec over in-memory framed bytes."""
    import json
    from types import SimpleNamespace

    from test_quote_ownership_worker import FakeRuntime

    from scripts.ci import quote_ownership_measurement as controller
    from scripts.ci.quote_ownership_worker import PipeChannel, run_owner

    owner = FakeRuntime()

    def refuse(deadline):
        raise WorkerRefusal("role_unverified")

    owner.reserve = refuse
    result = run_owner(owner, identity, 65_000_000_000)
    frame = {
        "schema": 1,
        "kind": "ocwp.ownership.frame",
        "identity": identity,
        "sender": "owner",
        "case": "teardown",
        "sequence": 1,
        "event": "RESULT",
        "payload": result,
    }
    if change:
        change(frame)
    body = json.dumps(frame, separators=(",", ":")).encode()
    wire = bytearray(len(body).to_bytes(4, "big") + body)
    sent = []

    class MemoryChannel(PipeChannel):
        def __init__(self, read_fd, write_fd, identity, sender):
            self.identity, self.sender = identity, sender
            self.sent, self.streams = {}, {}
            self.clock = lambda: 0

        def _transfer(self, data, count, deadline):
            if data is not None:
                sent.append(data)
                return b""
            chunk = bytes(wire[:count])
            del wire[:count]
            return chunk

    runtime = object.__new__(controller.HostRuntime)
    runtime.expected = identity
    runtime.containers = {"worker": "a" * 64}
    runtime.resources = {
        "worker_peak_bytes": 100,
        "pg_peak_bytes": 200,
        "worker_processes": 3,
        "pg_processes": 4,
        "pressure_events": 0,
    }
    runtime.sample = lambda deadline: None
    clock = [0]
    runtime.now = lambda: clock[0]
    child = SimpleNamespace(
        stdin=SimpleNamespace(fileno=lambda: 11),
        stdout=SimpleNamespace(fileno=lambda: 12),
        returncode=exit_code,
    )

    def wait(timeout):
        if late:
            clock[0] = 65_000_000_000

    child.wait = wait
    monkeypatch.setattr(controller.subprocess, "Popen", lambda *args, **kwargs: child)
    monkeypatch.setattr(controller, "PipeChannel", MemoryChannel)
    return runtime, sent, result


def test_valid_failed_result_before_reserved_preserves_failure_without_go(identity, monkeypatch):
    runtime, sent, expected = prego_host(identity, monkeypatch)
    observation, resources = runtime.observe(65_000_000_000)
    assert observation == expected
    assert observation["failure"] == "role_unverified"
    assert sent == []
    assert resources == runtime.resources


@pytest.mark.parametrize(
    "fault", ["identity", "sequence", "success", "elapsed", "started", "late_reap", "exit_code"]
)
def test_early_result_cannot_bypass_identity_phase_or_original_deadline(
    identity, monkeypatch, fault
):
    def change(frame):
        if fault == "identity":
            frame["identity"] = {**identity, "nonce": "f" * 32}
        elif fault == "sequence":
            frame["sequence"] = 2
        elif fault == "success":
            frame["payload"]["status"] = "observed"
        elif fault == "elapsed":
            frame["payload"]["elapsed_ns"] = 1
        elif fault == "started":
            frame["payload"]["cases"][0].update(status="failed", start_ns=0)

    runtime, sent, _ = prego_host(
        identity,
        monkeypatch,
        change=change,
        exit_code=0 if fault == "exit_code" else 1,
        late=fault == "late_reap",
    )
    with pytest.raises((WorkerRefusal, OwnershipEvidenceError)):
        runtime.observe(65_000_000_000)
    assert sent == []


def test_transport_loss_after_actual_host_go_is_explicitly_unknown(identity, monkeypatch):
    from scripts.ci.quote_ownership_evidence import decode_frame

    def reserved(frame):
        frame.update(
            case="setup", event="RESERVED", payload={"read_only": True, "transaction_idle": True}
        )

    runtime, sent, _ = prego_host(identity, monkeypatch, change=reserved)
    runtime.source = lambda deadline: None
    runtime.setup = lambda deadline: None
    runtime.cleanup = lambda deadline: True
    runtime.save = lambda report: None
    report = supervise_measurement(runtime, 65_000_000_000)
    assert len(sent) == 1
    assert decode_frame(sent[0], identity)["event"] == "GO"
    assert report["owner_observation"] == "unavailable"
    assert report["cases"] == [
        {"name": "H", "status": "unknown"},
        {"name": "S", "status": "unknown"},
    ]
    assert report["observer"] is None
    assert report["setup_ns"] is None and report["elapsed_ns"] is None


@pytest.mark.parametrize("status", ["passed", "failed"])
def test_current_save_and_stage_refuse_legacy_even_after_cleanup(
    identity, receipt, monkeypatch, status
):
    import json

    from test_quote_ownership_actions_adapter import environment

    from scripts.ci import quote_ownership_measurement as controller
    from scripts.ci import quote_ownership_staging as staging
    from scripts.ci.quote_ownership_evidence import identity_from_environment

    env = environment() | dict(
        OCWP_OWNERSHIP_WORKER_IMAGE_ID="sha256:" + "c" * 64,
        OCWP_OWNERSHIP_PG_IMAGE_ID="sha256:" + "d" * 64,
        OCWP_OWNERSHIP_NONCE="e" * 32,
    )
    expected = identity_from_environment(env)
    receipt["identity"] = expected
    for case in receipt["cases"]:
        case["backend"].update(database=expected["database"], role=expected["role"])
    if status == "failed":
        receipt.update(status="failed", failure="protocol")
    # Historical parser retains bytes but current publication boundaries reject.
    raw = encode_receipt(receipt, expected)
    assert decode_receipt(raw, expected)["schema"] == 1
    runtime = object.__new__(controller.HostRuntime)
    runtime.expected = expected
    runtime.evidence = None
    writes = []
    monkeypatch.setattr(controller, "_write_closed", lambda *args: writes.append(args))
    with pytest.raises(OwnershipEvidenceError):
        runtime.save(receipt)
    assert writes == []
    with pytest.raises(OwnershipEvidenceError):
        staging.validators_for_environment(env)["receipt.json"](json.dumps(receipt).encode())


@pytest.mark.parametrize("change", ["extra_case_key", "skipped", "wrong_order", "extra_top_key"])
def test_unavailable_closed_shape_cannot_smuggle_execution_claims(identity, change):
    host = FakeHost(identity, source_fail=True)
    report = supervise_measurement(host, 65_000_000_000)
    assert report["owner_observation"] == "unavailable"
    if change == "extra_case_key":
        report["cases"][0]["read_only"] = False
    elif change == "skipped":
        report["cases"][0]["status"] = "skipped"
    elif change == "wrong_order":
        report["cases"].reverse()
    else:
        report["actually_not_started"] = True
    with pytest.raises(OwnershipEvidenceError):
        encode_receipt(report, identity)


def test_early_failed_result_retains_valid_partial_observer_setup(identity, monkeypatch):
    def partial(frame):
        frame["payload"]["observer"].update(
            reserved=True,
            read_only=True,
            transaction_idle=True,
            process={"pid": 99, "start_ticks": 100, "pidfd_owned": True},
            reserved_setup_ns=0,
        )

    runtime, sent, _ = prego_host(identity, monkeypatch, change=partial)
    observation, _ = runtime.observe(65_000_000_000)
    assert observation["observer"]["reserved"] is True
    assert observation["observer"]["process"]["pid"] == 99
    assert sent == []
