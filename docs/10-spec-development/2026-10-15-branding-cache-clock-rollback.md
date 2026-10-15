# Branding cache operation-entry clock rollback

Date: 2026-10-15. Status: implemented_pending_evidence.
Scope: bounded production cache admission and deterministic tests. This expands
PR41's original administration clock-fixture-only scope; probe behavior, browser
assertions, timeouts, public APIs, schema and operational data are unchanged.

## Retained first failure

[CI 38673600999](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38673600999)
tested PR41 head `537b2c689a40e2fe8de7138ad96b89e46f54847f`, tree
`27be03b34aa32e2d5f043067273113643b7f46c5`, synthetic merge
`64993f4d3abedfef0dce47aa67ff3370893bb623`. The direct frontend phase had **731
passes and one failure** at `apps/web/tests/branding/cache.test.mjs:95`: the
existing `NOW - 1` rollback assertion expected `null` but received a complete
branding profile. All four new administration clock tests passed on Node 22.16.
The later aggregate's 732 frontend passes do not replace the original failure.

Direct browser and the separate five-run probe gate were skipped after that
failure. Aggregate browser launch was unavailable because Chromium installation
had been skipped, not because 63 application journeys were observed failing.
The aggregate separately passed 2375 Python tests with 14 skips. No failed run
was cancelled or retried to hide the result.

## Cause and bounded correction

`elapsedClock(now)` adds monotonic elapsed time to the supplied wall timestamp.
Previously the first context/control/snapshot checks all used that advancing
value, after asynchronous transaction/digest work. An input already behind
trusted timestamps by one millisecond could become apparently valid after two
milliseconds of elapsed work. This is a production fail-closed admission defect,
not an invalid assertion, Node-version incompatibility or browser-fixture bug.

The repository now preserves the immutable entry wall timestamp for context
validity and device/snapshot rollback comparisons. Stored-context lease expiry
continues to use advancing monotonic time after asynchronous reads, including
the final read/write transaction. Existing digest, owner, scope, exact-row and
version checks remain. A denied write preserves snapshots and unrelated journal
records; late expiry aborts the transaction. Invalid existing snapshot provenance
retains its explicit persistence-error behavior rather than repairing/erasing it.

Read and write are the only elapsed-clock consumers. The display controller
already supplies a fresh wall timestamp to each call; its public contract and
runtime behavior are unchanged. A concurrent newer trusted observation may
conservatively refuse an older operation. No lease is extended and no cached
bytes grant authority. This is a correction within the existing authenticated
cache architecture, not a new admission mechanism or schema migration.

## Deterministic evidence

Six cases exercise read and write independently against context, device-control
and snapshot timestamps. The entry timestamp is behind the chosen boundary;
`performance.now()` is exactly zero at clock creation and two milliseconds at
later validation. All six fail with the original production implementation.
The same tests pass with the correction, without sleeps, timeout changes or
removing the original rollback assertion.
Each refused operation also verifies exact snapshot/journal preservation and
successful read/write recovery with a fresh valid entry timestamp.

Three controls prove valid entry survives delivery delay, expiry during the
second read transaction prevents publication, and expiry after snapshot update
aborts the write transaction. Existing takeover-during-digest, digest-expiry,
renewed-lease, remembered-offline-admission, corruption and preservation tests
remain in the full runner.

- Exact supported Node **22.16.0**: original implementation **six expected
  failures / three passing controls**; corrected full frontend core **741
  passed, zero failures or skips**.
- The official `node-v22.16.0-linux-x64.tar.xz` distribution was verified against
  Node's published SHA-256:
  `f4cb75bb036f0d0eddf6b79d9596df1aaab9ddccd6a20bf489be5abe9467e84e`.
- Local Node 24.19 also reproduced all six failures and passed 13 focused cases
  after correction. This is supplementary to exact supported-runtime evidence.
- Final local Node 22.16 frontend core: **741 passed**, repository contracts:
  **22 passed**. Touched ESLint/Prettier, web/offline types and production PWA
  build passed. The build retains its existing large-chunk warning.
- Independent Node 22.16 review: **19 cache cases**, **33 combined
  cache/contracts/runtime cases**, and **three additional concurrency controls**
  passed with no blocking findings. These overlapping groups are not additive.

The local pnpm wrapper attempted an automatic dependency installation and failed
on its local store directory before running typecheck/build. Those checks were
then executed successfully through the already installed TypeScript/Vite
entrypoints with Node 22.16; no dependency or lockfile change was made.

These are actual production repository checks with fake IndexedDB, not native
browser execution. Fresh exact changed-head hosted qualification and the
original browser/repetition gates remain required. Physical devices, screen
readers, operator recovery and actual installation remain outside this proof.

## Subsequent exact-head browser failure

Published head `d4c05100e83da06710e0843c6c2fd18447095e2b`, tree
`a57c700a764ec4f3aba322bfa763745f49b82358`, passed its 741 frontend core cases but
[CI 38676085071](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38676085071)
failed the offline-branding journey in both direct and aggregate execution.
The direct report has 62 passing cases, one failing case and zero flaky cases;
both attempts of that case failed before its first reload. Aggregate: 26/27
controls passed, 2375 Python passes / 14 skips, 741 core passes, 62/63 browser
passes. Repetition phases were skipped. Neither failed result is superseded by
the local checks above.

The repository correctly refused concurrent newer control evidence, but the
display caller discarded an explicit recovery refresh while a flight was
active. This made the previously documented conservative refusal an actual
offline availability regression. The [bounded caller correction](2026-10-15-offline-branding-refresh.md)
retains every repository rollback check and records deterministic composition
RED/GREEN plus the original native evidence. The exact interleaved writer is
not observable in the browser artifact; controlled composition tests prove the
mechanism without claiming that missing trace detail.
