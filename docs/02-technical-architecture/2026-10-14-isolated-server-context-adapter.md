# ADR: isolated authenticated context transport

Status: accepted for isolated prerequisite only; production activation is blocked.
Base: actual main32 `d831cd49136e3d036199a2464b5e422e8608d615`.

Traceability: Foundation ADR-003/007/013, TA-02/05/07; FR-IAM-002/004/006/008;
OFF-001/003/005–009/012; SEC-002/003; NFR-004/005/010/014;
INV-LOCAL-001/GATE-LOCAL-001. AGPL-3.0-only and truthful DCO remain unchanged.

## Decision and trust boundary

Add `access-kernel/server-context.ts` without importing it from App, production
session/auth code, defaultDB or any live repository. The server authenticates the
bearer and derives effective authority. This adapter supplies routing checks;
it cannot authenticate a fabricated response from a malicious fetch implementation
or defend against arbitrary same-origin script/device control.

A configured canonical API base is captured when constructing the adapter. The
caller must supply its trusted deployment configuration, not Host headers,
response fields or decoded JWT claims. The current closed generated
`AccessContextResponse` requires `principal.api_realm: null`; only after checking
the exact configured response destination does the adapter bind that null to the
configured realm. Unknown wire keys, missing nullable keys, foreign identity or
location, incompatible policy/protocol, wildcard/duplicate grants, invalid UTC
timestamps, expired or greater-than-eight-hour leases fail closed. The server's
signed-expiry bound is authoritative: the client never decodes JWT claims or
creates a longer lease. UTC microseconds are truncated conservatively to the
kernel's millisecond time representation. Clock rollback during a request and a
server verification time later than the local clock are rejected rather than
silently extending trust. A future clock-skew policy requires separate review.

Each verification synchronously copies the expected principal, selected concrete
location, configured realm, device generation, tab attempt and opaque session
handle plus the bearer string before asynchronous work. The caller supplies a
synchronous `isCurrent(captured)` comparison of every relevant current identity,
realm, selected location, session handle and generation field. It must invalidate
on logout/disposal/context changes. A fresh opaque session handle is required for
a replacement token, including same-principal refresh; handles must not contain
credentials. No mutable token-provider callback exists. A supplied expected epoch
must match exactly; omit it for fresh verification where the server determines
the new epoch. Client identity/expected epoch are routing expectations, not grants.

A per-adapter sequence also rejects older overlapping requests even in the same
generation. Checks occur before network dispatch, after headers and after body
resolution. Returned identity, principal, grants and context are frozen. Any
later asynchronous kernel persistence must still compare the durable kernel
fences within its own transaction; returning a context is not a persistence or
activation ticket. Cross-tab coordination is not claimed by this volatile helper.

Fetch uses an explicit selected-location query, bearer authorization, no-store,
redirect:error, credentials:omit and no-referrer. No redirects, including
same-origin ones, may forward credentials. A redirected/different response URL,
non-JSON content type, missing no-store directive or non-success response fails
closed. Transport exceptions and response error bodies are never reflected to
logs or caller errors. Fetch and clock are injected for deterministic tests;
production must use a trusted browser transport and retains its separate service
worker qualification requirement. Browser cache flags alone do not prove that
an existing service worker ignores a request.

## Literal capabilities and activation boundary

Copy the server's concrete capabilities exactly. Never add read from write,
expand wildcards, infer owner/role grants or synthesize grants from session data.
An empty list stays empty. Current `snapshot_protocol: null` always returns
`BASELINE_REQUIRED` using the existing `VerifiedAccessContext` kernel type.
`baseline-v1` remains unsupported by this transport until its integrated wire
contract and consumption/activation protocol are qualified. Server baseline code
landing separately does not authorize changing this boundary.

No baseline page ingestion, migration, persistent credentials, account UI,
user-switching UI, production authentication wiring or database writes are added.
No old journal is read, reassigned, copied, acknowledged, replayed or deleted.
Host/port/base-path changes are distinct realms and require new partition and
baseline; matching IDs never authorize retargeting original journal entries.
The old realm's journal must be preserved with its original authorship and
uncertainty. The separately reviewed old-writer compatibility floor, distinct
new database name, restore/session invalidation and legacy recovery contracts
remain production activation gates. Offline old tabs cannot be remotely revoked.
