# Fixed pure bounded-effects qualification

The product snapshot 2460fbc11577170ec7660bc75c237dfd5a905bcf/tree 326ff11ac86241c787ae8b0469b24968c867a748 passed the six static/contract commands in run 39061922896. Functional qualification remains separate.

Select exactly eighteen existing cases: seven nonparametrized codec tests, all nine combinations of the three byte-limit names with offsets -1/0/+1, and the model-DDL plus offline-migration-refusal tests. No test body or product code changes in this increment. The other 47 pure parameter cases remain unrun; PostgreSQL 0013 migration/runtime, rollback/restore, concurrency and capacity also remain pending.

Collection is bound to the ten fixed source functions, exact actual parameter values and canonical integer positions derived from those values. Do not predict pytest-generated IDs or treat pytest internal indices as semantic positions. Locked pytest 9.1.1 flattens direct parameter indices; the receipt instead derives each position from the fixed typed value lists. Captured IDs must be unique, bounded safe ASCII and attached to the correct fixed selector. The final report validates the same collection, the nine distinct index pairs and all 54 ordered setup/call/teardown phases, zero skips/errors, and closed fields. Bool indices are invalid. The unchanged 16 KiB success-report limit accommodates a conservative 15,103-byte bound including the new closed case_indices receipt; it remains a hard limit.

Use the proven containment and fixed one-shot workflow with the same 20-second aggregate workload, 1 CPU / 512 MiB worker, canary, output limits and independent cleanup. The owned PostgreSQL container remains unused environment overhead. No database URL or schema identity is injected for this pure/offline selection. DDL is compiled in memory and the offline migration request must refuse before a database bind; neither is live migration evidence.

Reuse the previously reviewed short-trace capture from fe30964b: --tb=short, --no-showlocals, --show-capture=no; retain only bounded synthetic test output after verified stop and client reap, before parsing the numeric failure marker. Keep the 16 KiB diagnostic, 24 KiB marker and 32 KiB specimen spool limits. Preserve failure and truncation explicitly; no retry or budget expansion makes a failed run qualified.

The exact source and guard changes require independent review. The operation is a new fixed small functional workload, not a repeat of the consumed maximum/profile experiments. The initial preparation status is superseded by the exact result below.

## Verified finite result

[Run 39063614879](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39063614879), number 1 / attempt 1, passed all 18 cases and 54 ordered phases with zero errors or skips. Exact source commit 0b8e3ea96d11362b7d65477bb57038727691b818, tree ea1c25d9320b548f78e656e4afd8f5d0443b1d13. Artifact 12112502333 has SHA-256 64cca88e845b79f0f0df45420f4641579bc457306f4113ddda7b34e7e6805a55.

Independent evidence review confirmed collection identity, all nine boundary pairs, the 13,106-byte inner report, source identity, resource limits, cancellation canary, client reap and both container-absence receipts. Measured workload was 2.394 seconds, setup 1.959 seconds and supervisor elapsed time 4.692 seconds. Final worker peak was 90,959,872 bytes. Final worker/database CPU usage was 2,404,262 / 1,002,785 microseconds; those are lifetime totals, not solely test CPU. PostgreSQL was unused environment overhead.

The other 47 pure cases and new negative guard regressions remain unexecuted. This result does not prove live PostgreSQL 0013 migration, runtime, rollback, restore, concurrency or capacity. No product routes or real installation are activated.
