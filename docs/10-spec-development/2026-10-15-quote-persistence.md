# Quote persistence · repository-first evidence

## Architecture acceptance

The coordinator accepted the independently reviewed
[quote persistence/application ADR](../02-technical-architecture/2026-10-15-quote-persistence-and-online-command-boundary.md)
on 2026-10-15 for **repository-first Increment 2 Task 6 only**. The inspected pure
quote source was `9d8dcd5f80d036f0fb7a0407584bb761dad83e95`; merged main
`d9381808c61b4682844666eb62967ccbf9afc5b9` has the identical tree
`ac1e5985e7bb89a274755e9ab0bcb2d1ec35778a` and is the implementation base.

- Final reviewed proposal SHA-256:
  `01f27bd760033cda7c9fa92f1420d7c9ba8b5a123be736bc9d2826761023b250`.
- Independent architecture review report SHA-256:
  `2be3327b843e3be9e7471fc0c4662b9c8d8de4364a36fa0e0ff20fcfc4461758`.
- All eight findings closed: complete effect associations, no mixed old server
  writers at enrollment, exact monotone authority narrowing, compact bounded
  current-order response, per-dimension candidate limits, explicit first-owner
  establishment rather than bootstrap widening, admission/proof separation and
  text-storage/catalog precision. Pure decision mode `initial` is not itself
  an order-transition instruction.
- Formatting, all five original local document links and whitespace checks
  passed on the reviewed proposal. Acceptance adds status/reference metadata;
  it does not qualify the future implementation.

## Implementation and qualification status

The first schema slice implements six registered tables: quote lineages,
revisions, typed lines, reference edges, decisions and terminal operations.
Migration `0012` is additive after `0011`; it preserves previous rows and grants,
uses scoped foreign keys and deferred root/head references, and guards immutable
history against update, delete, truncate and SQLite replacement. Only the lineage
head/version/sequence cursor is mutable. Reserved order-effect columns are not an
activation mechanism.

Observed test-first evidence: two missing-table failures before implementation;
a currency-NUL regression failed then passed; thirteen affected operator tests
failed until the existing cutover schema allowlist narrowly accepted `0012`.
Empty, old, unknown and multiple stamps still fail. No operator action ran.

- Schema tests: 84 passed, 84 skipped (83 unavailable PostgreSQL cases and one
  PostgreSQL-only TRUNCATE case on SQLite).
- Affected migration/cutover tests: 93 passed, 50 PostgreSQL skips.
- Independent schema review: no blocking finding; 159 passed, 107 explicit skips
  across its broader selected scope. Independent probes also confirmed UNIQUE
  and CHECK parity; those assertions are now retained in the schema suite.
- Frozen migration/ORM parity, scoped Ruff, mypy for four touched source files and
  whitespace checks passed. Generated PostgreSQL DDL is not live execution.

Repository/codecs and real PostgreSQL/restore fixtures are in progress, not
qualified by this schema checkpoint. Existing 243 quote tests, including the
unchanged original 106, remain exact-source regression requirements.

Reinspected base SQL head is `0011`; the candidate adds quote revision `0012`.
Authenticated local schema stays 7. This executor currently has no configured
PostgreSQL test URL or psql/postgres/docker binaries. Real migration, race and
restore qualification must run in the existing authorized hosted PostgreSQL
fixture; local skip counts cannot replace that evidence. No cloud database,
account, credential or persistent test service is to be created for this work.

## Scope retained

Only models/migration, strict bounded complete reconstruction, atomic repository
operations and their tests are authorized now. No route, capability catalog,
grant/adoption, synchronization, offline store, UI or operational enrollment is
activated. The accepted ADR's future application, all-ingress guard, mixed-server
writer and line-coverage gates remain open. The full durable Task 5, Task 8 and
quote/inventory journey are not complete.
