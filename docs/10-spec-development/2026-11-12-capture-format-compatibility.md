# Preventive capture payload compatibility

## Baseline and decision

Fresh clone matches PR103 main `cc18a203a8c754284fc14ef3570d94d7d98fac23`, tree
`0116b82f10277f1a78057140cc1f7885f5a35ecf`. The coordinator reports accepted main
CI43241109742: 10 checks, aggregate 27, frontend 1,483, Python 6,739 plus 58 exact
expected skips, browser 139 with zero retries. Those results qualify only that
baseline. The previous temporary checkout was absent; no lost bytes or evidence
were reused to qualify this candidate.

The user requested draft compatibility before existing-bicycle selection. The
[design](../superpowers/specs/2026-11-12-capture-format-compatibility-design.md)
limits this increment to a preventive compatibility baseline. All production
writes remain v1; there is no selector, new draft field, migration, schema version,
sidecar, ownership policy, financial activation or server change.

## Behavior and proof

The reader distinguishes supported v1, unsupported future payload with a fixed
validated lifecycle envelope, and corrupt/unclassified data. Only the unsupported
case gains preservation and explicit refusal. It is never restored, down-converted,
overwritten or submitted. No current invalid v1 payload becomes valid. Absolute
TTL and exact-generation explicit cleanup retain the approved lifecycle contract;
unknown payload meaning is never consulted. Unsupported clock rollback preserves
bytes and reports unresolved cleanup instead of inferring expiry.

Three initial kernel regressions failed as expected: unknown payload deletion,
generic refusal and premature expiry. A fourth clock-rollback regression failed
before its preservation guard. A fifth real-runtime regression exposed a missing
leave warning for opaque retained input; it failed before metadata-only leave
protection was added. Historical compatibility controls already passed.
The fixture contains exact original validator/store bytes pinned by SHA-256 to
cc18a203 and independently transpiled, not a modern parser pretending to be old.
The actual old reducer refuses the payload, then its maintenance deletes it. The
actual v8 database class reopens v9 with installed Dexie 4.4.4. These are retained
counterexamples, not successes of a safe old-reader rollout.

Focused tests additionally cover exact-byte/TTL preservation, overwrite/protect/
settle/enrollment refusal, ordinary v1 roundtrip through the old reader, corrupt
metadata/JSON controls, explicit cleanup and aborted transactions. A real runtime
composition proves same-session offline reload preserves opaque bytes, shows the
compatible-version message, blocks capture, emits no new journal/network effects,
and explicitly purges on logout. App guard cancellation preserves bytes, confirmed
workshop discard removes only the exact generation, and a stale generation keeps
the newer payload with an honest cleanup warning. Unsupported refusal carries only
validated checkpoint metadata for these existing explicit actions, never payload.
The expanded focused suite passes 22 tests. This uses fake IndexedDB, not physical
recovery. The earlier aggregate run predates the leave-guard correction and is
superseded, not qualification of the final source.

## Qualification and rollback boundary

Final frozen local aggregate: **21 passed, zero failed, five environment blockers**
(exit 0 with `--allow-blocked`, partial qualification). Frontend **1,505 passed**,
zero failed/skipped; Python **6,113 passed, 685 environment skips, 12 warnings**.
API client 1 passed. Repository suite 205 passed before final documentation stamp;
final documentation rerun is retained with the receipts. Lint, typechecks,
397-file Python formatting, mypy 126 files, OpenAPI/generated contracts, PWA build
and pinned legacy App/SW build pass. Independent review accepted the source and
metadata-only departure correction without blocking findings.

The five blockers are PostgreSQL test URL, unavailable Docker, unavailable psql,
the verifier's file-based IndexedDB browser probe under managed navigation policy,
and missing destructive E2E database URL. The policy permits HTTP/HTTPS exceptions;
the probe result is not a claim that all HTTP navigation is forbidden. Native E2E
is **not executed**: 140 browser tests collected, including the authored future-
payload reload/cancel/explicit cleanup journey, and its E2E TypeScript passes.
Fake-IDB historical-reader proof is not real old-app/native browser qualification.
The frozen source manifest and complete aggregate receipt are retained; only this
documentation stamp follows qualification. The interrupted earlier aggregate and
five RED regression receipts remain separately labeled, never final evidence.

Before future activation, reverting to historical v8 is safe only because this
candidate still writes exact v1. After activation of a new payload, rollback must
use the compatibility-aware baseline or newer. Excluding pre-baseline offline
clients is still an unresolved release gate; time, a version bump, service-worker
update or a feature flag does not prove exclusion. The existing-bicycle selector
remains blocked. This increment does not claim complete backward safety.

The historical branding timeout remains unresolved. Physical T1–T8/R01-T035,
M2/capacity, actual restore and quote gates remain open. SPENT40927223929 and
UNKNOWN41011497919 are unchanged. No publication, merge or deployment is authorized.
