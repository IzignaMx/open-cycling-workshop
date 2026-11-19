# Reception workflow observation, not a LIBERTAD readiness certificate

Baseline: main `95813a35123884e2f310b6c696c41361e3570e54` (PR115).
Status: implemented measurement journey; native measurements pending.

## Decision this evidence can support

Prepare a bounded, reproducible reception exercise before deciding whether to
schedule a physical trial. Use the real current App, native IndexedDB and synthetic
PostgreSQL server through existing authenticated UI/sync flows, not a standalone
IndexedDB throughput benchmark. No product/runtime behavior changes.

The journey authors three sequential receptions with one existing synthetic
customer and a newly created inline bicycle per order. It uses one newly scoped
synthetic location, one browser session and no background workload deliberately
introduced by the test. The initial business cache contains one customer, zero
bicycles and zero orders; final counts must be one/three/three. This tiny growing
workload does not represent a workshop's history, capacity, concurrent operators or
worst case. Login, account/location/customer setup and earlier form fields are
outside reported phase durations, but setup failures still fail the test.

## Exact observational boundaries

All starts/ends use the driver's monotonic `performance.now()`, not mixed wall-clock
values. Times include automation delivery, polling, scheduling, readback and assertion
observation overhead. They are not pure UI, HTTP, database or storage latencies.

| Phase             | Start                                                                  | End                                                                                                                               |
| ----------------- | ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `draftDurable`    | Immediately before the final reported-problem edit, after other fields | Readonly IndexedDB shows matching order content and UNSENT checkpoint                                                             |
| `reloadRecovered` | Immediately before page reload                                         | Ready App, recovered visible fields, unchanged payload/checkpoint metadata except legitimate `observedAt`, and unchanged journal  |
| `localCommit`     | Immediately before clicking Guardar orden                              | Readonly journal contains the new bicycle and dependent order with expected identity/customer linkage and exact journal growth    |
| `serverConfirmed` | The SAME submit timestamp as localCommit                               | Both durable applied results, authoritative cache versions, and actual server GETs matching bicycle/order IDs, fields and version |

The UI success message is asserted independently **after** the local journal
boundary. It is not the persistence timer endpoint. IndexedDB visibility after the
committed write is not a power-loss/fsync or physical-disk durability claim.
`serverConfirmed` is cumulative from submission and overlaps `localCommit`; adding
their durations would be wrong. Draft/reload phases are separate observations.
The test stays connected to loopback, without network shaping or an offline claim.

## Report integrity and reproducibility

Keep all three planned trial positions, raw phase start/end/duration observations,
synthetic entity/mutation identities and attempted/passed/failed/not-attempted counts.
There is no retry and no discarded warmup. Trial one is first reception after setup,
not a cold browser/server start; later trials reuse the session and growing data.
A failed phase retains completed earlier phases and its failure stage; absent phase
endpoints are not zero durations. Any functional failure fails the test. A final
feed/count failure invalidates the last provisional completion too. Raw attempts
are attached before receipt validation, so a validator failure cannot silently erase
what the driver observed. The successful trace is retained as well as failed traces.

The closed receipt validator rejects malformed/nonfinite/backward timestamps,
missing or inconsistent phases, mismatched submit origins, duplicate identities in
passed attempts, unexpected fields and impossible complete-without-final-dataset
reports. Failed attempts retain available identity evidence but never enter timing
summaries. Summaries contain only min/max of complete successful trials, accompanied
by counts and `complete`, `failed` or `incomplete` outcome. `readiness` always remains
`not_assessed`. No percentile, statistical confidence, regression budget or latency
SLA is inferred from three observations.

Record browser version, observed App module/SW hashes, origin, viewport, runner
project, network condition and dataset counts. CI source/head and runner metadata
remain in the enclosing workflow artifacts. The module/SW hashes identify those
served bytes, not a claim that every asset or physical installation was qualified.
The minimal receipts omit credentials and business payloads. Full traces contain
only disposable synthetic fixture data and must not be repurposed for real data.

## Physical decision card (not executed)

Follow the existing [safe physical protocol](../11-device-qualification/2026-10-31-safe-tier1-protocol.md)
without replacing or marking its pending template complete. Before a physical trial:

1. Identify and obtain permission for the actual device, OS/browser, CPU/RAM/storage,
   server device, network topology, profile and synthetic test installation.
2. Verify the already authorized trusted origin, exact App/server source, legitimate
   account/scope and proven backup/restore. Preserve existing drafts and queues.
3. Agree the representative starting workload and operator acceptance criteria.
   The preliminary QA UI/API targets are different measurements on representative
   hardware, not thresholds for this whole workflow or these driver observations.
4. Record each phase, functional result, IDs, failures and device/network context on
   that actual equipment. Investigate errors or unacceptable observed waits before
   scheduling broader use. Do not translate hosted milliseconds into tablet,
   Windows, laptop or Raspberry performance.

Missing equipment, authorization, trusted origin, source mapping or recovery proof
means BLOCKED, not permission to install, bootstrap, modify TLS/firewall, clear
storage or deploy. This increment performs none of those actions and contacts no
workshop. G1–G6, the existing-bicycle selector, migration/transition decisions,
physical accessibility, R01-T035 and LIBERTAD pilot acceptance remain open.

## Local qualification

Frontend **1,786 tests passed**, repository **223 contracts passed**, receipt helper
**9 controls passed** (including RED→GREEN malformed/outcome controls). TypeScript,
scoped lint/format/diff, production PWA build and both production-isolation checks
passed. Official collection found the new measurement case and existing source
completion case: **2 collected, 0 locally executed**. No durations were measured
locally. Dependency setup used frozen locks; the first package install failed on a
missing default store directory, then succeeded with an explicit temporary store.
Node 24.22.3 / pnpm 11.25.0 were the local authoring environment, not a timing sample
or the pinned hosted runner. Lockfiles were unchanged.
