# S1 · Unmounted quote ASGI byte admission

> **Current receipt (2026-10-29): verified unmounted S1 scope.**
> [PR #68](https://github.com/IzignaMx/open-cycling-workshop/pull/68) merged as
> [`72927ca56d8337a07f5b9813902074d87523e920`](https://github.com/IzignaMx/open-cycling-workshop/commit/72927ca56d8337a07f5b9813902074d87523e920),
> tree `2fffef9f478f714d6daea2ed77f3270f9b20bd64`;
> [post-merge CI 40831394467](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40831394467)
> passed 27/27 aggregate controls (5,081 collected, 5,023 passed, 58 expected skips), including
> all 55 admission cases. Local-only/pending statements and failed local checks
> below record the historical implementation checkpoint; their failure details
> remain intact. S1 remains unmounted and cooperative, not a hard cancellation
> guarantee, public route, quote activation or application deployment.

Assistant-selected design under delegated local implementation authority. Source:
`38a8542e7afda0e1da2ca488f0963543bf9cfa31`. No publication, activation or deployment.
Normative for this bounded increment; the quote persistence/online boundary ADR
§5.1 and existing privacy, authorization, cancellation and capacity gates remain.

## Decision and alternatives

Implement only `quotes/admission.py:read_quote_body(receive, *, headers, deadline)
-> bytes`. It accepts Starlette's ASGI `Receive`, raw byte header pairs and the
original `QuoteDeadline`; it neither starts a deadline nor invokes services.
Use a type-only deadline import to avoid coupling transport admission to SQL.
`Request.body()` would buffer before admission; a replacement JSON parser would
duplicate canonical semantics; mounting financial endpoints would expose still
unqualified writes. All three are rejected. This helper is internal Core, not
an extension SDK, loader, middleware registration or public route.

## Exact contract

- Import `MAX_REQUEST_BYTES` (128 KiB); no configurable override. Check length
  before copying each body chunk into one bytearray, then return immutable bytes.
  The existing strict decoder runs exactly once downstream, not inside S1.
  Buffer copying is bounded, not zero-copy. ASGI may already hold a large chunk;
  this does not bound server/proxy allocations or establish wire-framing safety.
- Header names/values must be bytes in two-item pairs. Names match encoding
  case-insensitively. Accept absent Content-Encoding or exactly one value equal
  to identity after ASCII SP/HTAB trimming and case folding. Reject empty,
  duplicate, comma-combined, compressed or other values before any receive.
  Ignore Content-Length entirely, including absent, malformed, duplicated or
  conflicting values: it never authorizes bytes or terminal completion. ASGI
  servers own transfer decoding; S1 does not interpret Transfer-Encoding.
- Accept `http.request`; absent body defaults to `b""`, absent more_body to False.
  Present body must be exact bytes and more_body exact bool. Empty nonterminal
  chunks are valid. Stop after the first terminal request; never drain or read
  ahead. `http.disconnect` fails without parsing. Wrong event type or malformed
  known fields fail closed. Unrelated ASGI extension keys are ignored.
- Fixed `QuoteAdmissionError.code`: `unsupported_encoding`, `too_large`,
  `disconnected`, `deadline_expired`, `invalid_transport`, `receive_failed`.
  Messages contain only the code, with no input/header/exception echo. No HTTP
  status mapping, response sending or successful response-delivery claim here.
  Receiver exceptions become receive_failed; external cancellation propagates.
- Reuse the original deadline's `remaining_ms()` semantics (eight-second start,
  monotonic injected clock, sub-millisecond refusal). Check before/after receive
  and before/after the final immutable copy, before returning. Derive each relative asyncio timeout from remaining time,
  never pass a foreign absolute clock into the loop or renew the deadline.
  Each iteration includes an explicit cancellation/fairness checkpoint, including
  immediately returned empty chunks. Receive executes in the same task, without
  an orphan background task; its timeout context distinguishes owned expiry from
  a receiver-raised TimeoutError. External CancelledError is not normalized.
- Cancellation is cooperative. A receive implementation suppressing cancellation
  indefinitely cannot be forcibly stopped here. Synchronous parsing is not
  preemptible and is outside this helper. A disconnect after terminal body need
  not be observed. Later integration must check the original deadline around
  decoding/business work and separately qualify cancellation/cleanup/commit.

## Preservation and acceptance

No route, OpenAPI, generated client, grants, migrations, SQL/session access,
settings, dependency, runtime budget, M0 contract or Pages/QEMU behavior changes.
Controlled ASGI fixtures exercise the real helper, not actual network/proxy or
physical devices. Prove exact byte boundary, unsupported encoding before reads,
ASGI defaults/type failures, original-deadline exhaustion, external cancellation,
no read-ahead/parse/service call and no orphan receive. Retain all existing strict
JSON/privacy tests. Independent review and exact-source hosted evidence remain
separate; Tasks 5/6/8 and total cancellation are not completed by S1.

## Local evidence and retained gaps

Initial behavioral RED: 50 failed, then 50 passed. Additional exact-event-type
regression failed before its correction. Independent review exposed a deadline
crossing during final immutable copy; its regression failed before adding the
post-copy check. Final affected suite: **200 passed**, including **55 admission
cases**, zero skips and one existing Starlette test-client deprecation warning.
Final full quotes-directory run: **1,042 passed / 397 environment skips / ten
warnings**, 76.50 seconds under the same serial 900-second/768-MiB address-space
cap. Skipped PostgreSQL/restore cases are unverified. Fresh full collection is
5,081 cases. This affected-suite pass does not supersede the failed whole-suite
attempt below. Strict mypy, touched Ruff/format, OpenAPI and generated-client
checks passed.
Independent source/security review reported 58 cases plus 3,000 malformed inputs
and no remaining blocker after the copy fix; not formal PR approval or hosted proof.

The full local Python attempt did **not** pass: with `timeout 900` and
`ulimit -v 786432` (768 MiB virtual address space), it accumulated failures/errors
then segfaulted in the existing deep-JWT-header test. A bounded first-failure run
stopped at `test_browser_protocol_unit_cases`: Node could not reserve its virtual
CodeRange (940 passed, nine skipped, one failed). The same single test on exact
unchanged base `38a8542` reproduced that failure with the same cap. RLIMIT_AS is
not the existing container RSS/memory budget and this comparison is not a product
regression diagnosis. The deep-JWT-header case passed alone on that exact base
under the same cap; the full-run crash cause remains unproven. No resource limit
was increased, no full run retried after that classification, and no passing
whole-suite or runtime qualification is claimed. A redundant earlier quote-only
run was interrupted at 55% after overlap was noticed, not counted as completed.

The local implementation remains uncommitted/unpublished pending coordinator
assessment. Production router/client/workflows, grants and M0 remain unchanged.

## Draft qualification handoff

The local-only checkpoint above is preserved as history. The bounded reviewed
payload proceeds separately to ordinary draft-PR qualification under the
continuing development request; this does not waive the failed local full run.
Require all 55 new cases and the complete existing identity/security matrix in
exact-source hosted fixed-limit evidence, with no omitted tests, changed skips,
weakened harness or resource increase, before considering integration. No route,
SDK export, grant, module execution or operational deployment is authorized by
this handoff. A successful hosted result would not retrospectively pass the
failed local run or prove total synchronous Python/DB cancellation.
