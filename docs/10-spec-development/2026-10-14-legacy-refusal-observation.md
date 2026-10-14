# Exact old-client protocol refusal: observer correction

## Scope and original evidence

The first PR38 hosted head `b9da73fa7c764b7a3592688db7199e77457e44a0`
(tree `0b5bd4e399dd577b879f2f2a8c7bf524f54cccc6`) timed out at
`legacy-client-upgrade.spec.ts:125`, reading the old client's real HTTP409 body.
The response waiter had already resolved. The current-distribution switch and
SW update were never reached. The pinned old transport throws on non-success
status without consuming its response body; Playwright's body observation did
not finish. The trace supports this observation failure, not a proven
browser-internal cause or a successful full upgrade journey.

The direct artifact SHA256 is
`6452551f5d67241171709f85ba69b61ff53018d6a212fdc54430f2244d713b88`;
the nested old-client trace SHA256 is
`25d4bf268fba9bb1c7b14612daaafd3e4b69e8f98bb72544b1ca4e01a5e8315b`.
It identifies Playwright 1.62.0/Linux Chromium. The archived spec exactly matches
source `1aa21364c1ded9b3a3b5dfa1caaa8d4b012eebc8`. It records real 401 and
409 responses and identical raw legacy DB snapshots after offline creation,
reload and the 401, containing one customer and one pending mutation.

## Correction and preserved invariants

Only the E2E spec, its loopback proxy and focused tests change. The proxy observes
the existing upstream response while forwarding its original status, headers and
bytes unchanged. It never reissues the mutation, substitutes a response, changes
page fetch, or modifies the actual old App/SW. The browser still must observe a
real POST409 from the exact mutation URL.

A fixture-only GET supplies the same response's validated request ID, method,
path, status and allowlisted `client_upgrade_required` code. The assertion compares
all five against the actual browser response and expected code. Missing, pending,
invalid, duplicate and ambiguous records fail closed. No authentication headers,
request bodies, tokens, arbitrary error text or full response bodies are retained
in the evidence records. Temporary parsing is bounded to 4 KiB per response and
32 unique eligible request IDs; capacity exhaustion invalidates the complete set.

Content type/encoding, valid request ID, declared/received byte agreement and
complete upstream response are mandatory. An incomplete or malformed body cannot
become evidence. Reading the evidence endpoint cannot forward another API call.
The test-only proxy accepts explicit temporary synthetic asset paths and an
upstream loopback port for HTTP regression tests; normal startup retains its exact
historical/current build directories and backend port.

All legacy DB equality, queue counts, old-SW control, real new-SW activation,
late-old-tab additions, authenticated-DB isolation, recovery, theme, accessibility
and screenshot assertions remain. The 120-second test timeout and zero-retry
forward-only tenant policy are unchanged. The original historical source, tree,
lock, builder and asset provenance are unchanged.

## Local evidence and limits

The new real-loopback contract was observed RED: the browser-side response
received HTTP409, but the unmodified proxy exposed no correlated evidence.
After correction, **18 focused tests pass**. They include an intentionally unread
downstream body, byte/header/status pass-through, single forwarded mutation,
wrong method/route/status, closed code validation, malformed/oversized bodies,
missing/duplicate IDs, pending/truncated responses, in-flight duplicate races and
bounded-capacity refusal. Six guard-removal mutations independently turn their
corresponding negative tests RED; restoring the guards returns GREEN.

Full frontend core: **496 tests pass**; API-client core: **1 test passes**.
Web/offline types and the touched E2E spec's strict compile pass, alongside
ESLint, Prettier and whitespace checks. The E2E compile uses installed host Node
types; it is a static check, not browser execution. The root `pnpm test` wrapper
refuses the temporary symlinked dependency directory, so the existing core test
runners and Python suite are invoked directly without installing dependencies.

The first direct full Python run against that historical shared environment
reported **1,632 passed, 194 skipped, 11 failed**. All failures are the dependency
security regression file: four PyJWT hardening cases, six malformed-Host cases
and the request-path authority case. Its installed Starlette 0.52.1/FastAPI 0.128.8
predate the current locked remediation (Starlette 1.3.1). The shared environment
was not modified. A subsequent full rerun with the already-qualified read-only
FastAPI 0.133.1/Starlette 1.3.1/PyJWT 2.15.1 environment and pinned Gitleaks binary
passed **1,648 tests**, with **189 explicit PostgreSQL skips**. Import location was
verified against this worktree. The initial failures therefore remain recorded
as a stale-environment result; the corrected local suite is green. Hosted
PostgreSQL and native-browser qualification remain required.

Independent review of source commit
`280391e15c70605bb3b8f5cd06da27494c4363db` (tree
`07cea6a882e3a513cf83057849aec43a6f468dc7`) found no actionable correctness or
security issue. It independently reran all 18 focused tests, touched static
checks, web/offline types and strict E2E compile, and mechanically confirmed all
other old-client acceptance code and historical build inputs remain unchanged.
The later documentation update records completed evidence only; the reviewed
three executable/test files are unchanged.

Hosted execution of the complete original journey is still required. Synthetic
HTTP observation tests do not prove native service-worker takeover, old-tab late
writes, recovery UI or PostgreSQL behavior. No browser was attempted locally,
no production source or installation changed, and no remote mutation occurred.
