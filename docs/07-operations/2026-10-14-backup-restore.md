# Backup y restauración del MVP local

Fecha: 2026-10-14. Alcance: herramienta de recuperación **sólo PostgreSQL**,
para el MVP Docker de laptop y su posterior traslado a Raspberry Pi de 64 bits.
Implementa una parte de OPS-ADR-013 / OPS-ADR-015 y OPS-GATE-006; no cierra por sí
sola el gate de recuperación completa ni sustituye un ensayo real.

## Qué protege y qué falta

Cada generación contiene `database.dump` (formato custom de `pg_dump`) y
`manifest.json`. El manifiesto registra versión de formato, versión del paquete
local, revisiones Alembic, versión PostgreSQL, tablas y cantidades de filas,
timestamps UTC, tamaño y SHA256 del dump. La revisión Git o digest de la imagen
no se deduce de la versión del paquete: conserva también el checkout/tag y digest
exactos del despliegue junto al registro del ensayo.

El snapshot de PostgreSQL permanece abierto mientras se recogen los conteos y se
ejecuta `pg_dump --snapshot`. Así, ambos representan el mismo punto consistente,
aunque el taller siga escribiendo. `snapshot_started_at` aproxima desde el reloj
del operador el inicio de ese snapshot; `created_at` registra la finalización.
No ejecutar cambios de esquema simultáneamente.

No incluye:

- Archivos de fotos, documentos u otros blobs externos. Sus referencias SQL no
  equivalen a sus contenidos; deben copiarse y comprobarse por separado.
- IndexedDB de cada navegador, mutaciones sin sincronizar ni su cola local.
- Configuración, certificados TLS, imágenes Docker ni secretos de autenticación.
- Roles globales de PostgreSQL; la restauración omite propietarios y ACL originales.
- Cifrado, firma, almacenamiento externo, retención automática o PITR.

El dump sí contiene datos del taller, incluidas cuentas y hashes de contraseña.
Trátalo como información sensible. Guarda las generaciones completas en un destino
restringido y cifrado, preferentemente fuera del disco principal. El backup no se
cifra automáticamente; una segunda carpeta del mismo SSD no es una segunda copia
independiente. Conserva el material de recuperación de secretos de forma separada.

**Sólo restaurar archivos de procedencia confiable creados/controlados por el
operador.** SHA256 detecta cambios accidentales respecto al manifiesto; no demuestra
autenticidad. Un atacante puede modificar el dump y su manifiesto. `pg_restore`
ejecuta SQL del archivo, por lo que no es seguro probar archivos desconocidos,
aunque el checksum coincida.

## Niveles de evidencia

- `backup_created_not_restored`: se completó la generación; no se probó su recuperación.
- `integrity_checked_not_restored`: tamaño, SHA256 y lectura del índice del archivo
  coinciden. `pg_restore --list` no lee/restaura todos los datos y no prueba recuperación.
- `database_restore_checked`: se ejecutó una restauración real y coincidieron las
  revisiones y los conteos de todas las tablas. Sigue faltando el smoke funcional,
  blobs y reconciliación de clientes. Los conteos no son una comparación de cada
  valor ni una demostración de todas las invariantes del dominio.

El manifiesto conserva `restore_tested: false`; no se reescribe al verificar o
restaurar. Guarda el JSON del ensayo por separado, asociado al SHA256 que contiene.

## Preparar el destino de backups

La imagen `infra/docker/operations.Dockerfile` incluye Python 3.13 y clientes
PostgreSQL 18.4. El servicio `operations` es opcional; no se ejecuta con el arranque
normal del taller. No utiliza el secreto de autenticación de la aplicación.

Desde la raíz del repositorio:

```sh
export OCWP_BACKUP_DIR=/ruta/absoluta/a/backups-ocwp
# Crear la carpeta con permisos restringidos para el usuario del contenedor
# (uid 10001). En Linux, el administrador debe preparar su dueño/permisos.
# En Docker Desktop, comprobar que el directorio compartido es escribible.
docker compose -f infra/compose/docker-compose.local.yml --profile operations build operations
```

El bind mount exige una carpeta existente y accesible; no cambia sus permisos ni
crea silenciosamente una carpeta root. Las generaciones se crean con modo 0700 y
los archivos con 0600 donde el filesystem aplica permisos POSIX. La publicación
atómica sin reemplazo utiliza hardlinks: generar en un filesystem que los soporte
(por ejemplo ext4 o NTFS); después puede copiarse la generación completa a otro
medio y volver a verificarla.

## Crear y verificar una generación

Con el PostgreSQL del taller ya iniciado:

```sh
docker compose -f infra/compose/docker-compose.local.yml --profile operations run --rm --no-deps \
  operations backup /backups/2026-10-14-antes-del-traslado

docker compose -f infra/compose/docker-compose.local.yml --profile operations run --rm --no-deps \
  operations verify /backups/2026-10-14-antes-del-traslado
```

Cambiar el nombre para cada generación. Nunca se sobrescribe una carpeta o dump
existente. Un fallo deja una generación incompleta sin manifiesto válido; no la
utilices ni la renombres como si fuera correcta. El dump parcial temporal se
elimina; un dump terminado cuyo manifiesto no terminó puede permanecer para
investigación, sin ser declarado válido. Conserva las generaciones anteriores.

Para uso directo, el entorno Python debe tener las dependencias bloqueadas del
workspace y `pg_dump`/`pg_restore` 18 en PATH:

```sh
export OCWP_DATABASE_URL_FILE=/ruta/restringida/database_url.txt
uv run python -m scripts.database.backup_postgres backup /ruta/backups/generacion-nueva
uv run python -m scripts.database.backup_postgres verify /ruta/backups/generacion-nueva
```

Los archivos de URL contienen una única URL PostgreSQL. No escribir credenciales
en argumentos, comandos de ejemplo, reportes o historial del shell. El CLI acepta
exactamente una de `OCWP_DATABASE_URL` / `OCWP_DATABASE_URL_FILE`; los archivos son
la ruta recomendada. La conexión conserva opciones TLS explícitas admitidas
(`sslmode`, `sslrootcert`, `sslcert`, `sslkey`, `channel_binding`, `connect_timeout`)
y rechaza opciones desconocidas o repetidas. Las variables de conexión `PG*`
heredadas del entorno (por ejemplo `PGHOSTADDR`, `PGSERVICE`, `PGPASSWORD`) se
rechazan antes de conectar, para impedir que psycopg y los clientes PostgreSQL
apunten a destinos distintos. Sólo se permiten `PG_MAJOR`, `PG_VERSION`,
`PG_SHA256` y `PGDATA`, metadata de la imagen oficial. Usar la URL explícita para
la conexión y quitar esos overrides del entorno. El timeout de conexión debe ser 1–60
segundos. Los subprocesos reciben credenciales por el entorno, no por argv;
administradores del host todavía pueden inspeccionar procesos, secretos y backups.

## Ensayo en una base realmente nueva

**Nunca apuntar restore a la base activa.** No hay opción de sobrescritura,
`--clean` ni eliminación de tablas. El operador debe elegir una base dedicada,
recién creada, sin migrar, y mantener fuera a API, worker, migraciones y cualquier
otro cliente durante todo el ensayo.

Antes de modificar el destino, la herramienta exige confirmación explícita,
integridad del bundle, la misma versión de paquete y las mismas revisiones Alembic
que la herramienta local, el mismo major PostgreSQL, ausencia de objetos de usuario
y ausencia de otros clientes conectados. También rechaza tablas vacías, secuencias,
vistas, rutinas, tipos, esquemas adicionales, extensiones y large objects existentes.
Una base que ya ejecutó `alembic upgrade` no es un destino vacío.

Un advisory lock transaccional impide restauraciones simultáneas realizadas por
esta herramienta. No bloquea clientes arbitrarios ni convierte el chequeo de
conexiones en aislamiento de red: detener servicios y aislar el destino es
responsabilidad del operador. `pg_restore` se ejecuta con `--single-transaction`,
`--exit-on-error`, `--no-owner` y `--no-privileges`. Un error SQL revierte la transacción.
Un fallo de conexión puede dejar incierto si se confirmó: aislar e inspeccionar,
no iniciar la aplicación ni borrar automáticamente el destino.

Para un ensayo en la misma laptop, un nombre de proyecto Compose distinto crea
red y volumen nuevos. Mantener el mismo nombre alternativo en todos los comandos:

```sh
# Sólo postgres. NO arrancar migrate/api/worker todavía.
docker compose -p ocwp-recovery-drill -f infra/compose/docker-compose.local.yml up -d postgres

# En este proyecto aislado, el secreto database_url apunta al postgres NUEVO.
docker compose -p ocwp-recovery-drill -f infra/compose/docker-compose.local.yml \
  --profile operations run --rm --no-deps \
  -e OCWP_RESTORE_DATABASE_URL_FILE=/run/secrets/database_url \
  operations restore /backups/2026-10-14-antes-del-traslado --confirm-empty-target \
  > restore-drill-evidence.json
```

La inicialización PostgreSQL local crea el usuario `ocwp` sin superusuario y una
base vacía que posee. Utilizar ese dueño como destino. No ejecutar el restore con
credenciales de superusuario ni reutilizar un proyecto de ensayo con datos: el
segundo intento contra un destino ya poblado será rechazado.

Para un destino distinto, proporcionar un archivo de URL del destino separado
mediante `OCWP_RESTORE_DATABASE_URL_FILE` (y montarlo de sólo lectura en el
contenedor). `OCWP_DATABASE_URL` nunca se utiliza implícitamente como destino.
El script no crea ni elimina bases por sí mismo.

Si los conteos o revisiones posteriores no coinciden, la restauración SQL puede
haber terminado, pero el resultado global falla. Aislar esa base para diagnóstico.
No hay rollback automático posterior a la confirmación de `pg_restore`.

## Completar el ensayo y trasladar a Raspberry Pi

1. Confirmar el JSON `database_restore_checked` y guardar su SHA256, versión,
   tiempos y resultado junto a la identidad del operador y release/digest exactos.
2. Comprobar fotos/documentos y su almacenamiento externo si existen. Recuperar
   configuración y secretos por su procedimiento separado.
3. Iniciar la misma release sobre la base restaurada, en otro puerto si comparte
   laptop. Por ejemplo, configurar `OCWP_HTTP_PORT=18080` y arrancar `migrate api edge`
   del proyecto de ensayo. Mantener worker/adaptadores externos detenidos hasta
   revisar tareas/outbox pendientes, para evitar reejecuciones no deseadas.
4. Comprobar `/health/ready`, login, lectura de clientes/bicicletas/órdenes y
   límites de organización/ubicación. Revisar cantidades, estados y registros
   sintéticos conocidos. Registrar el smoke realmente ejecutado; no inferirlo de
   los conteos SQL.
5. Preservar las colas IndexedDB. Si se recuperó un snapshot anterior al estado
   que conocían los navegadores, mantener la sincronización detenida hasta revisar
   cursores, pendientes y conflictos. No borrar IndexedDB ni iniciar replay ciego.
6. Para el traslado definitivo, detener nuevas escrituras, sincronizar y confirmar
   pendientes cuando sea posible, hacer una generación final, copiarla completa
   a la Raspberry y verificar allí. Registrar pendientes que no pudieron converger.
7. En Raspberry de 64 bits, construir/usar imágenes de la misma release para ARM64,
   con PostgreSQL 18 del mismo major. Restaurar en una base nueva antes de arrancar
   la aplicación. El dump lógico es la vía portable; no copiar el volumen binario
   PostgreSQL x86 como estrategia de migración ARM.
8. Tras el smoke en el equipo destino, planificar el cambio de URL/TLS/origen de
   los clientes. IndexedDB y Service Worker pertenecen al origen del navegador:
   cambiar hostname/protocolo/puerto no traslada los datos locales pendientes.
9. Conservar el origen y al menos una generación anterior hasta validar la nueva
   instalación. Detener un ensayo con `docker compose ... down` conserva su volumen.
   No usar `down -v`, podar volúmenes ni borrar la instalación original como rutina.

No se hace upgrade de major PostgreSQL ni actualización de schema durante restore.
Restaurar primero con la release de recuperación correspondiente; una actualización
posterior necesita su propio plan y ensayo. La compatibilidad ARM64, RTO con datos
realistas, hardware físico y restauración completa siguen requiriendo evidencia.

## Fallos y pruebas

Los errores salen por stderr con código distinto de cero. Se suprime stdout/stderr
crudo de PostgreSQL porque puede incluir filas sensibles. Revisar disponibilidad
local del cliente, versión, permisos, espacio y conexión sin publicar secretos.
Timeout de dump/restore: una hora. Los conteos también tienen límite SQL de una
hora por consulta. Una pérdida de conexión no prueba ni éxito ni ausencia de cambios.

Si la última generación falla, conservarla aislada y probar una generación anterior
en otro destino fresco. No reparar el checksum para ocultar corrupción.

```sh
uv run pytest -q tests/operations/test_backup.py tests/operations/test_backup_bundle.py
uv run pytest -q tests/operations/test_backup_postgres_integration.py
```

El segundo comando necesita `OCWP_TEST_DATABASE_URL` apuntando a una base de prueba
con sufijo `_test` o `_e2e`, host loopback explícito, sin opciones query en la URL,
permiso de crear bases y clientes PostgreSQL 18.
Crea/restaura/elimina solamente bases desechables con nombres UUID propios;
no restaura ni elimina la base indicada en esa variable. Sin estos requisitos,
el test informa `skipped`, no evidencia de recuperación. La limpieza destructiva
pertenece exclusivamente a ese fixture de pruebas; no al CLI de operaciones.

Evidencia local de este incremento: pruebas unitarias/mocks y análisis estático;
la ejecución real PostgreSQL/Compose y laptop → ARM debe registrarse por separado.
