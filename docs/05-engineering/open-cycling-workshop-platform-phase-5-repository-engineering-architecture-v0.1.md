# Fase 5 · Repository & Engineering Architecture v0.1

**Open Cycling Workshop Platform**  
Baseline: Foundation v0.2 · Functional Requirements v0.1 · Technical Architecture v0.2 · Security/Privacy v0.1 · UX/UI v0.1  
License baseline: `AGPL-3.0-only`

> Este documento convierte las decisiones de producto, arquitectura, seguridad y UX en una estructura de ingeniería directamente implementable. Las decisiones técnicas se cierran autónomamente cuando existe evidencia suficiente. Los ADR continúan siendo el mecanismo de trazabilidad y revisión.

## 1. Objetivo de la fase

La Fase 5 define cómo debe organizarse, desarrollarse, probarse, versionarse y mantenerse el código fuente para que el proyecto pueda crecer durante años sin degradar sus límites de dominio, su capacidad offline ni su accesibilidad para contribuidores externos.

Los objetivos concretos son:

1. Definir un monorepo coherente para TypeScript, Python, documentación y extensiones.
2. Convertir los bounded contexts conceptuales en límites físicos verificables.
3. Establecer una fuente única para contratos API y evitar duplicación manual entre backend y frontend.
4. Definir convenciones de desarrollo, revisión, testing, migraciones y releases.
5. Mantener el Core pequeño, modular y compatible con el modelo de plugins.
6. Hacer que una instalación de desarrollo nueva pueda arrancar de manera reproducible.
7. Integrar seguridad, calidad, accesibilidad y cumplimiento AGPL como gates de ingeniería.
8. Preparar el repositorio para contribuciones comunitarias y para implementadores comerciales independientes.

## 2. Decisiones de ingeniería cerradas

| ID          | Decisión                                                      | Estado   | Motivo principal                                                    |
| ----------- | ------------------------------------------------------------- | -------- | ------------------------------------------------------------------- |
| ENG-ADR-001 | Monorepo único                                                | Accepted | Cambios de contrato, frontend, backend y docs permanecen atómicos   |
| ENG-ADR-002 | `pnpm` para workspace TypeScript                              | Accepted | Workspaces maduros, almacenamiento eficiente, lockfile reproducible |
| ENG-ADR-003 | `uv` para Python                                              | Accepted | Resolución, lock y entornos rápidos y reproducibles                 |
| ENG-ADR-004 | Python Core como un paquete modular con múltiples entrypoints | Accepted | Evita duplicación entre API, worker y CLI                           |
| ENG-ADR-005 | Backend organizado por bounded context y capas internas       | Accepted | Protege dominio y reduce acoplamiento accidental                    |
| ENG-ADR-006 | Frontend organizado por módulos de negocio                    | Accepted | Refleja el dominio y escala mejor que carpetas globales por tipo    |
| ENG-ADR-007 | OpenAPI generado por FastAPI como contrato HTTP canónico      | Accepted | Evita esquemas TypeScript escritos manualmente                      |
| ENG-ADR-008 | Cliente TypeScript generado desde OpenAPI                     | Accepted | Detecta drift en CI y simplifica consumo seguro                     |
| ENG-ADR-009 | REST + JSON como API principal                                | Accepted | Simplicidad operativa, offline sync y tooling excelente             |
| ENG-ADR-010 | GitHub Actions como CI de referencia                          | Accepted | Ecosistema open source y checks de PR ampliamente accesibles        |
| ENG-ADR-011 | Trunk-based development con ramas cortas                      | Accepted | Reduce divergence y acelera integración                             |
| ENG-ADR-012 | Conventional Commits + DCO                                    | Accepted | Changelog automatizable y contribución sin CLA inicial              |
| ENG-ADR-013 | SemVer                                                        | Accepted | Compatibilidad comprensible para Core, API y plugins                |
| ENG-ADR-014 | `release-please` para automatizar releases                    | Accepted | PR de release auditable y menor automatismo destructivo             |
| ENG-ADR-015 | Ruff + mypy para Python                                       | Accepted | Lint/format rápido más verificación estática explícita              |
| ENG-ADR-016 | ESLint + Prettier + TypeScript strict                         | Accepted | Ecosistema React estable y reglas verificables                      |
| ENG-ADR-017 | Vitest + Testing Library + Playwright                         | Accepted | Cobertura equilibrada de lógica, UI y flujos reales                 |
| ENG-ADR-018 | pytest + Hypothesis                                           | Accepted | Unit/integration + propiedades para ledger y sincronización         |
| ENG-ADR-019 | Alembic forward-first y expand/contract                       | Accepted | Migraciones seguras y compatibles con despliegues graduales         |
| ENG-ADR-020 | Dexie schema migrations versionadas                           | Accepted | Evolución controlada de datos locales offline                       |
| ENG-ADR-021 | REUSE/SPDX para higiene de licencias                          | Accepted | Cumplimiento AGPL y ecosistema de plugins auditable                 |
| ENG-ADR-022 | Renovate para actualización de dependencias                   | Accepted | Cobertura multi-ecosistema y políticas agrupables                   |
| ENG-ADR-023 | CI como autoridad, hooks locales opcionales                   | Accepted | Contribuir no depende de instalar hooks propietarios                |
| ENG-ADR-024 | Docs-as-code Markdown en el mismo monorepo                    | Accepted | Cambios de comportamiento y documentación viajan juntos             |

## 3. Topología del monorepo

El repositorio raíz se denominará provisionalmente `open-cycling-workshop-platform` hasta que se cierre branding público. El nombre del paquete Python y de namespaces técnicos no deberá depender de una marca comercial futura.

```text
open-cycling-workshop-platform/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── CODEOWNERS
│   ├── dependabot.yml                 # sólo si se conserva junto a Renovate para alerts
│   └── workflows/
│       ├── ci.yml
│       ├── e2e.yml
│       ├── security.yml
│       ├── release.yml
│       ├── docs.yml
│       └── nightly.yml
│
├── apps/
│   └── web/
│       ├── public/
│       ├── src/
│       ├── tests/
│       ├── vite.config.ts
│       └── package.json
│
├── services/
│   └── platform/
│       ├── src/cycling_workshop/
│       ├── tests/
│       ├── migrations/
│       ├── pyproject.toml
│       └── README.md
│
├── packages/
│   ├── ui/
│   ├── api-client/
│   ├── plugin-sdk/
│   ├── plugin-manifest/
│   ├── branding/
│   ├── eslint-config/
│   ├── tsconfig/
│   └── test-utils/
│
├── plugins/
│   ├── official/
│   │   ├── email-smtp/
│   │   ├── whatsapp-business/
│   │   └── filesystem-backup/
│   └── examples/
│       ├── hello-world/
│       └── inventory-listener/
│
├── docs/
│   ├── 00-foundation/
│   ├── 01-functional-requirements/
│   ├── 02-technical-architecture/
│   ├── 03-security-privacy/
│   ├── 04-ux-design/
│   ├── 05-engineering/
│   ├── 06-quality/
│   ├── 07-operations/
│   ├── 08-open-source/
│   ├── 09-commercial/
│   ├── 10-spec-development/
│   └── adr/
│
├── infra/
│   ├── compose/
│   ├── docker/
│   ├── dev/
│   └── examples/
│
├── scripts/
│   ├── bootstrap/
│   ├── ci/
│   ├── contracts/
│   ├── database/
│   └── release/
│
├── fixtures/
│   ├── minimal/
│   ├── demo-workshop/
│   └── load/
│
├── .editorconfig
├── .gitattributes
├── .gitignore
├── .python-version
├── .nvmrc                         # o archivo equivalente de runtime fijado
├── pnpm-workspace.yaml
├── package.json
├── pnpm-lock.yaml
├── pyproject.toml                 # configuración Python de workspace/tooling raíz
├── uv.lock
├── renovate.json
├── LICENSE
├── LICENSES/
├── REUSE.toml
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── GOVERNANCE.md
├── ARCHITECTURE.md
├── CHANGELOG.md
└── README.md
```

### Regla de ubicación

Una pieza de código vive en el nivel más específico que pueda poseerla correctamente:

- Si sólo pertenece a `workshop`, vive dentro de `workshop`.
- Si la comparten dos módulos frontend pero no es pública, vive en `apps/web/src/shared`.
- Si es una primitive visual reutilizable y sin conocimiento de negocio, vive en `packages/ui`.
- Si es un contrato público para autores de plugins, vive en `packages/plugin-sdk`.
- Si sólo existe para facilitar tests, vive en `test-utils` o junto al módulo probado.
- `shared`, `common` y `utils` nunca son destinos por defecto.

## 4. Workspace y toolchain raíz

### 4.1 JavaScript y TypeScript

El workspace TypeScript utiliza `pnpm`. La versión exacta se fija mediante `packageManager` en `package.json` y se actualiza mediante PR controlado. No se permite depender de una versión global indeterminada.

El root `package.json` contiene únicamente scripts orquestadores, tooling compartido y dependencias realmente globales. Las aplicaciones y paquetes declaran sus propias dependencias.

Scripts mínimos:

```json
{
  "scripts": {
    "dev": "...",
    "build": "...",
    "lint": "...",
    "format:check": "...",
    "typecheck": "...",
    "test": "...",
    "test:e2e": "...",
    "contracts:check": "..."
  }
}
```

### 4.2 Python

Python utiliza `uv` con lockfile versionado. El runtime de producción se fija a una versión soportada y probada. El baseline de compatibilidad permanece en Python 3.13 o superior, con CI sobre la versión de producción y la siguiente versión estable soportada cuando el ecosistema sea compatible.

No se permite `pip install` manual como procedimiento oficial de desarrollo. Los comandos documentados deben ser reproducibles mediante `uv sync` y `uv run`.

### 4.3 Orquestación transversal

Los comandos de CI y documentación deberán tener equivalentes ejecutables localmente. La fuente de verdad de cada operación será un script versionado o comando del package manager, nunca YAML de CI con lógica exclusiva.

Ejemplo conceptual:

```text
CI step
  → scripts/ci/check-contracts.sh
  → mismo script ejecutable localmente
```

Los scripts críticos deben ofrecer alternativas compatibles con Windows cuando sean parte del flujo de contribución ordinario. Para tareas internas del servidor Linux se permite shell POSIX.

## 5. Arquitectura física del backend

El backend será un **modular monolith** dentro de un único paquete Python. FastAPI, worker y CLI son entrypoints distintos sobre el mismo conjunto de módulos de dominio.

```text
services/platform/src/cycling_workshop/
├── api/
│   ├── app.py
│   ├── dependencies.py
│   ├── middleware/
│   ├── errors.py
│   └── routers.py
│
├── bootstrap/
│   ├── container.py
│   ├── settings.py
│   └── lifecycle.py
│
├── contexts/
│   ├── identity/
│   ├── customers/
│   ├── bicycles/
│   ├── workshop/
│   ├── inventory/
│   ├── purchasing/
│   ├── sales/
│   ├── payments/
│   ├── communications/
│   ├── knowledge/
│   ├── automation/
│   ├── analytics/
│   └── administration/
│
├── integrations/
│   ├── blobs/
│   ├── messaging/
│   ├── payments/
│   └── plugins/
│
├── platform/
│   ├── db/
│   ├── events/
│   ├── jobs/
│   ├── observability/
│   ├── security/
│   └── sync/
│
├── shared_kernel/
│   ├── ids.py
│   ├── money.py
│   ├── time.py
│   └── errors.py
│
├── worker.py
└── cli.py
```

### 5.1 Estructura interna de cada bounded context

```text
contexts/workshop/
├── domain/
│   ├── entities.py
│   ├── value_objects.py
│   ├── events.py
│   ├── policies.py
│   └── errors.py
│
├── application/
│   ├── commands/
│   ├── queries/
│   ├── services/
│   ├── dto.py
│   └── ports.py
│
├── infrastructure/
│   ├── repositories.py
│   ├── models.py
│   └── adapters.py
│
├── api/
│   ├── schemas.py
│   ├── routes.py
│   └── dependencies.py
│
└── tests/
    ├── unit/
    ├── integration/
    └── contract/
```

### 5.2 Regla de dependencias

```text
api/interface
      ↓
application
      ↓
domain

infrastructure → implements application/domain ports
```

El dominio no importa FastAPI, SQLAlchemy, Pydantic Settings, servicios cloud ni otros adapters.

La infraestructura puede depender de application/domain para implementar ports, pero application no conoce una implementación concreta.

### 5.3 Dependencias entre contextos

Queda prohibido que un repositorio de un bounded context consulte directamente tablas privadas de otro contexto para ejecutar reglas de negocio.

Integración permitida:

1. Application service explícito.
2. Read model público documentado.
3. Domain/Integration event.
4. Public port definido por el contexto propietario.

Ejemplo incorrecto:

```python
# inventory leyendo directamente tabla interna de workshop
select(ServiceOrderTable.parts)
```

Ejemplo correcto:

```text
workshop.parts_committed
→ InventoryApplication.consume_parts(...)
```

## 6. Shared Kernel mínimo

`shared_kernel` sólo contendrá conceptos verdaderamente universales y estables.

Permitidos inicialmente:

- UUIDv7/identificadores.
- Dinero y moneda.
- Clock abstractions.
- Error base de dominio.
- Tipos de tenant/location cuando sean inevitables.

No permitido:

- Customer.
- Bicycle.
- Product.
- Repository genérico omnipotente.
- Base service.
- Helpers de negocio ambiguos.

Cada nueva adición al Shared Kernel requiere ADR o justificación explícita en PR.

## 7. Arquitectura física del frontend

`apps/web` se organiza por módulos de negocio y shell de aplicación, no por una carpeta global gigantesca de `components`, `hooks` y `services`.

```text
apps/web/src/
├── app/
│   ├── router/
│   ├── providers/
│   ├── shell/
│   ├── permissions/
│   └── bootstrap/
│
├── modules/
│   ├── customers/
│   ├── bicycles/
│   ├── workshop/
│   ├── inventory/
│   ├── purchasing/
│   ├── sales/
│   ├── communications/
│   ├── knowledge/
│   ├── automation/
│   ├── analytics/
│   └── administration/
│
├── offline/
│   ├── db/
│   ├── repositories/
│   ├── mutation-queue/
│   ├── sync/
│   └── diagnostics/
│
├── shared/
│   ├── components/
│   ├── hooks/
│   ├── lib/
│   ├── formatting/
│   └── accessibility/
│
├── generated/
│   └── api/
│
├── styles/
├── i18n/
└── main.tsx
```

### 7.1 Estructura de módulo frontend

```text
modules/workshop/
├── api/
├── model/
├── routes/
├── ui/
├── offline/
├── permissions/
└── tests/
```

La carpeta `ui` del módulo puede usar primitives de `packages/ui`, pero `packages/ui` nunca puede importar entidades o permisos de Workshop.

### 7.2 Estado de datos

Reglas:

- **Dexie/IndexedDB** conserva el estado local durable.
- **TanStack Query** coordina consultas remotas, revalidación y estados request/response cuando corresponda.
- Estado efímero de UI permanece en React local/context donde sea suficiente.
- No se introduce un store global generalista hasta que exista un caso que React + Query + Dexie no resuelvan limpiamente.
- El estado crítico de negocio no vive exclusivamente en memoria de React.

### 7.3 Formularios

React Hook Form se utiliza para formularios operativos complejos. Zod se utiliza para validación cliente y composición de schemas UX cuando sea útil, pero el servidor continúa siendo la autoridad final.

Los errores del servidor se mapean a campos o mensajes de formulario sin perder detalle técnico en diagnostics.

## 8. UI package y Design System

`packages/ui` implementa los tokens y componentes definidos en Fase 4.

```text
packages/ui/
├── src/
│   ├── primitives/
│   ├── components/
│   ├── patterns/
│   ├── tokens/
│   ├── accessibility/
│   └── index.ts
├── stories/
├── tests/
└── package.json
```

Reglas:

1. Radix Primitives se encapsula detrás de componentes propios.
2. Ningún módulo de negocio importa Radix directamente salvo excepción documentada.
3. Los colores críticos de estado usan tokens semánticos protegidos del white labeling.
4. Todo componente interactivo público tiene keyboard behavior documentado.
5. Componentes nuevos deben incluir estados loading, disabled, error y focus cuando apliquen.
6. Componentes densos deben verificarse en Windows desktop y Android tablet.

## 9. Branding y white labeling

`packages/branding` contiene contratos, resolución de tokens, assets y validaciones de BrandProfile.

```text
packages/branding/
├── schema/
├── defaults/
├── runtime/
├── validators/
└── tests/
```

El branding no modifica lógica de negocio. La configuración de marca se carga como datos y produce CSS variables/tokens, metadatos y assets.

No se permite mantener forks por cliente para cambiar logos, colores, tipografía, dominio o plantillas de comunicación ordinarias.

## 10. Contratos API y código generado

### 10.1 Fuente canónica

FastAPI/Pydantic genera OpenAPI. El OpenAPI publicado por el backend es la fuente canónica de HTTP.

Pipeline:

```text
Pydantic schemas
→ FastAPI OpenAPI
→ normalized openapi.json
→ TypeScript types/client
→ apps/web + plugin-sdk consumers
```

### 10.2 Cliente TypeScript

`packages/api-client` contiene únicamente código generado más una pequeña capa manual estable de transporte.

La generación debe ser determinista. CI ejecuta:

```text
contracts:generate
→ git diff --exit-code
```

Si el backend cambia un contrato sin regenerar el cliente, el PR falla.

### 10.3 Política de código generado

- Archivos generados llevan cabecera `DO NOT EDIT`.
- No se corrigen manualmente.
- La versión del generador se fija.
- Cambios inesperados se revisan igual que cualquier diff.
- La capa de dominio frontend nunca depende de detalles internos del generador.

## 11. Contratos de eventos

Los eventos públicos usan un envelope versionado independiente del transporte.

```json
{
  "event_id": "uuidv7",
  "event_type": "workshop.service_order.ready.v1",
  "occurred_at": "...",
  "tenant_id": "...",
  "location_id": "...",
  "aggregate_id": "...",
  "schema_version": 1,
  "data": {}
}
```

Reglas:

- El nombre del evento incluye versión mayor del schema.
- Un consumidor debe ignorar campos desconocidos.
- Un cambio incompatible crea `v2`.
- Eventos ya publicados no se reescriben retroactivamente.
- Integration Events no exponen accidentalmente estructuras internas completas de entidades.

## 12. Arquitectura de sincronización en el repositorio

La implementación del Sync Engine se divide explícitamente entre cliente y servidor.

### Cliente

```text
apps/web/src/offline/
├── db/
├── mutation-queue/
├── projections/
├── sync/
│   ├── push.ts
│   ├── pull.ts
│   ├── merge.ts
│   ├── cursor.ts
│   └── coordinator.ts
└── diagnostics/
```

### Servidor

```text
services/platform/src/cycling_workshop/platform/sync/
├── mutations.py
├── idempotency.py
├── feed.py
├── cursors.py
├── conflicts.py
└── tombstones.py
```

El algoritmo no se mezcla con UI ni con repositorios SQL concretos. Las políticas de merge por dominio se registran a través de interfaces explícitas.

### Invariantes obligatorias

1. Una mutation confirmada no se ejecuta dos veces.
2. Un cursor sólo avanza después de aplicar durablemente todos los cambios previos.
3. Un conflicto no destruye silenciosamente una versión local.
4. Pagos, autorizaciones e inventario preservan trazabilidad append-only/compensatoria.
5. Un error permanente queda visible y exportable para diagnóstico.

## 13. Persistencia y SQLAlchemy

### 13.1 Modelos ORM

Cada bounded context posee sus modelos SQLAlchemy. No existe un único archivo `models.py` global.

Las tablas se prefijan o agrupan de manera consistente para hacer visible su ownership. En instalaciones que utilicen schemas PostgreSQL, la separación lógica no debe impedir migraciones simples.

### 13.2 Repositories

Los repositories implementan ports definidos en application/domain. No exponen `Session` a capas superiores.

Los queries analíticos o de lectura pueden usar read models específicos en lugar de forzar aggregates a resolver reporting.

### 13.3 Transacciones

La unidad de trabajo se alinea con un caso de uso. Domain mutations, ledger entries y outbox event correspondiente deben persistir en la misma transacción cuando formen una unidad atómica.

## 14. Migraciones de servidor

Alembic es la herramienta canónica.

Política:

1. Migraciones son forward-first.
2. Cada migración tiene `upgrade` determinista.
3. Destructive changes siguen patrón expand/contract.
4. Renames complejos se dividen en etapas compatibles.
5. Migrations se prueban desde el último release soportado.
6. CI crea una base vacía desde cero y también ejecuta upgrade desde fixture de release previo.
7. Data migrations grandes se ejecutan mediante jobs controlados cuando excedan presupuestos de lock/tiempo.
8. Un release no se publica si rollback operativo o restore strategy no está documentado para cambios irreversibles.

## 15. Migraciones IndexedDB

Dexie utiliza versiones explícitas de schema.

Cada cambio local debe definir:

- Schema anterior.
- Schema nuevo.
- Transformación de datos si aplica.
- Estrategia ante interrupción.
- Prueba con datos representativos.
- Compatibilidad con service worker/app bundle durante actualización.

La migración no debe requerir conectividad. La aplicación debe impedir operar sobre un schema parcialmente actualizado.

## 16. Background jobs

Worker comparte el paquete Python del Core y ejecuta jobs durables almacenados inicialmente en PostgreSQL.

```text
api transaction
→ jobs table/outbox
→ worker claim with SKIP LOCKED
→ execute
→ success / retry / dead-letter state
```

Cada job define:

- `job_type` versionado.
- Payload mínimo.
- Idempotency key cuando tenga side effects externos.
- Retry policy.
- Timeout.
- Dead-letter handling.
- Observability metadata.

No se permite llamar proveedores externos de forma no idempotente dentro de una transacción HTTP larga.

## 17. Blob storage

El dominio usa ports de blobs. Implementaciones iniciales:

1. Filesystem local.
2. S3-compatible.
3. MinIO para desarrollo/integración.

Metadata de negocio vive en PostgreSQL/IndexedDB. Los blobs no se guardan como columnas gigantes salvo un caso excepcional documentado.

Uploads usan checksum, content type validado, tamaño máximo y nombres internos no derivados del filename del usuario.

## 18. Plugin SDK

El SDK se divide en contratos públicos, manifest y ejemplos.

```text
packages/plugin-sdk/
├── src/
│   ├── events/
│   ├── capabilities/
│   ├── ui-slots/
│   ├── api/
│   └── compatibility/
└── tests/
```

### 18.1 Tipos de extensión

**Official in-process extension**  
Código revisado y distribuido junto al proyecto o explícitamente confiado por el administrador.

**External connector**  
Proceso o servicio separado que consume eventos/API con credenciales y capabilities limitadas.

El proyecto no promete ejecutar plugins comunitarios no confiables dentro del proceso principal.

### 18.2 Manifest

```yaml
id: org.example.inventory-listener
name: Inventory Listener
version: 1.0.0
platform: '>=1.0 <2.0'
license: AGPL-3.0-only
capabilities:
  - inventory.read
subscriptions:
  - inventory.stock_changed.v1
ui_slots: []
```

Un plugin falla instalación si:

- su platform range no es compatible,
- solicita capabilities inexistentes,
- su manifest es inválido,
- sus migraciones no son aplicables,
- incumple una política de trust configurada.

## 19. Política de plugins y AGPL

El Core y aplicaciones oficiales usan `AGPL-3.0-only`.

El SDK y ejemplos se mantendrán bajo AGPL salvo que un ADR futuro demuestre que una licencia permisiva para una interfaz estrictamente separada mejora de forma material la interoperabilidad sin debilitar la intención copyleft del proyecto.

No se realizará dual licensing propietario del Core como mecanismo predeterminado.

Implementadores pueden cobrar libremente instalación, personalización, hosting, soporte, capacitación, integración y desarrollo compatible con la licencia.

## 20. Configuración

### Backend

Pydantic Settings define settings tipados. Precedencia:

```text
defaults seguros
→ archivo/config de deployment
→ environment variables
→ secret provider/archivo secreto
```

Secrets jamás se incluyen en defaults, imágenes Docker o repositorio.

### Frontend

Variables `VITE_*` se consideran públicas por definición. Ningún secreto se compila dentro del bundle.

Runtime configuration no sensible puede cargarse desde un endpoint/config generado para permitir reutilizar el mismo build en varios entornos.

## 21. Perfiles de entorno

Se normalizan cuatro perfiles:

| Perfil       | Propósito                                             |
| ------------ | ----------------------------------------------------- |
| `dev`        | desarrollo humano con hot reload y servicios locales  |
| `test`       | ejecución determinista y aislada                      |
| `demo`       | dataset seguro para demos, screenshots y capacitación |
| `production` | defaults endurecidos y servicios persistentes         |

No debe existir lógica de negocio que cambie silenciosamente por entorno. Las diferencias son de infraestructura, debugging y configuración explícita.

## 22. Desarrollo local

El onboarding objetivo será:

```text
git clone
→ bootstrap dependencies
→ start infrastructure
→ migrate + seed
→ start API/worker/web
```

El repositorio incluirá un comando único documentado para bootstrap y otro para `dev`.

Servicios de desarrollo recomendados:

- PostgreSQL.
- MinIO.
- Mailpit o equivalente SMTP local.
- API.
- Worker.
- Web PWA.

WhatsApp, pagos reales y proveedores externos no forman parte del happy path local. Se usan fakes/adapters de sandbox.

## 23. Fixtures, factories y seeds

Se separan tres conceptos:

**Factories:** crean objetos válidos para tests.  
**Fixtures:** datasets versionados para escenarios reproducibles.  
**Seeds:** inicialización opcional de instalaciones dev/demo.

Perfiles oficiales:

### `minimal`

- 1 organización.
- 1 location.
- 1 admin.
- Config mínima.

### `demo-workshop`

- clientes ficticios,
- bicicletas diversas,
- órdenes en distintos estados,
- inventario,
- ventas,
- mensajes simulados,
- datos suficientes para demos y screenshots.

### `load`

- 100k+ movimientos de inventario,
- miles de órdenes,
- múltiples dispositivos simulados,
- blobs representativos,
- escenarios de sync conflict.

Todos los datos demo son sintéticos. Nunca se distribuyen dumps de clientes reales.

## 24. Estándares Python

### 24.1 Typing

- Type hints obligatorios en API pública y application/domain.
- `mypy` con configuración estricta incremental.
- `Any` explícito debe estar justificado en integración externa.
- Protocols/ports se prefieren a inheritance innecesaria.

### 24.2 Ruff

Ruff realiza lint y format. Las excepciones se configuran centralmente y no mediante comentarios masivos `noqa` sin razón.

### 24.3 Estilo de dominio

- Entidades y Value Objects expresan invariantes.
- No se aceptan `dict[str, Any]` como sustituto de modelos de dominio estables.
- Exceptions de dominio son específicas.
- Fechas reciben `Clock` inyectable en lógica que deba probarse.
- IDs se generan mediante provider cuando la determinación sea relevante para tests.

### 24.4 Async

Async se usa en boundaries de I/O cuando aporta valor. No se convierte dominio puro en async artificialmente.

## 25. Estándares TypeScript/React

### 25.1 TypeScript

`strict: true` es obligatorio. Se activarán gradualmente flags adicionales que aumenten seguridad, como `noUncheckedIndexedAccess`, cuando la base inicial quede compatible.

No se permite `any` implícito. `unknown` se utiliza en boundaries no confiables y se valida.

### 25.2 React

- Componentes funcionales.
- Hooks sólo para comportamiento React, no como contenedor arbitrario de negocio.
- Fetching y mutations mediante capas definidas.
- Side effects en `useEffect` se mantienen mínimos.
- Estado derivado se calcula en render/selectors en vez de duplicarse.
- Accesibilidad forma parte del API del componente.

### 25.3 Imports

Se definen aliases estables y reglas ESLint para prevenir imports cruzados indebidos entre módulos.

Ejemplo:

```text
modules/inventory → packages/ui          allowed
modules/inventory → modules/workshop    denied by default
```

## 26. Testing pyramid y boundaries

La calidad no se mide sólo por porcentaje de coverage. Se exige cobertura por riesgo.

```text
          E2E critical paths
        Integration / contracts
      Component / application tests
    Domain unit + property-based tests
```

### 26.1 Backend

- `pytest`: unit e integration.
- Hypothesis: property-based tests.
- PostgreSQL real en integration tests relevantes.
- API contract tests contra OpenAPI.
- Migration tests.

Propiedades prioritarias:

- ledger nunca produce cantidades inconsistentes por duplicación de mutation,
- payment mutation idempotente no duplica cobro lógico,
- cursor aplicado dos veces no altera resultado,
- compensating transaction preserva historial,
- state machine rechaza transiciones inválidas.

### 26.2 Frontend

- Vitest para lógica y componentes.
- Testing Library para comportamiento observable.
- axe-core para checks automatizados de accesibilidad.
- Playwright para critical paths y offline scenarios.

### 26.3 Tests de sincronización

Debe existir un harness de dispositivos virtuales:

```text
Device A local DB
Device B local DB
Server
Network controller
Clock/failure injection
```

Escenarios:

- offline → mutations → reconnect,
- push duplicated,
- response lost after server commit,
- concurrent stock movement,
- conflicting customer edit,
- tombstone propagation,
- auth revoked while offline,
- migration + pending queue,
- blob pending upload.

## 27. Contract testing

Los contratos relevantes incluyen:

1. HTTP OpenAPI.
2. Integration Events.
3. Plugin manifest.
4. BrandProfile.
5. Stored sync envelopes.

Cada contrato versionado debe disponer de fixtures válidos e inválidos.

Un cambio incompatible exige versión mayor o estrategia de compatibilidad explícita.

## 28. Test data privacy

Está prohibido copiar datos de producción a tests o fixtures públicos sin proceso formal de anonimización verificable.

Los logs de CI tampoco deben contener tokens, teléfonos reales, emails reales ni contenidos de comunicaciones.

## 29. Quality gates de pull request

Un PR ordinario debe pasar, según áreas afectadas:

```text
format check
lint
static typing
unit tests
component tests
contract drift check
migration check
license/REUSE check
secret scan
security static analysis
build
```

PRs que afecten critical paths añaden:

```text
integration tests
Playwright E2E
a11y checks
offline/sync scenarios
```

El conjunto exacto se puede optimizar por paths, pero ningún check de seguridad crítico se omite por velocidad.

## 30. CI/CD de referencia

### `ci.yml`

- install reproducible,
- generated code check,
- lint,
- typecheck,
- unit/component tests,
- build.

### `e2e.yml`

- PostgreSQL + MinIO + app,
- migrations,
- demo fixtures,
- Playwright desktop/tablet,
- offline scenarios.

### `security.yml`

- secret scanning,
- dependency vulnerability scan,
- CodeQL/SAST,
- container scan,
- SBOM generation,
- REUSE/license validation.

### `nightly.yml`

- extended sync chaos suite,
- load fixtures,
- migration rehearsal,
- accessibility crawl,
- optional browser matrix.

### `release.yml`

- release PR validation,
- tag,
- artifacts,
- container images,
- SBOM,
- checksums,
- changelog,
- provenance/signing cuando la infraestructura lo permita de forma mantenible.

## 31. Seguridad de supply chain

La ingeniería incorpora los controles de Fase 3.

Baseline:

- lockfiles versionados,
- Renovate,
- secret scanning,
- SAST,
- dependency audit,
- image scanning,
- SBOM por release,
- base images fijadas por digest en release pipelines críticos,
- mínimo uso de actions de terceros y referencias fijadas,
- no ejecutar scripts de plugins comunitarios durante CI principal sin aislamiento.

## 32. Gestión de dependencias

Renovate agrupa actualizaciones de bajo riesgo y separa majors.

Política:

- patch/minor compatibles pueden autoabrirse agrupadas,
- majors requieren revisión humana y pruebas completas,
- dependencias de seguridad críticas reciben prioridad,
- una dependencia abandonada con impacto core genera issue de reemplazo,
- el Core evita dependencias para funciones triviales.

No se persigue “cero dependencias”. Se persigue una superficie de dependencia justificable y mantenible.

## 33. Branching y pull requests

Modelo: **trunk-based development**.

- `main` siempre protegida.
- ramas cortas `feat/...`, `fix/...`, `docs/...`, `refactor/...`.
- no `develop` permanente.
- merges mediante PR.
- squash merge como default para cambios ordinarios.
- commits preservados sólo cuando la historia tenga valor técnico específico.

PR debe incluir:

- propósito,
- impacto funcional,
- pruebas realizadas,
- screenshots/video cuando cambia UX,
- migraciones,
- riesgos,
- issue/ADR relacionado,
- `Signed-off-by` conforme DCO.

## 34. Conventional Commits

Formato:

```text
feat(workshop): add quality-control transition
fix(sync): preserve rejected local mutation
refactor(inventory): isolate ledger projection
security(auth): rotate portal token format
docs(adr): accept plugin trust model
```

Scopes preferidos reflejan bounded contexts o infraestructura reconocible.

## 35. Versionado

### Platform

SemVer:

```text
MAJOR.MINOR.PATCH
```

- MAJOR: incompatibilidad pública significativa.
- MINOR: funcionalidad compatible.
- PATCH: bugfix/security compatible.

Antes de `1.0`, breaking changes siguen siendo posibles, pero deben aparecer explícitamente en changelog y migration notes.

### API

HTTP usa path major cuando exista ruptura real:

```text
/api/v1/...
```

Cambios compatibles no generan `/v2`.

### Plugins

Cada plugin tiene SemVer propio y un `platform` compatibility range.

## 36. Release management

`release-please` mantiene un Release PR con:

- versión propuesta,
- changelog,
- packages afectados,
- enlaces a cambios.

Un maintainer revisa y fusiona el Release PR. El merge crea tag y activa pipeline de artifacts.

Security releases pueden usar flujo acelerado sin omitir pruebas obligatorias.

## 37. Changelog

`CHANGELOG.md` documenta cambios relevantes para operadores e implementadores, no cada refactor interno.

Categorías:

- Added.
- Changed.
- Fixed.
- Security.
- Deprecated.
- Removed.
- Migration notes.

## 38. Deprecation policy

Una API pública no se elimina sin:

1. marcar deprecación,
2. documentar alternativa,
3. emitir warning/telemetría local si es apropiado,
4. mantener una ventana de compatibilidad razonable,
5. registrar removal en release notes.

Plugins reciben compatibility checks antes de upgrades de plataforma.

## 39. Logging y observability hooks

Backend emite logs estructurados con:

- timestamp,
- level,
- service/entrypoint,
- request/correlation ID,
- tenant/location cuando sea seguro,
- event/job type,
- error code.

PII y contenido de mensajes no se registran por defecto.

OpenTelemetry será la interfaz de instrumentación preferida para traces/metrics exportables, manteniendo exportación opcional y configurable.

Frontend mantiene un diagnostics buffer local limitado para:

- sync failures,
- schema version,
- app version,
- network state,
- error codes.

El usuario/admin puede exportarlo sin incluir contenido personal salvo consentimiento explícito.

## 40. Error taxonomy

Los errores públicos usan códigos estables, no mensajes como contrato.

Ejemplo:

```json
{
  "code": "WORKSHOP_INVALID_TRANSITION",
  "message": "This service order cannot move to READY from DIAGNOSIS.",
  "details": {},
  "correlation_id": "..."
}
```

Categorías:

- validation,
- authorization,
- domain conflict,
- sync conflict,
- dependency failure,
- temporary infrastructure,
- permanent infrastructure,
- security.

## 41. Feature flags

Feature flags se definen como configuración tipada y auditable.

No se permite utilizar flags eternos sin owner ni fecha de revisión.

Cada flag contiene:

```text
id
owner
purpose
introduced_in
expected_removal
safe_default
```

Flags de permisos no sustituyen RBAC.

## 42. Arquitectura de módulos opcionales

Un módulo oficial adicional debe decidirse como:

1. **Core context**, si es universal y fundamental.
2. **Official plugin**, si es especializado pero mantenido por el proyecto.
3. **Community plugin**, si no requiere mantenimiento oficial.
4. **External integration**, si pertenece claramente a un proveedor/servicio.

La incorporación de Rentals, Fleet, Ecommerce, Fiscal, Sustainability, AI e IoT seguirá esta clasificación antes de añadir código al Core.

## 43. Política para IA futura

Ninguna dependencia de IA entra en el Core base.

Cuando se implemente la Intelligence Layer:

```text
plugin / module
→ AI Provider interface
→ local or remote provider
```

Los tests de dominio no requerirán red ni modelos externos. Las respuestas de modelos siempre atravesarán adapters y políticas de validación.

## 44. Internacionalización del código

- Textos de UI no se hardcodean en componentes reutilizables.
- Moneda y locale usan tipos/contexto explícito.
- Fechas se almacenan normalizadas y se presentan por timezone/locale.
- Reglas fiscales viven en plugins de jurisdicción.
- Tests incluyen al menos un locale distinto al español y formatos con timezone diferente.

## 45. Accesibilidad como ingeniería

La accesibilidad no se delega a una auditoría final.

Gates:

- ESLint/a11y cuando aplique.
- axe en component/E2E.
- keyboard tests para primitives críticas.
- Playwright con viewport tablet.
- contraste verificado para themes oficiales.
- reduced motion.
- focus visible.
- target sizes definidos en Fase 4.

Un componente que sólo funciona con mouse no se considera terminado.

## 46. Performance engineering

Budgets preliminares se convierten en checks progresivos.

Áreas prioritarias:

- bundle inicial,
- tiempo de bootstrap local,
- queries IndexedDB,
- render de tablas,
- sync batches,
- memory en Android tablet,
- tiempos de API P95,
- locks de migración,
- upload de imágenes.

Las optimizaciones complejas sólo se introducen después de profiling reproducible.

## 47. Estructura de documentación técnica

```text
docs/
├── adr/
│   ├── 0001-modular-monolith.md
│   ├── 0002-local-persistence-dexie.md
│   ├── 0003-sync-protocol.md
│   └── ...
│
├── architecture/
├── api/
├── plugins/
├── operations/
├── security/
├── contributing/
└── runbooks/
```

Los ADR son inmutables después de Accepted salvo correcciones editoriales. Una decisión nueva que reemplaza otra crea ADR nuevo con `Supersedes`.

## 48. Template de ADR

```markdown
# ADR-XXXX · Title

Status: Proposed | Accepted | Superseded | Rejected
Date: YYYY-MM-DD
Owners: ...
Supersedes: ...

## Context

## Decision

## Consequences

### Positive

### Negative / tradeoffs

## Alternatives considered

## Verification
```

## 49. Architecture fitness functions

Estas reglas deberán automatizarse progresivamente:

| Fitness function                                  | Verificación                 |
| ------------------------------------------------- | ---------------------------- |
| Domain no importa FastAPI/SQLAlchemy              | import/lint rule             |
| Módulos frontend no cruzan boundaries arbitrarios | ESLint import boundaries     |
| OpenAPI y cliente generado no divergen            | generation diff              |
| Migration chain es aplicable desde release previo | CI database test             |
| IndexedDB schema migra fixture previo             | browser test                 |
| AGPL/REUSE completo                               | `reuse lint`                 |
| Secrets ausentes                                  | secret scan                  |
| Critical UI keyboard accessible                   | Playwright/axe               |
| Sync duplicate mutation es idempotente            | property/integration test    |
| Plugins incompatibles se rechazan                 | manifest compatibility tests |

## 50. Código de ejemplo y snippets en documentación

Todo snippet ejecutable que forme parte de guía oficial debe probarse cuando sea razonable.

Ejemplos largos vivirán como proyectos reales en `plugins/examples` o `examples/`, y la documentación enlazará al código en vez de mantener copias divergentes.

## 51. Política de TODO/FIXME

`TODO` debe incluir issue o contexto suficientemente accionable.

No permitido:

```text
TODO fix later
```

Preferido:

```text
TODO(#431): remove compatibility bridge after v1.4 support window
```

Deuda técnica estructural se registra como issue etiquetado, no queda enterrada indefinidamente en comentarios.

## 52. Security-sensitive code ownership

`CODEOWNERS` exigirá revisión de maintainers designados para:

- auth/session,
- portal capability tokens,
- payments,
- sync conflict/idempotency,
- plugin loader/trust,
- migrations destructivas,
- cryptography,
- CI/release signing,
- permissions/RBAC.

Un autor puede mantener el área, pero los cambios sensibles requieren segunda revisión cuando el proyecto tenga suficientes maintainers.

## 53. AGPL, SPDX y REUSE

Root:

```text
LICENSE
LICENSES/AGPL-3.0-only.txt
REUSE.toml
```

Archivos y packages incluyen metadata SPDX donde corresponda.

Assets, fuentes, iconos y fixtures de terceros deben declarar licencia separada cuando no sean AGPL.

Un PR que agregue un asset sin procedencia/licencia verificable falla revisión.

## 54. Developer Certificate of Origin

Cada commit aportado debe contener:

```text
Signed-off-by: Name <email>
```

El proyecto usa DCO en lugar de CLA inicial. Esto reduce fricción y mantiene trazabilidad de derecho de contribución.

## 55. Issue taxonomy

Labels recomendadas:

```text
area:workshop
area:inventory
area:sync
area:accessibility
area:security
area:plugins
area:docs

type:bug
type:feature
type:refactor
type:security
type:research

good-first-issue
help-wanted
breaking-change
needs-adr
```

Issues de seguridad no se reportan públicamente cuando exista un canal privado definido en `SECURITY.md`.

## 56. Definition of Ready para implementación

Una historia o issue de desarrollo está lista cuando:

1. Tiene objetivo observable.
2. Contexto/bounded context está identificado.
3. Criterios de aceptación son verificables.
4. Permisos y offline behavior están definidos cuando aplican.
5. Impacto de datos/migraciones está identificado.
6. Riesgos de seguridad están identificados cuando corresponda.
7. Diseño o comportamiento UI está definido si afecta interacción.
8. Dependencias externas están disponibles o simulables.

## 57. Definition of Done de código

Un cambio no está Done sólo porque compila.

Debe cumplir según aplique:

- implementación alineada con bounded context,
- tests adecuados al riesgo,
- typecheck/lint limpios,
- migraciones probadas,
- contratos regenerados,
- offline behavior probado,
- accesibilidad verificada,
- documentación actualizada,
- changelog si es user-facing,
- security review si es sensible,
- license provenance si agrega assets/dependencies,
- observability/error codes suficientes,
- no deuda temporal sin issue/owner.

## 58. Definition of Done de la Fase 5

Esta fase se considera cerrada cuando el futuro repositorio pueda implementar:

1. Estructura de monorepo exacta.
2. Workspace pnpm reproducible.
3. Workspace Python uv reproducible.
4. Web app shell compilable.
5. Python package con API, worker y CLI entrypoints.
6. Primer bounded context respetando dependency rules.
7. OpenAPI → TypeScript generation automática.
8. Postgres + MinIO + SMTP dev mediante infraestructura local.
9. Alembic y Dexie migration harness.
10. Unit, integration, E2E y property test skeletons.
11. GitHub Actions gates.
12. DCO + REUSE/AGPL validation.
13. Release automation baseline.
14. Plugin example compilable/validable.
15. Docs/ADR structure.

## 59. Bootstrap implementation order

El primer ciclo de implementación técnica deberá seguir este orden para reducir retrabajo:

### Step 1 · Repository foundation

- root files,
- license,
- DCO,
- workspaces,
- formatting/linting,
- CI skeleton.

### Step 2 · Backend skeleton

- package,
- settings,
- FastAPI health endpoint,
- PostgreSQL connection,
- Alembic,
- worker/CLI entrypoints.

### Step 3 · Frontend skeleton

- Vite/React/PWA,
- router,
- shell,
- Design System tokens,
- offline DB bootstrap.

### Step 4 · Contracts

- OpenAPI export,
- generated TypeScript client,
- drift gate.

### Step 5 · Identity foundation

- users,
- sessions,
- capabilities,
- tenant/location scope.

### Step 6 · First vertical slice

Se recomienda **Customers + Bicycles minimal slice** antes de Workshop completo, porque prueba:

- API,
- Postgres,
- Dexie,
- sync,
- permissions,
- forms,
- generated client,
- local IDs,
- migrations,
- tests.

### Step 7 · Workshop vertical slice

Crear Service Order básico y llevarlo offline → sync → server → segundo dispositivo.

Ese flujo será la primera validación integral de la arquitectura.

## 60. Primera vertical slice de referencia

```text
Reception device
  → create Customer offline
  → create Bicycle offline
  → create ServiceOrder offline
  → local UI confirms durable save
  → reconnect
  → mutation push
  → server transaction
  → outbox
  → cursor feed
  → second device pull
  → same order appears
```

Acceptance:

- IDs permanecen estables.
- Mutation replay no duplica entidades.
- Audit timeline registra evento.
- UI distingue local/synced.
- Permissions aplican en servidor.
- Cliente generado coincide con OpenAPI.
- E2E puede ejecutarse repetidamente en CI.

## 61. Lo que deliberadamente no se introduce todavía

- Kubernetes.
- Microservices.
- Redis obligatorio.
- Kafka/RabbitMQ obligatorio.
- GraphQL como API principal.
- Event sourcing generalizado.
- CQRS generalizado.
- Redux global por defecto.
- Monorepo framework complejo obligatorio.
- Electron.
- Aplicación Android nativa separada.
- Service mesh.
- Base de datos por bounded context.
- Plugin community code arbitrario dentro del proceso principal.

Cada uno podrá introducirse sólo cuando un problema medido lo justifique.

## 62. Riesgos de ingeniería y mitigaciones

| Riesgo                                   | Impacto           | Mitigación                                      |
| ---------------------------------------- | ----------------- | ----------------------------------------------- |
| Monorepo se vuelve lento                 | Productividad     | path-aware CI, cache, scripts segmentados       |
| Contextos se acoplan                     | Deuda estructural | import rules + ADR + fitness functions          |
| OpenAPI generation crea churn            | PRs ruidosos      | generator fijado + normalización determinista   |
| Offline tests son frágiles               | Falsos negativos  | network harness controlado y clocks inyectables |
| Plugin API se congela muy pronto         | Evolución difícil | surface mínima + experimental namespace pre-1.0 |
| Shared Kernel crece                      | Acoplamiento      | review explícita de cada adición                |
| Migrations bloquean producción           | Downtime          | expand/contract + rehearsal + budgets           |
| Tooling abruma contributors              | Menos comunidad   | bootstrap único, docs claras, CI como autoridad |
| Licencias de assets se pierden           | Riesgo legal      | REUSE + provenance gate                         |
| Actualizaciones automáticas rompen stack | Inestabilidad     | Renovate + grouping + no auto-merge majors      |

## 63. Handoff hacia Fase 6

La siguiente fase deberá convertir esta arquitectura de ingeniería en una **QA & Verification Strategy** completa con:

- matriz de pruebas por requirement/risk,
- test pyramid formal,
- browser/device matrix,
- offline chaos testing,
- sync concurrency testing,
- accessibility test plan,
- security verification,
- performance/load testing,
- migration/restore testing,
- plugin compatibility testing,
- release qualification,
- defect severity,
- quality metrics,
- test evidence y exit criteria de cada release.

## 64. Resultado de la fase

La plataforma queda preparada conceptualmente para pasar de documentación arquitectónica a un repositorio que pueda ser generado y ejecutado por personas o agentes de IA sin decidir de nuevo la estructura fundamental a mitad del desarrollo.

El objetivo no es maximizar cantidad de tooling. Es maximizar **claridad de ownership, reproducibilidad, capacidad de prueba, resiliencia offline, seguridad y facilidad de contribución**, manteniendo el proyecto suficientemente simple para que un pequeño taller o un implementador independiente no necesite infraestructura empresarial para utilizarlo.
