# Increment B · isolated context/baseline reconciliation

Date: 2026-10-14. Base: actual published PR36 head
`0fe421dc9cde8ff132f078187da71b692ddae286`, tree
`fbf5e567` (abbreviated). This is isolated client-side support for the
[server cutover contract](../02-technical-architecture/2026-10-14-server-cutover-contract.md),
not production client activation. AGPL-3.0-only and DCO remain unchanged.

## Changes and invariants

- Closed live and historical context parsing requires explicit canonical lowercase
  UUID `dataset_incarnation`, exact policy `ocwp-access-baseline-2`, and exactly
  null or `baseline-v1` support. Configured API realm, current principal/scope,
  concrete grants, 43-character epoch and bounded lease checks remain mandatory.
- `VerifiedAccessContext.datasetIncarnation` and local
  `BaselineMetadata.datasetIncarnation` retain explicit provenance. Context
  identity includes incarnation and support. The latter metadata binds the
  retained original start, latest page/continuation, completion and checkpoint;
  no new fields are fabricated on server completion DTOs.
- Original start evidence is parsed by the live closed parser at its original
  verification time. It cannot renew the current lease, relax policy/epoch rules
  or reinterpret unknown provenance. Unknown-format/missing/mismatched proof
  remains in storage and cannot establish READY, ordinary reads or offline reuse.
- Unchanged-incarnation equivalent verification can reuse supported completion.
  A changed incarnation cannot reuse even an artificially repeated epoch. Original
  context/proof remains intact in the superseded partition. No migration/backfill,
  deletion, journal mutation, inferred authorship or cross-incarnation replay is
  introduced.
- Production App, production repositories/authentication and default v4 database
  are unchanged. C still owns journal provenance, command/overlay admission and
  recovery holds, ongoing deltas, production offline reload and application cutover.

## Local evidence

Observed before implementation: existing focused suite 109/109 passed; new
contract regression suite **7 failed, 2 passed**, including accepted provenance,
closed persisted policy, incarnation/support equality, nested context acceptance,
completion metadata, old internally consistent proof and reuse boundaries.
After implementation and added composition coverage:

- Frontend core: **335 passed, 0 failed, 0 skipped**. This compiles all eight test
  projects, including the isolated native harness.
- New focused cutover suite: **10 passed**, including real client adapters and
  coordinator using explicitly synthetic DTO fixtures. Synthetic fixtures are
  not server-advertisement evidence.
- Root ESLint, touched Prettier, web TypeScript, offline TypeScript,
  production Vite/PWA build and isolated Vite harness build passed.
- Actual B FastAPI HTTP plus fake IndexedDB: passed with the coordinating task's
  disposable SQLite fixture, genuine `cutover_enabled=True` and separate floor-1
  organization `...000101`/location `...000102`/user `...000103`. The exact new
  `openSupportedBaselineQualification` harness traversed five ordinary coordinator
  steps, ingested a direct-REST historical customer, reached READY, and reused the
  same completed partition after equivalent verification. Actual context/start/
  activation agreed on supported protocol, policy and incarnation. No response
  rewriting, credential persistence or journal writes occurred.

The actual-HTTP run is functional evidence using emulated storage; it is not
native browser, PostgreSQL locking, installation activation or production proof.
Its server code/fixture came from the coordinating B worktree, rather than the
pre-B server retained in this frontend-only base. Final integrated exact-tree
qualification belongs to the coordinating task.

## Native test and remaining qualification

The separate native case in `baseline-browser.spec.ts` uses the genuine supported
fixture and ordinary adapter/coordinator. The original floor-0/null staging and
refusal journey is retained. Only the separate test harness entrypoint imports
these helpers; production imports are unchanged. Test traces remain disabled for
actual-auth cases so bearer material does not enter traces.

Local native execution is **blocked before test execution**: the Playwright
bundled Chromium executable is absent, and the available system Chromium aborts
on `socket() failed: Operation not permitted`. No permission bypass or browser
installation was attempted. The actual B server and Vite started successfully.
The native case is compiled and built, but still requires exact integrated-head
hosted Chromium evidence. Independent source review at
`86e8fad1403119c0460c45795a574c7c1dbff32d` (tree
`99dbdb3cf33f8af994612f00f2e30a775048f986`) found no remaining blockers and
independently passed335 core tests plus type/lint/format checks. PostgreSQL,
old-bundle/service-worker, C production journeys, physical-device and installation
gates remain open.
