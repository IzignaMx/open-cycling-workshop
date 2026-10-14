# Local workshop MVP: delivery and acceptance plan

Status: accepted implementation direction; implementation and qualification in progress.
Date: 2026-10-14. Baseline: main `b1df504`; inventory PR #22 and quote-domain PR #23 remain independent, unmerged proposals.

## Product outcome and boundaries

Run one coherent workshop application in Docker on a laptop, then transfer its authoritative data to a qualified ARM64 local server. Reuse the existing modular monolith, PWA, PostgreSQL, scoped capabilities and append-only domain history. A Raspberry model, memory, storage and operating system have not been supplied; ARM64 image qualification is not physical-device qualification. No production-readiness or release certification is implied.

An organization represents an independent business; locations represent its branches. Users and operational records remain tenant scoped. The initial deploy may host several organizations; a multi-organization account switcher is a later explicit identity decision, not an implicit relaxation of the existing account scope.

## Coverage at baseline

- Implemented: authentication and capability enforcement; customer, bicycle and service-order slices with offline queue/conflicts; product/ledger persistence; development Compose and backup wrapper.
- Pending review: #22 inventory commands/derived stock and #23 immutable quote domain. Neither provides the complete money-and-parts user journey.
- Specified, not implemented: user/role/location administration; supplier/purchase-order lifecycle; configurable BrandProfile and color schemes; complete server distribution.
- Existing release gates remain: physical Windows/Android qualification, manual accessibility and operator recovery evidence.

## Increment A: portable local runtime (current)

Traceability: NFR-006; OPS-ADR-001/002/012/013/015; operations sections 7–12, 31–32; Master Loop portability/recovery invariants.

Acceptance:

1. A separate Compose topology builds and serves the production PWA and same-origin API through an edge service, with private PostgreSQL and worker. Development Compose remains available.
2. Default published access is loopback; LAN access requires the documented HTTPS/trust setup. No insecure-origin browser exception is required or automated.
3. Database/auth credentials are files, absent from tracked files and container command arguments. Application database role is not a PostgreSQL superuser. A single successful migration job gates API and worker startup.
4. Persistent storage survives container replacement. First-admin creation is explicit and refuses reinitialization; install documentation describes safe secret handling and existing-volume behavior.
5. API and health requests never fall back to successful SPA HTML, including through service-worker navigation fallback.
6. Database backup records integrity and provenance. Restore refuses a populated target, preserves historical identity, and produces explicit recovery evidence. Database-only tooling never claims to preserve unsynchronized browser work or filesystem blobs.
7. Hosted qualification builds amd64/arm64 images without publishing them, exercises an amd64 clean installation and recovery, and records exact source revision. ARM image build is not a Raspberry performance test.
8. Local commands distinguish executed checks from unavailable Docker/PostgreSQL/browser gates. No deployment to user equipment occurs in this increment.

## Increment B: people and workshop administration (next independent slice)

Traceability: FR-IAM-001/004/005/006/008; tenant isolation and scoped RBAC.

Implement audited user creation/deactivation, capability bundles (Owner/Administrator/Manager/Mechanic/Sales/Reception/Viewer/Technical Admin), per-user capability assignment and location administration. Preserve deny-by-default server enforcement, prevent privilege escalation, protect the last operational administrator, revoke stale sessions after access changes, and test cross-organization/location denials. Keep technical operations permissions separate from customer/business data access. Start with server contracts and tests, then an accessible administration UI; never use shared admin credentials as multi-user support.

## Increment C: complete money-and-parts vertical slice

Review and integrate #22/#23 only with merge authorization; reconcile their overlapping documentation. Continue the existing Increment 2 plan: authorization evidence, migrations, sync fan-out, quote API, offline draft storage, quote editor/inventory panel, reservation lifecycle E2E, qualification. Financial and stock truth remain server authoritative; no offline stock promises.

## Increment D: purchasing

Traceability: FR-INV-007/008 and inventory ledger invariants. Supplier → draft purchase order → approval → partial receipt → closure/cancellation. Each receipt must be idempotent, authorized, tenant/location scoped and produce append-only inventory movements exactly once. Define currency, units, over-receipt policy and corrections before implementing. Do not add POS/payments to this slice.

## Increment E: accessible customization

Traceability: FR-WL-001..006, ACC-009 and UX sections 15–16. Persist validated organization BrandProfile, logo/contact/name and light/dark/high-contrast presets; protect operational colors and focus/error semantics. Include export/import, offline read availability and contrast checks. UI configuration, not source edits, is the acceptance boundary.

## Increment F: migration and physical qualification

Before moving real data: identify laptop/target architecture, Raspberry model/RAM, 64-bit OS, SSD capacity, network, backup destination and power resilience. Run measured load and restore drills on the actual target. Retain the old installation until restored identities/counts and business workflows are verified. Drain or explicitly preserve all local mutation queues before changing origins; browser IndexedDB is origin-bound and not transferred by a PostgreSQL dump. Move filesystem assets and configuration separately, validate checksums, and retain encrypted off-device backup. Record measured RPO/RTO, not estimates presented as evidence.

## Release and status discipline

Each slice updates changelog, execution state and its acceptance evidence. Keep existing development versions until an explicit release checkpoint; use SemVer through the repository release process. Main and draft work are reported separately. Physical/manual gates cannot be closed by hosted CI.
