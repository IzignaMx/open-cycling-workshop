# ADR · Shared workshop branding and admitted read cache

Date: 2026-10-14. Status: implemented, exact integrated hosted/runtime evidence pending.
Base: merged main39 `eef9559d8c3e528e79c99898360892188b23b55e`.

## Scope and invariants

One shared profile belongs to one organization and one concrete workshop/location.
It contains a display name, one of the existing twelve palettes and an optional
canonical PNG. Two branches can have different brands. A display name is not a
legal tenancy name and never rewrites historical documents. Scope covers a bounded
part of FR-WL-001/002 and FR-WL-003/004; public contacts and FR-WL-005 per-profile
interchange remain follow-on work. Domains, arbitrary CSS/colors, portal/document/
message branding, feature flags and production certification are excluded.

The persistent Banco/Plano/Ritmo/Noche shell and operational form ownership remain
unchanged. Palette and logo inheritance are render-only composition. A valid v1
palette, including the default value, remains an explicit personal override.
Absent logo records inherit; stored null remains an explicit hidden logo; stored
local images remain local. v2 writes occur only on explicit changes. The legacy
first-admission copier preserves provenance without rewriting original bytes.
Personal theme, scheme and density remain available offline. No local image is
uploaded automatically.

## Compatible authority and catalog contract

`branding.read` and `branding.write` are independent, explicit-only grants. The
immutable legacy wildcard set contains exactly the original seventeen business,
sync and administration capabilities. Effective authority is that fixed set when
`*` is present, plus recognized explicit literals. Role names and owner designation
are never capability shortcuts. Token/current-record intersections remain
restrictive; adoption invalidates prior sessions and requires fresh admission.

GET `/api/v1/admin/roles` retains its exact original closed response and seventeen-
grant role snapshots. Existing v1 role-string POST/PATCH aliases also retain those
snapshots. Freezing only the GET catalog would silently widen old role requests.
GET `/api/v2/admin/roles` advertises `catalog_version: 2`, the current catalog and
`legacy_wildcard_capabilities`. New clients expand selected roles into explicit
capabilities before dispatch. The same-origin v2 request does not change the
`/api/v1` realm used in session, partition or offline bindings. There is no unsafe
v1 fallback when v2 is unavailable.

Existing established organization-wide owners with all original grants can retain
their exact stored grants/scope/owner status on unrelated edits. Name-only PATCH
stays minimal; legacy wildcard snapshots are not resubmitted as new assignments.
Unknown grants and malformed owners remain fail-closed. Creation, promotion and
explicit owner grant/scope replacement require the full current owner grant set.
Old clients cannot create/promote a full new owner through a legacy role alias;
they must upgrade. Old clients seeing new literals safely refuse unknown-grant
editing. The narrow local adoption command is never run by migration/startup and
was exercised only on synthetic fixtures.
Apply the complete migration chain before any explicitly authorized adoption;
adopting grants against an older schema is unsupported, and grants alone do not
provide the missing profile storage.

### Policy revision clarification

The authenticated-context ADR requires a policy bump for a catalog/read-map or
epoch-policy change. This additive explicit-only catalog is compatible with its
existing semantics: every prior concrete/wildcard account publishes the same
seventeen-or-fewer effective grants and the epoch calculation is unchanged.
Existing operational maps/entities and baseline contract are unchanged. Therefore
`ocwp-access-baseline-2` is retained to preserve the old client's closed parser.
Adding/removing actual branding literals changes the existing authority-derived
epoch; adoption also increments session version. A future change to prior grant
resolution, epoch calculation or operational read maps still requires a negotiated
policy revision. A brand name/palette/version change never rotates authority.

## Profile transport and persistence

SQL migration 0011 adds `workshop_brand_profiles`, keyed by organization/location
with composite tenant FKs, descriptor consistency constraints and positive saved
versions. Absent profiles have explicit version 0 responses; first save is CAS 0.
The unimplemented quote reservation moves to SQL 0012. No applied migration is
rewritten; destructive downgrade is refused before DDL/DML.

GET/PUT `/api/v1/locations/{location_id}/branding` use protocol 1 admission and closed
DTOs. PUT contains only expected_version, display_name, palette_id and nullable
logo_png_base64. Name normalization is NFC/trim, 1–160 Unicode codepoints, <=640
UTF8 bytes, no Unicode control/private/surrogate/unassigned categories. Version 0
normalizes the permitted location label for display only and falls back to Taller
when old tenancy values cannot meet this contract.

Responses repeat organization/location/incarnation, schema 1/version, name/palette,
update metadata and explicit logo states. `none` has no descriptor, `available`
embeds canonical bytes, `unavailable` retains the descriptor with a safe diagnostic
and no bytes. Missing/corrupt assets never become deliberate removal or reuse old
image bytes. Write-only success returns only the newly submitted replacement; read
permission is independently required for display/cache. Request/response envelopes
are bounded to 384 KiB, PNG to 256 KiB. Streaming checks do not trust Content-Length.
All paths, including validation/auth failures, redirects, unsupported methods and
unexpected errors, carry no-store. Validation failures are constant bounded
messages rather than echoed input arrays.

The service decodes before long-lived DB locks, then acquires organization before
current actor, validates protocol/incarnation/expiry, intersects current authority,
validates concrete location, locks/CASes profile and publishes immutable bytes
before SQL reference/audit commit. Final admission revalidation remains mandatory.
Reads use the same coherent current authorization boundary. Audit stores bounded
IDs/versions/palette/digest/change fields, never names, original files or base64.
409 requires explicit reload/review; lost/malformed success is unconfirmed, never
an automatic retry or inferred success from a matching later read.

## Assets and recovery

Pillow 12.3.0 is pinned in the lock. PNG framing/CRC/chunk/dimension/ancillary checks
precede full isolated decode/re-encode. One killable child per API worker has no
waiting queue, a two-second wall limit and a 128 MiB Linux limit. Canonical output is
metadata-free 8-bit RGB/RGBA PNG, <=512 px per side. No SVG, URLs, animation or APNG.
See [decoder/storage evidence](../03-security-privacy/2026-10-14-branding-image-storage.md).

Organization namespaces derive from server-validated IDs. Opened directory/file
descriptors, no-follow checks, bounded reads, digest verification, exclusive temp
creation, file fsync, atomic no-replace hardlink publication and directory fsync
protect immutable content. Old referenced files are retained; no online GC or
replacement/removal deletion is introduced. API gets a narrow named volume; backup
access is read-only and an explicit fresh restore target is separate. Worker and
edge get no asset mount. Docker ownership/ARM runtime remain evidence gates.

The existing PostgreSQL-only bundle stays truthful. A separate branding bundle
collects exact asset references inside the exported repeatable-read snapshot used
by pg_dump, then copies those immutable bytes and publishes its manifest last.
Restore requires trusted provenance, fresh targets, all references/hash/bytes and
metadata checks, then the established expected-incarnation recovery fence before
API reopening. No tenant or browser journal is excluded. Checksums establish
integrity, not authenticity. See the [operator procedure](../07-operations/2026-10-14-branding-recovery.md).

Shared branding does not implicitly activate a protocol-floor 0 organization.
Full-instance bundles preserve every floor 0/floor 1 tenant, including tenants with
no branding profile. By default restore refuses any floor 0 tenant before changing
either target. `verify --show-legacy-cutover` is read-only. A separate, sensitive
operator decision may supply the exact complete set of floor 0 organization/source-
incarnation pairs and acknowledge drained old writers, raw legacy preservation
and existing audited cutover prerequisites. Missing, extra, duplicate or stale
pairs fail before target modification. All restored metadata and asset bytes are
verified before existing audited activation/recovery; activation checks the same
incarnation atomically under the organization lock. These flags authorize an
actual compatibility transition when an operator runs them. A partial failure
leaves both targets quarantined. Implementation and tests authorize no real
installation transition.

## Authenticated offline display

Only the separate authenticated database gains schema 7 `brandingSnapshots`; legacy
`ocwp` is not upgraded. Future quote local schema is 8. Branding is not an operational
sync entity and never enters journals, receipts, baseline records or mutation
transports. The dedicated cache repeats realm/org/user/location/epoch/policy/
incarnation/partition/lease and validates canonical data. Current device ownership
and READY/OFFLINE_READY admission are checked transactionally. Offline reload uses
its new valid owner ticket under the same existing lease; stored provenance never
grants admission. Monotonic elapsed time fences delayed digest/IDB work.
The original operation-entry wall timestamp separately fences rollback behind
the verified context, device control and snapshot observation. Waiting cannot
erase an invalid entry time; expiry checks continue advancing through final
transactional admission. Concurrent newer trusted evidence may conservatively
refuse an older operation, without deleting the snapshot or operational work.
An explicit refresh requested during a branding flight is coalesced into one
freshly captured and validated trailing flight. The trailing flight cannot queue
another, and a null cache result does not itself retry. This preserves rollback
refusal while honoring the offline transition's already-requested recovery.
Offline readmission also requests a refresh after its initial operational page
and issue reads finish: their kernel transactions may advance trusted observation
time after the first cache read began. The completion request requires the same
still-current active source and uses the existing finite coalescer. It is not a
retry triggered by cache refusal and does not run for connected startup.
Connected admission keeps one source-bound completion request until its first
settled sync finishes the final operational reads. Intermediate progress or
transient retry does not consume it; cancellation, offline transition and a new
admission replace it. Consume only after rechecking the current source following
terminal publication. Subsequent sync polls and page changes do not request more
branding. Both paths use the unchanged finite coalescer, not a cache-null loop.

The runtime owns refresh on admission, reconnection, focus (throttled) and explicit
request/save. Exact saved session, current ticket/source generation, lease and
currentness surround all awaits and publication. Logout, takeover, held/expired
admission and current refusals synchronously hide content. Older versions cannot
replace newer accepted profiles. Quota failure may retain verified content in
memory with a visible warning, without evicting operational work. Only superseded
branding caches are boundedly pruned. Cross-device convergence occurs on refresh;
there is no immediate push claim or public/service-worker image cache.

## Evidence boundary

Unit, injected-network and fake-IDB tests establish their own boundaries only.
Real PostgreSQL locking/migration, native browser storage/DOM, actual screenshots,
asset-inclusive authenticated restore, container ownership and ARM images require
exact-tree hosted evidence. Physical Windows/Android, screen readers, glare,
realistic capacity/RTO and actual installation recovery remain separate gates.
The [increment evidence record](../10-spec-development/2026-10-14-shared-workshop-branding.md)
separates executed local checks, inherited main39 evidence and authored hosted
qualification.

## 2026-10-15 presentation and ARM evidence decisions

A transparent image may contain light, dark or colored artwork independently of
its viewer's surface scheme. The three logo render sites therefore share a small
presentation-only image component. It chooses a white or dark canvas from bounded
alpha-composited samples of the already decoded current PNG, with white fallback
for opaque/empty/unreadable input. This is a heuristic for readable presentation,
not a per-stroke or universal contrast guarantee for mixed artwork. The original
image bytes, canonical descriptor, cache and personal inheritance are unchanged;
there is no new fetch, encoding, persisted preference or authority. Textual workshop
identity and accessible image descriptions remain independent. Only the image's
canvas opts out of forced-color substitution, not the surrounding controls.

Architecture execution qualification now deliberately requires all three ARM64
image builds plus the installed decoder on a standard native ARM64 runner with
its unchanged production limits. An always-evaluated aggregate rejects missing,
skipped, failed or cancelled native/build dependencies. A separate QEMU workflow
is explicitly non-qualifying and preserves genuine nonzero exits, failed reports
and diagnostic history. Its original failure cause is not proven by a native
pass or by a separate instrumented child. No failure-signature exception,
permanent image allowlist, branch-protection change or physical Raspberry claim
is introduced. Native evidence timing consistency adds only bounded accounting
checks; it does not extend the two-second wall/CPU limits. These changes require
new exact-source hosted execution and pixel review, as described in the increment
evidence record.
