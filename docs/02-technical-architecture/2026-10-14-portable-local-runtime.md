# ADR: additive portable local runtime

Date: 2026-10-14
Status: accepted for implementation; qualification pending

## Context

The owner prioritizes a complete workshop MVP running locally in Docker on a laptop and later a Raspberry server. The repository already specifies Docker Compose, PostgreSQL, Caddy, a PWA and amd64/arm64 distribution. Existing development Compose serves only backend components and contains development credentials. Inventory PR #22 is merged; quote PR #23 remains pending.

## Decision

Add a separate local deployment topology rather than repurpose development defaults. Serve the compiled PWA and `/api` on one origin through Caddy; API and worker use a private PostgreSQL service and a shared, explicit migration prerequisite. Keep loopback access the default. Document a separate LAN HTTPS configuration and client certificate trust prerequisites without automating security-setting changes.

Use file-based credentials and a non-superuser application database role. Retain authoritative state in persistent volumes, provide explicit first-admin bootstrap, and never auto-delete volumes or regenerate existing secrets. Build dependencies from committed locks. Qualify ARM64 builds independently of actual Raspberry capacity.

For portability use logical PostgreSQL backups and clean-target restore with integrity/schema/count checks. DB-only backup is explicitly incomplete for filesystem blobs, installation configuration and unsynchronized browser queues; complete migration remains an operator workflow with independently verified assets. Never copy live PostgreSQL data directories between machines as the prescribed migration path.

Keep this increment independent of inventory/quotes and defer account/role/location administration to the next bounded slice. No changes to licensing, tenancy semantics, stock truth, offline guarantees or public deployment are authorized by this ADR.

## Consequences and evidence

One origin reduces deployment-specific API configuration and cookie/CORS mistakes; it does not make LAN HTTP a secure PWA context. API/health paths require both edge exclusions and service-worker navigation exclusions. Secret lifecycle, backups, certificate trust and release upgrades remain explicit operator responsibilities.

More services/configuration require fresh-install and restore testing. Hosted amd64 runtime and ARM64 build results must be reported separately; a green build cannot establish storage durability, performance or power-loss resilience on unknown hardware. See the associated local workshop MVP acceptance plan and runtime runbook for evidence as it becomes available.
