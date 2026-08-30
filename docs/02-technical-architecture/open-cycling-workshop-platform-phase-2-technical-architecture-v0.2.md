# Fase 2 · Technical Architecture & ADRs v0.2

> Sustituye v0.1 como registro técnico vigente.

## Arquitectura de referencia

```text
PWA React/TypeScript/Vite
  ├─ UI + feature modules
  ├─ Dexie / IndexedDB repositories
  ├─ mutation queue + sync coordinator
  └─ service worker / app shell
            ⇅ REST/JSON + sync endpoints
FastAPI modular monolith
  ├─ bounded-context application services
  ├─ SQLAlchemy + PostgreSQL
  ├─ transactional outbox
  ├─ durable jobs in PostgreSQL
  ├─ blob adapters
  └─ plugin/event extension points
```

## Decisiones cerradas

- Persistencia local: **IndexedDB mediante Dexie**.
- Persistencia conectada: **PostgreSQL**.
- Backend: **FastAPI + Pydantic + SQLAlchemy 2 + Alembic**.
- IDs sincronizables: **UUIDv7**.
- Sync: mutation log idempotente + cursor incremental + conflict policy por dominio.
- Integration events: **Transactional Outbox**.
- Jobs: queue durable inicialmente sobre PostgreSQL con worker `SKIP LOCKED`.
- API: REST JSON versionada + OpenAPI.
- Desktop: PWA primero, Tauri sólo para capacidades nativas justificadas.
- Distribución servidor: Docker Compose.
- AuthZ: RBAC por capabilities y scopes.
- Blobs: abstraction con filesystem y S3-compatible.
- Plugins: manifest, capabilities, hooks y compatibility ranges.
- Core/apps oficiales: **AGPL-3.0-only**.
- Contribuciones: DCO inicialmente.

## Sync protocol

```text
local mutation
→ persist mutation_queue
→ optimistic local projection
→ POST /api/v1/sync/mutations
→ idempotency guard
→ domain transaction
→ transactional outbox
→ server change feed
→ cursor pull
→ domain merge
→ durable cursor advance
```

Los timestamps no son la autoridad única del orden. El servidor emite sequence/cursor por tenant/location. Deletes sincronizados usan tombstones con retention. Los fallos permanentes pasan a estado visible y diagnosticable, no se descartan silenciosamente.

## Spikes restantes

1. Dexie/IndexedDB 100k+ movimientos en Android y Windows.
2. Chaos sync multidispositivo.
3. Blob upload offline/online.
4. PostgreSQL job queue bajo carga.
5. Tauri hardware PoC sólo si Web APIs son insuficientes.
6. Android storage eviction/recovery.
7. LAN discovery + TLS onboarding.

Los spikes ya no representan indecisión de stack. Validan límites y budgets antes de producción.
