# Official Module Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inspect the built-in reference's exact declarations without granting authority or disturbing reception.

**Architecture:** A closed source-owned descriptor and React disclosure are explicitly composed as a sibling in App. A localized error boundary contains only detail rendering; native disclosure remains usable.

**Tech Stack:** Existing React 19, TypeScript, Node test runner, ReactDOMServer and Playwright. No new dependencies.

**Spec:** [Accepted design](../specs/2026-11-02-official-module-reference-design.md).

## Global Constraints

- No loader, SDK, manifest execution, storage, network, grants or controller interface.
- Static inspection remains available offline; declared operational mode remains online-only.
- No fake asynchronous states or production fault-injection hook.
- Preserve AGPL-3.0-only and existing capture identity/ownership.
- No remote publication, merge or deployment in this local authorization.

## Review Focus

- Public declarations describe only this reference, not Core; exact content tests.
- Omitted build descriptor is not an installation state; null descriptor test.
- Unexpected render error must not expose details or break capture; native harness test.
- Disclosure toggle must preserve draft DOM identity and focus; native App journey.
- Plain metadata text must be escaped; real React rendering assertion.

## Task 1 — Source-owned inspection and App composition (implementation agent)

Files: create `apps/web/src/features/module-information/reference.ts`,
`ModuleInformation.tsx` and `module-information.css` in that directory; create
`apps/web/tests/module-information/reference.test.mjs`; modify
`apps/web/src/App.tsx`, `apps/web/tools/run-core-tests.mjs` and the narrow React class declaration in `apps/web/tools/static-shims.d.ts`.

Interface: `OfficialModuleReference` is a closed readonly source-owned type;
`officialModuleReference` is its sole production constant.
`ModuleInformation({ reference }: { reference: OfficialModuleReference | null })`
accepts no runtime/transport or action callbacks.

- [x] Write actual ReactDOMServer behavioral test; a null-rendering minimal component baseline must fail on missing declared-scope content, not unresolved import.
- [x] Preserve RED under `artifacts/module-reference/`.
- [x] Implement descriptor, semantic disclosure, omission copy and fixed localized error fallback; add explicit App sibling import.
- [x] Verify exact rendered declarations, absence of installation/action claims and HTML escaping; integrate test into core runner.
- [x] Run focused tests and normal/offline types, build, lint/format. Record commands/results; no native claim from SSR.

## Task 2 — Native isolation and independent qualification (browser agent/coordinator)

Browser agent owns its new e2e spec and any test-only component harness; no production debug API.
Coordinator owns state/checklist/traceability and broad qualification receipt.

- [ ] Prove native disclosure keyboard/focus, same mounted draft inputs/values, operational capture after toggle, themes/accessibility.
- [ ] Prove honest build omission and genuine render error containment in test-only actual React composition.
- [ ] Run full core and independent review on final source.
- [ ] If native sandbox remains blocked, retain exact blocker; static collection does not satisfy native execution. Publication requires separate authority.

## Ledger

- 2026-11-02: coordinator and independent builder accepted bounded design. Local source/TDD authorized; no remote operations.

- Task 1 RED: actual ReactDOMServer renders the null component baseline; 3 content/omission/escaping assertions fail (not import failures), retained `artifacts/module-reference/render-red.log`. Implementation then passes all 3.
- Ruling: add narrow summary CSS with existing 44px/56px workshop-density/focus tokens — native summary alone does not guarantee target size. No shared style overhaul.
- Ruling: error UI contains no exception text and code adds no logger; React framework diagnostics are not claimed suppressed.

- Task 1 verification: focused 5/5, normal and offline types, build and scoped lint pass. Initial offline check failed because static React shim lacked Component; narrow generic declaration fixes it, real React typecheck remains primary.
- First full core run: 1236/1237, retained automatic-verification/new-baseline sync assertion observed `local` rather than `synced` after its fixed event-turn budget. Failure preserved in `artifacts/module-reference/core.log`; no assertion was weakened. Both affected modes pass five focused repetitions (10 tests); unchanged-source full rerun passes 1237/1237 (`core-rerun.log`). This does not establish why the first attempt failed.
- All 39 affected runtime/kernel/fixture/test sources are byte-identical to baseline aa43206 (artifact hash manifest); no causal claim from workload alone. Coordinator retains the transient qualification finding.
- CSS contract was added after the density correction and passed; it is not claimed as an observed RED. Native geometry/focus/error-boundary evidence remains separate.
- Artifact-only diagnostic copied the exact aa43206 affected test and preserved its original assertion outcome; both cases reached synced inside the original budget (0 extra diagnostic turns). It did not reproduce or explain the first suite failure. No runtime or retained-test change follows; `baseline-timing-diagnostic.log` retains the traces.

- 2026-11-02 local execution: focused5 pass; frontend first1236/1237 then1237/1237. First unchanged controller timing assertion failure remains unexplained and retained, not fixed. Native5 authored/collected, zero local execution; hosted qualification/publication gates remain open.
