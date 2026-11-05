# Autonomous tests: workshop read boundaries

## Scope and requirements

The current request defers physical T1–T8 and asks for useful autonomous tests.
It does not accept those gates or authorize deployment, capacity, M2, quote
ingress or a new release. V0.1 remains partial and R01-T035 remains open.

This bounded correction follows an actual synthetic reproduction against accepted
main `9356d467bde4750b57bb2115d2c56c9944f7188e`, tree
`ed606d591f1f9153264f8f4993064904f2ad5ee1`. It hardens the already shipped workshop
reads under SEC-002, FR-IAM-004, canonical R01-T029, Foundation ADR-013 and Phase 3
sections 8/13. It adds no feature breadth or architecture decision.

## Reproduced failures and smallest correction

A real signed session, with both its persisted account and token restricted to
one location, could read another location's bicycle and private notes through
`GET /api/v1/customers/{id}/bicycles`. The customer was accessible, but the nested
query did not constrain each bicycle's location. Direct foreign-location reads
already called authorization, but leaked the expected PermissionError to HTTP
as a generic 500 rather than a deliberate denial.

- Add the effective principal's optional location to the bicycle query. Apply
  its SQL predicate before the effective LIMIT; retain tenant/customer predicates,
  stable ordering, limit and organization-wide visibility.
- Translate only expected authorization PermissionError to 403 at five existing
  read handlers: customer, bicycle, order, order events and customer bicycles.
  Preserve same-location 200, foreign-tenant 404 and capability/session checks.
- Mark the exact customers, bicycles and service-orders namespace roots and
  descendants no-store for every response, including writes, errors and redirects.
  Classify the decoded ASGI path without additional decoding, independently of
  Host/raw_path. Prefix lookalikes and public paths retain their prior behavior.
  Existing unexpected-error sanitization now also protects these responses.

No schema, migration, payload, role, session, dependency or persistence change.
No-store governs HTTP caches, not Dexie or the durable mutation journal. Workbox
does not configure an API runtime cache and excludes API navigation fallback.

## Tests-first and independent review

- Authorization regression RED: seven failed / eleven passed before correction.
  Final retained matrix: 25 passed, including persisted-only, token-only, both
  restrictions, contradictory scope, tenant isolation, mixed-location listing,
  organization-wide access and filter-before-limit.
- Privacy regression RED: 52 failed / seven passed before correction. The 59-case
  retained matrix covers successful reads/writes; 401/403/404/405/422/500/503;
  307 redirects; encoded namespace and separator; malformed Host; safe errors;
  unknown descendants and unrelated routes.
- Privacy plus existing identity/dependency tests: 164 passed. Independent final
  review reran 175 cache/authorization/identity cases and 18 direct ASGI probes.
  No blocking finding. Expected-denial mapping does not mask unrelated exceptions.
- The first broad run reported three failures, 5,761 passes and 671 environment
  skips. Its three older quote tests treated nonquote service-order descendants as
  cacheable. They remain nonquote paths, but now explicitly require no-store while
  retaining unchanged payload/query/request-ID assertions. No quote classifier or
  ingress changed. Independent classification probes and 65 quote/inventory
  privacy/logging cases passed. The full suite passed after this repair, as below.

These are synthetic HTTP tests with real authentication dependencies and SQLite,
not PostgreSQL concurrency, deployed reverse-proxy or physical-device evidence.

## Additional offline evidence

36 deterministic tests passed against actual compiled kernel code and
Dexie/fake-indexeddb, without changes to that code:

- 24 seeded incremental-sync scenarios: 384 accepted pages, concurrent duplicate
  pairs and exact replays; 360 stale-response refusals; 96 late transaction quota
  aborts followed by reopen checks. An independent maximum-version/cursor oracle
  held throughout.
- 12 capture scenarios: 96 eight-writer races, 768 save attempts and exactly 96
  accepted writes; 96 late quota rollbacks; protection/settlement races; preserved
  TTL and wrong-receipt refusals.

The executable probes, commands and output are retained in ignored local
`artifacts/autonomous-offline/`. Close/reopen stays in-process; injected quota
errors do not prove native storage eviction, disk durability or power-loss recovery.

## Verification receipt

Frozen dependency installs completed without lockfile changes. Local versions:
Python 3.13.5, Node 24.22.1, pnpm 11.25.0. These are not the hosted tool receipt.
Final local Python: 5,765 passed, 671 environment skips, 12 warnings in 361.44
seconds, exit zero. Production and regression source preceded that full run;
only this final documentation receipt followed. Repository 191 and focused
authorization/privacy 84 passed and are rerun after the receipt.

Frontend 1,299 and API-client one passed with zero failures/skips. Full Ruff,
ESLint, Prettier, mypy (124 source files), TypeScript/web/offline types,
OpenAPI/generated-client contracts, repository contract and PWA build passed.
The existing chunk-size warning remains. Disposable probe outputs initially
entered ESLint's scan; moving those generated files into existing ignored
`.tmp-*` locations restored the source-only check without changing lint policy.
Both offline probes passed again after relocation.

New exact-source hosted qualification remains pending; accepted PR90 evidence
cannot substitute. No publication or merge of this candidate has been attempted.
Local logs are under `artifacts/autonomous-20261105/`; they are not public downloads.

The documented isolated native-kernel command was attempted with the installed
Chromium. Its fixture build succeeded, but browser processes aborted before
assertions because socket creation was not permitted and crashpad initialization
failed. The run was interrupted after observing that restriction, exit 130, with
no complete report. No native pass, security-setting change or manual retry is
claimed. Docker/PostgreSQL services are unavailable locally; their skipped tests
remain unverified for this candidate.

## Accepted PR90 baseline

[PR90](https://github.com/IzignaMx/open-cycling-workshop/pull/90) merged as the main
SHA above. [CI 41969020058](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/41969020058)
passed aggregate 27/27, Python 6,293 plus 58 exact skips, frontend 1,299, API one,
browser 133 direct and 133 aggregate, repetitions 20/9/5/10 and isolated kernel 14.
Expiry completed ten single-attempt passes. Runtime, Security and microfixture
also passed on that exact main. Bounded receipts were independently validated;
large browser archives, traces and screenshots were not inspected.

This closes PR90 hosted acceptance and preserves its initial failed CI41958483575.
It does not qualify this changed source. Physical T1–T8/R01-T035 and operational
acceptance remain pending, now deferred for this autonomous testing pass.
SPENT40927223929, UNKNOWN41011497919, capacity, M2 and Pages remain unchanged.
