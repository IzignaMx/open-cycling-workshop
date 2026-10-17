# Quote service integrity edge corrections

Status: source corrections and regressions prepared and independently reviewed; hosted execution pending.

Consolidated source review after the [fixed integration selection](2026-10-17-quote-integration-checks.md) identified two narrow contract mismatches:

1. The receipt projector used platform-dependent strftime year formatting. Canonical storage and the response DTO require four-digit years throughout the supported 0001–9999 range. Use UTC ISO formatting with exactly six fractional digits and Z, matching the existing canonical storage convention. Eight prepared projector cases cover years 1, 999, 1000 and 9999 for applied and replayed responses. The old runtime failure has not been reproduced; platform dependence is documented in the [Python datetime specification](https://docs.python.org/3.13/library/datetime.html#strftime-and-strptime-behavior).
2. SQLite permits NUL in referenced text identifiers, while scalar order metadata previously deferred NUL refusal until complete projection validation after bounded Text hydration. The bounded-effects ADR requires refusal before hydration. Add a narrow check only to scalar order metadata; keep the shared historical-ID contract unchanged. Two prepared SQLite cases retain valid foreign-key relationships, forbid Text hydration and assert normalized integrity refusal without any new lineage or effect. PostgreSQL itself does not admit NUL text, so this is a surrogate prehydration correction rather than a demonstrated PostgreSQL bypass.

The regressions were added before verification. No local candidate tests ran and no observed RED/GREEN result is claimed. Preserve the exact prior tested source and qualify the corrected source with the existing finite contained mechanism.

No chronology policy change is included. The current order's timestamp monotonicity relative to a new quote decision remains a separate specification question; source inspection alone does not justify changing established behavior.

## Remaining integration and activation boundaries

Current service, effect-integrity, DTO and real-PostgreSQL negative/compatibility coverage remain required for internal integration. The prior tiny valid restore checked retained data and metadata, rotated incarnation, then reconstructed on fresh replay; it does not establish full-history validation before reopening or corrupted/oversized/unknown-version restore refusal. Capacity, actual service contention, production total deadlines, API/UI and deployment remain separately unqualified.

## Prepared finite current-source qualification

The amended plan covers 210 checks in ten sequential groups; exact source and bound review remains required:

- Service group: the complete SQLite service module (21 cases, including both NUL regressions) plus six fixed mock-only selection/identity/observer regressions. The latter add no live database or subprocess workload.
- Complete SQLite atomic-effect module: 18 corruption cases and 18 other cases.
- Complete database-free response module: 50 strict-number cases and 64 other cases, including eight year regressions.
- PostgreSQL metadata trust: seven malformed sync-change definitions, seven malformed order-outbox definitions, and nine relation/dependency cases.
- Current PostgreSQL 0013 service bridge: four existing cases.
- Static/contracts: the existing six commands on the corrected source and touched qualification recipes.

Every group retains its own 20-second workload cap; the allocation is 200 seconds across ten workloads, with max-parallel 1. Preparation/canary/cleanup retain their separate existing bounds. Grouping is driven by complete-function coverage, output size and fresh migration cost. No duration guarantee follows from prior smaller cases. A failed or timed-out group remains unqualified and must retain its evidence.

The existing frozen-helper JUnit mechanism covers SQLite, DTO and static groups. The existing contained PostgreSQL mechanism covers metadata and the service bridge. Metadata bodies deliberately leave rejected catalogue definitions behind: their final-only observer checks actual driver/database/schema/encoding/revision, not catalogue validity. The bridge retains its own earlier setup identity observation without a duplicate final observer. Exact typed PostgreSQL parameter matrices, complete phase records and isolated schema identities remain required. No arbitrary selector, resource budget, retry or general runner is introduced.

The PostgreSQL inner result remains strictly below 16 KiB; its outer artifact also contains resource evidence and may be larger. The fixed phase-counter maximum becomes 27 for nine-case metadata groups, while the six-command static protocol remains exactly 18 phases. The JUnit mechanism keeps its existing 16 KiB XML/result bounds. No resource or enforced output limit is increased. Exact implementation review and hosted results remain pending.
