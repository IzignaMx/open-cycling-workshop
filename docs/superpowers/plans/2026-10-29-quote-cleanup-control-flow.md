# Quote cleanup control-flow precedence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Independent design acceptance precedes TDD; final independent review precedes publication.

**Goal:** Preserve the first observed control-flow exception through existing quote cleanup.

**Architecture:** One invocation-local captured exception/traceback tuple and capture closure flows through existing private cleanup helpers. Existing cleanup ordering, ordinary mapping and financial persistence remain unchanged.

**Tech Stack:** Python, pytest, existing SQLAlchemy SQLite synthetic fixtures; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-29-quote-cleanup-control-flow-design.md`.

## Global constraints

Local only until coordinator authorization; no commits/publication in this task.
No new executor, ledger, exception fields, routes, grants, SDK, budgets or workflows.
First non-Exception BaseException wins with identical object and origin traceback;
raising adds frames, so no byte-identical traceback claim. No hard cutoff claim.
Group the existing five-file PR67/69 receipt reconciliation without rewriting old
failures. S2b remains pending until its own source-specific qualification.

## Review focus

- Nested invalidation cannot swallow the first cleanup cancellation (matrix 3, 7).
- Original cancellation precedes all later cleanup errors (matrix 6).
- Quarantine is set before recovery and no failed Session is reused (matrix 1–8).
- COMMIT outcomes are observed via same-ID receipt, never guessed rollback (4, 5).
- Raw exception objects remain transient/private, never logged or persisted (all).

## Task 1: Capture precedence without changing transaction semantics

**Files:** modify `services/platform/src/cycling_workshop/quotes/service.py` and
`services/platform/tests/quotes/test_quote_application_service.py`; update this
plan/spec, `docs/10-spec-development/execution-state.yaml` and
`MANUAL-ACTIONS-CHECKLIST.md` with truthful bounded evidence only.

**Interfaces:** Public execute/error contracts unchanged. Local
`capture_control_flow(error: BaseException) -> None` retains the first eligible
`tuple[BaseException, TracebackType | None]`. Private `_rollback` and `_invalidate`
accept `capture: Callable[[BaseException], None]` and still return bool.

- [x] Receive coordinator's independent design acceptance and incorporate its
      capture-before-cleanup, same-object traceback suffix, no-persistent-roots and
      finite-topology clarifications before TDD.
- [x] Add `test_cleanup_control_flow_precedence` parametrized over matrix rows
      1–3, 6–8: assert exact earliest exception identity, first-observed traceback suffix (including same-object secondary raise), call order,
      quarantine-before-invalidate, max one rollback/two invalidations/one release,
      no new persistent service/session roots and rejected Session reuse.
      Use sentinel args without logging/serialization; restore fault before teardown.
- [x] Add `test_committed_cleanup_control_flow_replays_exact_receipt` for rows
      4–5 using existing capture/receipt/Session helpers: actual commit once,
      exact C1, no success, one effect tuple and fresh same-ID/proof receipt equality.
- [x] Run both new test groups with existing venv, serial `timeout 900` and
      `ulimit -v 786432`; record genuine baseline failures from swallowed cleanup
      exceptions. Distinguish already-passing characterization rows.
- [x] Implement only the local capture tuple/closure, capture-before-cleanup and
      capture-before-nested-invalidation ordering specified by the design; propagate
      the winner after bookkeeping with captured traceback and `from None`.
- [x] Rerun both groups GREEN, then application-service, driver-budget, recovery,
      requests, admission, HTTP-privacy and logging modules. Require existing
      ordinary flags/codes and all four S2a cases unchanged (matrix 9).
- [x] Temporarily remove nested capture or swap first/last precedence where needed
      to prove test sensitivity; record expected RED and restore source before GREEN.
- [x] Run Ruff/format, generated OpenAPI/TypeScript checks, repository contract,
      YAML parsing, final collection and full locked repository Prettier AFTER all
      documentation edits; `git diff --check` must pass. No broken full-suite retry.
- [ ] Record actual commands/counts/failures, freeze source hashes and local diff,
      request independent implementation/security review and wait for coordinator.
      No commit, remote write, deployment or diagnostic execution in this plan.
