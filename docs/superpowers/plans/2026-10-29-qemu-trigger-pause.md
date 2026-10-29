# Temporary QEMU automatic-trigger pause Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans; independently review before integration.

**Goal:** Pause only the QEMU diagnostic's automatic PR and main-push executions.

**Architecture:** Remove the two automatic event entries from the existing diagnostic workflow. Preserve manual dispatch and every job, permission and resource bound byte-for-byte; native ARM64 qualification stays automatic and required by its existing aggregate.

**Tech Stack:** GitHub Actions YAML; pytest source/control-flow contracts.

**Spec:** `docs/07-operations/2026-10-14-branding-arm64-probe.md`, with the bounded trigger-policy amendment below.

## Decision and constraints

Assistant-selected minimal reversible implementation of the requested temporary pause.
Removing the workflow would lose manual diagnostics; job-level skipping would leave
unnecessary automatic checks. Remove only `pull_request` and main `push` triggers.
This is not a diagnosis, successful QEMU result, or permission to run diagnostics.
Historical failures remain failed and NON-QUALIFYING. Reactivation requires a
diagnosed root cause, reviewed bounded fix and specific choice to re-enable the
automatic triggers. Existing runtime/native ARM, security, limits and required-check
settings must not change. Preparation is local only; review and publication remain
separate. No new secrets, credentials, grants, deployment or runtime attempts.

## Review focus

- No automatic trigger remains, including aliases or a different event.
- Manual dispatch and full diagnostic job remain intact.
- Native ARM64 and runtime qualification stay unchanged.
- Failed diagnostic evidence is not rewritten as passing or qualifying.
- Reactivation and manual execution are not implied by retaining dispatch.

## Task 1: Trigger policy and traceability

**Files:** `.github/workflows/branding-arm64-qemu-diagnostic.yml`,
`tests/operations/test_arm64_qualification_workflows.py`, the spec above,
`docs/10-spec-development/execution-state.yaml`, `MANUAL-ACTIONS-CHECKLIST.md`.

**Interfaces:** Existing workflow events become exactly `workflow_dispatch`;
all jobs and qualification-report interfaces remain unchanged.

- [x] Add `test_qemu_automatic_triggers_are_temporarily_paused` asserting the exact
      event block is `on:\n  workflow_dispatch:\n`; update the older trigger
      expectations without changing its security assertions.
- [x] Run the named test; expect failure while PR/main-push triggers remain.
- [x] Remove exactly the three automatic-trigger lines; run both ARM workflow
      and branding probe test modules, expecting all pass.
- [x] Compare the complete workflow suffix beginning at `permissions:` against
      base `3c6513d`; verify all other workflow files are unchanged.
- [x] Amend the normative trigger policy, current state and manual checklist;
      preserve prior failure status and reactivation conditions.
- [x] Run touched lint/format and `git diff --check`; hand off local diff and
      evidence for independent review. Do not push, dispatch or merge.

## Local verification ledger

Baseline workflow module: 148 passed. New trigger regression: 1 failed for
exactly the still-present PR/main-push events, then both focused modules:
263 passed (5.20 seconds), zero skips. Ruff check/format, touched Prettier and
`git diff --check` passed. Byte comparison against `3c6513d` proves exactly the
three trigger lines removed and identical permission/job suffix; all other
workflow files are unchanged. Tests use synthetic shell commands, not actual
Docker/QEMU/native ARM execution. No full application/runtime suite was attempted
in this bounded local-only preparation. Independent review, publication and
hosted evidence remain pending; no remote writes, dispatch, deployment or merge.
