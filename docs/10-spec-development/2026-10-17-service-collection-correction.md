# Initial service collection correction

## Verified correction regressions and next service gate

[Correction run 39041234055](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39041234055)
passed once (run 1/attempt 1) on commit `54fe65bee87f615a78c771507515ab95e6ef247e`,
tree `b480a2aaf641f7dd12c7bc22fa73ffceef436185`. All eight exact identities passed
with zero errors, failures or skips. Workload time was 1.803724695 seconds;
worker lifetime was 2.286161421 seconds and total supervisor time 3.417525785 seconds.
Final worker CPU was 1,872,811 microseconds and peak memory 67,121,152 bytes.
Actual source/image/cgroup/privilege identity, three-generation canary,
whole-worker cancellation, bounded client reap and both final absence receipts
were independently reviewed. Artifact `12104072554` SHA-256:
`0bff116ef047cecee132989c92453b2f906ad1bd725e4d35ba226087af4e4fee`.

The synthetic negative/positive collection regression passed. Diagnostic
fault-path scenarios are mocked; this result does not recover the original
discarded error or qualify actual service behavior. The dated preparation text
below is preserved as history and is superseded only by this exact evidence.

The next fixed gate is `quote-service-corrected-collection.yml`, accepting only
`codex/quote-service-corrected-collection`, run 1/attempt 1. It runs exactly the
six original DTO/SQLite service nodes through the now regression-tested guard
SHA-256 `a8c92710682204575b7affa26fccd263f9ab2325a3033bf8aff4f03b000dd11a`.
The only changes from the failed source are the reviewed pure-test separation
and closed diagnostics already qualified above. Product code, fixtures, selected
node IDs, schema 0012 and all service success/resource/cleanup budgets remain
unchanged. No previous workflow is modified; the correction is a demonstrated
technical reason for a distinct qualification, not a blind retry.

The new workflow mirrors the original service recipe, changing only its fixed
identity and artifact name, and disabling checkout credential persistence.
The workload ceiling remains 20 seconds including imports through teardown;
worker 1 CPU/512 MiB/swap zero/64 PIDs and idle PostgreSQL overhead
1 CPU/768 MiB/swap zero/128 PIDs remain separately bounded. No extra workload,
capacity/profile, schema 0013, endpoint, account or activation is included.
Fresh exact-source review and remote branch/run/trigger preflight precede the
single push. A failed or skipped run stops; no automatic retry is implied.

This service qualification is still pending. Full setup/call/teardown protocols,
source/image/resource identity, cancellation and both absence receipts are
required. Passing it would cover only the six original tiny cases. The two moved
pure tests, broader semantic coverage, PostgreSQL, hard service deadlines,
payload/version policy, API/UI, capacity and activation remain open.

## Failed evidence remains authoritative

[Run 39039629649](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39039629649)
executed once (run 1, attempt 1) on commit
`49a6f9d8ddce77f1b9488fac78f17a952300e448`, tree
`8def8ab7ce55db121c9f31f72265f0447e3c3253`.
It failed with specimen return code 4 during pytest bootstrap. Supervisor elapsed
time was 6.395 seconds including 2.076 seconds setup; the workload ceiling was
20 seconds. No six-case result or setup/call/teardown protocols were retained.
The exact initiating error is unknown because the original diagnostic was discarded.

Artifact `12103397218` has SHA-256
`56d6933692f4e7a1a2cfd581c5aa12b6d0aa108a46b2b5d6662abb8c50301da0`.
The real containment checks and three-generation cancellation canary passed;
workload cancellation, client reaping, supervisor cleanup and independent cleanup
reported successful final absence. Worker limits were 1 CPU, 512 MiB, no swap,
64 PIDs. Reported worker memory peak was 94,679,040 bytes. These observations
do not qualify the service, PostgreSQL atomicity, throughput or deployment.

## Minimal correction

`test_quote_application_service.py` applies indirect parametrization of
`identity_migration_database` to every test in the module. Two pure zero-argument
driver-budget tests do not use that fixture. The locked pytest 9.1.1 collector
generates module items before selecting requested function names, and rejects
an indirect parameter outside the fixture closure. The selection hook can then
raise a usage error when the expected six nodes were not collected.

This is a source-demonstrated defect, independently reviewed. It supplies a
plausible path to return code 4, but the retained incident evidence does not prove
that it was the exclusive initiating cause.

Move those two pure tests to `test_quote_driver_budgets.py`, preserving bodies
and assertions. Do not add unused database fixtures or change the original six
service node identities, semantic acceptance or workload budgets.

Prepare a strictly closed, bounded stage/count summary for failed collection or
execution. It must contain no exception message, captured payload or arbitrary
failure text. Failure observability must never delay whole-container cancellation,
weaken success acceptance, mask the original failure or bypass final cleanup.
Missing/invalid diagnostics remain unavailable rather than fabricated evidence.

## Verification boundary

The correction is locally prepared, unexecuted. RED/GREEN, static toolchain and
runtime behavior have not been observed for it. No application source, dependency
or migration change is part of this correction. Schema remains 0012. Existing
workflows stay unchanged; the separate fixed regression gate below is new.

Before a distinct corrected-source trial: review the exact diff, fixed finite
diagnostic regression selection, source/image identity and containment limits.
The pure tests and diagnostic parser/hook regressions need bounded execution;
the original six DTO/SQLite cases still require their full successful protocols.
The original consumed workflow remains unchanged and cannot be retried or
renamed implicitly. A later trial needs a separately reviewed purpose and gate,
and may not claim historical RED/GREEN or erase this failed result.

All PostgreSQL service, full authorization semantics, effect-version/payload,
hard deadline, API/UI, capacity, restore, physical-device and activation gates
remain open. This correction only addresses collection and diagnostic visibility.

## Fixed correction-validation gate

The proposed `quote-collection-regression.yml` gate accepts only a push to
`codex/quote-collection-regression-proof`, run 1/attempt 1. Publication starts
one eight-node regression batch, not another service workload. The exact source
and wrapper must pass independent review and fresh branch/trigger preflight
before publication. The consumed service and bootstrap workflows remain intact.

`quote_collection_regression.py` preserves the established fixed outer bootstrap
recipe and imports only the frozen baseline helper whose hash is verified. The
changed guard is test input inside the container, never outer supervision code.
The development-only image has locked pytest dependencies, the two operations
test modules, changed guard source and the existing fixed workflow fixture.
It contains no application source or database. Six fixed nodes test closed
diagnostics and mocked cancellation/cleanup scenarios; two create tiny synthetic
modules and prove the original invalid collection and corrected collection.

One 20-second workload deadline covers imports, collection, nested synthetic
collection, tests and teardown. Limits remain 1 CPU, 512 MiB, no swap, 64 PIDs,
read-only filesystem, no network, 64-MiB tmpfs and 16-KiB outer output. Each of the
two synthetic pytest children has a five-second wait; those waits do not replace
the containing deadline, descendant cancellation or storage bounds. Existing
bounded setup, real three-generation canary, termination, ownership reconciliation
and independent final absence checks remain required. Overall CI preparation may
take up to 20 minutes under the fixed workflow job limit.

Acceptance requires exactly eight successful JUnit identities, zero errors,
failures or skips, successful process exit, source/image/limit identity and both
cleanup receipts. Missing evidence is failure. This qualifies only the correction's
guard and synthetic collection behavior. It does not execute the six original
service nodes or the two moved pure driver tests, and cannot establish production
readiness. A failed, skipped or consumed gate is preserved without automatic retry.
