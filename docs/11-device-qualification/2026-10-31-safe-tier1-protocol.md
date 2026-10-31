# Protocolo físico Tier 1 seguro · Windows y Android

Estado: **NO EJECUTADO**. Este documento prepara observaciones; no acredita ningún
dispositivo ni autoriza cambios de instalación. La revisión de documentación y las
pruebas estáticas no sustituyen la ejecución física. Usar la
[plantilla vigente](2026-10-31-safe-tier1-results.md). Copiarla a un nuevo registro
fechado y vinculado a la fuente; conservar la plantilla con todos los casos PENDIENTE.

## Alcance y precedencia

Se reemplaza el procedimiento operativo de agosto, conservado como histórico.
Las reglas de recuperación del [runtime local](../07-operations/2026-10-14-local-runtime.md)
y de [backup/restauración](../07-operations/2026-10-14-backup-restore.md) tienen
precedencia. No copiar credenciales, puertos, nombres de contenedores ni comandos
sembrados de aquel documento. No hay contraseña predeterminada.

T1–T8 son una primera observación funcional de un candidato en Windows físico y
una tablet Android física. No cierran R01-T035: el spike de **100,000** registros,
la línea base de almacenamiento de ambos dispositivos, recuperación, conflicto y
accesibilidad completa requieren evidencia y criterios propios. Tampoco califican
Raspberry Pi, capacidad de producción, publicación, activación de presupuestos,
migraciones o una instalación real. Los ensayos ya consumidos no se repiten.

## Antes de ejecutar: condiciones obligatorias

1. Registrar consentimiento del operador para los dispositivos, perfiles y el
   taller de prueba concretos. Usar exclusivamente registros sintéticos dentro de
   una instalación de prueba identificada y previamente autorizada; no improvisar
   despliegue ni bootstrap como parte de este protocolo. Si falta, marcar BLOQUEADO.
2. Registrar SHA del servidor y del PWA, IDs de imágenes cuando estén disponibles,
   origen exacto, fecha/zona horaria, modelos, OS y versiones de navegador. Si no se
   puede vincular un componente a su fuente, la calificación de ese componente
   queda BLOQUEADA; no atribuirle el SHA del checkout por proximidad.
3. Revisar datos y mutaciones pendientes en **todos** los perfiles participantes.
   Preservar IndexedDB, borradores y colas locales. El backup PostgreSQL **no incluye**
   trabajo local sin sincronizar. Un dump no es prueba de restauración. No continuar
   con acciones que puedan borrar o abandonar ese trabajo; no usar cerrar sesión
   como método para simular desconexión ni para reparar un fallo.
4. La instalación debe estar sana y corresponder al runtime documentado, con origen
   único para API/PWA. El acceso local documentado es `http://localhost:8080` en el
   propio host. Un HTTP con IP LAN no constituye contexto seguro. En Android usar
   un origen **HTTPS** confiable ya preparado y autorizado; no aceptar advertencias
   TLS ni relajar protecciones del navegador. Comprobar `window.isSecureContext`
   en cada dispositivo y registrar el origen real. No suponer confianza por un
   candado visto en otro equipo. Si no hay canal confiable, BLOQUEADO.
5. La instalación de certificados, depuración USB, reenvío de puertos, firewall,
   permisos de dispositivo y cualquier cambio de seguridad requieren revisión y
   autorización separadas. Este protocolo no los configura. No ejecutar el antiguo
   override de desarrollo para eludir estas condiciones.
6. Usar una cuenta ya preparada y con capacidades legítimas para el taller de
   prueba. No pegar contraseñas/tokens en comandos, capturas o reportes. Confirmar
   sesión inicial y carga online completa antes de desconectar.
7. Identificar un método reversible para interrumpir **la ruta efectiva al servidor**
   sin alterar la seguridad. El modo avión no demuestra por sí solo desconexión:
   USB, Ethernet, un proxy o rutas alternativas pueden mantenerla. Registrar
   evidencia de servidor inaccesible desde el dispositivo, sin capturar secretos.
   No apagar la base de datos ni matar contenedores para simular offline.

## Casos T1–T8 (repetir y registrar por dispositivo)

Cada caso usa la misma identidad de sesión/taller y el mismo registro sintético,
con nombre único de ensayo. Conservar su identificador visible cuando exista;
coincidir solamente en el nombre o contar una fila no demuestra exactly-once.
Un paso sin observación es PENDIENTE, una precondición ausente es BLOQUEADO y una
expectativa incumplida es FALLO. N/A requiere una razón verificable y no equivale a
PASE. Ante un fallo, conservar evidencia y detener los pasos dependientes.

### T1 Identidad y lectura online

Abrir el origen aprobado; iniciar sesión únicamente si no existe una sesión
válida. Verificar taller, permisos y datos sintéticos esperados sin revelar
credenciales. Registrar estado visible y disponibilidad del servidor. PASE exige
identidad correcta y lectura real; una captura de pantalla de login no basta.

### T2 Instalación y apertura standalone

Sólo con permiso del operador para instalar en ese perfil, usar la función normal
de instalación ofrecida por el navegador y abrir desde su icono. Si no se ofrece,
registrar BLOQUEADO o FALLO con el contexto; no cambiar flags para forzarla.
Registrar ventana standalone, origen y versión servida. No desinstalar una copia
existente ni borrar datos para hacer aparecer la opción de instalación.

### T3 Captura offline

Conservar la sesión y cortar la ruta identificada al servidor. Confirmar servidor
inaccesible y estado offline antes de crear **un** cliente sintético único con la
UI normal. Registrar el resultado local y la indicación de pendiente. Si aparece
resultado desconocido/requiere atención, no volver a enviar ni asumir rollback;
registrar FALLO o BLOQUEADO según la evidencia y preservar el borrador.

### T4 Recarga offline

Sin reconectar, recargar la misma app/origen. Comprobar que abre desde su caché
válida y conserva cliente, identificador y estado pendiente. Si una política de
sesión bloquea el acceso, registrar el bloqueo sin borrar datos ni extender la
sesión artificialmente. Una pantalla de error no demuestra pérdida de IndexedDB.

### T5 Cierre y reapertura offline

Sin cerrar sesión ni borrar almacenamiento, cerrar normalmente la ventana/PWA.
En Android cerrarla desde recientes sin usar «borrar datos». Reabrir aún offline
y repetir las observaciones de T4. Registrar exactamente qué proceso se cerró;
no llamar a esto prueba de reinicio del sistema, crash o resistencia a corte de
energía si esas acciones no ocurrieron. No forzar una actualización de la app.

### T6 Reconexión y comprobación sin duplicados observados

Restablecer únicamente la ruta que se interrumpió. Esperar el flujo normal, sin
reenvío manual ni edición SQL. Verificar que la UI muestra el registro y su estado
actual; con una segunda lectura online autorizada del mismo taller, cotejar el
identificador y contenido sintético. Si hay una herramienta ya aprobada de lectura
del servidor, anotar su referencia sanitizada y el resultado del mismo ID.
Sin evidencia del servidor, el tramo servidor queda BLOQUEADO, no PASE inferido.
Registrar ausencia o presencia de duplicados observados, no una garantía universal
de exactly-once. La desaparición de un pendiente no prueba sola el resultado.

### T7 Teclado y lectura asistida

En Windows recorrer login, formulario y acciones disponibles con Tab, Shift+Tab,
Enter y Espacio. Registrar foco visible, orden y ausencia de trampas. En el lector
de pantalla realmente disponible, comprobar nombres de campos, errores y estado.
Si falta lector, separar «teclado observado» de «lector BLOQUEADO»; no afirmar
WCAG 2.2 AA por un smoke. No ejecutar acciones irreversibles para probar un botón.

### T8 Tacto y lectura en tablet

En Android recorrer el mismo flujo con tacto, teclado del sistema y orientación
normal. Registrar solapamientos, scroll, foco y legibilidad con zoom/reflow; medir
los targets del flujo frente a la [especificación UX](../04-ux-design/open-cycling-workshop-platform-phase-4-ux-ui-design-system-v0.1.md):
base general 44 × 44 CSS px; en Workshop, primarios 56 × 56 CSS px y secundarios
mínimo 48 px. Registrar cada categoría aplicable sin reducirla al mínimo general.
Registrar lector de pantalla real por separado si se usa. En Windows registrar
el subconjunto aplicable sin inferir comportamiento táctil de Android. Capturas
de emulación no sustituyen una tablet física ni acreditan toda la accesibilidad.

## Fuera de este ensayo: NO EJECUTAR

- **Escenario de conflicto**: requiere escenario propio con identidades/versiones conocidas,
  resultado esperado y preservación de ambas historias. No fabricar escrituras con
  curl ni alterar SQL siguiendo el protocolo histórico.
- **Reinstalación y actualización**: no desinstalar, limpiar perfiles ni borrar
  IndexedDB. Hace falta un plan separado que preserve colas/borradores, backup y
  restauración probada. No asumir que todo lo local ya vive en el servidor.
- **Presión de almacenamiento/evicción**: no llenar el disco ni provocar cuota en
  un dispositivo con datos del usuario. Requiere autorización, límites, destino
  desechable identificado, mecanismo de parada y recuperación revisados aparte.
- **100,000 registros, apagado/pérdida de energía, restauración o migración**:
  siguen sus propios gates. Este documento no autoriza ensayos ni reinicia los
  presupuestos de experimentos anteriores. La limpieza histórica desconocida de
  microfixture41011497919 permanece UNKNOWN; una prueba nueva no la resuelve.

## Evidencia y cierre

Registrar por caso dispositivo, hora, condición inicial, acción real, resultado,
criterio, referencia sanitizada y responsable. No publicar contraseñas, tokens,
dumps, datos de clientes, identificadores de sesión ni capturas sin revisión.
Guardar evidencia privada localmente; compartir sólo material sintético revisado
y autorizado. Una ruta de archivo ausente o una casilla marcada no es evidencia.

No marcar R01-T035, Tier 1 global, release ni checklist como completados a partir
de esta plantilla. Entregar resultados como un PR separado con trazabilidad a la
fuente y revisión humana; mantener pendientes todos los casos no ejecutados y
los gates excluidos. No borrar evidencia de un intento fallido al repetirlo.
