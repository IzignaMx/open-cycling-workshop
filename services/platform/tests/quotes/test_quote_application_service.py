"""Tiny synthetic service cases with authorized local SQLite characterization.

SQLite is functional evidence only. These tests do not qualify HTTP, PostgreSQL,
network cancellation, hard termination or capacity.
"""

import asyncio
import json
from dataclasses import replace

import pytest
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.identity.cutover import WriteAdmission
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.quotes.models import QuoteOperationRecord
from cycling_workshop.quotes.repository import QuoteRepository
from cycling_workshop.quotes.service import QuoteDeadline, QuoteService, QuoteServiceError
from cycling_workshop.service_orders.models import ServiceOrderEventRecord, ServiceOrderRecord
from cycling_workshop.sync.models import ChangeRecord
from cycling_workshop.sync.writes import lock_writer
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_repository import counts, creation, decision, revision
from test_quote_repository import database as database
from test_quote_schema import insert
from test_quote_storage import NOW

pytestmark = pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)

GRANTS = frozenset(
    {"orders.read", "orders.write", "quotes.read", "quotes.write", "quotes.authorize"}
)


@pytest.fixture
def actors(database):
    with Session(database) as session:
        actor = session.get(UserRecord, "actor-a")
        actor.capabilities = sorted(GRANTS)
        session.commit()
    return Principal("actor-a", "a", "location-a", GRANTS)


def execute(session, principal, command, *, enabled=True, deadline=None):
    return json.loads(
        QuoteService(session, commands_enabled=enabled, now=lambda: NOW).execute(
            command,
            principal=principal,
            admission=WriteAdmission.for_fixtures(1, enabled=True),
            deadline=deadline or QuoteDeadline.start(),
        )
    )


def totals(session):
    return tuple(
        session.scalar(select(func.count()).select_from(model))
        for model in (QuoteOperationRecord, ServiceOrderEventRecord, ChangeRecord, OutboxRecord)
    )


def test_create_decide_replay_commits_one_complete_tuple(database, actors):
    with Session(database) as session:
        created = execute(session, actors, creation())
        assert created["receipt"]["effects"]["kind"] == "quote_only"
        applied = execute(session, actors, decision())
        effects = applied["receipt"]["effects"]
        assert effects["kind"] == "order_transition"
        assert effects["resulting_order_version"] == 2
        assert effects["quote_outbox_id"] != effects["order_outbox_id"]
        assert list(
            session.scalars(
                select(QuoteOperationRecord.order_effect_version).order_by(
                    QuoteOperationRecord.ordinal
                )
            )
        ) == [None, 1]
        assert applied["order"]["state"] == "AUTHORIZED"
        before = totals(session)
        session.rollback()
        replay = execute(session, actors, decision(), enabled=False)
        assert replay["delivery"] == "replayed"
        assert replay["receipt"] == applied["receipt"]
        assert totals(session) == before == (2, 1, 1, 3)


def test_false_flag_denies_new_but_preserves_exact_revision_replay(database, actors):
    with Session(database) as session:
        original = execute(session, actors, creation())
        assert execute(session, actors, creation(), enabled=False)["receipt"] == original["receipt"]
        with pytest.raises(QuoteServiceError, match="quote_commands_unavailable"):
            execute(session, actors, revision(), enabled=False)
        assert session.scalar(select(func.count()).select_from(QuoteOperationRecord)) == 1


@pytest.mark.parametrize("missing", sorted(GRANTS))
def test_replay_requires_fresh_operation_grants(database, actors, missing):
    with Session(database) as session:
        execute(session, actors, creation())
        execute(session, actors, decision())
        # quotes.write is not a decision grant; exercise revision replay for it.
        command = creation() if missing == "quotes.write" else decision()
        actor = session.get(UserRecord, "actor-a")
        actor.capabilities = sorted(GRANTS - {missing})
        session.commit()
        with pytest.raises(QuoteServiceError, match="quote_access_denied"):
            execute(session, actors, command, enabled=False)


def test_historical_quote_only_decision_replay_does_not_invent_transition(database, actors):
    with Session(database) as session:
        lock_writer(session, actors, WriteAdmission.for_fixtures(1, enabled=True))
        repository = QuoteRepository(session)
        repository.apply(creation(), recorded_at=NOW)
        repository.apply(decision(), recorded_at=NOW)
        session.commit()
        replay = execute(session, actors, decision(), enabled=False)
        assert replay["delivery"] == "replayed"
        assert replay["receipt"]["effects"]["kind"] == "quote_only"
        assert replay["order"]["state"] == "DIAGNOSIS"
        assert totals(session) == (2, 0, 0, 2)
        assert list(session.scalars(select(QuoteOperationRecord.order_effect_version))) == [
            None,
            None,
        ]


def test_response_failure_rolls_back_all_decision_effects(database, actors, monkeypatch):
    with Session(database) as session:
        execute(session, actors, creation())
        before = totals(session)
        session.rollback()

        def fail(_):
            raise ValueError("synthetic projection refusal")

        monkeypatch.setattr("cycling_workshop.quotes.service.encode_command_response", fail)
        with pytest.raises(QuoteServiceError, match="quote_integrity_failed"):
            execute(session, actors, decision())
        assert totals(session) == before
        assert session.get(ServiceOrderRecord, "order-a").state == "DIAGNOSIS"


def test_commit_ack_loss_is_unknown_and_same_identity_replays(database, actors, monkeypatch):
    with Session(database) as session:
        execute(session, actors, creation())
        original = session.commit

        def committed_then_lost():
            original()
            raise OSError("synthetic acknowledgment loss")

        monkeypatch.setattr(session, "commit", committed_then_lost)
        with pytest.raises(QuoteServiceError) as error:
            execute(session, actors, decision())
        assert error.value.code == "quote_request_unavailable"
        assert error.value.outcome_unknown is True
    with Session(database) as session:
        assert execute(session, actors, decision(), enabled=False)["delivery"] == "replayed"
        assert totals(session) == (2, 1, 1, 3)


def test_expired_deadline_refuses_before_writer_or_effects(database, actors, monkeypatch):
    with Session(database) as session:

        def forbidden(*_, **__):
            pytest.fail("expired request reached writer")

        monkeypatch.setattr("cycling_workshop.quotes.service.lock_writer", forbidden)
        deadline = QuoteDeadline(expires_at=1.0, clock=lambda: 2.0)
        with pytest.raises(QuoteServiceError, match="quote_request_unavailable"):
            execute(session, actors, creation(), deadline=deadline)
        assert totals(session) == (0, 0, 0, 0)


def test_foreign_actor_and_noncustomer_decision_are_refused(database, actors):
    with Session(database) as session:
        with pytest.raises(QuoteServiceError, match="quote_access_denied"):
            execute(session, replace(actors, organization_id="b"), creation())
        execute(session, actors, creation())
        command = decision(evidence=replace(decision().command.evidence, party_id="customer-b"))
        with pytest.raises(QuoteServiceError, match="quote_conflict"):
            execute(session, actors, command)
        assert totals(session) == (1, 0, 0, 1)


@pytest.mark.parametrize(
    "field,table,details",
    [
        ("customer_id", "customers", {"display_name": "Synthetic"}),
        ("bicycle_id", "bicycles", {"customer_id": "customer-a", "brand": "Synthetic"}),
    ],
)
def test_nul_order_reference_refuses_before_text_hydration(
    database, actors, monkeypatch, field, table, details
):
    reference_id = "reference\x00a"
    column = getattr(ServiceOrderRecord, field)
    with database.begin() as connection:
        insert(
            connection,
            table,
            id=reference_id,
            organization_id="a",
            location_id="location-a",
            created_at=NOW,
            updated_at=NOW,
            **details,
        )
        connection.execute(
            update(ServiceOrderRecord)
            .where(ServiceOrderRecord.id == "order-a")
            .values({field: reference_id})
        )
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        assert (
            connection.scalar(select(column).where(ServiceOrderRecord.id == "order-a"))
            == reference_id
        )

    def forbidden(*_args, **_kwargs):
        pytest.fail("NUL scalar order metadata reached Text hydration")

    monkeypatch.setattr(QuoteRepository, "_load_bounded_order", forbidden)
    with Session(database) as session:
        with pytest.raises(QuoteServiceError) as error:
            execute(session, actors, creation())
        assert error.value.code == "quote_integrity_failed"
        assert error.value.outcome_unknown is False
    with Session(database) as session:
        assert counts(session) == (0, 0, 0, 0)
        assert totals(session) == (0, 0, 0, 0)
        assert (
            session.scalar(select(column).where(ServiceOrderRecord.id == "order-a")) == reference_id
        )


def test_service_does_not_take_ownership_of_existing_transaction(database, actors):
    with Session(database) as session:
        order = session.get(ServiceOrderRecord, "order-a")
        order.diagnosis = "Unrelated pending caller change"
        with pytest.raises(QuoteServiceError, match="quote_request_unavailable"):
            execute(session, actors, creation())
        assert order in session.dirty
        assert session.in_transaction()
        session.rollback()


def test_replay_retains_receipt_after_order_cancellation(database, actors):
    from cycling_workshop.service_orders.repository import SqlAlchemyServiceOrderRepository

    with Session(database) as session:
        execute(session, actors, creation())
        original = execute(session, actors, decision())
        repository = SqlAlchemyServiceOrderRepository(session)
        order = repository.get(order_id="order-a", organization_id="a")
        transition = order.transition("cancel", actor_id="actor-a", now=NOW)
        repository.save(transition.order)
        repository.add_event(transition.event)
        session.commit()
        replay = execute(session, actors, decision(), enabled=False)
        assert replay["receipt"] == original["receipt"]
        assert replay["order"]["state"] == "CANCELLED"
        assert replay["order"]["version"] == 3


def test_expiry_after_order_effect_flush_rolls_back_outer_transaction(
    database, actors, monkeypatch
):
    from cycling_workshop.quotes import service

    with Session(database) as session:
        execute(session, actors, creation())
        before = totals(session)
        session.rollback()
        clock = [0.0]
        original = service._append_prepared_order_change

        def append_then_expire(*args, **kwargs):
            result = original(*args, **kwargs)
            clock[0] = 9.0
            return result

        monkeypatch.setattr(service, "_append_prepared_order_change", append_then_expire)
        with pytest.raises(QuoteServiceError, match="quote_request_unavailable"):
            execute(
                session,
                actors,
                decision(),
                deadline=QuoteDeadline(expires_at=8.0, clock=lambda: clock[0]),
            )
        assert clock == [9.0]
        assert totals(session) == before
        assert session.get(ServiceOrderRecord, "order-a").version == 1


def test_create_revise_initial_and_revision_replays(database, actors):
    from test_quote_storage import uid

    with Session(database) as session:
        first = execute(session, actors, creation())
        second = execute(session, actors, revision())
        execute(
            session,
            actors,
            decision(
                quote_id=uid(2), quote_version=2, expected_head_id=uid(2), expected_head_version=2
            ),
        )
        assert execute(session, actors, creation(), enabled=False)["receipt"] == first["receipt"]
        assert execute(session, actors, revision(), enabled=False)["receipt"] == second["receipt"]
        assert totals(session) == (3, 1, 1, 4)


def test_failed_rollback_and_invalidation_preserve_closed_cleanup_state(
    database, actors, monkeypatch
):
    with Session(database) as session:

        def fail():
            raise OSError("synthetic cleanup failure")

        monkeypatch.setattr(session, "rollback", fail)
        monkeypatch.setattr(session, "invalidate", fail)
        with pytest.raises(QuoteServiceError) as error:
            execute(session, actors, creation(), enabled=False)
        assert error.value.code == "quote_commands_unavailable"
        assert error.value.cleanup_unverified is True
        assert session.info["ocwp_quote_unusable"] is True
        with pytest.raises(QuoteServiceError, match="quote_request_unavailable"):
            execute(session, actors, creation())


def test_hook_cleanup_failure_never_replaces_unknown_commit(database, actors, monkeypatch):
    with Session(database) as session:
        execute(session, actors, creation())
        commit = session.commit

        def lose_ack():
            commit()
            raise OSError("synthetic acknowledgment loss")

        def lose_hook(*_):
            raise OSError("synthetic hook cleanup failure")

        monkeypatch.setattr(session, "commit", lose_ack)
        monkeypatch.setattr(QuoteService, "_release_hook", staticmethod(lose_hook))
        with pytest.raises(QuoteServiceError) as error:
            execute(session, actors, decision())
        assert error.value.code == "quote_request_unavailable"
        assert error.value.outcome_unknown is True
        assert error.value.cleanup_unverified is True


def test_driver_budget_failure_invalidates_instead_of_returning_connection(
    database, actors, monkeypatch
):
    from cycling_workshop.quotes import service

    with Session(database) as session:
        invalidated = []
        invalidate = session.invalidate

        def fail_projection(_):
            raise service._QuoteDriverUnavailable()

        def capture_invalidation():
            invalidated.append(True)
            invalidate()

        monkeypatch.setattr(service, "encode_command_response", fail_projection)
        monkeypatch.setattr(session, "invalidate", capture_invalidation)
        with pytest.raises(QuoteServiceError, match="quote_request_unavailable"):
            execute(session, actors, creation())
        assert invalidated == [True]
        assert session.info["ocwp_quote_unusable"] is True


def _capture_encoded_response(monkeypatch):
    from cycling_workshop.quotes import service

    original = service.encode_command_response
    captured = []

    def encode(response):
        encoded = original(response)
        captured.append(json.loads(encoded))
        return encoded

    monkeypatch.setattr(service, "encode_command_response", encode)
    return captured


def test_cancellation_before_commit_preserves_identity_and_rolls_back(
    database, actors, monkeypatch
):
    from cycling_workshop.quotes import service

    cancellation = asyncio.CancelledError("synthetic before-commit cancellation")
    with Session(database) as session:
        execute(session, actors, creation())
        before = totals(session), counts(session)
        session.rollback()
        cleanup = []
        rollback = session.rollback
        release = QuoteService._release_hook

        def cancel_after_writes(_):
            assert totals(session) == (2, 1, 1, 3)
            assert session.get(ServiceOrderRecord, "order-a").version == 2
            raise cancellation

        def forbidden_commit():
            pytest.fail("cancelled command reached commit")

        def observed_rollback():
            cleanup.append("rollback")
            rollback()

        def observed_release(*args):
            cleanup.append("hook")
            release(*args)

        with monkeypatch.context() as patch:
            patch.setattr(service, "encode_command_response", cancel_after_writes)
            patch.setattr(session, "commit", forbidden_commit)
            patch.setattr(session, "rollback", observed_rollback)
            patch.setattr(QuoteService, "_release_hook", staticmethod(observed_release))
            with pytest.raises(asyncio.CancelledError) as error:
                execute(session, actors, decision())
            assert error.value is cancellation
            assert cleanup == ["rollback", "hook"]
            assert not session.in_transaction()
            assert session.info.get("ocwp_quote_unusable") is not True
        assert (totals(session), counts(session)) == before
        order = session.get(ServiceOrderRecord, "order-a")
        assert (order.state, order.version) == ("DIAGNOSIS", 1)
    with Session(database) as session:
        assert (totals(session), counts(session)) == before


def test_cancellation_after_actual_commit_preserves_identity_and_exact_replay(
    database, actors, monkeypatch
):
    cancellation = asyncio.CancelledError("synthetic after-commit cancellation")
    with Session(database) as session:
        execute(session, actors, creation())
        commit = session.commit
        committed = []
        with monkeypatch.context() as patch:
            captured = _capture_encoded_response(patch)

            def commit_then_cancel():
                commit()
                committed.append(True)
                raise cancellation

            patch.setattr(session, "commit", commit_then_cancel)
            with pytest.raises(asyncio.CancelledError) as error:
                execute(session, actors, decision())
            assert error.value is cancellation
            assert committed == [True] and len(captured) == 1
            assert not session.in_transaction()
    with Session(database) as session:
        replay = execute(session, actors, decision(), enabled=False)
        assert replay["delivery"] == "replayed"
        assert replay["receipt"] == captured[0]["receipt"]
        assert replay["order"]["state"] == "AUTHORIZED"
        assert replay["order"]["version"] == 2
        assert totals(session) == (2, 1, 1, 3)


def test_successful_commit_returning_after_deadline_is_unknown_and_replays_exactly(
    database, actors, monkeypatch
):
    clock = [0.0]
    with Session(database) as session:
        execute(session, actors, creation())
        commit = session.commit
        with monkeypatch.context() as patch:
            captured = _capture_encoded_response(patch)

            def commit_then_expire():
                commit()
                clock[0] = 9.0

            patch.setattr(session, "commit", commit_then_expire)
            with pytest.raises(QuoteServiceError) as error:
                execute(
                    session,
                    actors,
                    decision(),
                    deadline=QuoteDeadline(expires_at=8.0, clock=lambda: clock[0]),
                )
            assert error.value.code == "quote_request_unavailable"
            assert error.value.outcome_unknown is True
            assert error.value.cleanup_unverified is False
            assert clock == [9.0] and len(captured) == 1
            assert not session.in_transaction()
            assert session.info.get("ocwp_quote_unusable") is not True
    with Session(database) as session:
        replay = execute(session, actors, decision(), enabled=False)
        assert replay["delivery"] == "replayed"
        assert replay["receipt"] == captured[0]["receipt"]
        assert totals(session) == (2, 1, 1, 3)


def test_hook_failure_alone_after_commit_marks_unusable_and_replays_exactly(
    database, actors, monkeypatch
):
    with Session(database) as session:
        execute(session, actors, creation())
        commit = session.commit
        committed = []
        with monkeypatch.context() as patch:
            captured = _capture_encoded_response(patch)

            def observed_commit():
                commit()
                committed.append(True)

            def fail_hook(*_):
                assert committed == [True]
                raise OSError("synthetic hook removal failure only")

            patch.setattr(session, "commit", observed_commit)
            patch.setattr(QuoteService, "_release_hook", staticmethod(fail_hook))
            with pytest.raises(QuoteServiceError) as error:
                execute(session, actors, decision())
            assert error.value.code == "quote_request_unavailable"
            assert error.value.outcome_unknown is True
            assert error.value.cleanup_unverified is True
            assert session.info["ocwp_quote_unusable"] is True
            assert not session.in_transaction()
            assert committed == [True] and len(captured) == 1
        with pytest.raises(QuoteServiceError, match="quote_request_unavailable"):
            execute(session, actors, decision())
    with Session(database) as session:
        replay = execute(session, actors, decision(), enabled=False)
        assert replay["delivery"] == "replayed"
        assert replay["receipt"] == captured[0]["receipt"]
        assert totals(session) == (2, 1, 1, 3)


@pytest.mark.parametrize(
    "original,rollback_fault,invalidate_fault,release_fault,winner",
    [
        ("ordinary", "first", None, None, "first"),
        ("driver", None, "first", None, "first"),
        ("ordinary", "cleanup_error", "first", None, "first"),
        ("first", "second", None, None, "first"),
        ("first", "cleanup_error", "second", None, "first"),
        ("first", None, None, "second", "first"),
        ("ordinary", "first", "second", None, "first"),
        ("ordinary", None, "second", "first", "first"),
        ("first", "first", None, None, "first"),
        ("first", "cleanup_error", None, None, "first"),
        ("ordinary", "first", "second", "second", "first"),
        ("ordinary", "first", "first", None, "first"),
    ],
)
def test_cleanup_control_flow_precedence(
    database, actors, monkeypatch, original, rollback_fault, invalidate_fault, release_fault, winner
):
    from cycling_workshop.quotes import service

    faults = {
        "ordinary": ValueError("private ordinary canary"),
        "cleanup_error": OSError("private cleanup canary"),
        "driver": service._QuoteDriverUnavailable(),
        "first": asyncio.CancelledError("private first canary"),
        "second": asyncio.CancelledError("private secondary canary"),
    }
    calls = []
    origin = []
    first_observed_chain = []

    def snapshot_before_secondary_cleanup():
        if origin and not first_observed_chain:
            current = faults[winner].__traceback__
            while current is not None:
                first_observed_chain.append(current)
                current = current.tb_next

    def first_site_marker(error):
        try:
            raise error
        except BaseException as caught:
            origin.append(caught.__traceback__)
            raise

    def secondary_site_marker(error):
        raise error

    def inject(name):
        if name is None:
            return
        error = faults[name]
        if error is faults[winner] and not origin:
            first_site_marker(error)
        else:
            secondary_site_marker(error)

    with Session(database) as session:
        candidate = QuoteService(session, commands_enabled=True, now=lambda: NOW)
        initial_attributes = dict(vars(candidate))
        initial_info = dict(session.info)
        rollback = session.rollback

        def encode(_):
            initial_info.update(session.info)
            inject(original)

        def observed_rollback():
            snapshot_before_secondary_cleanup()
            calls.append("rollback")
            inject(rollback_fault)
            rollback()

        def observed_invalidate():
            snapshot_before_secondary_cleanup()
            calls.append("invalidate")
            assert session.info["ocwp_quote_unusable"] is True
            inject(invalidate_fault)
            # No claim of backend invalidation: fixture rollback is teardown below.

        def observed_release(*_):
            snapshot_before_secondary_cleanup()
            calls.append("release")
            inject(release_fault)

        with monkeypatch.context() as patch:
            patch.setattr(service, "encode_command_response", encode)
            patch.setattr(session, "rollback", observed_rollback)
            patch.setattr(session, "invalidate", observed_invalidate)
            patch.setattr(QuoteService, "_release_hook", staticmethod(observed_release))
            patch.setattr(session, "commit", lambda: pytest.fail("unexpected commit"))
            with pytest.raises(asyncio.CancelledError) as caught:
                candidate.execute(
                    creation(),
                    principal=actors,
                    admission=WriteAdmission.for_fixtures(1, enabled=True),
                    deadline=QuoteDeadline.start(),
                )
            assert caught.value is faults[winner]
            chain = []
            current = caught.value.__traceback__
            while current is not None:
                chain.append(current)
                current = current.tb_next
            assert origin[0] in chain
            assert chain[-1] is origin[0]
            assert first_observed_chain
            assert chain[-len(first_observed_chain) :] == first_observed_chain
            assert "secondary_site_marker" not in [tb.tb_frame.f_code.co_name for tb in chain]
            expected = ["invalidate"] if original == "driver" else ["rollback"]
            if original != "driver" and rollback_fault is not None:
                expected.append("invalidate")
            expected.append("release")
            if release_fault is not None:
                expected.append("invalidate")
            assert calls == expected
            assert calls.count("rollback") <= 1 and calls.count("invalidate") <= 2
            assert calls.count("release") == 1
            assert session.info == {**initial_info, "ocwp_quote_unusable": True}
            assert vars(candidate) == initial_attributes
            before_reuse = list(calls)
            with pytest.raises(QuoteServiceError, match="quote_request_unavailable"):
                execute(session, actors, creation())
            assert calls == before_reuse
        # Explicit fixture recovery, outside asserted service cleanup lifetime.
        rollback()


@pytest.mark.parametrize("ack_loss", [False, True])
def test_committed_cleanup_control_flow_replays_exact_receipt(
    database, actors, monkeypatch, ack_loss
):
    cancellation = asyncio.CancelledError("private committed cleanup canary")
    calls = []
    with Session(database) as session:
        execute(session, actors, creation())
        commit = session.commit

        def observed_commit():
            commit()
            calls.append("commit")
            if ack_loss:
                raise OSError("private ACK loss canary")

        def observed_invalidate():
            assert session.info["ocwp_quote_unusable"] is True
            calls.append("invalidate")
            if ack_loss:
                raise cancellation

        def observed_release(*_):
            calls.append("release")
            if not ack_loss:
                raise cancellation

        with monkeypatch.context() as patch:
            captured = _capture_encoded_response(patch)
            patch.setattr(session, "commit", observed_commit)
            patch.setattr(session, "invalidate", observed_invalidate)
            patch.setattr(session, "rollback", lambda: pytest.fail("unexpected rollback"))
            patch.setattr(QuoteService, "_release_hook", staticmethod(observed_release))
            with pytest.raises(asyncio.CancelledError) as caught:
                execute(session, actors, decision())
            assert caught.value is cancellation
            assert calls == (
                ["commit", "invalidate", "release"]
                if ack_loss
                else ["commit", "release", "invalidate"]
            )
            assert session.info["ocwp_quote_unusable"] is True
            assert not session.in_transaction()
            assert len(captured) == 1
        with pytest.raises(QuoteServiceError, match="quote_request_unavailable"):
            execute(session, actors, decision())
    with Session(database) as session:
        replay = execute(session, actors, decision(), enabled=False)
        assert replay["delivery"] == "replayed"
        assert replay["receipt"] == captured[0]["receipt"]
        assert totals(session) == (2, 1, 1, 3)


@pytest.mark.parametrize("control_type", [SystemExit, KeyboardInterrupt])
def test_cleanup_control_flow_family_parity(database, actors, monkeypatch, control_type):
    from cycling_workshop.quotes import service

    first = control_type("private control-flow canary")
    second = asyncio.CancelledError("private later cancellation")
    with Session(database) as session:

        def ordinary(_):
            raise ValueError("private ordinary canary")

        def rollback():
            raise first

        def invalidate():
            assert session.info["ocwp_quote_unusable"] is True
            raise second

        with monkeypatch.context() as patch:
            patch.setattr(service, "encode_command_response", ordinary)
            patch.setattr(session, "rollback", rollback)
            patch.setattr(session, "invalidate", invalidate)
            with pytest.raises(control_type) as caught:
                execute(session, actors, creation())
            assert caught.value is first
            assert session.info["ocwp_quote_unusable"] is True
        # Fixture-only teardown, not verified service rollback.
        session.rollback()
