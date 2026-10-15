"""Complete supplied quote histories, without persistence or concurrency claims."""

from __future__ import annotations

from dataclasses import dataclass, replace

from cycling_workshop.quotes.domain import PartLine, Quote, QuoteLine


@dataclass(frozen=True, slots=True)
class QuoteHistory:
    revisions: tuple[Quote, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.revisions, (list, tuple)) or not self.revisions:
            raise ValueError("history requires a nonempty quote sequence")
        revisions = tuple(self.revisions)
        seen_ids: set[str] = set()
        retired: set[str] = set()
        prior_lines: dict[str, QuoteLine] = {}
        for index, quote in enumerate(revisions):
            if type(quote) is not Quote or quote.version != index + 1:
                raise ValueError("history requires contiguous typed revisions starting at one")
            if replace(quote) != quote or any(replace(line) != line for line in quote.lines):
                raise ValueError("history contains invalid quote snapshots")
            if quote.quote_id in seen_ids:
                raise ValueError("history revision IDs must be unique")
            seen_ids.add(quote.quote_id)
            root = revisions[0]
            if (quote.organization_id, quote.location_id, quote.order_id, quote.currency) != (
                root.organization_id,
                root.location_id,
                root.order_id,
                root.currency,
            ):
                raise ValueError("history scope and currency cannot change")
            if index:
                previous = revisions[index - 1]
                if (
                    quote.revises_quote_id != previous.quote_id
                    or previous.superseded_by != quote.quote_id
                    or previous.superseded_at != quote.created_at
                ):
                    raise ValueError("history links and supersession times must match")
            current_lines = {line.line_id: line for line in quote.lines}
            if retired.intersection(current_lines):
                raise ValueError("retired line identity cannot be reused")
            for line_id, line in current_lines.items():
                previous_line = prior_lines.get(line_id)
                if previous_line is not None and (
                    type(previous_line) is not type(line)
                    or (
                        isinstance(previous_line, PartLine)
                        and isinstance(line, PartLine)
                        and previous_line.product_id != line.product_id
                    )
                ):
                    raise ValueError("retained line kind and product cannot change")
            retired.update(prior_lines.keys() - current_lines.keys())
            prior_lines = current_lines
        if revisions[-1].superseded_at is not None:
            raise ValueError("history must include its unsuperseded head")
        object.__setattr__(self, "revisions", revisions)

    @property
    def lineage_id(self) -> str:
        return self.revisions[0].quote_id

    @property
    def head(self) -> Quote:
        return self.revisions[-1]
