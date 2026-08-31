# Fase 10 · Spec Development Master & Execution System v0.1

**Open Cycling Workshop Platform**  
Baseline ejecutable: Foundation v0.2 · Functional Requirements v0.1 · Technical Architecture v0.2 · Security/Privacy v0.1 · UX/UI v0.1 · Repository & Engineering Architecture v0.1 · QA/Verification v0.1 · Deployment/Operations v0.1 · Governance/Plugin Ecosystem v0.1 · Commercial Implementation v0.1  
Licencia normativa: `AGPL-3.0-only`

> Este documento no vuelve a diseñar el producto. Consolida las decisiones ya aprobadas en un sistema de ejecución determinista para humanos y agentes de IA. Define qué documentos son normativos, cómo seleccionar y descomponer trabajo, qué puede decidirse autónomamente, cómo verificar cada cambio y bajo qué condiciones una release puede avanzar.

## 1. Objetivo

La Fase 10 transforma la documentación acumulada en una especificación de desarrollo ejecutable. Sus objetivos son:

1. Establecer un índice inequívoco de fuentes de verdad.
2. Definir precedencia documental y control de drift.
3. Congelar restricciones no negociables para V1.
4. Traducir el roadmap V0.1 → V1.0 en epics y tareas ordenadas.
5. Establecer dependencias explícitas entre dominios y releases.
6. Crear un protocolo de trabajo incremental para agentes de IA.
7. Exigir evidencia verificable antes de marcar trabajo como terminado.
8. Integrar ADR, RFC, tests, documentación y release gates en un único loop.
9. Hacer posible detener y reanudar implementación sin perder estado.
10. Impedir que velocidad aparente degrade offline first, seguridad, accesibilidad, AGPL o capacidad de recuperación.

## 2. Estado de madurez de la especificación

Con esta fase se considera cerrada la **arquitectura de especificación previa a implementación** para V0.1. Esto no significa que el producto sea inmutable. Significa que cualquier cambio material posterior debe producir evidencia y quedar registrado mediante el mecanismo adecuado.

```text
Product Foundation
      ↓
Requirements
      ↓
Technical Architecture
      ↓
Security / Privacy
      ↓
UX / Design System
      ↓
Engineering Architecture
      ↓
QA / Verification
      ↓
Operations / Reliability
      ↓
Governance / Ecosystem
      ↓
Commercial Implementation
      ↓
════════════════════════════
SPEC DEVELOPMENT MASTER
════════════════════════════
      ↓
Executable backlog
      ↓
Implementation loops
      ↓
Release qualification
```

## 3. Source of Truth Index

| Orden | Documento                                                        | Estado                 | Autoridad                                                 |
| ----- | ---------------------------------------------------------------- | ---------------------- | --------------------------------------------------------- |
| 00    | `00-foundation/product-foundation-v0.2.md`                       | Normativo              | principios, licencia, autonomía técnica, ADRs rectores    |
| 01    | `01-functional-requirements/functional-architecture-v0.1.md`     | Normativo              | FR, NFR, OFF, SEC, ACC, BR y workflows                    |
| 02    | `02-technical-architecture/technical-architecture-v0.2.md`       | Normativo              | stack, persistencia, sync, eventos y arquitectura técnica |
| 03    | `03-security-privacy/security-privacy-threat-model-v0.1.md`      | Normativo              | amenazas, privacidad y security gates                     |
| 04    | `04-ux-design/ux-ui-design-system-v0.1.md`                       | Normativo              | IA, UX, design system y WCAG operacional                  |
| 05    | `05-engineering/repository-engineering-architecture-v0.1.md`     | Normativo              | monorepo, toolchain, conventions y CI                     |
| 06    | `06-quality/qa-testing-verification-strategy-v0.1.md`            | Normativo              | invariantes, suites, evidence y qualification gates       |
| 07    | `07-operations/deployment-operations-reliability-v0.1.md`        | Normativo              | deployment, backups, restore, SLO y runbooks              |
| 08    | `08-open-source/open-source-governance-plugin-ecosystem-v0.1.md` | Normativo              | AGPL operationalization, governance y plugins             |
| 09    | `09-commercial/commercial-implementation-playbook-v0.1.md`       | Normativo comercial    | paquetes, implementación, handover y COM gates            |
| 10    | `10-spec-development/master-spec-v0.1.md`                        | Normativo de ejecución | orden de trabajo, tareas, agent loop y checkpoints        |

Las versiones anteriores reemplazadas se conservan sólo como historial y contexto. No son fuente normativa si contradicen una versión vigente.

## 4. Precedencia documental

Ante conflicto aparente, aplicar este orden:

1. `AGPL-3.0-only`, obligaciones legales y restricciones de seguridad no negociables.
2. Foundation v0.2.
3. ADR `Accepted` más reciente aplicable.
4. Security/Privacy cuando endurece un requisito por riesgo material.
5. Documento normativo de fase más específico y reciente.
6. Functional Requirements y Business Rules no superseded.
7. Master Spec para secuenciación y ejecución.
8. Código existente solamente cuando sea consistente con lo anterior.

**Nunca se interpreta el código como autoridad suficiente para invalidar una especificación normativa.** Si el código y el spec divergen, se determina cuál está incorrecto y se corrige mediante ADR/RFC cuando corresponda.

## 5. Lenguaje normativo

Se usa semántica equivalente a MUST, MUST NOT, SHOULD, SHOULD NOT y MAY:

- **MUST**: requisito obligatorio para aceptación.
- **MUST NOT**: comportamiento prohibido.
- **SHOULD**: esperado salvo justificación documentada.
- **SHOULD NOT**: evitar salvo evidencia concreta.
- **MAY**: opcional y compatible.

## 6. Restricciones inmutables de V1

Un agente de implementación no puede cambiar unilateralmente estas restricciones:

1. Core y apps oficiales bajo `AGPL-3.0-only`.
2. Offline First y Local First como propiedades del producto, no como optimizaciones opcionales.
3. PWA React + TypeScript + Vite como cliente principal.
4. IndexedDB mediante Dexie como persistencia local V1.
5. Python + FastAPI + Pydantic + SQLAlchemy 2 + Alembic en backend.
6. PostgreSQL como persistencia autoritativa conectada.
7. UUIDv7 para entidades sincronizables.
8. Mutation log idempotente + cursor incremental + policy por dominio para sync.
9. Transactional Outbox para integration events.
10. Queue durable inicialmente sobre PostgreSQL.
11. REST JSON versionada + OpenAPI como API principal.
12. RBAC por capabilities y scopes con deny by default.
13. Docker Compose como deployment baseline.
14. PWA antes que desktop wrapper. Tauri sólo ante capability nativa demostrada.
15. Plugins comunitarios sin ejecución arbitraria dentro del Core.
16. WCAG 2.2 AA como mínimo de release.
17. Cero pérdida silenciosa de operaciones confirmadas.
18. Restore drill real antes de V1.
19. Data portability y handover como requisitos del producto y servicio.
20. No introducir dependencia obligatoria de SaaS propietario para operar el Core.

Modificar cualquiera requiere RFC explícito y, si afecta fundamentos del proyecto, Constitutional RFC. Cambiar la licencia está fuera de la autoridad ordinaria de un agente.

## 7. Autonomía técnica del agente

La autonomía técnica aprobada se formaliza en tres clases.

### Class A · Decisión autónoma inmediata

El agente decide sin pedir aprobación cuando la elección es local, reversible y no altera contratos normativos. Ejemplos:

- nombres internos
- extracción de helpers
- estructura local dentro de un módulo
- estrategia de memoization
- índices DB no semánticos
- composición de componentes
- optimización que respeta budgets y tests
- tooling menor compatible con el stack

### Class B · Decisión autónoma con ADR

El agente puede decidir y continuar, pero MUST escribir o actualizar ADR antes de considerar terminado el cambio. Ejemplos:

- nuevo boundary arquitectónico
- nuevo adapter oficial
- cambio de esquema con tradeoffs relevantes
- nueva conflict policy
- cambio de queue semantics
- estrategia de almacenamiento de un dominio
- dependencia runtime significativa

### Class C · Cambio constitucional o de producto

No se ejecuta como refactor ordinario. Requiere RFC y no puede romper restricciones inmutables sin autoridad explícita del proyecto. Ejemplos:

- abandonar offline first
- cambiar AGPL
- sustituir PWA como cliente principal
- hacer Cloud obligatorio
- introducir tracking invasivo
- convertir Core en microservicios sin necesidad demostrada
- alterar propiedad o portabilidad de datos

## 8. Regla de no bloqueo por preguntas técnicas

Si existe suficiente evidencia para una decisión Class A o B, el agente **MUST decidir** y continuar. No debe solicitar confirmación humana por preferencias de implementación ordinarias.

Sólo se detiene por una decisión realmente no inferible, un riesgo destructivo, un secreto/acceso ausente, un conflicto normativo o una acción legal/comercial que exceda la autoridad de implementación.

## 9. Product Boundary V1

V1 incluye:

- Identity & Access
- Customers
- Bicycles / Bicycle Passport
- Workshop / Service Orders
- Catalog / Inventory
- Purchasing
- POS / Payments
- Communications baseline
- Customer Portal
- Workshop Knowledge
- Automation
- Plugin SDK y registry baseline
- White Label
- Analytics básicos
- Documents / Print / QR
- Offline first y Sync Engine
- Standalone, LAN y Cloud deployment
- QA, security, accessibility y operations qualification

## 10. No Goals V1

No se construyen como requisitos de V1:

- contabilidad universal completa
- nómina
- ERP fiscal multi-jurisdicción
- marketplace propietario
- aplicación Android nativa separada
- app iOS nativa separada
- microservices
- Kubernetes
- Kafka
- Redis obligatorio
- blockchain
- IA obligatoria
- Computer Vision obligatoria
- IoT avanzado
- fleet avanzado
- rental avanzado
- ecommerce completo

Estos pertenecen a V1.x/V2/V3+ mediante Continuous Improvement Track y módulos.

## 11. Arquitectura ejecutable de referencia

```text
Windows / Android / browser
        ↓
React + TypeScript + Vite PWA
        ├─ accessible UI / Workshop Mode
        ├─ Dexie / IndexedDB repositories
        ├─ mutation queue
        ├─ sync coordinator
        └─ service worker / app shell
                ⇅
        REST/JSON + sync endpoints
                ⇅
FastAPI modular monolith
        ├─ bounded contexts
        ├─ SQLAlchemy 2
        ├─ PostgreSQL
        ├─ Transactional Outbox
        ├─ durable PostgreSQL jobs
        ├─ blob adapters
        └─ plugin/event extension points
```

## 12. Runtime topologies

### Standalone

PWA instalada con IndexedDB y backups/exportaciones locales. Internet no es requisito para operación esencial.

### Workshop LAN

Servidor local con PostgreSQL, API y PWA disponible sobre LAN segura. Es la topología recomendada para un taller físico con múltiples dispositivos porque mantiene operación aunque falle el ISP.

### Cloud / Connected

Servidor remoto para multisucursal, acceso remoto, portal público y servicios administrados.

## 13. Epic Catalog

| Epic | Nombre                             | Alcance                                                        |
| ---- | ---------------------------------- | -------------------------------------------------------------- |
| E00  | Repository, Licensing & Governance | Repositorio, AGPL, DCO, governance, release authority          |
| E01  | Engineering Toolchain              | pnpm, uv, CI, static analysis, reproducibilidad                |
| E02  | Platform Core                      | FastAPI modular monolith, API, jobs, errors, contracts         |
| E03  | Local First & Sync                 | Dexie, IndexedDB, mutation queue, cursors, conflict resolution |
| E04  | Organizations & Locations          | organizaciones, locations y scopes                             |
| E05  | Customers                          | clientes, contactos, preferencias y consentimiento             |
| E06  | Bicycles & Passport                | bicicletas, seriales, configuración e historial                |
| E07  | Workshop & Service Orders          | intake, diagnóstico, estimates, reparación, QC y timeline      |
| E08  | Files & Blobs                      | fotografías, documentos, queues y storage adapters             |
| E09  | Catalog & Inventory                | catálogo, variantes, ledger, stock y movimientos               |
| E10  | Purchasing                         | proveedores, órdenes de compra, recepción y costos             |
| E11  | POS & Payments                     | ventas, pagos, devoluciones, caja e idempotencia               |
| E12  | Communications                     | providers, email, WhatsApp adapters, consent y delivery        |
| E13  | Customer Portal                    | tracking, autorización remota, fotos y saldo                   |
| E14  | Workshop Knowledge                 | procedimientos, torque, compatibilidad y checklists            |
| E15  | Automation                         | WHEN/IF/THEN, triggers, actions, logs y builder                |
| E16  | Plugin Ecosystem                   | SDK, manifest, registry, trust y compatibility                 |
| E17  | White Label                        | BrandProfile, theme, documents, portal y communications        |
| E18  | Analytics                          | métricas operativas y privacidad                               |
| E19  | Documents, Print & QR              | notas, tickets, labels, QR y export                            |
| E20  | UX, Accessibility & i18n           | design system, Workshop Mode, WCAG e internacionalización      |
| E21  | Security & Privacy                 | authn, authz, threat model, supply chain y privacy             |
| E22  | QA & Verification                  | tests, chaos, migrations, performance, hardware y gates        |
| E23  | Deployment & Reliability           | Compose, Caddy, TLS, backup, restore, observability y ocwpctl  |
| E24  | Data Portability & Migration       | imports, exports, migration tooling y reconciliation           |
| E25  | Commercial Implementation          | discovery, demo, templates, supportability y pilot             |
| E26  | Release & Continuous Improvement   | qualification, release, governance y post release              |

## 14. Dependency Map

La dependencia macro se interpreta como grafo dirigido. Un epic puede comenzar parcialmente antes que su predecesor complete todo, pero ninguna task puede ignorar su `depends_on` explícito.

```text
E00 Repository/Governance
  ↓
E01 Toolchain
  ↓
E02 Platform Core ───────────────┐
  ↓                             │
E03 Local First & Sync          │
  ↓                             │
E04 Organizations               │
  ↓                             │
E05 Customers                   │
  ↓                             │
E06 Bicycles                    │
  ↓                             │
E07 Workshop                    │
  ├────────→ E08 Files          │
  ├────────→ E09 Inventory ─→ E10 Purchasing
  ├────────→ E11 POS/Payments
  ├────────→ E12 Communications ─→ E13 Portal
  ├────────→ E14 Knowledge
  └────────→ E15 Automation

Cross-cutting:
E20 UX/A11y/i18n
E21 Security/Privacy
E22 QA/Verification
E23 Deployment/Reliability
E16 Plugins
E17 White Label
E18 Analytics
E19 Documents/Print/QR
E24 Data Portability
E25 Commercial Implementation
E26 Release/Continuous Improvement
```

## 15. Release Train

| Release | Nombre                 | Resultado demostrable                                                  | Tareas maestras |
| ------- | ---------------------- | ---------------------------------------------------------------------- | --------------: |
| V0.1    | Foundations            | primer vertical slice Customer sincronizable y plataforma reproducible |              36 |
| V0.2    | Workshop Core          | ciclo completo de taller online/offline                                |              23 |
| V0.3    | Inventory & Purchasing | inventario ledger y purchasing                                         |              17 |
| V0.4    | POS & Payments         | venta, cobro e inventario transaccional                                |              14 |
| V0.5    | Communications         | communication hub baseline                                             |              11 |
| V0.6    | Customer Experience    | portal cliente y autorización remota                                   |              11 |
| V0.7    | Workshop Intelligence  | knowledge y checklists                                                 |               9 |
| V0.8    | Automation             | automation engine                                                      |              12 |
| V0.9    | Production Hardening   | hardening, operations, plugin/white label y commercial readiness       |              30 |
| V1.0    | Production Release     | release productiva cualificada                                         |              25 |

## 16. Regla de vertical slicing

Cada release se construye mediante slices que atraviesan las capas necesarias. Evitar secuencias como "terminar todo backend" y posteriormente "hacer frontend".

Un slice correcto incluye, cuando aplique:

```text
Domain rule
→ application service
→ persistence
→ API contract
→ generated client
→ local repository
→ UI
→ offline behavior
→ sync behavior
→ security
→ accessibility
→ tests
→ observability
→ docs
```

## 17. Work Item Schema

Toda tarea ejecutable MUST tener como mínimo:

```yaml
id: R02-T008
release: V0.2
epic: E07
status: ready
objective: Implementar estimate con mano de obra, partes y totales
requirements:
  - FR-...
risks:
  - QRISK-...
depends_on:
  - R02-T007
files_expected:
  - services/platform/...
  - apps/web/...
acceptance:
  - criterio observable 1
  - criterio observable 2
verification:
  - unit
  - integration
  - e2e
evidence:
  - pending
adr_required: false
```

El backlog maestro da intención, orden y evidencia mínima. Antes de implementar, el agente completa referencias precisas a requisitos y riesgos desde los documentos normativos.

## 18. Execution State

El repositorio MUST conservar:

`docs/10-spec-development/execution-state.yaml`

Contenido mínimo:

```yaml
spec_version: '0.1'
release: 'V0.1'
epic: 'E00'
task: 'R01-T001'
status: 'in_progress'
last_verified_commit: null
last_green_ci: null
active_adrs: []
blockers: []
failed_checks: []
evidence: []
next_candidates: []
notes: []
```

Este archivo es estado operativo, no sustituto de Git. Debe actualizarse al finalizar cada task o cuando el agente se detenga por un bloqueo real.

## 19. Status Model

```text
planned
→ ready
→ in_progress
→ verifying
→ done

Alternativas:
blocked
failed
superseded
```

Una task `done` no puede tener gates requeridos fallando.

## 20. Definition of Ready por task

Una tarea está `ready` cuando:

1. su objetivo es verificable
2. dependencias requeridas están `done` o explícitamente satisfechas
3. requisitos normativos relevantes están identificados
4. riesgo principal está identificado
5. acceptance criteria no dependen de interpretación subjetiva
6. datos o fixtures necesarios existen o forman parte de la task
7. no requiere credencial/servicio ausente sin adapter o fake oficial
8. cualquier ADR previo obligatorio ya está Accepted

## 21. Definition of Done por task

Una tarea está `done` sólo cuando:

1. implementación completa sin TODO ocultando alcance obligatorio
2. tests de la capa apropiada pasan
3. casos negativos/degradados relevantes pasan
4. lint, format y typecheck pasan
5. migraciones son reproducibles cuando existan
6. offline/sync se verifican cuando aplique
7. seguridad y privacidad se verifican cuando aplique
8. accesibilidad se verifica cuando exista UI
9. observability hooks existen en operaciones relevantes
10. documentación se actualiza
11. ADR/RFC se actualiza si la arquitectura cambió
12. evidence queda registrada
13. no existen cambios accidentales fuera de scope

## 22. Master Execution Loop

El agente opera repetidamente con este ciclo:

```text
1. CONTEXT SYNC
2. STATE RECOVERY
3. SELECT NEXT READY TASK
4. LOAD NORMATIVE REQUIREMENTS
5. PRE-FLIGHT
6. WRITE/REFINE TEST OR INVARIANT
7. IMPLEMENT SMALLEST COMPLETE SLICE
8. RUN LOCAL VERIFICATION LADDER
9. INSPECT DIFF AND DATA MIGRATIONS
10. RUN DOMAIN-SPECIFIC DEGRADATION TESTS
11. UPDATE DOCS / ADR / EXECUTION STATE
12. MARK DONE ONLY WITH EVIDENCE
13. SELECT NEXT READY TASK
14. REPEAT UNTIL RELEASE CHECKPOINT
```

## 23. Context Sync

Al iniciar una sesión de implementación:

1. leer `execution-state.yaml`
2. leer este Master Spec
3. leer Foundation v0.2
4. cargar solamente documentos de fase necesarios para la task actual
5. inspeccionar Git status y cambios existentes
6. inspeccionar ADRs activos
7. no asumir que el repositorio está limpio
8. no sobrescribir trabajo ajeno

## 24. State Recovery

Si una sesión anterior terminó abruptamente:

1. inspeccionar Git diff
2. identificar task indicada en execution-state
3. ejecutar tests más cercanos
4. determinar si el cambio está completo, parcial o inválido
5. conservar trabajo válido
6. revertir únicamente cambios propios claramente defectuosos
7. actualizar estado antes de continuar

Nunca se inicia otra task mientras el repositorio se encuentra en un estado ambiguo no comprendido.

## 25. Task Selection

Seleccionar la task `ready` de mayor prioridad que:

- pertenezca al release activo
- tenga dependencias satisfechas
- reduzca riesgo temprano
- produzca un slice demostrable cuando sea posible
- no introduzca trabajo speculative para releases futuras

Cuando dos tasks sean independientes, pueden ejecutarse en paralelo sólo si sus archivos, migraciones y contratos no generan competencia peligrosa.

## 26. Pre-flight

Antes de editar:

```text
□ git status entendido
□ requirements cargados
□ acceptance criteria concretos
□ dependencias satisfechas
□ test strategy definida
□ migration impact entendido
□ offline impact entendido
□ security impact entendido
□ a11y impact entendido
□ ADR requirement evaluado
```

## 27. Test First para invariantes

Para ledger, pagos, state machines, sync, migrations, authz y automation MUST escribirse o identificarse primero la propiedad/invariante que demostraría corrección.

No es obligatorio forzar TDD ceremonial en UI trivial, pero sí demostrar el comportamiento antes de declarar completitud.

## 28. Database Change Loop

Toda modificación de PostgreSQL sigue:

```text
model/domain decision
→ migration forward-first
→ empty DB test
→ previous snapshot test
→ demo-workshop test
→ load fixture test cuando aplique
→ application compatibility
→ rollback/recovery plan cuando sea material
```

No se escribe una migration que presuponga actualización simultánea de todos los clientes offline.

## 29. IndexedDB Change Loop

Todo schema upgrade Dexie MUST probar:

- versión local anterior soportada
- pending mutations presentes
- reanudación
- índices
- data preservation
- failure visibility

El agente no puede resolver errores de IndexedDB mediante `deleteDatabase()` como estrategia de producción.

## 30. Sync Change Loop

Cualquier cambio al Sync Engine MUST verificar:

1. idempotencia
2. duplicate delivery
3. reorder razonable
4. reconnect
5. timeout
6. two-device convergence
7. permanent failure visibility
8. cursor durability
9. tombstones cuando aplique
10. invariant de dominio

Los timestamps de cliente nunca son autoridad única de orden.

## 31. UI Change Loop

Cada UI significativa MUST comprobar:

- keyboard navigation
- focus visible
- semantic labels
- touch targets
- loading/empty/error states
- offline state
- sync state cuando aplique
- reduced motion
- responsive Windows/tablet/mobile según surface
- no depender sólo de color

## 32. Security Change Loop

Para authn, authz, portal, uploads, plugins, payments o admin:

```text
threat case
→ positive test
→ negative/abuse test
→ least privilege check
→ log/redaction check
→ secret exposure check
→ dependency/supply-chain implications
```

## 33. Plugin Change Loop

Un plugin o connector nuevo MUST declarar:

- id y versión
- licencia
- core compatibility range
- runtime type
- capabilities
- network hosts
- secrets
- events
- data ownership
- install/uninstall behavior
- failure isolation

Community code se trata como untrusted hasta verificación.

## 34. Operations Change Loop

Un cambio operativo material MUST responder:

- cómo se instala
- cómo se actualiza
- cómo se monitorea
- cómo falla
- cómo se diagnostica
- cómo se restaura
- cómo se revierte

Si no existe recovery story, el cambio no está listo para producción.

## 35. Documentation Change Rule

La documentación se actualiza en la misma task que cambia el comportamiento. No se difiere sistemáticamente a una fase posterior.

Actualizar según corresponda:

- user docs
- operator docs
- API docs
- ADR
- release notes
- migration notes
- plugin docs
- security docs

## 36. Verification Ladder

Ejecutar desde menor costo hacia mayor cobertura:

```text
1. formatter/lint cercano
2. unit/property tests cercanos
3. typecheck
4. integration tests del módulo
5. contract tests
6. component tests
7. E2E del journey afectado
8. offline / multi-device
9. security / a11y specialized checks
10. full CI requerido por release
```

No ejecutar suites enormes como sustituto de pruebas específicas. Tampoco omitir la suite grande en checkpoints que la exigen.

## 37. Evidence Model

Evidence aceptable incluye:

- test report
- CI run
- benchmark
- migration rehearsal
- screenshot/visual regression interno
- accessibility report
- security scan
- restore log
- device matrix result
- ADR Accepted

Cada evidencia debe registrar commit o versión cuando sea posible.

## 38. Drift Detection

En cada checkpoint de release, comprobar:

1. OpenAPI generado sin drift inesperado
2. schema DB y migrations consistentes
3. Dexie version y migrations consistentes
4. event contracts versionados
5. plugin compatibility intacta
6. docs de release alineadas
7. requirements traceability sin huecos críticos
8. execution-state consistente con Git

## 39. ADR Workflow

Crear ADR cuando una decisión Class B cambie arquitectura o tradeoffs duraderos.

Estado:

```text
Proposed
→ Accepted
→ Superseded
```

Un ADR MUST incluir contexto, decisión, alternativas, consecuencias, seguridad, offline, accesibilidad, verificación y estrategia de supersession.

## 40. RFC Workflow

Usar RFC para:

- cambio de alcance transversal
- nueva extensión pública significativa
- cambios de compatibilidad mayores
- cambios de governance
- cambios constitucionales

El agente puede redactar RFC completo autónomamente. No debe implementar un cambio constitucional antes de su aceptación por la autoridad correspondiente.

## 41. Commit Discipline

Preferencia:

- cambios pequeños y coherentes
- Conventional Commits
- DCO Signed-off-by
- no mezclar refactor masivo con feature salvo necesidad
- no formatear archivos ajenos sin razón
- no incluir secretos
- no commitear generated artifacts no definidos por política

## 42. Pull Request Contract

Un PR debe describir:

- qué problema resuelve
- task ID
- requirements afectados
- riesgos
- tests/evidence
- migration impact
- offline/sync impact
- security/privacy impact
- accessibility impact
- ADR/RFC relacionado
- screenshots sólo cuando aporten evidencia UI

## 43. Stop Conditions

El agente MUST detener la task actual y registrar `blocked` cuando:

1. falta una credencial o acceso imprescindible que no puede simularse responsablemente
2. existe riesgo de destruir datos no respaldados
3. dos documentos normativos vigentes se contradicen materialmente
4. una acción requiere cambiar una restricción inmutable
5. una migration destructiva no tiene recovery path
6. un proveedor externo cambió un contrato y no existe evidencia suficiente
7. tests demuestran una corrupción que requiere rediseño más amplio
8. el repositorio contiene cambios ajenos incompatibles imposibles de preservar automáticamente

No son stop conditions:

- preferencia de librería menor
- naming
- estructura interna reversible
- decisiones Class A
- decisiones Class B que pueden documentarse con ADR

## 44. Failure Recovery Loop

Cuando una implementación falla:

```text
Observe failure
→ classify root cause
→ preserve logs/evidence
→ reproduce minimally
→ decide: fix / revert own change / supersede approach
→ add regression test
→ verify closest layer
→ verify affected journey
→ update state
```

Nunca se "arregla" una suite deshabilitando el test sin demostrar que el test era incorrecto.

## 45. Anti-cheating Rules para agentes

Está prohibido:

- comentar tests para hacerlos pasar
- usar `skip` permanente sin issue y rationale
- relajar lint/type safety para ocultar errores
- devolver valores hardcoded sólo para fixtures
- ignorar excepciones silenciosamente
- borrar IndexedDB para resolver migraciones
- truncar tablas para resolver inconsistencia
- usar `latest` en producción
- almacenar secretos en repo
- marcar tarea done con CI roja
- declarar soporte offline sin probar desconexión real/simulada
- introducir una dependencia SaaS obligatoria para evitar implementar una capability del Core

## 46. Release Checkpoint Protocol

Al terminar las tasks de una release:

1. congelar nuevas features del release
2. ejecutar gates específicos
3. resolver C0/C1
4. validar migrations
5. ejecutar journey demostrable
6. actualizar docs
7. actualizar changelog
8. actualizar execution-state a siguiente release sólo con evidence verde

## 47. Requirement Traceability Strategy

No se copiarán los 177 identificadores de Fase 1 dentro de cada task por anticipado si aún no se implementa. La trazabilidad se completa just-in-time antes de ejecutar cada task.

Se mantiene una matriz en:

`docs/10-spec-development/traceability.csv` o representación equivalente versionada.

Columnas mínimas:

```text
requirement_id
release
epic
task_id
test_id
status
evidence
```

Un requisito C0/C1 o security critical no puede llegar a V1 sin task, test y evidence asociados.

## 48. Unified Gate Families

V1 combina gates de varias fases:

| Familia  | Fuente          | Propósito                                         |
| -------- | --------------- | ------------------------------------------------- |
| Product  | Fase 1 / Master | comportamiento y business rules                   |
| QA       | Fase 6          | correctitud, sync, migration, restore, devices    |
| Security | Fase 3 / 6      | authz, DAST, vulnerabilities, privacy             |
| OPS      | Fase 7          | instalación, backup, TLS, recovery, observability |
| GOV      | Fase 8          | AGPL, DCO, release authority, plugin governance   |
| COM      | Fase 9          | demo, templates, handover, supportability         |

Un V1 técnico que no pasa OPS/GOV no es V1 productivo. Un V1 productivo que no pasa COM no debe anunciarse todavía como paquete comercial estandarizado.

## 49. V0.1 Checkpoint

Debe demostrar, como mínimo:

- fresh clone reproducible
- frontend y backend arrancan
- PostgreSQL migrations
- Dexie local DB
- Customer vertical slice
- offline create/update
- sync idempotente
- two-device convergence mínima
- OpenAPI/client generation
- RBAC baseline
- no secrets
- AGPL/DCO baseline

## 50. V0.2 Checkpoint

Debe demostrar un taller capaz de recibir y procesar una bicicleta completamente, con Internet o sin Internet, hasta estado de entrega.

## 51. V0.3 Checkpoint

Debe demostrar que stock es consecuencia verificable del ledger y que workshop consumption/purchasing producen movimientos consistentes incluso bajo reconexión.

## 52. V0.4 Checkpoint

Debe demostrar venta, pagos, devoluciones e impacto de inventario sin doble contabilización y con comportamiento offline explícito.

## 53. V0.5 Checkpoint

Debe demostrar provider abstraction, consent, queue, retry y graceful degradation de comunicación.

## 54. V0.6 Checkpoint

Debe demostrar tracking y autorización remota segura sin cuenta obligatoria, con aislamiento entre clientes.

## 55. V0.7 Checkpoint

Debe demostrar knowledge contextual, provenance y checklists operativos sin presentar contenido comunitario como dato de fabricante.

## 56. V0.8 Checkpoint

Debe demostrar automatizaciones idempotentes, auditables y protegidas contra loops.

## 57. V0.9 Checkpoint

Debe demostrar hardening de producción, restore, device matrix, performance, plugin SDK, white labeling, i18n, operations y commercial readiness.

## 58. V1.0 Checkpoint

V1 sólo se publica cuando todos los gates bloqueantes relevantes estén verdes y un piloto real controlado no haya revelado defectos C0/C1 pendientes.

## 59. Backlog maestro

Las tareas siguientes representan el orden inicial de implementación. El agente puede dividir una task si excede una unidad razonable de review, pero no puede fusionar tareas de forma que se pierdan acceptance criteria o evidence.

### V0.1 · Foundations

| ID       | Epic | Tarea                                                                            | Depends           | Evidence mínima              |
| -------- | ---- | -------------------------------------------------------------------------------- | ----------------- | ---------------------------- |
| R01-T001 | E00  | Crear raíz del monorepo y archivos base de repositorio                           | -                 | Repositorio reproducible     |
| R01-T002 | E00  | Añadir LICENSE con texto GNU AGPL v3 y declarar SPDX AGPL-3.0-only               | R01-T001          | REUSE/SPDX gate              |
| R01-T003 | E00  | Crear CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, GOVERNANCE y MAINTAINERS baseline | R01-T002          | Governance review            |
| R01-T004 | E00  | Configurar DCO y Signed-off-by como gate de contribución                         | R01-T003          | CI DCO check                 |
| R01-T005 | E01  | Configurar pnpm workspace y runtime Node fijado                                  | R01-T001          | pnpm install reproducible    |
| R01-T006 | E01  | Configurar uv workspace y Python runtime fijado                                  | R01-T001          | uv sync reproducible         |
| R01-T007 | E01  | Crear GitHub Actions CI baseline para lint, typecheck, unit e integración        | R01-T005,R01-T006 | CI verde                     |
| R01-T008 | E01  | Configurar Ruff, mypy, ESLint, Prettier y TypeScript strict                      | R01-T005,R01-T006 | Static checks verdes         |
| R01-T009 | E02  | Crear paquete backend modular monolith y entrypoints API, worker y CLI           | R01-T006          | Smoke tests backend          |
| R01-T010 | E02  | Crear aplicación React + TypeScript + Vite PWA                                   | R01-T005          | Build PWA                    |
| R01-T011 | E20  | Crear packages/ui con primitives accesibles y tokens semánticos                  | R01-T010          | Component tests + axe        |
| R01-T012 | E20  | Configurar Tailwind CSS y capa de branding desacoplada                           | R01-T011          | Theme smoke                  |
| R01-T013 | E02  | Configurar FastAPI, Pydantic, SQLAlchemy 2 y Alembic                             | R01-T009          | API + migration smoke        |
| R01-T014 | E03  | Configurar PostgreSQL de desarrollo mediante Docker Compose                      | R01-T013          | Integration DB test          |
| R01-T015 | E03  | Crear Dexie repository abstraction y schema local inicial                        | R01-T010          | IndexedDB unit/integration   |
| R01-T016 | E03  | Implementar UUIDv7 factory compartida                                            | R01-T009,R01-T015 | Property tests               |
| R01-T017 | E03  | Definir mutation envelope y mutation_queue local durable                         | R01-T015,R01-T016 | Idempotency tests            |
| R01-T018 | E03  | Implementar endpoint sync mutations con idempotency guard                        | R01-T017          | Integration sync             |
| R01-T019 | E03  | Implementar change feed con cursor incremental por organization/location         | R01-T018          | Cursor tests                 |
| R01-T020 | E03  | Implementar pull, merge y durable cursor advance en cliente                      | R01-T019          | Two client convergence       |
| R01-T021 | E03  | Crear Conflict Center baseline para fallos permanentes visibles                  | R01-T020          | Conflict E2E                 |
| R01-T022 | E02  | Implementar Transactional Outbox                                                 | R01-T013          | DB transaction tests         |
| R01-T023 | E02  | Implementar durable PostgreSQL job queue con worker SKIP LOCKED                  | R01-T022          | Concurrency tests            |
| R01-T024 | E08  | Crear BlobStorage abstraction con filesystem local                               | R01-T009          | Blob integration tests       |
| R01-T025 | E02  | Crear error envelope, request IDs y logging JSON estructurado                    | R01-T009          | API contract tests           |
| R01-T026 | E02  | Generar OpenAPI determinista y cliente TypeScript                                | R01-T013,R01-T010 | OpenAPI drift gate           |
| R01-T027 | E04  | Modelar Organization y Location mínimos                                          | R01-T013          | Migration + repository tests |
| R01-T028 | E02  | Implementar Identity baseline con sesiones seguras                               | R01-T027          | Authn negative tests         |
| R01-T029 | E02  | Implementar RBAC por capabilities y scopes deny by default                       | R01-T028          | Authz negative suite         |
| R01-T030 | E05  | Implementar Customer vertical slice end to end local + servidor + sync           | R01-T020,R01-T029 | Golden slice online/offline  |
| R01-T031 | E22  | Crear fixtures minimal, demo-workshop y load baseline                            | R01-T030          | Fixture validation           |
| R01-T032 | E23  | Crear compose de desarrollo y ocwpctl doctor/status baseline                     | R01-T009,R01-T014 | Fresh install smoke          |
| R01-T033 | E23  | Crear backup baseline de PostgreSQL y validación estructural                     | R01-T014          | Backup/restore smoke         |
| R01-T034 | E21  | Añadir secret scanning, dependency scanning y baseline SAST                      | R01-T007          | Security CI                  |
| R01-T035 | E22  | Ejecutar spike Dexie 100k+ y Android/Windows storage baseline                    | R01-T015          | Benchmark evidence           |
| R01-T036 | E22  | Ejecutar chaos sync multidispositivo inicial                                     | R01-T020          | Chaos evidence               |

### V0.2 · Workshop Core

| ID       | Epic | Tarea                                                                                     | Depends  | Evidence mínima              |
| -------- | ---- | ----------------------------------------------------------------------------------------- | -------- | ---------------------------- |
| R02-T001 | E05  | Completar CRUD y búsqueda de Customers con contacto y preferencias                        | V0.1     | FR customer suite            |
| R02-T002 | E06  | Modelar Bicycle con propietario, serial, atributos y custom fields                        | R02-T001 | Domain + migration tests     |
| R02-T003 | E06  | Implementar Bicycle Passport e historial técnico                                          | R02-T002 | Passport E2E                 |
| R02-T004 | E07  | Implementar ServiceOrder aggregate y state machine canónica                               | R02-T002 | State property tests         |
| R02-T005 | E07  | Implementar intake rápido con problema reportado y prioridad                              | R02-T004 | Reception E2E                |
| R02-T006 | E08  | Integrar fotografías de recepción offline first                                           | R02-T005 | Offline attachment test      |
| R02-T007 | E07  | Implementar inspection y diagnosis                                                        | R02-T004 | Workflow tests               |
| R02-T008 | E07  | Implementar estimate con mano de obra, partes y totales                                   | R02-T007 | Calculation/property tests   |
| R02-T009 | E07  | Implementar authorization auditada con approve/reject                                     | R02-T008 | Auth + audit E2E             |
| R02-T010 | E07  | Implementar task list de reparación y asignación de mecánico                              | R02-T009 | Workshop flow                |
| R02-T011 | E07  | Implementar estados WAITING_FOR_PARTS, ON_HOLD, REWORK y CANCELLED                        | R02-T004 | State machine negative tests |
| R02-T012 | E07  | Implementar Quality Control checklist y pass/fail                                         | R02-T010 | QC E2E                       |
| R02-T013 | E07  | Implementar timeline append only de eventos relevantes                                    | R02-T004 | Audit invariant              |
| R02-T014 | E20  | Implementar Reception fast path con objetivo de menos de 60s para cliente/bici existentes | R02-T005 | Usability timing             |
| R02-T015 | E20  | Implementar Workshop Mode táctil con targets 56x56 en acciones principales                | R02-T010 | Tablet a11y pass             |
| R02-T016 | E20  | Implementar Kanban de órdenes por estado                                                  | R02-T004 | UI integration               |
| R02-T017 | E03  | Definir merge policies de Customer, Bicycle y ServiceOrder                                | R02-T013 | Conflict suite               |
| R02-T018 | E03  | Probar ServiceOrder con dos dispositivos offline y reconexión                             | R02-T017 | Multi-device convergence     |
| R02-T019 | E19  | Generar comprobante/orden imprimible básico                                               | R02-T008 | Print visual test            |
| R02-T020 | E19  | Generar QR interno de orden y bicicleta                                                   | R02-T003 | QR scan test                 |
| R02-T021 | E21  | Aplicar audit logging a transiciones administrativas                                      | R02-T004 | Audit security test          |
| R02-T022 | E22  | Crear golden journey recepción→diagnóstico→autorización→reparación→QC→entrega             | R02-T012 | Playwright online/offline    |
| R02-T023 | E22  | Ejecutar UAT workshop core con fixture demo-workshop                                      | R02-T022 | UAT evidence                 |

### V0.3 · Inventory & Purchasing

| ID       | Epic | Tarea                                                                                                              | Depends       | Evidence mínima                |
| -------- | ---- | ------------------------------------------------------------------------------------------------------------------ | ------------- | ------------------------------ |
| R03-T001 | E09  | Modelar Product, SKU, category, brand y variant                                                                    | V0.2          | Catalog tests                  |
| R03-T002 | E09  | Modelar inventory ledger append only                                                                               | R03-T001      | Ledger invariants              |
| R03-T003 | E09  | Implementar movimientos PURCHASE, SALE, WORKSHOP_USE, RETURN, ADJUSTMENT, TRANSFER, LOSS, DAMAGE, DONATION y REUSE | R03-T002      | Property tests                 |
| R03-T004 | E09  | Derivar stock desde ledger y crear materialized projection verificable                                             | R03-T003      | Rebuild equality test          |
| R03-T005 | E09  | Implementar ubicaciones físicas y stock por location                                                               | R03-T004      | Location tests                 |
| R03-T006 | E09  | Implementar stock mínimo y alertas low stock                                                                       | R03-T004      | Threshold tests                |
| R03-T007 | E10  | Modelar Supplier y datos operativos                                                                                | R03-T001      | Supplier tests                 |
| R03-T008 | E10  | Implementar Purchase Order state machine                                                                           | R03-T007      | PO workflow                    |
| R03-T009 | E10  | Implementar recepción parcial/completa y movimientos de inventario                                                 | R03-T008      | Transactional tests            |
| R03-T010 | E10  | Implementar histórico de costo y proveedor                                                                         | R03-T009      | Reporting tests                |
| R03-T011 | E09  | Integrar consumo de partes desde ServiceOrder como WORKSHOP_USE                                                    | R03-T002,V0.2 | Atomic workshop inventory test |
| R03-T012 | E09  | Implementar ajustes mediante compensación, no edición destructiva                                                  | R03-T002      | Compensation invariant         |
| R03-T013 | E19  | Implementar búsqueda y escaneo QR/barcode para productos                                                           | R03-T001      | Scanner E2E                    |
| R03-T014 | E20  | Implementar vistas densas de inventario con TanStack Table                                                         | R03-T004      | Keyboard/a11y/table tests      |
| R03-T015 | E03  | Probar ledger offline concurrente en múltiples dispositivos                                                        | R03-T002      | Sync property/chaos tests      |
| R03-T016 | E22  | Crear reconciliation report stock materializado vs ledger                                                          | R03-T004      | Reconciliation evidence        |
| R03-T017 | E22  | Ejecutar fixture load con 100k+ movements y performance budget                                                     | R03-T016      | Performance evidence           |

### V0.4 · POS & Payments

| ID       | Epic | Tarea                                                                  | Depends       | Evidence mínima               |
| -------- | ---- | ---------------------------------------------------------------------- | ------------- | ----------------------------- |
| R04-T001 | E11  | Implementar POS cart y búsqueda rápida de productos/servicios          | V0.3          | POS component/E2E             |
| R04-T002 | E11  | Implementar pricing, taxes configurables y descuentos auditables       | R04-T001      | Calculation properties        |
| R04-T003 | E11  | Crear Sale aggregate y líneas de venta                                 | R04-T002      | Domain tests                  |
| R04-T004 | E11  | Implementar payment records con idempotency key                        | R04-T003      | Payment idempotency           |
| R04-T005 | E11  | Soportar pagos parciales y múltiples métodos                           | R04-T004      | Payment workflow              |
| R04-T006 | E11  | Implementar devoluciones con movimientos compensatorios                | R04-T003,V0.3 | Return invariants             |
| R04-T007 | E11  | Integrar venta con reducción de inventario atómica                     | R04-T003      | Transaction test              |
| R04-T008 | E11  | Integrar cobro de ServiceOrder en POS                                  | R04-T003,V0.2 | Service payment E2E           |
| R04-T009 | E11  | Implementar cash session y cierre básico                               | R04-T004      | Cash reconciliation           |
| R04-T010 | E19  | Generar recibo/ticket imprimible                                       | R04-T003      | Print test                    |
| R04-T011 | E03  | Definir comportamiento POS offline sin proveedor externo               | R04-T004      | Offline POS E2E               |
| R04-T012 | E11  | Bloquear promesa de pago externo offline cuando proveedor requiera red | R04-T011      | Degradation UX test           |
| R04-T013 | E21  | Audit logging de descuentos, devoluciones y ajustes sensibles          | R04-T002      | Audit tests                   |
| R04-T014 | E22  | Ejecutar invariant suite Sale + Payment + Inventory                    | R04-T007      | Property/integration evidence |

### V0.5 · Communications

| ID       | Epic | Tarea                                                      | Depends       | Evidence mínima      |
| -------- | ---- | ---------------------------------------------------------- | ------------- | -------------------- |
| R05-T001 | E12  | Definir CommunicationProvider interface y message envelope | V0.4          | Contract tests       |
| R05-T002 | E12  | Modelar templates versionadas e i18n                       | R05-T001      | Template tests       |
| R05-T003 | E12  | Modelar communication consent y preferencias               | R05-T001      | Consent tests        |
| R05-T004 | E12  | Implementar SMTP email adapter oficial                     | R05-T001      | Provider integration |
| R05-T005 | E12  | Implementar WA0 deep link a WhatsApp                       | R05-T003      | UI E2E               |
| R05-T006 | E12  | Implementar WA1 templates copiables                        | R05-T002      | Template E2E         |
| R05-T007 | E12  | Crear outbound queue con retry/backoff y status            | R05-T004      | Queue tests          |
| R05-T008 | E12  | Integrar service_order.ready con mensaje configurable      | R05-T007,V0.2 | Event integration    |
| R05-T009 | E12  | Implementar provider outage graceful degradation           | R05-T007      | Chaos provider test  |
| R05-T010 | E21  | Redactar logs para evitar contenido sensible innecesario   | R05-T007      | Privacy log test     |
| R05-T011 | E22  | Probar mensajes duplicados y deduplicación                 | R05-T007      | Idempotency suite    |

### V0.6 · Customer Experience

| ID       | Epic | Tarea                                                            | Depends  | Evidence mínima        |
| -------- | ---- | ---------------------------------------------------------------- | -------- | ---------------------- |
| R06-T001 | E13  | Diseñar secure portal token model con expiración y revocación    | V0.5     | Security tests         |
| R06-T002 | E13  | Implementar portal público de estado de ServiceOrder             | R06-T001 | Portal E2E             |
| R06-T003 | E13  | Mostrar timeline público filtrado por visibilidad                | R06-T002 | Privacy tests          |
| R06-T004 | E13  | Mostrar estimate y detalle de trabajos autorizables              | R06-T002 | Portal component tests |
| R06-T005 | E13  | Implementar approve/reject remoto auditado                       | R06-T004 | Authorization E2E      |
| R06-T006 | E13  | Mostrar fotografías explícitamente marcadas como cliente-visible | R06-T002 | Access control tests   |
| R06-T007 | E13  | Mostrar saldo/estado de pago sin exponer datos de otros clientes | R06-T002 | Isolation tests        |
| R06-T008 | E19  | Generar QR/link seguro del portal                                | R06-T001 | QR portal test         |
| R06-T009 | E20  | Optimizar portal mobile first y WCAG 2.2 AA                      | R06-T002 | Mobile a11y pass       |
| R06-T010 | E21  | Implementar rate limiting y anti enumeration                     | R06-T001 | DAST/negative tests    |
| R06-T011 | E22  | Probar token expired/revoked/reused/guessed                      | R06-T010 | Security E2E           |

### V0.7 · Workshop Intelligence

| ID       | Epic | Tarea                                                                     | Depends  | Evidence mínima           |
| -------- | ---- | ------------------------------------------------------------------------- | -------- | ------------------------- |
| R07-T001 | E14  | Modelar KnowledgeEntry con source type Manufacturer, Workshop y Community | V0.6     | Domain tests              |
| R07-T002 | E14  | Implementar procedimientos y troubleshooting interno                      | R07-T001 | Knowledge CRUD            |
| R07-T003 | E14  | Implementar torque specifications con provenance                          | R07-T001 | Provenance tests          |
| R07-T004 | E14  | Implementar compatibility metadata estructurada baseline                  | R07-T001 | Compatibility rules tests |
| R07-T005 | E14  | Implementar checklist templates de mantenimiento y QC                     | R07-T001 | Checklist tests           |
| R07-T006 | E14  | Integrar conocimiento contextual dentro de Workshop Mode                  | R07-T002 | Mechanic UX E2E           |
| R07-T007 | E14  | Implementar search local/server de Knowledge                              | R07-T001 | Search tests              |
| R07-T008 | E21  | Mostrar claramente nivel/fuente de confianza del conocimiento             | R07-T003 | UX correctness test       |
| R07-T009 | E22  | Crear fixtures de Knowledge sin copiar material propietario incompatible  | R07-T001 | License review            |

### V0.8 · Automation

| ID       | Epic | Tarea                                                 | Depends       | Evidence mínima       |
| -------- | ---- | ----------------------------------------------------- | ------------- | --------------------- |
| R08-T001 | E15  | Modelar AutomationRule WHEN/IF/THEN                   | V0.7          | Domain tests          |
| R08-T002 | E15  | Definir catálogo de triggers versionados              | R08-T001      | Contract tests        |
| R08-T003 | E15  | Definir conditions seguras y deterministas            | R08-T001      | Property tests        |
| R08-T004 | E15  | Definir action provider interface                     | R08-T001      | Contract tests        |
| R08-T005 | E15  | Implementar execution log e idempotency               | R08-T004      | Idempotency tests     |
| R08-T006 | E15  | Implementar acción send communication                 | R08-T004,V0.5 | Integration tests     |
| R08-T007 | E15  | Implementar acción create reminder/delayed job        | R08-T004      | Job queue tests       |
| R08-T008 | E15  | Implementar regla inventory.low → purchase suggestion | R08-T004,V0.3 | Automation E2E        |
| R08-T009 | E15  | Implementar regla service_order.ready → notify        | R08-T006,V0.2 | Automation E2E        |
| R08-T010 | E20  | Implementar Automation Builder visual baseline        | R08-T001      | A11y/component tests  |
| R08-T011 | E21  | Añadir capability checks a cada action                | R08-T004      | Authz negative tests  |
| R08-T012 | E22  | Crear automation sandbox/dry run y loop prevention    | R08-T005      | Safety/property tests |

### V0.9 · Production Hardening

| ID       | Epic | Tarea                                                                         | Depends  | Evidence mínima        |
| -------- | ---- | ----------------------------------------------------------------------------- | -------- | ---------------------- |
| R09-T001 | E21  | Completar threat model verification y security requirements pendientes        | V0.8     | Security gate evidence |
| R09-T002 | E21  | Ejecutar DAST baseline y corregir Critical/High                               | R09-T001 | DAST report            |
| R09-T003 | E21  | Completar session hardening, CSRF donde aplique y rate limits                 | R09-T001 | Security regression    |
| R09-T004 | E22  | Ejecutar full PostgreSQL migration matrix                                     | V0.8     | Migration evidence     |
| R09-T005 | E22  | Ejecutar full IndexedDB migration matrix                                      | V0.8     | Migration evidence     |
| R09-T006 | E22  | Ejecutar extended chaos sync y fuzzing                                        | V0.8     | Chaos evidence         |
| R09-T007 | E22  | Validar Android storage eviction/recovery                                     | R09-T006 | Device evidence        |
| R09-T008 | E08  | Validar blob upload offline/online, retry y orphan cleanup                    | V0.8     | Blob chaos tests       |
| R09-T009 | E23  | Cerrar Debian 13 + Docker Compose production profile                          | V0.8     | Fresh host install     |
| R09-T010 | E23  | Implementar Caddy Cloud TLS profile                                           | R09-T009 | TLS verification       |
| R09-T011 | E23  | Implementar LAN TLS onboarding con internal CA y documented trust flow        | R09-T009 | LAN hardware pass      |
| R09-T012 | E23  | Completar ocwpctl backup/verify/restore/upgrade/diagnostics                   | R09-T009 | CLI E2E                |
| R09-T013 | E23  | Implementar restic encrypted backup profile                                   | R09-T012 | Restore drill          |
| R09-T014 | E23  | Implementar pgBackRest + WAL/PITR profile para managed reliability            | R09-T012 | PITR drill             |
| R09-T015 | E22  | Ejecutar full restore drill en entorno limpio                                 | R09-T013 | GATE restore           |
| R09-T016 | E22  | Ejecutar load, stress y endurance suites                                      | V0.8     | Performance report     |
| R09-T017 | E22  | Cerrar performance budgets web/API/storage                                    | R09-T016 | Budgets green          |
| R09-T018 | E20  | Ejecutar manual WCAG 2.2 AA pass Tier 1                                       | V0.8     | Accessibility report   |
| R09-T019 | E20  | Ejecutar Tier 1 Windows + Android hardware matrix                             | R09-T018 | Device matrix          |
| R09-T020 | E16  | Completar plugin SDK v1 y compatibility test kit                              | V0.8     | Plugin contract suite  |
| R09-T021 | E16  | Crear registry Git-backed skeleton y manifest validator                       | R09-T020 | Registry CI            |
| R09-T022 | E17  | Completar white label BrandProfile para app, portal, print y emails           | V0.8     | White label regression |
| R09-T023 | E18  | Implementar analytics básicos privacy-respecting                              | V0.8     | Metric correctness     |
| R09-T024 | E20  | Completar i18n es-MX/en baseline y locale/currency/timezone abstraction       | V0.8     | Locale E2E             |
| R09-T025 | E21  | Generar SBOM, checksums y provenance de release artifacts                     | V0.8     | Supply chain gates     |
| R09-T026 | E08  | Validar S3-compatible blob adapter                                            | V0.8     | Adapter tests          |
| R09-T027 | E23  | Crear runbooks incident, disk pressure, provider outage, DB recovery y TLS    | R09-T012 | Runbook rehearsal      |
| R09-T028 | E25  | Crear demo offline reproducible con demo-workshop                             | V0.8     | Commercial demo pass   |
| R09-T029 | E25  | Crear templates discovery, proposal, SOW, UAT, handover y exit plan           | V0.8     | Commercial gates       |
| R09-T030 | E26  | Completar governance files, CODEOWNERS, two-person release y source link AGPL | V0.8     | Governance gates       |

### V1.0 · Production Release

| ID       | Epic | Tarea                                                                          | Depends  | Evidence mínima          |
| -------- | ---- | ------------------------------------------------------------------------------ | -------- | ------------------------ |
| R10-T001 | E26  | Congelar release candidate y generar manifest de commit/dependencies/artifacts | V0.9     | RC manifest              |
| R10-T002 | E22  | Ejecutar superset PR + nightly + RC pipeline                                   | R10-T001 | CI evidence              |
| R10-T003 | E22  | Verificar cero C0 y cero C1 sin excepción formal                               | R10-T002 | Defect review            |
| R10-T004 | E22  | Ejecutar golden journey completo online y offline                              | R10-T002 | GATE-V1-003              |
| R10-T005 | E22  | Ejecutar multi-device convergence suite completa                               | R10-T002 | GATE-V1-004              |
| R10-T006 | E22  | Ejecutar migrations PostgreSQL e IndexedDB desde releases soportadas           | R10-T002 | GATE-V1-005/006          |
| R10-T007 | E23  | Ejecutar restore drill y rollback/recovery playbook                            | R10-T002 | GATE-V1-007/020          |
| R10-T008 | E11  | Ejecutar payment idempotency/reconciliation qualification                      | R10-T002 | GATE-V1-009              |
| R10-T009 | E09  | Ejecutar inventory ledger invariant qualification                              | R10-T002 | GATE-V1-008              |
| R10-T010 | E21  | Ejecutar authz negative suite, DAST y security qualification                   | R10-T002 | GATE-V1-010/011          |
| R10-T011 | E20  | Completar manual accessibility qualification WCAG 2.2 AA                       | R10-T002 | GATE-V1-012              |
| R10-T012 | E22  | Completar Tier 1 browser/device qualification                                  | R10-T002 | GATE-V1-013              |
| R10-T013 | E22  | Confirmar performance budgets sin regresión crítica                            | R10-T002 | GATE-V1-014              |
| R10-T014 | E16  | Ejecutar plugin SDK compatibility qualification                                | R10-T002 | GATE-V1-015              |
| R10-T015 | E26  | Verificar AGPL, SPDX, REUSE, DCO, source link, SBOM y provenance               | R10-T002 | GATE-V1-016/017          |
| R10-T016 | E23  | Rehearsal de upgrade desde release soportada                                   | R10-T002 | GATE-V1-018              |
| R10-T017 | E26  | Validar release notes, breaking changes y deprecations                         | R10-T002 | GATE-V1-019              |
| R10-T018 | E23  | Verificar OPS gates aplicables y soporte operable                              | R10-T002 | OPS gate evidence        |
| R10-T019 | E26  | Verificar GOV gates y autoridad two-person release                             | R10-T002 | Governance gate evidence |
| R10-T020 | E25  | Verificar COM gates, demo, templates, pricing y handover                       | R10-T002 | Commercial gate evidence |
| R10-T021 | E25  | Ejecutar piloto controlado en al menos un taller early adopter                 | R10-T020 | Pilot acceptance         |
| R10-T022 | E26  | Resolver defectos de piloto y repetir gates afectados                          | R10-T021 | Regression evidence      |
| R10-T023 | E26  | Tag v1.0.0, firmar provenance y publicar artefactos reproducibles              | R10-T022 | Release artifacts        |
| R10-T024 | E26  | Publicar documentación V1, upgrade guide, security notice y support matrix     | R10-T023 | Docs validation          |
| R10-T025 | E26  | Abrir Continuous Improvement Track V1.x con backlog basado en evidencia        | R10-T024 | Post release state       |

## 60. Task Splitting Rule

Una task del backlog se divide si:

- produce un diff excesivamente amplio
- requiere más de una migration independiente
- mezcla más de un bounded context sin necesidad
- no puede revisarse con una evidencia clara
- contiene varias decisiones Class B no relacionadas

Subtasks conservan el ID padre mediante sufijo, por ejemplo `R03-T004A`, `R03-T004B`.

## 61. Task Reordering Rule

Puede reordenarse trabajo dentro de una release cuando:

1. dependencias permanecen válidas
2. reduce riesgo temprano
3. no rompe el journey de checkpoint
4. se actualiza execution-state
5. no adelanta speculative work de otra release

## 62. Parallel Work Rule

Paralelizar sólo cuando los workstreams son independientes. Evitar paralelizar:

- migrations sobre mismas tablas
- schema OpenAPI compartido en áreas solapadas
- sync protocol core
- foundational design tokens
- release scripts

Sí puede paralelizarse, por ejemplo, documentación comercial y un adapter aislado si no comparten contrato mutable.

## 63. Generated Code Policy

Código generado desde OpenAPI:

- se genera determinísticamente
- no se edita manualmente
- drift inesperado bloquea CI
- el source contract vive en backend
- cambios breaking requieren versionado y notas

## 64. Dependency Policy

Una dependencia runtime nueva MUST justificar:

- problema que resuelve
- mantenimiento activo
- licencia compatible
- footprint
- seguridad
- alternativa estándar
- offline impact

Dependencias críticas se fijan mediante lockfiles y Renovate propone actualizaciones vía PR.

## 65. Deprecation Policy

Toda deprecación pública debe declarar:

- versión de introducción de deprecation
- replacement
- migration path
- última versión soportada
- breaking release objetivo

Offline clients obligan a ventanas de compatibilidad razonables.

## 66. Data Portability Gate

Antes de V1 debe existir una ruta documentada para exportar datos operativos relevantes en formato utilizable. No se utiliza formato deliberadamente opaco para retener clientes.

## 67. Backup and Restore Gate

El agente no puede declarar "backup implementado" por existir un comando que crea archivos. Debe existir un restore drill en un entorno limpio que arranque la aplicación y compruebe invariantes.

## 68. LAN Resilience Gate

La topología LAN se considera soportada sólo si:

- DNS/onboarding está documentado
- secure context/TLS funciona en Tier 1
- la operación interna continúa sin ISP
- recovery de servidor está documentado
- tablets pueden reconectar sin corrupción

## 69. Hardware Gate

Capacidades como cámara, QR, impresora, scanner o Tauri requieren evidence en hardware real antes de prometer soporte productivo.

## 70. Commercial Supportability Gate

Una función no se vende como estándar si carece de:

- owner
- docs
- tests
- upgrade path
- observability
- recovery story

## 71. Pilot Strategy

Antes de V1 estable se recomienda validar progresivamente con:

1. microtaller
2. taller con inventario
3. tienda + taller

V1.0 puede publicarse tras un piloto controlado suficiente para los journeys declarados. El aprendizaje de pilotos se convierte en issues/RFCs, no en hotfixes privados irrepetibles.

## 72. Continuous Improvement Track

Después de V1:

```text
Observe
→ Measure
→ Feedback
→ Issue / RFC
→ Prioritize
→ Implement
→ Verify
→ Release
→ Observe
```

V1.x prioriza compatibilidad y mejoras incrementales. V2 incorpora módulos avanzados de business operations, rental, fleet, ecommerce, analytics y sustainability. V3+ puede incorporar AI local, Computer Vision e IoT bajo módulos opcionales.

## 73. Post-V1 Module Admission

Una capability nueva entra preferentemente como módulo/plugin. Sólo se convierte en Core Candidate si es:

- ampliamente universal
- estable
- fundamental para integridad del sistema
- difícil de implementar correctamente fuera del Core

Popularidad no basta para entrar al Core.

## 74. Agent Output Contract

Durante implementación, cada ciclo debe producir una actualización concisa con:

- task actual
- hallazgo relevante
- decisión técnica material
- checks ejecutados
- resultado
- siguiente task o blocker

No se reporta "hecho" antes de verificar.

## 75. Session Handoff Contract

Antes de terminar una sesión:

1. actualizar execution-state
2. registrar tests verdes/rojos
3. registrar blockers
4. registrar ADRs pendientes
5. dejar Git diff comprensible
6. documentar siguiente acción concreta

Esto permite que otro agente continúe sin reconstruir la intención desde cero.

## 76. Master Prompt Location

El prompt operativo directo se conserva en:

`docs/10-spec-development/agent-master-loop-v0.1.md`

Debe poder copiarse a un agente de código o adaptarse a `AGENTS.md` sin perder las restricciones normativas.

## 77. Expected Repository Documentation after Bootstrap

```text
docs/
├── 00-foundation/
├── 01-functional-requirements/
├── 02-technical-architecture/
├── 03-security-privacy/
├── 04-ux-design/
├── 05-engineering/
├── 06-quality/
├── 07-operations/
├── 08-open-source/
├── 09-commercial/
└── 10-spec-development/
    ├── master-spec-v0.1.md
    ├── agent-master-loop-v0.1.md
    ├── execution-state.yaml
    ├── traceability.csv
    ├── release-checkpoints.md
    └── evidence/
```

## 78. Bootstrapping the Implementation

El primer ciclo de desarrollo debe ejecutar exactamente esta secuencia macro:

```text
R01-T001 Repository root
→ R01-T002 AGPL
→ R01-T003 governance baseline
→ R01-T005 pnpm
→ R01-T006 uv
→ R01-T007 CI
→ backend/frontend skeletons
→ PostgreSQL + Dexie
→ sync protocol skeleton
→ Identity/RBAC
→ Customer vertical slice
→ offline + two-device proof
```

No iniciar Workshop Core completo antes de demostrar que el vertical slice Customer atraviesa persistencia local, servidor, API y sincronización correctamente.

## 79. First Vertical Slice Acceptance

El primer slice se considera válido cuando:

1. se crea Customer online
2. se crea Customer offline
3. cerrar y reabrir PWA conserva operación pendiente
4. reconectar sincroniza una sola vez
5. segundo dispositivo recibe el cambio
6. duplicar request no duplica Customer
7. permiso faltante produce deny
8. OpenAPI y TypeScript client coinciden
9. logs no exponen datos innecesarios
10. test E2E produce evidence

## 80. Architecture Fitness Functions

CI debe evolucionar hacia checks que impidan:

- imports indebidos entre bounded contexts
- ORM leakage al dominio
- llamadas directas de UI a fetch fuera del API client definido
- edición manual de generated client
- uso de `latest` en artefactos de producción
- plugin sin manifest/capabilities
- secrets committed
- tabla de ledger con delete ordinario
- migration no versionada
- missing SPDX donde aplique

## 81. Quality Metrics

Métricas útiles:

- escaped defects por severidad
- flaky test rate
- migration success rate
- restore drill success rate
- sync conflict rate en suite
- performance regression count
- a11y critical defects
- mean time to repair CI
- release rollback rate

No usar número total de tests o cobertura global como KPI único.

## 82. Definition of Done de Fase 10

La Fase 10 se considera completa cuando existen:

- Source of Truth Index
- precedence rules
- immutable constraints
- decision authority model
- epic catalog
- dependency graph
- release train
- executable backlog V0.1 → V1.0
- Work Item schema
- execution-state contract
- Definition of Ready/Done
- verification loop
- ADR/RFC workflow
- stop/recovery conditions
- unified gates
- master agent prompt

## 83. Handoff a implementación

A partir de este punto, la siguiente actividad ya no es otra fase de planeación horizontal. Es **bootstrap del repositorio e implementación de V0.1**.

La planeación futura debe ocurrir verticalmente dentro del release activo mediante tasks, ADRs y RFCs, conservando el Continuous Improvement Track para capacidades posteriores.
