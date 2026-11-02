# Volatile capture continuity through verification

Status: **bounded design and implementation independently reviewed; hosted evidence pending**.
Base main `b88c4eee78d0603bb47368bcec83cd9567eac495` (PR78). Ordinary engineering
selection under the Master Loop's data-integrity priority and Foundation TA-01/03;
not a claim of human architectural approval or permission to publish this package.

## Requirement and demonstrated boundary

Phase 4 UX §22 calls for draft/local-change recovery and clear pending state;
Phase 1 FR-CUS-001, FR-SVC-001 and OFF-001 provide existing capture context.
This slice addresses **automatic same-scope verification in one controller visit**,
not full crash/reload recovery. PR75 explicitly deferred capture ownership; PR78
fixed late receipts only while a form remains mounted. Neither is reopened as a
failed completed requirement.

`reconnect()`/`retryVerification()` lead through `blank('verifying')`; actual App
replaces WorkshopShell and its two capture children with the nonready branch.
Restoring the same React key does not restore previously unmounted hook state.
Fresh exploratory tests on unchanged base fail seven behavioral assertions:
customer/order values (including hidden bicycle fields) disappear; both UNKNOWN
and PENDING forms admit two repository-boundary invocations instead of one; saved
order customer/priority clean defaults disappear. Actual controller, App TSX and
capture handlers are exercised with fake IDB and simulated hooks/reconciliation.
This is **not native React/browser proof**; unknown/pending instrumentation rejects
before writes and does not demonstrate persisted duplicates. Evidence remains in
`artifacts/capture-visit/` and will be promoted to maintainable regression coverage.

## Alternatives and selection

- Keep private workspace DOM mounted through verification: rejected; preserve the
  current visibility fence and actual unmount.
- Lift only submission guards: rejected; still silently loses entered input.
- Global singleton or a map of previous principals/drafts: rejected; unnecessary
  ownership, confidentiality and retention surface.
- **Selected:** a controller-owned volatile capture visit with exactly one current
  customer draft and one current order draft, their revision/defaults and guards.
  This is not IndexedDB, journal recovery, a persistence schema or execution authority.

No kernel, repository transaction, auth-admission, backend, workflow, dependency,
plugin, financial command/replay, Pages, physical-test or consumed-measurement changes.

## Owner and presentation

Introduce a pure capture-visit model owned privately by WorkshopController. Retain
all existing fields, hidden bicycle state, clean retained selection, opaque edit
identities, fixed feedback, per-form pending/unknown guards and opaque attempts.
Keep one current value per existing field, no history, TTL, eviction or per-user map.
Do not silently cap/truncate existing inputs. This is bounded in forms/entries,
not a newly measured byte/capacity claim.

A separate opaque **view token** is issued for each freshly READY source and
invalidated synchronously on nonready/closed/mismatched state. It is a local view
identity, not execution authority. Edit and submit handlers capture it; runtime
requires the current token, exact current source, READY and matching visit/scope.
Old unmounted handlers cannot edit even a same-scope remount or new visit. Ordinary
field updates/refreshes within the same ready source do not rotate this token.
Attempt tokens are separate and may settle across masked re-verification.
Updates name one whitelisted typed field rather than replacing a stale full draft.

CustomerQuickCreate and OrderQuickIntake become controlled views of this owner;
changes and submissions go through runtime capture methods. Settlements update
owner state rather than unmounted React setters. Preserve existing accessible
labels, value-based dirty semantics, editable fields during pending/unknown and
PR78's same-value/ABA revision fence. Existing low-level createCustomer/createOrder
and repository authorization remain unchanged; the new guarantee concerns the
application capture flow, not universal programmatic idempotency.

Runtime snapshots expose private capture values **only in READY with a current
independently verified matching scope**. Nonready snapshots expose no names,
customer IDs, text, messages containing input or authority objects. A content-free
unsent/protected boolean may support voluntary-leave confirmation. Centralize
snapshot masking so any publish/blank/held path cannot retain an earlier private
snapshot. Return detached frozen nested objects; presentation never authorizes a
command. No raw exceptions or draft content in logs/status/DOM data attributes.

## Scope and lifecycle

Scope is the exact tuple: API realm, organization, user, selected workshop,
dataset incarnation, authorization epoch, policy revision, normalized capability
set and session binding. Generation, admission ticket, verifiedAt and offlineUntil
renewal do not by themselves change semantic scope. Scope equality is not authority.
Every actual repository action retains its current kernel/session checks.

- Constructor starts one empty visit; start() does not reset it.
- Automatic verification, held/retry, offline/reconnect, refresh, paging and sync
  do not clear it or submit anything.
- Explicit login starts a new visit; accepted workshop selection does so only after
  existing selector/membership guards. Voluntary departure must be confirmed first.
- changeWorkshop, all logout paths and dispose synchronously close the visit and
  invalidate attempts. Automatic security paths that actually log out always win;
  they must never wait for a user confirmation. Private owner references are released;
  no claim of physical memory erasure or rollback of outstanding work is made.
- A closed visit cannot be reopened by automatic retry/reconnect. Fresh explicit
  login/accepted selection starts empty; no cross-login/reload recovery is promised.

Boundary matrix (use actual operations, not inferred meanings of error text):

| Runtime operation                                                                                                                 | Owner/attempts                                                                                          | View/input exposure                    |
| --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| blank, held, cancel, reconnect, retry, offline expiry, verification failure, takeover hold, temporary security-command suspension | Retain masked visit and attempts                                                                        | Invalidate view; no private snapshot   |
| verified authority refresh that clears/rebinds stored admission while remaining held                                              | Retain masked old scope until new verified scope comparison; never adopt from the intermediate snapshot | No private snapshot                    |
| logout from any caller (including proven invalid account/principal), explicit changeWorkshop, dispose                             | Close, release private owner references, invalidate attempts                                            | Closed/content-free only               |
| explicit login or accepted selection after existing guards                                                                        | Start a new empty visit                                                                                 | Still hidden until independently READY |
| freshly READY equal semantic scope                                                                                                | Retain drafts/attempts                                                                                  | New view token; current source only    |
| freshly READY different semantic scope                                                                                            | Apply irreversible mismatch policy below                                                                | Only new empty state or generic deny   |

Do not insert an owner reset into blank(), held(), cancel() or generic
invalidateAccount(): those also represent temporary verification and masking.
A hold is not proof of revocation/rollback; existing security machinery still
locks admission immediately. Actual logout closes regardless of caller.

Before READY publication, observe the verified semantic scope. On mismatch,
release all old values/defaults/feedback and invalidate old attempts irreversibly;
A→B→A cannot resurrect them. If an attempt is pending or unknown, retain only a
sticky generic **capture-only deny** until a new explicit visit. Otherwise adopt
an empty new scope; if an unsent draft was lost at that boundary show fixed notice:
`Los formularios anteriores no están disponibles en este contexto.`
Clean retained defaults also reset on mismatch, without implying unsaved work.
Read/transition/sync authority must not be changed by capture-only protection.
Generic deny copy:
`Hay una captura pendiente de confirmar de la visita anterior. No la repitas; las nuevas capturas están bloqueadas en esta visita.`
No automatic journal lookup, value matching, operation guessing or replay follows.

## Attempts and late receipts

Admit synchronously before the first await, one pending attempt per form; the
other form remains independent unless the visit is closed/denied. Capture immutable
submitted values and edit identity with an opaque token bound to form and visit.
Controller captures current source and must not dispatch old input under a new
source after a reentrant publication. Establish the owner gate, then either
dispatch before synchronous notification or recheck exact captured source and view
after notification, immediately before invoking the unchanged create method.
Failure to establish current admission does not dispatch a repository command.

Decode outcomes with the existing closed captureFeedback/captureValidation rules.
UNKNOWN/rejected/malformed remains blocked even after editing or emptying fields;
proven not_saved permits another explicit attempt and preserves current input.
A saved receipt resets only a matching revision; retain PR78's truthful older-save
copy otherwise. Unchanged saved orders promote only their own customer/priority
as clean defaults. A token settles once; stale visit/attempt completions cannot
reset fields, clear a new busy flag, unlock UNKNOWN or publish old feedback.
Late settlement during nonready may update retained owner state, never expose its
private values before matching fresh READY. Native completion observed by a test
is not authority to reinterpret the repository's UNKNOWN result.

## Voluntary leave while forms are absent

Combine the capture owner's unsent/protected signal with existing DOM dirty checks
in BOTH App.leaveWorkshop and administration's logout guard. Guard the LoginForm
explicit session-replacement path too; it currently bypasses leaveWorkshop.
Rejected confirmation leaves owner and controller untouched. Confirmed departure
may discard the volatile owner, not saved journal work. Fixed confirmation must
explain that leaving neither confirms nor rolls back a pending submission; do not
suggest it permits repeating uncertain work. Use one fixed confirmation in all
three voluntary paths:
`¿Continuar y descartar los formularios sin enviar o sin confirmar? El trabajo local ya guardado se conserva. Esta acción no confirma ni revierte los envíos pendientes; no los repitas.`
Automatic blanking/auth expiry,
revocation/takeover or controller disposal must never be vetoed by this guard.

## Verification required

1. Preserve and rerun the seven functional RED reproductions against the fixed
   actual controller/component path; refactor fixture copies into bounded reusable
   test infrastructure without changing expected behaviors.
2. Pure owner tests: all fields/defaults, same-value/ABA, pending/unknown, every
   outcome, both channels, token once, old visit, every scope field, capability
   ordering, A→B→A, immutable snapshots, no automatic dispatch.
3. Controller/UI tests: real reconnect and held/retry masking, both leave guards
   and explicit login canceled/confirmed while nonready, security invalidation
   unblocked, admission reentrancy, late results after scope/new visit, retained
   PR78 29 cases and all existing transition protections.
4. Actual PWA cases: genuine verification removes forms; same-scope READY restores
   draft/defaults and pending/unknown protection. Use existing test-only barriers
   without fabricating saved results or changing native terminal-event order.
   Check immutable journal identity, no second admission, privacy, keyboard/axe
   and screenshots. Browser cases remain unverified until executed.
5. Full frontend/Python/static/build and independent final review. Publication and
   conditional integration require separate explicit authorization for this package.

R01-T035, physical Windows/Android, actual installation/recovery/capacity,
durable capture-intent/batch correlation and full crash/reload drafts remain open.
Historical cleanup UNKNOWN, spent ownership40927223929 and Pages source remain unchanged.

## Closed-empty presentation ruling

An explicitly closed empty visit remains disabled but clean, with neutral copy:
`Las capturas no están disponibles en esta visita. Inicia una nueva sesión para continuar.`
It does not claim a pending attempt; sticky mismatch denial retains its distinct
protected-attempt warning. Both states reject stale handlers and cannot reopen
without the explicit new-visit lifecycle.
