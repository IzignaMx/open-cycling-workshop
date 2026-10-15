from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from fractions import Fraction
from itertools import permutations
from random import Random
from typing import Any

import pytest
from cycling_workshop.quotes.decisions import price_selection
from cycling_workshop.quotes.domain import (
    DiscountLine,
    LaborLine,
    PartLine,
    Quote,
    QuoteLine,
    TaxLine,
)

NOW = datetime(2026, 10, 15, tzinfo=UTC)


def part(line_id: str, amount_minor: int) -> PartLine:
    return PartLine(line_id, f"Part {line_id}", f"product-{line_id}", 1, amount_minor)


def quote(lines: list[QuoteLine] | tuple[QuoteLine, ...], *, currency: str = "MXN") -> Quote:
    return Quote.for_order(
        quote_id="quote-1",
        organization_id="org-1",
        location_id="loc-1",
        order_id="order-1",
        currency=currency,
        now=NOW,
        lines=lines,
    )


def snapshot(result: Any) -> dict[str, object]:
    return {
        "currency": result.currency,
        "approved_line_ids": result.approved_line_ids,
        "subtotal_minor": result.subtotal_minor,
        "discount_minor": result.discount_minor,
        "tax_minor": result.tax_minor,
        "total_minor": result.total_minor,
        "charges": tuple(
            (line.line_id, line.gross_minor, line.discount_minor, line.net_minor)
            for line in result.charges
        ),
        "discounts": tuple((line.line_id, line.allocations) for line in result.discounts),
        "taxes": tuple(
            (line.line_id, line.base_line_ids, line.amount_minor) for line in result.taxes
        ),
    }


def fraction_round(value: Fraction) -> int:
    rounded = value + Fraction(1, 2)
    return rounded.numerator // rounded.denominator


def fraction_oracle(original: Quote, selected: tuple[str, ...]) -> dict[str, object]:
    """Independent rational oracle; never imports production calculation helpers."""
    gross: dict[str, int] = {}
    for line in original.lines:
        if isinstance(line, LaborLine):
            gross[line.line_id] = fraction_round(
                Fraction(line.minutes * line.hourly_rate_minor, 60)
            )
        elif isinstance(line, PartLine):
            gross[line.line_id] = line.quantity * line.unit_price_minor
    net = gross.copy()
    allocations: dict[str, dict[str, int]] = {}
    for line in original.lines:
        if not isinstance(line, DiscountLine):
            continue
        base = sum(gross[line_id] for line_id in line.scope_line_ids)
        shares = {
            line_id: Fraction(line.amount_minor * gross[line_id], base)
            for line_id in line.scope_line_ids
        }
        integers = {
            line_id: amount.numerator // amount.denominator for line_id, amount in shares.items()
        }
        fractions = {line_id: amount - integers[line_id] for line_id, amount in shares.items()}
        ranked = sorted(shares, key=lambda line_id: (-fractions[line_id], line_id))
        for line_id in ranked[: line.amount_minor - sum(integers.values())]:
            integers[line_id] += 1
        for line_id, amount in integers.items():
            net[line_id] -= amount
        allocations[line.line_id] = integers
    selected_ids = tuple(sorted(selected))
    discounts = tuple(
        (
            discount_id,
            tuple((line_id, amounts[line_id]) for line_id in selected_ids if line_id in amounts),
        )
        for discount_id, amounts in sorted(allocations.items())
    )
    taxes = tuple(
        (
            line.line_id,
            tuple(line_id for line_id in selected_ids if line_id in line.base_line_ids),
            fraction_round(
                Fraction(
                    sum(net[line_id] for line_id in selected_ids if line_id in line.base_line_ids)
                    * line.rate_bps,
                    10000,
                )
            ),
        )
        for line in sorted(original.lines, key=lambda line: line.line_id)
        if isinstance(line, TaxLine)
    )
    subtotal = sum(gross[line_id] for line_id in selected_ids)
    discount = sum(gross[line_id] - net[line_id] for line_id in selected_ids)
    tax = sum(amount for _, _, amount in taxes)
    return {
        "currency": original.currency,
        "approved_line_ids": selected_ids,
        "subtotal_minor": subtotal,
        "discount_minor": discount,
        "tax_minor": tax,
        "total_minor": subtotal - discount + tax,
        "charges": tuple(
            (line_id, gross[line_id], gross[line_id] - net[line_id], net[line_id])
            for line_id in selected_ids
        ),
        "discounts": discounts,
        "taxes": taxes,
    }


def test_partial_selection_keeps_original_discount_and_recalculates_tax() -> None:
    original = quote(
        [
            part("a", 101),
            part("b", 100),
            DiscountLine("discount", "Coupon", 5, ("a", "b")),
            TaxLine("tax", "Tax", 1600, ("a", "b")),
        ]
    )
    assert original.totals.total_minor == 227
    assert snapshot(price_selection(original, ["b"])) == {
        "currency": "MXN",
        "approved_line_ids": ("b",),
        "subtotal_minor": 100,
        "discount_minor": 2,
        "tax_minor": 16,
        "total_minor": 114,
        "charges": (("b", 100, 2, 98),),
        "discounts": (("discount", (("b", 2),)),),
        "taxes": (("tax", ("b",), 16),),
    }


def test_full_selection_matches_every_original_monetary_total() -> None:
    original = quote(
        [
            LaborLine("labor", "Repair", 30, 1001),
            PartLine("part", "Part", "product", 2, 250),
            DiscountLine("d2", "Second coupon", 11, ("labor",)),
            DiscountLine("d1", "Coupon", 71, ("part", "labor")),
            TaxLine("t2", "Second tax", 2500, ("part",)),
            TaxLine("t1", "Tax", 1600, ("part", "labor")),
        ],
        currency="JPY",
    )
    result = price_selection(original, ["part", "labor"])
    assert result.currency == "JPY"
    assert result.approved_line_ids == ("labor", "part")
    for name in ("subtotal_minor", "discount_minor", "tax_minor", "total_minor"):
        assert getattr(result, name) == getattr(original.totals, name)
    assert snapshot(result) == fraction_oracle(original, ("part", "labor"))


def test_empty_selection_keeps_original_discount_and_tax_identities() -> None:
    original = quote(
        [
            part("a", 100),
            part("b", 100),
            DiscountLine("d2", "Coupon", 20, ("b",)),
            DiscountLine("d1", "Coupon", 10, ("a", "b")),
            TaxLine("t2", "Tax", 1600, ("a",)),
            TaxLine("t1", "Tax", 0, ("b",)),
        ]
    )
    expected = {
        "currency": "MXN",
        "approved_line_ids": (),
        "subtotal_minor": 0,
        "discount_minor": 0,
        "tax_minor": 0,
        "total_minor": 0,
        "charges": (),
        "discounts": (("d1", ()), ("d2", ())),
        "taxes": (("t1", (), 0), ("t2", (), 0)),
    }
    assert snapshot(price_selection(original, [])) == expected
    assert snapshot(price_selection(original, ())) == expected


def test_lexical_discount_tie_does_not_move_to_selected_charge() -> None:
    for scope in permutations(("a", "b")):
        lines: list[QuoteLine] = [part("a", 1), part("b", 1), DiscountLine("d", "Coupon", 1, scope)]
        for ordering in permutations(lines):
            original = quote(ordering)
            result = price_selection(original, ["b"])
            assert result.discount_minor == 0
            assert result.total_minor == 1
            assert snapshot(result)["discounts"] == (("d", (("b", 0),)),)
            assert snapshot(price_selection(original, ["a"]))["charges"] == (("a", 1, 1, 0),)


def test_overlapping_discounts_use_original_gross_for_every_term() -> None:
    original = quote(
        [
            part("a", 100),
            part("b", 100),
            DiscountLine("d1", "Restricted", 30, ("a",)),
            DiscountLine("d2", "Shared", 20, ("a", "b")),
            TaxLine("t1", "Selected tax", 1000, ("b",)),
            TaxLine("t2", "Unselected tax", 1600, ("a",)),
        ]
    )
    result = price_selection(original, ["b"])
    assert snapshot(result)["charges"] == (("b", 100, 10, 90),)
    assert snapshot(result)["discounts"] == (("d1", ()), ("d2", (("b", 10),)))
    assert snapshot(result)["taxes"] == (("t1", ("b",), 9), ("t2", (), 0))
    assert result.total_minor == 99


def test_each_tax_rounds_once_on_selected_base_without_per_charge_tax() -> None:
    original = quote(
        [
            part("a", 1),
            part("b", 1),
            part("c", 1),
            TaxLine("t2", "Tax", 5000, ("c", "b", "a")),
            TaxLine("t1", "Tax", 5000, ("a", "b", "c")),
        ]
    )
    result = price_selection(original, ["b", "a"])
    assert original.totals.tax_minor == 4
    assert result.tax_minor == 2
    assert result.total_minor == 4
    assert snapshot(result)["taxes"] == (("t1", ("a", "b"), 1), ("t2", ("a", "b"), 1))


def test_complementary_selections_need_not_add_to_original_rounded_tax() -> None:
    original = quote([part("a", 1), part("b", 1), TaxLine("t", "Tax", 5000, ("a", "b"))])
    left = price_selection(original, ["a"])
    right = price_selection(original, ["b"])
    assert original.totals.tax_minor == 1
    assert left.tax_minor == right.tax_minor == 1
    assert left.tax_minor + right.tax_minor != original.totals.tax_minor


@pytest.mark.parametrize(
    ("rate_bps", "expected_tax"),
    [(0, 0), (1, 0), (4999, 0), (5000, 1), (5001, 1), (9999, 1), (10000, 1)],
)
def test_tax_half_up_and_rate_boundaries(rate_bps: int, expected_tax: int) -> None:
    original = quote([part("a", 1), part("b", 1), TaxLine("t", "Tax", rate_bps, ("a", "b"))])
    assert price_selection(original, ["a"]).tax_minor == expected_tax


def test_selected_zero_gross_charge_keeps_zero_shares_and_tax_base() -> None:
    original = quote(
        [
            part("free", 0),
            part("paid", 1),
            DiscountLine("d", "Coupon", 1, ("free", "paid")),
            TaxLine("t", "Tax", 10000, ("free", "paid")),
        ]
    )
    result = price_selection(original, ["free"])
    assert result.approved_line_ids == ("free",)
    assert result.total_minor == 0
    assert snapshot(result)["charges"] == (("free", 0, 0, 0),)
    assert snapshot(result)["discounts"] == (("d", (("free", 0),)),)
    assert snapshot(result)["taxes"] == (("t", ("free",), 0),)
    paid = price_selection(original, ["paid"])
    assert paid.approved_line_ids == ("paid",)
    assert snapshot(paid)["charges"] == (("paid", 1, 1, 0),)
    assert paid.total_minor == 0


def test_all_zero_gross_quote_and_empty_selection_are_defined() -> None:
    original = quote(
        [
            part("part", 0),
            LaborLine("labor", "Free repair", 1, 0),
            TaxLine("tax", "Tax", 10000, ("part", "labor")),
        ]
    )
    for selection in [[], ["part"], ["part", "labor"]]:
        result = price_selection(original, selection)
        assert result.total_minor == 0
        assert snapshot(result) == fraction_oracle(original, tuple(selection))


def test_labor_is_rounded_at_each_original_charge_boundary() -> None:
    original = quote(
        [
            LaborLine("a", "Repair", 1, 30),
            LaborLine("b", "Repair", 1, 30),
            LaborLine("c", "Repair", 1, 29),
            TaxLine("t", "Tax", 10000, ("a", "b", "c")),
        ]
    )
    result = price_selection(original, ["c", "b", "a"])
    assert snapshot(result)["charges"] == (("a", 1, 0, 1), ("b", 1, 0, 1), ("c", 0, 0, 0))
    assert result.subtotal_minor == 2
    assert result.tax_minor == 2


def test_arbitrary_precision_above_binary_float_exact_integer_range() -> None:
    original = quote(
        [
            PartLine("a", "Part A", "product-a", 7, 2**70 + 1),
            LaborLine("b", "Repair", 61, 2**63 + 31),
            part("c", 2**53 + 1),
            DiscountLine("d1", "Coupon", 2**54 + 1, ("a", "b", "c")),
            DiscountLine("d2", "Coupon", 2**53 + 7, ("a", "b")),
            TaxLine("t", "Tax", 3333, ("a", "b", "c")),
        ]
    )
    for selection in [("a",), ("b", "c"), ("a", "b", "c")]:
        result = price_selection(original, selection)
        assert snapshot(result) == fraction_oracle(original, selection)
        for name in ("subtotal_minor", "discount_minor", "tax_minor", "total_minor"):
            assert type(getattr(result, name)) is int
        assert result.total_minor > 2**53
        for charge in result.charges:
            assert all(
                type(getattr(charge, name)) is int
                for name in ("gross_minor", "discount_minor", "net_minor")
            )
        for discount in result.discounts:
            assert all(type(amount) is int for _, amount in discount.allocations)
        assert all(type(tax.amount_minor) is int for tax in result.taxes)


def test_input_scope_and_selection_permutations_are_canonical() -> None:
    expected = None
    for scope in permutations(("a", "b", "c")):
        lines: list[QuoteLine] = [
            part("a", 101),
            part("b", 100),
            part("c", 99),
            DiscountLine("d", "Coupon", 7, scope),
            TaxLine("t", "Tax", 1600, tuple(reversed(scope))),
        ]
        for ordering in permutations(lines):
            original = quote(ordering)
            for selection in [("c", "a"), ("a", "c")]:
                result = price_selection(original, selection)
                if expected is None:
                    expected = result
                assert result == expected
                assert result.approved_line_ids == ("a", "c")
                assert snapshot(result) == fraction_oracle(original, selection)


def test_generated_valid_overlapping_discounts_match_independent_fraction_oracle() -> None:
    random = Random(20261015)
    for case in range(180):
        ids = tuple(chr(ord("a") + i) for i in range(random.randint(3, 6)))
        lines: list[QuoteLine] = []
        gross: dict[str, int] = {}
        for index, line_id in enumerate(ids):
            line: LaborLine | PartLine
            if index == 0:
                line = LaborLine(
                    line_id, "Repair", random.randint(1, 240), random.randint(10000, 10**9)
                )
                gross[line_id] = fraction_round(Fraction(line.minutes * line.hourly_rate_minor, 60))
            else:
                amount = random.randint(100, 10**9) if index < 2 or case % 3 else 0
                line = part(line_id, amount)
                gross[line_id] = amount
            lines.append(line)
        discount_count = random.randint(2, 4)
        for index in range(discount_count):
            # All discounts overlap on a/b. The bound leaves each positive charge
            # ample room even after each independently rounded allocation.
            scope = (*ids[:2], *(line_id for line_id in ids[2:] if random.choice([False, True])))
            amount = random.randint(
                1, sum(gross[line_id] for line_id in scope) // (4 * discount_count)
            )
            lines.append(DiscountLine(f"d{index}", "Coupon", amount, scope))
        for index in range(random.randint(1, 3)):
            scope = tuple(random.sample(ids, random.randint(1, len(ids))))
            lines.append(TaxLine(f"t{index}", "Tax", random.randint(0, 10000), scope))
        # Construction must succeed: invalid overlaps are not silently discarded.
        original = quote(lines)
        complete = fraction_oracle(original, ids)
        for name in ("subtotal_minor", "discount_minor", "tax_minor", "total_minor"):
            assert complete[name] == getattr(original.totals, name)
        partial = tuple(random.sample(ids, random.randint(0, len(ids))))
        for selection in [(), partial, ids]:
            result = price_selection(original, selection)
            assert snapshot(result) == fraction_oracle(original, selection), (case, selection)
            assert (
                result.subtotal_minor - result.discount_minor + result.tax_minor
                == result.total_minor
            )
            assert all(charge.net_minor >= 0 for charge in result.charges)
        random.shuffle(lines)
        assert price_selection(quote(lines), tuple(reversed(partial))) == price_selection(
            original, partial
        )


@pytest.mark.parametrize(
    "selection",
    [
        "a",
        {"a"},
        frozenset({"a"}),
        {"a": True},
        None,
        1,
        True,
        (value for value in ["a"]),
        ["a", "a"],
        ("a", "a"),
        ["missing"],
        ["d"],
        ["t"],
        ["a", "missing"],
        [""],
        [" a"],
        ["a "],
        ["two ids"],
        [1],
        [True],
        [None],
        [["a"]],
    ],
)
def test_invalid_selection_containers_ids_duplicates_and_noncharges_are_rejected(
    selection: object,
) -> None:
    original = quote(
        [
            part("a", 100),
            part("b", 100),
            DiscountLine("d", "Coupon", 1, ("a",)),
            TaxLine("t", "Tax", 0, ("b",)),
        ]
    )
    before = original.totals
    with pytest.raises(ValueError):
        price_selection(original, selection)  # type: ignore[arg-type]
    assert original.totals == before
    assert price_selection(original, ["a"]).total_minor == 99


def test_result_copies_selection_and_every_nested_value_is_immutable() -> None:
    original = quote(
        [
            part("b", 100),
            part("a", 101),
            DiscountLine("d", "Coupon", 5, ("b", "a")),
            TaxLine("t", "Tax", 1600, ("b", "a")),
        ]
    )
    selection = ["b", "a"]
    result = price_selection(original, selection)
    before = snapshot(result)
    original_lines, original_totals = original.lines, original.totals
    selection.clear()
    assert snapshot(result) == before
    assert original.lines == original_lines
    assert original.totals == original_totals
    for collection in (result.approved_line_ids, result.charges, result.discounts, result.taxes):
        assert type(collection) is tuple
    assert type(result.discounts[0].allocations) is tuple
    assert all(type(allocation) is tuple for allocation in result.discounts[0].allocations)
    assert type(result.taxes[0].base_line_ids) is tuple
    for target, field in [
        (result, "total_minor"),
        (result.charges[0], "gross_minor"),
        (result.discounts[0], "allocations"),
        (result.taxes[0], "amount_minor"),
    ]:
        with pytest.raises(FrozenInstanceError):
            setattr(target, field, 999)
    assert hash(result) == hash(price_selection(original, ["a", "b"]))
    assert snapshot(result) == before
