# Operación explícita del contrato de cutover

Este procedimiento describe código del incremento B. No demuestra una instalación
activada: la App de producción sigue en v4 hasta el incremento C. No activar un
taller real hasta cualificar la composición integrada, preservar sus pendientes,
verificar backup/restore y reemplazar todos los binarios escritores anteriores.
El header no puede detener un servidor viejo que ignora el contrato.

## Preparación y estado

- Revisión requerida por este binario: Alembic `0010`. Migración forward-only;
  incluso vacía, la base rechaza downgrade antes de cualquier DDL/DML.
- Detener API/edge, workers, mantenimiento y despacho de clientes. Conservar el
  origen anterior, IndexedDB y sus colas; nunca adoptar automáticamente trabajo
  de autor o encarnación desconocidos.
- Migrar en aislamiento mediante el servicio `migrate`. No cambiar claves,
  contraseñas o permisos para activar compatibilidad.
- `OCWP_CUTOVER_ENABLED` es `false` por defecto. La composición local lo pasa al
  servicio API/worker desde la configuración de Compose. Cuando esté cualificada,
  configurar explícitamente `OCWP_CUTOVER_ENABLED=true` para los procesos API
  nuevos y el comando de activación. Cambiar sólo el entorno del comando no
  habilita una API que ya estaba ejecutándose.

Ejemplos para el operador autorizado, no ejecutados por este desarrollo:

```sh
# Primero migrar con todos los escritores ordinarios detenidos.
docker compose -f infra/compose/docker-compose.local.yml run --rm --no-deps migrate
# El binario ocwpctl pertenece a la imagen platform, no a operations (restore).
docker compose -f infra/compose/docker-compose.local.yml run --rm --no-deps api \
  ocwpctl cutover status --organization-id "$ORGANIZATION_ID"
# Requiere composición cualificada habilitada; no hay transición inversa.
docker compose -f infra/compose/docker-compose.local.yml run --rm --no-deps \
  -e OCWP_CUTOVER_ENABLED=true api \
  ocwpctl cutover activate --organization-id "$ORGANIZATION_ID"
```

`OCWP_DATABASE_URL` o `OCWP_DATABASE_URL_FILE` debe estar explícitamente configurado;
no se admite el destino de desarrollo implícito. Compose monta el archivo existente
de sólo lectura. Ningún comando crea una credencial o cuenta. Status devuelve
metadatos no secretos y la última auditoría de mantenimiento. Activación cambia
0→1 bajo el lock de organización y agrega auditoría atómica; un estado ya activo
válido es idempotente sin duplicar auditoría. No existe comando para bajar el piso.

Un token legacy sin `di` puede recibir 401 después de activación. Un cliente viejo
con login nuevo recibe 409 `client_upgrade_required` al escribir sin protocolo 1.
Ambos casos deben preservar la cola. El servidor deshabilitado puede devolver
contexto null pero rechaza escrituras protocolo 1; no habilitar reintentos
indefinidos ni despachar baseline ordinario cuando la negociación es null.

## Recuperación

Seguir [backup/restore](2026-10-14-backup-restore.md). Mantener aislamiento desde
restore hasta la rotación. Un snapshot anterior a B o piso 0 necesita upgrade y
activación explícita antes de recuperación; nunca reducir requisitos para abrirlo.

```sh
# Copiar EXPECTED_INCARNATION del status y guardar su evidencia no secreta.
docker compose -f infra/compose/docker-compose.local.yml run --rm --no-deps api \
  ocwpctl cutover recover --organization-id "$ORGANIZATION_ID" \
  --expected-incarnation "$EXPECTED_INCARNATION"
```

La precondición exacta evita repetir una rotación después de una respuesta perdida.
Consultar estado/auditoría antes de decidir una nueva operación. Preserva usuarios,
contraseñas, grants, contadores de sesión, recibos, feed, outbox e historial.
No existe replay automático entre encarnaciones. Verificar tokens/checkpoints
viejos rechazados y login/baseline nuevos en una API aislada antes de abrir edge;
revisar outbox antes de reactivar workers. Un smoke aislado no constituye permiso
para reabrir servicio ni prueba de recuperación física/realista.

Rollback de aplicación: sólo una versión compatible con schema y los controles B.
Usar forward fix o restore aislado revisado; nunca binarios pre-B, quitar proofs,
bajar el piso ni borrar historiales para lograr compatibilidad.
