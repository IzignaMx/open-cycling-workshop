"""Target only workshop REST creation's global identifier conflict."""

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import CompileError
from sqlalchemy.orm import Session


def insert_unless_id_conflicts(session: Session, table: Table, values: dict[str, object]) -> bool:
    """Insert without overwriting; all non-ID integrity/database failures propagate.

    The caller owns authorization, transaction commit/rollback and change emission.
    Sync's receipt-based application must continue using its existing write path.
    """
    if table.name not in {"customers", "bicycles", "service_orders"} or list(
        table.primary_key.columns.keys()
    ) != ["id"]:
        raise ValueError("unsupported identifier conflict table")
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        statement = (
            postgres_insert(table)
            .values(values)
            .on_conflict_do_nothing(index_elements=[table.c.id])
            .returning(table.c.id)
        )
    elif dialect == "sqlite":
        statement = (
            sqlite_insert(table)
            .values(values)
            .on_conflict_do_nothing(index_elements=[table.c.id])
            .returning(table.c.id)
        )
    else:
        raise CompileError("unsupported database for workshop identifier conflicts")
    return session.scalar(statement) is not None
