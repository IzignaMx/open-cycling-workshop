# V0.2 Increment 2 · Task 4 · Quote domain

## Scope and traceability

- FR-SVC-007: immutable typed labor/part/tax/discount lines and computed totals.
- FR-SVC-008 and BR-004: append a new quote version, preserving predecessor values
  and explicitly recording supersession and lineage.
- NFR-009: explicit quote-wide currency with no implicit currency conversion.
- Arithmetic decision: [quote arithmetic and history ADR](../02-technical-architecture/2026-10-13-quote-arithmetic-and-history.md).

This is an independent pure-domain increment based on `b1df504`. The inventory
API Task 3 was merged through PR #22 on 2026-10-14 and is not a dependency of this
in-memory calculation. No quote persistence/migrations, REST/authorization,
sync, UI or payment behavior is claimed. Tasks 5–12 remain open. Stable release
versions and physical/manual qualification gates are unchanged.

## Evidence

- Test-first red: a package-availability assertion failed before production code
  existed; the full behavior suite then failed collection because the quote
  domain did not exist. Those are missing-feature evidence, not passing tests.
- Focused green: 106 quote-domain tests, including 3,660 exhaustive labor boundary
  cases, 150 large-integer generated cases, 250 generated discount/tax cases,
  250 per-charge discount-allocation cases,
  and 240 mixed-line/scope permutations within property tests.
- Full Python suite: 282 passed, one PostgreSQL integration skip because
  `OCWP_TEST_DATABASE_URL` is absent.
- Python lint/format and strict mypy: passed (66 source files).
- Independent review: no implementation defects. Reviewer verified 3,000 exact
  allocation cases. Added unequal-weight per-charge tax tests from its suggestion.
- Aggregate local qualification: 21 checks passed, zero failures, five explicit
  environment blockers. Repository contract, real HTTP SQLite smoke, Ruff/mypy,
  frontend lint/format/typechecks, 72 core tests, API client tests, OpenAPI/client
  drift checks and production PWA build passed.
- Hosted exact-head CI, Security and DCO are checked after draft publication;
  the pull request records the final head, synthetic merge/tree and workflow
  artifact evidence. The status below is the pre-publication checkpoint.

The local environment has no PostgreSQL/Docker runtime. Chromium navigation is
blocked by managed policy and is not bypassed. Existing database/browser runtime
gates will be checked in hosted CI; physical Tier 1 evidence remains manual.

## Versioning and next steps

Changelog entry is under Unreleased. Python `0.1.0.dev0` and workspace
`0.1.0-dev.0` remain development baselines. A maintainer-reviewed SemVer release
PR governs stable version/tag publication. Neither opening this draft nor passing
CI is authorization to merge, tag or deploy it.

Next dependent work must add authorization evidence, atomic revision persistence
with optimistic concurrency, and transport validation before exposing quotes.
Read current `main` and migration head before allocating any future migration;
inventory migration 0007 is present. The subsequently prioritized
[access-administration increment](2026-10-14-access-administration.md) uses 0008,
following 0007; the next quote-table migration is 0009, following 0008. This
supersedes the earlier quote reservation of 0008 without changing the historical
pure-domain evidence or creating an empty reserved migration.

Current migration reservation (2026-10-14): bounded server baseline persistence implements 0009 after 0008. The still-unimplemented quote migration is now 0010 after 0009; earlier reservation statements above are historical.
