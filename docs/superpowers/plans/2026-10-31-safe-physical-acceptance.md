# Safe Physical Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Replace active unsafe historical instructions with a bounded physical-device observation protocol, without executing it or claiming qualification.

**Architecture:** Preserve the August protocol/results as history with prominent warnings. Route active checklist/state entry points to a new eight-case protocol and unexecuted results template; enforce this with static documentation contracts only.

**Tech Stack:** Markdown, YAML and Python repository tests; no runtime, Compose, workflow or dependency changes.

**Spec:** `docs/10-spec-development/open-cycling-workshop-platform-agent-master-loop-v0.2.md`, `docs/07-operations/2026-10-14-local-runtime.md`, `docs/07-operations/2026-10-14-backup-restore.md`, and R01-T035 in the Phase 10 master specification.

## Global constraints

- AGPL-3.0-only; DCO; Offline First / Local First; preserve local pending work.
- Documentation is not device, restore, capacity, accessibility or release evidence.
- No security bypass, volume/IndexedDB deletion, credential reuse, destructive storage experiment or consumed measurement replay.
- No installation, credentials, authority, Pages, budgets, runtime or workflow changes.
- R01-T035 still requires its own 100,000-record spike and physical storage baseline.
- Historical cleanup of microfixture41011497919 remains UNKNOWN.

## Recovery and evidence provenance

The previously reviewed local October 30 package (candidate prefix 325ceafc,
tree prefix fd095964) was not published. Its bytes are unavailable after executor
replacement; surviving checkouts predate it and retained notes contain summaries,
not a patch. This is a newly authored replacement of the same approved eight-file
scope on main `ba3aced05a026a40aaf3c77cafea6b626498cba5`, not a byte-identical recovery.
The previous 110-test result does not qualify these new bytes. Fresh independent
review, local checks and exact-head hosted/postmerge evidence are required.

## Review focus

1. An existing installation with unsynced data must not be reset to make a test pass.
2. Android USB or another network route can defeat an assumed offline state.
3. A template or successful CI must not be presented as physical qualification.
4. Old checklist entry points must not continue directing operators to unsafe steps.
5. Server counts/local UI alone must not be treated as exactly-once or restore proof.

## Task 1: Documentation boundary and regression contracts

**Files (exactly eight):**

- Modify `MANUAL-ACTIONS-CHECKLIST.md`.
- Modify `docs/10-spec-development/execution-state.yaml`.
- Modify `docs/11-device-qualification/2026-08-31-tier1-protocol.md` (warning and removal of a historical fixture password).
- Modify `docs/11-device-qualification/2026-08-31-tier1-results.md` (warning only).
- Create `docs/11-device-qualification/2026-10-31-safe-tier1-protocol.md`.
- Create `docs/11-device-qualification/2026-10-31-safe-tier1-results.md`.
- Create this plan.
- Create `tests/repository/test_safe_tier1_protocol.py`.

**Interfaces:** Operator documentation only. T1–T8 are separately recorded per
device, default PENDIENTE; blocked/excluded work remains open. No product API.

- [x] Write 13 static contracts for the new documents, all eight pending rows,
      preconditions, safety exclusions, historical notices and active entry points.
- [x] Observe RED: all 13 failed against unchanged main before docs were added.
- [x] Add protocol and template, warning-only historical changes, and replace
      active checklist/state pointers. Preserve all unrelated evidence.
- [x] Run focused and retained repository/operations tests, Ruff/format, YAML,
      link validation and repository contract; record exact command outcomes.
- [x] Independently review final eight-file patch; resolve findings within scope.
      Review clarified Workshop target sizes and copying the pending template
      rather than overwriting it with physical results.
- [ ] Commit with DCO; publish as draft PR only after verifying remote parent.
- [ ] Accept exact-head hosted required workflows and artifacts; no same-head
      consumed-trial reruns or relaxed checks. Merge only on a fully accepted head.
- [ ] Verify fresh main workflows/artifacts. Physical execution remains pending.

## Local evidence

Evidence files are retained locally under `artifacts/safe-protocol/`, not published
as physical records. Initial docs run: 11 passed, two failed on case-sensitive text
contracts; clarified wording and made the excluded-scenario text check case-insensitive
without changing the required exclusions. Static
tests cannot prove the physical observations described by the protocol.

Fresh local evidence: 133 focused tests (13 new + 120 retained), full Ruff, touched
Ruff formatting, Prettier including YAML syntax, repository contract and diff
whitespace check passed. Initial Ruff line length/format failure and Markdown
table-padding test failure were corrected, not suppressed. Optional direct YAML
module probes were unavailable (Python/Node module missing); Prettier parsed the
YAML successfully. No dependencies installed and no physical test performed.

Publication preflight rejected the historical protocol blob because its unchanged
legacy text retained a plaintext fixture password. That value was removed rather
than republished; no credential is needed for this documentation. The regression
contract now checks its absence. Earlier checklist/state blobs are unreferenced
objects until the final eight-file tree is accepted and published.
