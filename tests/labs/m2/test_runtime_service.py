"""Preparation-only service contracts; SQLite functional checks are not hosted proof."""

import json

import pytest

from tests.labs.m2.authority import LabAuthority, LabDenied
from tests.labs.m2.runtime_authority import OwnedRun
from tests.labs.m2.runtime_service import _CHECKS, functional_checks, status_payload


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
    data = json.loads(
        status_payload(run, "ready", dict.fromkeys(_CHECKS, True), cleanup=False, stage="serving")
    )
    assert data["phase"] == "ready"
    assert data["source_commit"] == "b" * 40
    assert data["checks"] == dict.fromkeys(_CHECKS, True)
    assert data["database_cleanup_complete"] is False
    assert len(status_payload(run, "preparing", {}, cleanup=False)) < 65536


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
    data = json.loads(
        status_payload(
            run, "stopped", dict.fromkeys(_CHECKS, True), cleanup=True, stage="database_cleanup"
        )
    )
    assert data.get("database_cleanup_complete") is True
    assert "cleanup_complete" not in data
    assert set(data) == {
        "schema",
        "stage",
        "nonce",
        "source_commit",
        "source_tree",
        "phase",
        "checks",
        "database_cleanup_complete",
    }


def test_progress_publishes_attempt_before_completion_and_retains_prior_checks():
    from tests.labs.m2 import runtime_service as service

    published = []
    progress = service.ApiProgress(lambda stage, checks: published.append((stage, checks)))
    progress.advance("functional_scope")
    progress.complete("scope")
    progress.advance("functional_response")
    assert published == [
        ("functional_scope", {}),
        ("functional_scope", {"scope": True}),
        ("functional_response", {"scope": True}),
    ]
    assert published[0][1] == {}, "Earlier snapshots must not alias mutable progress"


def test_schema_two_retains_attempted_stage_and_rejects_partial_ready():
    from tests.labs.m2 import runtime_service as service

    run = OwnedRun("a" * 32, "b" * 40, "c" * 40)
    partial = {"postgresql_18_4": True, "fresh_database": True, "scope": True}
    data = json.loads(
        service.status_payload(run, "failed", partial, cleanup=True, stage="functional_response")
    )
    assert data["schema"] == 2 and data["stage"] == "functional_response"
    assert data["checks"] == partial and data["database_cleanup_complete"] is True
    with pytest.raises(LabDenied):
        service.status_payload(run, "ready", partial, cleanup=False, stage="serving")


@pytest.mark.parametrize("publication_failure", ["none", "once", "persistent"])
@pytest.mark.parametrize("cleanup_failure", [False, True])
def test_failed_check_or_publication_retains_stage_and_cannot_skip_cleanup(
    monkeypatch, capsys, publication_failure, cleanup_failure
):
    from tests.labs.m2 import runtime_service as service

    run = OwnedRun("a" * 32, "b" * 40, "c" * 40)
    private_canary = "PUBLIC-TEST-PRIVATE-CANARY"
    published = []
    attempts = []

    class FakeAuthority:
        owned_run = run
        cleanup_complete = False
        database_removed = False
        close_calls = 0

        def close(self):
            self.close_calls += 1
            if cleanup_failure:
                raise RuntimeError(private_canary)
            self.cleanup_complete = self.database_removed = True

    authority = FakeAuthority()

    def publish(payload):
        value = json.loads(payload)
        attempts.append(value)
        at_failed_step = value["stage"] == "postgres_lock_timeout"
        if (publication_failure == "once" and at_failed_step and value["phase"] == "preparing") or (
            publication_failure == "persistent" and at_failed_step
        ):
            raise RuntimeError(private_canary)
        published.append(value)

    expected_checks = {}
    for stage in service.API_STAGES[: service.API_STAGES.index("postgres_lock_timeout")]:
        expected_checks.update(dict.fromkeys(service.STAGE_CHECKS[stage], True))

    def checks(_authority, progress=None):
        for stage in service.API_STAGES[: service.API_STAGES.index("postgres_lock_timeout")]:
            progress.advance(stage)
            progress.complete(*service.STAGE_CHECKS[stage])
        progress.advance("postgres_lock_timeout")
        raise RuntimeError(private_canary)

    monkeypatch.setattr(service.signal, "signal", lambda *args: None)
    monkeypatch.setattr(
        service,
        "read_private_file",
        lambda *args: json.dumps(
            {
                "schema": 1,
                "nonce": run.nonce,
                "source_commit": run.source_commit,
                "source_tree": run.source_tree,
            }
        ).encode(),
    )
    monkeypatch.setattr(service.PostgresLabAuthority, "create_owned", lambda: authority)
    monkeypatch.setattr(service, "postgres_checks", checks)
    monkeypatch.setattr(service, "_status", publish)
    assert service.main() == 1
    assert authority.close_calls == 1
    assert attempts[-1]["phase"] == "failed"
    assert attempts[-1]["stage"] == "postgres_lock_timeout"
    assert attempts[-1]["checks"] == expected_checks
    from scripts.ci.m2_lab_hosted import validate_api_projection

    validate_api_projection(
        {
            key: attempts[-1][key]
            for key in ("phase", "stage", "checks", "database_cleanup_complete")
        }
    )
    assert attempts[-1]["database_cleanup_complete"] is (not cleanup_failure)
    assert not any(item["phase"] in ("ready", "stopped") for item in published)
    if publication_failure != "persistent":
        assert published[-1] == attempts[-1]
    captured = capsys.readouterr()
    leaked = private_canary in json.dumps(attempts) + captured.out + captured.err
    assert leaked is False


@pytest.mark.parametrize("stage", ["private-canary", "", "postgres_pool_recovery/secret"])
def test_arbitrary_stage_never_serializes(stage):
    with pytest.raises(LabDenied):
        status_payload(
            OwnedRun("a" * 32, "b" * 40, "c" * 40), "failed", {}, cleanup=False, stage=stage
        )


@pytest.mark.parametrize("field", ["nonce", "source_commit", "source_tree"])
def test_invalid_producer_identity_is_rejected(field):
    values = {"nonce": "a" * 32, "source_commit": "b" * 40, "source_tree": "c" * 40}
    values[field] = "PUBLIC-PRIVATE-CANARY"
    with pytest.raises(LabDenied):
        status_payload(OwnedRun(**values), "failed", {}, cleanup=False)


def test_future_check_and_false_completion_refused():
    from tests.labs.m2 import runtime_service as service

    run = OwnedRun("a" * 32, "b" * 40, "c" * 40)
    for checks in ({"pool_recovered": True}, {"scope": False}):
        with pytest.raises(LabDenied):
            status_payload(run, "failed", checks, cleanup=False, stage="functional_scope")
    progress = service.ApiProgress()
    progress.advance("functional_scope")
    with pytest.raises(LabDenied):
        progress.complete("pool_recovered")
    assert progress.checks == {}


@pytest.mark.parametrize("stage_index", range(16))
def test_each_closed_api_prefix_is_accepted_by_actual_supervisor_validator(stage_index):
    from scripts.ci.m2_lab_hosted import validate_api_projection
    from tests.labs.m2 import runtime_service as service

    stage = service.API_STAGES[stage_index]
    before = set().union(*(service.STAGE_CHECKS[item] for item in service.API_STAGES[:stage_index]))
    for names in (before, before | service.STAGE_CHECKS[stage]):
        payload = json.loads(
            service.status_payload(
                OwnedRun("a" * 32, "b" * 40, "c" * 40),
                "failed",
                dict.fromkeys(names, True),
                cleanup=False,
                stage=stage,
            )
        )
        assert payload["schema"] == 2
        validate_api_projection(
            {key: payload[key] for key in ("phase", "stage", "checks", "database_cleanup_complete")}
        )


def test_sparse_or_partially_completed_group_is_not_a_valid_receipt():
    for stage, checks in (
        ("postgres_lock_timeout", {"scope": True}),
        ("authority_initialization", {"fresh_database": True}),
    ):
        with pytest.raises(LabDenied):
            status_payload(
                OwnedRun("a" * 32, "b" * 40, "c" * 40), "failed", checks, cleanup=False, stage=stage
            )
