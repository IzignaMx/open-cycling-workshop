# Preparar un ensayo: laptop Windows y tablet Android

Estado: **PROPUESTA NO CALIFICADA, NO EJECUTADA**. Windows primero, sin recomendar
cambiar de sistema por anticipado. Esta guía pública usa un escenario genérico:
laptop con 8 GB de RAM, SSD y procesador de clase i5 como hipótesis, no como equipo
verificado; tablet Android de recursos limitados con Chrome como cliente. No se
han instalado componentes, desplegado OCW ni probado dispositivos con esta guía.

La ruta operativa documentada hoy es **rootful Linux**. Docker Desktop con WSL 2
sobre Windows necesita calificación propia, especialmente permisos de archivos,
volúmenes, arranque y acceso LAN. Que Docker arranque no demuestra que OCW funcione.
La revisión o CI de esta guía tampoco lo demuestra. El selector de bicicleta
existente sigue desactivado; G1–G6 y aceptación física permanecen abiertos.

## 1. Confirmar el equipo sin modificarlo

Anotar sólo modelo/CPU, RAM instalada, espacio libre del SSD, edición/build de
Windows, versión WSL/Docker/Compose si existen, y Android/Chrome/modelo de tablet.
No publicar número de serie, usuario del sistema, IP pública, contraseñas o tokens.
En Administrador de tareas → Rendimiento, observar memoria disponible, CPU,
virtualización y actividad del disco. Un «i5» sin generación/modelo no acredita
compatibilidad ni capacidad.

Comandos **de lectura**, en PowerShell, sólo si el componente ya está instalado:

```powershell
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber
Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory
Get-CimInstance Win32_Processor | Select-Object Name, VirtualizationFirmwareEnabled, SecondLevelAddressTranslationExtensions
Get-Volume | Select-Object DriveLetter, FileSystem, SizeRemaining, Size
wsl --version
wsl --list --verbose
docker version
docker compose version
git rev-parse HEAD
```

Si una orden falta, informa error o Docker no responde, registrar «no disponible».
No ejecutar instalación, actualización, elevación, habilitación de características
ni `wsl --shutdown` para completar la ficha. No iniciar una distribución detenida
sólo para inspeccionarla. Revisar localmente si existe `.wslconfig`, sin copiar
rutas personales ni editarla. Registrar backend Linux containers, versiones y
configuración efectiva, no inferirla sólo de valores por defecto.

### Requisitos externos y licencia (consulta: 19 noviembre 2026)

[Docker para Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
publica WSL ≥2.1.5, CPU de 64 bits con SLAT, virtualización habilitada y 8 GB de RAM.
Enumera Windows 10 22H2 build 19045 y Windows 11 23H2 build 22631 o posteriores,
con requisitos de edición y soporte Microsoft vigente. El número de build por sí
solo no basta: comprobar edición y ciclo de soporte del equipo concreto. OCW usa
contenedores Linux, no Windows containers. Docker también exige características
WSL y servicio LanmanServer habilitados según su ruta de instalación; esta guía
sólo inspecciona, no los cambia. Windows Server no es una alternativa Desktop
soportada. Volver a comprobar la página oficial al preparar la instalación.

[Licencia Docker Desktop](https://docs.docker.com/subscription-billing/desktop-license/):
la gratuidad para pequeñas empresas exige menos de 250 empleados **y** menos de
10 millones USD anuales; existen categorías gratuitas personal, educativa y OSS
no comercial. Entidades gubernamentales y usos fuera de los límites requieren
suscripción. No asumir elegibilidad por el tamaño aparente de una instalación ni
porque OCW sea AGPL. El responsable debe revisar los términos aplicables antes de
instalar/aceptar; no se compra ni acepta una licencia aquí.

### 8 GB: punto de partida, no capacidad prometida

El mínimo de Docker no reserva margen para Windows, navegador, WSL, PostgreSQL y
construcción de imágenes. Según [Microsoft WSL](https://learn.microsoft.com/en-us/windows/wsl/wsl-config),
la memoria predeterminada de la VM es 50% de RAM de Windows y swap es 25% redondeado
hacia arriba al GB: para 8 GB, aproximadamente 4 GB y 2 GB respectivamente, salvo
configuración distinta. Swap usa disco, no sustituye RAM. No son límites medidos
de OCW. El Compose local no establece un presupuesto de RAM/CPU por servicio.
No recomendar un cap, desactivar swap, tocar pagefile o cambiar límites antes de
medir. No confundir memoria comprometida, RAM residente y almacenamiento del VHD.

## 2. Qué se debe calificar antes de arrancar OCW en Windows

Revisar [runtime local](../07-operations/2026-10-14-local-runtime.md) y
[Compose local](../../infra/compose/docker-compose.local.yml), sin ejecutar sus
comandos de instalación como si fueran instrucciones Windows ya validadas.

- Servicios persistentes: PostgreSQL `18.4-trixie`, API, worker y edge Caddy.
  `migrate` y `branding-assets-init` son tareas de inicialización. Bootstrap,
  operaciones y restauración son perfiles explícitos, no servicios de uso diario.
- API espera migración exitosa y volumen de recursos válido. Worker saludable
  acredita conexión/configuración, no ejecución de automatizaciones de negocio.
- Volúmenes nombrados conservan PostgreSQL, recursos de marca y estado/configuración
  Caddy. No usar `down -v`, borrar volúmenes, limpiar IndexedDB o regenerar secretos.
- Secretos de archivo, montajes y UID/GID 10001 requieren prueba específica en
  Docker Desktop/WSL2. NTFS/ACL no equivalen a `chmod/chown` Linux. Si falla lectura,
  detenerse, no hacer secretos públicos ni copiar comandos `sudo chown` a ciegas.
- Construcción/descarga inicial necesita Internet. Registrar commit e IDs de
  imágenes; tags no son garantía inmutable. Tener binarios/imágenes preparados no
  prueba que primer login, autorización o carga inicial funcionen sin servidor.
- Preparar respaldo **y restauración comprobada** en instalación aislada según el
  [procedimiento existente](../07-operations/2026-10-14-backup-restore.md).
  PostgreSQL no contiene borradores o mutaciones aún locales del navegador.

**BLOQUEADO** hasta tener instalación sintética autorizada, cuentas legítimas,
permisos/montajes verificados y recuperación documentada. Esta guía no ejecuta
build/up/bootstrap/restart, instalación de certificados ni cambios de firewall.

## 3. Observar línea base, arranque y reinicio autorizado

En una instalación de prueba **ya preparada**, registrar tres filas comparables:
reposo de Windows antes del ensayo, OCW sano sin actividad, y una recepción seguida
de lectura/gestión. Anotar hora, RAM disponible/comprometida, CPU, actividad de
SSD, memoria de WSL/Docker y presión de paginación (Monitor de recursos: errores
fuertes/s y disco). Errores fuertes no equivalen por sí solos a swap; correlacionar
actividad sostenida con pausas. Registrar duración, fallos y carga concurrente,
no sólo la mejor muestra ni percentiles de tres intentos.

Lecturas para el proyecto existente, desde la raíz y con sus variables ya preparadas.
Confirmar primero el mismo Docker context y nombre de proyecto autorizados
(`COMPOSE_PROJECT_NAME` o `-p` usado en esa instalación); los ejemplos presuponen
esa selección correcta. `docker context show` sólo la muestra: no ejecutar
`docker context use` ni cambiar de proyecto para obtener una respuesta. Si no
coincide, detenerse. Medir únicamente contenedores de ese proyecto:

```powershell
docker context show
docker compose -f infra/compose/docker-compose.local.yml ps -a
$containerIds = @(docker compose -f infra/compose/docker-compose.local.yml ps -q)
if ($containerIds.Count -gt 0) { docker stats --no-stream $containerIds }
else { Write-Output 'Sin contenedores activos del proyecto: detener y revisar' }
curl.exe --fail http://localhost:8080/health/ready
```

Si el proyecto usa override LAN, debe usarse su composición exacta ya autorizada
y el origen HTTPS aprobado; no mezclar proyectos ni asumir disponible localhost8080.
No compartir salida de otros contenedores ajenos. Esperado: migración e inicializador
terminados con código 0; PostgreSQL/API/worker/edge sanos; readiness HTTP200 con
`status: ready` y `environment: production`. Una respuesta cacheada de la pantalla
no sustituye salud del servidor. Salud tampoco demuestra carga/recepción correctas.

Para un arranque o reinicio ordenado **posteriormente autorizado**, conservar el
mismo proyecto, secretos y volúmenes. Registrar tiempo hasta salud y luego lectura
de una orden sintética confirmada antes del reinicio, con mismo ID y contenido.
No reiniciar si hay trabajo local pendiente sin revisar su recuperación. No matar
procesos, simular corte eléctrico o cambiar suspensión/energía como parte del ensayo.
`restart: unless-stopped` no garantiza por sí solo inicio de Docker Desktop tras
reiniciar Windows. Registrar explícitamente si depende del login/inicio de Desktop.
Si falla arranque, hay OOM, paginación sostenida con pausas o salud inestable, parar
y conservar diagnóstico. No ajustar memoria ni repetir hasta ocultar el fallo.

## 4. Android: un cliente, no el servidor

La tablet usa Chrome contra el servidor local. RAM libre, almacenamiento disponible,
versión de Android/Chrome, teclado táctil y política de sesión deben observarse en
ese modelo; no hay un mínimo Android acreditado por esta guía. No cerrar sesión,
borrar caché/datos ni desinstalar PWA para arreglar un resultado.

El acceso por defecto `http://localhost:8080` sólo sirve en la laptop. En Android,
`localhost` nombra la tablet. Una IP LAN por HTTP no hereda la confianza de localhost.
[MDN](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts)
explica que service workers requieren contexto seguro. Usar HTTPS confiable en el
cliente real; comprobar `window.isSecureContext` mediante un método ya autorizado,
SW activo y origen exacto. Si inspeccionarlo requiere depuración/permisos nuevos,
registrar pendiente, no habilitarlos automáticamente.

El [override LAN](../../infra/compose/docker-compose.lan.yml) requiere Compose
≥2.24.4 (`!override`), host/IP estable explícito y confianza de la CA Caddy en cada
cliente. Sustituye publicación localhost por IP LAN explícita HTTPS443→8443;
API/PostgreSQL no publican puertos de host. Esto no acredita por sí solo accesibilidad
Windows/WSL2, DNS o confianza Android. Prepararlos es una tarea autorizada separada.
No aceptar advertencias TLS, usar flags inseguros, abrir router hacia Internet ni
modificar certificados/firewall/trust store desde esta guía.

## 5. Dos condiciones de red distintas, no una sola prueba «offline»

Usar el [protocolo T1–T8](2026-10-31-safe-tier1-protocol.md) y copiar su
[plantilla](2026-10-31-safe-tier1-results.md) a un registro fechado. No duplicar
ni marcar cumplidos sus casos. Añadir las siguientes observaciones como anexos
con instalación, origen, cuenta, fuente y método de interrupción autorizados.

**A. Sin WAN, con ruta local al servidor disponible.** Sólo en red de prueba con
método reversible previamente aprobado, verificar falta de salida externa mediante
un destino de control autorizado y ausencia de rutas alternativas (datos móviles,
VPN, USB). Mantener WiFi/LAN y comprobar respuesta fresca del servidor desde la
tablet. No cambiar router o red compartida para lograrlo. Si no hay método seguro,
BLOQUEADO. Tras carga/login inicial y preparación online, realizar recepción
sintética normal y confirmar resultado servidor. No debe interpretarse como trabajo
pendiente sólo porque falta Internet. Fallar una web externa tampoco demuestra
por sí solo ausencia total de WAN.

**B. Servidor realmente inaccesible desde el cliente.** Conservar servidor sano y
usar sólo el método reversible autorizado para aislar la ruta de esa tablet. Probar
falla de la ruta exacta al servidor, no sólo icono offline o `navigator.onLine`.
Otra lectura online autorizada puede demostrar que el servidor sigue sano. Un
HTTP503 recibido no equivale a fallo de transporte. No apagar DB/contenedores ni
improvisar el proxy de CI en una instalación real. Seguir T3–T6 para preservación y
reconexión; si lease/política impide acceso, registrar BLOQUEADO sin eludirla.

### Recepción y gestión que interesa observar

En la cuenta y ubicación sintéticas correctas: seleccionar un cliente de prueba,
crear bicicleta **nueva inline** y orden con problema/condición/accesorios, guardar
una sola vez y distinguir guardado local de confirmación servidor. Registrar IDs.
Con conexión sana, salir del panel y volver a localizar/abrir la misma orden:
comprobar datos de recepción, cliente/bicicleta asociados si sus permisos lo
permiten, estado e historial. Probar una transición permitida con nota opcional
sólo si esa modificación sintética está incluida en el ensayo aprobado; volver a
leer mismo ID, estado e historial. No activar selector de bicicleta existente ni
dominios financieros para completar la demostración.

En la condición B, registrar dependencia bicicleta→orden y pendientes, recargar o
reabrir según T4/T5 y comprobar mismos IDs/contenido. Reanudar sólo por flujo normal
al restaurar la ruta. Confirmar ambas entidades por lectura servidor autorizada y
mismo ID, no sólo por contador UI. Si resultado desconocido/requiere atención o la
sesión se bloquea, conservar datos y detener pasos dependientes: no crear otra
orden «por si acaso». Ni CI ni este ensayo garantizan que una persona no vuelva
a introducir la misma intención. Lectura/gestión offline se limita a datos y
capacidades realmente disponibles; no se promete acceso indefinido.

## 6. Decisión al terminar la ficha

- **Seguir con Windows** si cumple requisitos/licencia y el candidato puede
  calificarse con salud, permisos, recuperación y margen observados. No proclamar
  capacidad de producción por un único pase.
- **Investigar Windows primero** si faltan versiones, permisos, origen confiable o
  mediciones. Una tablet lenta no demuestra que Windows sea el cuello de botella.
- **Evaluar Linux como alternativa**, no instalarlo, sólo con causa concreta:
  Windows fuera de soporte/requisitos, incompatibilidad comprobada de permisos o
  consumo/paginación persistente que impida el ensayo. Linux coincide con la ruta
  documentada, pero tampoco queda físicamente calificado por cambiar de OS.

Falta confirmar equipo exacto, build/edición/soporte Windows, virtualización,
licencia/backend/versiones, margen RAM/SSD observado, Android/Chrome, instalación
sintética/recuperación y origen HTTPS confiable ya autorizado. Hasta entonces no
hay permiso implícito de despliegue ni aceptación física. No contactar terceros ni
usar datos reales para completar esta ficha.
