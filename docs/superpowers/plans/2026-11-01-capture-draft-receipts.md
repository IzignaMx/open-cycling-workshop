# Mounted Capture Draft Receipts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent late successful capture receipts erasing newer mounted-form edits.
**Architecture:** Keep the existing capture outcome and submission gate. Fence only
successful resets with an opaque local edit revision; no storage or runtime change.
**Tech Stack:** React 19, TypeScript, existing Node test runner.
**Spec:** `docs/superpowers/specs/2026-11-01-capture-draft-receipts-design.md`

## Global Constraints

No new dependency, schema/storage, runtime/controller/auth or production debug API.
No durable cross-navigation guarantee, automatic retry or weakened unknown latch.
Retain unchanged-draft success behavior and existing accessibility semantics.

## Review Focus

- Same-value and ABA interactions must not be acknowledged by earlier receipts.
- Selection-only edits must not promote older customer/priority to clean defaults.
- Hidden bicycle field state must survive an intervening checkbox edit.
- Unknown remains blocked even after clearing every field.
- The next explicit submission sends current values and may reset only its own draft.

## Task 1: Fence actual mounted form handlers

**Files:** modify `apps/web/src/features/customers/CustomerQuickCreate.tsx`,
`apps/web/src/features/orders/OrderQuickIntake.tsx`; create
`apps/web/tests/runtime/capture-draft-receipts.test.mjs`; register in
`apps/web/tools/run-core-tests.mjs`.

**Interfaces:** existing props and `CaptureSubmissionResult` unchanged. Internal
`markEdited(): void` replaces `draftRevision.current` with a fresh object.

- [x] Write actual-component callback tests for all 11 controls and ABA/same-value;
      retain reset, not_saved and unknown assertions.
- [x] Run `node --test apps/web/tests/runtime/capture-draft-receipts.test.mjs`.
      Fresh behavioral RED on unmodified baseline: 20 failed / 9 passed.
- [x] Original independent design/plan review accepted before original implementation;
      second replacement uses the same bounded approach, with fresh review required.
- [x] Add focused retained-baseline, second-submit, hidden bicycle, same-render busy,
      empty-unknown and empty-clean-draft cases.
- [x] Capture revision after gate.begin; on saved compare identity before resetting
      fields/retainedSelection. On mismatch preserve them and set exact copy from spec.
- [x] Run focused tests, then `pnpm --filter @ocwp/web test`, typecheck/build,
      touched ESLint/Prettier and `git diff --check`; preserve logs and report failures.
- [x] Add four actual PWA delayed-save cases; fresh static checks and collection
      pass. Fresh independent component/browser source review accepted.
- [ ] Qualify exact published candidate and fresh main with all hosted gates.

## Execution ledger

Baseline `cdb44aa`; one task, no shared implementation interfaces. After the second
workspace snapshot loss on 2026-11-02 the intended six-file scope is reconstructed
again from retained transcript, without lost candidate byte or commit identity
claims. No previous verification is inherited. No production API, dependency,
storage, auth or controller changes. No commits or remote writes by this implementer.

Fresh second-replacement focused GREEN: 29/29. Fresh touched ESLint/Prettier,
web typecheck and production PWA build pass; unchanged bundle-size warning.
Fresh full frontend core passes 1,050/1,050 without skips; no earlier result
substitutes for it. Fresh diff whitespace check passes. Browser and independent
whole-package review remain parent-coordinated gates.

Integration review: fresh independent source review accepted the components,
29-case harness and four PWA cases; copied-harness mutations failed 20/20/14
cases as expected. Native cases collected, not run locally. Publication before
CI is expressly authorized; only merge is conditioned on complete validation.
No deployment, physical or destructive testing is included.
