# Open Cycling Workshop Platform — Foundation v0.2

> Sustituye Foundation v0.1 como baseline conceptual.

## 1. Decisiones rectoras

- **Licencia oficial del Core y apps oficiales:** `AGPL-3.0-only`.
- **Autonomía técnica por defecto:** las decisiones de ingeniería se resuelven sin solicitar aprobación manual cuando los requisitos y la evidencia permiten escoger responsablemente.
- **ADRs obligatorios:** las decisiones arquitectónicas relevantes quedan registradas y son reversibles si aparece evidencia mejor.
- **Spikes con propósito:** sólo se mantienen abiertos cuando una medición empírica es material para la elección.

## 2. Política de autonomía técnica

| ID | Política | Criterio |
|---|---|---|
| TA-01 | Decidir por evidencia | Optimizar corrección, resiliencia, mantenibilidad, seguridad, accesibilidad, portabilidad, rendimiento y costo total. |
| TA-02 | ADR obligatorio | Toda decisión arquitectónica relevante queda documentada. |
| TA-03 | No bloquear por preferencia | No se pide aprobación humana para decisiones técnicas ordinarias ya resolubles. |
| TA-04 | Spikes sólo cuando aporten evidencia | Se prototipa cuando existe incertidumbre material medible. |
| TA-05 | Reversibilidad | Boundaries y adapters reducen lock-in. |
| TA-06 | No sobreingeniería | Microservicios, brokers o Kubernetes requieren necesidad demostrada. |
| TA-07 | Mejor resultado global | No optimizar una capa sacrificando seguridad, offline, accesibilidad o TCO. |

## 3. Licenciamiento

El Core y las aplicaciones oficiales usan **GNU Affero General Public License v3.0, `AGPL-3.0-only`**. El repositorio incluirá `LICENSE` y encabezados SPDX cuando correspondan. Se usará inicialmente **Developer Certificate of Origin (DCO)** para contribuciones, evitando cesión exclusiva mediante CLA. Documentación: recomendación `CC BY-SA 4.0`. Datos comunitarios: licencia explícita por dataset.

Plugins jurídicamente separables pueden usar otra licencia, siempre que su integración no imponga incompatibilidades al Core.

## 4. ADRs cerrados

| ADR | Área | Decisión | Estado |
|---|---|---|---|
| ADR-001 | Arquitectura | Monolito modular | Accepted |
| ADR-002 | Frontend | React + TypeScript + Vite PWA | Accepted |
| ADR-003 | Persistencia local | IndexedDB mediante Dexie y repository abstraction | Accepted |
| ADR-004 | Backend | Python + FastAPI + Pydantic + SQLAlchemy 2 + Alembic | Accepted |
| ADR-005 | DB servidor | PostgreSQL | Accepted |
| ADR-006 | IDs | UUIDv7 | Accepted |
| ADR-007 | Sync | Mutation log idempotente + cursor incremental + policy por dominio | Accepted |
| ADR-008 | Eventos | Transactional Outbox | Accepted |
| ADR-009 | Jobs | Queue durable en PostgreSQL + worker dedicado | Accepted |
| ADR-010 | API | REST JSON versionada + OpenAPI | Accepted |
| ADR-011 | Desktop | PWA default, Tauri sólo para capabilities nativas | Accepted |
| ADR-012 | Deployment | Docker Compose | Accepted |
| ADR-013 | AuthZ | RBAC por capabilities y scopes | Accepted |
| ADR-014 | Blobs | Filesystem y S3-compatible mediante abstraction | Accepted |
| ADR-015 | Plugins | Manifest + capabilities + hooks versionados | Accepted |
| ADR-016 | Licencia | AGPL-3.0-only | Accepted |

## 5. Principios vigentes

Offline First, Local First, Open Source First, API First, Modular by Design, Privacy by Design, Security by Default, Accessibility by Default, Internationalization Ready, Vendor Neutrality, Graceful Degradation, Interoperability, Auditability, Extensibility, Maintainability, Right to Repair Friendly y Open Knowledge.

## 6. Evolución

El roadmap V0.1 → V3+ permanece vigente y se acompaña de un Continuous Improvement Track permanente. Las capacidades especializadas entran como módulos antes de considerarse candidatas a Core.

## 7. Supremacía documental

La versión más reciente de una familia documental prevalece sobre versiones anteriores. Un ADR `Accepted` prevalece sobre narrativa anterior. Restricciones de seguridad pueden endurecer requisitos funcionales cuando exista riesgo material.
