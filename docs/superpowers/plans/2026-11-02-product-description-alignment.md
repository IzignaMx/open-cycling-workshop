# Product Description Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make every repository-description claim traceable to a truthful phased requirement and acceptance path without declaring unimplemented modules complete.

**Architecture:** Add a requirements supplement and machine-readable planning matrix, extend canonical Phase 10 tasks only for real agenda/staff gaps, and retain the separate runtime-evidence ledger. No runtime architecture, dependencies, permissions or deployments change.

**Tech Stack:** Markdown, JSON and Python repository contracts.

**Spec:** `docs/01-functional-requirements/2026-11-02-product-description-supplement.md`; current Foundation/Phase 1/Phase 10 and accepted ADRs.

## Global Constraints

- Core and official applications: `AGPL-3.0-only`.
- Offline First and Local First are mandatory product properties.
- WCAG 2.2 AA is the minimum stable-release accessibility target.
- Evidence precedes status; never mark blocked/untested work as verified.
- Preserve original IDs and historical evidence; PR79 candidate is merged; its fresh-main qualification remains a separate gate.

## Review Focus

- Agenda timezone and offline collisions: explicit UTC/IANA/DST and provisional conflicts, not double confirmation.
- Staff directory vs authority: no implied account/grant, no payroll scope expansion.
- Retail-only vs workshop assumptions: sale does not require bicycle/order.
- White label vs cosmetic themes: all output surfaces, license/privacy/accessibility preserved.
- Planning matrix vs proof: no fake test IDs or product completion from text checks.

### Task 1: Add deterministic coverage contracts

**Files:** Create `tests/repository/test_product_description_coverage.py`.

**Interfaces:** Consumes repository description and canonical source documents; produces checks for twenty unique claim keys, real source/task links, all supplemental FR references and an acyclic additive task graph.

- [x] Write five tests covering complete claim set, references/dependencies, unique supplemental requirements, discoverability and cross-cutting boundaries.
- [x] Run focused pytest on unchanged baseline; record five failures caused by missing artifacts, not environment.
- [x] Re-run after final documentation; all five must pass. A passing text contract is not behavior acceptance.

### Task 2: Reconcile specification, plan and navigation

**Files:** Create the requirements supplement, alignment record and `product-description-coverage.json`; modify Phase 10 master, Phase 1 pointer, README, ARCHITECTURE, AGENTS, execution state and checklist. No existing test-evidence row is promoted.

**Interfaces:** Matrix uses `schema: 1`, `coverage_kind: planning_not_product_completion`, source SHA, description provenance, `claims` and `added_tasks`. Every claim carries requirements, tasks, stage, product status, evidence paths, at least two concrete acceptance scenarios and remaining work. IDs R02-T024–029 are additive and mapped to six explicit dependency lists. The test parses canonical Depends cells, checks exact equality for new tasks and walks all task-ID edges for cycles. Release prerequisites retain the canonical sequence; workshop-only R02-T029 cannot close later retail/commerce profile acceptance.

- [x] Verify live repository description and inspect canonical docs/source.
- [x] Map all twenty claims; distinguish source inventory from validation receipts.
- [x] Add missing FR/task acceptance without replacing accepted architecture or original IDs.
- [x] Run `python -m pytest tests/repository -q`, Ruff/format on the new test, JSON parsing, YAML parsing and `git diff --check` against final files.
- [x] Independently review full-domain coverage, no circular dependencies or false completion; address findings and rerun affected checks.
- [x] Commit with DCO only after local green; record exact tree and scoped evidence. Publication/merge/CI remain separate from this local planning validation.

### Task 3: Resume implementation through release gates

**Files:** Future bounded slice must list exact files after reproduction; this task does not authorize speculative runtime edits within the documentation package.

**Interfaces:** Consumes PR79 exact-source qualification and remaining V0.1 requirements; produces one reviewed next-slice design and behavioral RED, or a precise physical/authority blocker.

- [x] Record PR79 candidate qualification and merge on `7cf38e17`; retain the original source receipts.
- [ ] Verify PR79 fresh-main terminal qualification before relying on postmerge acceptance.
- [ ] Inspect unsent draft/reload/crash and durable receipt ownership; reproduce one data-integrity gap if present.
- [ ] Follow existing design/TDD/independent review; preserve original requirement criteria and migration/security boundaries.
- [ ] Do not start broad V0.2/commerce while an automatable higher-priority readiness gate remains; document physical blockers honestly.
