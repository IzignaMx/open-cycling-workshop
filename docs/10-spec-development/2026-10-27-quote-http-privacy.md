# Quote HTTP namespace privacy prerequisite · 2026-10-27

## Status and normative scope

Implemented and independently reviewed; PR62 is merged as `a960bdd`, with
independent fresh postmerge [CI40571345621](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40571345621)
acceptance for this bounded source scope. This
is a bounded Tasks 5/8 prerequisite, not quote endpoint activation or completion
of V0.1, Task 5, Task 8 or the quote lifecycle.

The accepted [online-command boundary ADR §§5.1–5.2](../02-technical-architecture/2026-10-15-quote-persistence-and-online-command-boundary.md)
requires private no-store responses, server-generated correlation IDs, bounded
errors and no evidence/free-text/raw-input logging. Traceability: FR-SVC-005/007/
008/009/016, BR-004/005/006/007, OFF-005/008/009/012, SEC-002/003 and NFR-009.
This increment addresses privacy prerequisites only, not every criterion under
those IDs. No new ADR changes architecture or the accepted numerical budgets.

Before work, the cleanup checkpoint was completed: PR52–55 were exact integrated
ancestors through PR57; unique failed diagnostic PR51/56 work was preserved in
[PR61's inert exact-diff archives](archived-diagnostics/README.md), then closed.
PR61 merged as `993ac6cbf7558ad1b497198a35fc5d174a370bf4`, tree
`e60753f89d135e14a2a6ccf64617e7e47cc68840`. Open-PR API pages 1 and 2 both returned
empty at 2026-10-27 18:06 UTC, recorded in [PR61](https://github.com/IzignaMx/open-cycling-workshop/pull/61).
No branches were deleted or failed profiles relabelled. This is the new source
base; PR61's passed candidate evidence is not inherited qualification here.

Fresh main993ac6c [postmerge CI 40556696239](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40556696239)
then passed independent terminal review: 27/27 controls, 4,794 collected / 4,736
passed / 58 exact expected skips, all eight PostgreSQL cases and six restores
all phases, both serial primary/independent owned-absence proofs and strict
source/ordered/disjoint collection. Direct/aggregate browser each86/86 retry0,
repeats20+9+5+10 and kernel14 clean. Security/runtime/native ARM/containment passed;
optional QEMU remains failed NON-QUALIFYING. Full-Python artifact12760685080
SHA-256 `c727416f1b13106d05462357b7d453c2af5e2b8f7f484fdadf54c74ab5aa00a7`;
qualification12761866707 SHA-256
`7f675467048225a5f106a712f146fac6564379dc146d71dc6ad557646d1c7f18`.
This closes the source baseline, not this new privacy tree or external gates.

## Invariants and boundaries

- Recognize only direct `/api/v1/quotes[/…]` and nested
  `/api/v1/service-orders/{one nonempty segment}/quotes[/…]` namespaces. Do not
  treat similarly prefixed unrelated resources as quote operations.
- Application responses in those namespaces, including currently unmounted
  404s and malformed/error paths, receive no-store and a generated request ID,
  never the caller's arbitrary `X-Request-ID`.
- Quote validation/HTTP/API errors have fixed bounded safe bodies, no arbitrary
  input, nested validation locations, exception details or supplied headers.
  Existing generic/identity/inventory/branding behavior remains separately tested.
- Router-generated 405 responses retain only bounded normalized standard-method
  `Allow` tokens; arbitrary exception headers remain suppressed. This preserves
  method semantics without echoing supplied evidence.
- Classification uses the actual once-decoded ASGI `scope["path"]`, not a URL
  reparse that would truncate encoded `?`/`#` within nested order identifiers.
- Redaction happens only at logging boundaries. Routing, ASGI query bytes and
  proxy forwarding remain unchanged. Uvicorn decodes path once and re-quotes
  access records; Caddy sees the original URI. Do not recursively decode input
  or interpret a source-regexp check as actual proxy runtime evidence.
  Both Caddy configurations omit caller `X-Request-Id` from log encoding globally,
  without removing/rewriting it in forwarded requests or defining an edge ID.
  Other runtime log fields and unrelated query strings remain available.
- No quote router, body adapter, service call, OpenAPI/TypeScript DTO, frontend,
  catalog grant, migration, schema floor or real account change is introduced.

## Evidence and honest limitations

| Scope                                | Observed local evidence                                                                                                                             |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| App privacy baseline                 | RED 28 failed / 7 passed; first minimal GREEN 35 passed.                                                                                            |
| Real Uvicorn access filter           | RED 2 failed (missing filter and actual leaked query); corrected combined quote/inventory privacy/logging suite 55 passed.                          |
| Decoded nested `?`/`#` identifiers   | RED 2 failed before switching to actual ASGI scope path; corrected regressions pass.                                                                |
| Router 405 semantics                 | RED 2 failed / 4 passed before safe bounded `Allow` retention; corrected regressions pass.                                                          |
| Final quote privacy/logging          | 47 passed; real loopback HTTP, fixed errors, exact/encoded paths and unchanged forwarding covered.                                                  |
| Edge configuration/probe contracts   | Config RED 8 failed / 2 passed, probe RED 2 failed / 5 passed; final combined 56 passed. Deterministic source/guard tests, not Caddy runtime proof. |
| Broader API regressions              | 738 passed / 186 explicit local-environment skips / 3 warnings, before final 405 correction; not final full-suite acceptance.                       |
| Full final Python                    | 4,181 passed / 671 explicit local-environment skips / 12 warnings, 339.44 s; no failure/error. Collection 4,852 = 4,794 baseline + 58 new.          |
| Independent final review             | No source blockers; 126 focused plus 182 existing auth/context/branding checks passed, with existing warning.                                       |
| Frontend available regression checks | Web core 934 + API core 1 passed, zero skips; both TypeScript checks, ESLint and repository-contract Prettier glob passed.                          |
| Static/contracts                     | Ruff check/format 323 scoped files; mypy 123 sources and strict edge-probe mypy; OpenAPI/generated TypeScript unchanged.                            |

Counts overlap and are not summed as unique coverage. Existing Starlette/httpx
warnings remain. Full-suite raw log SHA-256:
`5de31e128b9e570a723c848039e2d8ab190dc697ae9db764c69efb395b5641dd`.
Independent review checked all thirteen changed source/test files, safe 405
method semantics, source contracts and no new reachability. Final document/package
review and fresh hosted proof remain separate. Synthetic test-only routes are
not production endpoint exposure.

The preceding archive preflight had 672 local skips before frontend dependency
links existed; this run has 671. The unchanged report-only Playwright privacy
test is now runnable: isolated missing-package reproduction skips it, linked
dependencies pass it. This explains the environment-dependent count difference,
not a relaxed skip rule. The older verifier retained only its last 4,000 output
characters, so no complete retrospective baseline skip-identity trace is claimed.
Hosted policy remains exactly 58 expected skips and needs its own fresh proof.

Real Uvicorn loopback and the existing actual Caddy probe must distinguish
observed runtime redaction from local deterministic/source assertions. Both
supported edge configurations, encoded aliases, unexpected/handled failures,
private header/query canaries, unchanged forwarding and unrelated controls are
required. Local Docker/PostgreSQL/native browser availability is not assumed;
hosted normal source-bound checks remain mandatory.

The existing Caddy backend policy already adds no-store, including upstream
502/503. An edge-generated upstream failure has **no application request
context**; this increment does not claim an established server-generated
correlation-ID policy for those proxy-local errors. That transport gate remains
open. Do not overwrite application IDs or silently change forwarding to create a
false all-boundaries claim. Malformed/incomplete percent escapes rejected by the
edge HTTP parser before routing likewise have no proven private-header/logging
acceptance here. No speculative regexp broadening claims to qualify that path;
valid encoded separators and literal encoded-percent identifiers are tested.

No quote authentication adapter or typed `WWW-Authenticate` challenge contract
is activated/qualified by synthetic 401 privacy tests; arbitrary supplied error
headers remain suppressed. Those semantics belong to the future typed adapter.

No streamed-byte enforcement, compressed-body admission, async body adapter,
synchronous Python/DB cancellation, total command/cleanup cutoff, COMMIT-unknown
semantics, capacity/latency or endpoint/client journey is qualified here.
Resource/security containment, retry policy and consumed capacity experiments
are unchanged. Physical R01-T035 Windows/Android/laptop/Pi/manual accessibility,
real-installation inventory, isolated corruption, actual-volume restore/RPO/RTO
and mixed-old-writer rollout/real grant adoption remain separate open gates.
No installation, reopening, deployment or quote activation was performed.

## Fresh postmerge source reconciliation

PR62 merged as `a960bddb94189c6c74c7f3d0a72472636c3caced`. Fresh CI
`40571345621` was independently reviewed: 27/27 aggregate controls, 4,852
collected / 4,794 passed / 58 exact expected skips, eight PostgreSQL cases and
six restores across phases, and both owned cleanup proofs. Direct and aggregate
browser runs each passed 86 cases without retries; repetitions and kernel proof
passed separately. Actual Caddy evidence for both configurations preserves the
private headers/logs and unchanged forwarding/unrelated controls. Qualifying
Security, runtime and native ARM companions passed; optional QEMU failed and
remains NON-QUALIFYING. No failed diagnostic is reclassified or rerun here.

This closes only this source-privacy evidence gate. It does not qualify body
streaming, total Python/database cancellation, malformed-wire behavior,
proxy-generated correlation IDs, maximum capacity, real grants, installation,
physical acceptance or quote activation. Earlier pending statements are retained
as historical stages, not the current postmerge result.
