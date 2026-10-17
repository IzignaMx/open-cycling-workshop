# Remaining PostgreSQL quote loader and writer checks

Status: all 32 PostgreSQL cases and six selection mocks passed; the repository check passed, Ruff failed four style comparisons and four later static commands were unrun. Independent artifact checks passed for the selected functional scope; the overall workflow remains failed.

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

The corrective source reverses only the four equality operands, refreshes the test pin and adds an exact `codex/quote-loader-static-checks` / `.github/workflows/quote-loader-static-checks.yml` pair restricted to the existing six static commands. It preserves all consumed workflows, production and PostgreSQL test bodies, and resource limits. No PostgreSQL or mock workload is selected again. Exact correction review and execution remain pending.

Independent artifact checks verified all five ZIP/source bindings, the 96 ordered PostgreSQL phases, 32 distinct closed schema identities, serialized jobs, real cancellation canaries and primary plus independent absence. PostgreSQL workloads were 4.936 / 6.985 / 7.166 / 9.760 seconds for writer/admission/history/guards respectively. Final worker memory peaks were 93,245,440 / 102,760,448 / 106,532,864 / 103,780,352 bytes. These successful-path readings precede container termination; they are not posttermination totals. PostgreSQL success records client reap, while failure-path specimen cancellation is not exercised by those successful bodies.
