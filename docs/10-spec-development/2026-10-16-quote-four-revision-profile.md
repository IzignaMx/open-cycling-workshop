# One bounded quote diagnostic profile

## Status and purpose

Reconciled on the qualified PR55 product-fix base: remote
`7c0dc84bf763cac7523f55f4fbc7d0a06c362b07`, tree
`5cd0717146d7f33331845ed08d1f95687e653df6`, local equivalent
`3946942ac91af47fdc9d492e319bb070386c7ec8`. This retains PR53's quote code,
QA54's workshop-identity readiness check and PR55's session-bound sync wake fix.
Both earlier preparation worktrees and their evidence remain intact.
[PR55 CI 38924829298](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38924829298)
qualified 218 browser tests with zero retries; ordinary runtime, security and
native ARM passed. Failed nonqualifying QEMU evidence remains preserved.
The coordinator closed that exact-source gate; this reconciled profile still
requires independent exact package review and deliberate coordinator publication.
Prior browser failures and retries remain preserved as historical evidence.
No profile specimen, Docker container or maximum history was executed locally.

The purpose is to observe where the corrected product spends time before making
any separate capacity decision. Structural count reductions do not identify time
coefficients. Do not project these measurements to 32 revisions, infer percentiles,
claim representative physical hardware, or treat diagnostic success as capacity.
The consumed PR51 maximum workflow is not present in this base and is not changed,
renamed or revived. Its failed result remains valid historical evidence.

## Fixed specimen and six actions

One fresh PostgreSQL database contains one synthetic quote lineage:

1. Create revision 1.
2. Append revision 2.
3. Append revision 3.
4. Append revision 4.
5. Load the complete history in a fresh transaction.
6. Retry the exact original creation request, checking the historical receipt and
   current ledger without new writes.

Every revision uses the previously reviewed legal record recipe: 80 labor charges,
10 discounts, 10 taxes, 500-ASCII-character normalized descriptions, 1,000 target
edges, and deterministic valid prices. Each charge is 60 minutes at 10,000 minor
units; each discount is 50 minor units over the first 50 charges; each tax is
1,000 basis points over the same 50 charges. Totals remain
800,000 / 500 / 499,500 / 1,299,000 minor units. No arbitrary padding, parameter
search, direct SQL history seeding or decision is included. This is a short history
with full-sized individual records, not a medium-sized record claim.

Commands are rebuilt through the actual request decoder, with fixed operation and
quote IDs, expected head/version/sequence, actor, organization and order scope.
Recorded times increase by one second between revisions. Assertions retain all
operation receipts, predecessor supersession, current ledger, zero decisions,
unchanged full service-order row, exact replay, and cardinalities `(1,n,n,n)`.
Request and joined operation-time logical-record bytes are measured. Canonical
array bytes use those measured immutable member sizes plus brackets/commas; no
extra historical replay is introduced just to measure the result.

Only the six fixed calls exist. There is no configurable point count, sweep,
maximum mode, automatic retry, fallback size or change of shape after a failure.

## Instrumentation and interpretation

All instrumentation is test-only. Production modules are unchanged. Wrappers time
the repository-bound candidate `advance`, locked `_load_with_bytes`, and explicit
commit. SQLAlchemy cursor events count client-observed cursor execution/wait;
The fixed SELECT / INSERT / UPDATE / DELETE / OTHER verb counters sum to the
cursor total and retain no statement text. They do not measure server CPU, all result fetching/hydration, or the whole
transaction. Action time includes input construction/decoding, admission, Python
validation, database work, commit and assertions.

Per-action cProfile output is reduced to five reviewed exact code objects:

| Closed label   | Source binding                    |
| -------------- | --------------------------------- |
| reconstruct    | reconstruction._reconstruct       |
| row_assembly   | reconstruction._revision_document |
| canonical_json | storage.canonical_bytes           |
| quote_codec    | storage.encode_quote              |
| command_proof  | commands.command_from_proof       |

These report primitive/total calls and own/cumulative seconds. The host requires candidate/load/commit counts appropriate to each action,
observed SQL SELECTs and all expected code objects. Only create legitimately
has no reconstruction/row-assembly observation; these are null, not fabricated
zero. Missing required instrumentation fails diagnostic qualification. Wrapper/cursor zero calls are valid observed
absence under installed hooks. Inclusive candidate/load/commit/SQL spans and
cumulative profile values overlap; never sum them as disjoint costs. Serialization
is nested detail within candidate/load. `_revision_document` own time means row
assembly including filtering, not pure filtering. Other reconstruction self time
remains unattributed orchestration/row filtering. No helper extraction claims
exact filter attribution. Profiling and polling have overhead and later actions
have a warmed process/cache; neither is an uninstrumented latency benchmark.

Row timing ends before profile extraction and atomic checkpoint publication.
Top process CPU begins before PostgreSQL fixture setup and ends before the final
checkpoint write. Final write, hook removal, pytest teardown and bootstrap remain
inside host wall/cgroup measurements, not inside that process-CPU interval.

## Containment, deadlines and evidence

Reuse actual verified cgroup/controller/counter, source/image/container identity,
non-root/capability/no-new-privilege, network and cancellation-canary checks.
Worker: 1 CPU, 512 MiB, 64 PIDs. PostgreSQL: 1 CPU, 768 MiB, 128 PIDs. No extra swap.
Keep existing SQL fixture values: lock timeout 15 seconds, statement timeout
20 seconds. These are test settings, not claimed production defaults or UX goals.

- Setup and canary: at most 20 seconds from immutable supervisor start.
- Entire workload: one immutable 20-second deadline starting before pytest spawn,
  including bootstrap, fixture setup, all six actions, profiling, polling, teardown
  and final result read. Every subprocess uses remaining time. No action can
  acquire a fresh deadline after exhaustion.
- Successful final probes and cleanup: at most 20 additional seconds, also capped
  by supervisor start + 120 seconds.
- External watchdog: 120 seconds plus at most 30 seconds emergency cleanup only.
  On workload failure or interruption, attempt immediate SIGKILL of the two exact
  validated worker/DB IDs, prove non-running, then reconcile and remove owned IDs.
  A blocked stop is failed/unverified; it never proves an exact execution cutoff.
- Contained lifetime CPU ceiling: 240 seconds, including canary; this defensive
  ceiling is not efficiency evidence. Whole job wall ceiling: 900 seconds with
  image preparation 9 minutes, guarded step 3, cleanup 1, upload 1 and checkout
  margin. Image-build CPU is unmeasured and outside contained counters.

The complete host report and each worker checkpoint are bounded below 16 KiB.
The host stores one metric copy only; report overflow fails closed with a compact
source/cleanup summary and explicit omitted metrics. The worker atomically
replaces its closed checkpoint before
each action and immediately after each completed action. The host polls it during
the original workload deadline, validates contiguous immutable records and stores
its latest observation. Timeout retains this last observed prefix and observation
time, which may lag the worker. An active ordinal is not proof of completion or
commit. Expiry never grants a diagnostic read or delays stop to recover evidence.
Zero pytest exit requires six valid completed records and completed final state.

No raw request, financial proof, SQL, exception message, full process status,
Docker inspect/environment or raw pstats is emitted. Missing final CPU/pressure
measurements remain unavailable. Source/run/job metadata and exact artifact bytes
must be independently checked before any diagnostic interpretation.

## Deliberate one-shot execution gate

Proposed workflow: `.github/workflows/quote-four-revision-profile.yml`, one job,
`pull_request` activity `opened` only, exact head branch
`codex/quote-four-revision-profile`, same-repository head and exact repository
`IzignaMx/open-cycling-workshop`, `run_number == 1` and `run_attempt == 1`.
There is no dispatch dependency, push trigger or synchronize trigger.

GitHub documents that new workflow runs increment run number while reruns retain
that number and increment run attempt. The explicit activity filter limits the
trigger. See [context semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts)
and [pull-request events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request).
This fails closed on a previously consumed first run; it is not a durable
repository-wide anti-duplication registry. Historical workflow absence across all
remote history is unproven. If skipped, report and stop; do not rename, raise the
number, reopen or rerun to bypass the gate. Branch/PR publication remains with the
coordinator after PR55 CI closure and reconciled exact package review.
If the required CI repair changes the published base, regenerate and independently
review the exact parent/tree binding before publication; do not reuse a stale
prepared tree merely because the diagnostic diff is unchanged.

## Decision after a future authorized run

First independently validate source binding, containment, six-action integrity,
partial/final metrics and cleanup. If the workload expires, preserve the result
without repeating it or increasing limits. Missing or overlapping attribution
must not be turned into a favorable estimate. A clear remaining bottleneck calls
for a separately reviewed narrow correction preserving full integrity checks.
Only a later explicit parent decision could authorize a distinct capacity
qualification. This profile does not resolve ordinary API percentiles,
organization-lock contention, restored 32/128 histories or stage-3 activation.

## Local preparation evidence

Only small mock/process/schema and instrumentation-helper tests were selected:
104 guard tests passed and six helper tests passed, with one explicit hosted
specimen deselection and one existing Starlette deprecation warning. The initial
three control tests failed before their implementation, then passed; the twelve
closed-schema cases likewise failed before the validator was added. Later mocks
cover checkpoint timeout with retained prefix, zero-exit incomplete output,
deadline expiry during probes and worker/database stop before reconciliation.
The full six-record metric encoding fits the existing 16-KiB command-output limit.

Ruff check/format, strict mypy on the touched supervisor, Prettier and diff checks
pass. Existing locked Python 3.13.5 / pytest 9.1.1 / Ruff 0.16.5 / mypy 1.20.2 /
Prettier 3.9.6 tools were reused; no dependency or environment installation was
performed. These results do not establish hosted feasibility, actual profiling
cost, containment execution on this source, or capacity qualification.

Independent review previously closed the instrumentation, whole-artifact bound,
required observations, SQL counters and deadline findings on the QA54 preparation,
including independently passing 104 guards and six helpers. The executable
profile files remain byte-identical during PR55 reconciliation. Fresh selected
small tests and exact commit/package/body review are required on this tree before
publication. No hosted profile result exists.
