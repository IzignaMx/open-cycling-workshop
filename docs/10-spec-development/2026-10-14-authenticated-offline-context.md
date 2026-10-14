# Authenticated offline context increment

Status: first-head hosted verified; actual-main reconciliation pending its own
exact-head hosted qualification. This is an unactivated server prerequisite, not
release qualification or permission-administration rollout.

Base: merged effective-authority main `f87205157e298f5c1c7c3f08d024fe822d84582b`.
See the [accepted contract and decision](../02-technical-architecture/2026-10-14-authenticated-offline-context.md)
for traceability, epoch serialization, error behavior and deferred boundaries.

## Acceptance

- Additive authenticated `GET /api/v1/auth/context`, no-store on successes/errors.
- Original validated token survives organization→user lock waits; current persisted
  account/session and expiry are rechecked after both locks.
- Literal grants intersect before normalization to known capabilities. Empty,
  unknown, write-only and asymmetric wildcard grants remain least-privilege.
- Concrete same-tenant location selection is mandatory for organization scope;
  bound sessions may omit it without skipping existence checks.
- Durable epoch excludes token renewal/display/selection; includes effective scope,
  grants, persisted session version and policy revision.
- Lease ends at signed expiry or eight hours, whichever comes first. Integer JWT
  times, signature/issuer and final pre-response expiry are checked.
- Server realm and snapshot protocol remain null. No Host trust, activation,
  migration, journal changes or deployment.
- Closed generated contracts preserve literal protocol/policy types; the generator
  now handles JSON Schema `const` rather than widening it to string/number.

## Evidence

Initial regression execution: 30 failed before implementation (missing context
endpoint and validated-clock API). Initial generated literal contract regression:
1 failed, 1 passed before adding `const` handling. These logs are local evidence;
no PostgreSQL/browser execution is inferred from them.

First-head local source qualification (historical, before hosted evidence):

- 43 context unit/API tests and 2 TypeScript contract tests pass.
- Full Python suite: 869 passed, 81 explicitly skipped; the 16 new real
  PostgreSQL tests are among those skips.
- Ruff check/format across source/tests/scripts, mypy (77 source files),
  deterministic OpenAPI/client drift checks, API-client TypeScript typecheck,
  repository contract and changed-document/generated-file formatting pass.
- Independent final review: 70 focused tests pass, 16 PostgreSQL skips and no
  blocking findings. Review caught the generic-500 no-store gap: one regression
  was observed failing before the endpoint-only sanitized-error correction.
  Added tests verify rollback, correlation and no private exception/token logging.
  Cancellation/BaseException and unrelated-route errors retain existing behavior.

These results use existing installed tools. No fresh frozen install, aggregate
browser run, deployment or PostgreSQL execution is claimed.
The new PostgreSQL suite contains 16 cases using a dedicated-target isolated-schema
fixture and observable `pg_stat_activity` lock waits, across both organization
and user-row barriers. It covers revoke/disable/incompatible scope/grant removal,
grant widening/location narrowing and expiry at or after the signed deadline.
Without `OCWP_TEST_DATABASE_URL` these cases explicitly skip; SQLite unit tests do
not establish their contention behavior.

## Operations and remaining gates

No new environment setting, secret, database migration or account is required.
The current server realm is intentionally null until a separately reviewed trusted
canonical-base configuration exists. Production browser bindings must supply their
verified configured endpoint realm. The previous realm's journal must be retained
on moves; automatic retargeting/replay is not authorized by context equality.

The manual checklist records the missing real PostgreSQL proof and continued
baseline/activation/browser/device/restore gates. Native browser access remains
unavailable in this environment; no bypass or browser proof is claimed. Existing
local tools are reused, not a claimed new frozen dependency installation.

## First-head hosted proof and actual-main reconciliation

[PR #32](https://github.com/IzignaMx/open-cycling-workshop/pull/32) head
`2a7bd701429e08b786e8c7c3da2927b344cb00b9` and tested synthetic merge
`0f032515a031e93869b586993ce3428dc81b5346` share the reviewed tree
`158b7489b0e2167f2d925031c45ac0a1820bfbcd`, verified from Git metadata. Its
parents are main29 `f87205157e298f5c1c7c3f08d024fe822d84582b` and the PR head.

- [CI 38562738320](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38562738320)
  passed all 27 checks with zero blockers. Downloaded qualification artifact
  `11893288642` records that exact synthetic merge and Python 3.13.16.
- Full Python execution passed 947 tests, including all 16 context PostgreSQL
  organization/user-lock wait cases on PostgreSQL 18.4. The three unrelated skips
  are host restore without matching major-18 clients, TRUNCATE on SQLite, and
  INSERT OR REPLACE on PostgreSQL. The separate real-stack run below covers its
  own major-18 backup/restore path.
- Browser execution passed 23 direct cases, ten retry-free sync repetitions and
  23 aggregate cases. The 100k IndexedDB check passed with 39,624.9 ms writes and
  146.6 ms count/sample reads. This is hosted Chromium, not physical-device proof.
- [Local runtime 38562738314](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38562738314)
  passed all 11 checks, including actual-edge offline/reconnect convergence,
  restart persistence, PostgreSQL backup/restore and credential-free logs.
  Downloaded artifact `11892912835` records the same tested merge. Three ARM64
  image builds passed without claiming physical hardware qualification.
- [Security 38562738322](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38562738322)
  and [DCO 38562738313](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38562738313)
  passed on their first attempt. No product correction or workflow rerun was needed.

The final reconciliation true-merges actual main31
`6ad6acc146ec47b7b6bd7bf82b6c850898fb5c0e` onto the published PR32 head, retaining
both histories. It preserves context/security/app/generated-contract source from
PR32 and isolated kernel, ordered feed, all phase-separated browser artifacts,
order baseline handshake and twenty retry-free repetitions from main31 exactly.
The only conflicts were additive documentation sections; both were retained.
There is no additional product change, migration, deployment or client activation.

The first-head browser artifacts predate main31's phase-separated output fix; no
claim of retained per-phase artifacts is made for that historical run. The
combined candidate retains the corrected direct/repeat/qualification directories
and requires its own fresh hosted evidence. The final combined local aggregate passed 21 checks with zero failures and five
explicit environment blockers: dedicated PostgreSQL/E2E URLs, Docker, psql and
managed-browser navigation. Python passed 1,021 tests with 91 explicit skips;
158 frontend core tests and one API-client test passed. Static checks, contracts,
production PWA build and repository validation passed. The existing toolchain
was reused; no fresh frozen installation or local browser proof is claimed.
Independent reconciliation review confirmed the exact parent-source union and
passed 388 focused identity/feed/contract tests with 82 explicit skips, plus
Ruff/format, contract drift and conflict/whitespace checks, without findings. Earlier green evidence
does not qualify the new combined tree, and all unactivated-client, physical,
restore-operation and manual rollout gates remain explicit.
