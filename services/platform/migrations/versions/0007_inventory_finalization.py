"""Allow only one terminal finalization per inventory reservation.

Revision ID: 0007
Revises: 0006

Preserve the historical ledger, including legacy CONSUME +n / ADJUST -n
pairs. Any existing duplicate finalizations require reviewed reconciliation;
this migration never updates or deletes inventory movements.
"""

import sqlalchemy as sa
from alembic import context, op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_inventory_reservation_finalization"


def upgrade() -> None:
    if not context.is_offline_mode():
        duplicate = (
            op.get_bind()
            .execute(
                sa.text(
                    "SELECT 1 FROM inventory_movements "
                    "WHERE kind IN ('RELEASE', 'CONSUME') "
                    "AND reference_movement_id IS NOT NULL "
                    "GROUP BY organization_id, reference_movement_id "
                    "HAVING COUNT(*) > 1 LIMIT 1"
                )
            )
            .first()
        )
        if duplicate is not None:
            raise RuntimeError(
                "Inventory migration 0007 blocked: duplicate reservation finalizations exist. "
                "Stop inventory writes and take a verified backup. Review RELEASE/CONSUME "
                "rows grouped by organization_id and reference_movement_id, and obtain a "
                "reviewed, history-preserving reconciliation plan before retrying. "
                "No inventory rows were changed."
            )

    # Offline SQL cannot inspect existing data; the unique index still rejects
    # duplicate terminal rows when the generated migration is executed.
    op.create_index(
        INDEX_NAME,
        "inventory_movements",
        ["organization_id", "reference_movement_id"],
        unique=True,
        postgresql_where=sa.text("kind IN ('RELEASE', 'CONSUME')"),
        sqlite_where=sa.text("kind IN ('RELEASE', 'CONSUME')"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="inventory_movements")
