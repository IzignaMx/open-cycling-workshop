"""Closed revision projections from a fully reconstructed QuoteSnapshot only.

These pure functions do not load, admit, authorize or revalidate stored history.
The caller must use QuoteRepository.load under fresh protocol-1 writer admission
and, once the separate catalog/application boundary exists, both read grants.
Never turn a manually assembled snapshot or a continuation into read authority.
There are no mounted routes, persistence writes or HTTP error handlers here.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    ValidationError,
    model_validator,
)

from cycling_workshop.quotes.domain import Quote
from cycling_workshop.quotes.reconstruction import QuoteSnapshot
from cycling_workshop.quotes.storage import (
    MAX_EDGES,
    MAX_LINES,
    MAX_REVISIONS,
    MAX_SAFE_INTEGER,
    _id,
    _string,
    _timestamp,
    canonical_bytes,
    encode_quote,
)

PAGE_LIMIT = 25
RESPONSE_LIMIT = 1024 * 1024
ERROR_LIMIT = 8 * 1024


def _identifier(value: str) -> str:
    canonical_bytes(value)
    return _id(value)


def _revision_id(value: str) -> str:
    return _id(value, generated=True)


def _canonical_time(value: str) -> str:
    _timestamp(value)
    return value


def _description(value: str) -> str:
    # _string bounds codepoints/UTF-8; canonical_bytes also refuses NUL/surrogates.
    _string(value, 500)
    canonical_bytes(value)
    return value


type Identifier = Annotated[StrictStr, AfterValidator(_identifier)]
type RevisionID = Annotated[StrictStr, AfterValidator(_revision_id)]
type Timestamp = Annotated[StrictStr, AfterValidator(_canonical_time)]
type Money = Annotated[StrictInt, Field(ge=0, le=MAX_SAFE_INTEGER)]
type SignedMoney = Annotated[StrictInt, Field(ge=-MAX_SAFE_INTEGER, le=MAX_SAFE_INTEGER)]
type Version = Annotated[StrictInt, Field(ge=1, le=MAX_SAFE_INTEGER)]
type Quantity = Annotated[StrictInt, Field(ge=1, le=1_000_000)]
type Description = Annotated[StrictStr, AfterValidator(_description)]
type Targets = Annotated[
    tuple[RevisionID, ...], Field(strict=False, min_length=1, max_length=MAX_LINES)
]


class ClosedReadModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always"
    )


class PricingSummary(ClosedReadModel):
    subtotal_minor: Money
    discount_minor: Money
    tax_minor: Money
    total_minor: Money


class LineAmount(ClosedReadModel):
    line_id: RevisionID
    amount_minor: SignedMoney


class RevisionTotals(PricingSummary):
    line_amounts: Annotated[
        tuple[LineAmount, ...], Field(strict=False, min_length=1, max_length=MAX_LINES)
    ]


class LaborReadLine(ClosedReadModel):
    kind: Literal["labor"]
    line_id: RevisionID
    description: Description
    minutes: Quantity
    hourly_rate_minor: Money


class PartReadLine(ClosedReadModel):
    kind: Literal["part"]
    line_id: RevisionID
    description: Description
    product_id: Identifier
    quantity: Quantity
    unit_price_minor: Money


class TaxReadLine(ClosedReadModel):
    kind: Literal["tax"]
    line_id: RevisionID
    description: Description
    rate_bps: Annotated[StrictInt, Field(ge=0, le=10_000)]
    base_line_ids: Targets


class DiscountReadLine(ClosedReadModel):
    kind: Literal["discount"]
    line_id: RevisionID
    description: Description
    amount_minor: Annotated[StrictInt, Field(ge=1, le=MAX_SAFE_INTEGER)]
    scope_line_ids: Targets


type ReadLine = Annotated[
    LaborReadLine | PartReadLine | TaxReadLine | DiscountReadLine, Field(discriminator="kind")
]


class RevisionMetadata(ClosedReadModel):
    quote_id: RevisionID
    version: Version
    revises_quote_id: RevisionID | None
    created_at: Timestamp
    currency: Annotated[StrictStr, Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")]
    totals: PricingSummary


class FinancialRevision(RevisionMetadata):
    """Immutable financial payload; derived supersession belongs outside it."""

    lines: Annotated[tuple[ReadLine, ...], Field(strict=False, min_length=1, max_length=MAX_LINES)]
    totals: RevisionTotals

    @model_validator(mode="after")
    def bounded_edges(self) -> Self:
        edges = sum(
            len(line.base_line_ids)
            if isinstance(line, TaxReadLine)
            else len(line.scope_line_ids)
            if isinstance(line, DiscountReadLine)
            else 0
            for line in self.lines
        )
        if edges > MAX_EDGES:
            raise ValueError("quote read target limit exceeded")
        return self


class CurrentLineage(ClosedReadModel):
    """Fresh lineage context, never an authorization or execution permission."""

    organization_id: Identifier
    location_id: Identifier
    order_id: Identifier
    lineage_id: RevisionID
    head_quote_id: RevisionID
    head_version: Version
    decision_sequence: Money


class RevisionMetadataPage(ClosedReadModel):
    current: CurrentLineage
    items: Annotated[
        tuple[RevisionMetadata, ...], Field(strict=False, min_length=1, max_length=PAGE_LIMIT)
    ]
    next_cursor: Annotated[StrictStr, Field(pattern=r"^[a-f0-9]{64}$")] | None


class RevisionDetail(ClosedReadModel):
    current: CurrentLineage
    revision: FinancialRevision


type ErrorCode = Literal[
    "invalid_quote_page",
    "invalid_quote_cursor",
    "quote_revision_not_found",
    "invalid_quote_projection",
    "quote_response_too_large",
]


class ReadFailure(ClosedReadModel):
    code: ErrorCode


class QuoteReadError(ValueError):
    """One bounded allowlisted code; no evidence, raw request or exception echo."""

    def __init__(self, code: ErrorCode):
        self.failure = ReadFailure(code=code)
        super().__init__(code)


def encode_read_error(error: QuoteReadError) -> bytes:
    value = ReadFailure.model_validate(error.failure)
    encoded = value.model_dump_json().encode("utf-8")
    if len(encoded) > ERROR_LIMIT:
        raise ValueError("quote read error exceeds byte limit")
    return encoded


def encode_read_response(response: RevisionMetadataPage | RevisionDetail) -> bytes:
    """Return the exact bytes a later transport must send, never reserialize."""
    if type(response) not in (RevisionMetadataPage, RevisionDetail):
        raise QuoteReadError("invalid_quote_projection")
    try:
        # model_copy/model_construct bypass validation; do not trust those paths.
        checked = type(response).model_validate(response)
        encoded = checked.model_dump_json().encode("utf-8")
    except (ValidationError, ValueError, TypeError, UnicodeError):
        raise QuoteReadError("invalid_quote_projection") from None
    if len(encoded) > RESPONSE_LIMIT:
        raise QuoteReadError("quote_response_too_large")
    return encoded


def _current(snapshot: QuoteSnapshot) -> CurrentLineage:
    if type(snapshot) is not QuoteSnapshot:
        raise QuoteReadError("invalid_quote_projection")
    head = snapshot.ledger.history.head
    return CurrentLineage(
        organization_id=head.organization_id,
        location_id=head.location_id,
        order_id=head.order_id,
        lineage_id=snapshot.ledger.history.lineage_id,
        head_quote_id=head.quote_id,
        head_version=head.version,
        decision_sequence=snapshot.ledger.sequence,
    )


def _metadata(quote: Quote) -> RevisionMetadata:
    return RevisionMetadata(
        quote_id=quote.quote_id,
        version=quote.version,
        revises_quote_id=quote.revises_quote_id,
        created_at=quote.created_at.isoformat(timespec="microseconds").replace("+00:00", "Z"),
        currency=quote.currency,
        totals=PricingSummary(
            subtotal_minor=quote.totals.subtotal_minor,
            discount_minor=quote.totals.discount_minor,
            tax_minor=quote.totals.tax_minor,
            total_minor=quote.totals.total_minor,
        ),
    )


def _position(current: CurrentLineage, after_version: int) -> str:
    # Opaque position only, not a secret, MAC, grant or substitute for fresh reads.
    payload = dict(current.model_dump(), after_version=after_version)
    return hashlib.sha256(b"ocwp-quote-revisions-v1\0" + canonical_bytes(payload)).hexdigest()


def project_revision_page(
    snapshot: QuoteSnapshot, *, limit: int = PAGE_LIMIT, cursor: str | None = None
) -> RevisionMetadataPage:
    """Project only after complete repository validation, including outside page."""
    if type(limit) is not int or not 1 <= limit <= PAGE_LIMIT:
        raise QuoteReadError("invalid_quote_page")
    current = _current(snapshot)
    revisions = snapshot.ledger.history.revisions
    if not 1 <= len(revisions) <= MAX_REVISIONS:
        raise QuoteReadError("invalid_quote_projection")
    after = 0
    if cursor is not None:
        if type(cursor) is not str or len(cursor) != 64 or not cursor.isascii():
            raise QuoteReadError("invalid_quote_cursor")
        # The domain bounds this search to 31 possible continuation positions.
        after = next(
            (
                quote.version
                for quote in revisions[:-1]
                if hmac.compare_digest(cursor, _position(current, quote.version))
            ),
            0,
        )
        if after == 0:
            raise QuoteReadError("invalid_quote_cursor")
    items = tuple(_metadata(quote) for quote in revisions[after : after + limit])
    result = RevisionMetadataPage(
        current=current,
        items=items,
        next_cursor=_position(current, items[-1].version)
        if after + len(items) < len(revisions)
        else None,
    )
    encode_read_response(result)
    return result


def project_revision(snapshot: QuoteSnapshot, quote_id: str) -> RevisionDetail:
    """Return one original financial revision with separately current context."""
    current = _current(snapshot)
    quote = next(
        (item for item in snapshot.ledger.history.revisions if item.quote_id == quote_id), None
    )
    if type(quote_id) is not str or quote is None:
        raise QuoteReadError("quote_revision_not_found")
    # Explicit allowlist, not a storage codec masquerading as the wire contract.
    stored = encode_quote(quote)
    document = _metadata(quote).model_dump()
    document["lines"] = stored["lines"]
    document["totals"]["line_amounts"] = tuple(
        {"line_id": line_id, "amount_minor": amount}
        for line_id, amount in quote.totals.line_amounts
    )
    result = RevisionDetail(current=current, revision=FinancialRevision.model_validate(document))
    encode_read_response(result)
    return result
