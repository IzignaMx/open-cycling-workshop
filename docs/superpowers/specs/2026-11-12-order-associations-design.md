# Saved-order associated identities

## Selection and boundary

The user requested continued workshop development after PR102. Main is
`f09441c5dcd9aee721af92471ed836528c595668`, tree
`97ddba7b1dc66183a472f2393af8ec30984bf9be`. Saved orders currently identify only
that a bicycle exists, leaving mechanics unable to read the associated customer
or bicycle from the order. This read-only handoff supports FR-SVC-001 and the
existing R02-T005/R02-T014 reception flow as an independent prerequisite under
Master Loop §16/product alignment S2. It does not complete either task, activate
V0.2, or qualify the under-60-second physical usability target.

## Rejected larger increment

Existing-bicycle selection during intake was considered first. Current draft
format 1 accepts an exact eight-field shape. An additional association ID in the
shared store is unsafe for old clients: their maintenance sweep treats unknown
shapes as invalid and removes the content. An isolated fake-IDB experiment with
installed Dexie 4.4.4 proves a v8 instance can reopen a v9 database after its active
connection closes for versionchange. Dexie catches VersionError and retries
without a requested version. A version bump alone is not a downgrade fence.

That selection increment is blocked on a separately reviewed mixed-version
recovery representation. No field is overloaded, draft silently reinterpreted,
sweeper altered or database version changed here. The retained reproduction is
engineering evidence, not native-browser or physical-device proof. No global
customer-equals-bicycle-owner rule is introduced; the inspected contracts do not
establish that restriction for historical orders.

## Read contract and ownership

- Explicit per-order action reads an order already on the current admitted page.
- The repository rereads that exact order under orders.read. Independent
  customers.read and bicycles.read gates precede each related entity lookup.
- Only customer name/ID and bicycle brand/model/ID are returned. No contact,
  notes, serial, owner enrichment, broad search, server fetch or mutation.
- Reads use existing admitted kernel projection boundaries for current principal,
  organization and location. Missing/blocked projections stay unavailable, not
  reassigned or searched in other scopes.
- A second exact order read verifies its version and reference IDs before
  publishing. This is a bounded local snapshot, not an atomic multi-entity server
  snapshot, ownership proof or guarantee that all data is current.
- An explicit accessible close invalidates pending work; late results cannot reopen it.
- At most one volatile readback panel is retained. Duplicate same-order requests
  coalesce while loading. Newer requests, refresh, session/scope changes and
  authority loss fence stale completion. Refresh invalidates the old snapshot.
- UI independently masks each restricted field again. No association, unavailable
  locally, restricted, loading and generic failure are distinct. The same action
  retries without retaining raw errors.
- No schema, journal, sync command, recovery content or authority changes. Reload
  starts without presentation state and can reread admitted local entities.

## Acceptance

Tests must first expose absent behavior, then prove exact pending/local identity
readback, no additional journal/network effects, denied independent reads,
revocation, stale session/refresh completion, missing/blocked/absent bicycle,
changed order references, generic retry and App wiring. UI tests cover inert
multiline/bidi content, permission masking, row isolation, keyboard-capable button
semantics and actions preceding full-width details. Native E2E must exercise
keyboard activation, offline reload, themes and narrow layout when the permitted
backend/browser environment is available. Lower-level tests do not replace it.
