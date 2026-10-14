# Local users, roles and workshop administration: bounded server increment

Status: implemented pending hosted PostgreSQL evidence and prerequisite
integration. Local verification of the bounded server slice is recorded below;
this is not a declaration of release qualification.

## Scope and traceability

This increment implements the server boundary for local user creation/listing,
active status, concrete grant snapshots, session revocation, credential changes
and organization/location administration. It contributes to FR-IAM-001,
FR-IAM-003–006, FR-IAM-008, SEC-001–003, SEC-005 and OFF-009. Existing
FR-IAM-002 authentication remains the foundation. Credential reset is a bounded
administrator-assisted path; it does not fulfill every topology's recovery
workflow. Authentication/failure audit, MFA (FR-IAM-007), offline account
administration and complete end-user permission UX remain outside this slice.

Normative design: [administration ADR](../02-technical-architecture/2026-10-14-access-administration.md),
Foundation ADR-013, Security/Privacy §§7–10 and §18, Operations §§31–36.

Dependency: PR #26 change-feed read authorization, local base `0a9c935`, must be
integrated before this dependent increment. PR #25 runtime/bootstrap and visual
theme work are independent; this slice does not claim their completion. The
approved sequence prioritizes access administration before the remaining quote
workflow: identity migration `0008` follows `0007`, and future quote persistence
is reserved as `0009`, following `0008`. Preserve one linear migration history.

## HTTP contract

All routes below use persisted authentication, deny by default, derive tenant
and actor server-side and return no credential material. Bodies forbid unknown
fields. User responses contain `user_id`, `organization_id`, `location_id`,
`username`, `display_name`, `capabilities`, `is_active`, `is_owner` and `version`.
The response does not expose `password_hash` or session tokens.

| Route                                           | Required grant and contract                                                                                                                                                                    |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/v1/admin/roles`                       | `users.read`; returns `roles` (name/concrete capabilities) and the implemented `capabilities` catalog                                                                                          |
| `GET /api/v1/admin/users`                       | `users.read`; actor-scoped keyset page, optional `active` filter                                                                                                                               |
| `POST /api/v1/admin/users`                      | `users.write` and `users.grants.write`; username, display name, explicit location or null, initial password, exactly one role/snapshot, optional explicit `is_owner`; 201 with created account |
| `PATCH /api/v1/admin/users/{id}`                | `users.write`; required `expected_version`, at least one permitted change; scope/grant/owner changes additionally require `users.grants.write`                                                 |
| `POST /api/v1/admin/users/{id}/revoke-sessions` | `users.sessions.revoke`; required `expected_version`, target scope/subordination checks and audited version increase                                                                           |
| `POST /api/v1/admin/users/{id}/reset-password`  | `users.credentials.reset`; required `expected_version` and `new_password`, target scope/subordination checks; Argon2id and all-session revocation                                              |
| `POST /api/v1/auth/change-password`             | Authenticated self only; `current_password` and `new_password`; revoke every session, including this one, with no automatic login                                                              |
| Existing `POST /api/v1/auth/logout-all`         | Authenticated self only; serialized/atomic version increase and one success audit                                                                                                              |
| `GET /api/v1/locations`                         | `locations.read`; actor-scoped keyset page                                                                                                                                                     |
| `POST /api/v1/locations`                        | `locations.create` and organization-wide actor scope; validated name, server-generated UUIDv7/organization; 201 with created location                                                          |

PATCH permits only `display_name`, `is_active`, `location_id`, `is_owner` and one
of `role`/`capabilities`, plus the required precondition. Omission preserves a
value; explicit null location requests organization-wide scope and is subject
to authorization. Null is not a substitute for a valid display name, status or
owner flag. No username rename, account deletion, organization override or
location deletion/movement of business data is supported.

`role` and `capabilities` are mutually exclusive alternatives. The server
expands a role into a concrete stored snapshot; a later explicit snapshot
replaces the prior snapshot, not an implicit additive merge. `is_owner` remains
a separate protected designation. The starter matrix and full catalog are in
the ADR; `Administrator` excludes `locations.create`, and `TechnicalAdmin`
grants nothing by default. New wildcard/unknown grants are invalid.

User and location lists accept `after_id` and `limit` (default 50, range 1–200),
order by ID, and return `{items, next_cursor}`. Apply tenant, effective location
and the optional user `active` filter before the keyset predicate/lookahead.
Use a returned non-null `next_cursor` as the next request's `after_id`; null
means no further matching row was found. These are bounded traversal cursors,
not snapshot isolation across concurrent inserts/changes or a cross-tenant
authorization credential. A location-bound user sees only users/locations in
that location and never organization-wide accounts.

Expected error classes: 401 for absent/invalid/revoked authentication; 403 for
capability/scope/subordination denial; 404 for unavailable target as appropriate
without exposing foreign-tenant records; 409 for stale account versions,
normalized-username conflict or last-owner conflict; 422 for invalid strict
payloads; 503 for a sanitized database command failure. Preserve the existing
error envelope. Credential validation responses
and logs must omit request body/input/context, including too-short, too-long,
wrong-type and extra-field cases, including untrusted extra-property names.
Names, scope IDs, paths and cursors reject PostgreSQL-incompatible NUL values;
username bounds apply after lowercase/trim normalization. New passwords contain
12–1024 characters; login accepts the existing 1–1024-character credential range. Sensitive identity/administration requests use
server-generated `X-Request-ID` correlation; ordinary public health requests
retain historical supplied-ID behavior.

## Command and storage acceptance

1. Normalize username once at the identity boundary; duplicates within one
   organization return conflict. Account creation yields UUIDv7, version 1,
   active status and exact resolved grants. New credentials authenticate using
   Argon2id and only those grants.
2. Deny foreign organization/location targets, organization-wide targets from a
   location-bound actor, old or new grants exceeding the actor, client actor or
   tenant overrides, wildcard/unknown grants, and owner-target changes by a
   non-owner. Reset/revoke/deactivation must not bypass subordinate-target rules.
3. Acquire organization lock, reload actor/session/scope/grants, reload target,
   check `expected_version`, and authorize both old and new target before
   mutation. Security checks performed before waiting are insufficient.
4. PATCH/reset/revoke reject stale versions with zero mutation/success audit.
   Successful account changes bump `version`; security changes and explicit
   revocation also atomically bump `session_version`. Name-only changes preserve
   valid sessions. Disabled users cannot log in; revoked tokens cannot act.
5. Owner designation requires organization-wide scope, all implemented grants
   and a persisted owner actor. Leave at least one active recovery-capable owner
   after an established organization mutation. Self-demotion/deactivation loses
   sessions when allowed; two concurrent removals leave one owner.
6. Self password change checks the old password, rejects it after success,
   accepts the new password and invalidates every previous token, including the
   current one. Administrative reset and logout-all use equivalent atomic
   revocation discipline. Do not record passwords or credential-derived values.
7. Exactly one durable safe audit event commits per successful mutating command;
   failure to append audit rolls back the mutation. Database UPDATE/DELETE and
   PostgreSQL TRUNCATE guards protect history. Tenant composite FKs apply to
   actor/target identities. There is no audit HTTP endpoint.
8. Locations are created only by an organization-wide actor with the explicit
   grant; list/filter/pagination never escapes scope. No business records move.

## First-owner CLI and migration acceptance

The opt-in command is:

```text
ocwpctl access create-first-owner --organization-id ORGANIZATION_ID --username OWNER_USERNAME --display-name OWNER_DISPLAY_NAME --password-file PASSWORD_FILE
```

- It creates a separate new account in the named existing organization with
  null location, explicit `is_owner = true` and the full concrete catalog.
- It locks the organization and refuses if **any** owner record exists, active
  or inactive. A retry/race must not create a second first owner. It is not a
  rebootstrap or lost-owner recovery path.
- Existing bootstrap account, scope, grants, credentials and the
  `ocwpctl bootstrap admin` contract remain unchanged. No implicit promotion or
  existing-account promotion option is included.
- Passwords are read from a protected local file, never a command-line password
  argument. Success output/audit/errors contain no password, hash or token.
  Invalid organization, duplicate username or invalid credential has no success
  effect. The command is not run against a real installation by this increment.
- Alembic `0008_identity_administration.py` has `revision = "0008"` and
  `down_revision = "0007"`. Existing accounts gain only `is_owner = false` and
  `version = 1`; existing password hash, active state, grant snapshot, scope and
  session version are preserved. Positive version and owner-scope checks apply.
- Prove empty database → head and a representative `0007` snapshot → head. An
  invalid legacy session version blocks for review without deleting, silently
  correcting or promoting accounts. Quote persistence next uses `0009`.

## Verification and evidence

Local implementation checkpoint on the branch based at `0a9c935`:

- Full Python suite: **670 passed, 59 skipped**. The skips are 58 PostgreSQL
  cases unavailable in this environment and one PostgreSQL-only TRUNCATE case
  intentionally inapplicable to SQLite. Do not treat skips as passing evidence.
- Administration HTTP suite: 98 passed. First-owner CLI: 10 passed. New identity
  migration tests: 54 passed with 29 dialect/environment skips; administration
  PostgreSQL module: 16 safety checks passed, 22 real PostgreSQL cases skipped.
- TDD: initial missing-endpoint run 22 failed; mutation/redaction run 43 failed;
  first-owner CLI run eight failed. Subsequent credential, Unicode/NUL and
  file-backed-URL regressions were observed failing before correction. Removing
  the protected-owner target guard made four isolated abuse cases fail; restoring
  it made all six owner-guard/inactive-owner regressions pass.
- Independent security review found and verified the fix for CLI unknown-argument
  password echo, required isolated protected-owner coverage, and reconciled the
  database-failure status assertion. Final independent identity-directory run:
  177 passed, 51 skipped; contracts and diff checks passed, no unresolved defect.
  Two subsequent fixture-only URL-file isolation regressions also pass locally.
- Ruff lint/format and mypy (75 source files) pass. Repository, OpenAPI and
  generated TypeScript contract checks pass. Frontend core 72 and API-client
  core one pass; TypeScript checks, ESLint, Prettier and production PWA build pass.
- Aggregate local qualification: **21 checks passed, zero failures, five
  environment blockers**, recorded in `ocw-access-admin-qualification.json`.
  Blockers: no PostgreSQL test URL/server, Docker, psql, browser E2E database;
  the managed Chromium navigation policy also blocks the 100k browser spike.
  That policy was respected. No browser execution is claimed.
- No PostgreSQL server or Docker runtime is available locally. SQLite and SQL
  compilation are surrogate checks, not row-lock/migration runtime evidence.
- Exact-head hosted PostgreSQL 18.x qualification and reconciliation with the
  final prerequisite remain pending. Earlier PR/release results do not qualify
  the new migration or lock semantics. No real installation was modified.

Required PostgreSQL coverage includes simultaneous last-owner removals,
first-owner races, actor revocation while waiting for the organization lock,
optimistic-version conflicts, normalized-username collisions, atomic
mutation/audit rollback, tenant FKs, database audit immutability and both
migration paths. Use only isolated disposable `_test`/`_e2e` databases; preserve
ordinary/production databases. Attach exact SHA/run/artifact evidence when run.

## Operator gate and unresolved product work

The [manual checklist](../../MANUAL-ACTIONS-CHECKLIST.md#2026-10-14--local-account-administration-operator-gates)
contains backup, no-server-writes migration, blocked-version reconciliation,
explicit first-owner setup and smoke/recovery requirements. No real-install
upgrade, first-owner invocation, deployment or release is performed by this
implementation.

Before end-user rollout, partition/isolate browser state by user, capabilities
and scope; define authorization-epoch cursor invalidation, resnapshot/backfill
and reconciliation of pending writes. Cover user switching, grant contraction,
grant expansion, location changes, reload/offline and reconnect. Server token
revocation alone neither erases cached data nor backfills records older than
the existing cursor. Never delete IndexedDB or pending mutations to pass this
gate. Organization-wide owners remain API-only until the workshop-selector UI
exists. No App/Dexie/Compose/theme change is part of this slice.

The user/role/location API does not complete the broader MVP, the quote
workflow, the physical Windows/Android qualification or V0.1/V1 release gates.
