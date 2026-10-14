# Browser acceptance fixture contracts · 2026-10-14

Status: test-only correction implemented; exact integrated-head hosted browser
qualification and independent review remain required. Base: `01942a3`.
No production source, permission grant, timeout or acceptance outcome changes.

## Trace-backed RED evidence

The first PR38 source head was `b9da73fa7c764b7a3592688db7199e77457e44a0`;
CI tested merge `897ce6a54567461e3bbc9769967b04a4042ede68` in
[run 38611518068](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38611518068).
The downloaded [direct-browser artifact 11919782087](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38611518068/artifacts/11919782087)
was verified against the uploader's ZIP SHA-256:
`6452551f5d67241171709f85ba69b61ff53018d6a212fdc54430f2244d713b88`.
The following are first-attempt traces, not inferred from retry results.

1. **Both order-lifecycle cases stop before order submission or reload.**
   Their `1-trace.trace` records show `call@63` querying
   `internal:label="Cliente"s >> option[...]` and returning zero, followed by
   `call@65` waiting on the exact label until the test deadline. The actual
   target customer option already exists in snapshot `after@call@47`; login,
   customer create, durable ACK and authoritative delta checks have passed.
   Both error-context accessibility trees expose a combobox named `Cliente`.
   `OrderQuickIntake` nests its select and all options inside the label.
   Playwright 1.62's label engine uses that label's complete descendant text,
   including options; its role engine uses the control's accessible name.
   The corrected helper uses exact `combobox`/`Cliente` and
   `combobox`/`Prioridad` locators. Pagination, exact customer IDs, grouped intake,
   save/ACK barriers, conflicts and convergence assertions remain intact.
2. **The restricted-user case completes admission but fails a shared helper's
   unconditional synchronized-label assertion.** Its real second context has
   exactly `customers.write`, `orders.write`, `sync.pull`; the baseline page is
   empty. `test.trace` shows completed admission at `expect@189` and the failure
   at `expect@195`, receiving `Guardado localmente` instead of `Sincronizado`.
   Write grants do not imply reads, and this account has no push capability.
   The runtime deliberately avoids claiming synchronized readable state for
   write-without-read access. Only this caller now requests `local-only` status;
   the helper first proves missing `sync.push` and a write-without-read grant.
   All other callers, including read-only users, still require `Sincronizado`.
   The fixture also returns the server's user ID plus selected workshop so the
   unchanged identity/scope checks execute, alongside the full baseline checks.
   No grant is added or widened. Cross-user cache/draft assertions are unchanged.
3. **The transient-failure fixture supplies an invalid private response.**
   Its trace records `call@700` fulfilling HTTP503 with `{}`. The network entry
   contains only `content-type: application/json` and `content-length: 2`, with
   no `Cache-Control: no-store`. The production push transport requires both
   the private-response header and the closed, status-paired
   `temporary_unavailable` error envelope. Invalid responses become an integrity
   hold, which removes the operational form; the missing save confirmation is
   downstream of that hold. The fixture now supplies that exact closed envelope
   with no-store. Two failures, three identical immutable requests, backoff,
   dispatch counts, retained journal and authoritative convergence remain required.

These four failures demonstrate test-contract errors. They do not establish a
new production defect or prove that later browser steps pass. The separately
owned offline-reload and old-service-worker investigations remain independent.

## Negative coverage and verification

Three focused cases exercise the actual push transport plus coordinator:
valid private503 returns `RETRY_LATER`/`transient`; malformed503 and a valid503
without no-store each remain `HELD`/`integrity` and disable the session. Every
case retains the exact captured batch and produces no false acknowledgement.
Production response validation is unchanged.

Local checks on the corrected source:

- Frontend core runner: **482 passed, zero failed or skipped**.
- Focused push transport/coordinator: **8 passed** (included in that total).
- Web typecheck and strict TypeScript compilation of the three affected E2E
  specs: passed. The standalone E2E command explicitly supplies the installed
  Node type declarations; an initial ad-hoc invocation without them reported
  the pre-existing `Buffer` references, so it is not recorded as passing.
- Touched ESLint, Prettier and `git diff --check`: passed.
- Playwright collection: **27 tests in eight files**, unchanged. Collection is
  not browser execution.

Managed Chromium navigation restrictions remain in force; no local navigation
bypass was attempted. Native browser/SW/PostgreSQL execution, exact published-tree
CI, visual inspection and existing release/installation gates remain open on
separate evidence. No execution-state or release status is advanced here.
