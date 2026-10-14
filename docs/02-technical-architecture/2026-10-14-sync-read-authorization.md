# Scoped change-feed authorization and cursors

Status: Accepted for the bounded read-side enforcement fix.

## Context

Capability/scoped RBAC is the accepted authorization architecture (Foundation
ADR-013, Security/Privacy §§8–10). Reading the change feed must enforce the same
entity read permissions and tenant/location boundaries as the resource APIs.
The shared authorization helper also serves other domains, where an omitted
location can represent an organization-owned resource; its generic semantics
must not be changed as an incidental sync fix.

## Decision

- The sync router derives organization and effective grants from the persisted,
  authenticated principal. If the request omits `location_id`, a location-bound
  session uses its own location. An explicitly different location is denied.
- An organization-scoped session retains its existing ability to request one
  location or all locations within its organization. No request can select a
  different organization.
- `sync.pull` permits access to the transport, not every entity in it. The
  change-feed service requires an explicit capability set and maps `customer`
  to `customers.read`, `bicycle` to `bicycles.read`, and `service_order` to
  `orders.read`. Write permissions do not imply read permissions.
- Unknown entity types are excluded, including for wildcard users. Adding a
  synchronizable entity requires an explicit server-side read-permission map
  and its own contract/security tests. Existing client handling of unknown
  entities is unchanged.
- Apply the tenant, effective-location and readable-entity predicates in SQL
  **before** ordering, limiting, or looking ahead. A page contains only permitted
  rows. `has_more` describes another permitted row, not hidden activity.
- `next_cursor` is the last returned row's cursor. An empty page preserves the
  supplied cursor and returns `has_more: false`. Hidden-only prefixes/tails do
  not advance it or consume the page limit. Authorized later rows remain
  discoverable without requiring empty-page polling loops.

## Compatibility and boundaries

The public response/query shapes and existing numeric cursor are unchanged; no
migration or generated-contract update is needed. Numeric cursors can have gaps
because the stored sequence is global. This patch does not introduce opaque or
per-scope sequence identifiers, and makes no new sequence-confidentiality claim.

An incremental cursor is meaningful for a stable authorization scope. If grants
or locations change, reusing a prior cursor can omit older newly authorized
records. The future user-administration increment must pair session revocation
with an authorization-epoch/scoped resnapshot design, including reconciliation
of pending mutations and previously cached data. Do not silently clear IndexedDB
or pending writes. A new login alone is not proof that a cursor was reset.

This patch enforces the current persisted principal on subsequent connected
pulls. It cannot erase already-downloaded offline data or eliminate the offline
revocation window. It does not implement role management, complete multi-workshop
navigation, or claim broader session/offline release qualification.
