# Ownership Receipt Uncertainty Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve unknown execution facts and validated terminal pre-GO failures.
**Architecture:** Version only the host receipt, retain strict owner frame validation,
then enforce new receipt version at current finalizer/staging boundaries.
**Tech Stack:** Python3.13, pytest, existing closed JSON codec.
**Spec:** ../specs/2026-10-29-quote-ownership-receipt-design.md

## Global Constraints

- Actual run40927223929 remains spent; no runtime trial, new workflow or guard reset.
- Tests use pure/mock adapters only; no Docker, DB or actual process stop.
- Receipt16384B/frame4096B, existing deadlines/resources and success rules unchanged.
- Historical schema1/artifacts immutable; no claim the historical cause is identified.

## Review Focus

- Transport loss after synthetic GO must not become skipped/not-started evidence.
- Valid early failure must not permit GO or admit a success-result bypass.
- Legacy decoder compatibility must not qualify a fresh current artifact.
- Cleanup success must not promote unavailable observation to successful measurement.
- Partial observer setup facts in accepted failed RESULT must not be discarded.

### Task 1: Receipt uncertainty and closed transport correction

**Files:** scripts/ci/quote_ownership_evidence.py, quote_ownership_measurement.py,
quote_ownership_staging.py; tests/operations/test_quote_ownership_{measurement,controller,controller_boundaries,staging}.py.
**Interfaces:** Preserve decode_receipt(raw,identity) legacy reads; new host outputs
schema2; validate_receipt validates exact version-specific shapes. HostRuntime.observe
accepts only strict failed pre-GO RESULT or normal RESERVED choreography.

- [x] Independently review this design before implementation.
- [x] Add tests for unavailable canonical unknown output after mocked observe refusal,
      legacy decode retention and fresh boundary rejection; observe expected RED.
- [x] Add in-memory early RESULT positive/negative transport tests; observe RED.
- [x] Implement versioned receipt and host transport branch minimally.
- [x] Run all ownership mocks and retained containment tests serially under existing
      900s/768MiB ceiling; strict mypy, Ruff and touched documentation formatting.
- [ ] Independent exact-diff review; record failures and scope without runtime claims.
- [ ] Coordinator handles whole-suite qualification, publication and any later authority.
