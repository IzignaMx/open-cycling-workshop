# Registro físico Tier 1 seguro · plantilla

Estado inicial: **NO EJECUTADO**. No existe resultado físico en este archivo.
Usar el [protocolo vigente](2026-10-31-safe-tier1-protocol.md); no el de agosto.
Copiar esta plantilla a un nuevo registro fechado y vinculado a la fuente;
conservar esta plantilla con todos los casos PENDIENTE.
No cierra R01-T035 ni el spike de 100,000 registros. Una prueba estática no convierte
PENDIENTE en PASE. No marcar calificación global sin todos sus gates independientes.

## Identidad y precondiciones

- Operador, fecha y zona horaria: PENDIENTE.
- Alcance autorizado (dispositivos/perfiles/taller sintético): PENDIENTE.
- SHA servidor y PWA; IDs de imágenes y forma de verificar correspondencia: PENDIENTE.
- Modelo físico, OS y versiones de navegador, por Windows y Android: PENDIENTE.
- URL/origen exacto y comprobación de contexto seguro por dispositivo: PENDIENTE.
- Cuenta/taller de prueba, capacidades comprobadas sin credenciales: PENDIENTE.
- Preservación de borradores, colas y datos locales en cada perfil: PENDIENTE.
- Backup y restauración comprobada, alcance y limitaciones: PENDIENTE.
- Ruta efectiva de conexión y prueba de interrupción/reconexión: PENDIENTE.
- PWA instalada/pestaña y versión realmente cargada: PENDIENTE.

## Resultados separados

| Caso | Windows   | Android   | Hora, observación y evidencia sanitizada |
| ---- | --------- | --------- | ---------------------------------------- |
| T1   | PENDIENTE | PENDIENTE |                                          |
| T2   | PENDIENTE | PENDIENTE |                                          |
| T3   | PENDIENTE | PENDIENTE |                                          |
| T4   | PENDIENTE | PENDIENTE |                                          |
| T5   | PENDIENTE | PENDIENTE |                                          |
| T6   | PENDIENTE | PENDIENTE |                                          |
| T7   | PENDIENTE | PENDIENTE |                                          |
| T8   | PENDIENTE | PENDIENTE |                                          |

Estados admitidos: PENDIENTE, BLOQUEADO, FALLO, PASE o N/A justificado.
Para cada cambio de estado registrar precondición, acción exacta, criterio y
observación. En T6 separar lectura local y servidor. En T7/T8 separar teclado,
tacto y lector de pantalla; un subconjunto pasado no acredita todos los demás.

## Gates excluidos, aún abiertos

- Conflicto/historias y política de resolución: NO EJECUTADO.
- Reinstalación/actualización con preservación y recuperación: NO EJECUTADO.
- Presión/evicción y cuota real: NO EJECUTADO.
- Spike 100,000 + baseline Windows/Android de R01-T035: NO EJECUTADO.
- Raspberry, cortes de energía, instalación/restore reales: NO EJECUTADO.
- Accesibilidad integral y soporte Tier 1 global: NO CALIFICADO.

## Privacidad y revisión

Evidencia exclusivamente sintética y sanitizada; **no publicar** secretos, tokens,
contraseñas, dumps, datos de clientes ni logs completos sin revisión. Guardar
referencias privadas de forma restringida, fuera de Git. Una captura sin fecha,
fuente o dispositivo no acredita el caso. No adjuntar evidencia privada sólo
porque esta plantilla está en un repositorio público.

- Hallazgos, limitaciones y enlaces a incidencias sanitizadas: PENDIENTE.
- Revisión independiente del resultado físico: PENDIENTE.
- Conclusión de alcance observado: NO EJECUTADO; sin declaración de release.
