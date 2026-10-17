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
