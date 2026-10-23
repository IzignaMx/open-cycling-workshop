"""Pure driver-budget checks without database parametrization or fixtures."""

import pytest
from cycling_workshop.quotes.service import QuoteDeadline


def test_raw_driver_budget_failure_has_availability_category():
    import psycopg
    from cycling_workshop.quotes.service import _QuoteDriverUnavailable, _set_cursor_budgets

    class Cursor:
        def execute(self, _):
            raise psycopg.OperationalError("synthetic private driver diagnostic")

    with pytest.raises(_QuoteDriverUnavailable) as error:
        _set_cursor_budgets(Cursor(), QuoteDeadline(expires_at=8.0, clock=lambda: 0.0))
    assert str(error.value) == ""


def test_budget_first_round_trip_can_exhaust_original_deadline():
    from cycling_workshop.quotes.service import _DeadlineExpired, _set_cursor_budgets

    clock = [0.0]
    statements = []

    class Cursor:
        def execute(self, statement):
            statements.append(statement)
            clock[0] = 8.0

    with pytest.raises(_DeadlineExpired):
        _set_cursor_budgets(Cursor(), QuoteDeadline(expires_at=8.0, clock=lambda: clock[0]))
    assert statements == ["SET LOCAL lock_timeout = '2000ms'"]


def test_postgres_settings_iterates_result_pairs_and_keeps_fail_closed_validation(monkeypatch):
    from types import SimpleNamespace

    from cycling_workshop.identity.cutover import WriteAdmission
    from cycling_workshop.identity.domain import Principal
    from cycling_workshop.quotes import service
    from test_quote_repository import creation

    class Result:
        """SQLAlchemy tuples() returns itself with keys(), not a mapping."""

        def __init__(self, values):
            self.values = values
            self.key_calls = 0
            self.iterations = 0

        def keys(self):
            self.key_calls += 1
            return ("name", "setting")

        def tuples(self):
            return self

        def __iter__(self):
            self.iterations += 1
            return iter(self.values.items())

    valid = dict(transaction_timeout="8000", lock_timeout="2000", statement_timeout="5000")
    cases = (
        valid,
        {key: value for key, value in valid.items() if key != "lock_timeout"},
        valid | {"unknown": "1"},
        valid | {"lock_timeout": "0"},
        valid | {"lock_timeout": "2001"},
        valid | {"statement_timeout": "not_numeric"},
        valid | {"transaction_timeout": "0000001"},
        valid | {"transaction_timeout": "٨٠٠٠"},
    )
    principal = Principal(
        "actor-a",
        "a",
        "location-a",
        frozenset({"orders.read", "orders.write", "quotes.read", "quotes.write"}),
    )
    monkeypatch.setattr(service.event, "listen", lambda *_: None)
    monkeypatch.setattr(service.event, "remove", lambda *_: None)
    for values in cases:
        result = Result(values)
        statements, reached_writer, rolled_back = [], [], []

        def execute(statement, *, statements=statements, result=result):
            statements.append(str(statement))
            return result

        def writer(*_, reached_writer=reached_writer):
            reached_writer.append(True)
            raise service.QuoteServiceError("quote_commands_unavailable")

        connection = SimpleNamespace(
            dialect=SimpleNamespace(
                name="postgresql", driver="psycopg", server_version_info=(18, 4)
            ),
            execute=execute,
        )
        session = SimpleNamespace(
            info={},
            new=[],
            dirty=[],
            deleted=[],
            in_transaction=lambda: False,
            connection=lambda connection=connection: connection,
            rollback=lambda rolled_back=rolled_back: rolled_back.append(True),
        )
        monkeypatch.setattr(service, "lock_writer", writer)
        with pytest.raises(service.QuoteServiceError) as error:
            service.QuoteService(session, commands_enabled=True).execute(
                creation(),
                principal=principal,
                admission=WriteAdmission.for_fixtures(1, enabled=True),
                deadline=QuoteDeadline(expires_at=8.0, clock=lambda: 0.0),
            )
        accepted = values == valid
        assert reached_writer == ([True] if accepted else [])
        assert error.value.code == (
            "quote_commands_unavailable" if accepted else "quote_request_unavailable"
        )
        assert result.key_calls == 0 and result.iterations == 1
        assert len(statements) == 2
        assert statements[0] == "SET LOCAL transaction_timeout = '8000ms'"
        assert rolled_back == [True]
