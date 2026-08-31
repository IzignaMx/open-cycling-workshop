# Fase 7 · Deployment, Operations & Reliability Architecture v0.1

**Open Cycling Workshop Platform**  
Baseline: Foundation v0.2 · Functional Requirements v0.1 · Technical Architecture v0.2 · Security/Privacy v0.1 · UX/UI v0.1 · Repository & Engineering Architecture v0.1 · QA/Verification v0.1  
License baseline: `AGPL-3.0-only`

> Este documento define cómo instalar, operar, actualizar, respaldar, recuperar, observar y mantener la plataforma en condiciones reales. El objetivo no es solamente que el software pueda desplegarse, sino que un implementador independiente pueda sostenerlo profesionalmente durante años y recuperar el servicio de manera reproducible cuando falle infraestructura, conectividad, almacenamiento, una actualización o una integración.

## 1. Objetivo de la fase

La Fase 7 convierte la arquitectura y los gates de calidad previos en una arquitectura operativa concreta para tres topologías oficiales: Standalone, LAN y Cloud.

Los objetivos son:

1. Definir topologías de producción soportadas y sus límites.
2. Establecer una referencia de servidor reproducible y de bajo costo.
3. Determinar cómo se sirven PWA, API, jobs, PostgreSQL, archivos y plugins.
4. Formalizar configuración, secrets, TLS, DNS, redes y permisos de host.
5. Diseñar instalación, bootstrap, upgrades, rollbacks y migration rehearsals.
6. Establecer backups, PITR, restore drills y disaster recovery.
7. Definir observabilidad y diagnóstico sin convertir telemetría externa en requisito.
8. Definir health checks, alerting, SLOs y capacity planning.
9. Diseñar procedimientos de field support para talleres con personal no técnico.
10. Producir runbooks que puedan utilizar agencias, freelancers y equipos internos.
11. Mantener la operación esencial durante fallas de Internet y ventanas de mantenimiento del servidor.
12. Preservar portabilidad y control de datos en coherencia con `AGPL-3.0-only`.

## 2. Principios operativos no negociables

### OPS-P01 · Internet no es una dependencia del taller

La pérdida del ISP no puede impedir crear, consultar o modificar información esencial ya disponible localmente.

### OPS-P02 · El servidor es reemplazable

Ninguna instalación debe depender de conocimiento oculto, configuración manual no documentada o un proveedor cloud específico.

### OPS-P03 · Recuperación antes que alta disponibilidad artificial

Para el mercado objetivo inicial se prioriza recuperación demostrable, backups verificables y operación offline sobre clusters complejos de alta disponibilidad.

### OPS-P04 · Infraestructura mínima suficiente

No se introduce Kubernetes, service mesh, Kafka, Redis obligatorio ni otros componentes distribuidos hasta que una necesidad medida lo justifique.

### OPS-P05 · Secure by default

PostgreSQL, métricas, backups y servicios internos no se exponen públicamente.

### OPS-P06 · Upgrade seguro y reversible dentro de una ventana definida

Toda actualización debe tener preflight, backup, migración validada, health checks, smoke tests y estrategia explícita de recuperación.

### OPS-P07 · La evidencia operativa forma parte de la release

Backup status, migration status, checksums, image digests, versión, schema versions y restore evidence deben poder identificarse.

### OPS-P08 · Telemetría opcional

La plataforma puede operar sin enviar métricas a terceros. Observabilidad remota se habilita mediante configuración explícita.

### OPS-P09 · Datos antes que disponibilidad cosmética

Ante falta crítica de espacio o corrupción sospechada, el sistema puede degradar funciones antes de arriesgar integridad.

### OPS-P10 · Documentación ejecutable

Todo procedimiento importante debe tener comandos reproducibles o una implementación en `ocwpctl`.

## 3. Decisiones operativas cerradas

| ID          | Decisión                                                           | Estado   | Motivo                                                                |
| ----------- | ------------------------------------------------------------------ | -------- | --------------------------------------------------------------------- |
| OPS-ADR-001 | Debian 13 stable como host Linux de referencia                     | Accepted | Estabilidad, soporte prolongado, amd64 y arm64                        |
| OPS-ADR-002 | Docker Engine + Docker Compose para servidor V1                    | Accepted | Portabilidad y baja complejidad operacional                           |
| OPS-ADR-003 | Caddy como edge, static server y reverse proxy oficial             | Accepted | TLS automático, configuración compacta y reverse proxy robusto        |
| OPS-ADR-004 | Sólo 80/443 públicos para aplicación                               | Accepted | Superficie de ataque mínima                                           |
| OPS-ADR-005 | PostgreSQL nunca expuesto a Internet                               | Accepted | Data plane interno                                                    |
| OPS-ADR-006 | Contenedores de aplicación ejecutan como usuario no root           | Accepted | Menor impacto de compromiso                                           |
| OPS-ADR-007 | Docker Compose secrets para secrets locales de producción          | Accepted | Acceso granular y menor exposición que env vars ordinarias            |
| OPS-ADR-008 | Configuración no secreta en TOML versionable por instalación       | Accepted | Legibilidad y validación estructurada                                 |
| OPS-ADR-009 | Caddy automatic HTTPS en Cloud                                     | Accepted | Reduce errores manuales de certificados                               |
| OPS-ADR-010 | Split DNS + certificado público o CA interna administrada para LAN | Accepted | PWA requiere secure context estable                                   |
| OPS-ADR-011 | Docker image digests como identidad de despliegue                  | Accepted | Reproducibilidad y rollback verificable                               |
| OPS-ADR-012 | OCI images para `linux/amd64` y `linux/arm64`                      | Accepted | VPS, mini PC y ARM compatibles                                        |
| OPS-ADR-013 | Baseline backup = pg_dump + restic cifrado                         | Accepted | Sencillo, portable y suficiente para microinstalaciones               |
| OPS-ADR-014 | Reliability tier = pgBackRest + WAL/PITR + offsite repo            | Accepted | RPO reducido y recuperación temporal                                  |
| OPS-ADR-015 | Restore drills obligatorios                                        | Accepted | Un backup no probado no cuenta como recuperable                       |
| OPS-ADR-016 | Logs estructurados JSON a stdout                                   | Accepted | Container native y vendor neutral                                     |
| OPS-ADR-017 | OpenTelemetry hooks + Prometheus compatible metrics                | Accepted | Observabilidad portable y desacoplada                                 |
| OPS-ADR-018 | Observability stack como profile opcional                          | Accepted | No penaliza microtalleres                                             |
| OPS-ADR-019 | `ocwpctl` como interfaz operacional canónica                       | Accepted | Reduce procedimientos manuales divergentes                            |
| OPS-ADR-020 | Actualización controlada, no auto update del Core                  | Accepted | Evita migraciones no supervisadas                                     |
| OPS-ADR-021 | Security updates del host automatizables, reboot controlado        | Accepted | Seguridad sin interrupciones sorpresivas                              |
| OPS-ADR-022 | Trunk release artifacts firmados y con SBOM                        | Accepted | Supply chain verificable                                              |
| OPS-ADR-023 | LAN recomendado para operación multiusuario sin WAN                | Accepted | Resiliencia del taller ante ISP                                       |
| OPS-ADR-024 | Cloud recomendado para multisucursal                               | Accepted | Autoridad compartida y acceso remoto                                  |
| OPS-ADR-025 | Standalone no se considera sustituto de backup externo             | Accepted | IndexedDB puede depender de políticas de almacenamiento del navegador |

## 4. Topologías oficiales

```text
Standalone
──────────
Windows / Android device
PWA + IndexedDB + local blobs
       │
       └── encrypted export backup

LAN
───
Tablet ─┐
PC ─────┼── HTTPS LAN ── Caddy ─ API ─ PostgreSQL
Phone ──┘                         ├─ Worker
                                 └─ Blob store
                     Internet optional for external integrations

Cloud
─────
Devices
   │
Internet
   │
Caddy / HTTPS
   │
API + Worker + PostgreSQL + Blob provider
   │
Encrypted offsite backup / PITR
```

Las tres topologías comparten dominio, API contracts, export formats y mecanismos de migración. No son productos separados.

## 5. Topología Standalone

Standalone es el modo de entrada más pequeño. Está pensado para un solo dispositivo principal o una operación extremadamente pequeña.

### 5.1 Componentes

- PWA instalada
- Service Worker
- Dexie + IndexedDB
- local mutation log
- local blobs
- local users cuando se habiliten cuentas múltiples
- export/import cifrado
- diagnostics de storage y schema

### 5.2 Capacidades offline

Las operaciones Core de clientes, bicicletas, órdenes, inventario, POS local, notas y documentos generables localmente permanecen disponibles.

Integraciones externas se convierten en acciones pendientes cuando no existe conectividad.

### 5.3 Persistencia del navegador

La aplicación solicitará persistent storage cuando el navegador lo soporte.

El panel de diagnóstico mostrará:

```text
Storage persistence       granted / not granted
Local database size       1.2 GB
Pending mutations         14
Last export backup        2026-08-06 20:30
Backup age                2h 41m
Local schema              7
App version               1.0.2
```

Si el navegador no concede persistencia, el sistema mostrará una advertencia visible y recomendará LAN Mode para uso operacional prolongado.

### 5.4 Recomendación comercial

Standalone es apropiado para:

- demostraciones
- microtaller de una persona
- operación temporal
- intake móvil
- taller itinerante

Para un negocio con más de un dispositivo o dependencia diaria fuerte, LAN es el deployment recomendado.

## 6. Backup Standalone

Se define un formato de aplicación versionado:

```text
workshop-2026-08-06T203000.ocwp-backup
```

El archive contiene:

```text
manifest.json
schema.json
records/
mutations/
blobs/
checksums.json
metadata.json
```

### 6.1 Propiedades

1. El backup se genera desde el modelo de aplicación, no copiando internals de IndexedDB.
2. Debe incluir mutaciones aún no sincronizadas.
3. Debe incluir checksum por objeto.
4. Debe incluir versión del formato.
5. Debe poder validarse antes de importarse.
6. Debe poder migrarse desde formatos soportados.
7. La exportación de datos personales será cifrada por defecto.
8. El passphrase nunca se almacena dentro del archive.

### 6.2 Política UI

Si no existe un backup reciente, el dashboard puede mostrar:

```text
Backup recomendado
Han pasado 8 días desde la última copia externa.
[Crear backup ahora]
```

La advertencia nunca bloquea operación ordinaria, salvo que una política administrada lo configure.

## 7. Topología LAN

LAN es la topología recomendada para la mayoría de talleres físicos con múltiples trabajadores.

### 7.1 Objetivo

Permitir que recepción, mecánicos, ventas y administración continúen trabajando aunque el proveedor de Internet falle por horas o días.

### 7.2 Hardware de referencia

Servidor local recomendado:

```text
Architecture      amd64 or arm64
CPU               2 to 4 modern cores baseline
RAM               4 GB minimum, 8 GB recommended
System disk       SSD
Usable storage    sized for photos, documents and backups
Network           wired Ethernet preferred
UPS               strongly recommended
```

Las cifras son sizing inicial y deberán validarse con el load profile del cliente.

### 7.3 Conectividad

Los dispositivos acceden al servidor mediante HTTPS dentro de la LAN.

```text
client device
   ↓
shop DNS
   ↓
192.168.x.x
   ↓
Caddy
```

El tráfico operativo interno no sale a Internet.

### 7.4 WAN failure

Cuando el ISP falla:

- el frontend sigue sirviéndose localmente
- API sigue disponible
- PostgreSQL sigue disponible internamente
- impresión local continúa
- órdenes y POS continúan
- WhatsApp, email cloud y pagos dependientes de Internet quedan pendientes
- el UI refleja las integraciones pendientes sin ocultar el estado

## 8. TLS y DNS LAN

Un Service Worker completo requiere secure context. Por ello LAN no se diseñará alrededor de HTTP plano por IP.

### 8.1 Método preferido · Public trust con split DNS

Ejemplo:

```text
workshop.example.com
```

DNS interno resuelve a la IP LAN.

El certificado se obtiene mediante ACME y DNS challenge cuando el dominio lo permita.

Ventajas:

- confianza nativa en tablets y Windows
- PWA normal
- no requiere distribuir una CA manualmente

### 8.2 Método administrado · Internal CA

Cuando no existe dominio apropiado, Caddy puede operar con una CA interna.

El certificado root se instala explícitamente en los dispositivos administrados.

Este modo sólo se recomienda cuando el implementador controla los dispositivos.

### 8.3 Regla

No se instruirá al cliente a ignorar advertencias TLS ni a instalar certificados sin verificar fingerprint/origen.

## 9. Topología Cloud

Cloud es la topología preferida para:

- acceso remoto
- múltiples ubicaciones
- home office administrativo
- implementaciones gestionadas
- integraciones públicas
- customer portal desde Internet

### 9.1 Host de referencia

Debian 13 stable.

Arquitecturas oficiales de imagen:

```text
linux/amd64
linux/arm64
```

### 9.2 Server layout

```text
Internet
   │
80 / 443
   │
Caddy
   ├── static PWA
   └── /api → FastAPI
             ├── PostgreSQL
             ├── Worker
             ├── Blob provider
             └── Integrations
```

## 10. Docker Compose deployment model

Docker Compose es el runtime oficial V1 para LAN y Cloud de un solo servidor.

Servicios Core:

```yaml
services:
  edge:
    image: ghcr.io/.../web@sha256:...

  api:
    image: ghcr.io/.../api@sha256:...

  worker:
    image: ghcr.io/.../api@sha256:...

  db:
    image: postgres:...
```

Servicios opcionales pueden habilitarse con profiles:

```text
backup
observability
mail-dev
maintenance
```

## 11. Red de contenedores

Se definen redes lógicas separadas:

```text
edge_net
app_net
data_net
```

### 11.1 Reglas

- `edge` puede alcanzar `api`
- `api` puede alcanzar `db`
- `worker` puede alcanzar `db`
- `db` no se une a `edge_net`
- `db` no publica puerto al host por defecto
- observability sólo recibe acceso explícito a endpoints necesarios

El objetivo es reducir lateral movement accidental y hacer explícitos los boundaries.

## 12. Hardening de contenedores

Los contenedores oficiales deberán:

- ejecutar procesos como usuario no root
- utilizar filesystem read only donde sea compatible
- declarar writable mounts explícitos
- `cap_drop: [ALL]` por defecto
- añadir capabilities sólo cuando exista necesidad documentada
- no utilizar `privileged: true`
- definir healthcheck
- definir límites razonables de recursos cuando el deployment profile lo requiera
- no incluir herramientas de desarrollo innecesarias en imágenes de producción
- usar multi stage builds

## 13. Caddy como Edge oficial

Caddy sirve:

1. PWA estática
2. TLS
3. redirects HTTP → HTTPS
4. reverse proxy a FastAPI
5. compression cuando corresponda
6. security headers definidos por configuración
7. request ID forwarding
8. access logging redacted

### 13.1 Cloud

El hostname público activa automatic HTTPS.

### 13.2 LAN

Caddy opera mediante public trust con split DNS o internal CA administrada.

### 13.3 No se permite

- `tls_insecure_skip_verify` como solución ordinaria
- exposición directa de Uvicorn a Internet
- certificados compartidos por email o chat sin canal seguro

## 14. Static PWA delivery

La imagen `web` contiene assets compilados e inmutables.

Las rutas versionadas usan nombres content hashed.

`index.html` y service worker reciben cache policy compatible con actualización segura.

### 14.1 Service Worker update policy

Una actualización disponible no fuerza reload si existen mutaciones pendientes.

Flujo:

```text
New app version detected
        ↓
Pending mutations?
  ├─ yes → continue old client + warning
  └─ no  → offer/apply safe reload
```

No se utilizará un mecanismo que reemplace el cliente en mitad de una orden o cobro.

## 15. API runtime

FastAPI se sirve mediante Uvicorn en la imagen oficial.

### 15.1 Worker model

El número de workers se configura por deployment size.

No se maximiza por CPU automáticamente sin considerar el pool de PostgreSQL.

### 15.2 Timeouts

Endpoints interactivos tendrán timeouts acotados.

Operaciones largas se convierten en jobs o procesos asíncronos auditables.

Uploads grandes utilizan streaming y límites explícitos.

## 16. PostgreSQL operativo

PostgreSQL es authoritative store para LAN y Cloud.

### 16.1 Reglas

- no public port
- password aleatorio fuerte
- usuario de aplicación sin privilegios de superuser
- usuario de migration separado cuando sea necesario
- backups usan credenciales dedicadas
- timezone del servidor almacenada en UTC
- encoding UTF-8
- conexiones cifradas cuando PostgreSQL atraviese hosts

### 16.2 Schema compatibility

El API no entra en ready state si detecta una versión de schema incompatible con su release.

## 17. Blob storage

Se soportan dos estrategias oficiales.

### 17.1 Filesystem provider

Preferido para LAN y micro Cloud.

```text
/var/lib/ocwp/blobs/
```

### 17.2 S3 compatible provider

Preferido cuando:

- el volumen de imágenes crece
- hay múltiples ubicaciones
- el proveedor ofrece versioning
- se desea separar compute y media

### 17.3 Regla de consistencia

La DB almacena metadata y object IDs, no paths arbitrarios del host.

Los blobs se validan mediante hashes.

Un proceso de reconciliation detecta:

- metadata sin blob
- blob sin metadata
- hash inconsistente

## 18. Filesystem layout del host

Referencia:

```text
/opt/ocwp/
├── compose.yaml
├── compose.production.yaml
├── Caddyfile
├── VERSION
└── bin/

/etc/ocwp/
├── config.toml
└── secrets/

/var/lib/ocwp/
├── postgres/
├── blobs/
├── backups/
└── diagnostics/

/var/log/ocwp/
└── optional exported logs
```

Docker volumes pueden abstraer paths internos, pero los procedimientos oficiales mantienen una ubicación operacional conocida.

## 19. Configuration architecture

La configuración se divide en tres niveles.

### 19.1 Application defaults

Versionados con la release.

### 19.2 Installation config

`/etc/ocwp/config.toml`

Ejemplo conceptual:

```toml
[instance]
name = "Taller Ejemplo"
timezone = "America/Mexico_City"
locale = "es-MX"

[features]
pos = true
inventory = true
rentals = false

[storage]
provider = "filesystem"

[telemetry]
enabled = false
```

### 19.3 Environment overrides

Se reservan para deployment automation y casos donde el host necesita sobreescribir un valor sin editar TOML.

No se utilizará una `.env` gigante como fuente de verdad de producción.

## 20. Secrets architecture

Secrets mínimos:

- PostgreSQL application password
- PostgreSQL backup credentials
- session signing secret
- encryption keys
- SMTP credentials
- WhatsApp credentials
- payment provider secrets
- backup repository credentials

### 20.1 Compose secrets

Los secrets se montan sólo en los servicios que los requieren.

```text
/run/secrets/db_password
/run/secrets/session_key
```

### 20.2 Host permissions

```text
root:root
0600
```

### 20.3 Rotation

`ocwpctl secrets rotate` soportará rotación planificada por tipo de secret.

No todos los secrets pueden rotarse sin coordinación. El comando debe conocer la estrategia correspondiente.

## 21. Host operating system baseline

Debian 13 stable es la referencia de producción V1.

### 21.1 Host mínimo

- current security updates
- Docker Engine
- Docker Compose plugin
- nftables
- system time sync
- SSH server sólo cuando sea necesario
- restic para baseline backup cuando se ejecute desde host
- herramientas de diagnóstico mínimas

### 21.2 SSH hardening

- public key authentication
- password authentication disabled para servidores administrados
- root login disabled
- acceso limitado por firewall o VPN cuando sea posible
- logs de autenticación conservados según política

### 21.3 Remote administration

Para instalaciones privadas se prefiere WireGuard o acceso equivalente de red privada antes que exponer SSH globalmente.

## 22. Host patching

El host recibe actualizaciones de seguridad de Debian regularmente.

### 22.1 Política

- security patches pueden automatizarse
- reinicios no se realizan arbitrariamente durante horario de taller
- kernel reboot pendiente se muestra en diagnostics
- actualización mayor de Debian requiere rehearsal separado
- Docker Engine updates se realizan dentro de maintenance window

## 23. Firewall baseline

Cloud:

```text
Inbound
80/tcp     HTTP redirect / ACME
443/tcp    HTTPS
SSH        private admin path only

Denied
5432       PostgreSQL
metrics    internal
backup     internal
```

LAN:

- aplicación accesible sólo desde subredes autorizadas
- administración preferentemente desde management VLAN o dispositivo de confianza

## 24. Time, clocks and ordering

Todos los hosts usan time synchronization.

La base almacena timestamps UTC.

El UI presenta timezone de la organización.

Los domain events no dependen exclusivamente del reloj del cliente para orden autoritativo.

UUIDv7 ayuda a ordenamiento aproximado, pero server sequence/cursor continúa siendo autoridad de sync.

## 25. `ocwpctl` · Operational CLI

`ocwpctl` es el command surface oficial para implementación y soporte.

Comandos objetivo:

```text
ocwpctl doctor
ocwpctl status
ocwpctl config validate
ocwpctl bootstrap admin
ocwpctl migrate status
ocwpctl backup create
ocwpctl backup verify
ocwpctl restore plan
ocwpctl restore execute
ocwpctl upgrade plan
ocwpctl upgrade apply
ocwpctl diagnostics collect
ocwpctl queues inspect
ocwpctl sync inspect
ocwpctl secrets rotate
ocwpctl plugins doctor
ocwpctl version
```

En servidor puede ejecutarse mediante una imagen CLI oficial para no requerir Python instalado en el host.

## 26. Preflight de instalación

`ocwpctl doctor --preflight` valida:

- OS y arquitectura
- Docker Engine
- Compose
- memoria
- espacio libre
- filesystem
- DNS
- puertos
- reloj
- HTTPS prerequisites
- permissions
- backup target
- secrets presence
- conflictos de container names

Una instalación no debe continuar silenciosamente si falla un preflight crítico.

## 27. Installation workflow

Flujo oficial LAN/Cloud:

```text
1. Provision host
2. Apply OS updates
3. Configure DNS/firewall
4. Install Docker
5. Download signed deployment bundle
6. Verify checksum/signature
7. Generate config
8. Generate secrets
9. Validate Compose model
10. Pull immutable images
11. Start PostgreSQL
12. Apply migrations
13. Start API + worker + edge
14. Run readiness checks
15. Bootstrap first administrator
16. Configure backup
17. Execute first backup
18. Execute restore validation where practical
19. Record installation manifest
20. Handover
```

## 28. Installation manifest

Cada instalación conserva:

```json
{
  "instance_id": "...",
  "installed_at": "...",
  "release": "1.0.0",
  "git_sha": "...",
  "image_digests": {},
  "schema_version": "...",
  "deployment_mode": "lan",
  "host_os": "Debian 13",
  "backup_policy": "baseline",
  "enabled_plugins": []
}
```

No contiene secrets.

## 29. Release artifacts

Cada release estable publica:

- OCI image digests
- SBOM
- checksums
- signatures
- deployment bundle
- migration notes
- upgrade notes
- known issues
- compatibility window
- plugin SDK version

La instalación no se basa en `latest`.

## 30. Release channels

### stable

Único canal recomendado a clientes ordinarios.

### candidate

Para staging, implementadores y early validation.

### development

No recibe garantías de migración ni soporte de datos reales.

Una instalación de producción no sigue `main` directamente.

## 31. Upgrade principles

### OPS-UPG-01

El cliente puede continuar realizando trabajo local durante una ventana razonable de mantenimiento del servidor.

### OPS-UPG-02

Toda actualización servidor ejecuta backup pre upgrade salvo que el operador presente una excepción documentada.

### OPS-UPG-03

Migraciones expand/contract deben preservar compatibilidad con clientes soportados.

### OPS-UPG-04

No se hace auto update silencioso de API, DB o worker.

### OPS-UPG-05

El service worker no fuerza reload destructivo.

## 32. Upgrade workflow

```text
ocwpctl upgrade plan 1.1.0
        ↓
compatibility checks
        ↓
backup + verification
        ↓
pull images by digest
        ↓
expand migrations
        ↓
start new API/worker
        ↓
readiness + smoke
        ↓
client compatibility observation
        ↓
contract migrations later
```

### 32.1 Pre upgrade checks

- current version supported
- no unresolved migration failure
- enough disk for old + new images
- backup repository healthy
- no C0/C1 local diagnostics
- pending plugin migration compatibility
- database backup age acceptable

## 33. Maintenance mode

El mantenimiento del servidor no debe confundirse con cierre del taller.

Durante maintenance:

```text
PWA local operations        available
Existing cached data        available
New local mutations         queued
Public customer portal      maintenance response if backend unavailable
External integrations       delayed
Sync                         resumes after server return
```

El UI muestra:

> Servidor en mantenimiento. Puedes seguir trabajando. Los cambios se sincronizarán al restablecerse el servicio.

## 34. Rollback strategy

Rollback se divide en dos tipos.

### 34.1 Application rollback

Permitido si el schema permanece dentro de la compatibility window.

Se vuelve a image digests anteriores.

### 34.2 Data rollback

No se realiza automáticamente.

Si una migration contract o corrupción requiere revertir datos, se activa recovery plan mediante backup/PITR o forward fix.

### 34.3 Regla

Nunca ejecutar `down migration` destructiva automáticamente sólo para hacer coincidir una imagen antigua.

## 35. Database migration operations

Cada release clasifica migraciones:

```text
expand
backfill
contract
maintenance-only
```

### 35.1 Backfill

Backfills grandes se ejecutan como jobs resumibles, no como una transacción de startup indefinida.

### 35.2 Lock budget

Migraciones que puedan bloquear tablas operativas requieren ensayo con dataset `load` y una estimación de lock time.

## 36. Client schema migration operations

IndexedDB migrations ocurren en cliente.

### 36.1 Reglas

- no borrar pending mutations sin migrarlas
- migration failure deja app en recovery screen, no en estado parcialmente usable
- backup/export de emergencia debe estar disponible cuando técnicamente sea seguro
- local schema version aparece en diagnostics

## 37. Backup strategy overview

Se definen tres niveles.

| Tier        | Uso                     | PostgreSQL            | Blobs/config                    | RPO objetivo inicial               |
| ----------- | ----------------------- | --------------------- | ------------------------------- | ---------------------------------- |
| Standalone  | Un dispositivo          | app export            | app export                      | depende de frecuencia del operador |
| Baseline    | Micro/LAN/Cloud pequeño | pg_dump custom diario | restic cifrado                  | ≤ 24 h                             |
| Reliability | Managed / multisucursal | pgBackRest + WAL/PITR | restic/versioned object storage | ≤ 15 min DB, blobs según policy    |

Los objetivos se convierten en SLA sólo cuando el implementador los contrata y opera.

## 38. Baseline backup

### 38.1 PostgreSQL

Se crea `pg_dump` en custom format.

El dump se valida estructuralmente y se incluye dentro del snapshot cifrado.

### 38.2 Blobs

Restic captura blobs, config no secreta, manifests y dumps.

### 38.3 Secrets

Los secrets no se copian automáticamente al mismo repositorio sin una política explícita.

El recovery kit de secrets se administra por separado y cifrado.

### 38.4 Retention baseline

Referencia inicial:

```text
Daily       7
Weekly      5
Monthly     12
```

El cliente puede requerir política diferente por regulación o volumen.

## 39. Restic repository policy

Restic se utiliza porque cifra repositories y soporta múltiples backends.

Requisitos:

- contraseña fuerte o key material administrado
- copia de recovery key fuera del host
- repository fuera del mismo disco primario para producción
- `restic check` programado
- políticas de forget/prune controladas
- alertar ante backup fallido

### 39.1 3-2-1

Para managed deployments se buscará:

```text
3 copies
2 media / failure domains
1 offsite
```

No se considerará un segundo directorio del mismo SSD como segundo failure domain.

## 40. Reliability backup con PITR

Para clientes que requieren menor RPO se habilita pgBackRest con WAL archiving.

### 40.1 Referencia

```text
Full backup          weekly
Differential backup  daily
WAL archive          continuous
Repository           offsite or separate failure domain
```

La frecuencia concreta se ajusta por write rate y SLO.

### 40.2 Objetivo

Poder restaurar el cluster a un punto anterior a una corrupción lógica o error humano dentro de la retention window.

### 40.3 No dependencia única

El formato de exportación funcional de la aplicación se mantiene aunque exista PITR para evitar que una única tecnología de backup sea la única vía de portabilidad.

## 41. Backup scheduling

Los jobs de backup deben tener:

- lock para evitar ejecuciones solapadas
- timeout razonable
- logs estructurados
- exit status
- métricas
- alerting de fallo
- duración
- tamaño
- timestamp del último éxito

El dashboard administrativo debe poder mostrar sólo metadata no sensible del estado de backup.

## 42. Restore drill

El procedimiento operacional implementa la exigencia de Fase 6.

```text
Known dataset
   ↓
Backup
   ↓
Clean target
   ↓
Restore
   ↓
Start stack
   ↓
Migrations if documented
   ↓
Smoke suite
   ↓
Invariant comparison
   ↓
Evidence bundle
```

### 42.1 Frecuencia recomendada

- Baseline managed: trimestral
- Reliability managed: mensual o por release mayor
- V1 release candidate: obligatorio

## 43. Recovery evidence

Cada drill conserva:

```text
backup ID
backup timestamp
restore start
restore finish
RTO measured
recovery point
release version
schema version
smoke result
invariant result
operator
notes
```

Esto permite vender soporte con evidencia real en lugar de promesas vagas.

## 44. Recovery Time Objective

Valores iniciales de producto, a validar con hardware real:

| Deployment          | RTO objetivo operacional     |
| ------------------- | ---------------------------- |
| Standalone import   | ≤ 60 min para dataset típico |
| LAN Baseline        | ≤ 4 h                        |
| Cloud Baseline      | ≤ 4 h                        |
| Managed Reliability | ≤ 2 h                        |

Un SLA contractual puede ser más estricto sólo si existe infraestructura, personal y pruebas que lo respalden.

## 45. Disaster recovery scenarios

Runbooks obligatorios:

1. host perdido
2. SSD fallido
3. PostgreSQL no inicia
4. DB corruption sospechada
5. logical corruption posterior a una release
6. blobs perdidos con DB intacta
7. DB restaurada con blobs incompletos
8. ransomware o host comprometido
9. secret expuesto
10. DNS incorrecto
11. TLS renewal failure
12. disk full
13. worker queue bloqueada
14. plugin defectuoso
15. provider externo fuera de servicio
16. restauración a hardware nuevo
17. clientes offline con mutaciones posteriores al último backup

## 46. Orphaned client recovery

Los dispositivos offline pueden contener trabajo más nuevo que el último backup del servidor.

No se tratan como backup autoritativo, pero sí como fuente potencial de mutaciones legítimas.

### 46.1 Flujo

```text
Server lost
   ↓
Restore server to last valid point
   ↓
Freeze automatic sync temporarily
   ↓
Export pending client mutations
   ↓
Validate IDs / tenant / causal metadata
   ↓
Replay through normal idempotent sync API
   ↓
Resolve conflicts explicitly
```

Nunca se copia IndexedDB directamente dentro de PostgreSQL.

## 47. Disk exhaustion strategy

Thresholds iniciales:

```text
< 70%      normal
70-84%     warning
85-89%     critical
≥ 90%      emergency degradation
```

### 47.1 Emergency degradation

El servidor puede:

- rechazar nuevos blobs grandes
- mantener operaciones de texto cuando PostgreSQL tiene espacio seguro
- detener jobs no esenciales
- alertar operador
- preservar logs mínimos

No debe llenar el disco intentando escribir logs de la propia falla.

## 48. Health checks

Se definen tres niveles.

### `/health/live`

Confirma que el proceso puede atender.

No depende de proveedores externos.

### `/health/ready`

Valida:

- schema compatible
- PostgreSQL reachable
- configuración válida
- migrations completas
- required storage accessible

### `/health/diagnostics`

Requiere capability administrativa y devuelve información ampliada no secreta.

Ejemplo:

```json
{
  "version": "1.0.0",
  "db": "ok",
  "schema": 42,
  "queue_depth": 18,
  "blob_store": "ok",
  "last_backup": "2026-08-06T02:00:00Z"
}
```

## 49. Dependency health

Integraciones externas no vuelven `ready=false` al Core salvo que estén declaradas como required por la instalación.

Ejemplo:

WhatsApp caído:

```text
Core         healthy
WhatsApp     degraded
Messages     queued
```

Esto implementa graceful degradation real.

## 50. Structured logging

Formato JSON.

Campos comunes:

```text
timestamp
level
service
version
request_id
correlation_id
organization_id
actor_id_hash when appropriate
event
outcome
duration_ms
```

### 50.1 Redaction

No se registran por defecto:

- message bodies
- passwords
- session tokens
- payment secrets
- full authorization payloads
- documentos personales

## 51. Log retention

Baseline local conserva logs por rotación con límite de tamaño y tiempo.

Managed puede exportar a un backend externo.

La retención se adapta a privacidad y soporte.

Logs de auditoría de negocio siguen una política separada a logs técnicos.

## 52. Metrics

Métricas iniciales:

### HTTP

- requests
- latency
- errors
- active requests

### Database

- pool usage
- query latency agregada
- connections
- transaction failures

### Sync

- pending mutations
- push rate
- pull rate
- conflicts
- last successful sync
- cursor lag

### Worker

- queue depth
- oldest job age
- retries
- dead jobs

### Backup

- last success age
- duration
- size
- restore drill status

### Storage

- DB size
- blob size
- disk utilization

No se incluyen datos personales en labels de métricas.

## 53. OpenTelemetry

El Core instrumenta boundaries mediante OpenTelemetry compatible APIs.

La exportación está deshabilitada si no existe collector configurado.

Esto permite conectar:

- self hosted collector
- Prometheus compatible metrics
- tracing backend
- proveedor comercial

sin modificar dominio.

## 54. Observability profile

Un profile opcional puede incluir:

```text
Prometheus
Grafana
Loki or compatible log backend
OpenTelemetry Collector
```

No forma parte de los requisitos mínimos de microtaller.

Para managed services, puede ejecutarse fuera del host del cliente para evitar consumir recursos locales.

## 55. Alerting

Alertas prioritarias:

### Critical

- backup vencido más allá del policy threshold
- restore verification failure
- PostgreSQL unavailable
- disk emergency
- migration failure
- repeated data integrity invariant failure

### High

- queue age excesiva
- no WAL archive cuando PITR está habilitado
- blob provider unavailable
- certificate near expiry sin renovación
- repeated 5xx rate

### Warning

- storage trend
- pending OS reboot
- plugin degradation
- sync lag creciente

## 56. Alert delivery

Alerting es modular.

Adapters posibles:

- email
- webhook
- Matrix
- Slack
- Telegram
- provider monitoring

El Core no depende de ninguno.

## 57. SLO model

El proyecto define SLOs de referencia, no un SLA contractual universal.

### 57.1 Connected Core availability

Objetivo baseline managed:

```text
99.5% monthly
```

Reliability tier puede aspirar a:

```text
99.9% monthly
```

Sólo después de medir infraestructura real.

### 57.2 Offline continuity

La pérdida de WAN no debe detener journeys Core que ya tienen datos y assets requeridos localmente.

### 57.3 Backup freshness

No debe existir un backup baseline exitoso con edad mayor al threshold configurado sin alerta.

### 57.4 Sync recovery

Después de recuperar conectividad, operaciones pendientes deben progresar sin intervención manual salvo conflicto real o error de negocio.

## 58. Error budget

Managed deployments pueden usar error budget para decidir si una ventana se dedica a features o hardening.

Ejemplo:

Si el SLO de 99.5% se consume tempranamente, cambios de riesgo alto pueden pausarse hasta recuperar estabilidad.

No se usará error budget para justificar pérdida de datos o defectos de seguridad.

## 59. Capacity planning

El sizing se basa en:

```text
concurrent users
API request rate
work orders per day
inventory movements per day
photos per order
average photo size
retention years
sync devices
plugin load
```

### 59.1 Storage formula

Estimación simple:

```text
annual_blob_storage =
orders_per_day × photos_per_order × avg_photo_size × open_days
```

Añadir factor de crecimiento, thumbnails, documentos y margen operativo.

### 59.2 DB growth

El ledger y audit history son append oriented. Su crecimiento debe monitorizarse desde el inicio.

## 60. Initial sizing tiers

Cifras preliminares que deberán validarse con benchmarks de Fase 6:

| Tier           | Usuarios concurrentes | Host inicial orientativo                          |
| -------------- | --------------------: | ------------------------------------------------- |
| Micro          |                   1-5 | 2 vCPU · 4 GB RAM                                 |
| Standard       |                  5-20 | 4 vCPU · 8 GB RAM                                 |
| Multi-location |                   20+ | 8 vCPU · 16 GB RAM + storage separado recomendado |

El almacenamiento no se deriva de esta tabla porque las fotografías dominan el consumo y varían mucho entre talleres.

## 61. Database connection sizing

`pool_size × worker_count` no puede exceder de manera arbitraria la capacidad de PostgreSQL.

El deployment tool calculará una configuración conservadora y permitirá override explícito.

Se prioriza baja latencia estable antes que cientos de conexiones ociosas.

## 62. Job queue operations

El worker usa la cola durable sobre PostgreSQL definida previamente.

Diagnostics debe mostrar:

- queue depth
- oldest pending age
- retry counts
- poison/dead jobs
- throughput

### 62.1 Queue incident

Si un provider externo falla, jobs relacionados reintentan con backoff y jitter.

No deben bloquear jobs internos independientes.

## 63. External provider resilience

Cada adapter declara:

```text
required? false
retry policy
rate limit policy
circuit breaker policy
idempotency behavior
health status
```

Un outage de Meta, email o payment provider no derriba el Core.

## 64. Customer Portal operations

En Cloud el portal público depende del server.

En LAN sin exposición pública, puede deshabilitarse o publicarse mediante un endpoint cloud específico.

El portal nunca abre PostgreSQL ni storage interno directamente.

Maintenance response debe ser accesible y no filtrar detalles técnicos.

## 65. Backpressure

Ante sobrecarga:

- rate limit endpoints sensibles
- queue jobs asíncronos
- limitar concurrent uploads
- rechazar trabajo no esencial antes que agotar DB
- conservar journeys críticos

Los límites se exponen como configuración por deployment size.

## 66. Graceful shutdown

API y worker deben responder a termination signals.

### API

- deja de aceptar nuevas conexiones
- completa requests cortos dentro del grace period
- cancela trabajo no seguro después del timeout

### Worker

- deja de claim jobs
- termina el job actual cuando sea seguro
- libera lease para retry si no termina

## 67. Startup ordering

Compose health checks garantizan readiness de dependencias.

No se confía sólo en `depends_on` como indicador de que PostgreSQL ya acepta conexiones.

El API también implementa retries bounded durante startup.

## 68. Plugin operations

Cada plugin tiene:

- version
- compatibility range
- migration status
- health
- last error
- permissions

### 68.1 Plugin failure

Un plugin opcional defectuoso debe poder deshabilitarse sin impedir el arranque del Core.

### 68.2 Upgrade

La compatibilidad de plugins se comprueba en `ocwpctl upgrade plan`.

## 69. Plugin isolation roadmap

V1 prioriza permisos y contract boundaries.

Fases posteriores podrán ejecutar conectores de alto riesgo en procesos o containers separados.

La arquitectura operational no asume que código comunitario arbitrario sea confiable dentro del Core.

## 70. Security incident operations

Runbook mínimo:

```text
Detect
 ↓
Contain
 ↓
Preserve evidence
 ↓
Rotate exposed secrets
 ↓
Assess data impact
 ↓
Patch / rebuild clean
 ↓
Restore if needed
 ↓
Validate
 ↓
Communicate according to obligations
 ↓
Postmortem
```

No se “limpia” un host comprometido y se vuelve a confiar en él sin evaluar rebuild.

## 71. Secret exposure runbook

Según secret:

- revoke provider token
- rotate local secret
- invalidate sessions
- rotate database password
- update Compose secret
- restart affected services
- verify no old credential remains
- review access logs

La secuencia se documenta por secret type.

## 72. Certificate incident

Si automatic HTTPS falla:

1. revisar DNS
2. revisar reachability 80/443 o DNS challenge
3. revisar ACME rate limits
4. revisar system time
5. revisar Caddy logs
6. mantener certificado anterior si aún es válido
7. no desactivar TLS verification para “resolver” el incidente

## 73. Disk full runbook

1. detener jobs no esenciales
2. verificar qué filesystem está lleno
3. preservar PostgreSQL free space
4. rotar/prune logs de forma segura
5. verificar backup repo no ubicado por error en root disk
6. ampliar storage o mover blobs
7. ejecutar integrity checks
8. reanudar gradual

No se borra WAL o data directory manualmente.

## 74. Database corruption runbook

1. declarar incident
2. detener writes cuando corresponda
3. preservar copia del estado afectado
4. validar si es filesystem, PostgreSQL o lógica
5. seleccionar restore point
6. restaurar a entorno limpio
7. aplicar smoke/invariants
8. reconciliar mutaciones de clientes offline
9. promover instancia recuperada

## 75. Blob loss runbook

Si DB está intacta y blobs faltan:

- congelar garbage collection
- restaurar snapshot/versioning
- ejecutar blob reconciliation
- listar objetos irrecuperables
- mantener metadata con estado `missing` en lugar de apuntar a archivo inexistente
- no inventar archivos vacíos

## 76. Queue backlog runbook

Diagnóstico:

```text
provider outage?
worker dead?
DB contention?
poison job?
rate limit?
configuration?
```

Acciones:

- aislar queue/provider
- escalar workers sólo si DB lo permite
- pausar tipo de job defectuoso
- requeue seguro
- mantener idempotency keys

## 77. Diagnostics bundle

`ocwpctl diagnostics collect` crea un bundle sanitizado.

Incluye:

- version manifest
- container status
- health endpoints
- non-secret config summary
- migration status
- recent structured errors redacted
- queue summary
- disk/memory summary
- backup age
- plugin health

No incluye:

- passwords
- API tokens
- message bodies
- customer datasets

El usuario revisa el contenido antes de compartirlo cuando sea viable.

## 78. Support tiers como capacidad comercial

La plataforma no impone precios, pero define capacidades operativas vendibles.

### Self managed

- software
- documentation
- community support

### Care

- update assistance
- backup monitoring
- periodic health review

### Managed

- hosting or LAN management
- backup + restore drills
- alerting
- updates
- incident support

### Reliability

- PITR
- offsite repositories
- tighter SLO
- scheduled DR rehearsal
- capacity review

Esto permite monetizar implementación y operación sin cerrar el código.

## 79. Handover package para cliente

Una implementación profesional entrega:

```text
instance summary
architecture diagram
URLs
administrator contacts
backup policy
restore responsibility
maintenance policy
support boundaries
version
enabled plugins
data export procedure
incident contact path
credential ownership statement
```

Las contraseñas no se colocan dentro del documento de handover ordinario.

## 80. Credential ownership

Por defecto el cliente debe poder recuperar control de:

- dominio
- DNS
- backup repository
- SMTP/provider accounts cuando sean suyos
- payment accounts
- WhatsApp Business account
- administrative application account

Un implementador no debe crear lock in accidental mediante cuentas personales imposibles de transferir.

## 81. Data portability operations

El administrador puede producir exportaciones funcionales versionadas.

El cliente no necesita mantener una suscripción con un implementador para poder obtener sus datos.

El restore/export path se mantiene documentado como parte del proyecto open source.

## 82. Multi-location operations

Cloud es la referencia para múltiples ubicaciones.

Cada location tendrá:

- location ID
- timezone si difiere
- inventory scope
- users/permissions
- device registrations
- sync visibility

LAN islands con sincronización federada quedan como fase posterior, no requisito de V1.

## 83. Offline during server outage

Este escenario se prueba como feature operacional.

```text
Server unavailable
   ↓
PWA enters local-only state
   ↓
New mutations persist locally
   ↓
Connectivity check recovers
   ↓
Push mutations idempotently
   ↓
Pull server changes
   ↓
Resolve true conflicts
```

Ninguna pantalla debe mostrar “sistema inutilizable” únicamente porque API no responde si el journey es localmente posible.

## 84. Network change handling

No se depende de un único evento `online/offline` del navegador.

El cliente combina:

- browser signal
- bounded API probe
- sync failures
- backoff state

Esto evita declarar Internet funcional sólo porque existe una interfaz de red.

## 85. Scheduled maintenance

Cadencia de referencia para managed installations:

- health review continuo/automatizado
- security patch review semanal
- application updates mensual o según release risk
- backup verification diaria
- restore drill mensual/trimestral según tier
- capacity review trimestral
- major upgrade rehearsal antes de ejecución

La cadencia contractual puede variar.

## 86. Dependency lifecycle

El proyecto mantiene una support matrix de:

- Debian
- Docker Engine / Compose
- PostgreSQL
- Python
- Node build toolchain
- browser tier

No se mantienen indefinitely versiones EOL sólo porque una instalación antigua aún funciona.

## 87. PostgreSQL major upgrades

Una major upgrade no ocurre como parte de un patch rutinario.

Procedimiento:

1. compatibility review
2. staging rehearsal
3. backup verified
4. upgrade method selected
5. downtime window or migration plan
6. validation
7. rollback/recovery point preserved

Se prioriza `pg_upgrade` o dump/restore según tamaño y compatibilidad probada.

## 88. OS major upgrade

Se recomienda reemplazo o upgrade ensayado, no actualización improvisada durante horario de taller.

Para managed cloud, reconstruir host nuevo desde infraestructura documentada y migrar estado puede ser preferible a mutar un servidor antiguo durante años.

## 89. Rebuildability

Una instalación Cloud/LAN administrada debe poder reconstruirse a partir de:

```text
release artifacts
config.toml
secrets recovery material
backup repository
DNS/TLS information
installation manifest
runbook
```

No debe depender de archivos “mágicos” creados manualmente y olvidados.

## 90. Infrastructure as code roadmap

V1 usa Docker Compose y scripts versionados.

Fases posteriores podrán añadir:

- Ansible role oficial
- Terraform examples para proveedores comunes
- cloud-init
- immutable image templates

Sin hacer que esos proveedores sean requisito del Core.

## 91. Local hardware resilience

Para LAN se recomienda:

- SSD de calidad
- UPS
- Ethernet cableado
- backup externo/offsite
- ventilación adecuada
- auto power-on after AC loss cuando hardware lo soporte

El software debe detectar reinicio inesperado y ejecutar startup integrity checks.

## 92. UPS integration roadmap

Una integración opcional futura puede reaccionar a UPS/NUT:

```text
Power failure
   ↓
UPS battery threshold
   ↓
stop accepting large jobs
   ↓
finish DB checkpoint/work
   ↓
graceful shutdown host
```

No es requisito V1.

## 93. Printer and peripheral operations

Hardware local se maneja mediante adapters.

Diagnostics puede incluir:

- printer configured
- last successful print
- browser permission state
- scanner availability

La falla de una impresora no bloquea la finalización de una orden. Se permite reimpresión o entrega digital.

## 94. Observability privacy

Telemetría técnica debe aplicar minimización.

No se usarán customer name, phone, bike serial ni message text como metric labels o trace attributes.

Los identifiers internos usados para debugging se limitarán o pseudonimizarán según necesidad.

## 95. Reliability dashboard

Vista administrativa propuesta:

```text
System        Healthy
API           Healthy
Database      Healthy
Worker        Healthy
Sync queue    12 pending
Backups       Last success 5h ago
Restore test  Passed 18 days ago
Disk          46%
TLS           Valid 71 days
Version       1.0.3
Updates       None
```

El dashboard no debe convertirse en una consola incomprensible para el propietario del taller.

## 96. Safe mode

La plataforma puede entrar en `safe mode` ante ciertos riesgos:

- schema incompatibility
- integrity check failure
- critical disk state
- failed migration

Safe mode permite diagnostics y export/recovery cuando sea seguro, pero evita writes que puedan empeorar corrupción.

## 97. Maintenance page

Caddy puede servir una página estática durante backend maintenance.

Requisitos:

- accesible
- branded
- sin stack traces
- status claro
- no prometer tiempos no conocidos
- distinguir customer portal de PWA local instalada

## 98. Operational audit trail

Acciones de administración sensibles registran:

- upgrade initiated
- backup created
- restore executed
- secret rotated
- plugin enabled/disabled
- emergency mode entered
- migration applied

No se guardan secret values.

## 99. Configuration drift

`ocwpctl config validate` compara:

- schema de config
- unknown keys
- deprecated keys
- invalid combinations
- required secrets

Managed environments podrán calcular hash del config no secreto para detectar drift.

## 100. Change management

Cambios operativos de alto riesgo requieren:

```text
change description
risk
backup state
rollback/recovery plan
maintenance impact
verification
operator
```

En microinstalaciones este registro puede automatizarse desde `ocwpctl` para no introducir burocracia manual.

## 101. Post deployment verification

Después de install/upgrade:

1. `health/live`
2. `health/ready`
3. DB schema version
4. worker test job
5. blob write/read test
6. auth smoke
7. create/read synthetic record cuando environment lo permita
8. service worker version
9. backup status
10. external provider status no bloqueante

## 102. Release qualification operational gates

Además de Fase 6, V1 requiere:

| Gate         | Condición                                           |
| ------------ | --------------------------------------------------- |
| OPS-GATE-001 | instalación limpia LAN reproducible                 |
| OPS-GATE-002 | instalación limpia Cloud reproducible               |
| OPS-GATE-003 | Standalone export/import validado                   |
| OPS-GATE-004 | Caddy TLS Cloud validado                            |
| OPS-GATE-005 | LAN secure context validado en Tier 1               |
| OPS-GATE-006 | backup baseline + restore completo                  |
| OPS-GATE-007 | PITR documentado y probado en reliability profile   |
| OPS-GATE-008 | upgrade desde versión soportada                     |
| OPS-GATE-009 | application rollback dentro de compatibility window |
| OPS-GATE-010 | failed migration entra a estado seguro              |
| OPS-GATE-011 | disk pressure alert y degradation probados          |
| OPS-GATE-012 | WAN outage no detiene Core LAN                      |
| OPS-GATE-013 | server outage no pierde mutaciones locales          |
| OPS-GATE-014 | orphaned client recovery rehearsal                  |
| OPS-GATE-015 | diagnostics bundle sin secrets/PII crítica          |
| OPS-GATE-016 | image digests + SBOM + signatures verificables      |
| OPS-GATE-017 | secrets no presentes en repository/logs             |
| OPS-GATE-018 | host rebuild desde artifacts + backup               |
| OPS-GATE-019 | alerting de backup failure probado                  |
| OPS-GATE-020 | runbooks de incidentes críticos revisados           |

## 103. Operational Definition of Done

Una capacidad operacional se considera terminada cuando:

1. tiene procedimiento documentado
2. puede ejecutarse mediante tooling versionado cuando corresponda
3. maneja error path
4. genera evidencia útil
5. no filtra secrets
6. tiene prueba automatizada o rehearsal reproducible
7. tiene rollback/recovery definido
8. tiene ownership claro
9. actualiza runbook y troubleshooting
10. puede ser realizada por un implementador que no escribió el código original

## 104. Runbook index objetivo

```text
docs/07-operations/
├── deployment/
│   ├── standalone.md
│   ├── lan.md
│   └── cloud.md
├── install/
│   ├── preflight.md
│   ├── bootstrap.md
│   └── handover.md
├── upgrades/
│   ├── standard.md
│   ├── rollback.md
│   └── major-upgrade.md
├── backup/
│   ├── baseline.md
│   ├── pitr.md
│   └── restore-drill.md
├── incidents/
│   ├── db.md
│   ├── disk.md
│   ├── tls.md
│   ├── security.md
│   ├── queue.md
│   └── blobs.md
├── observability/
│   ├── health.md
│   ├── metrics.md
│   └── alerts.md
└── support/
    ├── diagnostics.md
    └── field-checklist.md
```

## 105. Repository additions from this phase

```text
infra/
├── compose/
│   ├── compose.yaml
│   ├── compose.production.yaml
│   ├── compose.backup.yaml
│   └── compose.observability.yaml
├── caddy/
│   └── Caddyfile
├── system/
│   ├── nftables.conf.example
│   └── systemd/
└── backup/
    ├── restic/
    └── pgbackrest/

scripts/
└── operations/
    ├── install
    ├── backup
    ├── restore
    └── upgrade
```

## 106. Implementation sequence · O0 to O9

### O0 · Operational skeleton

- Compose baseline
- Caddy
- config schema
- secrets
- health endpoints

### O1 · Clean install

- Debian reference host
- LAN install
- Cloud install
- bootstrap admin

### O2 · Backup baseline

- pg_dump
- restic
- retention
- backup status

### O3 · Restore

- clean restore
- evidence
- smoke
- invariants

### O4 · Upgrade

- version manifest
- preflight
- image digest pinning
- migrations
- rollback window

### O5 · Observability

- structured logs
- metrics
- diagnostics
- alerting

### O6 · Failure handling

- disk pressure
- queue backlog
- provider outages
- safe mode

### O7 · Reliability profile

- pgBackRest
- WAL archive
- PITR
- lower RPO

### O8 · Field operations

- diagnostics bundle
- handover
- support checklist
- client recovery

### O9 · Production qualification

- rebuild host
- WAN outage
- server outage
- restore drill
- upgrade rehearsal
- security review

## 107. Costs operativos derivados

El software Core no requiere licencias de pago.

Los costos reales se originan en:

- hardware LAN
- VPS/cloud
- dominio
- offsite storage
- SMS/WhatsApp/email providers
- payment providers
- soporte humano
- monitoring externo opcional

### 107.1 LAN

Puede funcionar sin cuota cloud para el Core después de la instalación, salvo dominio, backup offsite o integraciones contratadas.

### 107.2 Cloud

Una sola VM pequeña puede alojar implementaciones iniciales. El sizing real debe basarse en benchmarks y volumen de media.

### 107.3 Reliability

PITR y offsite retention aumentan almacenamiento, operaciones y responsabilidad de soporte. Deben cobrarse como servicio profesional, no absorberse como “licencia gratuita”.

## 108. Cost control principles

1. No introducir servicios pagos obligatorios.
2. Separar costos de terceros del valor de implementación.
3. Permitir storage self hosted o compatible.
4. Hacer visible consumo de disco y backups.
5. Evitar overprovisioning por defecto.
6. Escalar cuando las métricas lo justifiquen.
7. Documentar qué capacidades aumentan RPO/RTO/SLO y cuánto cuestan operar.

## 109. Commercial implementation checklist

Antes de vender una implementación:

- número de sucursales
- usuarios concurrentes
- dispositivos
- Internet reliability
- necesidad de LAN
- acceso remoto
- volumen de fotos
- inventario aproximado
- integrations
- RPO esperado
- RTO esperado
- backup responsibility
- support hours
- hardware ownership
- domain ownership
- admin ownership
- training
- migration volume

Esta información determina el deployment profile, no el tamaño aparente del cliente.

## 110. Field technician checklist

En visita física:

```text
[ ] server power / UPS
[ ] Ethernet link
[ ] router/DNS
[ ] server IP reservation
[ ] HTTPS valid
[ ] tablet PWA installed
[ ] storage persistence checked
[ ] printer/scanner test
[ ] first order test
[ ] offline test
[ ] reconnect test
[ ] backup test
[ ] admin credentials transferred
[ ] support contact documented
```

## 111. Documentation for nontechnical workshop staff

La documentación operacional tendrá dos capas.

### Staff guide

Lenguaje breve:

- Internet se cayó
- no imprime
- WhatsApp pendiente
- cómo respaldar
- cómo verificar sincronización
- cómo cerrar sesión

### Implementer runbook

Incluye comandos, logs, containers, backups, DB y recovery.

No se obliga a un mecánico a interpretar infraestructura para continuar trabajando.

## 112. Status semantics

El UI diferencia:

```text
Offline
Server unavailable
External service unavailable
Sync pending
Sync conflict
Maintenance
Local storage risk
Backup overdue
```

Estos estados no se agrupan bajo un ambiguo “Error de conexión”.

## 113. Communication during incident

Los mensajes operativos deben explicar:

1. qué está afectado
2. qué sigue funcionando
3. si el trabajo está guardado localmente
4. qué acción debe tomar el usuario si existe

Ejemplo:

> WhatsApp no está disponible. Tu orden y los cambios están guardados. El mensaje se enviará cuando la integración vuelva a estar disponible.

## 114. Vendor neutrality

La arquitectura operacional no exige:

- AWS
- Azure
- GCP
- Cloudflare
- Sentry
- Datadog
- Twilio
- Meta como mensajería única

Pueden integrarse mediante adapters o deployment examples.

## 115. AGPL operational implications

El deployment package debe conservar:

- `LICENSE`
- notices requeridos
- source availability correspondiente
- información de versión

Si un implementador modifica el software y lo opera para usuarios a través de red, debe revisar sus obligaciones bajo AGPL v3.

El proyecto facilitará cumplimiento mediante source links, SPDX y documentación, sin convertir esto en asesoría jurídica individual.

## 116. Supply chain verification

Antes de producción:

```text
verify release signature
verify checksum
verify image digest
record SBOM reference
record version manifest
```

El update tool debe fallar cerrado ante una firma inválida en canales oficiales.

## 117. Reproducible rollback artifacts

Se conservan metadata de al menos la release anterior soportada:

- image digests
- deployment bundle
- migration compatibility
- config schema

Esto no significa que data rollback sea siempre posible. Permite application rollback cuando el schema lo admite.

## 118. Supportability score

Una instalación puede evaluar madurez operacional:

```text
Backup configured             yes/no
Offsite copy                  yes/no
Restore drill                 yes/no
Monitoring                    yes/no
UPS LAN                       yes/no
Admin ownership documented    yes/no
Recovery kit                  yes/no
Current release               yes/no
```

El score se utiliza para identificar riesgo, no para culpar al cliente.

## 119. Exit criteria de Fase 7

La Fase 7 queda cerrada conceptualmente cuando:

- las tres topologías están documentadas
- Compose baseline está especificado
- Caddy/TLS/DNS están definidos
- host baseline está cerrado
- config/secrets están cerrados
- install/bootstrap están definidos
- upgrade/rollback están definidos
- backup/PITR/restore están definidos
- DR runbooks tienen índice
- observability está definida
- SLO model está definido
- capacity planning está definido
- support/handover están definidos
- operational gates están definidos
- costos operativos están diferenciados de licencia

La implementación concreta de scripts y manifests se realizará durante las milestones de desarrollo correspondientes.

## 120. Relación con fases anteriores

### Foundation

Materializa local first, open source, service based business y vendor neutrality.

### Functional Requirements

Da operación real a backup, offline, communications, plugins, portal y administración.

### Technical Architecture

Despliega modular monolith, PostgreSQL, worker, Caddy boundary y Sync Engine sin introducir microservicios.

### Security & Privacy

Implementa secrets, network isolation, TLS, logging minimization, recovery y incident handling.

### UX/UI

Define estados operativos comprensibles y no bloqueantes para offline, maintenance y sync.

### Repository & Engineering

Añade Compose, operations scripts, release artifacts y `ocwpctl` al monorepo.

### QA & Verification

Convierte restore drills, upgrade rehearsals, offline tests y release gates en procedimientos operativos concretos.

## 121. Próxima fase

La siguiente fase será **Fase 8 · Open Source Governance, Contribution & Plugin Ecosystem**.

Deberá definir:

- governance model
- maintainer roles
- DCO workflow
- contributor ladder
- RFC process
- issue taxonomy
- security disclosure
- release authority
- plugin trust levels
- registry metadata
- plugin compatibility policy
- official/community plugin promotion
- funding and sponsorship
- commercial neutrality
- trademark/white label boundary
- community moderation
- translation contributions
- documentation contributions
- sustainability of maintenance

Después de Fase 8 se avanzará a Fase 9 Commercial Implementation Playbook y finalmente al Spec Development maestro ejecutable.

## 122. Fuentes técnicas verificadas para esta fase

Se revisaron como referencias normativas y operativas:

- Debian Releases, Debian Project: https://www.debian.org/releases/
- Docker Compose production guidance: https://docs.docker.com/compose/how-tos/production/
- Docker Compose secrets: https://docs.docker.com/compose/how-tos/use-secrets/
- Docker Compose service health checks: https://docs.docker.com/reference/compose-file/services/
- Docker Compose profiles: https://docs.docker.com/compose/how-tos/profiles/
- Caddy automatic HTTPS: https://caddyserver.com/docs/quick-starts/https
- Caddy reverse proxy: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
- PostgreSQL Backup and Restore: https://www.postgresql.org/docs/current/backup.html
- PostgreSQL Continuous Archiving and PITR: https://www.postgresql.org/docs/current/continuous-archiving.html
- restic documentation: https://restic.readthedocs.io/
- pgBackRest documentation: https://pgbackrest.org/

## 123. Cierre

Con esta fase la plataforma deja de ser únicamente una arquitectura de software y adquiere una arquitectura operacional explícita.

El estándar esperado para V1 es que un implementador pueda:

```text
provision
install
secure
configure
backup
restore
upgrade
diagnose
recover
handover
```

sin conocimiento privado del equipo original y sin convertir una falla de Internet en una interrupción general del taller.

La resiliencia queda definida como propiedad de producto, de infraestructura y de operación al mismo tiempo.
