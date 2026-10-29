# Quota-safe Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give existing customer/order capture truthful storage-failure feedback
and safe explicit retry only after proven noncommit.

**Architecture:** Add an opt-in capture transaction outcome around the existing
Dexie transaction with positive native abort evidence, leaving noncapture APIs and fences unchanged. Carry a bounded
source-owned result through existing repositories/controller to shared form
presentation. Unknown outcomes block repeat submission without erasing drafts.

**Tech Stack:** Existing TypeScript, React, Dexie 4.4.4, fake-indexeddb 6.2.5,
Node core tests and Playwright 1.62.0 production-PWA fixtures; no new dependency.

**Spec:** `docs/superpowers/specs/2026-10-29-quota-safe-capture-design.md`

## Checklist provenance

The task checkboxes below preserve the pre-implementation plan, not the current
completion ledger. The dated disposition at the end records actual qualification;
unchecked combined browser/CI steps remain incomplete.

## Global Constraints

- Baseline main6106028/treee6bc0218; preserve frozen prior worktrees and artifacts.
- Only customer/order capture opts in. Noncapture throws/returns and all security
  fences remain unchanged; no duplicate atomic store/transaction implementation.
- Only a native abort observed for the exact top-level transaction before the
  rejected-await catch establishes noncommit. Rejection alone, even quota-named,
  does not. Pending/complete/conflicting evidence stays unknown. No extra wait,
  timer, grace window, private Dexie API or synthetic event-order manipulation.
- No global reused-error rollback brand, raw exception text or automatic retry.
- Refuse capture nested in another Dexie transaction before writes; noncapture
  topology and behavior remain unchanged.
- No storage deletion/eviction/persist prompt/new store, route/grant/module changes,
  real capacity experiment, consumed measurement retry or workflow identity reset.
- Existing resource limits and complete exact-source qualification stay unchanged.
- Design is assistant-selected; implementation waits for independent review.

## Review Focus

- Quota-looking errors thrown after transaction completion must remain unknown.
- The same error object reused in a new operation must not carry old provenance.
- A bicycle-plus-order late write abort must preserve all prior unrelated work.
- A session replacement/refresh hold must not surface another user's data or
  relabel committed work as not_saved.
- Unknown submission followed by edits/Enter must not invoke capture again.

---

### Task 1: Capture-only transaction outcome and provenance regressions

**Files:**

- Modify: `apps/web/src/access-kernel/kernel.ts`
- Test: `apps/web/tests/access-kernel/kernel.test.mjs`

**Interfaces:**

- Preserve `commitLocalCommands(ticket, supplied, current): Promise<string[]>`.
- Add `commitLocalCommandsOutcome(ticket, supplied, current)` with the exact
  committed/not_committed union in the design.
- Share cloning/validation and atomic batch execution through private helpers.
  Capture-only native abort/complete listeners observe the exact top-level
  transaction before authorization/action, without replacing Dexie handlers; the
  rejected await maps only already-observed unambiguous abort. Remove listeners
  on settlement. Recheck database/parent identity inside the callback.

- [ ] Write failing tests with real kernel + fake IndexedDB for native/Dexie quota,
      generic late-write rejection, atomic bicycle/order batch rollback, unchanged
      journal/delivery/events/sequence, preserved prior work, and explicit retry once
      only for timely proven-abort cases.
- [ ] Write pre/postcommit fence and reused-error tests: only actual transaction
      rejection WITH timely native abort returns not_committed; noncapture calls
      retain original errors.
- [ ] Retain independent reviewer reproductions: scope resolves/throws generic/
      throws quota after native commit, leaving persisted rows; all must stay
      unknown. Add abort-after-catch, absent/conflicting evidence and nested-call
      refusal tests without writes. No name blacklist or ordering fabrication.
- [ ] Test defensive quota unwrap cycles/throwing getters only after abort proof.
- [ ] Compile kernel tests and run focused cases; record expected RED.
- [ ] Implement the minimal opt-in method/private helpers; do not alter authority,
      table set, sequence rules, transaction topology or timing.
- [ ] Run focused and complete existing kernel tests; record GREEN and diff review.
- [ ] Commit this verified source/test unit with DCO after independent review.

### Task 2: Trusted capture result and truthful form presentation

**Files:**

- Create: `apps/web/src/runtime/capture-outcome.ts`
- Create: `apps/web/src/features/capture-feedback.ts`
- Modify: `apps/web/src/runtime/repositories.ts`
- Modify: `apps/web/src/runtime/controller.ts`
- Modify: `apps/web/src/features/customers/CustomerQuickCreate.tsx`
- Modify: `apps/web/src/features/orders/OrderQuickIntake.tsx`
- Test: `apps/web/tests/runtime/controller.test.mjs`
- Create: `apps/web/tests/runtime/capture-feedback.test.mjs`
- Modify if required for normal test discovery: `apps/web/tools/run-core-tests.mjs`
  and existing runtime test tsconfig include (no isolated hidden test runner).

**Interfaces:**

- `CaptureSubmissionResult` is the saved/not_saved union in the design, fixed
  safe messages only. Existing controller createCustomer/createOrder produce it;
  only these capture repository paths use the new kernel outcome method.
- `captureFeedback(input: { kind: 'resolved'; value: unknown } |
{ kind: 'rejected'; error: unknown }): CaptureFeedback` returns the exact
  status/message/blockSubmission shape in the spec. Resolved inputs must have
  exact closed shapes/codes; thrown quota-looking errors remain unknown.
- The two forms retain their existing input props and successful field behavior,
  with their callback return type narrowed to CaptureSubmissionResult.

- [ ] Write RED tests for actual native/Dexie transaction outcomes through runtime,
      safe known validation, raw-message canaries, unrecognized thrown/result
      values, pre/postcommit session changes and unchanged refresh hold/wake.
- [ ] Write RED helper/state tests for draft retention, existing successful clear
      defaults, repeated unknown submit blocked even after edit, and explicit
      retry only after not_saved. Unknown itself remains dirty after all fields
      clear; synchronous busy/latched reentry is blocked. Use the same source
      helper imported by forms.
- [ ] Implement repository/controller result propagation and minimal shared
      presentation using fixed Spanish copy from the design. Keep dynamic
      priority values out of messages; preserve fixed useful validation guidance.
- [ ] Integrate both forms: no raw Error.message; unknown latch prevents callback
      invocation, retains dirty state, and adds no reset/autoretry action.
- [ ] Run focused runtime/form tests and all core tests; record GREEN; independently
      review the actual transaction-to-form wiring, not merely mocked callbacks.
- [ ] Commit this verified source/test unit with DCO.

### Task 3: Actual production-PWA journey and coherent status documentation

**Files:**

- Create: `apps/web/e2e/quota-safe-capture.spec.ts`
- Reuse without new production hooks: `apps/web/e2e/helpers/authenticated-workshop.ts`
  and `apps/web/e2e/helpers/visual-fixture.ts`
- Modify: this plan/design only to record evidence and settled interfaces.
- Later, coordinated with owner: `docs/10-spec-development/execution-state.yaml`
  and `MANUAL-ACTIONS-CHECKLIST.md` for PR72 receipt plus this scoped status.

- [ ] Add production-PWA tests for both forms with test-context-only IDB write
      failure at the journal/event stage, including multi-command order intake;
      use fresh existing scoped synthetic fixtures and existing budgets.
- [ ] Verify expected RED against unchanged UI (raw text/no bounded feedback), then
      GREEN against reviewed source. Snapshot operational tables before/after
      failure and record real native abort/complete ordering. Only timely-proven
      abort permits removing fault and explicitly resubmitting once with exact
      counts. Otherwise assert unknown/no-repeat and disclose that practical
      limit; do not force event ordering or claim universal quota retry.
- [ ] Verify keyboard/status/axe, retained input/dirty navigation warning, theme
      structures, no raw exception canary, and unknown no-repeat behavior using
      test-context crypto.getRandomValues failure after ready/offline to drive
      unknown preparation rejection; restore it, edit and press Enter, then prove
      callback is not retried and operational data unchanged. Do not call this
      browser scenario postcommit uncertainty; test that separately at kernel.
- [ ] Run `pnpm --filter @ocwp/web test:core`, frontend lint/typecheck/build, focused
      Playwright with retries0 and existing full qualification workflow. Do not
      raise budgets or hide failures/skips; preserve exact-source artifacts.
- [ ] Update coordinated docs with observed evidence only. Distinguish synthetic
      quota rollback/UX from physical eviction/capacity acceptance. Preserve
      measurement40927223929 as spent with admission/cause unknown.
- [ ] Independent exact-patch review; DCO commit and normal reviewed PR workflow
      under the coordinator's authority. No formal approving review by automation.

## Self-review / current disposition (2026-10-29)

The initial await-rejection-equals-rollback proposal was rejected by independent
review before implementation. The native-abort-only amendment and plan were
independently accepted before implementation. Local frontend core is 959/959
with 25 added tests and no skips; the design's local checkpoint records the initial
failure, correction and remaining limits. Four actual-PWA tests are authored and
statically checked but unexecuted locally. Independent final patch review accepted draft-CI qualification with a fresh
181/181 kernel, feedback and controller test run, zero skips. Hosted qualification
remains open. No dependency installation, actual browser
fault, ownership experiment or remote publication was performed by this task.
All tests use existing discovery; original resource ceilings and noncapture
security/error semantics remain enforced.
