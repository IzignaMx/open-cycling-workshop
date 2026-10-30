# Transition visit protection implementation plan

> For agentic workers: REQUIRED SUB-SKILL `superpowers:executing-plans`.
> Implement only after independent final design review accepts this contract.

**Goal:** retain existing transition uncertainty protection across automatic
same-workspace verification without weakening authentication or implying reload recovery.

**Architecture:** one volatile host-runtime owner composes the existing transition
gate and safe feedback decoder. The controller is the sole admission boundary;
OrderList receives immutable presentation state rather than owning admission.
Repository/kernel execution and persistence remain unchanged.

**Tech stack:** existing React, TypeScript, Dexie and Playwright; no dependencies.

**Spec:** `docs/superpowers/specs/2026-10-30-transition-visit-protection-design.md`.

## Global constraints

- Baseline main ff890bca/tree f9ddd024; preserve PR74 evidence and local988/989 failure.
- Fifty protected transition entries maximum; never evict uncertainty to admit work.
- No new stores, grants, tickets, retry authority, raw error echo or automatic replay.
- Capture forms/drafts and full reload recovery remain explicitly outside this slice.
- Existing fixed CI budgets unchanged. Ownership40927223929 spent; Pages unchanged.

## Review focus

- Automatic logout is not explicit resolution or a fresh visit.
- Rebinding after changed epoch/capability must not expose old order identifiers.
- A late completion must not clear a later visit or sticky transition deny.
- Saturation must reject before repository execution without changing other features.
- UI must not reintroduce a second gate or read mutable refs during render.

## Task 1: pure bounded owner, RED then GREEN

Files:

- Create `apps/web/src/runtime/transition-protection.ts`.
- Extend `apps/web/src/features/orders/transition-feedback.ts` only with a copied
  snapshot/size accessor needed to compose its existing gate (no second gate logic).
- Create `apps/web/tests/runtime/transition-protection.test.mjs` and wire existing
  `tools/run-core-tests.mjs` / `tsconfig.runtime-test.json` inclusions.

Interfaces:

- `TransitionProtectionScope`: explicit fields from the design's semantic tuple;
  capabilities normalized as a sorted distinct string array, binding is noncredential.
- `TransitionProtectionSnapshot`: immutable copied per-order states and fixed
  notice (`null`, saturation or scope-change/closed notice), never scope/ticket/token.
- `TransitionProtection`: `startVisit(): void`, `endVisit(): void`,
  `observeScope(scope): void`, `begin(orderId): object | null`,
  `finish(orderId, token, feedback): boolean`, `getSnapshot(): TransitionProtectionSnapshot`.
- Existing `OrderTransitionGate` remains sole entry/token state machine; owner
  adds scope, visit lifetime, bounds and sticky deny. Tokens from an ended visit
  cannot match a new gate instance.

- [x] Test fresh owner is closed until startVisit plus observeScope; synchronous
      duplicate admission refused and independent orders admitted below50.
- [x] Test exactly50 retained entries,51st refused, UNKNOWN cannot free a slot,
      committed/updated frees exactlyone; repeated finish rejected.
- [x] Test each semantic scope field mismatch with entries converts to sticky
      content-free deny; returning to old scope does not clear; empty owner rebinds.
- [x] Test start/end visit invalidates all old tokens; generation/clock metadata
      are absent from semantic identity and cannot reset retained entries.
- [x] Observe expected RED, implement minimum owner, rerun GREEN. Mutation-test
      removed bounds, removed token/lifetime fence and mismatch auto-clear.

## Task 2: real controller lifecycle and single admission boundary

Files: `runtime/controller.ts`, `tests/runtime/controller.test.mjs`.

- [x] Write RED tests using real repository/kernel fixture for duplicate controller
      calls and retained protection across actual reconnect verification. Include
      pending completion, UNKNOWN and committed/view-unavailable separately.
- [x] Add snapshot field `transitionProtection` with safe empty/closed presentation.
      In `transition`, call owner.begin synchronously after current source admission,
      before repository await; a refused begin invokes no repository and resolves the
      existing conservative UNKNOWN result, without pretending rollback.
- [x] Settle owner exactly once from existing structured transition result and
      safe feedback. Publish only into a current ready matching scope. A stale source
      may record its original outcome internally, not publish into a replacement.
- [x] Observe freshly verified scope before ready publication. Never reset through
      blank/held/verification/reconnect/offline/retryVerification. Start fresh visit
      exactly once at controller construction (existing retained-session startup
      still requires all admission guards), at explicit login and accepted selection
      after existing membership guards;
      changeWorkshop/logout/dispose invalidate tokens. Automatic logout retains only
      terminal content-free state until explicit new admission.
- [x] Cover invalid selection does not reset; automatic logout does not grant a
      new visit; existing online/offline retained startup is usable after verified
      admission, but retry/start/reconnect after terminal logout cannot reopen it.
      Assert nonready snapshots contain no per-order protection IDs. Changed
      realm/principal/location/incarnation/epoch/policy/capability/
      binding hides identifiers and denies transitions only. Existing reads/create/
      sync fences and behavior remain unchanged. Assert exact journal/event bytes.
- [x] Run focused GREEN, then full retained frontend suite without timing changes.

## Task 3: stateless transition presentation and actual PWA proof

Files: `App.tsx`, `features/orders/OrderList.tsx`, new
`e2e/order-transition-lifecycle.spec.ts`, affected source-wiring tests.
Reuse the unchanged native fault probe through `e2e/helpers/order-transition-fault.ts`;
include both transition specs in existing `tsconfig.e2e-inventory.json` so CI
actually typechecks their imports rather than relying on discovery alone.

- [x] Pass the host snapshot to OrderList. Remove its admission gate, completion
      lifecycle ref and local transition-state owner; retain filter/history UI state.
      Render buttons disabled for retained entry or fixed global transition notice.
      onTransition still returns existing `OrderTransitionResult`; no UI retry.
- [ ] Actual PWA RED uses existing native completion observation and production
      reconnect path to prove verification unmount/remount, not a fake refresh throw.
- [ ] Verify pending and UNKNOWN block after same-scope reconnect, exact one
      mutation, stale completion after leave causes no new-owner feedback, semantic
      scope change exposes no old IDs. Include keyboard, axe and actual screenshots.
- [x] Retain PR73 four and PR74 six actual cases; adjust only ownership-specific
      test wiring where the intended new controller boundary replaces local ownership.
      Never remove assertions, weaken timeouts or turn UNKNOWN into rollback proof.

## Task 4: grouped documentation and exact-source qualification

Files: this plan/design, `MANUAL-ACTIONS-CHECKLIST.md`,
`docs/10-spec-development/execution-state.yaml`.

- [x] Record PR74 fresh postmerge receipt and new local evidence; preserve all
      historical failures and still-open capture/reload/physical/module gates.
- [ ] Normal/offline TypeScript, eslint/prettier, repository contract, full core,
      build and independent final product/security/browser fixture review.
- [ ] Publish reviewed exact tree only under applicable authority; stop any denied
      action without omission/bypass. Full hosted Python/PG restores/security/runtime/
      nativeARM/Caddy/browser/repeats required before normal expected-head merge.
- [ ] Fresh postmerge artifact/source qualification; no formal approving review.

## Current checkpoint

Local implementation and independent product/browser-source reviews completed.
Core1,021/1,021 zero skips, normal/offline/browser types, source-only lint and
repository contract passed. The initial test-lint pass summary was incorrect;
the preserved test-lint exit code is1 (empty catch). Five browser cases are authored/discovered only; no
actual-browser RED or GREEN is claimed locally. The initial controller six RED
cases and UI ownership RED are retained. Host qualification including all101
browser cases remains pending. Local source baseline has main's exact tree but a
preserved different commit identity; never call that local commit current main.

## First hosted lint failure and evidence correction

PR75 candidate54979197, CI41005801485, failed frontend lint on the empty catch in
`transition-protection.test.mjs`; direct browser execution was skipped. Replace
the catch with two independent TypeError assertions for the frozen assignments,
retaining the admission/snapshot assertions. No runtime behavior or lint rule changes.

Do not overwrite the failed local receipt or equate source-only lint with all lint.
Before reporting combined local validation, require every named exit receipt to
exist, parse as an integer and equal zero; include a negative check using the
original test-lint exit1. Fresh full root ESLint and core tests plus independent
exact-diff review are required before publishing a successor. Hosted/browser
qualification remains pending; no identical-head rerun is authorized.
