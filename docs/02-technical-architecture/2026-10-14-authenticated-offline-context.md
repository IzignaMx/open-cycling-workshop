# Authenticated offline context prerequisite

Status: Accepted for this bounded, unactivated server contract. First-head
PostgreSQL contention qualification passed; final integrated-source qualification
is tracked separately in the increment specification.

## Decision and invariant

Provide additive `GET /api/v1/auth/context`, using the existing session token
and persistence. Do not activate the isolated offline kernel or advertise a
baseline protocol. This follows Foundation ADR-003/007/013, FR-IAM-002/004/006/008,
OFF-001/003/005–009/012, SEC-002/003 and the administration/effective-authority
prerequisites. Existing `/auth/me`, login and sync wire contracts stay intact.

Retain the original signature/issuer/HS256-validated token principal. Lock its
organization, then reload and lock its account with `populate_existing`; check
active state, identity, session version and compatible scope after both waits.
Compute the existing literal account/token capability intersection first. Only
then expand a surviving `*` over the implemented `CAPABILITIES`, or intersect
surviving explicit grants with that catalog. Thus token `{*}` plus account
`{customers.read}` has no grants, as does the reverse. Unknown capabilities and
write-only grants confer no implicit read permission. Owner/role labels confer
no bypass. No administration-specific wildcard expansion is reused.

A location-bound principal may omit `selected_location_id`; the endpoint uses
its effective location. An organization-wide principal must explicitly select a
concrete location. Every selected location must exist in the same organization,
including implicit selection. Missing selection returns the existing structured
422 `location_required` envelope. Forbidden/foreign/nonexistent locations return
403 without distinguishing existence. Invalid/revoked sessions return 401.
Selection never widens effective account/token scope.

## Expiry and offline lease

`decode_session()` returns the validated principal and UTC expiry internally;
`decode()` remains a principal-only wrapper. JWT `exp`, `iat`, and optional
`nbf` must be finite integer NumericDates (booleans/strings/floats are rejected).
The existing signature, issuer, algorithm and required claims remain enforced.
Temporal validation uses an injectable aware UTC clock, rejects future issuance
or not-before times and expired/nonpositive lifetimes, and validates representable
expiry. No browser decoding or second token is involved.

After the organization and user locks, recheck expiry. Check again immediately
before constructing the response, after location lookup and epoch calculation.
`verified_at` is server UTC now, and `offline_until` is the earlier of the signed
expiry and eight hours after verification. A fresh same-epoch token can renew
this lease only through a fresh connected verification. Revocation after the
response cannot be detected offline before the next online check or lease end.
Clock disagreement must remain fail-closed in the future client adapter; this
slice adds no skew allowance or client clock correction.

All responses on this route, including authentication/validation/database errors
and redirects, carry `Cache-Control: no-store`. No token is persisted to a new
store or logged. This route returns metadata only and performs no database
mutation, checkpoint creation or baseline activation.

## Durable equality identity and realm

`authorization_epoch` is unpadded base64url SHA-256 of UTF-8 canonical compact
JSON (Unicode preserved) containing, in this exact array order:

1. `ocwp-access-epoch-v1`
2. server API realm, currently null
3. user ID
4. organization ID
5. effective location ID or null
6. sorted unique concrete capabilities
7. persisted session version
8. policy revision `ocwp-access-baseline-1`

This public equality identifier is derived from durable current authority, not
an access credential. It survives restarts/renewals/display-name edits and does
not include selected location, JWT bytes, jti, iat, exp, or display/account
version. Selected location is independently bound by the future local partition.
A catalog/read-map or epoch-policy change requires a policy revision bump.
Database restore can restore old authority/session versions; this hash does not
claim restore detection. Existing restore maintenance/session invalidation and
fresh-baseline requirements remain mandatory before any future activation.

No trusted canonical API realm setting currently exists, so `api_realm` is
explicitly null in this increment. Never derive it from Host, forwarded headers
or an untrusted request value. The future authenticated adapter must bind the
verified configured API endpoint to the kernel's required non-null API realm,
reject cross-origin redirects and mismatched realm configuration, and capture
an immutable token handle per request. A realm move, including host/port/base
path changes, requires a new partition/baseline and preserves the original
journal in its original realm. Matching account/entity IDs do not authorize
retargeting, copying or replaying old mutations at a new endpoint.

## Compatibility and deferred work

Closed OpenAPI response schemas and generated TypeScript DTOs are additive.
`snapshot_protocol` is always null. No baseline-v1 endpoints, client adapter,
production singleton wiring, UI, IndexedDB upgrade, persistence migration,
credentials, key generation, account action or deployment are included. The
ordered-feed writer work is independent and no writer files change here.

Legacy journals/cache/preferences remain byte-for-byte untouched. Baseline
completeness, staged merge/activation, user switching, old-client/service-worker
fencing, restore operations, physical Windows/Android and accessibility rollout
evidence remain separate gates. This prerequisite is not an offline-login or
multi-user isolation completion claim.
