# Quote ASGI admission Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans; independent review follows local verification.

**Goal:** Admit bounded raw quote bytes without activating a route or business operation.

**Architecture:** One unmounted async receive helper composes with existing QuoteDeadline and strict decoders. Relative waits consume the original deadline; no receive task or background worker is created.

**Tech Stack:** Python 3.13, asyncio, existing Starlette ASGI types, pytest.

**Spec:** `docs/superpowers/specs/2026-10-29-quote-asgi-admission-design.md`.

## Global constraints

128 KiB fixed request limit; original eight-second deadline; no router/SQL/grants,
dependency, budget or public SDK changes. Local-only implementation authority.

## Review focus

Optional ASGI keys, immediate empty-chunk floods, receiver-raised versus owned
timeout, simultaneous external cancellation, terminal-body read-ahead. Each gets
explicit cases in the admission tests. Cooperative cancellation is not hard cutoff.

## Task 1: Unmounted transport admission

**Files:** create `services/platform/src/cycling_workshop/quotes/admission.py` and
`services/platform/tests/quotes/test_quote_admission.py`; update execution state
and manual checklist with precise evidence boundaries after testing.

**Interface:** `async read_quote_body(receive: Receive, *, headers:
list[tuple[bytes, bytes]], deadline: QuoteDeadline) -> bytes`; fixed-code
`QuoteAdmissionError`, no response mapping or parser.

- [x] Write parameterized byte/header/event cases and deadline/cancellation tests.
- [x] Run `pytest services/platform/tests/quotes/test_quote_admission.py -q`;
      expect missing implementation failure, then observe behavioral RED using
      a minimal not-implemented helper before implementing admission logic.
- [x] Implement only the design's admission contract; run the new tests GREEN.
- [x] Run existing quote request/privacy/logging/service/deadline suites and
      app/OpenAPI/generated-client unchanged guards, then touched static checks.
- [ ] Run the full local Python suite within existing serial limits; distinguish
      environment skips from runtime proof. Record results and independent-review
      handoff; no remote publication, capacity trial or diagnostic execution.

## Execution ledger

Focused request/privacy/logging/driver/admission: 200 passed, zero skips; typed
source and contract checks passed. Terminal-copy deadline review finding fixed
through its own RED→GREEN regression. Full-suite attempt failed and crashed;
first-failure exact-base comparison and isolated JWT result are recorded in the
spec, not normalized into full acceptance. No additional full execution or remote
action. The broad-suite plan step remains unqualified. Independent review found
no remaining source blocker, but publication still requires coordinator assessment.

Final quotes-directory verification: 1,042 passed, 397 environment skips, ten
warnings in 76.50 seconds under serial 900-second/768-MiB address-space cap.
Fresh full collection: 5,081. Full-suite acceptance remains unqualified.
