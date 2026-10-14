# Connected account administration in the production PWA

Status: implemented; exact integrated hosted qualification pending.
Date: 2026-10-14. Base: merged main38
`79cb4055aeb34344f2182d77e244c8187e9bb71b`, tree
`9a26bebbd05f54508b3432b28759a44878d17d2e`.

## Boundary and authority

This finite slice adds Usuarios y permisos, Ubicaciones and Mi sesión using the
existing server endpoints and generated DTOs. It implements no custom-role CRUD,
user deletion/rename, location edit/delete, audit reader, recovery, invitation,
shared branding, backend grant/API, dependency or schema. SQL remains 0010 and
authenticated local schema remains 6; future quote reservations remain SQL0011
and local7. AGPL-3.0-only, DCO, FR-IAM-001/002/003/004/005/006/008,
SEC-001/002/003/005/006 and OFF-003/005/007/009/012 remain in force.

WorkshopController remains the sole session and operational owner. Its separate
volatile account snapshot is non-secret and never means an operational partition
is ready. Explicit bounded `/auth/me` verification admits account controls before
workshop selection, including zero locations, missing locations.read, missing
sync.pull and empty grants. Account-only login first blanks and locks any previous
operational source. It does not manufacture an offline ticket, baseline or lease.

Captures bind the exact immutable saved session, runtime/network/account
generations and current operational source/ticket/context when present. Transient
request captures contain a bearer token; observable UI state never does. Account
invalidation aborts requests and synchronously notifies feature subscribers before
React can reuse personnel rows or credential controls. Cancel, held, takeover,
offline (including selector), logout, workshop transition, automatic probe
revalidation and disposal invalidate account access. Existing automatic probes
retain their original lease, deadline, backoff and single-flight semantics.

Unchanged-authority account refresh does not rotate operational ownership. A
validated name-only update changes only the name and the source's exact saved
snapshot in one synchronous boundary. Authority changes lock the old context and
remove its remembered admission; old offline authority cannot be resumed merely
by reopening account administration.

## Requests, permissions and uncertain results

Administration is connected-only, never journaled, cached, automatically retried
or replayed. All commands send write protocol1. Transports enforce exact URLs,
closed and bounded response shapes, no-store including bodyless success,
request/body deadlines, currentness after headers/body and safe local error text.
Current 401 clears only its exact matching session; current 403 removes account
admission until fresh verification. Late failures cannot affect replacement login.
No selected operational workshop is sent as an administrative scope override.

Role bundles are replacement snapshots, not authority or owner identity. The
server catalog and effective grants determine affordances. Write does not imply
read; unknown grants remain visible but block unsafe editing; legacy wildcard
hints expand only within the fetched catalog. Old and proposed target grants and
scope must be subordinate. Owner designation comes only from a consistent,
unfiltered current actor row. A bounded explicit one-page lookup establishes
unknown/owner/non-owner; incoherent self evidence requires fresh verification.
The server still decides authorization, last-owner rules and versions.

Editors capture immutable target rows/expected_version. Reopening explicitly
creates a new editor instance; refreshing a directory does not silently rebase an
old draft. PATCH contains actual changes only. Pages, catalogs and owner lookup
have independent result generations. Cursor history is volatile and bounded.

Self-security review explains session closure and pending forms. The runtime
captures the old credential, blanks/cancels operational work synchronously, locks
the existing kernel context, then supplies a dedicated suspended-generation
handle. Lock failure sends no command. Login/logout/offline/workshop/disposal
invalidates that handle. Confirmed success closes the session; uncertain or
refused outcomes remain held until explicit connected verification or sign-in.
No previous offline admission is restored. Other-user mutations never replace the
actor session or selected workshop.

A lost response, timeout, malformed success or uncertain server failure is
reported as unconfirmed. Refreshing matching values cannot prove which command
committed. There is no invented idempotency key and no automatic retry.

## Secret lifetime, presentation and preservation

Passwords live in mounted uncontrolled credential controls and necessary
request-local values. Controls clear synchronously when dispatch takes ownership,
on cancel, account-generation invalidation and unmount. They never enter shared
feature snapshots, operational queues, IndexedDB, session/local storage, URLs or
error text. This is bounded application retention, not cryptographic erasure of
JavaScript strings or browser request buffers.

Administration is a stable sibling inside the existing WorkshopShell; opening
and closing it do not remount operational forms. It uses the existing four theme
token systems. Account-only controls use existing login-shell presentation, with
assigned account scope, selected workshop and server-scoped directory labeled
separately. Dirty form transitions require a deliberate decision. Semantic
labels/fieldsets, focus return, 48px controls, 56px submit targets, narrow reflow
and forced-colors styling are included. Source tests are not mounted DOM proof;
actual native screenshots and keyboard/axe journeys remain required.

All original journals, receipts, legacy databases, cursor/partition ownership and
recovery holds remain untouched by administration. No installation, credentials,
first-owner operation, deployment or actual user account was changed to implement
this slice. See the [evidence record](../10-spec-development/2026-10-14-connected-administration-ui.md).
