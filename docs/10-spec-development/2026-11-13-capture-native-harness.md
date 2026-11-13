# Native capture boundary harness: implemented, execution pending

## Design and scope

Baseline PR105 main `698420be10043afa2c237cbfe255e46490cf1f88`, tree
`b2721df8bceefc02eed40b3ef5c7a293dac993e2`. This implements a bounded evidence
instrument for the [rollout decision](2026-11-13-capture-rollout-boundary.md),
not another production fence or approval to migrate origins. G1–G6 stay open.

The separate Vite build imports the actual SHA-pinned cc18a203 validator/reducer,
transpiled without changing the stored source bytes, and composes it with the
current KernelDatabase/Dexie 4.4.4 class. It is **not the historical App/SW**.
Fixture hashes, exact historical commit, Dexie version and missing inputs are
checked before compilation. Built asset hashes and current source hashes are
recorded with the build-time HEAD. Uncommitted source hashes, rather than HEAD
alone, identify a precommit build. Both origins must match the checkout HEAD/source hashes and their served assets.
Native results also attach browser version and
synthetic before/after rows. No fixture content is real customer data.

`test:capture-browser` builds/typechecks before Playwright. Two loopback-only HTTP
servers use the same hostname/scheme, ports 5176 and 5177. Tests use one browser
context with top-level pages, not separate storage contexts masquerading as origin
isolation. Database names are identical within each scenario and restricted to
`capture-native-*`; the harness rejects production names and existing-fixture
reseeding. No production database, backend, account, migrations or purge operation
is needed. Only ephemeral test storage contains synthetic future-format rows.

Three native scenarios are authored:

1. Same-origin pages observe identical rows. Current maintenance preserves a valid
   unexpired future envelope and current load refuses it. After going offline, a
   failed uncached fetch proves network unavailability, then the already-loaded
   historical reducer deletes that row. The exact-v1 customer sibling survives
   and remains readable by the old reducer. This is loaded-code offline execution,
   not reload/restart or service-worker lifecycle qualification.
2. An open declared-v8 connection receives versionchange during a synthetic v9
   upgrade. It closes and reopens, reports native version 90, and still has the
   identical fixture before the historical deletion. No delete/reset/reseed is
   used to simulate a reopen.
3. Distinct origins seed distinguishable rows under identical keys/database names.
   A same-origin control page sees A's rows, A does not see B's sentinel and vice
   versa. Historical maintenance deletes A's future row (positive control) while
   B's entire payload/checkpoint snapshot remains unchanged. This can demonstrate
   a browser storage mechanism, not safe deployment or lossless handover.

No production source, service-worker configuration, draft writer or storage schema
changes. The production isolation guard scans source and the actual PWA build for
harness markers. CI runs the independent harness after Chromium installation and
retains its JSON result, traces and build provenance even on failure. Retries are
zero. The three cases are separate from the ordinary direct-browser suite.

## Negative controls and local validation

Sixteen Node checks verify the actual harness composition using fake IndexedDB and
reject changed source, altered declared hash, wrong historical commit, wrong Dexie
version, missing input, production database names and fixture overwrite. Additional
controls reject wrong served-manifest pin/HEAD/source, empty or invalid assets
and extra fields. They
verify matching generation/revision, original TTL and current preservation before
historical deletion. These checks do not establish native origin semantics.

Local normal Playwright launch with the system Chromium failed before any page
opened: `process_singleton_posix.cc:297 ... socket() failed: Operation not permitted`
and SIGABRT, with a preceding crashpad directory error. No browser test ran. No
policy edit, alternate binary, escalation retry or security-flag workaround was
used. The failure is retained as a launch blocker, not a product defect or a RED
behavioral test. Compilation/build/collection results are separate evidence.

A review found a wrong literal historical pin in the authored page assertion. A
regression was observed failing, then the assertion was corrected to use the same
verified pin and served provenance checks were strengthened. No native pass was
claimed before this correction. Final source checks and independent delta review passed. Publication is not
currently authorized; CI wiring is not evidence that hosted execution happened.

## Remaining acceptance

Even a future passing harness qualifies only the named native browser's storage
behavior with the pinned reducer and current database class. It does not prove
actual cc18a203 App/SW startup, old offline restart, partial SW update, deployment
entry-point enforcement, credential/draft/journal migration, private-copy cleanup,
physical platforms, rollout or rollback safety. A separate reviewed native App/SW
rehearsal and transition architecture remain required. Keep shared-origin v1
writes and the selector blocked; separate-origin product deployment is proposed,
not approved or implemented. Historical branding and other release gates remain.

## Final local receipts

- Frontend: **1,527 passed**, zero failed/skipped, including 16 harness controls.
- Repository: **207 passed**. Production isolation: **2 passed** against actual PWA.
- Lint, prescribed formatting (397 Python files), TypeScript, native-test typecheck
  and mypy (126 files) pass. Production and separate harness builds pass.
- Native Playwright: **3 collected, zero executed locally**. Launch is blocked as
  recorded above; hosted execution is pending publication/CI, not presumed green.
- Full backend/aggregate was not rerun for this test-harness/CI-only increment.
  PR105's hosted checks qualify its baseline, not these new native scenarios.
- Independent review accepted the corrected pin and both-origin checkout/asset
  provenance checks. Earlier failed/superseded receipts are retained separately.

Only documentation stamping follows these checks; repository/format checks are
rerun after the stamp. Source and receipts are bound to the final local commit.
G1–G6 remain open, production writes remain v1 and the selector is not activated.
