# ADR · Quote arithmetic and immutable revisions

- Date: 2026-10-13
- Status: Accepted for V0.2 Increment 2 Task 4
- Requirements: FR-SVC-007, FR-SVC-008, BR-004, NFR-009
- Implementation: `services/platform/src/cycling_workshop/quotes/domain.py`

## Context

The increment plan requires typed labor, part, tax and discount lines; integer
minor-unit money; ordering-independent totals; and appended quote revisions.
The normative specifications do not choose rate units, rounding rules, discount
allocation or tax bases. These ordinary technical choices need a deterministic
contract before persistence, authorization, REST or offline drafting are added.

## Decision

### Input and money boundaries

A quote has explicit organization, location, order and currency context. All its
lines use that currency; amounts never mix currencies or perform conversion.
Currency is a three-uppercase-ASCII-letter identifier, validated for shape only.
Currency catalog membership, allowed workshop currencies and their major/minor
unit exponents belong to later configuration/presentation boundaries. The domain
never assumes that every currency has two decimal places.

Money, quantities, minutes and basis points accept exact Python integers only.
Floats (including integral-looking floats), booleans, decimal objects, numeric
strings and implicit coercion are rejected. Arbitrary precision prevents local
integer overflow; a future JSON/client boundary must add an explicit safe integer
or decimal-string transport contract rather than silently converting to floats.

Line identifiers must be unique within a revision. IDs cannot be blank or contain
whitespace. Quote IDs default to UUIDv7; caller-supplied IDs follow the existing
domain convention of nonblank identifiers. Persistence/sync will enforce their
external UUIDv7 contract. Descriptions are normalized nonblank snapshots; product
IDs are references, and prices are immutable snapshots, not live catalog lookups.
At least one labor or part line is required. Zero prices are permitted.

### Calculation phases

1. Labor takes positive whole `minutes` and nonnegative `hourly_rate_minor`.
   `minutes × hourly_rate_minor / 60` is rounded half up to a minor unit once per
   labor line. Parts use positive whole `quantity × unit_price_minor` exactly.
2. A discount takes a positive `amount_minor` and an explicit nonempty set of
   labor/part IDs (`scope_line_ids`). No wildcard, percentage, self-reference,
   tax-on-discount cycle or implicit scope is inferred. The amount is allocated
   proportionally to the original rounded charge amounts. Integer floor shares
   are followed by largest-remainder allocation; equal remainders use lexical
   line ID order. Every minor unit is conserved. Each discount uses original gross
   weights, so multiple discounts do not depend on input order. Reject a discount
   above its scoped subtotal, or overlapping discounts that make any charge's
   net amount negative. Do not silently cap, redistribute or reorder them.
3. A tax takes integer `rate_bps` between 0 and 10,000 inclusive and explicit
   `base_line_ids` referencing labor/part lines only. Sum those lines' net amounts
   after all discounts, multiply by `rate_bps / 10000`, then round half up once
   per tax line. Taxes do not compound. Distinct tax lines may share a base.
4. Total = rounded charge subtotal − fixed discounts + rounded taxes. Per-line
   results contain positive charge/tax amounts and negative discount amounts.
   Results are stored in canonical ID order; presentation order is preserved in
   the immutable input lines. Totals cannot be supplied by a caller.

These are quote-calculation primitives, not jurisdiction-specific fiscal policy,
a tax-compliance claim or a payment implementation. Inclusive/compound taxes,
fractional quantities, percentage discounts and other policies need separate
specification and tests before extension. Fiscal rules remain plugin concerns.

### History

`Quote.for_order(...)` creates version 1. `quote.revise(...)` computes a new quote
with a fresh ID, the same order/scope/currency, `version + 1`, and explicit
`revises_quote_id`. It returns a `QuoteRevision` containing both the predecessor
with `superseded_at`/`superseded_by` and the appended successor. The original
Python object remains unchanged, and the returned predecessor preserves every
financial value, line and creation timestamp. Input collections are copied to
immutable tuples. A failed revision changes neither object.

Timezone-aware timestamps normalize to UTC. Revision time cannot precede the
previous creation time; equal timestamps are allowed because version, not wall
clock time, orders revisions. A marked superseded predecessor cannot be revised.
The future repository must atomically persist both returned records, enforce
unique revision/order lineage, and reject stale versions under a transaction.
A pure function cannot know that a stale immutable snapshot was already revised
elsewhere. This task does not claim persistence or concurrent-write protection.

## Consequences and verification

The arithmetic is deterministic using integers only, independent of line and
scope order, and portable to a client using the same explicit algorithm.
Largest-remainder ties depend on stable IDs, not array position. A mathematically
redistributable combination of overlapping discounts may still be rejected if
its independently computed allocations overdraw one charge; this conservative
rule is intentional and must be surfaced by a future editor.

Property tests use exhaustive minute/rate boundary cases and seeded generated
inputs with an independent exact `Fraction` oracle. All five-line permutations,
reference permutations, mixed taxes/discounts, zero-priced lines, invalid values,
immutability and revision failure paths are covered. No third-party property
framework or runtime dependency is required.
