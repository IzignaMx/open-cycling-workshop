# Order transition attribution · 2026-11-08

Status: **locally verified and independently reviewed; unpublished; hosted qualification pending**.
Base main `3534fdd59f219bdcd4943aded4b86f7883b0d382`, tree
`5c6491a66fc4df029f57edb17cd46f2cf269db75`.

## Scope and requirements

The user requested continued development toward a real multi-user workshop,
including visible author attribution. This increment exposes existing order-event
author identifiers, recorded dates and source in the existing history view.
Follow the [design](../superpowers/specs/2026-11-08-order-transition-attribution-design.md).
FR-SVC-016/R02-T013 remains partial. This does not implement assigned mechanics
(FR-SVC-004/FR-STF-003), staff workloads, full audit history or author-name lookup.

The presentation distinguishes local records from server records. Local history
includes original attempts regardless of delivery outcome, so it cannot imply
pending or accepted status. Recorded time may originate on the client. Preserve
the existing scoped/current-session reads, partial/offline messages, event-ID merge
and normal string ordering. No extra request, capability, API, persisted schema,
journal mutation, dependency or workflow is introduced.

## Accepted baseline, not new candidate proof

[PR96](https://github.com/IzignaMx/open-cycling-workshop/pull/96) was merged and its
fresh main [CI42459836502](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/42459836502)
passed: aggregate 27/27, Python 6,696 plus 58 intentional skips, frontend 1,356/API
one, direct and aggregate browser 136/136 each, all cases single-attempt.
Repetitions 20/9/5/10 and kernel 14 passed. All ten main checks/four workflows
passed on attempt one. Source, coverage, container cleanup and artifact byte/digest
receipts were independently checked. Structured browser reports were inspected,
not screenshots/videos/traces; build-resource cleanup was not assessed.

That exact-source receipt supersedes historical customer-edit publication/CI
pending entries only for accepted main. It does not qualify this new increment.

## Local preflight

The clean checkout was advanced to the verified main before selecting the new
branch. Frozen dependency installation succeeded without lockfile changes.
Baseline aggregate: partial, exit 0 with --allow-blocked; 16 passed, zero failed,
eight blockers. Python 6,069 passed/685 environment skips/12 warnings in 371.46s;
frontend 1,356 and API one passed, zero skips. Three reported static-tool blockers
came from the local PATH, not missing packages; the final run exposed the
already-installed .venv Ruff/mypy executables and passed those checks. Other blockers: PostgreSQL, Docker,
psql, managed Chromium navigation and the dedicated E2E database.

## Candidate implementation and focused verification

The implementation retains the existing actor and timestamp fields and adds only
an ephemeral read-time source projection. Rendered identifiers are complete, with
control/format characters treated as unavailable and valid RTL text isolated using
`bdi`. Original records are not rewritten. Explicit-zone calendar-valid timestamps
retain their original precision and offset; ambiguous/invalid values are unavailable.

Observed RED preceded GREEN for actual OrderList rendering and controller tests.
The final focused run passed 47 cases: 39 actual OrderList SSR cases and eight
runtime history cases. Independent review passed those 47 plus 17 transport cases
(64 total), TypeScript and whitespace checks. Review findings concerning bidi
control characters and hidden browser assertions were corrected and re-reviewed.
The final browser assertions explicitly open the history and verify each displayed
author/source, rather than relying only on counts inside a collapsed element.

Retained tests are `apps/web/tests/orders/order-history.test.mjs`,
`apps/web/tests/runtime/order-history.test.mjs`, and the existing
`apps/web/e2e/order-lifecycle.spec.ts` journey. The existing backend invariant tests
remain in `services/platform/tests/service_orders/test_state_machine.py`.
Coverage includes source spoofing, collisions, distinct similar records, immutable
journal/source data, two actors, malformed values, offline reload, rejected/held
attempts, remote failure and session/read-scope fences. No backend change was made.

The affected two browser journeys were collected and typechecked, not executed.
Actual local browser/PostgreSQL execution remains blocked. No result is inherited
from the accepted base.

## Final local qualification

The final aggregate against frozen production/test sources completed with
`--allow-blocked`: **partial, 21 passed, zero failed, five environment blockers**.
Python: **6,070 passed, 685 environment skips, 12 warnings, 377.83s**. Frontend:
**1,403 passed, zero skipped**; API client: one passed. Runtime HTTP smoke, repository
contract, OpenAPI/generated types, frontend/API TypeScript, Ruff, formatting, mypy
(126 files), ESLint, Prettier and both PWA builds passed. No lockfile changes were
needed. Compared with accepted main, 47 frontend cases and one repository contract
were added and executed locally.

The five blockers are PostgreSQL integration, Docker CLI, PostgreSQL client/server
tools, managed Chromium navigation for the IndexedDB probe, and the dedicated E2E
database. No policy bypass or substitute browser qualification was attempted.

The full run precedes the final evidence-only documentation stamp; production and
test hashes stayed frozen. Aggregate metadata records the base HEAD because the
candidate was still uncommitted. Its result describes this working tree, not the
unchanged base commit. After the evidence stamp, all 197 repository tests and
format checks passed; the affected browser file again typechecked and collected
two journeys without executing them.
Any later hosted qualification must identify and exercise the actual published SHA.

## Boundaries

No publication authorization exists for this increment. A later approved PR needs
its own hosted/browser/PostgreSQL proof and, if merged, fresh main verification.
Physical T1–T8/R01-T035 remain omitted by user request, not accepted. V0.1 remains
partial; M2/capacity, deployment and real-data restore are not authorized.
SPENT40927223929 and UNKNOWN41011497919 remain unchanged. No real customer data is
used, and no notification provider, user-directory lookup or external message is
introduced by this display increment.
