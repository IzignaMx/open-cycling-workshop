# Protocolo de Calificación Física Tier 1 · V0.1

> Ejecutable por el operador con dos dispositivos: **este equipo Windows** (navegador Chromium) y una **tablet Android**. Cada paso define qué hacer, qué evidencia capturar y el criterio de pase. Registra todo en `2026-08-31-tier1-results.md` (plantilla adjunta) y archiva las capturas en `docs/11-device-qualification/evidence/`.

## 0. Preparación del host (una vez, en el PC Windows)

```bash
# 1. Stack completo (PostgreSQL 18.4 + API + worker) — evidencia ya probada
docker compose -f infra/compose/docker-compose.dev.yml up -d

# 2. Build de producción del PWA
pnpm --filter @ocwp/web build

# 3. Servir el build de producción (mantén esta terminal abierta)
pnpm --filter @ocwp/web exec vite preview --host 127.0.0.1 --port 5173
```

- URL de la app: `http://127.0.0.1:5173` (mismo origen; el preview proxya `/api` al backend 8000).
- Credenciales sembradas por el smoke anterior: organización `01a0560c-2f58-7a84-b52d-e3f3c13b4710` · usuario `admin` · contraseña `compose-smoke-password-1234`. Si prefieres un ambiente limpio: `docker compose ... down -v` y `ocwpctl bootstrap admin` de nuevo.
- **localhost es contexto seguro** → Service Worker e instalación PWA funcionan sin HTTPS.

## 1. Windows Tier 1 (navegador Chromium de escritorio)

Antes de empezar registra: navegador + versión (`chrome://version`), edición de Windows, y si es PWA instalada o pestaña.

| #   | Paso                                                                                                                                                                                                         | Criterio de pase                                                                                                                                                                                                          | Evidencia                                                                                                                                              |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| W1  | Abre `http://127.0.0.1:5173` e inicia sesión                                                                                                                                                                 | Sesión visible ("Sesión: Admin…"), estado "Sincronizado"                                                                                                                                                                  | Captura 01                                                                                                                                             |
| W2  | Instala la PWA (icono instalar en la barra de direcciones) y ábrela como app                                                                                                                                 | Ventana standalone sin barra de navegador; icono en inicio                                                                                                                                                                | Captura 02                                                                                                                                             |
| W3  | **Offline**: DevTools → Network → Offline (o desconectar red). Crear cliente "Cliente Tier1 Offline"                                                                                                         | Mensaje "Cliente guardado localmente" y estado "Sin conexión"                                                                                                                                                             | Captura 03                                                                                                                                             |
| W4  | Con la app aún offline: **recargar** (Ctrl+R)                                                                                                                                                                | App carga desde Service Worker; el cliente y la mutación pendiente siguen ahí                                                                                                                                             | Captura 04                                                                                                                                             |
| W5  | **Reconectar** (Network → Online o reconectar red)                                                                                                                                                           | Estado pasa a "Sincronizado" sin duplicar el cliente; en PostgreSQL queda exactamente 1 fila                                                                                                                              | Captura 05 + `docker exec ocwp-dev-postgres-1 psql -U ocwp -d ocwp -t -c "SELECT count(*) FROM customers WHERE display_name='Cliente Tier1 Offline';"` |
| W6  | **Conflicto**: con la app offline, editar ese cliente desde OTRO navegador/perfil (o `curl` al API `POST /api/v1/sync/mutations` con `base_version` actual). Descolgar un cambio local obsoleto y reconectar | "Requiere atención" + incidente visible en "Centro de incidencias" con el ID y motivo `base version`; el dispositivo converge a la edición ganadora                                                                       | Capturas 06a/06b                                                                                                                                       |
| W7  | **Teclado**: navegar login → alta rápida → botones solo con Tab/Enter/Espacio                                                                                                                                | Todo operable; foco visible; sin traps                                                                                                                                                                                    | Captura 07 (o nota)                                                                                                                                    |
| W8  | **Reinstalación**: desinstalar la PWA y reinstalar                                                                                                                                                           | Registrar comportamiento: el navegador ELIMINA el almacenamiento al desinstalar (esperado); documentar que la recuperación es re-login + sync pull (los datos ya sincronizados NO se pierden porque viven en el servidor) | Nota en results                                                                                                                                        |

## 2. Android Tablet Tier 1

### Conectividad — Opción A (recomendada): reenvío de puertos USB

Mantiene `localhost` en la tablet = contexto seguro (SW + instalación sin flags).

```bash
# En el PC (una vez): instalar adb si no existe
winget install --id Google.PlatformTools   # o usa el adb que ya tengas

# Tablet: activar Opciones de desarrollador + Depuración USB; conectar por cable
adb devices                                # debe listar la tablet
adb reverse tcp:5173 tcp:5173              # tablet:localhost:5173 → PC:5173
```

> El preview del PC proxya `/api` al backend: **solo necesitas reenviar el 5173.**

### Conectividad — Opción B (sin cable, con flag)

En Chrome de la tablet: `chrome://flags/#unsafely-treat-insecure-origin-as-secure` → añadir `http://<IP-DEL-PC>:5173` → relanzar. En el PC sirve con `--host 0.0.0.0`:
`pnpm --filter @ocwp/web exec vite preview --host 0.0.0.0 --port 5173` (y permitir el puerto en el Firewall de Windows). **Registra en resultados que se usó este flag** (afecta la interpretación del contexto seguro).

### Pasos

Antes de empezar registra: modelo exacto, versión de Android, versión de Chrome.

| #   | Paso                                                                                                                                                                            | Criterio de pase                                                                                                                                                                              | Evidencia        |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| A1  | Abrir `http://localhost:5173` (Opción A) e iniciar sesión                                                                                                                       | Sesión activa, "Sincronizado"                                                                                                                                                                 | Captura A1       |
| A2  | Instalar PWA: menú Chrome → "Instalar aplicación"/"Añadir a pantalla de inicio" y abrirla desde el icono                                                                        | Pantalla completa standalone sin UI del navegador                                                                                                                                             | Captura A2       |
| A3  | **Targets táctiles**: alta rápida de cliente solo con los dedos                                                                                                                 | Campos y botones tocables sin precisión fina (mínimo 44px); teclado del sistema usable                                                                                                        | Captura A3       |
| A4  | **Offline + reinicio de proceso**: activar modo avión (o apagar Wi-Fi), crear cliente "Cliente Tier1 Android", cerrar la app del todo (swipe/recientes) y reabrirla aún offline | La app abre offline desde SW; el cliente creado sigue presente                                                                                                                                | Capturas A4a/A4b |
| A5  | **Conmutación de red**: reconectar Wi-Fi                                                                                                                                        | "Sincronizado"; sin duplicados (verificar igual que W5)                                                                                                                                       | Captura A5       |
| A6  | **Presión de almacenamiento** (si es viable): llenar el almacenamiento del dispositivo hasta la presión (descargas/videos) y observar la app                                    | Registrar si el navegador desaloja el almacenamiento de la PWA y qué ve el usuario. La app NO llama hoy a `navigator.storage.persist()` — si ocurre desalojo, regístralo: será mejora de V0.2 | Nota/capturas A6 |
| A7  | Cámara/archivos: N/A en V0.1 (sin feature de adjuntos) — registrar "no aplica"                                                                                                  | —                                                                                                                                                                                             | Nota             |

## 3. Al terminar

1. Completa `2026-08-31-tier1-results.md` con modelos, versiones, resultado por paso y referencias a capturas.
2. Copia las capturas a `docs/11-device-qualification/evidence/` (nómbralas según la tabla).
3. Marca en `MANUAL-ACTIONS-CHECKLIST.md` la sección "Tier 1 physical device qualification" y actualiza `execution-state.yaml` (R01-T035) con un PR.
4. Cualquier fallo: NO lo marques pase; repórtalo como issue con captura — se corrige y se repite el paso.
