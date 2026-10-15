from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from cycling_workshop.quotes.domain import LaborLine, PartLine, Quote
from cycling_workshop.quotes.history import QuoteHistory

NOW = datetime(2026, 10, 15, tzinfo=UTC)


def first() -> Quote:
    return Quote.for_order(
        organization_id="org",
        location_id="loc",
        order_id="order",
        quote_id="q1",
        currency="MXN",
        now=NOW,
        lines=[PartLine("part", "P", "product", 2, 100), LaborLine("labor", "L", 60, 100)],
    )


def test_history_validates_full_chain_and_keeps_original_snapshots():
    q = first()
    pair = q.revise(lines=list(reversed(q.lines)), quote_id="q2", now=NOW)
    chain = QuoteHistory([pair.predecessor, pair.successor])
    assert chain.lineage_id == "q1" and chain.head.quote_id == "q2"
    assert isinstance(chain.revisions, tuple)
    assert q.superseded_by is None
    again = pair.successor.revise(lines=pair.successor.lines, quote_id="q3", now=NOW)
    assert QuoteHistory((pair.predecessor, again.predecessor, again.successor)).head.version == 3


@pytest.mark.parametrize(
    "change",
    [
        "missing_root",
        "gap",
        "scope",
        "currency",
        "wrong_predecessor",
        "wrong_successor",
        "wrong_time",
        "unmarked_predecessor",
        "reused_id",
        "type_change",
        "product_change",
    ],
)
def test_invalid_history_rejected(change):
    q = first()
    pair = q.revise(lines=q.lines, quote_id="q2", now=NOW + timedelta(hours=1))
    old, new = pair.predecessor, pair.successor
    if change == "missing_root":
        items = (new,)
    elif change == "gap":
        items = (old, replace(new, version=3))
    elif change == "scope":
        items = (old, replace(new, location_id="other"))
    elif change == "currency":
        items = (old, replace(new, currency="USD"))
    elif change == "wrong_predecessor":
        items = (old, replace(new, revises_quote_id="other"))
    elif change == "wrong_successor":
        items = (replace(old, superseded_by="other"), new)
    elif change == "wrong_time":
        items = (replace(old, superseded_at=NOW), new)
    elif change == "unmarked_predecessor":
        items = (q, new)
    elif change == "reused_id":
        third = new.revise(lines=new.lines, quote_id="q3", now=NOW + timedelta(hours=1))
        fourth = third.successor.revise(
            lines=new.lines, quote_id="q1", now=NOW + timedelta(hours=1)
        )
        items = (old, third.predecessor, fourth.predecessor, fourth.successor)
    elif change == "type_change":
        items = (old, replace(new, lines=(LaborLine("part", "now labor", 60, 200),)))
    else:
        items = (old, replace(new, lines=(PartLine("part", "replacement", "different", 2, 100),)))
    with pytest.raises(ValueError):
        QuoteHistory(items)


def test_retired_line_cannot_reappear_but_new_id_can():
    q = first()
    second = q.revise(lines=(q.lines[1],), quote_id="q2", now=NOW)
    third = second.successor.revise(lines=q.lines, quote_id="q3", now=NOW)
    with pytest.raises(ValueError):
        QuoteHistory((second.predecessor, third.predecessor, third.successor))
    new_line = replace(q.lines[0], line_id="new-part")
    fixed = replace(third.successor, lines=(new_line, q.lines[1]))
    assert QuoteHistory((second.predecessor, third.predecessor, fixed)).head == fixed


def test_same_line_new_amount_is_new_revision_without_identity_change():
    q = first()
    revised = q.revise(lines=(replace(q.lines[0], quantity=3), q.lines[1]), quote_id="q2", now=NOW)
    assert QuoteHistory((revised.predecessor, revised.successor)).head.totals.total_minor == 400


@pytest.mark.parametrize("value", [(), "bad", {"q": "bad"}])
def test_history_requires_nonempty_typed_sequence(value):
    with pytest.raises(ValueError):
        QuoteHistory(value)
