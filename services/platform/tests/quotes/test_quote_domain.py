from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from fractions import Fraction
from itertools import permutations
from random import Random
from uuid import UUID

import pytest
from cycling_workshop.quotes.domain import DiscountLine, LaborLine, PartLine, Quote, TaxLine

NOW = datetime(2026, 10, 13, tzinfo=UTC)


def labor(line_id: str = "labor", **overrides: object) -> LaborLine:
    values: dict[str, object] = {
        "line_id": line_id,
        "description": "Repair",
        "minutes": 30,
        "hourly_rate_minor": 1001,
    }
    return LaborLine(**(values | overrides))  # type: ignore[arg-type]


def part(line_id: str = "part", **overrides: object) -> PartLine:
    values: dict[str, object] = {
        "line_id": line_id,
        "description": "Brake pad",
        "product_id": "product-1",
        "quantity": 2,
        "unit_price_minor": 250,
    }
    return PartLine(**(values | overrides))  # type: ignore[arg-type]


def quote(lines: object = None, **overrides: object) -> Quote:
    values: dict[str, object] = {
        "quote_id": "quote-1",
        "organization_id": "org-1",
        "location_id": "loc-1",
        "order_id": "order-1",
        "lines": [labor()] if lines is None else lines,
        "currency": "MXN",
        "now": NOW,
    }
    return Quote.for_order(**(values | overrides))  # type: ignore[arg-type]


def test_typed_lines_calculate_integer_minor_units_after_scoped_discount() -> None:
    result = quote(
        [
            labor(),
            part(),
            DiscountLine("discount", "Coupon", 101, ("labor", "part")),
            TaxLine("tax", "Tax", 1600, ("labor", "part")),
        ]
    )
    assert result.version == 1
    assert result.currency == "MXN"
    assert result.totals.subtotal_minor == 1001
    assert result.totals.discount_minor == 101
    assert result.totals.tax_minor == 144
    assert result.totals.total_minor == 1044
    assert dict(result.totals.line_amounts) == {
        "labor": 501,
        "part": 500,
        "discount": -101,
        "tax": 144,
    }
    assert result.superseded_at is None
    assert result.superseded_by is None
    assert result.revises_quote_id is None


def test_scoped_discount_has_deterministic_remainder_allocation() -> None:
    lines = [part("a", quantity=1, unit_price_minor=1), part("b", quantity=1, unit_price_minor=1)]
    result = quote(
        [
            *lines,
            DiscountLine("d", "Coupon", 1, ("b", "a")),
            TaxLine("t", "Tax", 10000, ("a",)),
        ]
    )
    # Equal weights: the minor-unit remainder goes to lexical ID a.
    assert result.totals.tax_minor == 0
    assert result.totals.total_minor == 1


def test_tax_is_rounded_once_per_tax_line_after_discount() -> None:
    result = quote(
        [
            part("a", quantity=1, unit_price_minor=3),
            part("b", quantity=1, unit_price_minor=3),
            TaxLine("t1", "Tax", 2500, ("a", "b")),
            TaxLine("t2", "Tax", 2500, ("a", "b")),
        ]
    )
    assert dict(result.totals.line_amounts) == {"a": 3, "b": 3, "t1": 2, "t2": 2}
    assert result.totals.total_minor == 10


def test_rounding_occurs_at_labor_line_boundaries_not_on_aggregate() -> None:
    result = quote(
        [labor("a", minutes=1, hourly_rate_minor=30), labor("b", minutes=1, hourly_rate_minor=30)]
    )
    assert result.totals.subtotal_minor == 2


def test_totals_are_independent_of_line_and_reference_order() -> None:
    charges = [labor(), part()]
    expected = quote(
        [
            *charges,
            DiscountLine("d1", "Coupon", 71, ("labor", "part")),
            DiscountLine("d2", "Coupon", 11, ("labor",)),
            TaxLine("t", "Tax", 1600, ("labor", "part")),
        ]
    ).totals
    for scope in permutations(("labor", "part")):
        lines = [
            *charges,
            DiscountLine("d1", "Coupon", 71, scope),
            DiscountLine("d2", "Coupon", 11, ("labor",)),
            TaxLine("t", "Tax", 1600, scope),
        ]
        for ordering in permutations(lines):
            assert quote(ordering).totals == expected


def test_integer_rounding_properties_against_exact_fraction_oracle() -> None:
    random = Random(20261013)
    cases = [(minute, rate) for minute in range(1, 61) for rate in range(61)]
    cases += [(random.randint(1, 10**6), random.randint(0, 10**16)) for _ in range(150)]
    for minutes, rate in cases:
        exact = Fraction(minutes * rate, 60)
        expected = (exact + Fraction(1, 2)).numerator // (exact + Fraction(1, 2)).denominator
        result = quote([labor(minutes=minutes, hourly_rate_minor=rate)])
        assert result.totals.total_minor == expected
        assert abs(Fraction(result.totals.total_minor) - exact) <= Fraction(1, 2)
        assert type(result.totals.total_minor) is int


def test_discount_tax_and_permutation_properties_on_generated_inputs() -> None:
    random = Random(73)
    for _ in range(250):
        a, b = random.randint(1, 10**8), random.randint(1, 10**8)
        discount, rate = random.randint(1, a + b), random.randint(0, 10000)
        lines = [
            part("a", quantity=1, unit_price_minor=a),
            part("b", quantity=1, unit_price_minor=b),
            DiscountLine("d", "Coupon", discount, ("a", "b")),
            TaxLine("t", "Tax", rate, ("a", "b")),
        ]
        result = quote(lines)
        exact = Fraction((a + b - discount) * rate, 10000) + Fraction(1, 2)
        assert result.totals.tax_minor == exact.numerator // exact.denominator
        assert result.totals.total_minor == a + b - discount + result.totals.tax_minor
        assert sum(amount for _, amount in result.totals.line_amounts) == result.totals.total_minor
        random.shuffle(lines)
        assert quote(lines).totals == result.totals


@pytest.mark.parametrize("value", [True, False, 1.0, "1", None, -1])
@pytest.mark.parametrize(
    "field",
    ["minutes", "hourly_rate_minor", "quantity", "unit_price_minor", "rate_bps", "amount_minor"],
)
def test_invalid_numeric_values_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=field):
        if field in {"minutes", "hourly_rate_minor"}:
            labor(**{field: value})
        elif field in {"quantity", "unit_price_minor"}:
            part(**{field: value})
        elif field == "rate_bps":
            TaxLine("t", "Tax", value, ("part",))  # type: ignore[arg-type]
        else:
            DiscountLine("d", "Coupon", value, ("part",))  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["minutes", "quantity", "amount_minor"])
def test_positive_fields_reject_zero(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        if field == "minutes":
            labor(minutes=0)
        elif field == "quantity":
            part(quantity=0)
        else:
            DiscountLine("d", "Coupon", 0, ("part",))


def test_zero_prices_and_zero_tax_are_valid() -> None:
    result = quote(
        [labor(hourly_rate_minor=0), part(unit_price_minor=0), TaxLine("t", "Tax", 0, ("labor",))]
    )
    assert result.totals.total_minor == 0
    with pytest.raises(ValueError, match="rate_bps"):
        TaxLine("t", "Tax", 10001, ("labor",))


@pytest.mark.parametrize(
    "value", ["", "mxn", " MXN", "MXN ", "US", "EURO", "€UR", "123", None, 123]
)
def test_currency_requires_unambiguous_uppercase_ascii_code(value: object) -> None:
    with pytest.raises(ValueError, match="currency"):
        quote(currency=value)


@pytest.mark.parametrize("field", ["quote_id", "order_id", "organization_id", "location_id"])
@pytest.mark.parametrize("value", ["", " ", " id ", "two ids", True, 1])
def test_quote_requires_nonblank_unambiguous_identifiers(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=field):
        quote(**{field: value})


def test_line_identifiers_and_descriptions_are_validated() -> None:
    with pytest.raises(ValueError, match="line_id"):
        labor("")
    with pytest.raises(ValueError, match="product_id"):
        part(product_id=" ")
    with pytest.raises(ValueError, match="description"):
        labor(description=" ")
    with pytest.raises(ValueError, match="description"):
        labor(description=2)
    assert labor(description="  Repair   brake ").description == "Repair brake"


@pytest.mark.parametrize("references", [(), ("a", "a"), ("",), (" a",), "a", {"a"}, None])
@pytest.mark.parametrize("kind", ["tax", "discount"])
def test_empty_duplicate_and_ambiguous_scopes_are_rejected(references: object, kind: str) -> None:
    with pytest.raises(ValueError, match=r"base_line_ids|scope_line_ids"):
        if kind == "tax":
            TaxLine("t", "Tax", 1600, references)  # type: ignore[arg-type]
        else:
            DiscountLine("d", "Coupon", 1, references)  # type: ignore[arg-type]


def test_nonexistent_or_noncharge_references_are_rejected() -> None:
    for target in ("missing", "t", "d"):
        with pytest.raises(ValueError, match="charge line"):
            quote(
                [
                    part(),
                    DiscountLine("d", "Coupon", 1, (target,)),
                    TaxLine("t", "Tax", 1600, ("part",)),
                ]
            )
        with pytest.raises(ValueError, match="charge line"):
            quote(
                [
                    part(),
                    DiscountLine("d", "Coupon", 1, ("part",)),
                    TaxLine("t", "Tax", 1600, (target,)),
                ]
            )


def test_over_discount_and_overlapping_discounts_cannot_make_charges_negative() -> None:
    with pytest.raises(ValueError, match="discount"):
        quote([part(), DiscountLine("d", "Coupon", 501, ("part",))])
    with pytest.raises(ValueError, match="discount"):
        quote(
            [
                part(),
                DiscountLine("d1", "Coupon", 300, ("part",)),
                DiscountLine("d2", "Coupon", 201, ("part",)),
            ]
        )
    with pytest.raises(ValueError, match="discount"):
        quote([part(unit_price_minor=0), DiscountLine("d", "Coupon", 1, ("part",))])


def test_duplicate_and_unknown_lines_and_empty_quotes_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        quote([part(), part()])
    for lines in ([], [TaxLine("t", "Tax", 0, ("part",))], [{"kind": "part"}], "part"):
        with pytest.raises(ValueError, match=r"lines|charge"):
            quote(lines)


def test_inputs_and_computed_history_are_deeply_immutable() -> None:
    scope = ["part"]
    discount = DiscountLine("d", "Coupon", 1, scope)  # type: ignore[arg-type]
    lines = [part(), discount]
    result = quote(lines)
    scope.append("missing")
    lines.clear()
    assert result.lines == (part(), discount)
    assert discount.scope_line_ids == ("part",)
    with pytest.raises(FrozenInstanceError):
        result.currency = "USD"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.totals.total_minor = 1  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        discount.amount_minor = 500  # type: ignore[misc]


def test_revision_returns_explicit_predecessor_and_successor_without_rewriting_history() -> None:
    original = quote()
    later = NOW + timedelta(hours=1)
    revision = original.revise(lines=[part()], quote_id="quote-2", now=later)
    assert original.superseded_at is None
    assert revision.predecessor == replace(original, superseded_at=later, superseded_by="quote-2")
    assert revision.predecessor.lines == original.lines
    assert revision.predecessor.totals == original.totals
    assert revision.predecessor.created_at == NOW
    assert revision.successor.quote_id == "quote-2"
    assert revision.successor.revises_quote_id == "quote-1"
    assert revision.successor.version == 2
    assert revision.successor.created_at == later
    assert revision.successor.superseded_at is None
    assert revision.successor.totals.total_minor == 500
    for field in ("organization_id", "location_id", "order_id", "currency"):
        assert getattr(revision.successor, field) == getattr(original, field)
    third = revision.successor.revise(lines=[labor()], now=later)
    assert third.successor.version == 3
    assert third.successor.revises_quote_id == "quote-2"
    assert UUID(third.successor.quote_id).version == 7
    with pytest.raises(ValueError, match="superseded"):
        revision.predecessor.revise(lines=[labor()], now=later)


def test_failed_revision_leaves_original_unchanged() -> None:
    original = quote()
    with pytest.raises(ValueError, match="duplicate"):
        original.revise(lines=[part(), part()], now=NOW)
    assert original.superseded_at is None
    assert original.version == 1
    with pytest.raises(ValueError, match="quote_id"):
        original.revise(lines=[part()], quote_id="quote-1", now=NOW)
    with pytest.raises(ValueError, match="before"):
        original.revise(lines=[part()], now=NOW - timedelta(seconds=1))


def test_quote_generates_uuid7_and_normalizes_aware_timestamps_to_utc() -> None:
    result = quote(quote_id=None, now=NOW.astimezone(timezone(timedelta(hours=-6))))
    assert UUID(result.quote_id).version == 7
    assert result.created_at == NOW
    assert result.created_at.tzinfo is UTC
    with pytest.raises(ValueError, match="timezone"):
        quote(now=datetime(2026, 10, 13))
    with pytest.raises(ValueError, match="timestamp"):
        quote(now="2026-10-13")
    automatic = quote(quote_id=None, now=None)
    assert automatic.created_at.tzinfo is UTC


def test_reconstruction_cannot_bypass_quote_invariants() -> None:
    original = quote()
    for changes in (
        {"version": True},
        {"version": 0},
        {"version": 2},
        {"revises_quote_id": "old"},
        {"superseded_at": NOW},
        {"superseded_by": "next"},
        {"superseded_at": NOW, "superseded_by": "quote-1"},
    ):
        with pytest.raises(ValueError):
            replace(original, **changes)


def test_unequal_discount_weights_are_visible_in_each_tax_subset() -> None:
    result = quote(
        [
            part("a", quantity=1, unit_price_minor=1),
            part("b", quantity=1, unit_price_minor=2),
            part("c", quantity=1, unit_price_minor=4),
            DiscountLine("discount", "Coupon", 3, ("a", "b", "c")),
            TaxLine("tax-a", "Tax", 10000, ("a",)),
            TaxLine("tax-b", "Tax", 10000, ("b",)),
            TaxLine("tax-c", "Tax", 10000, ("c",)),
        ]
    )
    # Exact shares 3/7, 6/7, 12/7 allocate 0, 1, 2 after largest remainders.
    amounts = dict(result.totals.line_amounts)
    assert [amounts[f"tax-{line_id}"] for line_id in ("a", "b", "c")] == [1, 1, 2]


def test_scoped_tax_exposes_generated_discount_allocations() -> None:
    random = Random(104)
    for _ in range(250):
        gross = {line_id: random.randint(0, 10000) for line_id in ("a", "b", "c")}
        total = sum(gross.values())
        if total == 0:
            continue
        discount = random.randint(1, total)
        exact = {line_id: Fraction(discount * value, total) for line_id, value in gross.items()}
        allocation = {
            line_id: value.numerator // value.denominator for line_id, value in exact.items()
        }
        ranks = sorted(
            exact, key=lambda line_id: (-(exact[line_id] - allocation[line_id]), line_id)
        )
        for line_id in ranks[: discount - sum(allocation.values())]:
            allocation[line_id] += 1
        lines = [
            part(line_id, quantity=1, unit_price_minor=value) for line_id, value in gross.items()
        ]
        result = quote(
            [
                *lines,
                DiscountLine("d", "Coupon", discount, tuple(reversed(gross))),
                *(TaxLine(f"tax-{line_id}", "Tax", 10000, (line_id,)) for line_id in gross),
            ]
        )
        amounts = dict(result.totals.line_amounts)
        for line_id in gross:
            assert amounts[f"tax-{line_id}"] == gross[line_id] - allocation[line_id]
