# Shared workshop branding · source and evidence boundary

Date: 2026-10-14. Status: implemented, exact integrated hosted qualification pending.
This is a bounded MVP increment, not full MVP or production certification.

## Inherited baseline

This increment starts from merged main39
`eef9559d8c3e528e79c99898360892188b23b55e`, tree
`1640101f9af5cd278e8a71f8392444502d7f5ce2`.
Its separate postmerge evidence is complete:

- [Aggregate CI](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38649053162):
  27/27 controls, 1,825 Python passes/12 explicit skips, 662 frontend tests,
  11 native kernel tests, 43 direct and 43 aggregate browser cases, plus 20+9
  retry-free repetitions. Artifact SHA256
  `660768d3b41472ea817be3f8dd9705ca6988ee8941be580ce39022d81cd46aa6`.
- [Disposable runtime](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38649053150):
  eleven controls, authenticated isolated restore and three ARM64 cross-builds.
  Artifact SHA256 `b2a40196fdb72f8192024993190ad3c7609c61ac300fa5a4ddfc81de19644c2c`.
- [Security](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38649053154):
  220 content commits, 10,967,193 bytes, forty packages, zero findings and seven
  scanner canaries. Artifact SHA256
  `837e70ea9c9db196f0723bb635f4cf10ea59921e5d1a5e96782e89c7737adc5b`.

These results qualify that inherited source only. They do not qualify the changes
below. Older administration candidate-failure notes remain historical diagnostics,
not unresolved main39 failures.

## Implemented scope

The [ADR](../02-technical-architecture/2026-10-14-shared-workshop-branding.md)
freezes compatible v1/v2 catalog semantics, explicit-only grants, personal
inheritance, independent profile authority, canonical PNG limits, private durable
assets and exact admitted offline cache ownership. SQL head is 0011; authenticated
local schema is 7; future quote reservations are SQL 0012/local 8. Existing operational
policy remains `ocwp-access-baseline-2` with unchanged prior effective authority.

The [recovery procedure](../07-operations/2026-10-14-branding-recovery.md)
covers same-snapshot database-plus-assets bundles, fresh targets, exact byte
validation and quarantine on partial failure. Mixed-floor tenants are all
preserved. Default refusal precedes target changes; explicit legacy transition
requires the exact complete tenant/incarnation list and separate prerequisites.
No real grants, accounts, installation cutover, recovery or deployment was performed.

## Executed local evidence

The implementation qualification completed 21 executable controls successfully;
five controls reported explicit environment blockers. Its source metadata is
`55b6535ca3202ca7344c389cdca8ab0c3621b671`, with the final reviewed settings-anchor
and strengthened PostgreSQL ordering test changes present in the working tree
(subsequently committed in `7fb7fe5`). Because implementation and documentation
were still being finalized, this is an implementation checkpoint, not an exact
final clean-commit certificate.

- Full Python: 1,865 passed, 224 explicitly skipped, three dependency deprecation
  warnings. PostgreSQL-dependent tests did not run.
- Frontend core: 715 passed, no failures or skips; API-client core: one passed.
- Repository checks, SQLite-surrogate real HTTP smoke, offline and API-client
  TypeScript checks, generated OpenAPI/TypeScript drift checks passed.
- Ruff, Python format, mypy (99 source files), ESLint, Prettier, current PWA build
  and pinned legacy App/service-worker build passed. Whole-app TypeScript also
  passed separately after fixing this worktree's external dependency links.
- Pillow 12.3.0 is pinned in `uv.lock`. The isolated frozen dependency environment
  includes it; no other worktree's dependency environment was changed. The
  [decoder/storage evidence](../03-security-privacy/2026-10-14-branding-image-storage.md)
  records 41 active Linux packages with zero known audit findings, actual x86_64
  child decode timing/RSS, timeout/kill/reap and filesystem fault/race tests.
- Recovery correction tests: 156 passed, three PostgreSQL skips; independent
  combined backend/asset/recovery review tests: 419 passed, thirty PostgreSQL
  skips. These overlapping focused counts are not added to the full-suite total.

The aggregate JSON is retained with the implementation handoff. Later exact-head
coordinator and hosted reports must identify their own commit/tree and results.

## Independent source review

Frontend/runtime/cache/preference/admin review found and reproduced two lifecycle
issues: current editor 403 did not retire operational admission, and a delayed
older response could overwrite a newer accepted profile after asynchronous
validation. Both were fixed and independently rerun. The settings navigation
anchor was also corrected to its unconditional target. Final review: 175 targeted
passes, seven independent adversarial tests, five isolated TypeScript builds and
23 exact product-source hashes; no remaining source finding. Manifest SHA256:
`5ac93796dc2256dbfc2a10de22215b02f831f42cd18bdbf336c114f5b2c32c94`.

Backend/asset/recovery review covered through `55b6535` and strengthened ordering
test blob `814d91f5666fd6dad4edfd628b89bced800fa53b`. It closed nested-directory
fsync, unsafe recovery path/file ownership, complete mixed-floor recovery and
atomic activation-incarnation consent findings. The CI wrapper now requires two
fresh distinct safe recovery proofs, floor 1 and mixed-floor, with activation
counts 0/2 and incarnation rotations 2/3. Final review found no remaining blocking
source issue. Reports and exact source manifests are retained with the handoff;
source review is not native runtime proof.

Two bounded qualification-source additions followed that implementation checkpoint:
the QEMU image probe (`d879bc8`, 34 helper/mock tests) and the named-volume Compose
probe (`c29cf4a`, 40 focused tests; the complete operations suite passed 213 with
three explicit PostgreSQL skips). Both retain separate authored/runtime evidence
boundaries. These counts overlap other focused runs and are not added to the
full-suite total. Final independent review and exact-source handoff accompany
these additions; no container execution is inferred from the mocked tests.

## Authored or collected, not locally executed

- Browser suite: 63 cases collected, including twenty branding cases. Four-theme
  desktop/tablet/320px, light/dark, 200% CSS enlargement and forced-colors coverage
  includes 36 labelled synthetic-logo captures requiring actual pixel review.
- Native access-kernel suite: fourteen cases collected, including three new
  schema 6→7/cache/admission cases. Fake IndexedDB is not native-browser evidence.
- Real PostgreSQL tests cover migrations, both authority lock orders, expiry while
  blocked, coherent read-first logo bytes and independent tenant progress.
- `bash scripts/ci/run_branding_recovery.sh` requires disposable PostgreSQL 18.4,
  both restore variants and authenticated returned-logo byte checks, plus corrupt
  latest-generation refusal, earlier recovery, stale token/checkpoint rejection
  and explicit old-client refusal. It does not publish dump/logo bytes as CI artifacts.
- The disposable Compose runtime adds a separate synthetic branding actor and
  named-volume save/read, API restart/persistence and fresh database-plus-assets
  restored-byte probe. The original wildcard actor, eleven runtime checks and
  browser recovery handshake remain separate. These authored checks require
  actual Docker execution; source and mocked orchestration do not prove durability.
- The [ARM64 probe](../07-operations/2026-10-14-branding-arm64-probe.md) loads the
  actual API image under QEMU and checks installed architecture, non-root identity,
  unchanged decoder limits, exact pixels and metadata removal. Only bounded JSON
  tied to source SHA and image ID is uploaded. QEMU failure is not retried with
  weaker limits. Emulated execution, cross-building and native Raspberry resource
  qualification are distinct evidence; none establishes physical-device behavior.

Local blockers: no configured PostgreSQL test/E2E URL, no Docker or PostgreSQL
client/server tools, and managed Chromium navigation restrictions. No browser
policy bypass was attempted. Hosted exact-source tests, actual screenshot review,
physical Windows/Android, screen readers, glare and realistic recovery capacity
remain open. Public contacts and profile interchange remain follow-on scope.

## First hosted candidate and bounded corrections

The initial draft [PR40](https://github.com/IzignaMx/open-cycling-workshop/pull/40)
published head `2813dc7c98b31092bb597bbe543a41dccf75ded5`. Its tested merge
`eb4a31b55af4ef1a698daf58762da41c01b8b78b` has tree
`416f0737d677b2c810af7be302facee03fe9340e`, identical to the local implementation
checkpoint. This run provides partial evidence, not a passing candidate:

- [Security](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38655209041)
  passed: 248 content commits, 12,147,729 bytes, 41 active packages, zero findings
  and seven canaries.
- [Disposable runtime](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38655208868)
  passed its original checks and actual named-volume API save/read, source restart,
  database-plus-assets restore, restored restart, exact profile/byte comparison
  and stale-token refusal.
- The actual loaded ARM64 image ran under QEMU, but the decoder qualifying attempt
  failed with `decoder_unavailable_under_emulation` after 2.009593 seconds. Its
  unchanged wall limit is two seconds. This coarse result does not distinguish
  cold startup, imports, decode, resource-limit refusal or signal exit. ARM runtime
  qualification remains failed; native Raspberry behavior is not established.
- [CI](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38655209127)
  passed 2,140 Python tests with fourteen explicit skips. Both dedicated PG18
  recovery cases then failed in pytest fixture setup because the clean checkout
  lacked the parent `artifacts` directory. The clients correctly reported 18.4;
  neither recovery scenario reached its assertions.
- Consequently, direct kernel and browser steps were skipped. The independent
  aggregate passed 25 of 26 controls; browser journeys failed before launch because
  their skipped install step left Chromium absent. The downloaded artifact has 125
  missing-executable contexts across 63 cases and no PNG captures. These are setup
  failures, not executed UI or visual qualification.

The correction prepares only the artifact parent, validates its ownership and
ancestor chain, preserves existing modes and refuses unsafe parents or a
substituted basetemp before pytest cleanup. The two-proof validator is unchanged.
The ARM probe now retains original-attempt timeout/exit/spawn/CPU evidence and may
run one explicitly supporting phase diagnostic with the same bounds. Instrumented
second-child timing cannot prove the original bottleneck; its outcome cannot
replace the original failure or exit status. Neither change edits production
decoder limits or recovery authority. A new exact-source hosted run is required.
