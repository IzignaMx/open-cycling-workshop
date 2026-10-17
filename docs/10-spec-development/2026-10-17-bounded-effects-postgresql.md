# Fixed PostgreSQL 0013 bounded-effects qualification

Status: preparation; exact review and execution pending. Product source is unchanged from the static-qualified snapshot 2460fbc11577170ec7660bc75c237dfd5a905bcf. The separate eighteen-case pure result is recorded in [its evidence note](2026-10-17-bounded-effects-pure.md).

## Four existing cases

Select only the PostgreSQL parametrization of these existing functions, in order:

1. `test_quote_effect_metadata.py::test_seeded_upgrade_preserves_bytes_and_regenerates_counts`: start at 0012, retain seeded rows and raw JSON, migrate to 0013, inspect generated metadata, verify UTF-8 counts are regenerated and direct generated-column writes refuse.
2. `test_quote_bounded_effects_postgres.py::test_version_one_binds_both_measured_raw_copies_and_replays`: actual service creation/decision, version-one receipt, exact measured text and byte-count equality for both copies, then disabled-command replay with unchanged totals.
3. `test_quote_bounded_effects_postgres.py::test_both_raw_casts_share_both_count_guards_without_orm_materialization`: use a tiny injected ceiling to prove rejection before mapped JSON materialization and inspect both guarded SQL casts. This is a guard regression, not a capacity test.
4. `test_quote_historical_upgrade_postgres.py::test_valid_quote_only_0012_upgrade_replays_without_inventing_transition`: insert genuine valid quote-only history through reflected 0012 tables, preserve the original rows through migration, and reconstruct/replay through a fresh session at 0013 without inventing an order transition.

All paths are under `services/platform/tests/quotes/`. Require exactly four collected cases and twelve ordered passed setup/call/teardown phases, no skips/errors, four distinct disposable PostgreSQL schemas, the exact source identity and all resource/cleanup receipts.

## Preserve migration chronology

The old identity fixture depended on `database`, which upgrades and seeds the schema. It must not be reused for migration-owned cases: doing so would pre-upgrade them before their own initial 0012 step.

The selected observer depends only on the existing isolated-schema fixture. It forwards each test-requested Alembic upgrade unchanged and observes the actual committed revision afterward, using a separately closed read connection. It never requests a migration or seeds rows. Require observed revision sequences `[0012,0013]`, `[0013]`, `[0013]`, `[0012,0013]`, with a final 0013 observation before fixture cleanup. Actual PostgreSQL version, dialect, driver, UTF-8 settings and isolated schema are checked; command target strings alone are not revision evidence. The two migration test bodies independently assert their historical rows and effects.

## Bounded execution and remaining gates

Reuse the established 20-second aggregate workload, 1 CPU / 512 MiB worker, 1 CPU / 768 MiB PostgreSQL container, cancellation canary, bounded output and independent cleanup. Preparation has the existing separate job limit. Diagnostic output uses the existing bounded short traceback, without locals or environment dumps; a failure remains a failure and its evidence is retained. No consumed workflow is modified or rerun.

This batch changes no product code or selected test bodies. It does not prove DDL failure rollback, logical restore, lock contention, production latency, maximum capacity or physical Raspberry Pi operation. Those gates remain open, as do the other pure/negative cases. No routes, installed workshop or real permissions are activated.
