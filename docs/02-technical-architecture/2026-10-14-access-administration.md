# Local account administration, protected owners and audit history

Status: Accepted for the bounded server/API increment. Runtime qualification is
tracked separately in the [increment specification](../10-spec-development/2026-10-14-access-administration.md).

## Context and sequencing

Foundation ADR-013 requires deny-by-default capability/scoped authorization.
FR-IAM-001, FR-IAM-003–006 and FR-IAM-008 need usable local account administration,
but an administrative role label must never become an authorization shortcut.
The existing bootstrap account has wildcard grants and one location. Promoting
it automatically to an organization-wide owner would silently widen its scope
and break the current PWA's non-null-location assumption.

This work follows the [change-feed read-authorization prerequisite](2026-10-14-sync-read-authorization.md),
PR #26, merged at `c1e2230` after all seven checks passed. This branch includes
that main ancestry, runtime/bootstrap PR #25 merged at `0342799` and migration
target-isolation fixes. The initial hosted administration checkpoint is recorded
in the increment specification; each later integration head requires fresh CI.
Visual/theme changes remain independent.

Account administration is the explicitly prioritized bounded increment before
the remaining quote workflow. Inventory migration `0007` remains immutable.
The next actual migration is `0008_identity_administration`, with
`down_revision = "0007"`; future quote persistence moves to `0009`, following
`0008`. This supersedes the earlier quote-only reservation of `0008`. Do not add
an empty reserved migration, a second Alembic head, or rewrite applied history.

## Account and grant model

An account belongs to exactly one organization and either one location or the
existing explicit organization-wide scope (`location_id = null`). No
multi-organization membership, global identity or SSO is introduced.

Role bundles are server-defined starter snapshots. A create or grant-change
request selects exactly one of `role` or `capabilities`; the server resolves and
stores one concrete capability set. They are not combined. Unknown roles,
unknown capabilities and new wildcard grants are rejected. Existing wildcard
accounts remain compatible, but their administrative authority is interpreted
only over the currently implemented capability catalog. New modules do not
implicitly become supported administration capabilities through a label.

The implemented business catalog is:

- `customers.read`, `customers.write`
- `bicycles.read`, `bicycles.write`
- `orders.read`, `orders.write`
- `inventory.read`, `inventory.write`
- `sync.pull`, `sync.push`

The implemented administrative catalog is:

- `users.read`, `users.write`, `users.grants.write`
- `users.sessions.revoke`, `users.credentials.reset`
- `locations.read`, `locations.create`

| Starter bundle   | Concrete snapshot                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------------- |
| `Owner`          | All implemented business and administrative capabilities                                          |
| `Administrator`  | All implemented capabilities except `locations.create`                                            |
| `Manager`        | All business capabilities and `locations.read`                                                    |
| `Mechanic`       | All business capabilities except `customers.write` and `inventory.write`, plus `locations.read`   |
| `Reception`      | All business capabilities except `inventory.write`, plus `locations.read`                         |
| `Sales`          | All business capabilities except `orders.write` and `inventory.write`, plus `locations.read`      |
| `Viewer`         | `customers.read`, `bicycles.read`, `orders.read`, `inventory.read`, `sync.pull`, `locations.read` |
| `TechnicalAdmin` | Empty snapshot                                                                                    |

`TechnicalAdmin` receives no business, sync, user-administration, credential or
invented diagnostic/backup capability by default. Existing public health and
self-session endpoints do not imply an administrative grant. The `Sales` name
does not claim a POS or payment module exists.

### Protected owner designation

`is_owner` is persisted independently of the role selection. Choosing the
`Owner` bundle grants its snapshot; it does not designate an owner. Designation
requires explicit `is_owner = true`, an organization-wide scope and the complete
implemented concrete catalog. A designated owner is therefore recovery-capable.
Owner-target administration and designation/removal require a persisted owner
actor as well as the applicable capabilities. Owner status never bypasses scope
or capability checks.

Once owners are established, a successful mutation must leave at least one
active recovery-capable owner. Deactivation, removal of owner status, narrower
scope or grant changes cannot evade this invariant. Self-demotion/deactivation
may succeed only when another active owner remains; security changes revoke the
caller's own sessions in the same transaction. Merely creating a non-owner with
the `Owner` grant bundle does not satisfy the last-owner invariant.

## Authorization and concurrency

All account, credential, session and location mutations lock the Organization
row before loading/locking actors or targets. The explicit first-owner command
uses the same organization lock. This simple per-organization serialization is
deliberate for a small workshop and avoids unlocked cross-row owner counts.

After any wait for the lock, reload the persisted actor, active state, session
version and current grants/scope; reauthorize against the token's authority.
Then reload the target and check its required `expected_version`. A request
authorized before waiting must not commit after the actor was revoked while it
waited. Use the consistent organization-then-user lock order.

For every administrative target change:

1. Derive actor and organization from the authenticated persisted identity.
   Client-supplied organization, actor or generated-ID overrides are invalid.
2. Require the operation's capabilities. Display-name changes need
   `users.write`; permission/scope/owner changes additionally need
   `users.grants.write`; reset and revocation use their dedicated capabilities.
3. Check both the old and proposed target scope and concrete grants. The actor
   must possess every delegated capability and cannot administer a target that
   already has privileges beyond the actor. Reset, deactivate and revoke must
   not become indirect account-takeover or denial-of-service bypasses.
4. A location-bound actor cannot administer an organization-wide account or
   move an account into or out of another location. An organization-wide actor
   is still limited to its own organization. Check location tenancy before use.
5. Apply owner-target and last-active-owner guards, then mutate and append one
   audit event in the same transaction. Any failure rolls back both effects.

Two concurrent attempts to remove the final two owners must yield one success
and one conflict, leaving one active owner. SQLite tests cannot establish this
PostgreSQL row-lock behavior.

## Versions, credentials and connected sessions

`version` is a positive account revision used by required `expected_version`
preconditions on PATCH, administrative password reset and explicit session
revocation. Stale preconditions fail with 409 without mutation or success audit.
Each successful account update increases it, including a name-only update.

Status, owner designation, scope, grant and credential changes, and explicit
revocation, also atomically increase the positive `session_version`. Name-only
updates do not revoke sessions. Self password change verifies the current
password, writes an Argon2id hash and revokes all sessions including the current
one. It does not log the caller in again. Self logout-all uses the same
serialized/atomic version discipline so concurrent revocations are not lost.

Passwords are accepted only through the credential fields or the local
password-file command boundary. Passwords, hashes, bearer tokens, complete
request bodies and credential-derived fingerprints must never enter user
responses, audit snapshots or logs. Validation failures must be redacted too:
`SecretStr` alone does not prevent Pydantic error `input` or validator `context`
from exposing a secret. Reject malformed credential requests without returning
or logging their body/input/context. Correlation for sensitive identity and
administration requests is generated by the server, not copied from an
untrusted request header. Ordinary public health requests retain the historical
supplied-ID behavior; this is not a global request-ID contract change.

## Durable audit boundary

Every successful mutating administration command emits exactly one append-only
event, including self logout-all, self password change and first-owner setup.
Record organization, actor/target identity where applicable, target type, action,
UTC timestamp, server-generated correlation and safe before/after state.
Account snapshots contain grants, scope, active/owner flags and versions; omit
username/display-name PII and all credential-derived values. Location events
identify the created location in safe event data without pretending it is a
user foreign key. CLI setup records the local operator boundary without
inventing an authenticated API actor.

The audit insert and state change commit together. An audit insert failure must
roll back the account/location change. Denied, stale or invalid commands must
not emit success events. This is not comprehensive login/failure audit or a
security-monitoring product.

PostgreSQL database guards reject audit UPDATE, DELETE and TRUNCATE, including
bulk operations. Tenant composite foreign keys prevent cross-organization
actor/target references. SQLite surrogate guards cover UPDATE/DELETE and reject INSERT OR REPLACE
collisions so implicit replacement cannot bypass append-only history. There is no audit read/export/update/delete HTTP API in this
increment. Database-owner privileges can alter schema/guards; this is an
application/database integrity boundary, not protection against a hostile DBA.

## Opt-in first-owner establishment and migration

Migration 0008 adds `is_owner = false`, `version = 1`, positive version checks,
an owner-organization-scope check and the audit table/guards. Existing accounts,
password hashes, active states, grants, locations and session versions are
preserved. It neither promotes wildcard users nor creates owners. Invalid
legacy session versions block the migration for reviewed remediation rather
than being silently normalized.

The only initial-owner path is an explicit local operator invocation:

```text
ocwpctl access create-first-owner --organization-id ORGANIZATION_ID --username OWNER_USERNAME --display-name OWNER_DISPLAY_NAME --password-file PASSWORD_FILE
```

It creates a separate new organization-wide account with explicit owner status
and the full concrete catalog. It never promotes/reuses the bootstrap account,
changes its scope, creates an organization or changes the existing
`bootstrap admin` command. Under the organization lock it refuses if **any**
owner record exists, including an inactive owner. Duplicate usernames and
invalid organization/credential input fail without side effects. A rerun must
not create another owner or duplicate a success audit.

This is a one-time elevation boundary, not password recovery, owner resurrection
or a rebootstrap backdoor. After establishment, owner changes use authenticated
API guards. Loss of every usable owner credential requires a separately reviewed
recovery procedure; rerunning this command or clearing owner flags is not one.
This increment does not invoke the command against a real installation.

Upgrade operations require a verified backup, a coordinated no-server-writes
window, migration and post-upgrade checks. If a guard blocks, preserve evidence
and reconcile the affected records through a reviewed history-preserving plan;
never delete audit/history rows or bypass constraints. A schema downgrade that
would remove owner metadata/audit history is not a routine rollback. Prefer a
compatible application rollback or reviewed restore/forward fix with explicit
accounting for post-backup changes. See the
[operator checklist](../../MANUAL-ACTIONS-CHECKLIST.md#2026-10-14--local-account-administration-operator-gates).

## Explicit product and rollout boundaries

This is an online server-administration API slice. It does not change the PWA,
Dexie schemas, Compose configuration, deployment, theming or the bootstrap
workflow. No user administration screen, organization-wide workshop selector,
SSO, MFA, custom-role designer, user deletion, username rename, location
deletion, location-data migration or audit HTTP API is included. Organization-wide
owners use the API until the selector UI exists.

**End-user rollout is gated on browser isolation and reconciliation.** Current
browser data/cursors are shared by organization/location, rather than safely
partitioned by user, capability snapshot and scope. Connected token revocation
does not remove previously cached data. A user switch or authorization change
needs a defined authorization epoch, safe cached-data isolation and a scoped
resnapshot/backfill so older newly allowed rows are not skipped by an existing
cursor. Preserve and reconcile pending mutations; do not clear IndexedDB or
discard queued writes as a shortcut. Prove downgrade, expansion, user-switch,
reload/offline and reconnect behavior before exposing per-user administration
as a complete end-user workflow.

The broader MVP and release remain partial. Existing device, accessibility,
security, runtime, backup and other qualification gates are unchanged.
