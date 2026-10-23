# Joint bounded-effects static verification

The joint schema 0013 candidate is source-prepared, with its schema/pure and
composition reviews recorded separately. Its immediate product base is the
corrected PostgreSQL 0012 source 9c07e224; earlier six-case evidence does not
qualify the new joint code. No local candidate imports or toolchain ran.

Use the same six-command static profile that passed run 39052034132, over the
new exact archived product/migration/test sources. The fixed source list now
contains 38 Python paths and 13 production roots with normal mypy import following.
Commands remain repository verification, Ruff check, Ruff format check, strict mypy,
OpenAPI freshness and generated-client freshness. The fixed report requires six
ordered nodes / 18 phases and zero errors/skips. This is a static profile: the owned
PostgreSQL container is unused overhead, and no schema migration is applied.

Keep the existing 20-second shared workload deadline, 1 CPU / 512 MiB worker,
1 CPU / 768 MiB database, output caps, source/image checks, descendant canary and
independent cleanup. Tool ceilings remain 2/3/3/12/6/2 seconds, not additive
allocations. A timeout/failure remains failed; no capacity inference follows.
Bounded standard tool output is retained with explicit truncation. No consumed
workflow is modified, and this new exact-source static workload runs once.

The profile restores the previously verified static guard/test pair rather than
adding a new selector framework. The PostgreSQL profile and its source-bound
identity receipts remain preserved on their consumed branch. Platform files
are byte-identical to the joint candidate snapshot; profile differences are
limited to test machinery, fixed lists, workflow and truthful documentation.

Actual results are pending. Prepared codec/metadata/service regressions,
PostgreSQL 0013, migration rollback, restore, concurrency and capacity are not
covered by static success. Full integration remains pending and main unchanged.
