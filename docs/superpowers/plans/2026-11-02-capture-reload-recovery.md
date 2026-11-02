# Same-session capture reload recovery implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Source implementation and independent review have separate owners.

**Goal:** Restore acknowledged unsent customer/order inputs in the same verified session without resurrecting uncertain submissions.

**Architecture:** Add one shared checkpoint protocol with separate expiring content in authenticated IndexedDB v8. Reuse kernel transaction admission and PR79 volatile ownership; consume the current checkpoint before business dispatch. Expiry/logout remove private fields, not unresolved protection.

**Tech Stack:** Existing TypeScript/React/Dexie PWA, IndexedDB, pinned pnpm 11.17.0, Python 3.13 repository contracts; no new dependencies.

**Spec:** `../specs/2026-11-02-capture-reload-recovery-design.md`.

## Global constraints

- Approved policy: same verified session only, 24 hours (`86_400_000` ms), logout PII purge, expired cleanup on app open; no publication/merge permission.
- No automatic retry, financial replay, cross-login restoration, authorization weakening, journal rewrite, deployment or physical/destructive trial.
- No operation may dispatch before positively acknowledged shared PROTECTED state.
- Preserve PR79 newer-edit/masking/attempt rules and all existing strict browser privacy assertions.
- No claim of encrypted storage, guaranteed erasure, browser-closed cleanup or complete crash/power-loss/eviction recovery.
- Existing historical UNKNOWN, spent ownership experiment and Pages source remain unchanged.

## Review focus

- Copied admission/hint before a real save: shared state must reject stale sendable restoration even if a copied tab later obtains legitimate READY.
- Quota, completion uncertainty and failed cleanup: no inferred noncommit, no false saved/deleted claim, authentication logout still masks immediately.
- Expiry or clock rollback concurrent with save/settle: private fields disappear without rearming protected state or letting a delayed callback recreate them.
- Older bundle and migration boundaries: preserve v1–v7 data, close old connections and reject incompatible reopening without database clearing.
- Same-scope reverify versus new session: trusted in-memory receipts may settle only exact live attempts; new binding never inherits old fields or makes claims about old outcomes.

---

## Task 1 · Shared checkpoint protocol and admitted transactions

**Files:** create `apps/web/src/access-kernel/capture-checkpoint.ts`, `apps/web/src/access-kernel/capture-checkpoint-types.ts`, `apps/web/src/access-kernel/capture-checkpoint-store.ts`; modify `apps/web/src/access-kernel/database.ts`, `apps/web/src/access-kernel/kernel.ts`, `apps/web/src/access-kernel/types.ts`; create `apps/web/tests/access-kernel/capture-checkpoint-store.test.mjs` and `apps/web/tests/access-kernel/capture-checkpoint-authority.test.mjs`; extend `apps/web/tests/access-kernel/migration.test.mjs` and `apps/web/tests/branding/migration.test.mjs`; register focused tests in `apps/web/tools/run-core-tests.mjs`.

**Interfaces:** The design's `CaptureCheckpoint`, `CaptureDraftContent`, `CaptureCheckpointCommand` and `CaptureCheckpointResult` are the shared data contract. Expose only `checkpointCapture(ticket, command, current)` through the existing kernel; pure row reduction is not authority. Deletion-only maintenance accepts bounded checkpoint/generation locators and current time, returns no private fields and cannot authorize dispatch.

- [x] Independently close the design review, including exact unions, row bounds, enrollment and cleanup-hint failure rules, before source edits.
- [x] Add focused RED and regression coverage for state/CAS transitions; exact binding uniqueness; shared clone-before-send; missing/corrupt expected rows; bounded field/metadata validation; independent channels; first-write absolute TTL and rollback.
- [x] Add focused RED and regression coverage for current-owner takeover inside the transaction, failed/uncertain protect with zero subsequent create calls, stale writes/settlement after protection/purge, and preservation of immutable history.
- [x] Implement additive v8 stores and narrow typed admission path reusing current kernel checks; apply only the separately approved atomic writer metadata correction to existing command transactions.
- [x] Verify v7→v8 preservation, aborted/blocked upgrade and old-version reopening tests, retaining observed migration failures and corrected runs. Advance the existing hypothetical future-version fixture to v9 without dropping its assertions.
- [x] Run focused checkpoint/migration and retained kernel tests; inspect diff and independently review the shared boundary before integration claims.

## Task 2 · Runtime ownership, recovery and truthful UI

**Files:** modify `apps/web/src/runtime/capture-visit.ts`, `apps/web/src/runtime/controller.ts`, `apps/web/src/features/draft-state.ts` and capture form/App presentation only as needed; create a focused `apps/web/src/runtime/capture-recovery.ts` owner/adapter if needed to keep controller responsibilities bounded. Add `apps/web/tests/runtime/capture-reload-recovery.test.mjs` and focused adapter tests; retain existing runtime fixture/PR78/PR79 tests.

**Interfaces:** Use Task 1 typed checkpoint operations and existing sessionStorage for content-free expected/cleanup hints. CaptureVisit remains immediate volatile presentation. Recovery tracks exact edit, persistence generation, acknowledged CAS revision and attempt identity; restoring or publishing state is never an execution authority.

- [x] Preserve initial six behavior REDs and the independently reproduced clone counterexample under `artifacts/durable-capture/`; production unchanged at reproduction.
- [x] Promote those assertions into maintained tests against this exact checkout. Await acknowledged writes before claiming recoverable reload; preserve call-count versus persisted-duplicate distinction.
- [x] Add focused RED and regression coverage for legacy no-hint enrollment denial, hint-before-enroll interruption, new binding blank state, expired cleanup while held/locked, malformed timestamp rows, failed logout purge/discoverability and synchronous masking.
- [x] Implement source-bound hydration before enabling capture, per-channel serialized latest-write persistence and acknowledged status. A late load or external CAS conflict must not overwrite current edits.
- [x] Implement protect-after-own-write-drain, exact source recheck and unchanged create calls; UNKNOWN stays protected. Trusted outcome settlement may preserve newer edits only with exact generation/attempt/current authority.
- [x] Cover protected-interval edits, outcome/settlement failure copy, reverify, A→B→A, stale handlers, TTL/purge races and retained defaults. No blanket reset or automatic resend.
- [x] Run complete frontend core, normal/offline typechecks, production build, touched and clean-product lint/format; independently review runtime/UI behavior and recorded limitations.

## Task 3 · Native evidence, traceability and final package

**Files:** create `apps/web/e2e/capture-reload-recovery.spec.ts`; new scoped evidence record under `docs/10-spec-development/`; reconcile execution-state, checklist and existing traceability rows; extend repository documentation contracts. Explicitly annotate the future quote plan's unimplemented v8 reservation as superseded; do not implement quote storage. Update this plan/design with actual decisions and evidence.

**Interfaces:** Native cases observe real PWA/IndexedDB terminal events using existing authenticated fixtures. They consume actual stored format/row state from Task 1 and public UI from Task 2, never fabricate authority or transaction success.

- [x] Author actual online/offline reload, native cloned-storage, pre-dispatch and post-commit interruption, UNKNOWN, quota/write failure, logout/scope privacy and 24-hour cleanup journeys with immutable journal assertions.
- [ ] Test +24h cleanup while LOCKED/HELD: real session lease is 8h; never invent renewed READY authority. Await acknowledged persistence, not arbitrary delays.
- [ ] Retain strict original privacy/confirmation checks; add representative keyboard/axe evidence. Record authored/collected versus actually executed counts separately.
- [x] Reconcile prior PR79/80 source-bound receipts as historical acceptance, not new artifact validation. Keep OFF-007/UX recovery partial and physical gates open.
- [x] Add new repository contracts RED→GREEN for current evidence/policy pointers and truthful pending gates; run147 repository tests and the full local Python invocation (4954 pass/671 environment skips).
- [ ] Execute complete hosted Python qualification; local environment skips are not accepted as full coverage.
- [ ] Perform independent complete source/design/evidence review; fix scoped findings without weakening controls. Run final generated contracts, repository verifier, Ruff/format/mypy, ESLint/Prettier, builds and source hash checks.
- [ ] Freeze coherent DCO commits and a sanitized recoverable Space/Library artifact, recording exact base/candidate/tree and local evidence.
- [ ] Report concrete file scope and remaining native/hosted qualification; request separate publication/conditional integration authority through the coordinator. Do not publish or merge without it.

## Initial evidence and environment

Baseline `02ec2f059e610768cb58ce20812fed33999bfa7a`: 144 repository tests passed.
Six reload regressions intentionally fail; clone probe passes and demonstrates the
inadequacy of a tab-only fence. Independent reviewer reproduced both results.
Workspace-local frozen dependencies are available; initial default-home cache and
wrong default-pnpm/offline metadata attempts failed, then pinned pnpm11.17.0 and
workspace-cache uv sync succeeded. No lockfile or dependency change was made.
No native browser or new implementation pass is claimed at this planning stage.

### Tasks 1–2 implementation checkpoint — 2026-11-02 07:49 UTC

- Independent design acceptance recorded at 07:37; implementation remains under review,
  not completed qualification. Source decomposition separates types, row validation,
  transaction reducer/maintenance, admitted kernel entry and runtime recovery adapter.
- Fresh seam evidence: store feature RED then GREEN; expanded behavioral REDs include
  missing UNSENT payload, malformed state and orphan cleanup. Authority API RED then
  three actual kernel tests GREEN (scope/binding, owner fence, channel capability).
- `capture-reload-recovery.test.mjs` promotes the six original actual-controller
  behavioral cases with acknowledged autosave and actual repository-call barriers.
  Fresh six RED then six GREEN; original artifact-only RED remains unchanged.
- Retained PR78 29 and continuity 7 tests keep every behavioral assertion. Timing now
  awaits the actual repository invocation after durable protection, and the same-render
  duplicate case separately asserts synchronous disabled state. Fresh 36/36 GREEN.
- Review finding: cancellation notification exposed old capture before masking.
  Actual subscriber regression RED then GREEN after silent view/source/snapshot mask
  precedes recovery notifications (`cancel-mask-{red,green}.log`).
- Cleanup warning now has a content-free global snapshot/App presentation, independent
  of masked forms. The locked App regression injects actual bulk deletion failure;
  no successful-erasure claim is made. A first test draft accidentally patched single
  delete instead of bulkDelete; that draft failure is not cleanup-failure evidence.
- Adapter final-ack microtask can enqueue an edit after its flush loop exits. The
  deterministic regression failed (one save rather than two), then passed after a
  source/lifetime-fenced tail drain; protection drains restarted local saves too.
- Remaining design/source blockers: mixed-version old bundle execution and explicit
  same-workshop voluntary retirement must be resolved before acceptance. No schema
  VersionError protection or full browser/crash qualification is claimed.

### Reviewed corrections — 2026-11-02 07:53 UTC

- Same-workshop voluntary discard/reload initially restored the discarded private
  input (actual runtime RED). Exact-generation deletion-only retirement plus
  synchronous hint removal now passes the nine-case reload/cleanup/masking suite.
- First full-core run exposed retained branding migration expectations for native70;
  the v6 fixture now excludes all later stores and checks current native80, retaining
  every v6-row preservation assertion. Focused migration passes.
- A retained branding write barrier exposed an ordering regression: setting branding
  admission before the new recovery await could launch branding before ready publication.
  Admission now remains adjacent to ready publication after the recovery await, preserving
  the old synchronous boundary. The existing delayed branding/relogin test passes.
- First full core was interrupted after the blocked branding test; it is not a pass.
  Fresh second core, build and typecheck are underway. The independently reproduced
  mixed-v7 duplicate counterexample still blocks acceptance; production protocol redesign
  is paused pending explicit authority. No external publication or commit performed here.

### Authorized Task 1 correction: shared writer epoch/sequence

User approved 2026-11-02 07:54 UTC after independently reproduced mixed-v7 duplicate.
The formal design's approved mixed-writer section is the exact contract. Extend the
existing DeviceControl type, checkpoint types/validation/store and kernel NEW-command
append metadata only; no new tables, permission changes or journal rewrites.

- [x] Independent written acceptance of the protocol section before source edits (07:59 UTC).
- [x] TDD actual kernel guard: healthy/absent/malformed/mismatched writer, atomic new
      append, exact-ID no-op, grouped rollback, enrollment uniqueness and old epoch denial.
- [x] Independent actual mixed-v7 probe verifies refusal after old append and after
      subsequent new-runtime append (old epoch never silently adopted).
- [x] Re-run retained suites with PNG-specific branding digest instrumentation and
      bounded actual-state polling rather than assumptions about unrelated digest/tick count.
- [ ] Reconcile final source/native evidence before any readiness claim.

### Writer protocol implementation checkpoint — 2026-11-02 08:03 UTC

- Actual authority RED: fresh enrollment lacked a writer and grouped append lacked
  covered sequence. Store/authority then passed 33/33; store expansion separately
  reached 30/30. New append now updates epoch/coverage atomically; exact-ID no-op
  remains before metadata changes. Existing checkpoints never adopt rotated epochs.
- Retained controller suite was blocked by logo tests intercepting the first unrelated
  SHA-256 call. PNG-byte-specific interception preserves their original barriers and
  logo count/assertions. Fresh retained controller suite: 151/151 passed. The bounded
  automatic-revalidation test allows more event-loop progress without relaxing outcome.
- Prehydration logout review finding: a locked new controller had no cached head and
  silently left acknowledged payload. Actual RED showed one residual row; metadata-only
  locator resolution plus exact-generation purge now passes all 12 failure tests.
- Fresh full-core rerun underway. Independent actual old-v7 probe and final native/source
  review remain required; intermediate unit counts do not establish overall readiness.

### Final implementation verification checkpoint — 2026-11-02 08:05 UTC

Fresh `node apps/web/tools/run-core-tests.mjs`: **1214/1214 pass**, zero failures,
cancellations or skips (`core-third.log`). Both earlier interrupted/failing runs remain
retained. Normal web typecheck and PWA production build pass after the writer and
prehydration fixes (`typecheck-writer-final.log`, `build-writer-final.log`); existing
large-chunk warning remains. Scoped ESLint and Prettier pass, and `git diff --check`
is clean. Independent actual-v7 probe/owner race and final native/source review are
separate evidence, not inferred from these unit/integration results.

The broad matrix checkboxes distinguish focused RED from regression coverage: initial seams and
identified regressions have explicit retained RED/GREEN logs, while some later
adversarial cases were added as already-green regression coverage. Do not relabel
those later cases as individually observed pre-fix REDs.

### Exact-source completion — 2026-11-02 08:11 UTC

- `core-final.log` retained one failed legacy timing assertion (1213 pass/1 fail):
  preference-copy completion was still VERIFYING after two fixed event-loop drains.
  The maintained test now waits for actual READY publication with a bounded loop,
  advancing mocked timers by zero only. Every session/journal/network assertion remains.
  Five isolated repeats pass (`preference-copy-repeat-green.log`).
- Fresh final `node apps/web/tools/run-core-tests.mjs`: **1214/1214 pass**, zero skipped,
  cancelled or failed (`core-exact-final.log`), including all 1119 retained cases.
- Normal/offline TypeScript pass (`typecheck-exact-final.log`,
  `offline-typecheck-exact-final.log`); additive offline Dexie shim signatures match
  the real `above`/`toCollection` APIs. The kernel table annotation is type-only.
- Production PWA build passes (`build-exact-final.log`), with the retained large-chunk
  warning. `eslint . --ignore-pattern 'artifacts/**'` passes (`eslint-exact-final.log`):
  this excludes only ignored generated evidence/mutation outputs, not product source;
  the earlier plain-dot scan's artifact-only errors remain in its log. No lint config
  weakening. Scoped formatting and `git diff --check` pass.
- Independent bounded source review accepted with seven actual runtime probes,
  49 store/authority/migration cases and two killed writer-guard mutants; native browser
  execution remains separately pending. Final package/document reconciliation belongs
  to the coordinator. No commit or external write performed by this implementation agent.

### Coordinator local checkpoint — 08:12 UTC

Final source review and local evidence are reconciled in the scoped evidence record.
Ten native journeys are authored/collected and statically reviewed, including keyboard
submission and axe assertions, but native execution remains zero. The unchecked
native/hosted gates above are intentional. Source scope34files; no publication authority.
