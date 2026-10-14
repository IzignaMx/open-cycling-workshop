# ADR · Stable structural themes and local personal presentation

Status: implemented pending hosted browser evidence; independent static review completed.
Date: 2026-10-14. Original base: `98394826884020d9de2498cab551120087dd5334`.
Reconciliation includes runtime/sync-test PRs #24/#25 and authorization
PR #26 at `273bc8f06bb8c367660c0afd354f4f6c0ae6864d`; the latter was
not merged when this local reconciliation was prepared.

## Context

The user approved all four visual directions as selectable structural themes,
with Banco de trabajo as default. They are not four color presets or four
independent products. The existing Core contains customer intake, optional bicycle
intake, orders and their legal state actions, and the Conflict Center. The visual
boards' delivery promises, team workload, purchasing and inventory widgets are not
implemented frontend data, and must not be fabricated.

Applicable invariants: UX-01–07, DADR-006–009, AC-UX-001–006/008/011,
security/privacy sections 8–10/15/18, Local First and Offline First. The existing
server remains the authority for capabilities, transitions and organization scope.

## Decision

- `WorkshopShell` is one persistent React parent. A theme changes validated data
  attributes and tokens, not the React tree or keys of operational forms.
- `banco`: side navigation, a metric band and an ordered list.
- `plano`: top navigation, a full-width operational area and aligned comparison
  rows. These remain a semantically labelled list because records include several
  actions and expandable histories; this increment does not claim a sortable data
  table. Essential metadata has text labels, independent of column position.
- `ritmo`: light side navigation by default, separate metric modules and a real
  two-column card grid when space permits.
- `noche`: dark by default, a prominent first record and a secondary queue. The
  existing deterministic created-at order is retained. There is no invented
  active-task selection, checklist, delivery promise or assigned technician.
- The same OrderRecord, forms, event history, handlers and permissions serve every
  theme. The existing `orders.write` capability also gates transition affordances
  uniformly; this is not server-side authorization or a new permission.
- Palette (12 curated choices), surface scheme (theme/light/dark), touch density
  and personal logo are independent. Switching structure does not reset them.
  Alternate schemes are derived, measured extensions of the approved boards,
  not additional approved screenshots.
- Protected success/warning/danger/info pairs and double-ring focus never derive
  from a brand palette. `on-accent` is explicit, including dark-text night CTAs.
- Theme-specific structural CSS never uses `order` or changes domain DOM parentage.
  Narrow screens use normal document flow, four real navigation destinations,
  full-width records and unrestricted vertical scrolling. No hover-only actions.

## Persistence and authority boundary

Dexie schema 4 adds only `presentationPreferences: key`. Existing stores, records,
indexes and queued mutations are untouched. The quote/offline plan now reserves
schema 5, rather than silently colliding with this addition.

Two disjoint record kinds use collision-safe JSON keys:

- Appearance: `["appearance", organizationId, userId]`. Stores schema version,
  theme, palette, scheme and density. It follows that user between locations of
  the same organization on this browser/device.
- Local logo: `["logo", organizationId, userId, locationId]`. Stores a bounded
  raster data URL or explicit null. It is not inherited by another location,
  organization or user.

The UI composes both on load. Each record repeats and validates its scope.
Unknown versions, unknown enum values, wrong scope or unsafe logos fall back to
Banco de trabajo. Unknown extra fields cannot introduce CSS or capabilities.
Writes are serialized at a repository boundary shared across mounts, and reads
join pending writes for that personal scope. Failures retain the applied session appearance and report
that persistence failed. Reset changes only personal appearance; it does not
remove the local logo or operational data. No authentication material is stored
in preferences. Logging out does not delete these non-secret preferences.

There is no branding API, shared BrandProfile, sync entity, organization-brand
permission or cross-device propagation in this increment. Other open tabs reload preferences
on their next app load; there is no live cross-tab presentation broadcast. Every authenticated
user can change their personal view. UI explicitly says that the logo is local
and personal. A real organization/workshop-wide editor remains pending and needs
server-scoped authorization, versioned persistence, cache and conflict policy.
The current local mutation queue is never repurposed for preferences.

## Raster safety

Only PNG and JPEG are accepted (including a clear rejection of WebP and SVG).
No URLs, SVG, scripts, external image fetch or network upload are supported.
Input is bounded to 2 MiB, 4096 pixels per side and 8 megapixels. Signature and
header dimensions are checked before browser decode/allocation. Decoded bounds
are checked again. Canvas re-encoding removes original metadata/name and produces
PNG at most 512×512 and 256 KiB. A preview requires explicit application.

Restored PNG data URLs have bounded base64, signature, IHDR dimensions, complete
chunk boundaries and CRCs, image data and terminal IEND validation. The image is
rendered only as an img, never as HTML. A decode failure renders the text/monogram
fallback without a broken-image icon. A neutral plate preserves the logo on dark
surfaces. Local device compromise is outside this representation's guarantees;
IndexedDB is not advertised as encrypted storage or a durable backup.

## Limitations and verification

The implementation uses currently available fields and true local counts. There
is no new organization/location switcher, branding synchronization, compact mode,
Inter font asset delivery, print branding, operational draft persistence across
reload, or full shared-branding implementation. In-progress form drafts survive
presentation changes; existing behavior on page reload is not upgraded to draft
autosave. Normal queued domain mutations remain durable.

An in-memory session-generation guard rejects late reads, create callbacks and
auth/sync continuations from an earlier login/scope. Deterministic unit tests
cover deferred completion and same-user logout/login; these prove the guard,
not a complete browser race. Scoped render filters add defense in depth.

Browser acceptance includes exact seven-store v3→v4 preservation, offline theme switching with a
queued mutation and partially filled forms, stable input nodes/selection/focus,
history and search state, all four structural geometries, tablet touch targets,
320/390px reflow, protected states, keyboard/Escape, axe, logo and storage failures.
It emits screenshots for manual review. Numerical contrast checks do not prove
WCAG conformance. Physical Android/Windows and screen-reader gates remain open.
Local browser navigation is administratively blocked; that restriction is
respected. Hosted proof and screenshot review are required before UI completion.
