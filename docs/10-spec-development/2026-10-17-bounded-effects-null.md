# PostgreSQL guarded NULL assertion correction

Status: source preparation; exact review and corrected execution pending.

The [original four-case run](2026-10-17-bounded-effects-postgresql.md#preserved-failed-result) is preserved as failed. Its third case required an explicit ELSE token, although the locked SQLAlchemy compiler emits an implicit NULL fallback for `else_=None`. PostgreSQL supports that form. No product SQL correction is justified by this assertion failure.

Change only the existing paired raw-cast test. Associate each result label with its expected table, separate the single WHEN predicate from the THEN result, retain all four qualified count comparisons, and require the exact locked compiler's `CAST(expected_table.payload AS pg_catalog.text) END` result. This rejects wrong casts, extra branches and non-NULL fallbacks instead of simply dropping the old assertion.

Also capture the existing known scoped SELECT and its bound synthetic parameters during the failed replay. After the service rejection and rollback, execute that same read-only query on a separately closed connection. Require both stored counts to exceed the tiny injected ceiling and both raw result columns to be SQL NULL. This observes real PostgreSQL behavior without replacing the product query or materializing JSON through the ORM. Captured SQL/parameters are not added to artifacts; failure output remains the existing bounded short traceback without locals.

Preserve the no-materialization assertions, exact cast counts, note-text exclusion and expected service rejection. No product, migration, selected fixture, guard or dependency change is included. The same four selected cases and twelve-phase acceptance run under the established 20-second aggregate workload and unchanged worker/database limits. The original consumed workflow remains intact; the new source-bound workflow validates this concrete test correction once, without claiming an unmodified retry succeeded.

The fourth historical migration case remains unrun until the corrected batch proves it. Restore, DDL failure rollback, other negative cases, concurrency, capacity and activation remain separate pending gates. The additional SELECT is small synthetic verification work inside the existing deadline, not an extension of the deadline.
