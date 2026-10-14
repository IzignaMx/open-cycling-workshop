# Change-feed read authorization

## Scope and traceability

This prerequisite enforces FR-IAM-004, SEC-002, Security/Privacy §§8–10 and §18
(server-side authorization and cross-tenant denial), and QA §23 authorization
verification. It preserves the existing Offline/Local First and sync protocol
baseline. The [authorization/cursor decision](../02-technical-architecture/2026-10-14-sync-read-authorization.md)
describes the bounded behavior and future permission-change resnapshot requirement.

## Acceptance

1. A location-scoped user omitting `location_id` sees only their own location.
2. Explicit foreign-location access is denied, including with wildcard grants.
   Organization-wide accounts remain bounded to their own organization.
3. Every returned entity requires its existing read capability in addition to
   `sync.pull`. Write-only grants, unknown capabilities, and unknown entity types
   expose no entity payload. Wildcards apply only to known mapped entity types.
4. Authorization predicates precede pagination. Interleaved hidden rows cannot
   replace visible rows, skip authorized later records, or set `has_more` by
   themselves. Empty pages retain the caller's cursor.
5. Reads use the intersection of persisted account and token grants. Existing
   tokens immediately lose revoked reads; newly persisted grants do not expand
   a token issued without them.
6. Existing sync application/idempotency/conflict behavior and public OpenAPI
   contracts remain intact. Generic `authorize` semantics are unchanged.

## Evidence

- Base: `98394826884020d9de2498cab551120087dd5334`.
- `services/platform/tests/sync/test_sync_read_authorization.py`: 16 synthetic,
  persisted-principal API cases. Before implementation: 13 failed, 3 passed.
  After implementation: all 16 passed.
- Focused sync/bicycle-sync/service-order-sync tests: 36 passed.
- Complete Python suite: 492 passed, 8 PostgreSQL tests skipped because
  `OCWP_TEST_DATABASE_URL` is not configured. SQLite/TestClient evidence does not
  establish PostgreSQL runtime behavior.
- Ruff lint/format and mypy (69 source files): passed.
- OpenAPI and generated TypeScript contract checks: passed without regeneration.
- Independent review: no implementation defects; sync/authorization checks
  passed (33), entire platform test directory passed (446, 8 PostgreSQL skips),
  and reviewed scope/cursor documentation matched the implementation.
- Aggregate qualification: 21 checks passed, zero failures, five environment
  blockers. This includes 72 frontend core tests, one API-client test, static
  checks, runtime HTTP smoke, and production PWA build. PostgreSQL integration,
  Docker, psql, browser E2E database setup, and the managed Chromium navigation
  policy remain blocked. Browser/device behavior is not inferred from the build.
- Hosted verification remains pending publication authorization and exact-head
  CI. Local evidence describes the reviewed working tree, not a published SHA.

No schema/data migration, credential changes, deployment, role-admin API or
client-cache reset is included. Existing physical-device, PostgreSQL/browser,
security, and operational release gates remain open where evidence is absent.
