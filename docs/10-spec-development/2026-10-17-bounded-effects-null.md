# PostgreSQL guarded NULL assertion correction

Status: corrected finite qualification passed; original failure retained.

The [original four-case run](2026-10-17-bounded-effects-postgresql.md#preserved-failed-result) is preserved as failed. Its third case required an explicit ELSE token, although the locked SQLAlchemy compiler emits an implicit NULL fallback for `else_=None`. PostgreSQL supports that form. No product SQL correction is justified by this assertion failure.

Change only the existing paired raw-cast test. Associate each result label with its expected table, separate the single WHEN predicate from the THEN result, retain all four qualified count comparisons, and require the exact locked compiler's `CAST(expected_table.payload AS pg_catalog.text) END` result. This rejects wrong casts, extra branches and non-NULL fallbacks instead of simply dropping the old assertion.

Also capture the existing known scoped SELECT and its bound synthetic parameters during the failed replay. After the service rejection and rollback, execute that same read-only query on a separately closed connection. Require both stored counts to exceed the tiny injected ceiling and both raw result columns to be SQL NULL. This observes real PostgreSQL behavior without replacing the product query or materializing JSON through the ORM. Captured SQL/parameters are not added to artifacts; failure output remains the existing bounded short traceback without locals.

Preserve the no-materialization assertions, exact cast counts, note-text exclusion and expected service rejection. No product, migration, selected fixture, guard or dependency change is included. The same four selected cases and twelve-phase acceptance run under the established 20-second aggregate workload and unchanged worker/database limits. The original consumed workflow remains intact; the new source-bound workflow validates this concrete test correction once, without claiming an unmodified retry succeeded.

At preparation, the fourth historical migration case was unrun; the corrected result below now proves that selected case. Restore, DDL failure rollback, other negative cases, concurrency, capacity and activation remain separate pending gates. The additional SELECT is small synthetic verification work inside the existing deadline, not an extension of the deadline.

## Verified corrected result

[Run 39065290465](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39065290465), number 1 / attempt 1, passed all four exact cases and twelve ordered phases, with zero errors or skips. Source commit 8a627dcffaaee5d63c5bf67436d2d534463b4eb7, tree d67ebe171d893ca87eff568ada80d2a8c221994a. Artifact 12112758073 has SHA-256 6d967e5a95bc8ec230915da3e526a82097a403a21b329d20af676ec9291a303c.

The complete receipt identifies four distinct disposable schemas on PostgreSQL 18.4 / psycopg 3.3.4 with UTF8 server/client encodings. Actual upgrade revision sequences were [0012,0013], [0013], [0013], [0012,0013], with all final probes closed at 0013. This includes both actual guarded NULL results and genuine valid quote-only historical migration/replay.

Measured workload was 6.98 seconds, setup 2.264 seconds and supervisor elapsed time 9.667 seconds. Final worker peak was 101,507,072 bytes and database peak 108,875,776 bytes. Final lifetime CPU was 6,363,980 / 3,065,894 microseconds respectively; observed workload CPU was 6,234,068 / 1,978,599 microseconds. Independent review verified the canary, source/image identity, client reap and both absence receipts. These small sequential cases do not establish capacity, concurrency or production latency.

After an execution-workspace replacement, the published source and public artifact were recovered read-only. All 775 source blobs and the original six-path manifest were verified against the exact tree; the final artifact digest matched. A fresh independent evidence review closed this result. Earlier local review prose was unavailable after that replacement and was not represented as re-read. The prior failed run remains failed; no run was repeated during recovery.

DDL refusal/rollback, logical restore, remaining pure and negative tests, broader integration and operational activation gates remain pending.
