# Changelog

## Unreleased

### Local workshop MVP foundation (pending hosted qualification)

- Define the laptop-to-ARM64 workshop MVP sequence, preserving existing tenant/capability and offline-first architecture.
- Add file-based database URL configuration and prevent service-worker navigation fallback from converting API/health routes into application HTML.
- Add isolated local Caddy/PWA/API/PostgreSQL/worker Compose, separate LAN TLS,
  non-superuser application database role and locked amd64/arm64 build paths.
- Add snapshot-consistent PostgreSQL bundles, integrity manifests and guarded
  fresh-target restore; database-only evidence excludes browser queues and assets.
- Local runtime and recovery qualification are tracked in the execution state; this is not a stable release or physical Raspberry qualification.
- Inventory API PR #22 and quote-domain PR #23 remain separate pending proposals and are not included in main by this entry.
