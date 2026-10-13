from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from cycling_workshop.shared.ids import new_id


def _identifier(value: str, name: str) -> None:
    if type(value) is not str or not value or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a nonblank identifier without whitespace")


def _integer(value: int, name: str, *, minimum: int = 0) -> None:
    # bool is an int subclass; implicit numeric coercion is unsafe for money.
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def _description(value: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError("description must be nonblank text")
    return " ".join(value.split())


def _references(values: Sequence[str], name: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError(f"{name} must be a nonempty list or tuple")
    for value in values:
        _identifier(value, name)
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicate identifiers")
    return tuple(sorted(values))


def _timestamp(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("timestamp must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(UTC)


def _round_half_up(numerator: int, denominator: int) -> int:
    """Round a nonnegative rational at a line boundary, without binary floats."""
    return (2 * numerator + denominator) // (2 * denominator)


@dataclass(frozen=True, slots=True)
class LaborLine:
    line_id: str
    description: str
    minutes: int
    hourly_rate_minor: int

    def __post_init__(self) -> None:
        _identifier(self.line_id, "line_id")
        object.__setattr__(self, "description", _description(self.description))
        _integer(self.minutes, "minutes", minimum=1)
        _integer(self.hourly_rate_minor, "hourly_rate_minor")


@dataclass(frozen=True, slots=True)
class PartLine:
    line_id: str
    description: str
    product_id: str
    quantity: int
    unit_price_minor: int

    def __post_init__(self) -> None:
        _identifier(self.line_id, "line_id")
        _identifier(self.product_id, "product_id")
        object.__setattr__(self, "description", _description(self.description))
        _integer(self.quantity, "quantity", minimum=1)
        _integer(self.unit_price_minor, "unit_price_minor")


@dataclass(frozen=True, slots=True)
class TaxLine:
    line_id: str
    description: str
    rate_bps: int
    base_line_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _identifier(self.line_id, "line_id")
        object.__setattr__(self, "description", _description(self.description))
        _integer(self.rate_bps, "rate_bps")
        if self.rate_bps > 10000:
            raise ValueError("rate_bps must not exceed 10000")
        object.__setattr__(self, "base_line_ids", _references(self.base_line_ids, "base_line_ids"))


@dataclass(frozen=True, slots=True)
class DiscountLine:
    line_id: str
    description: str
    amount_minor: int
    scope_line_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _identifier(self.line_id, "line_id")
        object.__setattr__(self, "description", _description(self.description))
        _integer(self.amount_minor, "amount_minor", minimum=1)
        object.__setattr__(
            self, "scope_line_ids", _references(self.scope_line_ids, "scope_line_ids")
        )


type QuoteLine = LaborLine | PartLine | TaxLine | DiscountLine


@dataclass(frozen=True, slots=True)
class QuoteTotals:
    subtotal_minor: int
    discount_minor: int
    tax_minor: int
    total_minor: int
    # Canonical ID order makes the complete calculation independent of presentation order.
    line_amounts: tuple[tuple[str, int], ...]


def _calculate(lines: tuple[QuoteLine, ...]) -> QuoteTotals:
    gross: dict[str, int] = {}
    for line in lines:
        if isinstance(line, LaborLine):
            gross[line.line_id] = _round_half_up(line.minutes * line.hourly_rate_minor, 60)
        elif isinstance(line, PartLine):
            gross[line.line_id] = line.quantity * line.unit_price_minor
    if not gross:
        raise ValueError("quote lines require at least one labor or part charge")

    amounts = dict(gross)
    net = dict(gross)
    discount_total = 0
    for line in lines:
        if not isinstance(line, DiscountLine):
            continue
        if any(line_id not in gross for line_id in line.scope_line_ids):
            raise ValueError("discount scope must reference a labor or part charge line")
        base = sum(gross[line_id] for line_id in line.scope_line_ids)
        if line.amount_minor > base:
            raise ValueError("discount exceeds its scoped charges")
        # Each discount uses the original rounded charges, never the iteration-dependent net.
        # Largest-remainder allocation conserves every minor unit. Ties use stable line IDs.
        allocated = {
            line_id: line.amount_minor * gross[line_id] // base for line_id in line.scope_line_ids
        }
        remaining = line.amount_minor - sum(allocated.values())
        discount_amount = line.amount_minor
        ranked = sorted(
            line.scope_line_ids,
            key=lambda line_id: (-(discount_amount * gross[line_id] % base), line_id),
        )
        for line_id in ranked[:remaining]:
            allocated[line_id] += 1
        for line_id, amount in allocated.items():
            net[line_id] -= amount
        discount_total += line.amount_minor
        amounts[line.line_id] = -line.amount_minor
    if any(amount < 0 for amount in net.values()):
        raise ValueError("overlapping discounts exceed a scoped charge")

    tax_total = 0
    for line in lines:
        if not isinstance(line, TaxLine):
            continue
        if any(line_id not in net for line_id in line.base_line_ids):
            raise ValueError("tax base must reference a labor or part charge line")
        tax = _round_half_up(
            sum(net[line_id] for line_id in line.base_line_ids) * line.rate_bps, 10000
        )
        amounts[line.line_id] = tax
        tax_total += tax
    subtotal = sum(gross.values())
    return QuoteTotals(
        subtotal_minor=subtotal,
        discount_minor=discount_total,
        tax_minor=tax_total,
        total_minor=subtotal - discount_total + tax_total,
        line_amounts=tuple(sorted(amounts.items())),
    )


@dataclass(frozen=True, slots=True)
class Quote:
    quote_id: str
    organization_id: str
    location_id: str
    order_id: str
    lines: tuple[QuoteLine, ...]
    currency: str
    version: int
    created_at: datetime
    revises_quote_id: str | None = None
    superseded_at: datetime | None = None
    superseded_by: str | None = None
    totals: QuoteTotals = field(init=False)

    def __post_init__(self) -> None:
        for name in ("quote_id", "organization_id", "location_id", "order_id"):
            _identifier(getattr(self, name), name)
        if (
            type(self.currency) is not str
            or len(self.currency) != 3
            or not all("A" <= char <= "Z" for char in self.currency)
        ):
            raise ValueError("currency must be a three-letter uppercase ASCII code")
        _integer(self.version, "version", minimum=1)
        object.__setattr__(self, "created_at", _timestamp(self.created_at))
        if (self.version == 1) != (self.revises_quote_id is None):
            raise ValueError(
                "version 1 has no predecessor; later versions require revises_quote_id"
            )
        if self.revises_quote_id is not None:
            _identifier(self.revises_quote_id, "revises_quote_id")
            if self.revises_quote_id == self.quote_id:
                raise ValueError("revises_quote_id must differ from quote_id")
        if (self.superseded_at is None) != (self.superseded_by is None):
            raise ValueError("superseded_at and superseded_by must be set together")
        if self.superseded_at is not None and self.superseded_by is not None:
            _identifier(self.superseded_by, "superseded_by")
            timestamp = _timestamp(self.superseded_at)
            if timestamp < self.created_at:
                raise ValueError("superseded_at cannot be before created_at")
            if self.superseded_by in (self.quote_id, self.revises_quote_id):
                raise ValueError("superseded_by must identify a new quote")
            object.__setattr__(self, "superseded_at", timestamp)
        if not isinstance(self.lines, (list, tuple)):
            raise ValueError("lines must be a list or tuple of typed quote lines")
        lines = tuple(self.lines)
        if any(type(line) not in (LaborLine, PartLine, TaxLine, DiscountLine) for line in lines):
            raise ValueError("lines must contain only typed quote lines")
        if len({line.line_id for line in lines}) != len(lines):
            raise ValueError("duplicate quote line identifiers")
        object.__setattr__(self, "lines", lines)
        object.__setattr__(self, "totals", _calculate(lines))

    @classmethod
    def for_order(
        cls,
        *,
        organization_id: str,
        location_id: str,
        order_id: str,
        lines: Sequence[QuoteLine],
        currency: str,
        quote_id: str | None = None,
        now: datetime | None = None,
    ) -> Quote:
        if not isinstance(lines, (list, tuple)):
            raise ValueError("lines must be a list or tuple of typed quote lines")
        return cls(
            quote_id=new_id() if quote_id is None else quote_id,
            organization_id=organization_id,
            location_id=location_id,
            order_id=order_id,
            lines=tuple(lines),
            currency=currency,
            version=1,
            created_at=datetime.now(UTC) if now is None else now,
        )

    def revise(
        self,
        *,
        lines: Sequence[QuoteLine],
        quote_id: str | None = None,
        now: datetime | None = None,
    ) -> QuoteRevision:
        """Return both records for an eventual atomic, optimistic repository write.

        The caller must persist the marked predecessor AND append the successor.
        This pure function cannot detect a stale copy held by another writer.
        """
        if self.superseded_at is not None:
            raise ValueError("cannot revise a superseded quote")
        timestamp = _timestamp(datetime.now(UTC) if now is None else now)
        if timestamp < self.created_at:
            raise ValueError("revision cannot be before predecessor creation")
        next_id = new_id() if quote_id is None else quote_id
        if next_id in (self.quote_id, self.revises_quote_id):
            raise ValueError("quote_id must identify a new revision")
        if not isinstance(lines, (list, tuple)):
            raise ValueError("lines must be a list or tuple of typed quote lines")
        successor = Quote(
            quote_id=next_id,
            organization_id=self.organization_id,
            location_id=self.location_id,
            order_id=self.order_id,
            lines=tuple(lines),
            currency=self.currency,
            version=self.version + 1,
            created_at=timestamp,
            revises_quote_id=self.quote_id,
        )
        predecessor = replace(self, superseded_at=timestamp, superseded_by=next_id)
        return QuoteRevision(predecessor=predecessor, successor=successor)


@dataclass(frozen=True, slots=True)
class QuoteRevision:
    predecessor: Quote
    successor: Quote
