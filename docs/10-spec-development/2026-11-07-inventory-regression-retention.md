# Retain inventory pagination regression coverage

## Purpose and accepted baseline

The current runtime remains unchanged. This increment makes a bounded selection
of useful autonomous probes part of normal pytest discovery, rather than leaving
them only in ignored temporary evidence. Its deliverable is future regression
protection and a current source-bound checkpoint, not a new product feature or a
claim that the earlier 184-test round found a defect.

Base main is `6930675bbdd0bd45cfb853be7721fcfab82baf9c`, tree
`ef4feabd7a4ec383bf968a702ecfab48e589321a`. The [PR94 receipt](https://github.com/IzignaMx/open-cycling-workshop/pull/94)
and [main CI 42096624558](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/42096624558)
record accepted fresh-main evidence: Python 6,690 plus 58 exact skips, all 169
text cases and eight PostgreSQL cases, frontend 1,299, API one, aggregate 27/27,
browser 133 direct/133 aggregate, repetitions 20/9/5/10, expiry ten and kernel 14.
All ten checks/four ordinary workflows passed attempt one. Historical independent
review checked source/cleanup/bounded receipts and small artifact digests. Large
browser archives were not inspected. The receipt supersedes historical PR94
pending source entries, never the qualification of this new candidate.

## Scope and existing contract

[Bounded connected inventory visibility](../02-technical-architecture/2026-10-15-connected-inventory-read.md)
remains authoritative. FR-INV-002 per-location visibility and SEC-002 isolation
are tested only for current connected GET behavior. The canonical broader
FR-INV-002/R03-T005 task remains partial; retaining tests for a shipped read path
does not start V0.3 implementation or complete physical stock/location features.
Earlier workshop read privacy evidence remains at
[autonomous read boundaries](2026-11-05-autonomous-read-boundaries.md).

The invariant is complete scoped traversal without duplicates or omissions for
unchanged data, strict cursor progress, and no database effects from GET requests.
Live paging is intentionally not a snapshot: newer inserts require refresh and
older inserts may appear later. UTF-8/code-point ordering and canonical UTC
microsecond timestamps remain unchanged.

The retained file is
`services/platform/tests/inventory/test_inventory_pagination_regressions.py`.
Use existing fixtures and bounded deterministic seeds. Cover combinations of
Unicode scalar identifiers, timestamp extrema, variable page sizes and
interleaved foreign organization/product/location rows, then live insertion on
both sides of a cursor. Exact response identities, scope, cursor boundaries and
all-table snapshots strengthen the existing simple examples.

No production, schema, dependency, workflow, skip-ledger, public API or storage
change is needed. No ADR or migration is introduced. Policy observations such
as duplicate protocol members are not converted into acceptance criteria.
The prior temporary probe files are not asserted byte-identical to this maintained
selection; fresh tests and receipts must prove this exact source.

## Local verification and evidence

The documentation contract first failed in two cases against the old current
checkpoint. The retained tests pass without a production correction. Three
temporary in-memory fault experiments prove sensitivity, not existing bugs:
ascending identifier ordering fails all four cases, removal of the location
filter fails three with one unaffected control, and an inclusive cursor fails
all four. Production source remained unchanged throughout.

- Four maintained inventory cases passed with zero skips. Three deterministic
  traversals each use 28 target rows and 16 interleaved excluded rows; the fourth
  exercises live insertions on both sides of a cursor and refresh semantics.
- The complete nearest inventory suite passed 456 tests, with 64 existing
  PostgreSQL-environment skips and one existing warning.
- Independent review ran the retained tests and repository contracts together:
  199 passed, with one existing warning. It verified discovery, the fault
  receipts, all ten inventory artifact hashes and the unchanged runtime scope.
  Its wording correction distinguishes complete unchanged-data traversal from
  strict live cursor ordering; newer rows still require refresh.
- Full Python passed 6,068 tests, with 685 environment skips and 12 warnings,
  exit zero in 359.89 seconds. JUnit confirms all four new inventory cases and
  the new repository acceptance-boundary contract executed and passed. No skip
  exemption was added. Production and test source were frozen for this run;
  final documentation receipts are checked separately afterward.
- Final independent evidence review accepted the corrected scope and checked
  raw full-suite JUnit, five individually passing new cases, frozen test hashes
  and completed post-receipt verification: 199 passed with one existing warning.
- Ruff lint/format (395 files), mypy (126 source files), generated OpenAPI and
  TypeScript contracts, repository verifier, Prettier and whitespace checks
  passed. Dependencies were installed from unchanged frozen lockfiles.

The new test-file SHA256 is
`2b6239451f3f6dcb1c2ad6cad2a2372ded38ddacf214bd7f3c99f87ab7607b36`.
Local receipt files are under
`artifacts/persistent-regressions-20261107/`: `inventory/` contains the retained
test, nearest-suite and fault-sensitivity logs plus their hash manifest;
`coordinator/` contains the documentation RED, full Python log/JUnit and static
checks. These ignored artifacts are supporting evidence, not required test
inputs. Main was rechecked at the same base with all ten checks successful;
that confirms only the existing baseline.

Reproduce the retained scope with:

    .venv/bin/python -m pytest -q services/platform/tests/inventory/test_inventory_pagination_regressions.py

Normal collection and the existing complete-Python CI discover the file under
`services/platform/tests`; no manual opt-in or workflow modification is required.
Local tests use synthetic SQLite and in-process HTTP. They do not qualify actual
PostgreSQL collation/locking, browser behavior, native storage or concurrency.

## Unchanged gates

Physical T1–T8 and R01-T035 remain deferred, not accepted. OPS-GATE-006,
capacity/M2, deployment and complete V0.1 acceptance remain unchanged. No real
user-data restore, provider operation, account or credential change occurs.
SPENT40927223929 stays spent, UNKNOWN41011497919 stays unknown, and Pages is
unchanged. Publication requires applicable authorization; hosted results for
PR94 cannot be inherited by this new candidate.
