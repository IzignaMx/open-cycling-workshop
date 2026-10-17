"""Prepared tiny synthetic service cases; never executed in the authoring host.

SQLite is functional evidence only when this selection is later authorized in
a contained venue. These tests do not qualify HTTP, PostgreSQL or capacity.
"""

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
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_repository import creation, decision, revision
from test_quote_repository import database as database
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
        original = service.append_change

        def append_then_expire(*args, **kwargs):
            result = original(*args, **kwargs)
            clock[0] = 9.0
            return result

        monkeypatch.setattr(service, "append_change", append_then_expire)
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
