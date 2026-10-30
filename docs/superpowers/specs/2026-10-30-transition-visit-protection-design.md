# Transition protection through automatic verification

Status: assistant-selected bounded design independently reviewed; local
implementation reviewed and tested, hosted runtime qualification pending. Baseline main `ff890bca`,
tree `f9ddd024`, PR74 fresh CI40994045589 accepted. The local source-equivalent
baseline is frozen commit `4c18730f`; publication must use the actual current main.

## Source facts and scope

`App.tsx` unmounts its ready workspace during verification and keys WorkshopShell
by `identityKey`. `OrderList` currently owns its synchronous gate, so automatic
reconnect loses that protection. Do not suppress verification or keep private
workspace DOM visible to preserve a latch. Existing reconnect/authentication and
kernel fences remain mandatory.

`runtime/repositories.ts` generates new mutation IDs inside each invocation;
UI outcomes do not retain a pre-dispatch intent handle. `kernel.readOperation`
supports exact authorized positive lookup, but missing/inaccessible rows do not
prove rollback. Matching values, order state, latest events or refreshed pages
cannot identify a particular unknown attempt. This design performs no lookup,
replay, draft recovery or durable intent correlation.

The smaller proposed create-refresh fix was rejected as unproven: normal refresh
read failures are already caught and held, and current tests prove saved status
survives that failure and source replacement. Do not manufacture a refresh-throw
test to claim an ordinary read failure is a product defect.

## Alternatives and selection

1. Keep workspace mounted while verification runs: rejected; weakens visibility
   fences and still cannot survive reload.
2. Global singleton or previous-principal map: rejected; broad ownership, memory
   and confidentiality risks.
3. **Selected:** one host-runtime-owned volatile workspace visit, order-transition
   protection only. It extends the existing gate across automatic verification;
   it does not create execution authority or persistent recovery state.
4. Capture forms and prepared exact-operation/durable handles: separate designs.
   Moving capture guards alone would still lose entered drafts on unmount; do not
   add an implicit private draft store. Grouped bicycle/order intent correlation
   requires immutable batch membership, not one guessed mutation.

This data-integrity slice precedes speculative M1 breadth under Master Loop §5.
OFF-003/005/007/008/009/012 remain applicable; full-reload and physical R01-T035
requirements are not closed by volatile protection.

## Lifetime and identity

A fresh controller construction begins exactly one empty volatile visit. This
allows existing retained-session online/offline startup to become usable after
all its existing admission guards pass; it is NOT recovery of the previous
process's protection. start() never resets the owner. Automatic retry/reconnect
cannot reopen a visit closed by logout. Test startup and post-logout separately.

Explicit login begins a new visit. Accepted workshop selection begins a new visit
only AFTER its existing selector/location-membership guards pass; changeWorkshop
ends the old visit when entering the selector. Controller dispose ends it.
Logout has automatic as well as explicit callers: every logout invalidates old
tokens and hides per-order content but retains a content-free terminal marker
until a fresh explicit login or accepted selection starts a visit. No direct
logout call may be mistaken for proof that the user resolved uncertain work.
Automatic verification, offline admission, reconnect, refresh,
filtering and pagination do NOT reset it. Explicit leave destroys the volatile
guard but is never described as resolution, rollback or permission to repeat.
Do not reset in blank, held, ready, verifyStored, offline, reconnect or
retryVerification. Those include ordinary automatic renewal paths.

Protection scope is a fixed tuple of API realm, principal user/organization,
selected location, dataset incarnation, authorization epoch, policy revision,
normalized capability set and session binding ID. Never include bearer tokens.
Normal ticket generation/tab-attempt, verifiedAt and offlineUntil renewal do not
change protection identity; existing fresh kernel checks still authorize every
action independently. Scope equality is not authorization.

Before publishing a newly ready source, compare its independently verified scope
with retained protection. If protected entries exist and semantic scope changes,
replace their presentation with a sticky content-free **transition-only deny**.
Discard old per-order IDs from the owner after this constant-size deny is set.
Do not call the runtime's auth `held`, lock the kernel, suppress sync, or restrict
otherwise authorized reads/create forms. Late settlements and switching back
cannot clear the deny. No prior-owner IDs or messages appear in a new workspace.

With no retained entries, the owner may adopt the new scope. Old attempt tokens
remain invalid after explicit leave/dispose, including a same-scope new visit.

## Admission, outcomes and memory

The host is the sole transition admission owner; UI disabled state is presentation,
not the security or duplicate-exclusion mechanism. Admit synchronously before the
first await. An opaque attempt token identifies exactly one current entry/visit.
Settlements can finish only that entry once; unknown/malformed/rejected result
uses the existing closed safe feedback decoder and remains blocked.

- Pending, UNKNOWN and committed/view-unavailable retain protection.
- Only committed/view-updated removes its own entry. No automatic action follows.
- Same-order duplicates never invoke the repository. Other orders remain
  independent below the bound and absent a scope-change transition deny.
- Maximum **50** protected entries per visit, aligned with the existing 50-row
  repository page as a conservative UI policy, not measured capacity. At 50,
  refuse new admissions before repository invocation; never evict/TTL-clear an
  unknown entry. A positive updated completion can free its own slot.
- Saturation feedback: “No se pueden iniciar más acciones: hay cambios pendientes de
  confirmar en esta vista. No repitas las acciones anteriores.”
- Scope-change feedback: “Se conservó una protección por un cambio sin confirmar.
  Las acciones de órdenes están bloqueadas en esta visita; no repitas ese cambio.”

Nonready blank/held/verifying snapshots expose no per-order protection identifiers
even while the internal owner retains them. Only a freshly ready matching scope
may receive the immutable presentation; a mismatch receives the generic deny.
Do not add arbitrary exception text, raw input or authority objects to snapshots.
Publish detached readonly maps with frozen nested state copies; the Map itself
is not deeply immutable and never controls admission. Keep all original journal/delivery/event bytes
and transaction semantics. No kernel, schema, grant, route or backend budget change.

## Acceptance

1. Current-source RED demonstrates actual automatic verification/remount loses
   pending/unknown/unavailable transition protection; no mocked throwing refresh.
2. Pure owner tests: synchronous duplicates, independent orders, exact token once,
   late token after leave, generation-only renewal, each semantic scope field,
   sticky deny after switching back, 50 admissions/51st refused, positive updated
   releases exactly one slot, paging cannot evict unknown and no auto replay.
3. Controller tests use real repositories/kernel fixtures: pending settlement
   across verification, UNKNOWN and positive commit before read-unavailable,
   changed owner/capability/dataset, no stale publication, unchanged journal.
4. Actual PWA tests exercise real reconnect unmount/remount with native commit
   observations and immutable journal identity checks. Successful online sync may
   legitimately change delivery/events/cache. Inspect screenshots, keyboard, axe,
   safe copy and no raw canary. Retain all PR73/74 cases and reconnect fences.
   A native-completion barrier precedes the kernel posttransaction fence: after
   reconnect its late rejection is UNKNOWN even when the test observed commit.
   The controller barrier after repository fulfillment instead proves known commit.
   Real capability edits invalidate the bearer; their browser proof is held/locked
   and no old content, NOT a fabricated same-session ready scope switch. Semantic
   ready mismatch is separately proven by pure/controller verified-context fixtures.
   The late-callback browser smoke observes native callback delivery and one frame;
   it cannot distinguish old UNKNOWN from new UNKNOWN or prove full settlement.
   Controller tests explicitly await the original promise for token-isolation proof.
5. Explicit logout/reload remains a documented negative guarantee boundary;
   durable journal retention is not claimed to preserve volatile UI admission.

## Boundaries and review

Core host/controller owns this state; M0 remains inert, with no plugin access to
tickets, IndexedDB, commands or new capabilities. External connectors unchanged.
Capture forms remain mounted-only pending a separately reviewed scoped draft and
intent lifetime. No ownership measurement replay (40927223929 spent), Pages
redeploy, credentials, resources, production activation or formal approving review.
Preserve PR74 final evidence and its original local988/989 failure. Group its
receipt into this substantive slice rather than a separate receipt-only PR.

## Local implementation checkpoint

1,021 frontend core tests passed with zero skips, including16 pure owner and11
controller cases. Initial controller RED showed duplicate repository invocation
(2 instead of1) and absent reconnect protection; UI ownership test also failed
before its correction. Source-only lint, normal/offline and explicit browser
types and repository contract passed. The initial all-lint pass summary was wrong:
the preserved test-lint exit1 and PR75 CI41005801485 identify an empty catch in the
new owner test. Two explicit frozen-assignment TypeError assertions replace that
catch without weakening admission assertions. Require all named exit receipts
present and zero before any combined pass statement; preserve the failed receipt. Five new actual PWA cases are authored and
discovered, not locally executed; all96 prior cases remain required. Local
Python3.12.14 lacks pytest and cannot qualify the Python3.13 baseline. Full hosted
source-bound validation and fresh postmerge proof remain mandatory.
