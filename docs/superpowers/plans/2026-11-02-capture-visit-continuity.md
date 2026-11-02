# Volatile capture continuity implementation plan

Goal: preserve existing capture drafts and uncertainty through automatic same-scope
verification within one controller-owned visit. Base `b88c4eee`; existing release
remains partial. Spec: `../specs/2026-11-02-capture-visit-continuity-design.md`.

## Constraints and reviewed decisions

No persistence, schema, kernel/repository transaction, auth-admission, financial
replay, dependencies, workflow, Pages, deployment or physical/capacity experiments.
No publication/merge authority for this new package is inherited from PR78.
Do not keep private DOM mounted during verification; preserve masks and explicit
negative guarantees. Treat model/view/attempt identity as separate lifetimes.

Pre-flight: model → controller → controlled form/App are dependent interfaces;
model contains no authority, controller binds actual current source, App binds an
opaque view token. Browser fixtures depend on unchanged labels/real runtime flow,
not production debug interfaces. Existing create methods remain the repository
boundary and keep their source fences; no duplicate auto-dispatch path is added.

Ruling: semantic mismatch purges private values; unsent-only state permits a fresh
empty form with fixed notice, whereas pending/unknown retains capture-only deny.
Reason: avoid unnecessary global denial while preserving uncertain-write safety.
Cost if wrong: duplicate uncertain dispatch or privacy loss; explicit tests gate it.
Ruling: only actual logout/changeWorkshop/dispose closes a visit; generic held,
blank and intermediate authority rebind mask it until independent scope comparison.
Reason: those existing paths include transient verification. Cost if wrong: silent
loss or stale-owner exposure; lifecycle matrix tests and snapshot masking gate it.

## Task 1 · Maintainable behavior-first tests and pure owner

Files: new `apps/web/src/runtime/capture-visit.ts`, focused runtime test(s), bounded
shared test helper(s) if required; update existing capture/controller test imports
only as needed to avoid copying large fixtures. Register tests in the core runner.

Interface: one pure owner, two current draft records, defaults/revisions, separate
view and attempt tokens, fixed outcomes. No callback dispatch, storage or network
inside the owner. Scope observation, view suspension, explicit start/end, typed
single-field edits, synchronous attempt admission and token-bound settlement.
Snapshots detached/frozen; dirty/protected signal contains no private content.

- [x] Exploratory actual-controller/App/component RED: seven expected failures;
      independent replay retained in `artifacts/capture-visit/`.
- [x] Promote reusable fixture/hook plumbing; rerun retained tests unchanged to
      ensure refactoring is not a behavior change. Retain the seven assertions.
- [x] Add pure owner tests before implementation: scope fields/normalization,
      A→B→A, closed/new visit, hidden inputs/defaults, both forms, same-value/ABA,
      all outcome kinds, stale views/attempts, once-only settlement and freezing.
- [x] Implement the smallest pure owner; prove GREEN. No source/controller scope
      adoption from an unverified snapshot and no automatic repository invocation.

## Task 2 · Runtime lifetime and source-bound admission

Files: `apps/web/src/runtime/controller.ts` and focused controller tests.
Interface: nullable masked capture presentation in runtime snapshots, content-free
`hasUnsentCaptures()` signal, and capture edit/submit methods taking the current
opaque view token. Controller owns the model privately; model API naming may be
settled locally without changing the reviewed invariants.

- [x] Add RED tests for real reconnect/held/retry, scope mismatch, new visit,
      old callbacks, transient versus terminal lifecycle and synchronous subscriber
      reentrancy. Assert actual repository-call counts and unchanged journal bytes.
- [x] Bind owner at existing constructor/login/accepted selection/leave/dispose
      boundaries; invalidate view but preserve attempts during transient masking.
- [x] Centralize presentation masking for every publish and blank path.
- [x] Recheck exact source/view after notification before dispatch; use unchanged
      low-level create methods and existing outcome classification/normalization.
- [x] Late callbacks settle only current attempt/visit; never expose private values
      while nonready or mutate a replacement visit. Run focused/retained GREEN.

## Task 3 · Controlled capture UI and voluntary leave

Files: `App.tsx`, both capture forms, relevant draft-state/helper/test files.
Interface: forms receive current owner presentation and typed edit/submit callbacks;
App captures view identity, retains real nonready unmount and combines DOM dirty
state with owner protection for voluntary logout/workshop change/login replacement.

- [x] Write RED coverage for both leave guards and explicit login during nonready:
      dismiss means no controller mutation; accept means existing departure once.
      Automatic revocation/disposal never asks or waits for confirmation.
- [x] Move existing draft/receipt logic to the owner; keep labels, accessibility,
      values, defaults and truthful PR78 feedback. No stale full-draft replacement.
- [x] Make all seven original functional regressions GREEN, preserve all 29 PR78
      scenarios, and verify no private input in nonready App branches.
- [x] Run complete frontend core, normal/offline typecheck, build and static checks.

## Task 4 · Native regression coverage, documentation and review

Files: new actual-PWA continuity spec, this plan/design, scoped evidence record,
execution-state/checklist/traceability updates. No unrelated documentation sweep.

- [x] Add bounded native cases using existing helpers: draft/default restoration;
      customer/order pending→UNKNOWN across actual verification; voluntary leave
      while absent; explicit new visit/late callback; real revocation privacy.
      Preserve trusted native completion and immutable journal inspection.
- [x] Strict browser typecheck/collection/lint; distinguish authored from executed.
- [x] Full local Python/frontend/static/build verification and independent complete
      source/design review. Record initial failures and exact unavailable paths.
- [ ] Freeze coherent DCO commits and a sanitized recoverable artifact; ask parent
      for new package publication/conditional merge authorization with exact scope.
- [ ] Only after authorization, exact-source hosted acceptance and fresh-main review.

## Initial ledger (historical design-stage snapshot)

Production unchanged at design stage. RED-only exploration has seven expected
failures, not browser or persisted-duplicate evidence. Local native services are
unavailable; no browser pass is claimed. Historical physical/UNKNOWN/SPENT gates
remain separate. All implementation and verification steps above are still pending.

## Tasks 1–3 implementation ledger

- Ruling: use `CaptureVisit` with `observeScope`, `activateView`, `suspendView`,
  `startVisit`, `endVisit`, `editCustomer`/`editOrder`, `begin`/`finish` and
  `getSnapshot`/`hasUnsent`/`isCurrentView`. One frozen view token is issued per
  freshly READY source; separate frozen attempt tokens survive masked verification.
  Runtime methods are `editCaptureCustomer`, `editCaptureOrder`,
  `submitCaptureCustomer`, `submitCaptureOrder`, `hasUnsentCaptures`; low-level
  `createCustomer`/`createOrder` bodies retain their previous semantics.
- Ruling: a closed empty visit is disabled but not dirty; only actual unsent values,
  pending/unknown or sticky mismatch denial mark dirty. Avoid spurious departure
  confirmations after deliberate closure without allowing automatic reopening.
  Cost if wrong: unclear admission/leave state; pure RED (true versus false), then
  GREEN proves closed blocked, stale tokens refused, unsent false and dirty false.
- Shared test-only `runtime-fixture.mjs` and `capture-component-host.mjs` replace
  fixture copies. Before production changes, retained controller151 + PR7829 =
  180/180 passed after extraction. Promoted seven regressions still failed for the
  original lost-value/admission reasons. Actual App branching and component
  callbacks use simulated hooks/reconciliation, not native React/browser evidence.
- Pure owner: initial28 RED before source, expanded36 GREEN; closed-dirty refinement
  RED36pass/1fail then37/37 GREEN. Owner tests use a pure source loader and do not
  replace real controller/kernel evidence.
- App voluntary departure: six real handler assertions initially failed because
  masked drafts bypassed confirmation; both existing leave guards and LoginForm
  replacement now use the same fixed confirmation. All six pass. Existing DOM
  dirty logic remains; automatic runtime security/logout never asks confirmation.
- Integration: original7 + retainedPR7829 + leave6 =42/42 pass. Adversarial real
  controller matrix18/18 passes, including source reentrancy, late old commit,
  semantic mismatch, stale views, temporary security suspension, intermediate
  account authority rebind and automatic principal-change logout. Initial matrix
  fixture timing assumptions failed five cases; waiting for actual baseline READY
  corrected those assertions without altering production timing or limits.
- Normal and offline web typecheck, production PWA build and touched ESLint pass;
  existing >500kB bundle warning remains. Initial full frontend core passed1118/1118; after the closed-notice review fix, fresh final1119/1119 passes with no skips.
  Evidence logs are under `artifacts/capture-visit/`; no commit/publication by the
  implementer. Parent owns native tests, complete package review and final evidence.

### Independent review correction

The reviewer found closed empty state reused the sticky-denied pending/unknown
notice despite having no protected attempt. Accepted finding: a truthful closed
presentation must not invent a pending capture. Added an actual pure-owner
endVisit→observeScope→activateView test asserting blocked/content-free/clean and
no pending/confirming claim; observed RED37pass/1fail, then GREEN38/38.
Closed notice is now `Las capturas no están disponibles en esta visita. Inicia una
nueva sesión para continuar.` Sticky pending/unknown denial copy and all authority
behavior remain unchanged. Evidence: `closed-notice-red.log` and
`closed-notice-green.log`. Fresh final whole-core1119/1119 passes with no skips after this change. Normal/offline web typecheck and production PWA build pass on the corrected source; touched lint/format and diff whitespace checks pass. Existing >500kB bundle warning remains.

## Final local package checkpoint

Six authored native cases pass collection, strict TypeScript and static checks;
zero native-browser cases executed locally. Full Python: 4,946 passed, 671 skipped,
12 warnings; missing PostgreSQL/native services remain unverified. Final frontend
core: 1,119 passed, zero skips. Repository contracts: 139 passed. Whole-repository
Ruff/format, mypy, ESLint, generated OpenAPI/client and repository checks passed.
Independent source/design review accepted after 60 integration/retained and 38
owner passes, plus copied-loader mutation failures 12/18/4. Native/hosted proof,
new publication/integration authorization and fresh-main acceptance remain open.
