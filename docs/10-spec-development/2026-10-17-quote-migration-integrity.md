# Fixed PostgreSQL migration integrity qualification

Status: preparation; exact review and execution pending. The previous [four-case PostgreSQL result](2026-10-17-bounded-effects-null.md#verified-corrected-result) is closed independently on the recovered exact source. This batch selects three different existing cases without changing their bodies or product code.

## Exact scope

Select only `[postgres]` from these functions in `services/platform/tests/quotes/test_quote_effect_metadata.py`:

1. `test_legacy_populated_tuple_refuses_before_any_ddl`: begin at 0012, create an old populated effect tuple and dependencies, require refusal before any ALTER TABLE, retain the full prior snapshot and absence of all three new columns. Final revision must remain 0012. This is a synthetic structurally populated legacy tuple, not a claim of valid replay history.
2. `test_effect_version_constraint_retains_dependencies_and_immutability`: require invalid or incomplete version/effect tuples to fail, preserve referenced event/change/outbox rows, reject receipt mutation, and refuse downgrade without changing the snapshot. Final revision is 0013.
3. `test_upgrade_failure_rolls_back_all_added_columns`: inject failure after the second generated-column ALTER TABLE, require the whole snapshot and absence of all added columns to be restored, then perform the test's existing successful upgrade and verify generated metadata. Final revision is 0013. This verifies transaction rollback at that specific after-final-ALTER boundary, not every DDL failure point or logical backup restoration.

Require three fixed collected nodes, nine ordered passed phases, zero skips/errors, three distinct actual PostgreSQL schemas and the exact final revisions above. The original assertions prove intended exception paths and the intermediate rollback snapshot, including alembic_version.

## Observation and limits

Use a final-only observer depending on the isolated-schema fixture. It must not request the ordinary database fixture or intercept/call migration functions. Probe committed identity after each body and before schema disposal, on a separately closed connection. This avoids changing the intentional failure behavior and does not manufacture an upgrade-history receipt. Preserve actual PostgreSQL 18.4, psycopg 3.3.4, UTF8, fixed owned database and distinct scoped-schema checks.

Reuse the established aggregate 20-second workload, 1 CPU / 512 MiB worker and 1 CPU / 768 MiB database, real cancellation canary, bounded short traceback and independent cleanup. No larger timeout or output cap is needed. The test's internal successful upgrade after its synthetic rollback is part of this fixed existing case; a failed workflow is not retried.

Keep all previous consumed workflows and original failures intact. No deployment, real workshop data, API activation, concurrency or maximum capacity is included. Separate restore work needs PostgreSQL 18 client tools and must distinguish base metadata preservation from replay of a valid restored quote history. Those results remain pending.
