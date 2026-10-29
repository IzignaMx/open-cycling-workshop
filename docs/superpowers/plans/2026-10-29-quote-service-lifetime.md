# Quote-service lifetime characterization Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans; independent review before publication.

**Goal:** Pin four existing service lifetime branches without adding behavior.

**Architecture:** Reuse SQLite fixtures and actual QuoteService.execute; inject bounded faults at encoding, commit return and hook-release method. Production source stays byte-identical.

**Tech Stack:** pytest, existing SQLAlchemy SQLite fixtures, synthetic CancelledError and fake clock.

**Spec:** `docs/superpowers/specs/2026-10-29-quote-service-lifetime-design.md`.

## Global constraints

Exactly four tests; no new executor, ledger, timeout, route, permission, grant or
SDK contract. Preserve original operation/proof/receipt and eight-second deadline.
No cleanup-arriving cancellation precedence decision. Local-only work.

## Review focus

Fault reaches real writes/commit; same cancellation identity; exactly-once cleanup;
full immutable receipt replay; mutation actually changes each asserted branch.

## Task 1: Four characterization tests and source receipts

**Files:** modify `services/platform/tests/quotes/test_quote_application_service.py`,
`docs/10-spec-development/execution-state.yaml`, `MANUAL-ACTIONS-CHECKLIST.md`;
record evidence in this design/plan pair.

**Interface:** unchanged existing `execute`, `totals`, commands and QuoteService.

- [x] Write the four design cases using existing fixtures; run baseline green or
      isolate any unexpected behavior before changing production.
- [x] Apply four temporary targeted mutations, one at a time; run the respective
      case and observe failure. Restore original source in a guaranteed cleanup.
- [x] Run application-service/request/deadline/admission/privacy regressions;
      compare all production files to base, then lint/format/diff checks.
- [x] Reconcile only grounded M0/S1 source qualification status with exact receipts,
      preserving historical failures and nonactivation boundaries.
- [ ] Freeze local diff, source hashes and logs for independent review; no push.
