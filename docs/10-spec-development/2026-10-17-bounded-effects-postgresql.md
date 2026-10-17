# Fixed PostgreSQL 0013 bounded-effects qualification

Status: original preparation completed; the exact run failed as recorded below. Corrected qualification is separately pending. Product source is unchanged from the static-qualified snapshot 2460fbc11577170ec7660bc75c237dfd5a905bcf. The separate eighteen-case pure result is recorded in [its evidence note](2026-10-17-bounded-effects-pure.md).

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

## Preserved failed result

[Run 39064719886](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39064719886), number 1 / attempt 1, failed on commit f842b58e5cd7a3cb7038c3af4a141979fd9756de, tree c56e653bb35cf8ab13e5af1ab38686db0fba3fea. Artifact 12111704973, SHA-256 82db1c3f071aa874e617ac34a2b2cc20177df24b0b38f62b2d60a7762577511d, retains the complete 1,249-byte diagnostic transport. Pytest itself abbreviates the SQL repr within that output.

Four cases were collected. The first two passed; the third call failed its literal `ELSE` assertion after the initial refusal/no-ORM checks and the first CASE's count-guard checks. Nine phases were recorded, one failed, zero skips or collection/protocol errors. The fourth historical case was not run. No complete final service/PG identity receipt was retained in the artifact, so this failed batch does not qualify all four schemas or the historical migration.

Independent review verified the artifact and source identity, the real cancellation canary, worker stop before client reap and both container-absence receipts. Supervisor elapsed time was 8.919 seconds, setup 2.316 seconds and cancellation 0.126 seconds. Failure-path resource counters are last samples, not final totals. Worker last-sampled peak was 98,746,368 bytes and CPU 5,898,662 microseconds; PostgreSQL was 100,917,248 bytes and 2,685,413 microseconds. No timeout or resource-limit failure is reported.

The concrete failure is in the test's SQL spelling requirement. Product source uses SQLAlchemy `case(..., else_=None)`; locked SQLAlchemy 2.0.52 emits no ELSE clause for this value. [PostgreSQL 18 CASE semantics](https://www.postgresql.org/docs/18/functions-conditional.html#FUNCTIONS-CASE) return NULL when no WHEN matches and ELSE is absent. The separate [test-only correction](2026-10-17-bounded-effects-null.md) preserves this failure and all resource limits.
