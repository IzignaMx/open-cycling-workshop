# Recuperación PostgreSQL + logos compartidos del taller

Fecha: 2026-10-14. Alcance: generación consistente y recuperación aislada de la
base PostgreSQL y los PNG canónicos referenciados por perfiles de taller. Es una
parte de OPS-ADR-013 / OPS-ADR-015 / OPS-GATE-006 y de Increment E. No completa la
portabilidad de perfiles FR-WL-005 ni certifica una instalación real.

La herramienta PostgreSQL anterior conserva su formato, CLI y afirmación de
alcance. Su dump **no contiene los bytes de los logos**. Para perfiles compartidos
con imágenes, utilizar la generación adicional descrita aquí. No sustituye la
preservación de colas IndexedDB de cada navegador.

## Formato, coherencia y límites

`scripts.database.branding_bundle` crea una carpeta nueva con:

- `postgres/database.dump` y `postgres/manifest.json`: generación PostgreSQL
  compatible con la herramienta original.
- `assets/`: almacenamiento privado con namespace SHA256 de la identidad de la
  organización y claves generadas `primeros-dos-hex/digest-SHA256`. No hay URLs ni
  rutas arbitrarias aceptadas en el manifiesto.
- `branding-manifest.json`: marcador de finalización publicado atómicamente al
  final, después de fsync de sus bytes y de todos los archivos referenciados.

El observador recoge perfiles, referencias e incarnaciones de organizaciones
**dentro de la misma transacción REPEATABLE READ exportada a `pg_dump`**. Después
copia únicamente esos archivos inmutables; no vuelve a consultar el estado vivo
para seleccionar imágenes. Una edición posterior puede crear otra referencia
sin cambiar el contenido respaldado. La retención de archivos antiguos, sin GC
online, es necesaria para esta garantía. No ejecutar cambios de esquema ni
eliminar blobs durante el backup.

Se conservan todos los perfiles persistidos, incluidos aquellos sin logo. El
manifiesto compara también nombre, paleta, versión, actor y timestamp restaurados;
los conteos SQL por sí solos no prueban esta información. Cada logo debe coincidir
en bytes, SHA256, tamaño, framing PNG y dimensiones. Si falta o está corrupto,
**falla toda la generación de branding**. Un `postgres/manifest.json` válido dentro
de una generación incompleta sólo conserva su afirmación PostgreSQL-only.

Límites explícitos: 2.048 organizaciones, 2.048 perfiles, 4 MiB de manifiesto,
256 KiB por PNG y lados de 1–512 píxeles. El límite no trunca referencias: excederlo
rechaza la generación completa. Las imágenes se copian una a una; el peor caso de
bytes referenciados es 512 MiB, más el dump SQL y metadata. No hay cuota ni limpieza
automática de generaciones o archivos antiguos. Vigilar capacidad del volumen y
conservar espacio de trabajo suficiente. Un taller mayor requiere una ampliación
revisada y probada del formato, nunca quitar validaciones para pasar un backup.

Las carpetas deben ser controladas por el operador y no escribibles por grupo u
otros usuarios. Se rechazan symlinks, incluso en componentes intermedios de las
rutas, archivos no regulares, manifiestos duplicados/desconocidos y referencias
que no coincidan con la clave derivada del digest. El destino padre debe existir;
la herramienta no prepara permisos del host ni sobrescribe generaciones.

Los manifiestos contienen nombres de taller e identidades; el dump también
incluye cuentas y hashes de contraseña. Mantener **toda la carpeta restringida**
y proteger la copia externa por separado. No hay cifrado automático, firma,
proveniencia, retención automática, secretos, otras fotos/documentos ni copia de
navegadores. SHA256 acredita integridad respecto al manifiesto, **no autenticidad**.
Un dump puede ejecutar SQL: restaurar únicamente generaciones confiables creadas
y controladas por el operador. Nunca ensayar un archivo desconocido por el solo
hecho de que coincida su checksum.

## Crear y verificar

Preparar `OCWP_BACKUP_DIR` y permisos UID/GID 10001 como indica el
[procedimiento PostgreSQL](2026-10-14-backup-restore.md). La API escribe únicamente
en el volumen privado `branding_assets`; worker/edge no lo montan. El servicio
opcional `operations` monta ese volumen de sólo lectura. Su entrypoint habitual
sigue siendo la herramienta PostgreSQL-only; esta operación elige explícitamente
el módulo adicional:

```sh
docker compose -f infra/compose/docker-compose.local.yml --profile operations run --rm --no-deps \
  --entrypoint python operations -m scripts.database.branding_bundle backup \
  /backups/2026-10-14-taller-completo --asset-root /var/lib/ocwp/branding-assets

docker compose -f infra/compose/docker-compose.local.yml --profile operations run --rm --no-deps \
  --entrypoint python operations -m scripts.database.branding_bundle verify \
  /backups/2026-10-14-taller-completo
```

Para ejecución directa, usar las dependencias bloqueadas y clientes PostgreSQL 18
compatibles; la URL se lee exclusivamente del entorno o de un archivo secreto:

```sh
export OCWP_DATABASE_URL_FILE=/ruta/restringida/database_url.txt
uv run python -m scripts.database.branding_bundle backup /backups/generacion-nueva \
  --asset-root /ruta/privada/branding-assets
uv run python -m scripts.database.branding_bundle verify /backups/generacion-nueva
```

No escribir contraseñas en argv, reportes o historial. Se mantienen los controles
de URL/TLS/libpq y la supresión de errores SQL sensibles de la herramienta
PostgreSQL. Conservar cada generación anterior; no reutilizar su carpeta. Un
fallo deja evidencia incompleta para diagnóstico y nunca autoriza eliminar la
instalación anterior.

Estados:

- `branding_backup_created_not_restored`: generación completa; recuperación no
  probada.
- `branding_integrity_checked_not_restored`: metadata, todos los bytes y TOC SQL
  comprobados; no se ha restaurado.
- `branding_restore_checked`: SQL restaurado con schema/conteos coincidentes,
  todos los perfiles y bytes comparados e incarnaciones rotadas. El resultado
  mantiene `application_smoke_tested: false` y
  `client_pending_mutations_checked: false`.

El manifiesto mantiene siempre `restore_tested: false`; no se modifica al
verificar/restaurar. Conservar el resultado del ensayo separado, vinculado a sus
digests y a la revisión/digest exactos de la release. La versión del paquete por
sí sola no identifica una revisión Git o una imagen Docker.

## Restaurar en destinos nuevos y aislados

**No apuntar al PostgreSQL activo ni al volumen de logos activo.** Mantener
API/edge/worker, migraciones y todos los escritores fuera de los destinos durante
el procedimiento completo. Crear una base realmente vacía, sin migrar, y un
volumen de assets vacío. La herramienta no crea/elimina bases ni ejecuta DROP,
`--clean` o sobrescrituras. El advisory lock PostgreSQL no es aislamiento de red.

El CLI exige `--confirm-empty-target`, una URL de destino explícita diferente de
la variable de origen y un `--asset-root` explícito. Antes de restaurar SQL,
verifica la generación completa y reserva exclusivamente el volumen vacío con
`.ocwp-branding-restore`. No acepta una carpeta dentro del backup ni un ancestro
que lo contenga. El marcador queda incluso tras un fallo: no borrar el marcador
para reintentar sobre un destino que puede haber cambiado.

La restauración conserva los controles de versión de paquete, revisión Alembic,
major PostgreSQL, ausencia de objetos existentes y ausencia de otros clientes.
Copia y verifica assets antes de restaurar SQL. Si SQL falla, el nuevo volumen
puede contener bytes válidos pero la operación global **no** tuvo éxito. Si la
restauración SQL ya se confirmó y fallan comprobaciones posteriores, ambos
destinos deben quedar aislados. No hay rollback automático ni borrado del destino.

Para Compose, usar un **nombre de proyecto nuevo y separado** durante todo el
ensayo. No arrancar migrate/API/edge/worker todavía:

```sh
docker compose -p ocwp-branding-recovery -f infra/compose/docker-compose.local.yml up -d postgres

docker compose -p ocwp-branding-recovery -f infra/compose/docker-compose.local.yml \
  --profile branding-restore run --rm --no-deps operations-restore \
  restore /backups/2026-10-14-taller-completo --asset-root /restore-branding-assets \
  --confirm-empty-target > branding-restore-evidence.json
```

El servicio `operations-restore` monta backups de sólo lectura y el volumen
`branding_assets` **de ese proyecto aislado** escribible en
`/restore-branding-assets`. La API del mismo proyecto monta ese mismo volumen en
`/var/lib/ocwp/branding-assets`, evitando una recuperación aparente contra otro
volumen. La imagen prepara esos puntos con UID/GID 10001 y permisos restringidos;
la prueba real de Docker Desktop/host sigue siendo necesaria. La URL de destino
proviene de `OCWP_RESTORE_DATABASE_URL_FILE=/run/secrets/database_url` del proyecto
nuevo. Comprobar el destino antes de ejecutar; el nombre de perfil no convierte
un proyecto existente en un destino seguro.

Ejecución directa equivalente:

```sh
export OCWP_RESTORE_DATABASE_URL_FILE=/ruta/restringida/destino_nuevo_url.txt
uv run python -m scripts.database.branding_bundle restore /backups/generacion \
  --asset-root /ruta/privada/volumen-nuevo --confirm-empty-target
```

## Incarnación y reapertura

Esta ruta exige que **todas** las organizaciones de la generación tengan piso de
protocolo 1. Una generación de piso 0 puede preservarse/verificarse, pero este CLI
rechaza restaurarla antes de crear el destino de assets. Requiere un procedimiento
separado de upgrade/cutover aislado con su release compatible; no activa permisos,
cuentas o compatibilidad automáticamente.

Tras comprobar SQL, perfiles y assets, la herramienta invoca la recuperación
existente de cutover para cada organización con **la incarnación exacta del
snapshot como precondición**. Cambia la incarnación y añade su auditoría; conserva
cuentas, permisos, contraseñas y contadores. No incrementar session_version para
simular recuperación: un contador restaurado puede coincidir con una sesión
posterior al backup. La migración/cutover de esta release debe admitir 0011.

Si una rotación falla o se pierde la respuesta, puede haber organizaciones ya
rotadas y otras pendientes. Mantener ambos destinos aislados, consultar status y
la auditoría de mantenimiento por el procedimiento existente, y resolver con
las precondiciones comprobadas. No reintentar ciegamente ni volver a restaurar
sobre la base poblada. No ejecutar otra rotación tras un resultado exitoso.

Antes de reabrir el servicio:

1. En la red aislada, iniciar únicamente la API cualificada con los assets
   restaurados y la configuración/secretos recuperados por su vía separada.
2. Probar rechazo de tokens y checkpoints previos, login nuevo y contexto con
   incarnación nueva.
3. Leer perfiles reales mediante GET autenticado y comparar el SHA256 **de los
   bytes base64 decodificados de la respuesta**, dimensiones, nombre, paleta y
   versión con la generación. Comprobar dos organizaciones y talleres distintos;
   no sustituir esta prueba por un conteo de archivos o una llamada no autenticada.
4. Comprobar una petición cross-tenant denegada y workflows de negocio. Guardar
   evidencia sin tokens, contraseñas, imágenes ni datos innecesarios.
5. Preservar IndexedDB, journals, recibos y pendientes de cada cliente. No borrar
   cachés de negocio ni reproducir comandos antiguos ciegamente. Revisar tareas y
   outbox antes de arrancar workers/adaptadores.
6. Abrir API/edge al uso ordinario sólo después del smoke y de la reconciliación
   autorizada. Conservar instalación origen y generaciones previas.

Si la generación más reciente está corrupta, conservarla aislada y ensayar una
anterior completa en **otros destinos nuevos**. No recalcular hashes para ocultar
corrupción. RPO depende de la cadencia real de backups; el resultado incluye tiempo
de restore/check/rotación, pero el RTO operativo también incluye configuración,
smoke, reconciliación y reapertura. Un ensayo pequeño no mide datos realistas ni
hardware Raspberry. Cross-build ARM64 tampoco prueba ejecución física.

## Evidencia implementada y pendiente

Pruebas unitarias ejecutables cubren el observador en la transacción exportada,
coherencia ante una actualización posterior, manifiestos cerrados/acotados,
publicación final, bytes/dimensiones, symlinks, corrupción, destinos poblados,
fallos SQL y rotación sólo después de comprobaciones.

El ensayo `tests/operations/test_branding_recovery_postgres.py` utiliza únicamente
bases temporales UUID creadas por el fixture PostgreSQL existente y PNG/cuentas
sintéticos. Escribe tres perfiles de dos organizaciones por la API, confirma una
edición concurrente después del snapshot, demuestra que el dump anterior conserva
sus referencias, corrompe la generación nueva y exige rechazo, restaura la
anterior, rota incarnaciones y lee/compara todos los logos por GET autenticado.
Comprueba sesiones/checkpoint previos y denegación cross-tenant. Emite un JSON de
hashes esperados/reales y tiempos en su directorio temporal; su recolección como
artefacto CI requiere la configuración correspondiente.

```sh
uv run pytest -q tests/operations/test_backup.py tests/operations/test_backup_bundle.py \
  tests/operations/test_branding_bundle.py
uv run pytest -q tests/operations/test_branding_recovery_postgres.py
```

El segundo comando necesita `OCWP_TEST_DATABASE_URL` con host loopback explícito,
sufijo `_test`/`_e2e`, permiso para crear bases desechables y clientes PostgreSQL 18.
Sin ello informa **skipped**. Este incremento se escribió en un entorno sin
PostgreSQL/Docker disponibles: los tests de mocks/filesystem no acreditan la
restauración PostgreSQL, el smoke autenticado real ni Docker. La ejecución de ese
ensayo, sus hashes/timing y la cualificación exact-tree deben registrarse aparte.
No se realizó backup, restauración, migración, despliegue, cambio de credenciales
ni adopción de permisos en ninguna instalación real.
