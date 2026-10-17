"""Additive quote storage; immutable-history guards are installed by migration 0012.

These rows are evidence, not current authorization. Strict domain reconstruction
and the transaction boundary remain responsible for JSON and cross-row meaning.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from cycling_workshop.db.base import Base

MAX_SAFE = 9_007_199_254_740_991


def _currency_check() -> str:
    # Exact ASCII membership, independent of a PostgreSQL locale collation.
    remaining = "currency"
    for character in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        remaining = f"replace({remaining}, '{character}', '')"
    return f"length(currency) = 3 AND {remaining} = ''"


def _range(column: str, minimum: int = 0) -> str:
    return f"{column} BETWEEN {minimum} AND {MAX_SAFE}"


class QuoteLineageRecord(Base):
    __tablename__ = "quote_lineages"
    __table_args__ = (
        UniqueConstraint("organization_id", "order_id", name="uq_quote_lineage_order"),
        UniqueConstraint("lineage_id", "organization_id", name="uq_quote_lineage_tenant"),
        ForeignKeyConstraint(
            ["order_id", "organization_id", "location_id"],
            ["service_orders.id", "service_orders.organization_id", "service_orders.location_id"],
            name="fk_quote_lineage_order_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["root_quote_id", "lineage_id", "organization_id"],
            [
                "quote_revisions.quote_id",
                "quote_revisions.lineage_id",
                "quote_revisions.organization_id",
            ],
            name="fk_quote_lineage_root",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        ForeignKeyConstraint(
            ["head_quote_id", "lineage_id", "organization_id", "head_version"],
            [
                "quote_revisions.quote_id",
                "quote_revisions.lineage_id",
                "quote_revisions.organization_id",
                "quote_revisions.version",
            ],
            name="fk_quote_lineage_head",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        CheckConstraint("root_quote_id = lineage_id", name="ck_quote_lineage_root"),
        CheckConstraint(_range("head_version", 1), name="ck_quote_lineage_head_version"),
        CheckConstraint(_range("decision_sequence"), name="ck_quote_lineage_sequence"),
        CheckConstraint(_currency_check(), name="ck_quote_lineage_currency"),
    )

    lineage_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[str] = mapped_column(String(36), nullable=False)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    root_quote_id: Mapped[str] = mapped_column(String(36), nullable=False)
    head_quote_id: Mapped[str] = mapped_column(String(36), nullable=False)
    head_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    decision_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)


class QuoteRevisionRecord(Base):
    __tablename__ = "quote_revisions"
    __table_args__ = (
        UniqueConstraint("lineage_id", "version", name="uq_quote_revision_version"),
        UniqueConstraint("predecessor_id", name="uq_quote_revision_successor"),
        UniqueConstraint(
            "quote_id", "lineage_id", "organization_id", name="uq_quote_revision_scope"
        ),
        UniqueConstraint(
            "quote_id",
            "lineage_id",
            "organization_id",
            "version",
            name="uq_quote_revision_scope_version",
        ),
        ForeignKeyConstraint(
            ["lineage_id", "organization_id"],
            ["quote_lineages.lineage_id", "quote_lineages.organization_id"],
            name="fk_quote_revision_lineage",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["predecessor_id", "lineage_id", "organization_id"],
            [
                "quote_revisions.quote_id",
                "quote_revisions.lineage_id",
                "quote_revisions.organization_id",
            ],
            name="fk_quote_revision_predecessor",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["actor_id", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_quote_revision_actor",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_range("version", 1), name="ck_quote_revision_version"),
        CheckConstraint(
            "(version = 1 AND predecessor_id IS NULL AND quote_id = lineage_id) OR "
            "(version > 1 AND predecessor_id IS NOT NULL AND quote_id <> lineage_id AND "
            "quote_id <> predecessor_id)",
            name="ck_quote_revision_root",
        ),
        *(
            CheckConstraint(_range(column), name=f"ck_quote_revision_{column}")
            for column in ("subtotal_minor", "discount_minor", "tax_minor", "total_minor")
        ),
    )

    quote_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lineage_id: Mapped[str] = mapped_column(String(36), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    predecessor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_amounts: Mapped[list[object]] = mapped_column(JSON, nullable=False)


class QuoteLineRecord(Base):
    __tablename__ = "quote_lines"
    __table_args__ = (
        UniqueConstraint("revision_id", "position", name="uq_quote_line_position"),
        ForeignKeyConstraint(
            ["revision_id", "lineage_id", "organization_id"],
            [
                "quote_revisions.quote_id",
                "quote_revisions.lineage_id",
                "quote_revisions.organization_id",
            ],
            name="fk_quote_line_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["product_id", "organization_id"],
            ["products.id", "products.organization_id"],
            name="fk_quote_line_product",
            ondelete="RESTRICT",
        ),
        CheckConstraint("position BETWEEN 0 AND 99", name="ck_quote_line_position"),
        CheckConstraint("length(description) BETWEEN 1 AND 500", name="ck_quote_line_description"),
        CheckConstraint(
            "(kind = 'labor' AND minutes IS NOT NULL AND hourly_rate_minor IS NOT NULL "
            "AND product_id IS NULL AND quantity IS NULL AND unit_price_minor IS NULL "
            "AND rate_bps IS NULL AND amount_minor IS NULL) OR "
            "(kind = 'part' AND product_id IS NOT NULL AND quantity IS NOT NULL AND "
            "unit_price_minor IS NOT NULL "
            "AND minutes IS NULL AND hourly_rate_minor IS NULL AND rate_bps IS NULL AND "
            "amount_minor IS NULL) OR "
            "(kind = 'tax' AND rate_bps IS NOT NULL AND product_id IS NULL AND quantity "
            "IS NULL AND unit_price_minor IS NULL "
            "AND minutes IS NULL AND hourly_rate_minor IS NULL AND amount_minor IS NULL) OR "
            "(kind = 'discount' AND amount_minor IS NOT NULL AND product_id IS NULL AND "
            "quantity IS NULL AND unit_price_minor IS NULL "
            "AND minutes IS NULL AND hourly_rate_minor IS NULL AND rate_bps IS NULL)",
            name="ck_quote_line_kind_fields",
        ),
        CheckConstraint("minutes BETWEEN 1 AND 1000000", name="ck_quote_line_minutes"),
        CheckConstraint("quantity BETWEEN 1 AND 1000000", name="ck_quote_line_quantity"),
        CheckConstraint("rate_bps BETWEEN 0 AND 10000", name="ck_quote_line_rate"),
        CheckConstraint(_range("hourly_rate_minor"), name="ck_quote_line_hourly_rate"),
        CheckConstraint(_range("unit_price_minor"), name="ck_quote_line_unit_price"),
        CheckConstraint(_range("amount_minor", 1), name="ck_quote_line_discount"),
    )

    revision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    line_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False)
    lineage_id: Mapped[str] = mapped_column(String(36), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    product_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hourly_rate_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    rate_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class QuoteLineTargetRecord(Base):
    __tablename__ = "quote_line_targets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["revision_id", "source_line_id"],
            ["quote_lines.revision_id", "quote_lines.line_id"],
            name="fk_quote_target_source",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["revision_id", "target_line_id"],
            ["quote_lines.revision_id", "quote_lines.line_id"],
            name="fk_quote_target_target",
            ondelete="RESTRICT",
        ),
        CheckConstraint("source_line_id <> target_line_id", name="ck_quote_target_distinct"),
    )

    revision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_line_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    target_line_id: Mapped[str] = mapped_column(String(36), primary_key=True)


class QuoteDecisionRecord(Base):
    __tablename__ = "quote_decisions"
    __table_args__ = (
        UniqueConstraint("lineage_id", "sequence", name="uq_quote_decision_sequence"),
        UniqueConstraint("supersedes_entry_id", name="uq_quote_decision_successor"),
        UniqueConstraint(
            "decision_id",
            "lineage_id",
            "organization_id",
            "quote_id",
            "quote_version",
            name="uq_quote_decision_scope",
        ),
        ForeignKeyConstraint(
            ["quote_id", "lineage_id", "organization_id", "quote_version"],
            [
                "quote_revisions.quote_id",
                "quote_revisions.lineage_id",
                "quote_revisions.organization_id",
                "quote_revisions.version",
            ],
            name="fk_quote_decision_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["supersedes_entry_id", "lineage_id", "organization_id", "quote_id", "quote_version"],
            [
                "quote_decisions.decision_id",
                "quote_decisions.lineage_id",
                "quote_decisions.organization_id",
                "quote_decisions.quote_id",
                "quote_decisions.quote_version",
            ],
            name="fk_quote_decision_predecessor",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["actor_id", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_quote_decision_actor",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_range("sequence", 1), name="ck_quote_decision_sequence"),
        CheckConstraint(_range("quote_version", 1), name="ck_quote_decision_version"),
        CheckConstraint(
            "reason IS NULL OR length(reason) BETWEEN 1 AND 500", name="ck_quote_decision_reason"
        ),
        CheckConstraint(
            "supersedes_entry_id IS NULL OR supersedes_entry_id <> decision_id",
            name="ck_quote_decision_distinct",
        ),
    )

    decision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lineage_id: Mapped[str] = mapped_column(String(36), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quote_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quote_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    supersedes_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    line_decisions: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    pricing: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class QuoteOperationRecord(Base):
    __tablename__ = "quote_operations"
    __table_args__ = (
        UniqueConstraint("lineage_id", "ordinal", name="uq_quote_operation_ordinal"),
        UniqueConstraint("quote_outbox_id", name="uq_quote_operation_outbox"),
        UniqueConstraint("order_event_id", name="uq_quote_operation_order_event"),
        UniqueConstraint("order_outbox_id", name="uq_quote_operation_order_outbox"),
        UniqueConstraint("change_cursor", name="uq_quote_operation_change"),
        UniqueConstraint("decision_id", name="uq_quote_operation_decision"),
        ForeignKeyConstraint(
            ["quote_id", "lineage_id", "organization_id", "quote_version"],
            [
                "quote_revisions.quote_id",
                "quote_revisions.lineage_id",
                "quote_revisions.organization_id",
                "quote_revisions.version",
            ],
            name="fk_quote_operation_revision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["decision_id", "lineage_id", "organization_id", "quote_id", "quote_version"],
            [
                "quote_decisions.decision_id",
                "quote_decisions.lineage_id",
                "quote_decisions.organization_id",
                "quote_decisions.quote_id",
                "quote_decisions.quote_version",
            ],
            name="fk_quote_operation_decision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["actor_id", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_quote_operation_actor",
            ondelete="RESTRICT",
        ),
        CheckConstraint("proof_version = 1", name="ck_quote_operation_proof_version"),
        CheckConstraint(
            "(kind = 'create' AND quote_version = 1 AND resulting_decision_sequence = 0 "
            "AND decision_id IS NULL) OR "
            "(kind = 'revise' AND quote_version > 1 AND decision_id IS NULL) OR "
            "(kind = 'decision' AND decision_id IS NOT NULL AND decision_id = "
            "operation_id AND resulting_decision_sequence > 0)",
            name="ck_quote_operation_result",
        ),
        CheckConstraint(_range("quote_version", 1), name="ck_quote_operation_version"),
        CheckConstraint(_range("resulting_decision_sequence"), name="ck_quote_operation_sequence"),
        CheckConstraint(
            _range("ordinal", 1) + " AND ordinal = quote_version + resulting_decision_sequence",
            name="ck_quote_operation_ordinal",
        ),
        CheckConstraint(
            "(order_event_id IS NULL AND resulting_order_version IS NULL AND "
            "change_cursor IS NULL AND order_outbox_id IS NULL) OR "
            "(kind = 'decision' AND order_event_id IS NOT NULL AND "
            "resulting_order_version IS NOT NULL AND change_cursor IS NOT NULL AND "
            "order_outbox_id IS NOT NULL)",
            name="ck_quote_operation_order_effects",
        ),
        CheckConstraint(
            "(order_event_id IS NULL AND resulting_order_version IS NULL AND "
            "change_cursor IS NULL AND order_outbox_id IS NULL AND order_effect_version IS NULL) "
            "OR (kind = 'decision' AND order_event_id IS NOT NULL AND "
            "resulting_order_version IS NOT NULL AND change_cursor IS NOT NULL AND "
            "order_outbox_id IS NOT NULL AND order_effect_version IS NOT NULL AND "
            "order_effect_version = 1)",
            name="ck_quote_operation_effect_version",
        ),
        CheckConstraint(
            _range("resulting_order_version", 1), name="ck_quote_operation_order_version"
        ),
        CheckConstraint(_range("change_cursor", 1), name="ck_quote_operation_cursor"),
        CheckConstraint(
            "order_outbox_id IS NULL OR order_outbox_id <> quote_outbox_id",
            name="ck_quote_operation_distinct_outboxes",
        ),
    )

    organization_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lineage_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    quote_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quote_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resulting_decision_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ordinal: Mapped[int] = mapped_column(BigInteger, nullable=False)
    decision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    proof_version: Mapped[int] = mapped_column(Integer, nullable=False)
    proof: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quote_outbox_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("outbox_events.event_id", ondelete="RESTRICT"), nullable=False
    )
    order_event_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("service_order_events.event_id", ondelete="RESTRICT"), nullable=True
    )
    resulting_order_version: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    order_effect_version: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    change_cursor: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sync_changes.cursor", ondelete="RESTRICT"), nullable=True
    )
    order_outbox_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("outbox_events.event_id", ondelete="RESTRICT"), nullable=True
    )
