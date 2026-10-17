# Fixed quote candidate integration checks

Status: the exact finite selection passed and was independently reviewed; consolidated service/schema integration remains pending.

The [tiny service-effect restore](2026-10-17-quote-service-restore.md#verified-tiny-service-effect-restore-result)
passed independently. This next finite check closes specific remaining unit and
static gaps before a consolidated service/schema review. It does not repeat a
capacity experiment or expose the private service.

## Fixed workload

One distinct workflow has four literal groups, executed with max-parallel 1:

- Guard foundation: 51 existing cases.
- Guard protocol/diagnostics: 68 existing cases.
- Pure product boundaries: 62 cases, comprising the remaining 47 codec cases
  (required fields, field domains, numeric lexemes, malformed/duplicate/deep JSON
  and raw byte boundaries), 14 prepared-writer bind/forgery/scope cases and one
  driver-settings Result-iteration regression with eight internal variants.
- Static/contracts: the existing six commands, including lint/format coverage
  of the new fixed outer recipe.

Each group has its own unchanged 20-second workload, 1 CPU / 512 MiB worker,
real cancellation canary and independent owned-container absence check. The
four-group workload allocation is at most 80 seconds, not a single 80-second
specimen. Preparation and cleanup retain their existing separate bounds. No
PostgreSQL server is required for these pure, mocked and static groups.

Use the established hash-pinned frozen outer baseline as the only host-side
helper import. The current guard under test is an ordinary contained specimen;
it cannot approve itself. Selection is a closed literal group table, not an
arbitrary command, selector or budget input. Exact source hashes, fixed function
counts, bounded unique observed case IDs and complete successful JUnit records
must agree. Missing, duplicate, failed or skipped cases remain nonqualifying.

Keep JUnit and closed result caps at 16 KiB. Guard/codec output uses the existing
16 KiB spool; static uses its established 32 KiB spool because the existing
24 KiB marker can carry 16 KiB of tool output. Retain bounded actionable public
pytest diagnostics only after verified worker stop and client reap, without
locals, credentials or environment dumps. Report truncation explicitly.

The proof image installs locked application/development dependencies and Git
from the base image's signed Debian repository. Git is required by one existing
tiny 240-file index regression. No host installation or access-setting change
is involved. Source reaches the image through the exact tracked archive.

## Acceptance and exclusions

Require every fixed group to pass on one identical candidate tree, together
with source/image identity, actual resource limits, cancellation and cleanup.
Record the first failure and diagnose it before any correction or new run.
Previous consumed workflows and their evidence remain unchanged.

The 47 cases are the previously identified codec gap. They are not all remaining
pure tests in the repository. Other SQL-backed prepared-writer, driver-budget, collection,
service/effect corruption and database/concurrency cases must be inventoried in
the consolidated review and cannot inherit this result. New static evidence
also does not retroactively execute those tests.

Internal merge readiness requires consistent specifications, exact complete
diff review, applicable ordinary integration gates and an explicit coverage
ledger. Capacity, concurrent lock behavior, bounded availability, all ingress
fences and HTTP/UI acceptance separately block production activation. Keeping
commands disabled does not excuse an integrity or authorization defect in an
internal merge. No API activation, deployment or real account/data operation is
part of this increment.

## Reusable PostgreSQL fixture identity correction

Read-only consolidated review found that the four-body PG service fixture
hardcoded ocwp_quote_micro_test, while ordinary CI configures ocwp_e2e. The
owning identity_migration_database fixture already validates loopback routing,
*_test/*_e2e names, absence of connection overrides and actual database identity.
The service bridge now compares current_database() to that validated engine URL.
It retains actual driver/version/schema/encoding checks. The outer qualification
receipt's fixed owned-database requirement remains unchanged.

This is a source-demonstrated integration mismatch, not a previously executed
failure. Static checks alone cannot qualify the corrected fixture; current
revision-0013 PG service execution remains an explicit integration requirement.


## Verified fixed integration selection

Run: https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39069601139

Commit: 181579e9a76fabb8af72ec4cc343d85ecbfde55b
Tree: 71adc27482ce823e062d055ae9bf911c9a12d0ee
Run number/attempt: 1/1. All four sequential jobs completed successfully.

| Group | Passed | Workload seconds | Final-read worker peak bytes | Artifact |
| --- | ---: | ---: | ---: | ---: |
| Guard foundation | 51 | 0.791 | 49,504,256 | 12114437035 |
| Guard protocol | 68 | 2.190 | 60,678,144 | 12114538048 |
| Database-free product | 62 | 3.488 | 93,605,888 | 12114712400 |
| Static/contracts | 6 | 9.632 | 274,591,744 | 12114547961 |

All 187 selected cases/commands passed with zero failures, errors or skips. Exact source hashes, observed case identities/counts, real cancellation canary, whole-worker stop before client reap, primary absence and independent absence were reviewed. CPU/memory samples are final-read counters before worker termination, not post-termination totals. Each distinct workload stayed within its own 20-second cap; no retries occurred.

Artifact SHA-256 values:
- 12114437035: c41e5c97f4d7528a7f3a32fb72d50a5c31294a936d855ae1450149e9ee3d481a
- 12114538048: 8a4b0696bf56998744d9e105f0f2b87b1141d65eb657bc355dd830df453a474a
- 12114712400: 63a04aab9aa678d8964b6ae5b861967cd92582ac1328aae0f75f061cf41cad8d
- 12114547961: 9095c4f276f09d4deaddfcf2b82009535c781bed8d72694ad00098231b1fe32f

This selection does not qualify the current PostgreSQL service fixture, the complete service/schema integrity matrix, actual service concurrency, capacity, production deadlines or activation. The consolidated application diff remains subject to independent review and applicable current-tree integration. Earlier failed capacity/profile evidence remains unchanged. No API was activated or installation deployed.
