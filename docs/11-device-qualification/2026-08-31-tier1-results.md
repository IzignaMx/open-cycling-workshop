# Resultados de Calificación Tier 1 · V0.1 · 2026-08-31

> Plantilla de registro. Completa cada campo con evidencia real; un paso sin evidencia NO se marca como pase. Adjunta capturas en `docs/11-device-qualification/evidence/`.

## Dispositivos

| Campo               | Windows                             | Android                                                   |
| ------------------- | ----------------------------------- | --------------------------------------------------------- |
| Modelo              | _(p. ej. PC ensamblado / Lenovo X)_ | _(p. ej. Samsung Galaxy Tab A9)_                          |
| OS + versión        | _Windows 11 26100)_                 | _(Android 14)_                                            |
| Navegador + versión | _(Chrome 1xx.0.xxxx)_               | _(Chrome 1xx.0.xxxx)_                                     |
| Modo PWA instalada  | _(sí/no)_                           | _(sí/no)_                                                 |
| Método de conexión  | localhost directo                   | _(A: USB adb reverse / B: flag origen seguro — IP usada)_ |

## Windows

| Paso                                         | Resultado (pass/fail/N/A) | Notas / evidencia |
| -------------------------------------------- | ------------------------- | ----------------- |
| W1 Login online                              | ☐                         |                   |
| W2 Instalación PWA                           | ☐                         |                   |
| W3 Offline: crear cliente                    | ☐                         |                   |
| W4 Reload offline persiste                   | ☐                         |                   |
| W5 Reconexión exactly-once (count en PG = 1) | ☐                         | `count = ___`     |
| W6 Conflicto visible + convergencia          | ☐                         |                   |
| W7 Smoke de teclado                          | ☐                         |                   |
| W8 Reinstalación (comportamiento registrado) | ☐                         |                   |

## Android

| Paso                                       | Resultado (pass/fail/N/A) | Notas / evidencia |
| ------------------------------------------ | ------------------------- | ----------------- |
| A1 Login online                            | ☐                         |                   |
| A2 Instalación PWA standalone              | ☐                         |                   |
| A3 Targets táctiles                        | ☐                         |                   |
| A4 Offline + reinicio de proceso persiste  | ☐                         |                   |
| A5 Conmutación de red sincroniza           | ☐                         | `count = ___`     |
| A6 Presión de almacenamiento (observación) | ☐                         |                   |
| A7 Cámara/archivos                         | N/A V0.1                  |                   |

## Hallazgos y mejoras detectadas

_(p. ej. necesidad de `navigator.storage.persist()`, targets pequeños, textos ilegibles — cada hallazgo genera issue)_

## Veredicto

- [ ] Windows Tier 1: APROBADO
- [ ] Android Tier 1: APROBADO
- [ ] Evidencia archivada en `docs/11-device-qualification/evidence/`
- Operador: ______________ · Fecha: ______
