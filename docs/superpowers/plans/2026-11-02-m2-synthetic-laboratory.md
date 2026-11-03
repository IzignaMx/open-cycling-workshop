# M2 Synthetic Laboratory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a non-production synthetic catalogue machine-authority boundary without activating any normal application access.

**Architecture:** Test-only Python package under `tests/labs/m2`, absent from the production wheel and app composition. Dedicated machine authority and fixture schema; real Core product projection through a bounded ASGI app. Explicitly separate local SQLite/ASGI functional evidence from blocked real PostgreSQL, TLS/process/network enforcement.

**Tech Stack:** Existing Python3.13, SQLAlchemy2, FastAPI, pytest/httpx; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-02-m2-synthetic-laboratory-design.md` (approved for isolated lab implementation16:07UTC).

## Global Constraints

- No normal-app routes, real data/credentials, new human permissions, publication, merge or deployment.
- Credentials only in ephemeral controlled test memory; never output/log/report/archive plaintext.
  -15-minute absolute and suspend-inclusive monotonic run limits; rotation never extends run; zero credential overlap.
- One derived location/read-only resource, no automatic retry/offline serving.
- No Docker or psql available locally: do not substitute an unconstrained network server for isolation; preserve unmet execution gates.
- Physical V0.1/SPENT/UNKNOWN/Pages unchanged; no release advancement.

## Review Focus

- Scope confusion across two organizations/locations: authority and API tests require exact projection and generic refusal.
- Clock rollback/expiry while materializing: authority tests exercise pre/postyield checks with controlled clocks.
- Token leakage through pytest failures/logging: credential repr hidden, assertions evaluate booleans/status, audit/verifier only.
- Production metadata contamination by test model imports: separate LabBase; production routes/OpenAPI/roles/schema unchanged test.
- Unavailable runtime guarantees: preflight is fail-closed; real PostgreSQL/network/TLS/resource/disposal gates remain explicitly unqualified.

## Task1 — Dedicated authority and lifecycle

Files: `tests/labs/m2/authority.py`, optional `models.py`, `test_authority.py`.
Interface: fresh owned functional fixture, opaque Credential, machine `read()` context returning scoped Session; fixture-only issue/rotate/revoke/grant operations and close cleanup. No arbitrary DSN or human principal.

- [x] Write behavioral tests for absent authority, scoped read, expiry, rotation/revoke/current grants and metadata separation; observe expected RED without plaintext outputs.
- [x] Implement minimum dedicated model/transaction/clock lifecycle; no production files.
- [x] GREEN focused suite; preserve SQLite-only proof and close all owned resources.

## Task2 — Closed ASGI catalogue boundary

Files: `tests/labs/m2/application.py`, `test_application.py`.
Interface: `create_lab_app(authority)` receives Task1-owned fixture; no app startup/CLI/network activation path. ClosedGET projects actual Core ProductRecord under `read()`; body fully serialized before transaction exit.

- [x] RED scoped five-field HTTP result and auth/token/unknownquery/limit/refusal tests, plus normal app route absence.
- [x] Implement server-side application concurrency/run/auth/input/response limits and no-store errors; preserve distinction from transport enforcement.
- [x] GREEN real ASGI/SQLite requests; no claim of TLS/network/PG lock proof.

## Task3 — Execution admission, cleanup and evidence

Files: `tests/labs/m2/connector.py`, `test_connector.py`, `preflight.py`, `test_preflight.py`, `README.md`; bounded status documentation.
Interface: explicit in-process TestClient-only one-shot reader, exact scope-bound memorySQLite projection, maximum4pages, no retries/stale-current response and verifiedclose. This does not stand in for a separate process or TLS.
Interface: read-only environment qualification probe; no credential creation/container launch when required capabilities absent.

- [x] RED real-ASGI owned-projection fetch, revoke/error clears stale data, malformed/cyclic pagination refused, close destroys the functional memory store; implement minimum GREEN.
- [x] RED preflight refuses unavailable Docker/PostgreSQL/runtime policy evidence; do not add production enable flags.
- [x] Implement explicit unmet-gate reporting with secret-free outputs; no fake runtime fixture or skipped-as-green evidence.
- [x] Verify cleanup of all actually created memory/state; no file credential/CA/volume claim if never created.
- [x] Run local fullPython/static/repository/frontend regressions appropriate to final diff; record environment skips.
- [x] Independent implemented-local-slice security review and TDD corrective regressions.
- [ ] Final sanitized recoverable backup and truthful partial completion checkpoint.

## Completion and blocked scope

Completed checks above describe the local functional increment only. No executable
separate-process/TLS/OS-enforcement harness or actual PostgreSQL test was delivered;
these remain unimplemented/blocked, not completed by the preflight inventory.

This environment can qualify only local functional layers. Separate-process TLS, PostgreSQL18 lock linearization, network/resource enforcement and crash teardown require an authorized capable environment; not implemented/verified by an ASGI client. Do not publish or seek merge while calling those passed. If no such environment exists, deliver the reviewed useful local increment with explicit remaining design tasks and ask parent for the next execution decision, not silently broaden security settings.
