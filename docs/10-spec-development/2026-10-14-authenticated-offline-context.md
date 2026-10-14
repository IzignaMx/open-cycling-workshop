# Authenticated offline context increment

Status: implemented_pending_evidence for real PostgreSQL contention and exact-head
hosted qualification. This is an unactivated server prerequisite, not release
qualification or permission-administration rollout.

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

Final local source qualification:

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
