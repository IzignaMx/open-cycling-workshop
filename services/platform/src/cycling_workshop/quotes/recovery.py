"""Read-only complete quote inventory before maintenance incarnation rotation.

The caller owns the organization writer barrier and transaction. All application
writers must be stopped on the isolated restored target; this is not a live repair
or a defense against privileged concurrent SQL. No authority principal is forged.
"""

from sqlalchemy import exists, func, inspect, or_, select, text
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.quotes.models import (
    QuoteDecisionRecord,
    QuoteLineageRecord,
    QuoteLineRecord,
    QuoteLineTargetRecord,
    QuoteOperationRecord,
    QuoteRevisionRecord,
)
from cycling_workshop.quotes.repository import (
    QuoteIntegrityError,
    QuoteRepository,
)


def validate_recovered_quotes(session: Session, organization_id: str) -> None:
    """Validate every retained lineage, not only a requested/current receipt.

    Pre-quote schemas have no quote history. Populated 0012 requires preserved
    forward migration before this 0013 reader can validate it. An ownerless target
    has no organization column: its ambiguity conservatively blocks recovery.
    """
    revision = session.scalar(text("SELECT version_num FROM alembic_version"))
    if revision in ("0010", "0011"):
        if any(
            inspect(session.connection()).has_table(model.__tablename__)
            for model in (
                QuoteLineageRecord,
                QuoteRevisionRecord,
                QuoteLineRecord,
                QuoteLineTargetRecord,
                QuoteDecisionRecord,
                QuoteOperationRecord,
            )
        ):
            raise ApiError(409, "cutover_schema_incompatible", "qualified cutover schema required")
        if session.scalar(
            select(
                exists().where(
                    OutboxRecord.organization_id == organization_id,
                    OutboxRecord.aggregate_type == "quote",
                )
            )
        ):
            raise QuoteIntegrityError("stored quote history is invalid")
        return
    if revision not in ("0012", "0013"):
        raise ApiError(409, "cutover_schema_incompatible", "qualified cutover schema required")
    lineage = QuoteLineageRecord
    # Scalar existence probes cannot hydrate malformed or oversized JSON.
    for model in (QuoteRevisionRecord, QuoteLineRecord, QuoteDecisionRecord, QuoteOperationRecord):
        owner = exists().where(
            lineage.lineage_id == model.lineage_id,
            lineage.organization_id == model.organization_id,
        )
        local_lineage = exists().where(
            lineage.lineage_id == model.lineage_id,
            lineage.organization_id == organization_id,
        )
        if session.scalar(
            select(
                exists().where(or_(model.organization_id == organization_id, local_lineage), ~owner)
            )
        ):
            raise QuoteIntegrityError("stored quote history is invalid")
    # A child can claim a different valid lineage while pointing at a local
    # revision. Such rows are outside _load's lineage selection, not ignorable.
    for model, parent_id in (
        (QuoteLineRecord, QuoteLineRecord.revision_id),
        (QuoteDecisionRecord, QuoteDecisionRecord.quote_id),
        (QuoteOperationRecord, QuoteOperationRecord.quote_id),
    ):
        parent = exists().where(
            QuoteRevisionRecord.quote_id == parent_id,
            QuoteRevisionRecord.lineage_id == model.lineage_id,
            QuoteRevisionRecord.organization_id == model.organization_id,
        )
        local_parent = exists().where(
            QuoteRevisionRecord.quote_id == parent_id,
            QuoteRevisionRecord.organization_id == organization_id,
        )
        if session.scalar(
            select(
                exists().where(or_(model.organization_id == organization_id, local_parent), ~parent)
            )
        ):
            raise QuoteIntegrityError("stored quote history is invalid")
    targets = QuoteLineTargetRecord
    for field in (targets.source_line_id, targets.target_line_id):
        owner = exists().where(
            QuoteLineRecord.revision_id == targets.revision_id,
            QuoteLineRecord.line_id == field,
        )
        if session.scalar(select(exists().select_from(targets).where(~owner))):
            raise QuoteIntegrityError("stored quote history is invalid")
    target_revision = exists().where(QuoteRevisionRecord.quote_id == targets.revision_id)
    if session.scalar(select(exists().select_from(targets).where(~target_revision))):
        raise QuoteIntegrityError("stored quote history is invalid")
    operation = QuoteOperationRecord
    local_outbox_lineage = exists().where(
        lineage.lineage_id == OutboxRecord.aggregate_id,
        lineage.organization_id == organization_id,
    )
    outbox_owner = exists().where(
        operation.quote_outbox_id == OutboxRecord.event_id,
        operation.organization_id == OutboxRecord.organization_id,
        operation.lineage_id == OutboxRecord.aggregate_id,
    )
    if session.scalar(
        select(
            exists().where(
                or_(OutboxRecord.organization_id == organization_id, local_outbox_lineage),
                OutboxRecord.aggregate_type == "quote",
                ~outbox_owner,
            )
        )
    ):
        raise QuoteIntegrityError("stored quote history is invalid")
    if revision == "0012":
        if session.scalar(select(exists().where(lineage.organization_id == organization_id))):
            raise ApiError(
                409, "quote_recovery_schema_required", "preserved quote migration required"
            )
        return
    # Detect shared identities across lineages/scopes even if constraints were
    # absent in a damaged restore. Never materialize the identity inventory.
    for column in (
        operation.quote_outbox_id,
        operation.order_event_id,
        operation.change_cursor,
        operation.order_outbox_id,
    ):
        shared = select(column).where(column.is_not(None)).group_by(column).having(func.count() > 1)
        if session.scalar(
            select(exists().where(operation.organization_id == organization_id, column.in_(shared)))
        ):
            raise QuoteIntegrityError("stored quote history is invalid")
    repository = QuoteRepository(session)
    after: str | None = None
    while True:
        statement = select(lineage).where(lineage.organization_id == organization_id)
        if after is not None:
            statement = statement.where(lineage.lineage_id > after)
        current = session.scalar(statement.order_by(lineage.lineage_id).limit(1))
        if current is None:
            return
        # Reuse bounded scalar order metadata, then complete retained-history and
        # generic-pair validation. Quote-only histories never hydrate order Text.
        try:
            repository._order(organization_id, current.location_id, current.order_id)
            repository._load(current)
        except (ValueError, TypeError, AttributeError, OverflowError) as error:
            raise QuoteIntegrityError("stored quote history is invalid") from error
        after = current.lineage_id
