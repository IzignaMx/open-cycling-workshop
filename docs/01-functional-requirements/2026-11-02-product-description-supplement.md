# Product-description requirements supplement · 2026-11-02

This additive requirement baseline implements the maintainer's explicit request
of 2026-11-02 to align the development plan with the repository description.
It does not supersede Foundation, accepted ADRs or the existing Phase 1 IDs.
The description is a product destination, not evidence that all modules ship.
These requirements are planned, not implemented or release-qualified by this
change. See the [coverage and sequencing record](../10-spec-development/2026-11-02-product-description-alignment.md).

## Interpretation and boundaries

“Documentación” covers business documents and technical knowledge as well as
maintainer/operator documentation. “Personal” means staff directory, role-scoped
assignment, availability and workload: no incluye nómina, recruitment scoring,
medical files, employment adjudication or jurisdictional HR compliance. Existing
V1 non-goals remain unchanged. “Negocios relacionados” means reusable profiles
for workshop, retail-only, combined store/workshop and service/cooperative use;
rental/fleet/ecommerce remain separately admitted post-V1 modules, not implied V1
implementations. Business profiles configure navigation/defaults, never grants.

## Agenda / scheduling

- `FR-SCH-001` Create, reschedule and cancel appointments with organization, location, customer or minimal walk-in reference, optional bicycle/order, service duration, resource/staff and explicit lifecycle. An appointment is not an accepted quote, inventory reservation or payment.
- `FR-SCH-002` Store instants in UTC with an IANA location timezone; preserve intended wall time for availability rules. Reject nonexistent DST local times and require explicit offset choice for ambiguous ones; render locale independently from storage.
- `FR-SCH-003` Reject overlapping confirmed occupancy for the same constrained resource atomically; expose conflicting intervals. Cancellation releases occupancy exactly once; overrides require explicit capability, reason and audit. Adjacent half-open intervals do not overlap.
- `FR-SCH-004` Authorized offline users can see admitted schedules and save a durable provisional booking intent after a separately reviewed sync/admission design. Reconnect validates current permission, version and resource occupancy; conflicts stay visible, never silently confirm both or discard intent. Initial connected-only delivery must be labelled partial.
- `FR-SCH-005` Provide keyboard-accessible list and calendar views, focus restoration, non-color status and announced errors; filters by location, date, staff and status must not leak another scope. A calendar-only drag gesture is insufficient.
- `FR-SCH-006` Support appointment-to-order linkage and auditable completion/no-show/cancellation without creating duplicate orders; reminders require the communication consent/provider boundary and do not imply external calendar synchronization.

## Personal / staff operations

- `FR-STF-001` Maintain a scoped staff profile with display name, active status and optional IAM link. A profile alone grants no login, capability or customer access; an account alone does not prove mechanic availability.
- `FR-STF-002` Represent location-specific working intervals and exceptions without requiring payroll or sensitive reasons. Validate time ranges, timezone semantics and authorized edits; inactive staff cannot receive new assignments.
- `FR-STF-003` Assign or reassign repair tasks and appointment resources using current capabilities and active staff/location membership. Preserve assignment history and surface conflicts rather than mutating an old actor record.
- `FR-STF-004` Show workload as assigned task duration/count with explicit unknown estimates, time window and freshness. Do not turn estimates into measured labor hours or opaque individual performance rankings.
- `FR-STF-005` Restrict staff exports and availability details by capability/scope; deactivation preserves historical attribution and blocks new assignments. Offline cached views obey expiry/revocation rules; no account or permission creation from profile synchronization.

## Metrics / operational analytics

- `FR-MET-001` Version a metric dictionary with formula, unit, numerator/denominator, exclusions, source events, timezone/window and freshness. Empty denominators produce unavailable, not fabricated zero or infinity.
- `FR-MET-002` Derive order backlog, cycle time and throughput from canonical transitions, explicitly treating cancelled/reworked/reopened orders and incomplete durations; fixtures pin exact values.
- `FR-MET-003` Derive sales/payment/refund and stock movement totals from authoritative ledgers with exact decimal/integer money rules; separate revenue, receipts, taxes and margin. Uncosted stock and mixed currencies cannot silently produce profit or summed currency totals.
- `FR-MET-004` Partition queries, caches and exports by organization/location/capability; minimize PII and aggregate where feasible. Metrics work without third-party tracking; customer/staff identifiers are not telemetry defaults.
- `FR-MET-005` Offer accessible table/text alternatives and reproducible CSV exports with formula-injection protection. Offline reports explicitly name snapshot time, coverage and pending exclusions; incomplete local data is never labelled global real-time truth.

## Business documents

- `FR-DOC-001` Generate reception, work-order, estimate and handover documents from a fixed source revision with organization/location, document type, template version and visibility policy. Old issued documents do not silently change when a template or price changes.
- `FR-DOC-002` Separate internal notes/photos from customer-visible content in print, preview, download and portal. QR/link uses non-PII identifiers or revocable authorization; possession of an internal QR is not permission.
- `FR-DOC-003` Apply BrandProfile and locale to print, portal and messages without removing licensing/source notices or accessibility baselines. Long names, missing logos, monochrome print and multi-page documents remain legible.
- `FR-DOC-004` Provide locally available permitted templates/documents and explicit attachment synchronization state. Downloads/exports preserve source revision and authorization; failed external delivery never rewrites the business transaction.
- `FR-DOC-005` Document retention, export, template migration and regeneration behavior; test representative print layouts and data fidelity. Fiscal invoicing/certification is an optional jurisdictional adapter, not an implied compliant invoice from a generic ticket.

## Business profiles

- `FR-BIZ-001` Offer workshop, retail-only, combined and service/cooperative profiles as reviewed defaults; optional navigation must not force retail sales to create bicycles or service orders, nor force workshops to enable POS.
- `FR-BIZ-002` Enabling/disabling a profile or feature preserves stored/history/pending data and existing permissions; prerequisite and unavailable states are explicit. A module toggle is not code loading, credential issuance or authorization.
- `FR-BIZ-003` Qualify one end-to-end synthetic journey for each declared supported profile, including offline availability, accessibility, privacy, export and operator recovery. Marketing names and fixtures alone cannot establish profile support.

## Acceptance ownership

Existing FR-CUS/BIK/SVC/INV/POS/COM/PRT/KNW/AUT/PLG/WL, OFF, SEC, ACC,
NFR and BR requirements remain binding. New identifiers fill previously missing
specification; they do not replace existing ones. Phase 10 adds R02-T024–T029 for
staff/agenda and refines evidence for existing documents, analytics and profile
tasks. Each implementation must add actual behavior tests before a requirement
can enter the verified evidence ledger. The coverage JSON is a planning index,
not fabricated test coverage.
