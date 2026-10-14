# ADR · Authenticated workshop production client (Increment C)

Status: accepted and implemented; independent source review closed; exact published-tree runtime qualification pending.
Date: 2026-10-14. Base: actual integrated main37
`14f4bf005f2b28ded5d31c45c9c532d50597aefc`, tree
`eb8f2575d06109916b38d6f3d579899d795cd943`.

This implements the reviewed finite C boundary after the server cutover contract.
Scope is the existing customer/bicycle/order offline workflow and necessary
concrete-workshop selector. No administration CRUD, shared branding, new domain,
real credential/access, installation activation or deployment is included.
Independent read-only plan review found no remaining blocker after the session,
transaction, incremental continuity, legacy and restore clarifications below.
AGPL-3.0-only, DCO, OFF-003/005/007/009/012, FR-IAM-002/004/006/008,
SEC-002/003 and applicable ACC requirements remain mandatory.

## Existing contracts and exact gaps

- B supplies required `dataset_incarnation`, exact policy
  `ocwp-access-baseline-2`, genuine `baseline-v1` only for enabled floor 1, and
  incarnation-bound signed sessions. Floor 0/disabled null remains inert.
- Strict push uses `X-OCWP-Write-Protocol: 1` and exact current
  `X-OCWP-Authorization-Epoch`, with one selected location per batch.
  Whole-response refusals: `client_upgrade_required` and
  `authorization_context_changed`. Item conflicts: `sync_conflict`,
  `legacy_receipt_unverified`, `receipt_integrity_conflict`, `receipt_proof_conflict`.
- Existing App still reads/writes shared v4 tables and uses mutable token-provider
  transports. WorkshopShell independently imports the v4 singleton. KernelDatabase
  imports its base class from the same module that instantiates that singleton.
- Existing kernel has initial baseline only, no reload admission, no journal
  incarnation, no list API and no grouped intake. Existing initial completion
  validator binds partition cursor directly to initial checkpoint; incremental
  consumption must explicitly replace that invariant rather than weaken it.
- `/locations?limit=...&after_id=...` already supplies authorized paginated
  locations. `/service-orders/{id}/events` supplies scoped online history; it is
  not paginated, so client byte/count limits must fail visibly rather than claim
  an oversized/partial result is complete.

## 1. Storage and session admission

Files: `apps/web/src/local/db.ts`, proposed `local/database.ts`,
`access-kernel/database.ts`, `types.ts`, `kernel.ts`, `context.ts`,
`auth/session.ts`; proposed `access-kernel/session-admission.ts` if extraction
keeps the kernel facade small.

- Extract the side-effect-free v1-v4 schema class. Legacy singleton remains in
  `local/db.ts` for legacy code/tests. Production runtime imports only the class
  and kernel factory, opening the stable distinct `ocwp-authenticated-v1` name.
  No in-place upgrade, operational copy, cursor adoption, deletion or fallback.
  Test the actual production import graph, including WorkshopShell.
- Retain current sessionStorage credential lifetime. A newly authenticated exact
  session gets a random noncredential binding identifier alongside its token/user
  snapshot. Token change creates a new binding and invalidates old volatile work.
  IndexedDB stores only the binding identifier and validated admission metadata,
  never another token, credential hash or password copy. Old v2 snapshots without
  binding may request online verification; they cannot establish offline admission.
- Login/logout/user/workshop/token transitions synchronously blank the visible
  model and volatile tickets, cancel the runtime attempt, then advance durable
  generation. Late completions cannot reinstall a ticket, publish a view, dispatch,
  acknowledge or hold a newer session. Session snapshots are immutable captures.
- Equivalent successful online verification may rebind the current baseline,
  incremental and session-admission owner to the new generation/ticket only inside
  its fenced transaction. Keep the original baseline origin/start/completion
  evidence unchanged. Resume ownership is the explicit current admission owner,
  never guessed from the original baseline owner or a READY flag.
- Proposed kernel entry `resumeOffline(rememberedAdmission, newTabAttemptId,
isCurrent)` checks in one transaction: exact session binding and remembered
  owner/generation/partition, principal/realm/selected workshop, policy/protocol,
  incarnation, completed initial proof and valid incremental proof, active
  partition/state, finite clock at or after durable observedAt and strictly before
  current offlineUntil. It then advances generation/owner, rebinding only this
  eligible completed session. Install the volatile ticket only after the existing
  post-commit current-owner check. Update sessionStorage resume metadata afterward;
  interruption between those stores fails closed and requires online verification.
- A new offline login, workshop switch, missing binding, stale prior owner,
  unknown format, partial baseline, expired lease or backward clock is refused.
  This promises eligible same-tab/session reload, not offline authentication after
  every browser termination. Cloned tab sessionStorage must still win an exact
  expected-generation claim; the loser stays locked. A durable takeover observer
  blanks stale UI but never starts an automatic verification tug-of-war.
- Controller schedules the exact current offlineUntil deadline and rechecks lease,
  monotonic observed time and durable owner on visibilitychange/pageshow/focus.
  Expiry/backward clock/takeover blanks an already-rendered view immediately;
  a stale timer cannot lock a replacement session. Do not wait for the next read
  or user click to hide expired cached data. Runtime and kernel use the same clock.
- A disconnect invalidates captured push/delta continuations synchronously while
  retaining the eligible offline session. Network-attempt generation is separate
  from session ownership: late success or failure cannot ACK, defer or lock the
  offline session. The original in-flight journal remains uncertain until genuine
  reconnect verification rebinds ownership and retries the same immutable IDs.

## 2. Journal provenance, queries and local repositories

Files: `access-kernel/types.ts`, `kernel.ts`, `operations.ts`, `projection.ts`;
proposed `access-kernel/queries.ts` and `runtime/repositories.ts`; existing pure
`features/{customers,bicycles,orders}/local-*.ts` builders remain reusable.

- Every new immutable operation records required authoredDatasetIncarnation in
  addition to original principal/scope/epoch. Missing/unknown/incarnation-mismatched
  operations are preserved and explicitly recovery-held, including uncertain and
  applied-awaiting-projection cases. No inferred backfill, reauthoring or automatic
  cross-incarnation replay. Hide those operational overlays immediately. Hold
  dependent chains, but permit an independent fresh baseline and new commands.
- Apply incarnation checks to dispatch selection, dependency admission, overlay
  composition and ACK validation. Recovery history remains original-author plus
  explicit entity-read-grant scoped. Preserve journal/event bytes and results;
  mutable delivery indices must no longer make a recovery-held applied item look
  like an eligible applied overlay. Same-incarnation renewal preserves exact IDs.
- Add bounded active-partition plus current-author query pages; never read every
  user's journal/cache into App for filtering. Existing compound cache keys and
  unique journal entity keys can supply bounded entity-ID enumeration; add an
  additive index only if needed and explicitly account for schema reservation.
  Recovery delivery/events queries are likewise author/read-grant bounded.
- C uses logical IndexedDB v6 for author-scoped pagination; future quote stores
  reserve v7. Its unpublished v6 schema also adds
  `[principalKey+locationId+entityType+state+localSequence]` and
  `[principalKey+locationId+entityType+state+retryAt]` delivery indices. The v5→v6
  upgrade builds indices without rewriting journal, event, delivery or unknown
  record fields. No earlier released schema declaration is changed.
- Issue pages use a closed set of held/rejected/awaiting-confirmation states and
  only currently readable entity types. At most 21 bounded metadata streams are
  merged; only the requested page of immutable originals is materialized.
  Separate bounded first-row probes establish global readable issue/pending
  presence and the earliest retry deadline. An empty later page cannot claim
  there are no issues, and an idle dispatch step cannot claim pending backoff work
  is synchronized. The UI provides an explicit next-issues-page action.
- Repositories accept a captured runtime ticket and derive all authority/scope.
  UI-supplied organization/user/location fields cannot grant authority. Strip old
  QueuedMutation delivery fields into an exact nine-field wire envelope.
- Add grouped `commitLocalCommands` with a small explicit bound for bicycle/order
  intake, journaling dependencies/events/deliveries atomically under one ticket.
  Resolve customer/bicycle create dependencies and aggregate order within the same
  transaction. A second awaited operation must never adopt another session.
- Timeline uses bounded, captured, scoped REST access on demand plus current-author
  local events. Show when remote historical timeline is unavailable offline; a
  baseline projection is never labelled complete event history.

## 3. Ongoing incremental chain

Files: `baseline-state.ts`, `baseline-wire.ts`, `baseline-transport.ts`, kernel
facade; proposed `incremental-state.ts`, `incremental-store.ts`,
`incremental-coordinator.ts` and narrow shared bounded transport helpers.

- Keep initial baseline parser requiring non-null baseline_id. Add a separate
  closed incremental validator requiring baseline_id and completion.baseline_id
  both null. Reuse strict entity/scope/grant/version/timestamp/byte validation.
- Preserve immutable original start and initial completed-delta proof. Add a
  versioned incremental metadata record bound to that exact initial checkpoint,
  context key, explicit incarnation, owner and partition. Retain bounded latest
  canonical receipt, exact predecessor/next body, phase, safe local chain sequence
  and retry/hold state. Precise cursor invariant: `partition.cursor` is the latest
  durably accepted opaque continuation, equal to the latest receipt.continuation
  and next request.continuation, even while phase is catching_up. It is a completed
  checkpoint only when that exact receipt has phase complete and a matching
  completion object. Do not persist a separate unsupported last-complete scalar.
  Do not retain an unbounded log of page bodies or decode/compute opaque cursors.
- Completion validation accepts either untouched initial checkpoint or the
  separately valid incremental chain anchored to its original checkpoint. It must
  reject arbitrary cursor changes, unknown metadata, contradictory receipt/phase,
  incarnation/epoch mismatch and stale owner. Initial activation is never repeated
  after incremental work; the server intentionally invalidates that activation hash.
- A completed initial working set plus valid partial incremental progress may
  remain readable/offline-eligible within its session lease. A catching_up receipt
  never claims the current sync round is complete. The retained latest receipt,
  chain sequence and original anchor validate local atomic-transition metadata;
  they do not reconstruct discarded history or create cryptographic authority.
- Each step: captured session first; read exact durable request under fences;
  bounded HTTP; one transaction revalidates current session and durable owner,
  validates whole page, version-merges projections, then commits receipt and
  successor atomically. Exact latest replay is idempotent; stale earlier response
  cannot rewind or advance. ACK delivery is independent of these projections.
- Lost response retries the same predecessor. Quota/abort preserves old checkpoint
  and rows; failed persisted hold also disables the volatile session. Expiry or
  context change starts a new private baseline and preserves all journal/history.
  No v4/numeric cursor zero fallback. Scheduling is bounded stepwise with existing
  retry policy; persistent failure becomes visible held state.

## 4. Captured push and runtime composition

Proposed `runtime/{controller,session,transport,repositories,legacy-preservation}.ts`
and `access-kernel/{push-transport,push-coordinator}.ts`; `App.tsx`, `main.tsx`,
`auth/LoginForm.tsx`, `personalization/WorkshopShell.tsx`, sync/status components.

- Synchronously capture exact endpoint/realm, token, session handle, runtime
  sequence, principal/workshop/epoch/incarnation and ticket before any await.
  Atomically select/mark dispatch under those durable fences, freeze selected
  exact IDs/envelopes, recheck current session immediately before HTTP, then
  compare current session plus original batch/owner inside ACK transaction and
  again before publishing results. No later mutable token callback.
- Pass the captured-current callback into local grouped command, dispatch selection,
  ACK and failure/deferral transactions, checking before their work and again just
  before the transaction callback resolves. The durable ticket fences remain
  mandatory. A post-commit stale-session throw alone cannot undo a stale write.
- Exact destination, no redirects/cookies/referrer, cache no-store, bounded request
  and response, closed typed status-paired errors. Protocol/context refusal holds
  dispatch for upgrade/reverification; bound-receipt errors become explicit
  integrity/recovery states. Original envelopes and history remain unchanged.
- Bounded streamed parsing applies to `/auth/context` (currently unbounded
  response.json), captured login/current-user/location/history reads and push,
  not just baseline/delta. Reuse/extract the narrow byte reader with endpoint
  limits before parsing; closed object keys alone do not bound allocation.
- A controller owns one production database/kernel, SessionStore, immutable active
  context, baseline/incremental/push coordinators and repositories. React consumes
  a stable subscription snapshot; it never opens operational stores directly.
- Fresh login is online. Verify current user, then use verified account location
  or ask an organization-wide user to select from paginated authorized locations
  before requesting context. Account scope and selected workshop stay distinct;
  no all-location aggregate cache or admin CRUD. Location-bound users do not need
  an extra locations.read permission merely to use their verified location.
- Reconnect does real current `/auth/context` verification before push/pull.
  `/auth/me`, navigator.onLine or a successful ping is not sufficient. Contraction
  blanks old data immediately; expansion creates a complete historical baseline.
  A current lease cannot reveal remote revocation while genuinely offline.
- Preserve all four themes and same-session draft/focus continuity on theme
  changes. Identity/workshop transitions must never expose another user's draft.
  Stable accessible states: sign-in/locked, selector, baseline progress, offline
  lease expiry, takeover, upgrade required, storage/retry/integrity/recovery held.
  No routine instruction to clear browser storage.
- Inject preference storage into WorkshopShell. After successful verification,
  lazily copy only exact owned appearance [organization,user] and local logo
  [organization,user,location] keys from old presentation storage. Read source
  using raw IndexedDB readonly open without a requested version, aborting any
  onupgradeneeded creation. Never construct the latest schema class against ocwp:
  that would upgrade an old schema. An absent legacy DB remains absent. Validate
  owner and value, then conditional
  destination transaction inserts only if absent and session still current.
  Two records bound each copy; interruptions/retries do not overwrite newer
  preferences. Originals/unknown fields remain untouched in old DB. No claim of
  cross-database atomicity or shared organization branding.
- Generic prior-work observation uses only bounded store metadata/counts, never
  materializes legacy operational payloads into the authenticated runtime.

## 5. Exact old bundle, SW and legacy evidence

Files: proposed `fixtures/legacy-client/manifest.json`,
`scripts/e2e/build_legacy_client.mjs`, test-only dual-build static server and
`apps/web/e2e/legacy-cutover.spec.ts`; existing migration test gets explicit
safety-contract supersession.

- Pin exact pre-cutover production source SHA main36
  `714342c60f4163c7b4c1ebec8433995dccbeea01` (App is v4). Build its unmodified
  production source/lock/config with pinned toolchain separately from C. CI must
  make this historical SHA available explicitly (checkout is currently shallow).
  Record source tree/lock/tool versions/build flags and hashes of every generated
  asset including actual sw.js/workbox. Upload the complete old build/SW fixture
  as its own test artifact; do not substitute a current v4 constructor or synthetic
  schema fixture for a genuine old installed application.
- Test-only static server switches served build at the same origin; no test
  admission/control endpoint enters production App. Install old SW, keep old JS
  live, create old offline work, install/activate current SW/build, and authenticate
  new App into its distinct DB. Observe generic prior-work notice without exposing
  legacy payload to an arbitrary signed-in user. Keep old live tab and add more
  offline work after the first observation; later reconnect the old captured
  client and prove a genuine server 401 old-session refusal preserves its queue
  (not an intercepted fake response), then verify current-incarnation fresh login
  still receives whole 409 for missing protocol. Include legitimate pre-B signed
  missing-incarnation session compatibility where the fixture can issue/validate
  it before floor activation; do not mix a pre-B writer into the activated pool.
  Original queues/conflicts/events/unknown fields remain exact.
- Compare dated raw legacy snapshots before/after expected old-tab additions,
  not a falsely frozen first archive. New DB never adopts old cursor/author/IDs or
  replays old work. No export/reconciliation UI is needed to qualify preservation.
- Replace unsafe legacy automatic replay expectation intentionally, documenting
  why. Separately prove known-author new-protocol unchanged-ID lost-ACK/reload replay
  applies once and retains immutable journal/history until authoritative coverage.

## 6. Test allocation and runtime fixture requirements

Core (register explicit files in `apps/web/tools/run-core-tests.mjs`):

1. Session/kernel tests: eligible offline reload; old/missing/cloned/replaced
   binding, takeover, unknown formats, incomplete proof, expiry/clock rollback,
   quota abort, race before/after ticket installation, no bearer persistence.
2. Journal/projection/repository tests: current-author reads, capability removal,
   incarnation missing/mismatch for pending/uncertain/applied overlays, dependency
   holds, same-incarnation unchanged replay, grouped intake rollback and bounded
   list/query allocations with foreign histories present.
3. Incremental wire/state/store/coordinator tests: strict null phase, bounded
   bytes/records, latest exact replay/lost response, mixed scope, version
   contradiction, stale response/hold, crash/abort, retry exhaustion, expiry and
   fresh baseline preserving originals.
4. Push/runtime tests: immutable token before asynchronous selection, independent
   token-refresh race, A/B and workshop switch at every await, stale ACK/failure,
   typed server refusal, no current-view restoration, deterministic tab lock.
5. Preference/import-graph tests: no production old singleton; exact owner scopes,
   interrupted copy, source unknown fields unchanged, newer destination preserved,
   raw v1 remains v1 and absent legacy database remains absent.

Native production journeys (real FastAPI/PG + production PWA, no fake READY):

- Extend `e2e/customer-offline-sync.spec.ts`, `order-lifecycle.spec.ts` with real
  historical REST records of all three types, floor1 baseline, offline create /
  reload, reconnect context first, exactly-once push, incremental coverage and
  second independent browser profile convergence. Assert retained journal and
  applied delivery plus projection coverage instead of queue deletion.
- Add `e2e/authenticated-context-switch.spec.ts` for actual A/B same-workshop,
  owner/two-workshop selector, same-browser tabs, token renewal, delayed commit /
  fetch/page/ACK/failure/UI, contraction/expansion and recovery incarnation holds.
- Convert `sync-chaos.spec.ts`, `conflict-path.spec.ts`, `sync-scope-integrity.spec.ts`
  to strict push and opaque `/sync/deltas/page`, retaining all original domain
  conflict/atomicity/convergence assertions and retry-free deterministic barriers.
- Convert `structural-themes.spec.ts` from fabricated v4 session/cache/API aborts
  to genuine verified baseline then offline cases. Keep Banco/Plano/Ritmo/Noche,
  drafts, keyboard/focus, reflow/touch/axe and add all new selector/held states.
- Add exact old installed SW/live-tab cutover above. Existing isolated native
  harness remains useful but does not substitute for production journeys. Preserve
  genuine floor0/null refusal separately in `baseline-browser.spec.ts`.

Fixture changes required, all isolated synthetic targets:

- `scripts/e2e/prepare_e2e_database.py` currently seeds only floor0. Prepare
  explicit floor1 multi-user/multi-workshop identities and historical records.
  `apps/web/playwright.config.ts` must enable supported composition. Test-side
  remote mutations need strict protocol and freshly obtained matching epoch.
- `.github/workflows/ci.yml`: build/archive pinned old source; add new affected
  races to retry-free repetitions; preserve distinct direct/repeat/aggregate
  result directories. `tests/repository/test_repository_contract.py` and
  `scripts/ci/verify_v01.py` must retain deterministic contract/aggregate coverage.
- Docker's 11-check entrypoint is `scripts/ci/local_compose_smoke.py`, not
  verify_local_runtime.py. It clears inherited OCWP_* variables, so set true only
  in its generated disposable environment. Keep ordinary Compose default false.
  After bootstrap/repeated-bootstrap refusal and existing floor0 historical REST
  customer, call supported `ocwpctl cutover activate` for that random fixture
  organization only; verify actual context advertisement before browser work.
- `scripts/ci/local_runtime_browser_smoke.mjs` waits for complete baseline, checks
  the historical customer, inspects new scoped journal/delivery/projections and
  preserves offline reload/reconnect/second browser plus both SW API-navigation
  denylist checks. Credentials remain stdin-only with existing redaction.
- Extend `tests/operations/test_local_compose_runtime.py` for fixture opt-in and
  default-disabled boundary. Upgrade the disposable runtime restore sequence too,
  rather than treating its existing never-served restored target as C recovery
  proof. Retain all eleven substantive checks, including original-DB down/up.
- For the floor1 restore drill, retain a live browser/session using a bounded
  test-only stdin/stdout phase handshake. After a verified backup, let that browser
  create unsent offline work and preserve its exact original journal, delivery and
  session metadata. Retain an opaque baseline checkpoint whose family is already
  present in the backup for a separate restored-checkpoint refusal assertion.
  Stop edge/API/worker and every fixture writer. Restore only
  into the existing dedicated `ocwp_restore_test`, preserving nonempty-target
  refusal. Invoke B's supported `cutover recover` against that isolated URL with
  the exact expected original incarnation. Assert atomic fresh incarnation and
  preserved history before exposing the restored target.
- Only afterward start the qualified API/edge against that disposable restored
  database via a generated temporary Compose override, with workers still stopped.
  Prove the retained pre-restore checkpoint is refused even with a freshly issued
  post-rotation token; old-token 401 alone does not establish checkpoint invalidation.
  The retained browser proves old-token refusal, fresh login/baseline, unchanged
  original pending journal in recovery hold and absent operational overlay; new
  independent same-user work remains usable. No auto replay into restored state.
  No generated restore URL/credential appears in arguments/log artifacts; use the
  existing mounted secret-file mechanism. Temporary override targets are derived
  only from this random test project, never ambient operator configuration.
- This is hosted synthetic restore/reopen evidence, not an actual installation
  recovery claim. Normal Compose defaults remain disabled and unchanged. API-only
  `runtime_http_smoke.py` can retain floor0 legacy-compatibility coverage.

## 7. Execution, independent review and exit

On this integrated B base, write observed RED tests;
implement modular green commits with DCO. Proposed component ownership: one worker
for kernel admission/provenance/query contracts, one for incremental modules,
coordinator for captured transports/runtime/repositories/UI; agree facade/type
edits to avoid concurrent kernel overwrites. Independent read-only plan review is complete. Independent component/final union
review precedes publication.

Run focused RED/GREEN then core, offline/web types, ESLint/format, contracts,
repository integrity, Python/server regression, production/isolated builds and
aggregate verifier. Existing local native browser/PG restrictions are not bypassed;
exact-head hosted direct/retry-free/aggregate Chromium and PostgreSQL/Compose
artifacts provide those gates. Reconcile every failure, inspect screenshots, tie
evidence to final SHA/tree, update changelog/state/manual/runbooks honestly.

Exit only when C automated acceptance is green on the integrated exact tree,
review findings are closed and current docs identify the real active production
path. Retain physical Windows/Android, screen-reader, first installation and actual
operator upgrade/restore/deployment gates. This is a code-qualified development
MVP, not full business-module or installed-workshop readiness.
