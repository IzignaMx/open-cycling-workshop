"""Bounded projection reads; the caller holds the organization writer barrier.

Metadata selection never transports Text/JSON values. ``estimated_bytes`` is a
conservative bound for a JSON envelope, including JSON escaping, for
ensure_ascii=False wire encoding.
The coordinator must budget that bound BEFORE calling ``load`` and still check
actual serialized response bytes. These helpers neither commit nor lock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import LargeBinary, Text, cast, func, literal, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement, SQLColumnExpression

from cycling_workshop.bicycles.models import BicycleRecord
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.service_orders.models import ServiceOrderRecord
from cycling_workshop.sync.models import ChangeRecord

_MODELS: dict[str, type[CustomerRecord] | type[BicycleRecord] | type[ServiceOrderRecord]] = {
    "customer": CustomerRecord,
    "bicycle": BicycleRecord,
    "service_order": ServiceOrderRecord,
}
_ID_KEYS = {"customer": "customer_id", "bicycle": "bicycle_id", "service_order": "order_id"}


@dataclass(frozen=True)
class Candidate:
    entity_type: str
    entity_id: str
    position: str | int
    estimated_bytes: int


class BaselineQueries:
    def __init__(
        self, session: Session, organization_id: str, location_id: str, entity_types: list[str]
    ) -> None:
        if any(value not in _MODELS for value in entity_types):
            raise ValueError("unsupported baseline entity type")
        self.session = session
        self.organization_id = organization_id
        self.location_id = location_id
        self.entity_types = tuple(dict.fromkeys(entity_types))
        self.postgres = session.get_bind().dialect.name == "postgresql"

    def _octets(self, expression: SQLColumnExpression[object]) -> ColumnElement[int]:
        if self.postgres:
            return func.octet_length(cast(expression, Text))
        return func.length(cast(expression, LargeBinary))

    def watermark(self) -> int:
        if not self.entity_types:
            return 0
        return (
            self.session.scalar(
                select(ChangeRecord.cursor)
                .where(ChangeRecord.organization_id == self.organization_id)
                .order_by(ChangeRecord.cursor.desc())
                .limit(1)
            )
            or 0
        )

    def maxima(self) -> dict[str, str | None]:
        result: dict[str, str | None] = {}
        for entity_type in self.entity_types:
            model = _MODELS[entity_type]
            identifier = model.id.collate("C" if self.postgres else "BINARY")
            result[entity_type] = self.session.scalar(
                select(model.id)
                .where(
                    model.organization_id == self.organization_id,
                    model.location_id == self.location_id,
                )
                .order_by(identifier.desc())
                .limit(1)
            )
        return result

    def scan_candidates(
        self, entity_type: str, after: str | None, maximum: str, limit: int = 101
    ) -> list[Candidate]:
        if entity_type not in self.entity_types:
            return []
        if not 1 <= limit <= 101:
            raise ValueError("candidate limit must be between 1 and 101")
        model = _MODELS[entity_type]
        identifier = model.id.collate("C" if self.postgres else "BINARY")
        # Keys, punctuation, envelope, timestamps, nulls and fixed-width numbers
        # fit within 2048 bytes. SQL JSON quoting measures actual UTF-8 escape
        # expansion without transferring the potentially TOAST-compressed Text.
        # The coordinator serializes with ensure_ascii=False, as PostgreSQL does.
        size: ColumnElement[int] = literal(2048)
        for column in model.__table__.columns:
            if column.name not in {"created_at", "updated_at", "version"}:
                quoted = func.to_json(column) if self.postgres else func.json_quote(column)
                size = size + func.coalesce(self._octets(quoted), 0)
        statement = select(model.id, size.label("estimated_bytes")).where(
            model.organization_id == self.organization_id,
            model.location_id == self.location_id,
            identifier <= maximum,
        )
        if after is not None:
            statement = statement.where(identifier > after)
        return [
            Candidate(entity_type, identifier, identifier, size)
            for identifier, size in self.session.execute(
                statement.order_by(identifier).limit(limit)
            )
        ]

    def delta_candidates(self, after: int, high: int) -> list[Candidate]:
        result: list[Candidate] = []
        for entity_type in self.entity_types:
            # Per-type equality-prefix range reads prevent hidden types from
            # causing an unbounded walk before a global LIMIT.
            statement = (
                select(
                    ChangeRecord.entity_id,
                    ChangeRecord.cursor,
                    (2048 + self._octets(ChangeRecord.payload)).label("estimated_bytes"),
                )
                .where(
                    ChangeRecord.organization_id == self.organization_id,
                    ChangeRecord.location_id == self.location_id,
                    ChangeRecord.entity_type == entity_type,
                    ChangeRecord.cursor > after,
                    ChangeRecord.cursor <= high,
                )
                .order_by(ChangeRecord.cursor)
                .limit(101)
            )
            result.extend(
                Candidate(entity_type, entity_id, cursor, size)
                for entity_id, cursor, size in self.session.execute(statement)
            )
        return sorted(result, key=lambda candidate: int(candidate.position))

    def load(self, candidate: Candidate) -> dict[str, object]:
        if candidate.entity_type not in self.entity_types:
            raise ValueError("candidate type is not authorized")
        if isinstance(candidate.position, int):
            record = self.session.scalar(
                select(ChangeRecord)
                .where(
                    ChangeRecord.organization_id == self.organization_id,
                    ChangeRecord.location_id == self.location_id,
                    ChangeRecord.entity_type == candidate.entity_type,
                    ChangeRecord.entity_id == candidate.entity_id,
                    ChangeRecord.cursor == candidate.position,
                )
                .execution_options(populate_existing=True)
            )
            if record is None:
                raise ValueError("candidate disappeared")
            version = record.entity_version
            payload = record.payload
        else:
            model = _MODELS[candidate.entity_type]
            row = (
                self.session.execute(
                    select(model.__table__).where(
                        model.organization_id == self.organization_id,
                        model.location_id == self.location_id,
                        model.id == candidate.entity_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ValueError("candidate disappeared")
            version = row["version"]
            payload = {}
            for key, value in row.items():
                if isinstance(value, datetime):
                    value = (
                        value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
                    ).isoformat()
                payload[_ID_KEYS[candidate.entity_type] if key == "id" else key] = value
        return {
            "entity_type": candidate.entity_type,
            "entity_id": candidate.entity_id,
            "entity_version": version,
            "payload": payload,
        }
