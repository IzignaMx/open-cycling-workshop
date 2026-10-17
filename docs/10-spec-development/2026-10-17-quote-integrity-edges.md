# Quote service integrity edge corrections

Status: 204 functional/mock checks passed and independently reviewed on the exact corrected source; static qualification failed with four style findings. The first corrective static-only run passed lint and exposed a complete formatter diff; its exact layout correction is pending verification.

Consolidated source review after the [fixed integration selection](2026-10-17-quote-integration-checks.md) identified two narrow contract mismatches:

1. The receipt projector used platform-dependent strftime year formatting. Canonical storage and the response DTO require four-digit years throughout the supported 0001–9999 range. Use UTC ISO formatting with exactly six fractional digits and Z, matching the existing canonical storage convention. Eight prepared projector cases cover years 1, 999, 1000 and 9999 for applied and replayed responses. The old runtime failure has not been reproduced; platform dependence is documented in the [Python datetime specification](https://docs.python.org/3.13/library/datetime.html#strftime-and-strptime-behavior).
2. SQLite permits NUL in referenced text identifiers, while scalar order metadata previously deferred NUL refusal until complete projection validation after bounded Text hydration. The bounded-effects ADR requires refusal before hydration. Add a narrow check only to scalar order metadata; keep the shared historical-ID contract unchanged. Two prepared SQLite cases retain valid foreign-key relationships, forbid Text hydration and assert normalized integrity refusal without any new lineage or effect. PostgreSQL itself does not admit NUL text, so this is a surrogate prehydration correction rather than a demonstrated PostgreSQL bypass.

The regressions were added before verification. No local candidate tests ran. Corrected-source GREEN is now observed; old-source RED was not executed. Preserve the exact prior tested source and qualify the corrected source with the existing finite contained mechanism.

No chronology policy change is included. The current order's timestamp monotonicity relative to a new quote decision remains a separate specification question; source inspection alone does not justify changing established behavior.

## Remaining integration and activation boundaries

The selected service, effect-integrity, DTO and PostgreSQL metadata/bridge coverage below now passes. Additional PostgreSQL loader/writer and broader integration coverage remain required. The prior tiny valid restore checked retained data and metadata, rotated incarnation, then reconstructed on fresh replay; it does not establish full-history validation before reopening or corrupted/oversized/unknown-version restore refusal. Capacity, actual service contention, production total deadlines, API/UI and deployment remain separately unqualified.

## Exact finite current-source qualification

The reviewed plan selected 210 checks in ten sequential groups:

- Service group: the complete SQLite service module (21 cases, including both NUL regressions) plus six fixed mock-only selection/identity/observer regressions. The latter add no live database or subprocess workload.
- Complete SQLite atomic-effect module: 18 corruption cases and 18 other cases.
- Complete database-free response module: 50 strict-number cases and 64 other cases, including eight year regressions.
- PostgreSQL metadata trust: seven malformed sync-change definitions, seven malformed order-outbox definitions, and nine relation/dependency cases.
- Current PostgreSQL 0013 service bridge: four existing cases.
- Static/contracts: the existing six commands on the corrected source and touched qualification recipes.

Every group retains its own 20-second workload cap; the allocation is 200 seconds across ten workloads, with max-parallel 1. Preparation/canary/cleanup retain their separate existing bounds. Grouping is driven by complete-function coverage, output size and fresh migration cost. No duration guarantee follows from prior smaller cases. A failed or timed-out group remains unqualified and must retain its evidence.

The existing frozen-helper JUnit mechanism covers SQLite, DTO and static groups. The existing contained PostgreSQL mechanism covers metadata and the service bridge. Metadata bodies deliberately leave rejected catalogue definitions behind: their final-only observer checks actual driver/database/schema/encoding/revision, not catalogue validity. The bridge retains its own earlier setup identity observation without a duplicate final observer. Exact typed PostgreSQL parameter matrices, complete phase records and isolated schema identities remain required. No arbitrary selector, resource budget, retry or general runner is introduced.

The PostgreSQL inner result remains strictly below 16 KiB; its outer artifact also contains resource evidence and may be larger. The fixed phase-counter maximum becomes 27 for nine-case metadata groups, while the six-command static protocol remains exactly 18 phases. The JUnit mechanism keeps its existing 16 KiB XML/result bounds. No resource or enforced output limit is increased. Exact implementation and partial hosted evidence review are complete as recorded below.

## Verified partial result and narrow static correction

[Run 39072574166](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39072574166), first run/attempt, tested commit `20f1d06d07898a89195c65d5c2143894bec1f6b0`, tree `5e25b34c56b16e5871d2367ea375880c963e2c9e`.

Nine jobs passed all 204 functional/mock cases: 21 SQLite service, six mock selection regressions, 36 SQLite atomic-effect, 114 response/DTO, 23 PostgreSQL metadata and four PostgreSQL service-bridge cases. The ten new product regressions passed. All 27 PostgreSQL cases have distinct real schema identity receipts for PostgreSQL 18.4, psycopg 3.3.4, UTF8 and revision 0013. Metadata observers run after the test body; their final identity observations do not certify intentionally corrupted catalogues. Expected refusals are established by the original passing assertions.

The static job passed the repository contract and failed Ruff with four complete SIM300 findings in the selection test (lines 607, 610 and 613). Formatting, production types, OpenAPI and generated-client commands did not run. The retained diagnostic is complete: 1,166 bytes with 431 bytes of decoded Ruff output. This is a failed workflow, not 210 passing checks.

All ten groups have verified resource configurations, real cancellation canaries and primary plus independent owned-container absence. Successful workloads took 3.533–9.770 seconds individually, below each unchanged 20-second limit. Successful final resource readings precede termination. The failed static report lacks final worker counters and workload duration; its supervisor duration does not replace those missing measurements. PostgreSQL successful specimens record client reap and final absence, not failure-path cancellation evidence.

The correction reverses only the four reported comparison operands. A new fixed `codex/quote-integrity-style-checks` branch/workflow pair uses the same reviewed controller and permits only `static6`; the original consumed workflow and all functional group selections remain unchanged. The six commands retain the shared 20-second, 1 CPU, 512 MiB workload and existing preparation, cancellation and cleanup limits. No functional rerun is included. That preparation was published and executed in the static-only run recorded below: repository and lint passed, then formatter failed.

Remaining internal gates include PostgreSQL bounded-loader/prepared-writer cases, broader service success/replay and rejection/race seams, and existing integration suites. Capacity, service contention, complete production deadlines and pre-reopen full-history restore validation remain open. No route activation or deployment follows from this partial qualification.

## Static-only formatter result

[Run 39073762410](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39073762410), first run/attempt, tested commit `86eb20b0db740d1911d06f7e1e6272f0cba87bb5`, tree `f04fd26f4748954cad6e9f81fa9b87fc27a579b9`. Repository and Ruff checks passed. Formatter failed with a complete, untruncated 2,616-byte diff in the existing controller, service test and selection test; 41 files were already formatted. Types, OpenAPI and generated client were unrun.

Artifact `12115797338` retains the exact diagnostic and both cleanup receipts. Its ZIP is 5,747 bytes, SHA-256 `bdb2ee258157ec5d0fcbed687ebedcb52e1d0dcc4f3bd99411d3f6783d6b438e`. Whole-worker stop, client reap and primary/independent absence were recorded. The failed specimen has no retained final worker counters or workload duration.

Apply only the retained layout hunks, refresh their source pins, and add a fixed `codex/quote-integrity-format-checks` / `.github/workflows/quote-integrity-format-checks.yml` pair restricted to the same six static commands. Both consumed workflows remain unchanged. The 20-second worker budget, resources, command ceilings and cleanup remain unchanged; no functional rerun or product behavior change is included. Exact source review and new execution remain pending. The previous two failures remain preserved.
