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

## Corrected hosted run and standalone decoder startup

The next published head `3271b9a45d507adf1438f8c3704a1111eb72a42d` has tree
`bd0fa97aacca042f9ebb473f6622de4782f9b146`. Its
[CI](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38657365015)
passed both actual PostgreSQL recovery scenarios and the isolated kernel browser
step. Its direct browser result, described below, is partial evidence rather than
complete qualification. The
[runtime run](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38657365147)
again passed named-volume save/read/restart/restored-byte checks, but its QEMU
decoder attempt failed again.

The retained original attempt reached its parent wall timeout at 2.010173 seconds,
with 1.996704 seconds of child CPU and 0.006577 seconds spent creating the process.
It was killed and reaped. A separate instrumented child observed `python_ready`
at 0.450244 seconds and no worker entry before its own deadline. These data focus
investigation on startup work, but cannot establish the original attempt's phase
or distinguish all emulator effects. Both failures remain failed qualifications.

The independently reviewed production correction in `3e51440963cfc37ce64327af1069dadb7af10bb7`
keeps API-only imports, response DTO construction and the single decoder lock out
of standalone child startup. Its private PNG record is now an immutable typed
tuple. The worker still runs the same trusted file and subprocess arguments; the
five parser/parent/worker function ASTs, all six admission/resource constants,
deadline origin and refusal behavior are unchanged. No prewarming, retry, pool,
limit extension or application state is introduced into the child.

Fresh-process import-boundary and normal API/lock regressions pass. Local results
are 84 decoder/probe tests and a separate broader 246 passed / 28 explicit
PostgreSQL skips; eight synthetic canonical outputs retain exact digests, byte
counts and dimensions. The complete native import graph drops from 155 to 122
records, including the cost of `typing`; sampled native wall times remain about
0.064 seconds before and after. This proves a reduced import graph, not a measured
latency improvement or QEMU success. The changed installed-image worker digest
must pass a new exact-source hosted probe. Physical-device resource qualification
and the broader installation gates remain open.

## Exact browser failures and test-contract corrections

The corrected hosted direct report finished with 55 of 63 tests passed, eight
failed, zero flaky and zero skipped. Branding passed 13 of 20, administration
15 of 16, and all other files passed. The retry-free repetition steps were skipped
after failure; the separate aggregate remains independent evidence.

All seven branding failures are demonstrated exact-label selector mismatches on
three wrapped selects: shared palette, personal palette and surface scheme.
The controls are present and enabled, with the intended accessible combobox names.
Playwright's exact label-text lookup also includes their nested option text.
The test-only correction uses exact combobox role and the same accessible names
for nine actions/assertions. Values, all behavioral checks, 63 cases and timeouts
are unchanged. The convergence case stopped before upload/save, and the four
branding visual scenes stopped before shared-branding scene setup and capture,
so no new branding image matrix is claimed from this run.

The inherited administration case rejected a legitimate multiword workshop name
wrapping at 640 viewport pixels with 200% CSS enlargement. The no-horizontal-
overflow and eleven complete-word-width assertions had passed; its three earlier
viewport captures exist, but no failing enlarged-state screenshot was available.
The obsolete single-line `OCWP` check is replaced with exact full-name, intact
single-fragment words and positive visible geometry inside the identity column
and navigation header. Existing metric/navigation readability, overflow, focus,
draft, enlargement and accessibility assertions remain. Pre-assertion pixels and
geometry are explicitly diagnostic; the normal verified-state captures stay
after assertions and alone count toward the qualification matrix.

These corrections do not alter product UI/CSS or substitute local test collection
for execution. Exact-source hosted browser rerun and original, expected-state
pixel review remain required. The earlier failed report and both QEMU failures
are retained as historical evidence.

## Separate standard native ARM64 qualification

A separate `ubuntu-24.04-arm` job uses the same API Dockerfile, checked-out source,
installed decoder, synthetic fixture and production resource/assertion contracts.
It verifies the host machine, Python ELF architecture, runner architecture and
Docker daemon before building, then verifies the container and installed worker.
Its bounded closed-schema report binds the tested commit, image ID, host facts,
installed worker hash and process result. Container output is never forwarded
unvalidated. Only safe JSON is emitted to the job log and summary; no image,
external cache, build-record or new evidence artifact is uploaded.

This is a separate native execution probe; the existing QEMU job, default probe
behavior and its failed results are preserved. It does not establish Raspberry
Pi timing, memory, storage or deployment suitability. Both probes retain the
same production limits; neither result substitutes for the other.

The literal standard runner has no custom/larger-runner fallback and is admitted
only when repository privacy metadata is the actual boolean `false`. The guard
also checks its serialized JSON type because GitHub's loose equality otherwise
equates missing/null values with false. Private or missing metadata skips the
native job. A queued or unavailable runner remains pending/blocked, with no native
pass claim. The official
[runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
[billing reference](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
and [expression semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions)
were checked for this bounded public-repository configuration. Actual exact-source
hosted native execution is still required; local helper tests are not ARM runtime
evidence.

## Native execution and complete browser run before pixel corrections

Published head `de5fa029656e3473b3cf895714e0ece5949f8694` was tested as merge
`aa07048079ff1c5bde5bad62855f792ddeda47de`, tree
`e32343c0150c2ca9be128167ba2d652e1d5779d9`. Its exact-source evidence is:

- [CI](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38664702315):
  27/27 aggregate controls, 2,228 Python passes / fourteen explicit skips,
  715 frontend core tests, fourteen isolated kernel cases, 63 direct and 63
  aggregate browser cases, and 20 + nine retry-free repetitions. Direct cases
  all passed on their first attempt. Aggregate artifact SHA256:
  `80bd86461e25b5c5183cf67a9efde181a2a7c76b15991a0ebf12820c0d95516f`.
- Both real PostgreSQL18 recovery scenarios passed; the floor1 scenario rotated
  two incarnations without activation, while the mixed-floor scenario rotated
  three and explicitly activated two. All three profiles and asset bytes matched,
  and stale sessions/checkpoints were refused. A pytest current-directory alias
  is a duplicate proof, not a third scenario. This proof does not cover browser
  queues. Recovery artifact SHA256:
  `332a20f72d0c202a904ff1926109a829e774507314b9562dca9cbb632e204288`.
- [Disposable runtime](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38664702357)
  passed actual named-volume API save/read, source restart, database-plus-assets
  restore, restored restart, exact bytes/metadata and stale-token refusal.
  Runtime artifact SHA256:
  `ab1f848c40cb1d9ff860158f3a513ff1bbc26ba08ca2247d5b6c0cd64c373c0e`.
- [Security](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38664702285)
  passed: 258 content commits, 12,337,528 bytes, 41 active packages and zero findings.
  Artifact SHA256:
  `cb9baa06cca8e39f680d696e84a0dee98d1f9a92938d2dfc8377b63c8f51afe0`.
- [Actual standard native ARM64 execution](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38664702357/job/116193824722)
  passed with host/guest ARM64 identity, unchanged production limits, installed
  worker SHA256 `449578bff3e198382b3f9b9a575547f3c04350e70e1365cd9dfa51d9314dcec5`,
  exact synthetic pixels and one successfully exited/reaped child. Elapsed time
  was 0.314891 seconds, child CPU 0.259400 + 0.015023 seconds. This single smoke
  observation is not a benchmark or physical Raspberry qualification.
- The same-source QEMU decoder still failed after 2.011278 seconds, killed/reaped
  at the unchanged parent wall bound. Its separate instrumented child reached
  `pillow_import_start` at 1.578520 seconds. Neither that marker nor the native
  result proves the original failure's cause. QEMU artifact SHA256:
  `bc86f768ec33f4e9d6c0dddf483f9c2b2a3b686cdf0a40715f0ab5dab5f343eb`.

The direct browser artifact SHA256 is
`b84903de79d4f3f2d69e81ba6e9bbdb33d9e24d4bdf51e91290c97827fa6c4a0`.
Independent pixel review bound 74 original post-assertion images to six passing
cases: 36 branding scenes and 38 administration scenes. Four pre-assertion
administration diagnostics and report copies were excluded. Inspection-only
crops helped read tall full-page originals; they were never counted as new scenes
or substituted for original evidence. Review report SHA256:
`5b39685ab908158aeb3d91aed717df57fe861be9dc05d600b8588f8e1fb4aab6`.
The complete original path/hash/state inventory has SHA256
`1875b591c7aa3f741cfc2a0d43f76772605847b9fdb1f0fdfb62161749d99a25`.

Despite automated green, twenty originals show pale transparent artwork nearly
invisible on the fixed white shell/preview backing. Eight CSS200 branding scenes
split the save word `compartida` midword. Their union is 24 affected originals;
no third clear blocker was observed in the 38 administration scenes. Therefore
this is not a visually qualified candidate. CSS enlargement is the tested
640-pixel viewport with CSS zoom2, not physical browser/device zoom. Target-size
and axe assertions do not establish physical touch or screen-reader behavior.

## Bounded presentation correction and revised ARM criterion

The renderer selects a fixed white or dark backing using bounded, alpha-composited
contrast scores from the already decoded current PNG. It performs no new request,
encoding, image mutation, persistence or authority change. Source identity and
connected/current image checks fence the synchronous work; opaque, empty or
unreadable images retain white. Mixed/translucent artwork remains a heuristic,
not a universal per-stroke contrast guarantee. Independent textual identity and
accessible descriptions remain. Only the image canvas opts out of forced-color
substitution. A fixed gray alternative was rejected because it reduced the
already exercised red artwork's contrast. Scoped nested form padding and button
margins reclaim width without abbreviating text, hiding overflow, shrinking
control targets or remounting operational forms.

The deliberately revised architecture criterion requires all three ARM64 builds
and actual native ARM64 installed-decoder execution. The aggregate rejects
missing, skipped, failed or cancelled native/build evidence. Native timing
consistency checks are accounting checks only; production wall/CPU limits remain
two seconds. QEMU moves to a separate, explicitly non-qualifying diagnostic
workflow which retains actual nonzero exits, failed reports and unproven causal
status. A red QEMU workflow must not be reported as all CI passing. No historical
image/signature exception, permanent allowlist or branch-protection change is
introduced. The diagnostic build reads the existing cache without additional
image/cache/build-record exports; only bounded safe diagnostic evidence is kept.

These are new source changes after the exact hosted results above. Their local
regressions, independent source review and new exact-source hosted execution must
be recorded separately. The strengthened image, offline, word-geometry and
original-state capture assertions still require actual new pixels. Physical
Raspberry, Windows/Android, screen readers, glare and realistic-capacity recovery
remain separate open gates; no installation, real grant adoption or deployment
was performed.
