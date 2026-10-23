# Remaining PostgreSQL quote loader and writer checks

Status: all 32 PostgreSQL cases and six selection mocks passed. The corrected static-only run passed all six commands with independent evidence review. Prior failed runs and their narrower results remain preserved. Broader service integration and activation are still pending.

The corrected service candidate has [204 functional/mock checks and six static commands verified](2026-10-17-quote-integrity-edges.md). The following historical preparation plan selected existing PostgreSQL prepared-writer and bounded-loader coverage. It introduces no product behavior or schema change.

## Fixed selection

Four PostgreSQL groups select 32 existing cases, with complete functions and exact typed parameter matrices:

- `writer5`: retain both original noncanonical raw copies and generated counts; three reached-insert/caller rollback cases; ordinary dictionary-writer compatibility with quote-only budgets injected small.
- `admission9`: source admission before writes, invalid references, exhausted version/new enrollment versus historical replay, projection preparation refusal, generic-writer exclusion, and UTF8 source boundary cases.
- `history9`: historical replay without current oversized Text hydration, six unknown/invalid version values, paired transition-claim refusal, and quote-outbox-pointer prefetch refusal.
- `guards9`: three timestamp guards before driver conversion, actual NOWAIT row-lock retention during prepare/persist, compressed Text refusal without hydration, and four forged prepared-projection values.

The source-reviewed implementation's explicit function tables define the exact node membership. Both selected test modules remain unchanged: `test_prepared_order_change.py` and `test_quote_bounded_effects_postgres.py`.

One additional `selection_static12` group runs the existing six mock selection/identity/parser regressions followed by the unchanged six static commands. Mock expectations must retain all old groups and validate the new mixed-type rows. Exact types distinguish `True` from `1`, and validate the fixed bytes value and one tiny dictionary without coercion or arbitrary serialization. This is 44 checks across five sequential workloads.

## Identity and resource acceptance

Each PostgreSQL case has a separate disposable schema and an actual closed driver/database/schema/encoding/revision identity observation. The final-only observer runs after the original body and its connections close, before fixture schema disposal. It must not migrate, seed, repair catalogue definitions, inspect payloads or substitute for the original test assertions. Expected identities are PostgreSQL 18.4, psycopg 3.3.4, UTF8 and revision 0013.

The existing mechanisms retain each independent 20-second workload limit. Workers retain 1 CPU, 512 MiB, zero swap, bounded PIDs/tmpfs, non-root identity, read-only root and removed capabilities. Each owned PostgreSQL instance retains 1 CPU and 768 MiB. Real cancellation canaries, bounded stop/reap and primary plus independent absence are required. Five workloads allocate at most 100 seconds of business execution; preparation and cleanup retain their separate existing ceilings. No group borrows another group's budget.

The 32 PostgreSQL cases create 32 fresh schemas and migrations; 27 also seed their ordinary fixture. Conservative closed inner-result bounds are 8,210–15,183 bytes before final implementation verification, below the unchanged 16 KiB cap. Actual observed node IDs and complete ordered phase records must match the exact typed matrix. No predicted parameter-ID spelling replaces that validation. The JUnit group retains its existing bounded XML/result and static diagnostics.

The prior static-only workload took 13.270 seconds. Previous metadata/bridge groups took 4.340–6.532 seconds, with different bodies. These measurements support the finite grouping but do not guarantee the combined or new workloads fit. A failed group remains failed, with retained bounded diagnostics; no automatic rerun or budget increase is allowed.

## Claims and remaining gates

The writer rollback cases contain reached-insert sentinels. Some injected preparation/bypass cases assert refusal and no writes without an independent callback-reached sentinel; passing them must be reported at that narrower assertion scope. Actual lock retention in one NOWAIT test does not qualify broader service concurrency or contention performance.

The prior tiny logical restore proves valid retained effects and replay after incarnation recovery. Full-history integrity validation before reopening, including corrupt/oversized/unknown-version restore refusal, remains open. Broader service integration, capacity, nominal latency, complete production deadlines, HTTP/UI and activation remain separate gates. No production route, deployment, real data or account change is included.

## Observed partial result and exact style correction

[Run 39075248467](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39075248467), first run/attempt, tested commit `07351675c671cf18077c5c08edab2132be070dec`, tree `cb254639c316e3a48f5f10e74c56377a9be3495d`. All four PostgreSQL groups passed their 32 cases and 96 ordered phases. The combined group passed all six mocks and the repository contract, then failed Ruff with four complete SIM300 findings in selection-test lines 825, 912, 922 and 927. Formatting, production types, OpenAPI and generated client did not run. The overall workflow failed; it is not 44 passing checks.

The four PostgreSQL artifacts are `12116244768` (writer5), `12117150411` (admission9), `12116887277` (history9), and `12117130639` (guards9). The combined failed artifact is `12117260084`; its complete decoded Ruff output is 431 bytes. Its failed outer report has no accepted JUnit aggregate or final worker counters, and no such values are inferred from seven diagnostic pass markers.

The corrective source reverses only the four equality operands, refreshes the test pin and adds an exact `codex/quote-loader-static-checks` / `.github/workflows/quote-loader-static-checks.yml` pair restricted to the existing six static commands. It preserves all consumed workflows, production and PostgreSQL test bodies, and resource limits. No PostgreSQL or mock workload is selected again. That comparison correction was reviewed and executed in the static-only run below.

Independent artifact checks verified all five ZIP/source bindings, the 96 ordered PostgreSQL phases, 32 distinct closed schema identities, serialized jobs, real cancellation canaries and primary plus independent absence. PostgreSQL workloads were 4.936 / 6.985 / 7.166 / 9.760 seconds for writer/admission/history/guards respectively. Final worker memory peaks were 93,245,440 / 102,760,448 / 106,532,864 / 103,780,352 bytes. These successful-path readings precede container termination; they are not posttermination totals. PostgreSQL success records client reap, while failure-path specimen cancellation is not exercised by those successful bodies.

## Single-line formatter correction

[Run 39075919485](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39075919485), first run/attempt, tested commit `0009343af1c56ffc8477d0b31efeba41a1a9fc74`, tree `5bb38a73cafd43948dfa8ae67979b31cb82f7543`. Repository and Ruff checks passed, then formatter requested one continuation-line join in `test_quote_integrity_selection.py`. Its complete 662-byte diff reports one file requiring formatting and 43 already formatted. Types, OpenAPI and generated client were unrun. Artifact `12117355365` retains the failed output and cleanup receipts; no final worker counters or workload duration are claimed for that failed run.

Apply only that exact formatting hunk, refresh the selection-test pin and add the literal `codex/quote-loader-format-checks` / `.github/workflows/quote-loader-format-checks.yml` pair restricted to static6 in the existing controller. All consumed workflows, production and PostgreSQL test bodies, selectors and resource budgets remain unchanged. Exact review and the new static execution completed as recorded below. This performs no PostgreSQL or mock rerun and does not qualify capacity or activation.

## Corrected static closure

[Run 39076298550](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39076298550), first run/attempt, passed all six commands on commit `4b0a19b64d346e9322d343f460069aebf145ccfb`, tree `0d5cbb2e03eb7601db1eb7935c21d7e15480ef2a`: repository contract, Ruff, formatter, strict production types, OpenAPI and generated client. Artifact `12117062612` has SHA-256 `7f30c4ded1d0fc4d33cf221be3f7dc176e55529283a7b0ebfe9f9d415bb00013`. There were no failures, errors or skips.

Independent review verified all 19 source pins and four locked inputs, exact image/ZIP identity, accepted JUnit counts, the real cancellation canary, whole-worker stop before bounded client reap, and primary plus independent absence. The workload took 13.499 seconds under the unchanged 20-second limit. The final pretermination worker reading reported 276,119,552 bytes peak memory and 13,544,030 microseconds CPU delta. These readings precede termination and do not establish posttermination totals or product performance.

The passed PostgreSQL cases remain bound to run 39075248467 and their unchanged test/product sources. This static closure does not turn that earlier failed workflow green or add functional execution. Complete service decisions, reached-write atomicity, small authority/idempotency races and remaining integration checks are separate work. Capacity, recovery reopening and activation gates remain open.
