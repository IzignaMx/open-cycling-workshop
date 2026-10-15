"""Local unit evidence for fail-closed budgets; PostgreSQL proof is separate."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from cycling_workshop.api.errors import ApiError
from cycling_workshop.inventory.read_guard import _cleanup, set_read_budgets
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session


def mock_session(dialect: str = "postgresql", version: tuple[int, ...] = (18, 4)) -> MagicMock:
    session = MagicMock(spec=Session)
    session.connection.return_value.dialect.name = dialect
    session.connection.return_value.dialect.server_version_info = version
    return session


def test_all_budgets_are_transaction_local_before_any_business_query() -> None:
    session = mock_session()
    set_read_budgets(session)
    assert [str(call.args[0]) for call in session.execute.call_args_list] == [
        "SET LOCAL transaction_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
        "SET LOCAL statement_timeout = '5s'",
    ]
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "dialect,version",
    [("postgresql", (17, 7)), ("postgresql", (19, 0)), ("mysql", (18, 0)), ("postgresql", ())],
)
def test_unsupported_database_cannot_silently_drop_budgets(
    dialect: str, version: tuple[int, ...]
) -> None:
    session = mock_session(dialect, version)
    with pytest.raises(ApiError) as failure:
        set_read_budgets(session)
    assert (failure.value.status_code, failure.value.code) == (503, "inventory_read_unavailable")
    session.execute.assert_not_called()


def test_sqlite_is_only_a_functional_surrogate() -> None:
    session = mock_session("sqlite", (3, 50))
    set_read_budgets(session)
    session.execute.assert_not_called()


def test_driver_invalidated_connection_is_discarded() -> None:
    session = mock_session()
    _cleanup(session, invalidated=True)
    session.invalidate.assert_called_once_with()
    session.rollback.assert_not_called()


def test_normal_read_rolls_back_without_commit() -> None:
    session = mock_session()
    _cleanup(session, invalidated=False)
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()
    session.invalidate.assert_not_called()


def test_cleanup_failure_discards_and_is_safe_unavailable() -> None:
    session = mock_session()
    session.rollback.side_effect = OperationalError(
        "private SQL canary", {}, RuntimeError("private")
    )
    with pytest.raises(ApiError) as failure:
        _cleanup(session, invalidated=False)
    session.invalidate.assert_called_once_with()
    assert failure.value.code == "inventory_read_unavailable"
    assert "private" not in str(failure.value)
