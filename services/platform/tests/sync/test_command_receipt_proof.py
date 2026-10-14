"""Stored proof, not the incoming protocol marker, controls receipt replay."""

from dataclasses import replace
from datetime import timedelta

import pytest
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.sync.domain import SyncApplicationContext, SyncConflict
from cycling_workshop.sync.models import ChangeRecord, MutationReceiptRecord
from cycling_workshop.sync.proof import envelope_digest
from cycling_workshop.sync.service import SyncService
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from test_sync_service import build_session, customer_create_mutation


def test_bound_receipt_cannot_be_downgraded_by_protocol_zero() -> None:
    with build_session() as session:
        mutation = customer_create_mutation()
        service = SyncService.for_fixtures(session)
        service.apply(mutation)
        receipt = session.get(MutationReceiptRecord, mutation.mutation_id)
        assert receipt is not None
        receipt.actor_id = "original-actor"
        receipt.command_digest = "0" * 64
        receipt.proof_version = 1
        session.commit()
        context = SyncApplicationContext(
            actor_id="different-actor",
            write_protocol=0,
            canonical_digest="0" * 64,
            admitted_session_id=id(session),
        )
        with pytest.raises(SyncConflict) as caught:
            service.apply(mutation, context=context)
        assert caught.value.error_code == "receipt_proof_conflict"


def test_protocol_one_does_not_claim_authorship_for_legacy_receipt() -> None:
    with build_session() as session:
        mutation = customer_create_mutation()
        service = SyncService.for_fixtures(session)
        service.apply(mutation)
        session.commit()
        context = SyncApplicationContext(
            actor_id="actor",
            write_protocol=1,
            canonical_digest="0" * 64,
            admitted_session_id=id(session),
        )
        with pytest.raises(SyncConflict) as caught:
            service.apply(mutation, context=context)
        assert caught.value.error_code == "legacy_receipt_unverified"


def _context(mutation, *, actor="actor", protocol=1, digest=True):
    return SyncApplicationContext(
        actor_id=actor,
        write_protocol=protocol,
        canonical_digest=envelope_digest(mutation) if digest else None,
    )


def _history(session):
    return {
        model.__tablename__: [
            dict(row) for row in session.execute(select(model.__table__)).mappings()
        ]
        for model in (CustomerRecord, ChangeRecord, OutboxRecord, MutationReceiptRecord)
    }


@pytest.mark.parametrize("protocol", [0, 1])
def test_bound_exact_replay_preserves_every_existing_column_and_effect(protocol: int) -> None:
    with build_session() as session:
        mutation = customer_create_mutation()
        service = SyncService.for_fixtures(session)
        first = service.apply(mutation, context=_context(mutation))
        session.commit()
        before = _history(session)
        replay = service.apply(mutation, context=_context(mutation, protocol=protocol))
        session.commit()
        assert replay == first
        assert _history(session) == before
        receipt = session.get(MutationReceiptRecord, mutation.mutation_id)
        assert receipt is not None
        assert (receipt.actor_id, receipt.command_digest, receipt.proof_version) == (
            "actor",
            envelope_digest(mutation),
            1,
        )


@pytest.mark.parametrize("protocol", [0, 1])
@pytest.mark.parametrize(
    "change",
    ["actor", "payload", "ignored", "base", "time", "location", "entity", "type", "operation"],
)
def test_bound_changed_actor_or_complete_command_is_typed_conflict_without_effects(
    protocol: int, change: str
) -> None:
    with build_session() as session:
        mutation = customer_create_mutation()
        service = SyncService.for_fixtures(session)
        service.apply(mutation, context=_context(mutation))
        session.commit()
        before = _history(session)
        changes = {
            "actor": {},
            "payload": {"payload": {"display_name": "Different"}},
            "ignored": {"payload": {**mutation.payload, "otherwise_ignored": True}},
            "base": {"base_version": 99},
            "time": {"occurred_at": mutation.occurred_at + timedelta(microseconds=1)},
            "location": {"location_id": "loc-2"},
            "entity": {"entity_id": "01929840-0000-7000-8000-000000000009"},
            "type": {"entity_type": "bicycle"},
            "operation": {"operation": "update"},
        }
        changed = replace(mutation, **changes[change])
        context = _context(
            changed, protocol=protocol, actor="other" if change == "actor" else "actor"
        )
        with pytest.raises(SyncConflict) as caught:
            service.apply(changed, context=context)
        assert caught.value.error_code == "receipt_proof_conflict"
        session.commit()
        assert _history(session) == before


@pytest.mark.parametrize("protocol", [0, 1])
def test_bound_receipt_cannot_use_pydantic_coercion_without_exact_raw_proof(protocol: int) -> None:
    with build_session() as session:
        mutation = customer_create_mutation()
        service = SyncService.for_fixtures(session)
        service.apply(mutation, context=_context(mutation))
        session.commit()
        with pytest.raises(SyncConflict) as caught:
            service.apply(mutation, context=_context(mutation, protocol=protocol, digest=False))
        assert caught.value.error_code == "receipt_integrity_conflict"


def test_missing_or_misaligned_raw_proof_prevents_new_protocol_one_effects() -> None:
    with build_session() as session:
        mutation = customer_create_mutation()
        service = SyncService.for_fixtures(session)
        other = customer_create_mutation()
        for context in (_context(mutation, digest=False), _context(other)):
            with pytest.raises(SyncConflict) as caught:
                service.apply(mutation, context=context)
            assert caught.value.error_code == "receipt_integrity_conflict"
        assert all(rows == [] for rows in _history(session).values())


@pytest.mark.parametrize("protocol", [0, 1])
@pytest.mark.parametrize(
    "corruption",
    [
        "actor_id = NULL",
        "command_digest = NULL",
        "proof_version = NULL",
        "proof_version = 2",
        "actor_id = ''",
        "command_digest = 'broken'",
        "command_digest = '" + "A" * 64 + "'",
        "status = 'unknown'",
        "entity_version = 0",
    ],
)
def test_partial_unknown_and_corrupt_stored_proofs_never_fall_back_to_legacy(
    protocol: int, corruption: str
) -> None:
    with build_session() as session:
        mutation = customer_create_mutation()
        service = SyncService.for_fixtures(session)
        service.apply(mutation, context=_context(mutation))
        session.commit()
        # Fixture-only simulation of storage/import corruption, bypassing constraints.
        session.execute(text("PRAGMA ignore_check_constraints = ON"))
        session.execute(text(f"UPDATE sync_mutation_receipts SET {corruption}"))
        session.commit()
        session.execute(text("PRAGMA ignore_check_constraints = OFF"))
        session.expire_all()
        before = _history(session)
        with pytest.raises(SyncConflict) as caught:
            service.apply(mutation, context=_context(mutation, protocol=protocol))
        assert caught.value.error_code == "receipt_integrity_conflict"
        assert _history(session) == before


@pytest.mark.parametrize(
    "change", ["actor_id = NULL", "proof_version = 2", "command_digest = '" + "G" * 64 + "'"]
)
def test_persistence_constraints_reject_partial_unknown_and_invalid_hex_proofs(change: str) -> None:
    with build_session() as session:
        mutation = customer_create_mutation()
        SyncService.for_fixtures(session).apply(mutation, context=_context(mutation))
        session.commit()
        with pytest.raises(IntegrityError):
            session.execute(text(f"UPDATE sync_mutation_receipts SET {change}"))
        session.rollback()


def test_unbound_protocol_zero_retains_legacy_behavior_and_null_metadata() -> None:
    with build_session() as session:
        mutation = customer_create_mutation()
        service = SyncService.for_fixtures(session)
        first = service.apply(mutation, context=_context(mutation, protocol=0))
        session.commit()
        before = _history(session)
        changed = replace(mutation, base_version=99, payload={"unrecognized": "legacy ignored"})
        replay = service.apply(changed, context=_context(changed, actor="other", protocol=0))
        session.commit()
        assert first == replay and _history(session) == before
        receipt = session.get(MutationReceiptRecord, mutation.mutation_id)
        assert receipt is not None
        assert (receipt.actor_id, receipt.command_digest, receipt.proof_version) == (
            None,
            None,
            None,
        )


@pytest.mark.parametrize("stored_bound", [False, True])
def test_cross_organization_id_collision_is_generic_without_disclosing_stored_proof(
    stored_bound: bool,
) -> None:
    with build_session() as session:
        mutation = customer_create_mutation()
        service = SyncService.for_fixtures(session)
        service.apply(mutation, context=_context(mutation, protocol=1 if stored_bound else 0))
        session.commit()
        changed = replace(mutation, organization_id="org-2", location_id="loc-2")
        with pytest.raises(SyncConflict) as caught:
            service.apply(changed, context=_context(changed, actor="other"))
        assert caught.value.error_code == "sync_conflict"
        assert str(caught.value) == "mutation id is unavailable for this envelope"


def test_independent_savepoints_survive_bound_command_conflict() -> None:
    with build_session() as session:
        original = customer_create_mutation()
        service = SyncService.for_fixtures(session)
        service.apply(original, context=_context(original))
        session.commit()
        changed = replace(original, payload={"display_name": "Do not apply"})
        outcomes = []
        for mutation in (customer_create_mutation(), changed, customer_create_mutation()):
            try:
                with session.begin_nested():
                    service.apply(mutation, context=_context(mutation))
                outcomes.append("applied")
            except SyncConflict as exc:
                outcomes.append(exc.error_code)
        session.commit()
        assert outcomes == ["applied", "receipt_proof_conflict", "applied"]
        assert all(len(rows) == 3 for rows in _history(session).values())


def test_normal_service_requires_transaction_owned_admission_but_fixture_path_is_explicit() -> None:
    with build_session() as session:
        mutation = customer_create_mutation()
        service = SyncService(session)
        with pytest.raises(RuntimeError, match="transaction-owned"):
            service.apply(mutation)
        context = replace(_context(mutation), admitted_session_id=id(session))
        with pytest.raises(RuntimeError, match="transaction-owned"):
            service.apply(mutation, context=context)
        with session.begin():
            with pytest.raises(RuntimeError, match="transaction-owned"):
                service.apply(mutation, context=replace(context, admitted_session_id=-1))
            with pytest.raises(RuntimeError, match="transaction-owned"):
                service.apply(mutation, context=context)
        assert all(rows == [] for rows in _history(session).values())


def test_receipt_result_contract_rejects_unknown_unbounded_error_codes() -> None:
    from cycling_workshop.sync.schemas import MutationResultResponse
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        MutationResultResponse(
            mutation_id="synthetic",
            status="conflict",
            entity_id="synthetic",
            error_code="unbounded_unknown_code",
        )


def _admit(session, *, capabilities=frozenset({"sync.push", "customers.write"}), protocol=1):
    from datetime import UTC, datetime

    from cycling_workshop.identity.cutover import WriteAdmission
    from cycling_workshop.identity.domain import Principal
    from cycling_workshop.identity.models import UserRecord
    from cycling_workshop.sync.writes import lock_writer

    if session.get(UserRecord, "actor") is None:
        session.add(
            UserRecord(
                id="actor",
                organization_id="org-1",
                location_id="loc-1",
                username="actor",
                display_name="Synthetic actor",
                password_hash="unused",
                is_active=True,
                session_version=1,
                capabilities=sorted(capabilities),
            )
        )
        session.commit()
    principal = Principal(
        "actor",
        "org-1",
        "loc-1",
        capabilities,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    # Exercise the real barrier and normal expiry checks; no fixture admission.
    admission = WriteAdmission(protocol=protocol, enabled=True, tokens=None)
    return lock_writer(session, principal, admission)


def test_real_writer_admission_permits_bound_service_application_and_savepoints() -> None:
    with build_session() as session:
        _admit(session)
        service = SyncService(session)
        for mutation in (customer_create_mutation(), customer_create_mutation()):
            with session.begin_nested():
                context = replace(_context(mutation), admitted_session_id=id(session))
                assert service.apply(mutation, context=context).status == "applied"
        session.commit()
        assert all(len(rows) == 2 for rows in _history(session).values())


@pytest.mark.parametrize("end", ["commit", "rollback"])
def test_completed_transaction_record_cannot_authorize_a_later_transaction(end: str) -> None:
    with build_session() as session:
        _admit(session)
        old_record = session.info["ocwp_write_admission"]
        getattr(session, end)()
        mutation = customer_create_mutation()
        with session.begin():
            assert session.info["ocwp_write_admission"] is old_record
            assert session.get_transaction() is not old_record[0]
            with pytest.raises(RuntimeError, match="transaction-owned"):
                SyncService(session).apply(
                    mutation,
                    context=replace(_context(mutation), admitted_session_id=id(session)),
                )
        assert all(rows == [] for rows in _history(session).values())


@pytest.mark.parametrize("mismatch", ["actor", "protocol", "organization"])
def test_admitted_service_cannot_substitute_actor_protocol_or_organization(mismatch: str) -> None:
    with build_session() as session:
        _admit(session)
        mutation = customer_create_mutation()
        context = replace(_context(mutation), admitted_session_id=id(session))
        if mismatch == "actor":
            context = replace(context, actor_id="different-actor")
        elif mismatch == "protocol":
            context = replace(context, write_protocol=0)
        else:
            mutation = replace(mutation, organization_id="org-2", location_id="loc-2")
        with pytest.raises(RuntimeError, match="transaction-owned"):
            SyncService(session).apply(mutation, context=context)
        assert all(rows == [] for rows in _history(session).values())


@pytest.mark.parametrize("denial", ["sync", "entity", "location"])
def test_real_admitted_principal_still_requires_sync_entity_and_location_authority(
    denial: str,
) -> None:
    with build_session() as session:
        capabilities = {"sync.push", "customers.write"}
        if denial == "sync":
            capabilities.remove("sync.push")
        elif denial == "entity":
            capabilities.remove("customers.write")
        _admit(session, capabilities=frozenset(capabilities))
        mutation = customer_create_mutation()
        if denial == "location":
            mutation = replace(mutation, location_id="loc-2")
        context = replace(_context(mutation), admitted_session_id=id(session))
        with pytest.raises(PermissionError):
            SyncService(session).apply(mutation, context=context)
        assert all(rows == [] for rows in _history(session).values())
