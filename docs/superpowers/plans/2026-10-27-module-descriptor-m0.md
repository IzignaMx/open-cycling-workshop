# Module Descriptor M0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a bounded data-only proposal contract for compatible modules, without adding an extension runtime.

**Architecture:** A trusted closed JSON Schema plus pure standard-library byte-envelope validation; inert official-build/external-connector fixtures. Exact source-target identity replaces any speculative host-version conversion.

**Tech Stack:** JSON Schema vocabulary subset, Python 3.13 standard library, pytest, existing formatting tools.

**Spec:** `docs/superpowers/specs/2026-10-27-module-descriptor-m0-design.md`

## Global Constraints

- AGPL-3.0-only Core/official code and DCO unchanged; descriptor validation is neither trust nor licensing certification.
- Input at most 16,384 bytes, strict UTF-8 JSON; fixed error codes with no input echo.
- No loader, dynamic imports, network, grants, identities, database/migration, offline enrollment or SDK runtime exports.
- Source target exactly `ocwp-source:a960bddb94189c6c74c7f3d0a72472636c3caced`; no SemVer host range evaluation.
- Existing canary/time/memory/capacity/install/physical gates unchanged; no consumed trial rerun.

## Review Focus

- Duplicate nested keys and bool-as-int must not bypass strict envelope/schema rules.
- Unsupported source target cannot become an implicit compatibility certification.
- Unknown/hidden executable or nonempty authority declarations fail closed.
- Pathological size/depth/Unicode/numeric input yields bounded errors, not tracebacks/input disclosure.
- A valid external descriptor never implies external service identity, installed runtime or Official trust.

### Task 1: Canonical normative contract

**Files:** design/plan above; `docs/08-open-source/2026-10-27-module-descriptor-m0.md`; `docs/10-spec-development/execution-state.yaml`.
**Interfaces:** consumes Phase 5/8 conceptual manifest drafts; produces explicit M0 vocabulary and non-goals.

- [x] Record independent design review and exact chosen fields; specify parser envelope versus schema semantics.
- [x] Validate docs/links and sign documentation commit before implementation.

### Task 2: Schema, examples and bounded validator

**Files:** `packages/plugin-sdk/manifest/descriptor-m0.schema.json`; `packages/plugin-sdk/examples/official-descriptor.m0.json`; `packages/plugin-sdk/examples/external-descriptor.m0.json`; `scripts/plugins/validate_manifest.py`; `tests/contracts/test_module_descriptor.py`.
**Interfaces:** `validate_descriptor(raw: bytes) -> dict[str, object]`; raises `DescriptorError` with fixed `.code`, no input values. CLI reads at most MAX_BYTES + 1 and prints only `descriptor valid; runtime not evaluated` or a fixed error code.

- [x] Write tests for two inert examples and all declared parser/schema failures: duplicate/unknown nested keys, bool/fractional numbers, invalid UTF-8/BOM/surrogates, 16,385 bytes, deep JSON, aliases, wrong source target, nonempty authority, executable fields, unsupported profile/runtime/version.
- [x] Observe RED for missing implementation; implement fixed closed schema and bounded pure validator using only its known trusted vocabulary, never fetching schemas or executing descriptor metadata.
- [x] Observe GREEN; prove CLI valid/error exit/status without payload echo; confirm original bytes/inputs remain unchanged and no filesystem/network runtime effects.
- [x] Run all contract/repository tests and touched Python/JSON formatting; sign implementation commit.

### Task 3: Guidance and integration proof

**Files:** `packages/plugin-sdk/README.md`; M0 guide and execution record above.
**Interfaces:** communicates descriptor-only readiness and later official/isolated runtime acceptance, with links to existing source and release tasks R09-T020/R09-T021/R10-T014.

- [x] Document example invocation, supported profile and exact parser bounds, namespace ownership review and license declaration limits.
- [x] Explain future migration/auth/tenant/offline/recovery requirements without advertising nonexistent interfaces.
- [x] Independently review local branch and fix important findings with RED/GREEN; run full local suite/static checks. Hosted exact-source qualification remains pending.
- [ ] Publish only with applicable explicit repository authority, then require normal CI and verified postmerge; never bypass pending publication blockers for another payload.

### Task 4: Local reconciliation after presentation merge

- [x] Preserve original `a37186c` and replay design/implementation onto reviewed
      main `1946608`; resolve only the execution-state insertion conflict without
      dropping current main records.
- [x] Retain the canonical Phase 8 vocabulary, reject Phase 5 aliases and keep
      the original exact proposal target rather than auto-promoting compatibility.
- [x] Re-run focused/full local tests, static checks and independent review of
      the final reconciled source; preserve source-bound logs and frozen payload.
- [ ] Obtain separate applicable publication authority before any remote M0
      branch/PR, then require normal exact-source hosted and postmerge evidence.
