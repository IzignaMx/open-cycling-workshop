# Finite quote service semantic closure

Status: all 40 PostgreSQL cases and six selection mocks passed with independent evidence review. Repository contract passed; Ruff failed one import-order finding, and four later static commands were unrun. The import correction passed Ruff; the next static-only run found one formatting line, with types and both contracts still unrun. The exact formatting correction is pending verification. No product behavior or schema change is proposed.

## Historical preparation plan: acceptance and bounded selection

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

## Observed finite result and import-only correction

[Run 39077801165](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39077801165), first run/attempt, tested commit `f5066d0056322ea1845bbfded24924e4ac90e8ae`, tree `c4fbd6c163722e192cd4663086deddfa6015c422`. All six PostgreSQL workloads passed 40 cases and 120 ordered phases, with 40 distinct actual PostgreSQL 18.4 / psycopg 3.3.4 / UTF8 / revision-0013 identities. Independent review verified source bindings, serialized jobs, canaries, client reap, primary cleanup and independent absence for all seven jobs.

Workload durations were 7.112 / 6.844 / 7.173 / 4.708 / 8.945 / 6.950 seconds for decision, identity mismatch, content mismatch, storage, atomicity and race groups respectively. These are complete small-fixture workload measurements, not product latency or capacity qualifications. The narrow race assertions observed the intended live lock waits before releasing participants. The acknowledgement-loss case injected an exception after a real successful commit; it does not simulate a network outage. Successful service bodies do not exercise failure-path specimen cancellation; the separate real canary remains its own evidence.

The PostgreSQL artifacts are `12117797076`, `12117747255`, `12116864750`, `12117722448`, `12117438699` and `12117284468` in the same order. The combined artifact `12118320104` preserves six passing selection mocks and a passing repository check, followed by one complete 178-byte Ruff I001 import-order finding in `test_quote_service_races_postgres.py`. Formatting, production types, OpenAPI and generated client were unrun. The workflow therefore failed and is not 52 passing checks. The failed combined report has no final worker resource counters; none are inferred from sampled values or pass markers.

The correction combines only the split ordinary imports from `test_quote_application_service`, preserving the explicit fixture re-export and all function bodies. A new literal `codex/quote-semantic-style-checks` / `.github/workflows/quote-semantic-style-checks.yml` pair selects only the existing six static commands in the proven controller. Refresh the affected source pins and preserve all consumed workflows, PostgreSQL controller and budgets. At that checkpoint, exact correction review was complete and execution was pending. The added mock branch vectors are prepared but are not executed by this static-six-only follow-on. No functional or mock workload is repeated by this static-only correction; broader integration and activation gates remain open.

## Retained formatter result

[Run 39078500578](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39078500578), first run/attempt, tested commit `a047ca603697b76a2ccfe449412bcebda638206b`, tree `09669755bc4e57355f2635a152bb8a3aa505615c`. Repository and Ruff passed. Formatter returned one complete 712-byte output requesting a conditional-expression line join in `test_quote_service_decisions_postgres.py`; 47 other files were already formatted. Production types, OpenAPI and generated client were unrun. Artifact `12117848133` has SHA-256 `586f6c6f68d8ab3a9c89e1b4a37ab8f43ad95b457c6987032c6f647682dbe437`.

Independent review verified the full formatter output, exact source/pins, real canary, whole-worker stop before bounded client reap, and primary plus independent absence. The failed report has no final worker resource counters or successful workload measurement. Preserve the failed result rather than substituting earlier passing static evidence.

Apply only the retained 655-byte unified hunk, whose conditional expression and operands remain unchanged, then refresh source pins and add the literal `codex/quote-semantic-format-checks` / `.github/workflows/quote-semantic-format-checks.yml` static-six pair. All consumed workflows and product sources remain unchanged. New branch mock vectors remain unexecuted in this static-only selection. Exact correction review is complete; execution remains pending. No functional or capacity workload is repeated.
