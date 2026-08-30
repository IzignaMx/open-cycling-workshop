# Fase 6 · QA, Testing & Verification Strategy v0.1

**Open Cycling Workshop Platform**  
Baseline: Foundation v0.2 · Functional Requirements v0.1 · Technical Architecture v0.2 · Security/Privacy v0.1 · UX/UI v0.1 · Repository & Engineering Architecture v0.1  
License baseline: `AGPL-3.0-only`

> Este documento convierte calidad, resiliencia y seguridad en criterios verificables de ingeniería. La plataforma no se considera correcta por compilar ni por superar una suite superficial. Cada riesgo importante debe tener una estrategia de prueba, evidencia reproducible y un gate de release proporcional a su impacto.

## 1. Objetivo de la fase

La Fase 6 define cómo demostrar que la plataforma funciona correctamente en condiciones normales, degradadas y adversas, especialmente cuando existen operaciones offline, múltiples dispositivos, sincronización eventual, movimientos financieros, inventario, datos personales, plugins y actualizaciones de esquema.

Los objetivos concretos son:

1. Establecer un modelo de calidad trazable entre requisitos, riesgos, tests y evidencias.
2. Definir el portfolio de pruebas por capa y por bounded context.
3. Tratar sincronización, migraciones, backups y recuperación como capacidades de producto verificables.
4. Diseñar pruebas específicas para operación offline, reconexión, concurrencia y conflictos.
5. Definir matrices de navegadores, dispositivos y topologías de despliegue.
6. Formalizar pruebas de accesibilidad, seguridad, rendimiento, privacidad e internacionalización.
7. Definir gates progresivos para releases V0.x y un release qualification obligatorio para V1.0.
8. Evitar métricas de cobertura engañosas y priorizar invariantes, riesgos y comportamiento observable.
9. Reducir flakiness y hacer que fallas no deterministas sean tratadas como defectos del sistema de ingeniería.
10. Producir evidencia suficiente para que un implementador independiente pueda confiar en una release sin depender del equipo original.

## 2. Principios de calidad no negociables

### QA-P01 · Riesgo antes que cantidad

Las pruebas se priorizan por severidad y probabilidad de falla, no por facilidad para alcanzar una cifra de cobertura.

### QA-P02 · Cero pérdida silenciosa

Ninguna operación confirmada al usuario puede desaparecer silenciosamente por cierre del navegador, pérdida de red, reinicio, conflicto, reintento o actualización.

### QA-P03 · Determinismo del Core

Ledger, state machines, cálculo de totales, permisos, idempotencia y resolución de conflictos deben tener pruebas deterministas y reproducibles.

### QA-P04 · Offline es un modo normal

Las pruebas offline no son edge cases. Forman parte de la suite ordinaria del producto.

### QA-P05 · Recuperación probada

Un backup que nunca ha sido restaurado no se considera backup válido.

### QA-P06 · Migraciones como producto

Toda migración de PostgreSQL e IndexedDB debe poder probarse desde versiones soportadas y con datos representativos.

### QA-P07 · Accesibilidad bloqueante

Los defectos de accesibilidad que impidan completar un flujo crítico bloquean release igual que un defecto funcional equivalente.

### QA-P08 · Seguridad verificable

Los controles de seguridad importantes deben tener pruebas automatizadas o procedimientos reproducibles, no solamente documentación.

### QA-P09 · Evidencia versionada

La release debe conservar artefactos de CI suficientes para reconstruir qué se verificó, sobre qué commit y con qué configuración.

### QA-P10 · Testabilidad arquitectónica

Si una característica importante es difícil de probar, se considera una señal de diseño deficiente y debe evaluarse antes de añadir más mocks.

## 3. Modelo de trazabilidad

Cada requisito verificable tendrá relaciones explícitas con riesgos y pruebas.

```text
Requirement
   ↓
Risk / Invariant
   ↓
Test Case or Property
   ↓
Execution Evidence
   ↓
Release Gate
```

### 3.1 Identificadores

| Tipo | Prefijo | Ejemplo |
|---|---|---|
| Requisito funcional | `FR` | `FR-WO-021` |
| Requisito no funcional | `NFR` | `NFR-OFF-004` |
| Seguridad | `SEC` | `SEC-SYNC-007` |
| Regla de negocio | `BR` | `BR-INV-003` |
| Riesgo de calidad | `QRISK` | `QRISK-SYNC-004` |
| Invariante | `INV` | `INV-LEDGER-002` |
| Caso de prueba | `TC` | `TC-SYNC-014` |
| Propiedad generativa | `PROP` | `PROP-INV-003` |
| Escenario de caos | `CHAOS` | `CHAOS-OFF-006` |
| Gate de release | `GATE` | `GATE-V1-012` |

### 3.2 Regla de aceptación

Un requisito crítico no se considera terminado hasta tener al menos:

1. criterio de aceptación verificable
2. una prueba automatizada en la capa apropiada cuando sea técnicamente viable
3. evidencia de CI
4. cobertura de caso negativo o degradado cuando corresponda
5. referencia al riesgo mitigado

## 4. Modelo de calidad del producto

Se adopta un modelo práctico inspirado en confiabilidad, seguridad, usabilidad y mantenibilidad, adaptado a la naturaleza local first.

| Dimensión | Pregunta de control | Evidencia esperada |
|---|---|---|
| Correctitud | ¿El resultado de negocio es correcto? | Unit, property, integration, E2E |
| Integridad | ¿Los datos permanecen consistentes? | Invariantes, DB tests, sync tests |
| Resiliencia | ¿Continúa funcionando ante fallas parciales? | Chaos, offline, retry, recovery |
| Seguridad | ¿Resiste abuso razonable? | SAST, DAST, authz tests, threat cases |
| Privacidad | ¿Minimiza exposición y retención? | Data flow tests, export/delete tests |
| Accesibilidad | ¿Puede completarse con tecnologías asistivas? | axe, keyboard, manual SR review |
| Rendimiento | ¿Responde dentro de budgets? | Browser, API, load, storage benchmarks |
| Compatibilidad | ¿Funciona en dispositivos soportados? | Matrix automation + device passes |
| Operabilidad | ¿Puede respaldarse, actualizarse y recuperarse? | Restore drills, migration rehearsal |
| Extensibilidad | ¿Plugins pueden evolucionar sin romper Core? | Contract tests, compatibility suites |
| Mantenibilidad | ¿Las fallas se localizan y corrigen de forma razonable? | Static checks, architecture tests, observability |

## 5. Portfolio de pruebas

No se utilizará una pirámide rígida como objetivo numérico. Se utilizará un portfolio equilibrado.

```text
Property and invariant tests      ← reglas matemáticas y dominios críticos
Unit tests                         ← lógica local, rápida y determinista
Integration tests                  ← DB, filesystem, queues, providers simulados
Contract tests                     ← OpenAPI, plugins, adapters
Component tests                    ← UI aislada con comportamiento realista
E2E tests                          ← journeys críticos
Offline and multi-device tests     ← diferenciador principal
Chaos and recovery tests           ← resiliencia
Security and accessibility tests   ← gates transversales
Performance and load tests         ← budgets y degradación
Manual exploratory testing         ← riesgos emergentes y UX
```

### 5.1 Regla de selección

La prueba debe ejecutarse en la capa más baja que pueda detectar correctamente el defecto, salvo que el riesgo sólo exista por integración entre capas.

No se escribirá un E2E para validar una función pura que puede demostrarse con una property test. Tampoco se sustituirá un flujo de sincronización real por mocks unitarios si el riesgo está precisamente en la coordinación entre cliente y servidor.

## 6. Clasificación de criticidad

### Criticality C0

Pérdida o corrupción de datos, acceso no autorizado grave, alteración financiera, imposibilidad de restaurar, bypass de permisos, incompatibilidad destructiva de migración.

### Criticality C1

Imposibilidad de completar un flujo central, duplicación de cobro o inventario, sincronización incorrecta recuperable, inaccesibilidad de una función esencial.

### Criticality C2

Degradación significativa con workaround razonable, errores de presentación de información no destructivos, fallas parciales de integración.

### Criticality C3

Defectos cosméticos o menores sin impacto material sobre operación, seguridad o accesibilidad.

Los casos C0 y C1 tienen gates explícitos en V1.0.

## 7. Invariantes de dominio prioritarias

### INV-LEDGER-001 · Inventario derivado

El stock actual debe ser derivable de movimientos válidos. No puede depender de un campo editable que contradiga el ledger.

### INV-LEDGER-002 · Operaciones compensatorias

Un movimiento confirmado no se elimina para corregirlo. Se genera un movimiento compensatorio auditable.

### INV-PAY-001 · No doble contabilización

Reintentar la misma mutación idempotente no puede registrar dos pagos.

### INV-SYNC-001 · Idempotencia

Procesar dos veces una mutación con el mismo identificador produce el mismo estado observable que procesarla una sola vez.

### INV-SYNC-002 · Monotonicidad de acknowledgement

Un cliente no debe retroceder de una operación confirmada a un estado donde el servidor la desconozca, salvo recuperación explícita de corrupción con advertencia visible.

### INV-WO-001 · State machine válida

Las órdenes de servicio sólo pueden transicionar mediante aristas permitidas o acciones administrativas auditadas.

### INV-AUTHZ-001 · Deny by default

La ausencia de capability concede cero acceso implícito.

### INV-AUDIT-001 · Auditabilidad

Las acciones críticas generan evidencia suficiente para identificar actor, momento, objeto y resultado.

### INV-MIG-001 · Preservación

Una migración soportada no pierde información representable del esquema anterior.

### INV-BACKUP-001 · Restaurabilidad

Un backup declarado válido puede reconstruir una instancia utilizable en un entorno limpio.

## 8. Unit testing

Los unit tests cubren lógica sin I/O real y deben ser extremadamente rápidos.

Áreas prioritarias:

- state machines
- cálculos de precios, impuestos y descuentos
- políticas de autorización
- normalización de datos
- validadores
- composición de movimientos de ledger
- reglas de inventario
- selección de estrategia de conflictos
- transformación de eventos
- plantillas de automatización
- permisos por capability
- serialización de contratos internos

### 8.1 Reglas

1. Un unit test no debe depender de red, reloj real o filesystem global.
2. El tiempo se inyecta mediante clock controlable.
3. UUIDs se generan mediante factory inyectable cuando el resultado exacto importe.
4. Los mocks se limitan a boundaries, no a cada colaborador interno.
5. Testear implementación privada no sustituye testear comportamiento público.

## 9. Property based testing

`Hypothesis` será obligatorio en dominios donde las combinaciones superan ampliamente los ejemplos escritos a mano.

### 9.1 Casos prioritarios

| Propiedad | Dominio | Ejemplo |
|---|---|---|
| Conmutatividad controlada | Ledger | movimientos independientes mantienen saldo final |
| Idempotencia | Sync | repetir operación no duplica efecto |
| Round trip | Serialization | encode/decode preserva contrato |
| Conservación | Inventory | stock final = inicial + suma movimientos |
| Invariantes de estado | Workshop | ningún camino alcanza estado imposible |
| Monotonicidad | Cursors | cursor confirmado no decrece |
| Preservación | Migration | datos antiguos representables permanecen |
| Totalización | POS | subtotales + ajustes = total final |

### PROP-SYNC-001

Para cualquier secuencia válida de mutaciones con reintentos arbitrarios, el estado final después de deduplicación debe ser equivalente al procesamiento de cada mutación única una vez.

### PROP-INV-001

Para cualquier secuencia de movimientos válidos, reconstruir stock desde cero debe producir el mismo resultado que el estado materializado.

### PROP-WO-001

Para cualquier secuencia generada de transiciones permitidas, la orden nunca debe alcanzar simultáneamente estados mutuamente excluyentes.

## 10. Integration testing del backend

Las integration tests ejecutan componentes reales con PostgreSQL y filesystem/objetos de prueba.

Se evitará SQLite como sustituto de PostgreSQL porque escondería diferencias de constraints, tipos, locking y transacciones.

### 10.1 Infraestructura efímera

Cada suite debe poder levantar dependencias aisladas mediante contenedores o servicios efímeros. Los tests nunca dependen de una base compartida persistente entre runs.

### 10.2 Cobertura mínima

- repositorios reales
- transacciones
- unique constraints
- foreign keys
- row locking cuando aplique
- transactional outbox
- queue claiming
- idempotency keys
- paginación por cursor
- authn/authz
- upload metadata
- retention jobs

## 11. API y contract testing

OpenAPI generado por FastAPI es el contrato HTTP canónico.

### 11.1 Gates

1. El schema OpenAPI debe generarse de forma determinista.
2. El cliente TypeScript debe regenerarse sin diff inesperado.
3. Breaking changes requieren SemVer compatible y migration note.
4. Endpoints críticos tendrán contract tests contra payloads válidos e inválidos.
5. Códigos de error deberán respetar el envelope documentado.

### 11.2 Compatibility

Durante una ventana de actualización escalonada, un cliente soportado ligeramente anterior debe recibir errores comprensibles y nunca producir corrupción si encuentra un servidor más nuevo dentro de la ventana declarada.

## 12. PostgreSQL migration testing

Cada migración Alembic debe verificarse contra al menos:

1. base vacía
2. snapshot de versión previa soportada
3. dataset `demo-workshop`
4. dataset `load`
5. datos con nulls y extremos permitidos
6. rollback solamente cuando se declare técnicamente seguro

### 12.1 Expand and contract

Los cambios incompatibles se dividen en etapas:

```text
Expand schema
   ↓
Deploy compatible code
   ↓
Backfill
   ↓
Observe
   ↓
Contract old schema
```

No se acepta una migration que requiera actualizar simultáneamente todos los clientes offline.

## 13. IndexedDB y Dexie migration testing

La base local es parte crítica del producto.

Cada incremento de schema version debe probar:

- upgrade desde cada versión local soportada
- datos pendientes de sincronización
- browser kill durante una ventana segura simulable
- reanudación posterior
- índices nuevos
- tablas eliminadas mediante proceso de deprecación
- compatibilidad con service worker actualizado

### INV-LOCAL-001

Una actualización de la PWA no puede descartar mutaciones locales `pending`, `retrying` o `conflict`.

### GATE-LOCAL-001

Toda release que cambie schema IndexedDB debe superar migración automatizada desde la versión mínima soportada antes de poder etiquetarse.

## 14. Sync Engine verification

El Sync Engine recibe la mayor inversión de QA del proyecto.

### 14.1 Modelo de referencia

Se mantendrá un modelo simplificado y determinista capaz de calcular el resultado esperado para secuencias de operaciones. Las pruebas compararán implementación real contra el modelo cuando sea viable.

### 14.2 Dimensiones

- orden de mutaciones
- duplicados
- retries
- timeouts
- acknowledgements perdidos
- server restart
- client restart
- operaciones concurrentes
- conflictos de campo
- operaciones append only
- clocks divergentes
- lote parcial
- cursor stale
- autenticación expirada
- schema mismatch

### 14.3 Escenarios obligatorios

| ID | Escenario | Resultado esperado |
|---|---|---|
| TC-SYNC-001 | Crear offline y reconectar | entidad sincronizada una vez |
| TC-SYNC-002 | ACK se pierde después de commit | retry no duplica operación |
| TC-SYNC-003 | servidor reinicia entre lotes | cliente reanuda desde cursor seguro |
| TC-SYNC-004 | dos dispositivos editan campos independientes | merge según política |
| TC-SYNC-005 | dos dispositivos editan mismo campo protegido | conflicto visible o regla explícita |
| TC-SYNC-006 | venta y ajuste simultáneos | ledger conserva ambos movimientos |
| TC-SYNC-007 | token expira con queue pendiente | datos permanecen locales hasta reauth |
| TC-SYNC-008 | payload incompatible | rechazo explícito sin pérdida local |
| TC-SYNC-009 | duplicación de lote completo | estado final sin duplicados |
| TC-SYNC-010 | reconexiones intermitentes | eventual convergence |

## 15. Concurrency testing

Se probarán condiciones de carrera reales a nivel DB y API.

Casos mínimos:

- dos pagos contra la misma orden
- dos ventas de la última unidad disponible
- dos workers reclamando el mismo job
- dos usuarios autorizando cambios incompatibles
- múltiples sync batches con mutation IDs repetidos
- actualización de orden mientras se genera una automatización

Las pruebas deben verificar no sólo el HTTP resultante, sino también el estado final persistido y los eventos emitidos.

## 16. Chaos testing

El proyecto tendrá una suite de caos controlado y reproducible.

### 16.1 Fallas inyectables

- pérdida de red antes de request
- pérdida de red después de request antes de respuesta
- latencia alta
- packet loss simulado
- HTTP 429
- HTTP 500 y 503
- restart del API
- restart del worker
- PostgreSQL temporalmente no disponible
- storage de blobs no disponible
- quota local cercana al límite
- reloj del dispositivo desfasado
- cierre abrupto de pestaña

### 16.2 Regla

Los chaos tests no persiguen que todo funcione mágicamente durante cualquier falla. Verifican que el sistema:

1. degrade de manera explícita
2. no pierda datos confirmados
3. no duplique efectos irreversibles
4. comunique el estado al usuario
5. pueda recuperarse cuando la dependencia vuelva

## 17. Offline testing

Se definen perfiles estándar.

### OFF-PROFILE-A · Conexión saludable

Baseline para comparar.

### OFF-PROFILE-B · Offline inmediato

El usuario abre una instalación previamente inicializada sin red.

### OFF-PROFILE-C · Pérdida durante flujo

La red desaparece después de cargar datos y antes de confirmar una mutación.

### OFF-PROFILE-D · Offline prolongado

El dispositivo acumula actividad de una jornada o varios días según política configurada.

### OFF-PROFILE-E · Intermitencia

Conectividad entra y sale repetidamente.

### OFF-PROFILE-F · Reconexión con divergencia

Otro dispositivo produjo cambios mientras el primero estuvo offline.

Cada flujo crítico de Workshop Core debe tener al menos un escenario offline antes de V1.0.

## 18. Multi device testing

El entorno E2E deberá poder lanzar al menos dos contextos de navegador independientes contra la misma organización.

### Escenarios

```text
Device A                        Device B
────────                        ────────
Create order offline            Modify customer online
Add service task                Sell inventory item
Reconnect                       Continue operation
          ↘                  ↙
             Synchronize
                 ↓
          Assert convergence
```

Se priorizarán casos donde los dispositivos tengan datos iniciales diferentes y queues pendientes.

## 19. Frontend component testing

`Vitest` y Testing Library cubrirán comportamiento observable de componentes.

Se validará:

- keyboard behavior
- focus management
- validation messages
- loading/saving/sync states
- optimistic UI
- rollback visual cuando una operación sea rechazada
- permissions
- empty states
- error boundaries
- reduced motion
- high contrast behavior

No se harán snapshots masivos de HTML como sustituto de assertions semánticas.

## 20. End to end testing

Playwright será el runner E2E de referencia.

### 20.1 Golden journeys V1

1. registrar cliente y bicicleta
2. crear orden
3. inspeccionar y diagnosticar
4. crear presupuesto
5. autorizar desde Customer Portal
6. ejecutar trabajo
7. consumir inventario
8. realizar QC
9. marcar lista
10. enviar notificación mediante provider simulado
11. registrar pago
12. entregar
13. consultar historial

### 20.2 Journeys adicionales

- operación completa con pérdida de red intermedia
- dos dispositivos concurrentes
- migración y continuación de trabajo pendiente
- usuario sin permisos intentando acción restringida
- restauración de backup y continuación de una orden
- cambio de white label sin romper contraste

## 21. Browser and device support matrix

### Tier 1 · Bloqueante

- Chrome/Chromium estable en Windows 11
- Microsoft Edge estable en Windows 11
- Chrome estable en Android moderno
- tablet Android física de referencia o dispositivo equivalente de laboratorio

### Tier 2 · Soportado

- Firefox estable en Windows, Linux y macOS
- Safari estable en macOS
- Safari iOS para Customer Portal y funciones web compatibles

### Tier 3 · Best effort

Navegadores fuera de ventana de soporte o plataformas sin capacidad suficiente para PWA completa.

### 21.1 Política de versiones

Para Tier 1 se probarán la versión estable actual y una ventana razonable hacia atrás definida en cada release train. No se prometerá soporte indefinido a motores obsoletos.

### 21.2 Android

La QA deberá incluir al menos:

- tablet de 8 a 11 pulgadas
- densidad media y alta
- orientación portrait y landscape
- memoria limitada razonable
- teclado virtual
- cámara para fotografías/QR cuando aplique
- suspensión y reanudación de la app instalada

## 22. Accessibility testing

WCAG 2.2 AA es gate mínimo, con targets táctiles reforzados por el Design System.

### 22.1 Automatización

- axe-core integrado en component tests prioritarios
- axe en journeys Playwright
- linting de patrones accesibles donde aplique

### 22.2 Verificación manual obligatoria antes de V1.0

- navegación completa por teclado
- focus visible y orden lógico
- zoom 200 y 400 por ciento en pantallas representativas
- screen reader sobre journeys críticos
- high contrast / forced colors donde aplique
- reduced motion
- touch targets en Workshop Mode
- mensajes de error asociados correctamente
- tablas densas con headers y navegación comprensible

### 22.3 Gate

Cualquier barrera que impida a una persona completar un journey crítico se clasifica como C1 y bloquea release.

## 23. Security verification

La Fase 3 define qué proteger. Esta fase define cómo verificarlo.

### 23.1 Automatización continua

- dependency vulnerability scanning
- secret scanning
- SAST
- container scanning
- SBOM generation
- license compliance
- tests de authz
- tests de rate limit en rutas sensibles
- upload validation
- CSP/header verification cuando aplique

### 23.2 DAST

Antes de V1.0 se ejecutará un baseline DAST contra una instancia de staging aislada, complementado con pruebas manuales sobre:

- authentication
- session invalidation
- IDOR/BOLA
- privilege escalation
- portal tokens
- replay de mutaciones
- upload abuse
- plugin permissions
- backup access

### 23.3 Regla de release

Vulnerabilidades conocidas Critical o High explotables dentro del threat model bloquean V1.0 salvo excepción documentada, con mitigación compensatoria y aceptación explícita de riesgo. La excepción no puede ocultarse en un issue privado sin referencia en el proceso de release.

## 24. Privacy verification

Se probarán comportamientos y no sólo políticas.

Casos mínimos:

- exportar datos de cliente
- eliminar o anonimizar cuando la política lo permita
- conservar registros legales/auditables cuando exista obligación
- revocar consentimiento de comunicaciones
- evitar envío posterior no autorizado
- impedir que portal público exponga datos de terceros
- borrar blobs huérfanos según retención
- backups respetan política documentada de expiración

## 25. Performance budgets

Los budgets se medirán en hardware representativo, no únicamente en máquinas de desarrollo potentes.

### 25.1 Frontend

Objetivos iniciales para pantallas críticas con dataset representativo:

| Métrica | Target preliminar |
|---|---:|
| Interaction response local | < 100 ms para acciones simples |
| Cambio de vista ya cargada | < 250 ms percibidos |
| Búsqueda local ordinaria | < 150 ms en dataset objetivo |
| Render de lista grande virtualizada | sin bloqueo prolongado del main thread |
| Startup offline instalada | usable sin depender de request remoto |

### 25.2 API

Para operaciones ordinarias bajo carga nominal:

| Percentil | Target preliminar |
|---|---:|
| p50 | < 150 ms |
| p95 | < 500 ms |
| p99 | < 1 s salvo operaciones explícitamente pesadas |

Estos budgets son SLO internos iniciales y se calibrarán con benchmarks reales antes de V1.0.

## 26. Load and stress testing

### 26.1 Perfiles

- microtaller: 1 a 3 usuarios activos
- taller mediano: 5 a 15
- multisucursal inicial: 20 a 75 concurrentes
- burst de sync: múltiples dispositivos reconectando simultáneamente

### 26.2 Pruebas prioritarias

- sync batches
- búsqueda de catálogo
- creación de órdenes
- ledger writes
- portal status checks
- worker queue
- notificaciones masivas razonables

### 26.3 Stress

La prueba no sólo busca el máximo throughput. Debe identificar el punto donde la degradación deja de ser graceful y confirmar que no aparece corrupción antes de ese punto.

## 27. Reliability and endurance testing

Antes de V1.0 se ejecutarán soak tests que mantengan API, worker y DB operando por periodos prolongados con carga sintética moderada.

Se observará:

- crecimiento de memoria
- conexiones DB
- queue backlog
- retries
- locks prolongados
- tamaño del outbox
- blobs huérfanos
- degradación de tiempos

## 28. Backup and restore verification

### 28.1 Restore drill

El procedimiento automatizado debe:

1. crear dataset conocido
2. generar backup
3. destruir o aislar instancia original
4. restaurar en entorno limpio
5. arrancar aplicación
6. ejecutar smoke suite
7. comparar invariantes
8. producir evidencia

### 28.2 Frecuencia

- CI: pruebas estructurales del mecanismo
- Nightly o scheduled: restore drill automatizado cuando infraestructura lo permita
- Release candidate V1: restore drill completo obligatorio

### 28.3 Datos locales

Cuando exista export/backup local soportado, también deberá probarse su importación y manejo de versiones.

## 29. Disaster recovery testing

Se simularán como mínimo:

- pérdida del servidor con clientes offline aún operativos
- restauración de PostgreSQL desde backup
- reemplazo del servidor LAN
- pérdida del storage de blobs con DB intacta
- corrupción lógica detectada después de una release

La recuperación debe documentar claramente qué datos pueden reconstruirse y cuáles requieren backup.

## 30. Plugin testing strategy

Cada plugin oficial debe superar:

1. manifest validation
2. capability permission tests
3. compatibility contract tests
4. installation/uninstallation tests
5. migration tests si persiste datos
6. failure isolation
7. upgrade tests
8. security checks
9. license checks

### 30.1 Compatibility matrix

El Plugin SDK declara rangos de Core compatibles. CI probará plugins oficiales contra la versión mínima y actual soportada cuando sea económicamente razonable.

### 30.2 Community plugins

El registro comunitario podrá ejecutar checks públicos, pero una aprobación del registry no debe presentarse como auditoría de seguridad exhaustiva.

## 31. Integrations and communications testing

Los providers externos se prueban en tres capas:

### Contract adapter tests

Validan transformación y errores sin red real.

### Sandbox integration tests

Se ejecutan contra sandbox oficial cuando exista y sea estable.

### Production smoke opt in

Sólo para implementaciones que lo habiliten con credenciales específicas y sin datos reales innecesarios.

WhatsApp, email, pagos y futuros adapters deberán tolerar timeouts, rate limits y retries sin duplicar efectos.

## 32. Payments verification

Aunque un proveedor externo procese pagos, el sistema debe verificar:

- idempotency
- webhook replay
- out of order webhook
- amount mismatch
- currency mismatch
- partial payment
- refund
- provider timeout
- duplicated callback
- reconciliation

Nunca se considerará el redirect del navegador como única evidencia de pago.

## 33. Inventory verification

Inventario requiere especialmente:

- property tests de ledger
- concurrencia sobre última unidad
- devoluciones
- ajustes
- transferencias
- stock negativo según política
- movimientos compensatorios
- rebuild del materialized balance

### GATE-INV-001

Una release no puede publicarse si el rebuild de stock sobre fixtures canónicos difiere del estado materializado esperado.

## 34. Automation Engine verification

Se probarán:

- trigger matching
- conditions
- action execution
- retry
- deduplication
- loop prevention
- disabled rules
- audit trail
- provider failure

### INV-AUTO-001

El mismo evento no debe producir múltiples efectos externos irreversibles cuando un worker reintenta la ejecución, salvo que la acción se declare explícitamente no idempotente y tenga protección equivalente.

## 35. Search testing

Búsquedas deberán probar:

- acentos
- mayúsculas/minúsculas
- términos parciales
- SKU y códigos
- nombres similares
- datasets grandes
- permisos sobre resultados
- consistencia offline

La búsqueda no debe revelar entidades que el usuario no tiene capability para consultar.

## 36. Internationalization and localization testing

Se verificará:

- idiomas soportados
- fallbacks
- strings faltantes
- interpolación
- pluralización
- monedas
- formatos de fecha
- timezone
- unidades
- textos largos
- pseudolocalization

Ninguna pantalla crítica debe romper layout con expansión artificial de texto de al menos 30 por ciento.

## 37. White labeling and theming testing

El motor de marca se prueba como configuración, no como fork.

Checks mínimos:

- logos con proporciones distintas
- nombres cortos y largos
- colores claros y oscuros
- contraste calculado
- favicon
- documentos
- emails
- Customer Portal
- dark mode cuando aplique

Configuraciones que violen mínimos de contraste deben advertirse o rechazarse según severidad.

## 38. Document and print testing

Tickets, presupuestos, comprobantes y documentos imprimibles requieren:

- snapshot visual controlado o comparación estructural
- tamaños A4 y ticket donde corresponda
- printer safe styles
- nombres largos
- montos grandes
- QR legible
- caracteres internacionales
- salto de página estable

Los golden files se usarán solamente cuando aporten señal real y su actualización requiera revisión humana.

## 39. Visual regression testing

Se aplicará selectivamente a superficies visuales estables:

- shell
- Workshop Mode
- Customer Portal
- estados críticos
- documentos
- white label reference themes

No se pretende capturar cada pantalla y bloquear desarrollo por diferencias insignificantes. Las tolerancias y áreas dinámicas se declararán explícitamente.

## 40. Exploratory testing

Antes de releases significativas se ejecutarán sesiones exploratorias con charters.

Ejemplos:

- “Intenta completar una jornada de taller sin Internet”
- “Busca inconsistencias entre dos tablets después de editar las mismas órdenes”
- “Opera el Workshop Mode con una sola mano y targets táctiles”
- “Intenta confundir autorización, presupuesto y cobro”
- “Fuerza errores de integración sin perder trabajo”

Los hallazgos se registran igual que defects ordinarios y alimentan nuevos tests automatizados cuando sean regresiones reproducibles.

## 41. Test data strategy

Fixtures canónicos:

### `minimal`

Organización pequeña, un usuario admin, datos mínimos.

### `demo-workshop`

Dataset humano y realista con clientes, bicicletas, órdenes en distintos estados, ventas, inventario y comunicaciones simuladas.

### `load`

Dataset determinista grande para performance, búsquedas, migraciones y sincronización.

### 41.1 Privacidad

No se utilizarán dumps de producción ni datos personales reales en CI público.

## 42. Test environments

### Local

Desarrollo rápido con dependencias efímeras.

### CI

Entorno reproducible sin credenciales productivas.

### Preview

Instancia por PR o rama cuando resulte coste eficiente.

### Staging

Topología lo más cercana posible a producción para release qualification.

### Hardware lab

Al menos una tablet Android y una máquina Windows representativas para journeys Tier 1.

## 43. CI pipeline

Pipeline mínimo de PR:

```text
Checkout
  ↓
License / DCO / secrets
  ↓
Lint + format
  ↓
Typecheck
  ↓
Unit + property tests
  ↓
Integration tests
  ↓
Contract drift check
  ↓
Frontend component + a11y
  ↓
Build
  ↓
Selected E2E
  ↓
Security scans
```

### 43.1 Parallelization

Las etapas independientes se ejecutan en paralelo. La optimización nunca puede ocultar dependencias reales o volver no reproducible el pipeline.

## 44. Nightly verification

La suite nightly podrá incluir:

- matriz ampliada de navegadores
- chaos tests
- sync fuzzing
- migration matrix completa
- load tests ligeros
- restore drill
- dependency scans amplios
- plugin compatibility
- visual regression completa

Los fallos nightly crean issues o alertas visibles y no pueden ignorarse indefinidamente.

## 45. Release candidate pipeline

Una release candidate ejecuta el superset de PR y nightly, además de:

1. build reproducible
2. SBOM
3. artifacts checksums
4. migration rehearsal
5. restore drill
6. Tier 1 hardware pass
7. security qualification
8. accessibility manual checklist
9. upgrade from previous supported release
10. release notes validation

## 46. Release gates por etapa

### V0.1 Foundations

Bloqueantes:

- lint/typecheck
- unit/integration baseline
- OpenAPI drift
- PostgreSQL migration tests
- IndexedDB migration baseline
- Sync Engine prototype con idempotencia demostrada
- no secrets

### V0.2 Workshop Core

Añade:

- golden journey recepción → orden
- state machine properties
- RBAC
- offline creation/reconnect
- accessibility sobre flujo central

### V0.3 Inventory

Añade:

- inventory ledger properties
- concurrency
- rebuild validation
- purchase/return scenarios

### V0.4 POS

Añade:

- totals
- payments
- refunds
- idempotency
- cash flows

### V0.5 Communications

Añade:

- provider contracts
- retry/deduplication
- consent
- rate limit behavior

### V0.6 Customer Experience

Añade:

- portal security
- authorization links
- mobile accessibility
- document generation

### V0.7 Workshop Intelligence

Añade:

- provenance of technical data
- checklist integrity
- search and content permissions

### V0.8 Automation

Añade:

- loop prevention
- idempotent actions
- retry policies
- auditability

### V0.9 Hardening

Añade:

- full migration matrix
- chaos suite
- extended browser matrix
- soak
- restore drill
- DAST baseline
- manual accessibility pass

### V1.0 Production Release

Todos los gates V1 deben estar verdes.

## 47. V1.0 qualification gates

| Gate | Condición de aprobación |
|---|---|
| GATE-V1-001 | cero defects C0 abiertos |
| GATE-V1-002 | cero C1 abiertos sin excepción formal |
| GATE-V1-003 | golden journey completo online y offline |
| GATE-V1-004 | multi-device convergence suite aprobada |
| GATE-V1-005 | migrations PostgreSQL desde versión soportada aprobadas |
| GATE-V1-006 | migrations IndexedDB desde versión soportada aprobadas |
| GATE-V1-007 | restore drill completo aprobado |
| GATE-V1-008 | inventory ledger invariant suite aprobada |
| GATE-V1-009 | payment idempotency/reconciliation aprobada |
| GATE-V1-010 | authz negative suite aprobada |
| GATE-V1-011 | seguridad Critical/High bloqueante resuelta |
| GATE-V1-012 | WCAG 2.2 AA crítica aprobada |
| GATE-V1-013 | Tier 1 browser/device matrix aprobada |
| GATE-V1-014 | performance budgets sin regresiones críticas |
| GATE-V1-015 | plugin SDK compatibility suite aprobada |
| GATE-V1-016 | AGPL/SPDX/REUSE/license checks aprobados |
| GATE-V1-017 | SBOM y checksums generados |
| GATE-V1-018 | upgrade rehearsal desde release previa soportada |
| GATE-V1-019 | release notes y breaking changes documentados |
| GATE-V1-020 | rollback/recovery playbook validado |

## 48. Defect severity model

### Sev 0 · Release Stopper

Corrupción o pérdida de datos, vulnerabilidad crítica explotable, restauración imposible, doble cobro reproducible, bypass grave de autorización.

### Sev 1 · Critical

Flujo esencial imposible, sync produce estado incorrecto recuperable sólo manualmente, inaccesibilidad de journey esencial, error financiero material sin corrupción permanente.

### Sev 2 · Major

Función importante degradada con workaround, integración parcial defectuosa, regresión importante de performance.

### Sev 3 · Minor

Problema limitado, cosmético o de ergonomía sin impacto material.

### Sev 4 · Trivial

Detalle muy menor o mejora sin defecto funcional.

## 49. Flaky test policy

Un test flaky es un defecto del proyecto.

Reglas:

1. No se permite “rerun until green” como solución permanente.
2. Un test confirmado flaky se etiqueta y se investiga.
3. Puede aislarse temporalmente sólo con issue, owner y plazo de corrección.
4. Un test C0/C1 no puede permanecer quarantined para publicar V1.
5. La tasa de flakes se mide.

## 50. Coverage policy

No se establece una cifra global como definición de calidad.

Se utilizarán thresholds por áreas donde tengan sentido:

- dominio crítico: branch coverage alta y property tests
- adapters triviales: cobertura proporcional
- generated code: excluido
- UI: comportamiento significativo sobre líneas

### Regla

Disminuir cobertura de un bounded context crítico requiere justificar qué riesgo dejó de estar cubierto o por qué la métrica era ruido.

## 51. Mutation testing

Se utilizará selectivamente en dominios críticos para medir la capacidad real de la suite de detectar cambios incorrectos.

Candidatos:

- ledger
- state machines
- permission policies
- totals
- sync deduplication

No se ejecutará necesariamente en cada PR si el costo es alto. Puede formar parte de nightly o release qualification.

## 52. Observability verification

Los tests deberán verificar que eventos operativos relevantes generan telemetría útil sin filtrar datos personales innecesarios.

Casos:

- correlation IDs
- sync batch outcome
- retry counts
- queue lag
- migration result
- backup result
- provider error class

No se incluirán cuerpos completos de mensajes, fotografías ni secretos en logs por defecto.

## 53. Test evidence and retention

Artefactos útiles de CI:

- JUnit/XML o equivalente
- coverage reports
- Playwright traces de fallas
- screenshots de fallas
- accessibility reports
- security scan summaries
- SBOM
- migration logs
- restore logs
- benchmark summaries

La retención dependerá del proveedor CI y costo, pero releases V1.x deben conservar evidencia suficiente para auditoría razonable.

## 54. Quality metrics

Métricas recomendadas:

- escaped defects por severidad
- flaky test rate
- mean time to repair CI
- sync conflict rate en pruebas
- migration success rate
- restore drill success rate
- accessibility critical defects
- performance regression count
- test execution time
- release rollback rate

No se utilizará “número de tests” como KPI de calidad.

## 55. Quality ownership

La calidad no pertenece a un único rol QA.

### Desarrollador

Responsable de pruebas de su cambio y de no degradar invariantes.

### Reviewer

Verifica riesgo, tests, migraciones y observabilidad.

### Maintainer

Define gates, exceptions y release qualification.

### Implementador

Ejecuta smoke, restore y checks de infraestructura en el entorno del cliente.

### Comunidad

Puede aportar casos, fixtures, fuzzing, hardware reports y regresiones reproducibles.

## 56. Pull request quality checklist

Todo PR significativo responde:

1. ¿Qué requirement o issue resuelve?
2. ¿Qué riesgos introduce?
3. ¿Qué tests nuevos o modificados lo verifican?
4. ¿Afecta sync?
5. ¿Afecta migraciones?
6. ¿Afecta permisos?
7. ¿Afecta offline?
8. ¿Afecta accesibilidad?
9. ¿Afecta privacidad o logs?
10. ¿Afecta contratos públicos o plugins?
11. ¿Afecta performance?
12. ¿Existe rollback o recovery razonable?

## 57. Definition of Ready para implementación

Una historia o cambio está listo cuando:

- tiene criterio de aceptación
- dependencias conocidas
- severidad/riesgo aproximado
- impacto offline evaluado
- impacto de datos evaluado
- estrategia de prueba identificada
- decisiones arquitectónicas necesarias resueltas

## 58. Definition of Done de feature

Además de la DoD de ingeniería de Fase 5:

- tests apropiados verdes
- casos negativos cubiertos
- accessibility checks aplicables verdes
- logs/telemetría revisados
- docs actualizadas
- migraciones verificadas cuando existan
- offline/multi-device cubierto cuando aplique
- security/privacy revisado cuando aplique
- no flakes nuevos conocidos

## 59. Definition of Done de esta fase

La Fase 6 se considera consolidada cuando el repositorio futuro pueda derivar de este documento:

1. estructura de test suites
2. tags y categorías
3. matrices CI
4. fixtures
5. release gates
6. calidad por bounded context
7. escenarios offline
8. scenarios multi-device
9. migration tests
10. restore drills
11. security verification
12. accessibility verification
13. performance budgets
14. release qualification

## 60. Estructura objetivo de tests

```text
apps/web/
├── src/
├── tests/
│   ├── component/
│   ├── accessibility/
│   ├── offline/
│   └── fixtures/
└── e2e/
    ├── journeys/
    ├── sync/
    ├── multi-device/
    ├── accessibility/
    └── visual/

services/platform/
└── tests/
    ├── unit/
    ├── property/
    ├── integration/
    ├── contract/
    ├── concurrency/
    ├── migration/
    └── security/

quality/
├── chaos/
├── load/
├── restore/
├── compatibility/
├── release/
└── evidence/
```

## 61. Tags y selección de suites

Markers sugeridos:

```text
unit
property
integration
contract
e2e
offline
multi_device
chaos
security
accessibility
performance
migration
restore
plugin
slow
release
```

Un test puede pertenecer a múltiples categorías.

## 62. Orden de implementación de QA

### Q0 · Foundation

Configurar runners, factories, fixtures y reporting.

### Q1 · Domain invariants

State machines, ledger, permissions, totals e idempotencia.

### Q2 · Persistence

PostgreSQL, Alembic, IndexedDB y migrations.

### Q3 · Sync harness

Cliente A, cliente B, servidor y network fault injection.

### Q4 · Golden vertical slice

Customer → Bicycle → Service Order con offline/reconnect.

### Q5 · Browser/device matrix

Tier 1 automatizado y hardware smoke.

### Q6 · Cross cutting

Accesibilidad, seguridad, performance, backup/restore.

### Q7 · Release qualification

Pipeline candidato a V1 reproducible.

## 63. Harness de sincronización requerido

Se construirá un test harness específico capaz de:

- crear múltiples `device_id`
- congelar/avanzar clocks
- desconectar individualmente clientes
- inyectar timeouts
- duplicar requests
- reordenar respuestas cuando sea seguro simularlo
- reiniciar API/worker
- inspeccionar mutation queues
- inspeccionar cursor
- comparar estados convergentes

Este harness es infraestructura estratégica del proyecto y no un test helper descartable.

## 64. Autonomous technical decision policy aplicada a QA

Las decisiones de testing se cerrarán autónomamente cuando exista evidencia suficiente.

Reglas:

1. Se elige la herramienta más simple que cubra correctamente el riesgo.
2. No se duplica tooling sin beneficio medible.
3. Una nueva dependencia de testing debe justificar mantenimiento, velocidad y compatibilidad open source.
4. Los spikes se reservan para incertidumbre empírica real, por ejemplo límites de storage o comportamiento de navegador.
5. Los resultados se registran como ADR o QA decision record cuando afecten la arquitectura del proyecto.

## 65. Decisiones QA cerradas

| ID | Decisión | Estado |
|---|---|---|
| QA-ADR-001 | pytest como runner backend | Accepted |
| QA-ADR-002 | Hypothesis para property based testing | Accepted |
| QA-ADR-003 | Vitest para unit/component frontend | Accepted |
| QA-ADR-004 | Testing Library para UI behavior | Accepted |
| QA-ADR-005 | Playwright para E2E y multi-context | Accepted |
| QA-ADR-006 | axe-core para automatización de accesibilidad | Accepted |
| QA-ADR-007 | PostgreSQL real para integration tests | Accepted |
| QA-ADR-008 | Contenedores efímeros para dependencias de integración | Accepted |
| QA-ADR-009 | Sync harness dedicado | Accepted |
| QA-ADR-010 | Property tests obligatorios para ledger e idempotencia | Accepted |
| QA-ADR-011 | Restore drill como gate V1 | Accepted |
| QA-ADR-012 | No global coverage percentage como KPI principal | Accepted |
| QA-ADR-013 | Mutation testing selectivo | Accepted |
| QA-ADR-014 | Flaky tests tratados como defects | Accepted |
| QA-ADR-015 | Hardware Tier 1 pass antes de V1 | Accepted |
| QA-ADR-016 | WCAG 2.2 AA como release gate | Accepted |
| QA-ADR-017 | Security High/Critical dentro del threat model bloquea V1 | Accepted |
| QA-ADR-018 | Evidencia de release versionada por commit/artifact | Accepted |

## 66. Riesgos QA que permanecen para validación empírica

No se dejan como decisiones abiertas, sino como aspectos que deben medirse durante implementación:

### QRISK-QA-001 · Límites reales de IndexedDB

La cuota y eviction behavior varían por navegador y dispositivo. Se diseñará una prueba de capacidad sobre hardware Tier 1 y mecanismos de advertencia antes de aproximarse al límite.

### QRISK-QA-002 · Suspensión agresiva Android

Algunos fabricantes suspenden procesos/background de manera distinta. La app debe preservar queues y no depender de ejecución continua en background.

### QRISK-QA-003 · Calidad de cámaras y escaneo

QR/barcode scanning debe probarse con dispositivos reales y condiciones de iluminación diferentes.

### QRISK-QA-004 · Impresoras

La impresión varía ampliamente. Se mantendrá una matriz de dispositivos oficialmente validados sin prometer compatibilidad universal.

## 67. Criterios de salida hacia Fase 7

La Fase 7 de Deployment & Operations puede construirse sobre esta estrategia porque ya quedan especificados:

- smoke tests de despliegue
- observabilidad a verificar
- backups y restore drills
- upgrade rehearsal
- artifacts y SBOM
- SLOs preliminares
- release qualification
- recuperación ante desastre

La Fase 7 deberá convertir estos requisitos en procedimientos operativos concretos para Standalone, LAN y Cloud.

## 68. Resultado consolidado

Con esta fase, Open Cycling Workshop Platform deja de tratar QA como una etapa posterior. La arquitectura de calidad se convierte en parte del producto y del contrato open source.

El objetivo no es demostrar que “los tests pasan”, sino poder afirmar con evidencia reproducible que una release:

- conserva datos
- converge después de operar offline
- no duplica efectos críticos
- puede actualizarse
- puede restaurarse
- respeta permisos
- mantiene accesibilidad
- resiste fallas previsibles
- cumple sus contratos
- funciona sobre los dispositivos que declara soportar

Ese estándar será condición para considerar V1.0 una release de producción y no simplemente una milestone de desarrollo.
