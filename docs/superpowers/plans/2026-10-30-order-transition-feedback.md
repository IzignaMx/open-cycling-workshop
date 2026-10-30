# Order transition feedback implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve known committed order changes, suppress raw errors and exclude repeated uncertain actions in the mounted board.

**Architecture:** Existing repository/kernel writes remain unchanged. The runtime returns a closed result with positive follow-up availability; one list-owned synchronous per-order gate controls presentation and excludes repeated calls.

**Tech Stack:** Existing React/TypeScript/Dexie, Node tests and Playwright/axe; no dependencies.

**Spec:** `docs/superpowers/specs/2026-10-30-order-transition-feedback-design.md`

## Global constraints

- No rollback inference, capture-only mapper reuse, automatic retries or raw error rendering.
- No new stores, kernel/state-machine changes, grants, module/runtime activation or deployments.
- Guard lifetime is the mounted list only, not reconnect/reload/other tabs; losing it does not prove noncommit.
- Preserve all fixed CI resource limits and permanently spent ownership run40927223929.
- Physical R01-T035 and other acceptance gates remain separate and open.

## Review focus

- Native commit followed by rejection remains unknown, never safe to retry.
- Refresh can resolve after internally holding the session; require positive availability.
- Source replacement during any await cannot access or publish replacement-owner history.
- Filtering, pagination and callback/row changes cannot reset a still-mounted order guard.
- Unmounted-list completion cannot mutate a replacement list or imply the old write was absent.

## Task 1: Closed transition result and positive read availability

**Files:** `apps/web/src/runtime/order-transition-outcome.ts` (new),
`apps/web/src/runtime/controller.ts`, `apps/web/tests/runtime/controller.test.mjs`.

**Interfaces:** `OrderTransitionResult = {status:'committed'; view:'updated'|'unavailable'} | {status:'unknown'}`.
`WorkshopController.transition(orderId, action): Promise<OrderTransitionResult>`;
`refresh(...): Promise<boolean>`; retain public `timeline(orderId): Promise<void>`
through a captured-source internal helper returning positive availability.

- [ ] Add actual repository/controller tests: normal offline result and mutation/event/projection;
      rejected preparation and native committed-then-rejected result; refresh-held;
      local timeline failure; source replacement during each await. Assert exact
      records, no replacement-source timeline and no stale sync wake.
- [ ] Run affected runtime tests and preserve expected RED assertions.
- [ ] Implement minimal result boundary and positive read returns, preserving
      hold/fence behavior. No changes to repository writes or public timeline API.
- [ ] Run runtime tests GREEN and normal/offline TypeScript checks.

## Task 2: List-owned safe feedback and synchronous exclusion

**Files:** `apps/web/src/features/orders/transition-feedback.ts` (new),
`apps/web/src/features/orders/OrderList.tsx`,
`apps/web/tests/runtime/order-transition-feedback.test.mjs` (new),
`apps/web/tools/run-core-tests.mjs`, `apps/web/tsconfig.runtime-test.json`.

**Interfaces:** pure `orderTransitionFeedback(resolved-or-rejected unknown)`
returns fixed message plus blocking state; `OrderTransitionGate` acquires per-order
tokens synchronously, preserves pending/blocked entries and finishes only its
own token. Gate is owned by OrderList, not filtered rows; its snapshot drives
button disabled/feedback rendering. Successful updated entries may be removed.

- [ ] Write RED tests for malformed/getter/raw-message canaries; one same-tick
      admission; independent orders; unknown/unavailable persistent across row and
      callback changes; old token cannot settle another entry; explicit next action
      only after committed/updated. Verify UI source wiring uses the tested gate.
- [ ] Implement safe fixed messages and list-level gate. Do not clear on finally,
      search/page/version/action changes or history reads. Keep late completion in
      the original gate; protect replacement/unmounted presentation.
- [ ] Run focused tests GREEN; rerun all core tests, format/lint/normal+offline
      types and production build. Preserve any first failure and cause.

## Task 3: Actual browser proof, receipts and qualification

**Files:** `apps/web/e2e/order-transition-feedback.spec.ts` (new),
`docs/10-spec-development/execution-state.yaml`, `MANUAL-ACTIONS-CHECKLIST.md`,
this plan and its design; existing quota plan for grouped final receipt if useful.

- [ ] Add actual-PWA synthetic cases using existing fixture/IDB observation,
      no production hooks: prewrite unknown, native write failure/unknown,
      postcommit follow-up failure and successful explicit subsequent action.
      Assert journal/event/projection identity and counts, no raw canary, synchronous
      duplicate exclusion, filter/page guard retention, keyboard and axe.
- [ ] Independently review final exact patch and browser instrumentation; static
      discovery/type checks do not count as actual browser qualification.
- [ ] Group PR73 final receipt with this meaningful slice: main b393c58,
      CI40977757107, Python5499/58, core959, aggregate27/27, browser90+90 retry0,
      retained repeats/kernel. Preserve all three historical failed source runs and
      their bounded corrections; do not retry blocked PR73 body mutation.
- [ ] Commit with DCO after final local checks; publish ordinary draft PR and
      qualify exact-source hosted full/actual-browser checks under existing budgets.
      No formal approving review. Normal merge only after independent acceptance;
      fresh postmerge proof before implemented-scope verification.

## Baseline and disposition

- Clean isolated branch `fix/order-transition-feedback-local` from actual main
  b393c58; original quota branch/commits preserved.
- Baseline local frontend: 959 passed, zero skipped, exit0 (2026-10-30).
- Design decisions are assistant-selected within delegated scope; independent
  review precedes implementation. No completed behavior is claimed by this plan.

## Local implementation checkpoint · 2026-10-30

The written design and current product patch were independently reviewed.
Runtime/source tests: 15 passed; feedback/gate tests: 20 passed. Baseline replay
observed eight expected transition failures while retaining two capture successes;
the first five tests were observed failing before implementation. Fixture-only
wrong-store and replacement-login-online setup mistakes were corrected and their
failed logs retained, not counted as behavioral RED.

First full frontend run: 988 passed/1 failed, the retained probe-backoff test
(`duplicate offline notifications preserve the probe backoff and original admission`)
observed 0 calls instead of 1. It passed focused without modifications. A later
full run after the React ref-render lint correction and five added availability
regressions reported 994/994, zero skips. Historical timing cause is unproved;
no timeouts, assertions or controls were weakened. Local Node is24.22.1 within
the supported range; exact hosted Node22 qualification remains required.

The initial UI ref read during render was rejected by ESLint. Rendering now uses
an immutable presentation snapshot derived from the synchronous list-owned gate;
there is no second admission policy. Production/kernel writes are unchanged.

Six actual-PWA tests are authored and independently source-reviewed: four outcome
cases plus pending filtered-card and actual workspace-unmount cases. The latter
reuse the existing genuine postcommit notification barrier with a narrow exact
transition matcher; they do not fabricate native commit or qualify timing. No
actual local browser pass is claimed. Local Python is3.12 without pytest or
SQLAlchemy, below the project Python3.13 floor, so full Python requires hosted
qualification; no dependency installation or substitute Python result is claimed.

PR73's final grouped receipt is in execution-state/checklist: fresh mainb393c58,
CI40977757107, Python5499/58, core959, aggregate27/27, direct90+aggregate90 and
retained repeats/kernel allretry0. All first failed heads remain historical evidence.
