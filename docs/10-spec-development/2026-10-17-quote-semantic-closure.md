# Finite quote service semantic closure

Status: test-only preparation. Designs and exact implementation have independent review; collection, static checks and hosted execution remain pending. No product behavior or schema change is proposed.

## Acceptance and bounded selection

This planned selection targets the remaining narrow service and retained-effect cases identified after the [32 PostgreSQL loader/writer cases and static closure](2026-10-17-quote-loader-writer-checks.md). It follows the complete integrity requirements in the [bounded-effects amendment](../02-technical-architecture/2026-10-17-bounded-quote-order-effects.md), especially sections 6 and 8. Existing PARTIAL, metadata, migration and tiny valid restore evidence remains separately source-bound.

The planned selection contains 40 cases in six independent PostgreSQL workloads:

- Seven actual service decision cases: APPROVE and REJECT with fresh exact replay, three initial enrollment refusals and two post-consent refusals. The latter use current CAS values and actual prior service consent; current order state also refuses, so these cases do not isolate a ledger-only branch. Complete retained rows and inventory remain unchanged on refusal.
- Two groups of seven valid-shaped, single-field retained-outbox mismatches cover all 14 projection fields. They use detached records loaded from real PostgreSQL and prove reconstruction rejection, rather than live SQL tampering behavior.
- Six cases cover exact event-note nullness (False and integer 1) plus four actual storage cases: external Text, compressed JSON and each one-sided raw-count oversize. The external Text case requires its actual storage signal and pre-hydration length refusal. The three retained-JSON cases require paired guarded NULL results. All four storage cases use small injected ceilings.
- Eight atomicity cases cover seven reached-write/serialization seams and synthetic commit-success/acknowledgement-loss. Fault hooks must call the real operation and establish that the intended row/result was reached. Fresh-session retained rows must match the baseline after rollback; fresh same-ID retry and replay must apply only once. Nontransactional sequence gaps are not rollback failures. Existing writer cases retain their separate generic change/outbox insertion evidence.
- Five small races cover same-operation same/changed proof, distinct decisions and authority revocation while a new decision or exact replay waits. Each requires the actual contender's PostgreSQL lock wait against the intended blocker, then complete outcome/row assertions. Timing alone cannot establish the race.

A seventh workload selects the existing six selection mocks and six static commands, including the new public test source in lint/format scope. The plan therefore selects 52 checks; this is a preparation count, not an executed pass count.

## Runtime and identity boundaries

Reuse the established fixed controllers, locked image preparation, bounded diagnostics and ownership cleanup. Each workload retains its own 20-second deadline, 1 CPU and 512 MiB worker, zero swap and existing PID/tmpfs/security limits. Each owned PostgreSQL instance retains 1 CPU and 768 MiB. Seven workloads allocate at most 140 seconds of business execution, without borrowing between groups; existing preparation and cleanup ceilings remain separate.

Prior nine-case PostgreSQL groups took 6.985–9.760 seconds, and the latest six static commands took 13.499 seconds. Those measurements inform grouping but do not guarantee that the new fixtures, retries, races or combined mocks fit. A failed workload remains failed and requires diagnosis; no automatic retry, budget increase or reuse of consumed experiments follows.

The new modules reuse the existing pre-service PostgreSQL identity fixture: PostgreSQL 18.4, psycopg 3.3.4, UTF8 and an isolated revision-0013 schema. Register these groups without the separate final-only observer so every case retains the exact single identity-property contract. Race observations remain asserted local evidence, without introducing a new report format. Source hashes, exact typed parameter membership, phase counts, cancellation and primary/independent absence must all be reviewed before accepting results.

## Remaining integration and exposure gates

Passing this finite selection would not close the complete candidate integration suite. The final intended integration tree still needs affected reconstruction/oracle/repository, migration, sync/outbox, cutover and backup regressions, plus the relevant SQLite surrogate checks. Full-history integrity validation before recovery reopening remains an explicit implementation gap; the earlier valid logical restore does not establish that gate.

Capacity, normal-use latency and contention budgets, a verified total Python deadline, actual network cancellation, ingress/adoption, HTTP/TypeScript/UI and physical/operator installation remain separate. Preserve failed experiments 51 and 56 and the unknown original restart cause. This preparation does not mount routes, grant real permissions, activate commands or deploy.
