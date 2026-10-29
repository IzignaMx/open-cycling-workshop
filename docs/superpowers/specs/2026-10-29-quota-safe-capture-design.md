# Quota-safe customer and order capture

Assistant-selected design under delegated technical decisions; not a claim of
human design approval. Source baseline main `6106028696c02b70a891c0d2bf44aeaeaf5fbcc3`,
tree `e6bc0218adc6396f286ba9fc5ace314bd1a75924`. Design review precedes implementation.

## Intent and requirements

Complete the bounded user-facing storage-failure path for the existing customer
and order intake forms. V0.1 remains partial. The manual checklist's IndexedDB
quota/recovery gate and Phase 6 QA sections 16/66 require explicit degradation,
preserved data, no duplicate effects and actionable recovery. The offline identity
kernel recovery contract forbids clearing IndexedDB, deleting queues, changing
origins or uninstalling as normal recovery.

This plans synthetic failure-handling evidence, not a capacity measurement, actual
browser eviction result, physical Windows/Android/Pi qualification or permission
to rerun consumed ownership run 40927223929. Its grant remains spent and historical
admission/cause unknown. No loader, module activation, grants, routes, schema
migration, persistence prompt, new store, backup/export or deployment is added.

## Source-grounded boundary

`runtime/repositories.ts` prepares customer or bicycle-plus-order commands and
calls `AccessKernel.commitLocalCommands`. The latter clones/validates the batch
and reuses `run` to execute all commands in one Dexie read-write transaction over
existing kernel tables. Tests already prove rollback of journal/delivery/events
and sequence on quota failure. Do not duplicate that transaction/store logic.

Crucially, `access-kernel/kernel.ts:run` can throw a session-fence error AFTER the
transaction has completed. Consequently a rejected public promise, Error.name,
message, or previously seen error object is not proof of rollback. Independent
review also reproduced Dexie 4.4.4 transaction-scope rejection AFTER native commit:
PrematureCommitError, generic Error and QuotaExceededError each left the row
persisted. The initial local proposal (design SHA
`44142234aca3f8a1d7f3d55625ab2ee10a4d761bcb0d95239d3821bd4fac303e`)
incorrectly equated awaited transaction rejection with rollback; review rejected
that premise before implementation. This amendment does not claim that proposal
was approved. A genuine abort can also be observed after the rejection catch. Normal
`runtime/controller.ts:refresh` catches read failures and enters an existing
hold; do not invent a refresh-rejection defect or weaken this behavior.

Both forms currently clear fields only after their callback fulfills, but echo
arbitrary Error.message on rejection. Order normalization has safe fixed errors
and one dynamic priority message. Keep useful validation guidance without
reflecting input values or arbitrary exception text.

## Approaches and selected decision

1. Presentation-only classification by exception name: smallest, but cannot prove
   rollback and would invite duplicate resubmission. Rejected.
2. Treat every rejection as unknown and permanently block the form: safe but even
   confirmed quota aborts cannot be retried meaningfully. Not selected.
3. **Selected:** capture-only structured transaction outcome, with the rejection
   boundary requiring positively observed native transaction abort by the awaited
   Dexie rejection catch. No event observation means unknown, not rollback. Existing noncapture
   behavior and authorization fences stay unchanged; forms consume the trusted
   source-owned capture result, not arbitrary exception names.

## Kernel and repository contract

Add `commitLocalCommandsOutcome(ticket, supplied, current)` returning
`Promise<{ status: 'committed'; mutationIds: string[] } |
{ status: 'not_committed'; reason: 'quota' | 'write_failure' }>`.
Only customer/order capture uses this method. Transition and existing
`commitLocalCommands`/`commitLocalCommand` consumers retain original return and
throw semantics. Share existing clone/validation and atomic batch body through
small private helpers; no second transaction implementation.

The private `run` may receive a capture-only internal observation option. Keep
existing pre-transaction checks, `outcome.ok` authorization handling and postcommit
fence checks outside rejection classification. For capture, refuse an existing
Dexie transaction before starting writes: a nested transaction can settle before
its parent commits. Recheck that the transaction callback's actual transaction has
no parent and belongs to this database before invoking the existing action.

Inside the actual transaction callback, before any authorization/action work,
attach transaction-local native `abort` and `complete` event listeners to that
transaction's public `idbtrans` (locked Dexie 4.4.4 types expose `idbtrans` and
`parent`). Do not replace Dexie's handlers, use request errors as abort proof, or
reach into private `_completion` APIs. Track exact target identity and conflicting
terminal observations. A rejected await may return not_committed ONLY when a
native abort was positively observed for this exact top-level transaction before
the catch, with no complete/conflict evidence. Complete, missing observer, pending
abort, observer failure or contradictory evidence remains thrown/unknown. Remove
listeners on settlement; no late event can retroactively promote a returned result.
No timer, grace window, additional wait/deadline, transaction topology change or
keepalive is introduced. Success retains existing authorized-result/fence checks.

This deliberately does not make every genuine quota abort retryable: locked
Dexie/fake-IDB review observed rejection before the native abort event. If actual
browser fixtures also take that ordering, report unknown honestly; do not synthesize
listener order or relax the contract for green tests. This is selective proven-abort
recovery plus safe unknown handling, not universal quota retry support.

A fresh result is created per invocation. No global WeakSet of error objects,
reusable rollback brand, exported error constructor or external mapper. Classify
native/Dexie-wrapped QuotaExceededError only AFTER positive abort proof, using a
bounded defensive unwrap (cycles or throwing getters fall back to write_failure).
No raw cause is retained or rendered. Arbitrary callback errors, postcommit fences
and even quota-named transaction rejections without abort evidence remain unknown.

Repository createCustomer/createOrder return a source-owned capture outcome in
addition to their successful entity: committed, not_committed, or a bounded
pre-write validation result. Domain builder validation is classified only before
any kernel call; fixed known messages are retained, dynamic invalid priority is
mapped to fixed `Selecciona una prioridad válida`. Unknown preparation failures
still throw. Capture/session errors are not reclassified merely by matching text.
The form-facing controller methods return `CaptureSubmissionResult`:
`{ status: 'saved' } | { status: 'not_saved'; reason: 'quota' | 'write_failure' } |
{ status: 'not_saved'; reason: 'validation'; code: 'customer_name_required' |
'order_problem_required' | 'priority_invalid' | 'bicycle_brand_required' }`.
No result carries arbitrary message text; presentation maps these closed codes.
This is an internal source-owned port, not an extension API, credential or proof
against malicious same-origin code. Unrecognized results/rejections are unknown.

A committed repository result follows existing refresh/wake/session behavior.
Do not turn a postcommit read hold into not_saved or revive stale-session work.
No automatic retry occurs at any layer.

## Form behavior and fixed copy

Use a shared small presentation/state helper, not a new global error framework.
`captureFeedback(input: { kind: 'resolved'; value: unknown } |
{ kind: 'rejected'; error: unknown }): CaptureFeedback`, where CaptureFeedback is
`{ status: 'saved' | 'not_saved' | 'unknown'; message: string | null;
blockSubmission: boolean }`. Saved message is null (each form retains its existing
success copy). Validate exact result shapes/codes; rejected errors are always
unknown here. Classify synchronous order normalization separately before callback
invocation using only known fixed validation codes; never echo dynamic values.

- saved: retain existing success copy and existing field-clear/default behavior.
- quota, proven not committed: `No se guardó: falta espacio de almacenamiento en
este dispositivo. Conserva este formulario y libera espacio sin borrar los
datos de esta aplicación. Después puedes volver a intentar guardar.`
- other proven native abort: `No se guardó el cambio. Conserva este
formulario y vuelve a intentarlo cuando el almacenamiento esté disponible.`
- pre-write validation: existing safe fixed Spanish guidance; no input echo.
- unknown: `No se pudo confirmar si el cambio se guardó. No lo envíes otra vez;
verifica el estado del taller antes de continuar.`

Retain every draft field on any nonsaved outcome. Unknown sets a local
submission-blocked latch: subsequent submit events do not invoke the callback,
even after editing. Do not add a retry/reset button that pretends to resolve
uncertainty. Existing explicit navigation/session boundaries remain; no new draft
persistence, cross-session retention, or automatic navigation. The visible status
explains the block; the latch itself contributes data-dirty=true even when every
field is cleared. A synchronous submission guard rejects busy/latched reentry
before callback invocation; React disabled rendering alone is insufficient. This
mounted-form latch is not a durable duplicate-prevention guarantee across explicit
discard/navigation or session changes; preserve those existing boundaries. Quota retry is
an explicit subsequent user submission only after proven noncommit; each positively observed
aborted transaction contributes no committed effects. Never promise that freeing space worked.

Keep role=status/aria-live, aria-describedby, keyboard focus and busy disabling.
Do not expose exception text to status, logs or diagnostics. Input editing while
busy is unchanged unless an independently reviewed concrete regression requires
scope reconsideration. No global kernel error semantics change.

## Acceptance and evidence

- Real existing kernel/repository with fake IndexedDB: native and actual Dexie
  quota errors at a later journal/event write prove full rollback separately from
  whether abort evidence arrived in time for a retry-safe result; bicycle/order
  batch and prior unrelated records remain intact; sequence unchanged.
- For positively observed abort cases only, remove the fault and explicitly submit once: exactly one customer, or one
  bicycle plus order, with expected journal/delivery/events and no duplicates.
- Retain the three independently reproduced persisted-after-rejection negatives
  (PrematureCommitError/generic/quota), abort-after-catch unknown, missing/conflicting
  observations, and nested capture refusal before writes. No error-name blacklist.
- Same original Error object reused in a later postcommit/current callback cannot
  inherit a rollback classification. Pre/postcommit fences remain unknown.
- Existing noncapture API returns/throws are identical. Postcommit refresh hold,
  session replacement and wake fences retain their existing behavior.
- Presentation tests cover thrown native/Dexie quota without trusted outcome,
  unknown/malformed results, raw-message canaries, validation, draft/default
  retention, unknown-latch repeated submit and explicit retry after not_saved.
- Actual built-PWA browser tests use existing authenticated synthetic fixtures,
  controlled IDB prototype write failure in test context only (as existing theme
  tests do), no production hooks or genuine disk filling. Prove visible message,
  unchanged operational snapshot and preserved form. Observe actual native event
  ordering: retry exactly once ONLY for proven-abort results; otherwise assert
  unknown/no-repeat and report the practical recovery limitation. Never dispatch
  synthetic abort/complete events or alter listener ordering to obtain a result.
  Check dirty-form
  guard and keyboard/status/axe behavior for both forms. Cover all existing theme
  structures without multiplying runtime unnecessarily. For a real unknown UI
  path, inject a bounded `crypto.getRandomValues` failure after ready/offline so
  existing newUuidV7 preparation rejects; restore the function and prove edits/
  Enter do not re-invoke capture. This is conservative preparation uncertainty,
  not a simulation of actual postcommit failure; that boundary has kernel tests.
- Existing focused/full core, lint/typecheck/build and full hosted qualification
  must pass exact reviewed source under unchanged limits. Physical capacity,
  eviction and screen-reader/touch acceptance remain open.

## Review gate

Independent review must challenge transaction-completion provenance, accidental
noncapture behavior changes, error-object reuse, authority/session races,
postcommit holds, unknown resubmission and tests' real integration boundary. No
implementation begins before this design and its plan are reviewed. No unresolved
product choice is silently treated as approval; consequential expansion stops.

## Local implementation checkpoint (not hosted/browser qualification)

The reviewed amendment is implemented locally. The normal frontend core runner
passed **959/959** with no skips: 25 added cases (15 kernel, 6 runtime and 4 shared
feedback cases) plus all 934 retained cases. TypeScript build and production Vite
PWA build pass; the existing >500 kB chunk warning remains, with no threshold
change. The actual browser suite has four new production-PWA cases, discovered
and statically checked but **not executed locally**: the pinned browser and
API/PostgreSQL fixture are unavailable. Exact-source hosted checks and independent
whole-patch review remain required before integration.

The first full local run was 939 passed/8 failed, not erased by this checkpoint.
Seven session-admission failures exposed an eager Dexie import initializing before
existing IndexedDB fixture setup; a type-only import, actual transaction callback
parameter and public inherited constructor accessor preserve initialization order.
The remaining retained controller test represented offline via its navigator hint
while its mocked transport still answered the existing two-second reachability
probe. A source-bound trace showed reconnect and dispatch racing the test's direct
synthetic delivery rewrites. Independent review accepted a correction **only in
that test**: transport fails during its stated offline phase and resumes at its
existing explicit reconnect. All 51 captures, assertions and production timers
remain unchanged. The untouched baseline passed one focused run; this was not
misreported as a consistently failing baseline or fixed by raising a timeout.

Positive native-abort unit cases deliberately delay the synthetic transaction
scope's rejection until a real native abort event. They prove only the narrow
already-observed-abort classification, not naturally occurring quota event order.
Natural hook rejection precedes abort in the local emulator and remains unknown.
No synthetic terminal event is dispatched. Conflicting native abort/complete
observations are conservatively refused by the implementation, but that defensive
branch is not experimentally exercised: a valid native transaction cannot emit
both terminal outcomes. Actual browser tests observe, never alter, native order.

PR72's receipt correction is separately integrated at main6106028/treee6bc0218,
with fresh CI40938841480 independently accepted (27/27; 5,499 passed/58 expected
skips; direct86/aggregate86 plus retained repeats/kernel, retry0). This record does
not turn the spent ownership run40927223929 into a successful measurement: owned
cleanup absence is proven, actual admission and historical cause remain unknown.
