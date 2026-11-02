# Shared local capture checkpoints for same-session reload

Status: **independently accepted for bounded implementation at 2026-11-02 07:37 UTC; implementation evidence pending**.
Base `02ec2f0` (PR80). The user explicitly authorized local IndexedDB draft storage,
24-hour expiry, purge on logout and expired-record deletion on application open
on 2026-11-02. No publication/merge/deployment authority is included.

## Boundary and evidence

Recover customer/order inputs after reload only for the same independently
verified session binding and semantic capture scope. No automatic command replay,
operation guessing, financial change, cross-login recovery or full device-crash/
power-loss durability promise. Stored draft fields are name/contact and order/
bicycle inputs already in CaptureVisit; no credentials or payments.

Artifact-only actual-controller/fake-IDB tests produced six expected failures:
unsent input lost through online/offline restart, and customer/order pending or
unknown admission reopened. A separate actual committed-create probe proves a
pre-submit copied sessionStorage admission can still regain offline READY after
the original submission. Thus per-tab storage/tombstones alone are rejected.
Runtime/source identity manifest covers127 equal files against the existing
installed-dependency worktree; no full-suite or native-browser claim follows.
Evidence: `artifacts/durable-capture/`.

## Selected architecture

Use a shared, admitted IndexedDB checkpoint with a separate expiring content row.
SessionStorage carries only a small **expected-checkpoint hint**, not draft fields
or authority. Its purpose is to distinguish missing expected metadata from first
explicit enrollment; missing data never means UNSENT. The current runtime/kernel
remains the sole admission authority. A stale copied tab sees the same shared
checkpoint status/CAS revision, not its own stale copy of private draft values.

Alternatives: sessionStorage-only fails the proven clone case; shared checkpoint
plus sessionStorage content adds a two-store consistency problem without meeting
the approved durable local-content choice. Reusing presentationPreferences or
operationJournal is rejected: neither expresses draft lifecycle/expiry, and the
journal is immutable business history. Do not persist React objects/view tokens.

## Data shape and identity

Add schema v8 with two stores; versions1–7 and all existing rows are unchanged.

`captureCheckpoints: checkpointId, &bindingKey` (unique binding key)

```
CaptureCheckpoint {
  format: 1
  checkpointId: string           // random opaque enrollment ID
  bindingKey: string             // SHA-256(canonical API realm + session binding)
  scopeKey: string               // SHA-256(canonical verified CaptureVisitScope)
  generation: string             // opaque visit generation, never reused
  closed: boolean
  observedAt: number             // finite wall-clock high-water mark
  customer: ChannelCheckpoint
  order: ChannelCheckpoint
}
ChannelCheckpoint {
  revision: number               // safe integer CAS, increment on every accepted write
  state: 'EMPTY' | 'UNSENT' | 'PROTECTED' | 'UNAVAILABLE'
  attemptId: string | null       // random opaque local fence, NOT a mutation ID
  contentStartedAt: number | null // preserve absolute TTL through protection
  contentExpiresAt: number | null
}
```

`captureDraftContents: [checkpointId+channel], expiresAt`

```
CaptureDraftContent {
  format: 1
  checkpointId: string
  generation: string
  channel: 'customer' | 'order'
  revision: number
  firstPersistedAt: number
  expiresAt: number              // firstPersistedAt + 86_400_000; never sliding
  draft: CustomerDraftState | OrderDraftState
  retainedSelection?: { customerId: string, priority: string } // order only
}
```

Limits: `MAX_CONTENT_UTF8_BYTES = 65_536` for JSON-encoded complete content
projection, `MAINTENANCE_PAGE_SIZE = 64`, exactly two content channels per
checkpoint. No silent truncation: oversized input remains in memory, visibly not
saved for reload, and capture dispatch is refused until its projection is within
the limit. No browser-wide metadata capacity claim or marker eviction is added.
Checkpoint/generation/attempt IDs are canonical lowercase UUIDs; hash keys are
exactly64 lowercase hex characters. Revisions and all timestamps are finite,
nonnegative safe integers; expiry addition and revision increment must remain safe.

Exact schemas/field types are validated; unknown format/fields, wrong generation,
revision or scope never produce restorable content or implicit enrollment. Existing
field values are not silently truncated. Quota/storage failure is explicit. Hashing
is completed before entering IDB, then current source/context is rechecked inside
the transaction. Hashes and IDs are linkable metadata, **not anonymous data or
secrets**. No bearer, names, customer IDs, problem text or exception text enters
checkpoint metadata, logs or DOM attributes.

At most one current customer and one current order content row per enrollment;
no edit history. Old no-content closed/protected metadata is retained rather than
silently rearming an old binding. This is not a bounded total historical byte
claim; metadata compaction is outside this slice and storage exhaustion refuses
new capture dispatch. Payload expiry/purge must not delete checkpoints.

## Enrollment versus missing metadata

`ocwp.capture-checkpoint.v1` in the existing sessionStorage contains only
`{format:1, sessionBindingId, checkpointId}`. It contains no private form input.
An explicit successful login with a **new session binding** may enroll one empty
checkpoint after independent READY. Before enrollment, synchronously write the
expected hint; then create the checkpoint under the current kernel admission.
Failure after writing the hint leaves expected-but-missing metadata: fail closed,
never recreate it as UNSENT. Failure writing the hint means no enrollment/dispatch.

On retained startup, a matching hint requires that exact existing checkpoint.
Missing/corrupt/closed expected checkpoint refuses restore and capture dispatch;
it is never auto-enrolled. A legacy v7 session without a hint remains able to read
its authorized workshop but must explicitly close/login to establish a new capture
binding before using the new capture flow. Ordinary verification/start/reconnect
cannot enroll or reopen a checkpoint. A copied hint cannot change a shared marker. Concurrent same-binding enrollment
with a different checkpointId is refused by the unique index and transaction
check; neither a changed hint nor a scope transition allocates another marker.

An explicit login that reuses the _same_ binding does not clear protected metadata
or migrate input. Require a genuine new binding (existing logout then login obtains
one); do not weaken SessionStore/admission semantics merely to make this convenient.
A new binding starts blank independently, consistent with PR79. It does not prove
any old send failed and offers no universal cross-session duplicate guarantee.

## Scope, admission and transaction API

Semantic scope is the PR79 tuple: realm, organization, user, workshop, dataset
incarnation, authorization epoch, policy revision, normalized capabilities and
session binding; lease/ticket renewal alone does not change it.

Introduce a source-owned typed kernel entry point:

```
checkpointCapture(ticket, command: CaptureCheckpointCommand, current): Promise<CaptureCheckpointResult>
```

Exact proposed source-owned command union (interfaces live in
`access-kernel/capture-checkpoint-types.ts`; content projection lives beside it):

```ts
type Channel = 'customer' | 'order'
type Identity = { checkpointId: string; scope: CaptureVisitScope }
type Expected = Identity & { generation: string }
type ChannelCAS = Expected & { channel: Channel; expectedRevision: number }
type ContentProjection =
  | { channel: 'customer'; draft: CustomerDraftState }
  | { channel: 'order'; draft: OrderDraftState; retainedSelection: RetainedOrderSelection }
type CaptureCheckpointCommand =
  | (Identity & { kind: 'enroll'; generation: string })
  | (Identity & { kind: 'load' })
  | (ChannelCAS & { kind: 'save'; content: ContentProjection })
  | (ChannelCAS & { kind: 'protect'; attemptId: string })
  | (ChannelCAS & {
      kind: 'settle'
      attemptId: string
      outcome: 'saved' | 'not_saved'
      content: ContentProjection | null
    })
  | (Expected & { kind: 'retireScope'; nextGeneration: string })
type CaptureCheckpointResult =
  | { kind: 'ack'; checkpoint: CaptureCheckpoint }
  | { kind: 'scope_changed'; checkpoint: CaptureCheckpoint }
  | {
      kind: 'loaded'
      checkpoint: CaptureCheckpoint
      contents: Partial<Record<Channel, CaptureDraftContent>>
    }
  | {
      kind: 'refused'
      reason:
        | 'missing'
        | 'conflict'
        | 'closed'
        | 'protected'
        | 'expired'
        | 'invalid'
        | 'clock'
        | 'oversize'
        | 'unavailable'
    }
```

`load`/`enroll` do not require an unknowable prior generation; every other command
does. The runtime's explicit-new-binding eligibility is mandatory for `enroll`;
the unique binding index refuses a second checkpoint for that binding. Unknown
result shapes are unavailable, never authorization. Returned objects are detached
and frozen. Load exposes content only for channels eligible under current UI
capabilities; checkpoint metadata is no-content. No raw errors cross presentation.

On a matching binding but independently verified different semantic scope, `load`
returns `scope_changed` metadata only. `retireScope` CAS uses that exact generation
and the newly verified scope: update the existing checkpoint, never allocate a new
ID; advance generation/revisions, delete content and retain PROTECTED/UNAVAILABLE
as sticky no-content denial, otherwise EMPTY. A→B→A never revives prior attempts.

The command's immutable scope is a _candidate_, never authority. Compute its hash
before IDB, then inside existing `run` compare every semantic field against the
actual authorized context. Reuse `validateAdmission` on the partition's current
sessionAdmission; require its owner equals the current ticket and its binding ID
equals the candidate session binding. This fences false same-binding claims inside
the same transaction as checkpoint CAS. No new auth verifier is introduced.

Implementation reuses existing private `run`/`authorized`/lease/current checks.
Extend `run` with an internal optional extra-table list used **only** by this new
entry point; existing command transactions continue using their unchanged table
set and business bodies. Checkpoint calls add the two new stores and atomically
read deviceControl, accessContexts and cachePartitions alongside marker/content
CAS. Require the current ticket generation/tab/partition, active complete baseline,
valid scope/lease/clock and channel capability (`customers.write`, or
`orders.write`+`customers.read`). OFFLINE_READY remains eligible under current
kernel offline checks; do not copy branding's online-only write restriction.

A separate source-owned repository module owns typed row reduction/validation;
it does not duplicate auth admission. Kernel receives only its bounded command,
not an arbitrary public transaction callback. No action or save runs merely
because a hash/hint/record matches. Post-transaction source fences remain; a rejected
promise is never reinterpreted as proof a transaction did not commit.

Deletion-only maintenance below is separate: it can purge content without exposing
it or granting business authority, and cannot transition PROTECTED to sendable.
Its source-owned API is `sweepExpiredCaptureContents(now): Promise<CleanupResult>`
and `purgeCaptureContents(checkpointId, generation): Promise<CleanupResult>`, where
`CleanupResult` is `{kind:'complete'} | {kind:'unavailable'}`. Purge compares exact
checkpoint generation, closes it and deletes matching content atomically; missing
content alone is never used to reopen a checkpoint. A stale generation purge is a
no-op complete because it must not mutate the replacement. Maintenance lives in
`access-kernel/capture-checkpoint-store.ts` and never returns private rows.

## Runtime owner and write ordering

CaptureVisit remains the in-memory/UI owner; do not replace editable state with
whichever asynchronous load happens to return last. Add an immutable persistable
projection (including order retained defaults), separate local edit identity and
persistence generation. Runtime owns per-channel serialized persistence, source
capture and latest requested projection. No historical edit queue, timers required
for correctness, storage-event authority or global singleton.

Every edit remains immediate in memory and schedules a source-bound CAS save.
Show explicit unsaved-to-device state until its exact edit projection is accepted.
Restore loads once after READY and before enabling capture dispatch; reject a late
load if the view/visit or local edit identity changed. Only `UNSENT` with matching
unexpired content can restore editable data; `EMPTY` starts blank; `PROTECTED` or
`UNAVAILABLE` never restores sendable values. Restoration performs no repository
create call. Permission/scope changes hide content immediately.

`save` accepts only the expected current revision and EMPTY/UNSENT channel state.
Successful saves increment revision. Once a channel becomes PROTECTED, queued or
stale saves cannot overwrite it even if their JS promise resolves later. A CAS
conflict does not overwrite another tab; reload current metadata under fresh
admission and present protection/conflict, never last-writer-wins private input.

On same-binding semantic scope change, purge private content and invalidate old
revisions/attempts irreversibly. Existing PROTECTED/UNAVAILABLE remains protected
regardless of A→B→A. Unsubmitted-only state may become EMPTY with the fixed PR79
scope-loss notice. An old view or receipt cannot repopulate purged content.

## Dispatch fence and crash windows

1. Admit the in-memory per-form gate synchronously and capture immutable submitted
   fields/local edit identity, checkpoint generation and fresh attempt ID.
   Local edit identity is distinct from the acknowledged durable CAS revision.
2. Drain prior _own_ queued saves and take their last acknowledged durable
   revision, then commit `protect` against that revision and the captured local
   projection. A queued save can advance the expected revision only through its
   own successful acknowledgment. An external CAS conflict/failed save never
   triggers blind rebasing; refuse dispatch and preserve visible input. This
   avoids capturing a stale pre-drain revision for an immediate edit→submit.
   Commit protection under the current exact kernel source/CAS. It changes channel to PROTECTED **and deletes that channel's
   private content in the same transaction**. Do not dispatch until this operation
   has returned a positively accepted current result. Uncertain/failing protection
   means no create invocation; keep explicit blocked/recovery-failed feedback.
3. Recheck exact source/view after notifications and immediately before invoking
   the unchanged createCustomer/createOrder. A reentrant replacement cannot dispatch
   old input under new authority. A no-dispatch source failure does not silently
   resurrect an earlier UNSENT checkpoint.
4. Await the existing structured capture result. No change to kernel transaction
   classification or native completion ordering. UNKNOWN leaves PROTECTED.
5. On trusted saved/not_saved, settle using the same enrollment/generation/attempt
   token and current independently admitted equal scope. Only this exact settlement
   may replace protection with current UNSENT content or EMPTY. A newer in-memory
   edit is preserved by PR78 revision rules, but while protected it is not persisted
   as a sendable draft. Lost late edits during a crash in this protected interval
   remain explicitly outside the initial unsent-only recovery guarantee.
6. If durable settlement fails or cannot obtain matching current authority, keep
   capture blocked even when the command outcome is known. Fixed copy distinguishes
   saved-local-but-recovery-protection-unavailable from unknown save. Never translate
   known saved into not_saved or encourage retry. A same-visit reverify may finalize
   a retained trusted outcome under fresh equal admission and exact CAS; after
   reload that volatile evidence is gone and PROTECTED remains conservative.

Crashes between protection and business commit produce false-positive protection,
not replay. The fence is NOT an operation receipt and says nothing about commit.
A crash after business commit but before settlement cannot restore old input as
UNSENT. No matching-by-values, journal scan, guessed mutation ID or replay is added.

## Expiry, clock rollback and logout

Channel metadata also retains nullable `contentStartedAt`/`contentExpiresAt`;
`protect` deleting payload must not erase the TTL anchor. `save` cannot reset an
existing anchor. `settle` cannot restart the old generation's24h window: if expired,
it deletes/omits content and leaves the now-resolved channel EMPTY. A subsequent
explicit user edit can begin a new content generation; restore/reverify cannot.

PII TTL is **24 hours from first successful persistence of that content generation**,
not from last edit, restore or reverify. Edits do not extend it. Replacing an old
completed/expired generation with genuinely new input starts a new TTL. A restored
row must have finite consistent timestamps, now >= firstPersistedAt and now <
expiresAt. Capture persistence rejects wall-clock rollback below its checkpoint
high-water mark or kernel observation; rollback cannot extend content retention or
turn a protection marker into UNSENT. Expire content conservatively on invalid/
rolled-back time rather than displaying it. This is not a trusted physical-clock
or browser-closed deletion guarantee. Auth lease expiry remains independent (<24h).

On application open, before any restore, run deletion-only maintenance using an
all-content primary-key keyset scan in pages of64, including when LOCKED/HELD.
Do not depend solely on an expiry index: malformed/missing timestamps would evade
it. Enumerate every content row without returning its content to the controller. Delete expired/invalid private content. Known expired, valid UNSENT becomes EMPTY
with an incremented revision; malformed/corrupt content with an otherwise usable
checkpoint becomes UNAVAILABLE rather than inferred empty. Leave any
PROTECTED/UNAVAILABLE state unchanged. Maintenance must never return private rows
to the caller. A failure disables restoration/capture recovery and is visible;
never claim cleanup succeeded. No background execution while the app is closed.

All logout/dispose/security closure paths synchronously invalidate volatile writes,
loads and attempts. Actual logout additionally requests a deletion-only CAS purge
for its captured checkpoint ID/generation: delete both private rows and mark closed;
retain protected/uncertain marker states. This purge must not close a newer binding
or let late queued writes/receipts recreate data. Automatic security logout is never
vetoed or delayed waiting for user confirmation. Do not purge merely because a
reload disposes its old controller: logout and disposal have distinct durable
semantics, even though both end the volatile visit.

Storage/purge failure cannot promise physical erasure. Close/mask immediately,
retain content-free cleanup-failure feedback. A separate sessionStorage hint,
`ocwp.capture-cleanup.v1 = {format:1, checkpointId, generation}`, is written before
logout purge and is NOT cleared/replaced by new login/session hint updates. Remove
it only after positive matching purge completion. App-open maintenance retries this
exact deletion-only locator before restore. It is a single locator, not an implicit
queue: never overwrite an older uncompleted locator. An overlapping logout can
still attempt its immediate purge, but if no locator can be retained, report that
its unexpired cleanup cannot be retried reliably. If writing/reading the locator
fails or it is lost, only later TTL/all-content cleanup is promised—not next-open
purge of undiscoverable unexpired content. No new login deletes another active
binding merely because it differs from the current session. In all failure cases, do not clear the database or discard journal work.
A storage subsystem that cannot accept a tombstone cannot provide durable purge
proof: communicate failure and keep this claim separate from completed logout.
The design does not assert defense against an independently authorized same-origin
actor with its own still-valid credential, full storage rollback or disk copying.

## Fixed presentation contract

These are source-owned fixed messages, never exception/field interpolation:

- Persisting: `Guardando el borrador en este dispositivo…`
- Exact current projection acknowledged: `Borrador guardado para recuperar al recargar esta sesión.`
- Oversize: `El borrador supera el límite local de 64 KiB. Conserva el formulario y reduce su tamaño antes de guardar.`
- Persistence/fence failure before dispatch: `No se envió la captura. No se pudo asegurar su recuperación local; conserva este formulario.`
- Protected/unknown after reload: `Hay una captura anterior pendiente de confirmar. No la repitas; verifica el estado del taller antes de continuar.`
- Known saved, checkpoint settlement unavailable: `La captura se guardó localmente, pero no se pudo actualizar su protección de recuperación. No la repitas.`
- Known not_saved, checkpoint settlement unavailable: `La captura no se guardó, pero no se pudo actualizar su protección de recuperación. Conserva este formulario; no lo envíes de nuevo desde esta vista.`
- Expired: `El borrador local caducó y sus datos se eliminaron. Esto no confirma ni revierte ninguna captura anterior.`
- Cleanup failure: `No se pudo confirmar la eliminación de los borradores locales. Sus datos podrían permanecer en este dispositivo.`
- Enrollment missing/unavailable: `La recuperación de capturas no está disponible en esta sesión. Cierra sesión e inicia una nueva para continuar; esto no confirma los envíos anteriores.`

Keep command outcome separate from recovery persistence status. Pending persistence
is not a saved checkpoint. A protection marker is not proof of business commit.
Existing role=status/aria-live and masks remain; no secret/content data attributes.

## Migration and retention acceptance

V8 adds only stores/indexes; no business rows, caches, queues or journals are rewritten.
Keep versionchange close. Upgrade blocked by an old client is reported; no forced
DB deletion. Test actual v7→v8 data preservation, aborted upgrade, concurrent old
connection, v7 binary reopening newer DB refusal, malformed rows and recovery.
Tests currently using synthetic future-v8 must use future-v9 preserving intent;
older quote-increment plans reserving future-v8 need explicit supersession notes,
not silent historical edits. Old clients do not implement the new recovery flow;
never claim universal capture idempotency across intentionally old runtime code.

Content is browser-local plaintext under existing device-security assumptions.
Existing server backups do not include IndexedDB; no export/restore support for
these rows is added. A restored/copied DB is not authority: owner/admission/scope
checks and conservative protection remain required. No new cryptographic-at-rest,
eviction, physical capacity or full-crash qualification claim.

## Planned verification before acceptance

- Preserve six baseline REDs and clone counterexample; same-session online/offline
  restore with zero create calls, immutable existing journal and hidden bicycle data.
- Pure state/CAS tests for every field/default, first-write TTL, clock rollback,
  missing/corrupt marker/content, stale revision/generation, A→B→A and closed state.
- Actual kernel transactions: same-binding/different-ID enrollment refusal and concurrent unique-index race, owner takeover between read/write, cloned hint before
  original commit, delayed autosave versus protect, quota/abort/uncertain settlement,
  crash cutpoints around protect/create/settle and deletion failures.
- Both channels independently protected; explicit new binding starts empty without
  migrating old input; old PROTECTED survives TTL/logout and late callbacks.
- Native same-tab reload and two-context cloned-storage journeys, inaccessible DOM
  while nonready, truthful persistence status, keyboard/axe. No synthetic terminal
  events or fabricated saved outcomes.
- Actual v7 migration/old-client tests, full retained suites, strict types/lint/build
  and independent design/source review. Native/full-device evidence remains separate.

## Independent design review

The design and three-task implementation plan were independently accepted at
2026-11-02 07:37 UTC. Exact command/result unions, enrollment ordering, legacy
session fail-closed behavior, same-scope settlement, marker retention and deletion
failure reporting are the accepted implementation contract. This acceptance is
not source, native-browser or completed verification evidence.

## Reviewed implementation corrections and current blocker

During implementation, independent review accepted explicit voluntary same-workshop
retirement as distinct from semantic-scope revalidation. A deletion-only
`retireCaptureContents(db, checkpointId, generation, nextGeneration)` transaction
requires the exact existing generation, advances generation and both CAS revisions,
deletes both private rows, preserves PROTECTED/UNAVAILABLE and never reopens a closed
checkpoint. `CaptureRecovery.retireVisit()` removes the expected hint synchronously,
invalidates the volatile lifetime, and restores the same checkpoint hint only after
positive retirement and only in that same still-current lifetime. Failure leaves
capture unavailable with a content-free cleanup warning. Ordinary load cannot invoke
this deletion to clear protection. Accepted departure to the selector masks immediately;
retirement finishes before selection is offered, including selecting the same workshop.

Cleanup failures are exposed through a separate content-free global runtime notice,
including LOCKED/HELD branches where capture forms are absent. Successful expiry sweep
cannot hide an unresolved failed logout purge. Exact positive cleanup clears only its
own warning; no mere new login or view change claims deletion.

**Historical pre-correction blocker (superseded by the approved protocol below; final evidence still required): mixed-version compatibility.** Actual old-v7
runtime execution can commit a command while leaving a v8 UNSENT checkpoint stale;
a subsequent new runtime restores that input and can submit a second distinct command.
IndexedDB schema version alone does not prevent Dexie old bundles reopening the database.
The independent actual-runtime probe retains this counterexample. A proposed shared
writer epoch/sequence guard would change the existing command transaction and therefore
required separately explicit approval and review, subsequently obtained as recorded below. No completed
same-session anti-replay claim, publication readiness or browser qualification follows
from the current happy-path tests.

## Reopened integrity gate — 07:50 UTC

The initial design acceptance does not cover the independently reproduced mixed-v7/
v8 duplicate-creation path. Old Dexie can reopen the newer database and commit
without updating capture checkpoints. New recovery then restores a stale UNSENT
draft. The implementation is NOT READY. Expanded atomic shared-commit protocol
design and explicit scope approval are pending; no publication or integration.
See the current evidence record and `artifacts/durable-capture/mixed-writer-design-gate.md`.

## Approved mixed-writer protocol correction — 2026-11-02 07:54 UTC

The user explicitly authorized expanding the internal shared save protocol after the
actual old-v7 duplicate probe. This supersedes the earlier prohibition on changing the
command transaction body, only for the following atomic metadata guard. Authorization,
operation validation, immutable journal contents and command result semantics remain
unchanged; no new transaction tables or replay capability are introduced.

`DeviceControl.captureWriter` is optional legacy-compatible metadata:
`{ format: 1, epoch: UUID, coveredSequence: nonnegativeSafeInteger }`. The object must
have exactly these three keys. It is healthy only when its shape is valid and
`coveredSequence === DeviceControl.localSequence`. Every new checkpoint also has a
required `writerEpoch: UUID`; old rows missing this field are invalid, not auto-migrated.

1. In the existing admitted transaction for each genuinely NEW command, after existing
   validation and exact-ID collision/no-op checks, preserve the epoch iff the writer is
   healthy against the pre-append sequence. Otherwise choose a new random UUID epoch.
   Persist that epoch with `coveredSequence = new localSequence` in the SAME
   `deviceControl.put` and transaction as the journal append and existing delivery/events.
   A grouped write uses the same mutable authorized control: the first new append may
   rotate; subsequent appends retain the now-healthy epoch. Aborts roll back both journal
   and writer metadata. Exact-ID no-ops return before writer updates and never heal a gap.
2. Every existing checkpoint load/save/protect/settle/semantic-retire must observe a
   healthy writer and `checkpoint.writerEpoch === writer.epoch` inside the SAME admitted
   owner/CAS transaction. Missing/malformed writers, sequence gaps and different epochs
   refuse without returning private content or changing the checkpoint epoch. A later
   healthy new-runtime command may rotate the device epoch; it MUST NOT make the old
   checkpoint usable again. This is sticky old-checkpoint invalidation, not a permanent
   principal/device-wide deny.
3. Explicit fresh enrollment first proves no existing checkpoint ID and no checkpoint
   for the admitted binding. Only then, in the SAME transaction that creates an EMPTY
   checkpoint, it may initialize/rotate an unhealthy or absent writer and record that
   epoch. Healthy writer epochs are retained. Rejected enrollment changes neither
   writer nor checkpoint. It never creates a fresh draft for a binding with an old row,
   migrates old fields, or treats a missing expected hint/row as enrollment permission.
4. Deletion-only expiry/logout/explicit-visit-retirement may purge/fence despite writer
   mismatch, but preserve the checkpoint's old epoch and never repair the device writer.
   Retirement cannot make an old epoch sendable. None of this claims prevention of all
   manual duplicate business actions or protects against arbitrary tampering with IDB.

Implementation adds pure writer-shape/epoch-selection helpers alongside checkpoint
validation; store enrollment/load validates the actual `deviceControl` in its existing
admitted transaction. Business transactions retain their original table list. Required
new evidence: real old-v7 commit then new restore refused; old→new legitimate append→old
restore still refused; exact-ID no-op cannot heal; grouped writes, rejected enrollment,
missing/malformed metadata, rollback/quota and fresh-binding blank start. The independent
mixed-v7 probe must change from its demonstrated unsafe outcome to a positive denial
assertion, not be removed or relabeled as unsupported.

### Implementation review: logout before hydration

Logout may occur while a new runtime has no hydrated checkpoint head. The expected
hint is captured before auth clearing; a bounded metadata-only checkpoint lookup resolves
its generation and requests the same exact-generation purge/cleanup locator. Private
payload is never loaded from this path. Lookup or hint failure produces the global
cleanup warning; if no generation can be discovered and retained, only the existing
TTL cleanup fallback is promised, not unexpired retry or successful deletion. This
path cannot restore hints, authorize reads or reopen capture.

## Bounded offline branding continuity correction — 2026-11-02

Native qualification exposed interaction between admitted checkpoint writes and the
existing strict cached-image entry-time fence: two finite local writes can invalidate
both original and trailing reads. Do not weaken those authority/clock fences. Signal
normally completed current-source save/protect/settle calls and eligible capture
completion explicitly to the branding display owner. Resolved refused writes may
also advance the observation fence: an ephemeral internal completion marker allows
that event without claiming persistence or changing refusal feedback. Emit only after
outcome publication and a fresh active/exact-source check; caught throws and preflight
failures do not emit. Only offline contexts
without a verified displayed profile are eligible. Coalesce at most one owed read per
flight, including a trailing flight, and recheck offline/current binding/generation
when draining. Clear/logout/takeover invalidate owed work. A null result, publication
or thrown/preflight-failed/late completion must not manufacture an activity event. Online typing
must not add transport reads. This is finite-activity convergence, not timer polling,
unbounded failure retry or broader cache authority. Preserve actual edit-only and
edit-plus-submit RED/GREEN evidence plus cancellation/coalescing/mutation checks.
