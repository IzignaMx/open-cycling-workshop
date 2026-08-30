# Fase 3 · Security, Privacy & Threat Model v0.1

## 1. Objetivo

Definir amenazas, activos, trust boundaries, controles preventivos y detectivos, requisitos de privacidad y criterios verificables para la PWA offline, servidor LAN/Cloud, sincronización, portal, plugins, integraciones, documentos, backups y administración.

## 2. Postura

- Secure by default y least privilege.
- El cliente y la LAN se consideran no confiables.
- Autenticación, autorización y consentimiento son conceptos separados.
- PII y secretos se minimizan.
- Pagos, autorizaciones, inventario sensible y acciones administrativas son auditables.
- Plugins e integraciones son trust boundaries explícitos.
- La seguridad no debe destruir innecesariamente la disponibilidad offline.

## 3. Activos críticos

| ID | Activo | Criticidad |
|---|---|---|
| A-01 | Identidades y credenciales | Crítico |
| A-02 | PII de clientes | Alto |
| A-03 | Bicycle Passport | Alto |
| A-04 | Órdenes y autorizaciones | Crítico |
| A-05 | Pagos y caja | Crítico |
| A-06 | Inventario | Alto |
| A-07 | Mensajería | Alto |
| A-08 | Backups | Crítico |
| A-09 | Secrets de integraciones | Crítico |
| A-10 | Audit log | Crítico |
| A-11 | Plugins y supply chain | Crítico |
| A-12 | Disponibilidad offline | Crítico |

## 4. Trust boundaries

1. Usuario ↔ PWA.
2. PWA ↔ IndexedDB.
3. PWA ↔ Service Worker.
4. PWA ↔ API.
5. Cliente LAN ↔ servidor LAN.
6. API ↔ PostgreSQL.
7. Core ↔ Plugin.
8. Core ↔ proveedores externos.
9. Customer Portal ↔ Internet.
10. Backup ↔ storage.
11. CI/CD ↔ release artifacts.

## 5. Método

STRIDE para superficies técnicas, complementado por abuse cases y análisis de privacidad orientado a datos. El threat register se revisa en cada release.

## 6. Amenazas prioritarias

- Account takeover por credential stuffing.
- Manipulación offline de autorizaciones, pagos o inventario.
- Repudiation de autorizaciones.
- XSS con extracción de PII o tokens.
- Sync flooding y payload abuse.
- Elevación de privilegios manipulando requests.
- Pérdida o robo de dispositivo con working set offline.
- Plugin malicioso o vulnerable.
- Customer portal token enumeration/reuse.
- Replay de mutaciones.
- Backup exposure.
- Supply-chain compromise.
- Service Worker defect o cache poisoning.
- Sobreexposición de información a WhatsApp/email.
- Cross-tenant data access.
- Exposición pública de serial + propietario.
- Ransomware y pérdida local.

## 7. Identidad y autenticación

- Argon2id.
- Password policy basada en longitud y blocklist.
- Cookies `HttpOnly`, `Secure` y `SameSite` para web conectado.
- Refresh tokens rotatorios cuando sean necesarios.
- MFA TOTP/WebAuthn para administradores antes de V1.0.
- Recovery codes de un solo uso.
- Sin preguntas de seguridad.
- Login/recovery sin enumeración de cuentas.

## 8. Autorización

```text
subject + tenant + location + capability + resource scope + state
→ ALLOW / DENY
```

Deny by default. Las verificaciones viven en application services del servidor, no sólo en la interfaz.

## 9. Seguridad offline

- Working set mínimo necesario por rol/ubicación cuando sea viable.
- Session lock configurable.
- No se prometerá cifrado aplicativo de IndexedDB como sustituto del cifrado y seguridad del dispositivo.
- No almacenar tokens persistentes de alto privilegio en `localStorage`.
- Logout y cambio de usuario deben evitar mezcla de datos sin perder mutaciones pendientes de forma silenciosa.
- Estado de sincronización y operaciones pendientes siempre visible.

## 10. Sync security

- TLS obligatorio fuera de localhost.
- `operation_id` único para idempotencia.
- Server reauthorization al aplicar mutaciones.
- Payload schemas versionados y estrictos.
- Request/blob size limits.
- Cursor opaco emitido por servidor.
- No resolver silenciosamente conflictos críticos.
- Dead-letter state visible.
- Audit con actor, device, operation y correlation context.

## 11. Customer Portal

- Opaque token con al menos 128 bits de entropía efectiva.
- Token almacenado hasheado.
- Expiry y revocation.
- Scope mínimo por orden/acción.
- Sin IDs públicos secuenciales.
- Action-bound/one-time token para autorizaciones sensibles cuando aplique.
- Rate limiting, anomaly logging, `noindex` y security headers.

## 12. Plugins y supply chain

Trust levels: **Official, Verified, Community, Local/Unverified**.

Official releases generan SBOM, hashes y provenance/firma cuando sea viable. El manifest declara capabilities. Plugins no confiables no reciben secretos globales y los backend-code plugins tienen un trust level superior al de adapters/UI-only.

## 13. Privacidad

| ID | Principio |
|---|---|
| PD-01 | Data minimization |
| PD-02 | Purpose limitation |
| PD-03 | Private by default |
| PD-04 | Configurable retention |
| PD-05 | Export/portability |
| PD-06 | Deletion/anonymization donde proceda |
| PD-07 | Consent separado para comunicaciones |
| PD-08 | Vendor minimization |
| PD-09 | Telemetry transparente y deshabilitable |
| PD-10 | No surveillance de ciclistas |

## 14. Data classes

- **Public**: información comercial publicada explícitamente.
- **Internal**: configuración y notas internas no sensibles.
- **Confidential**: PII, historial, costos, proveedores.
- **Restricted**: credentials, secrets, recovery codes y payment-sensitive metadata.
- **Immutable/Audit**: autorizaciones, movimientos y eventos auditables.

## 15. Blobs

Allowlist de MIME, validación real de contenido, límites, re-encoding de imágenes cuando proceda, EXIF eliminado por defecto, nombres internos, downloads seguros y scanner opcional para archivos arbitrarios.

## 16. Backups y DR

- Estrategia recomendada 3-2-1.
- Cifrado de backup.
- Restore autorizado y auditado.
- Restore drills antes de V1.0 y periódicos.
- Metadata de schema/app incluida.
- RPO/RTO por perfil de deployment y probados.

## 17. Comunicaciones y pagos

- Payload mínimo a WhatsApp/email/SMS.
- Mensajes transaccionales separados de marketing.
- Consentimientos verificados para comunicaciones no transaccionales.
- No almacenar tarjetas completas.
- Hosted/tokenized payment flows.
- Webhooks con firma, anti-replay e idempotencia.

## 18. Requisitos verificables clave

1. Todos los commands server-side verifican capability y scope.
2. Passwords sólo con Argon2id.
3. Secrets no aparecen en logs.
4. Portal tokens son no enumerables y hasheados.
5. Sync replay no duplica efectos.
6. Ledgers/autorizaciones no admiten delete destructivo ordinario.
7. CSP y security headers se prueban.
8. Official releases generan SBOM y dependency scan.
9. Restore se prueba antes de V1.0.
10. Cross-tenant access siempre se deniega.
11. Uploads inválidos/excesivos se rechazan.
12. MFA disponible para admins antes de V1.0.
13. Audit events contienen contexto suficiente.
14. Telemetría no esencial puede deshabilitarse.
15. Logout/session expiry no mezcla datos entre usuarios.

## 19. Security release gates

- V0.1: threat model, secure coding baseline, SCA/SAST/secret scan.
- V0.2: RBAC y offline session tests.
- V0.3: inventory ledger integrity.
- V0.4: payment boundaries.
- V0.5: consent y webhook verification.
- V0.6: portal threat tests.
- V0.8: automation permission boundaries.
- V0.9: security review, OWASP testing, chaos/recovery.
- V1.0: ningún hallazgo Critical/High explotable sin riesgo aceptado explícitamente y mitigación.

## 20. Vulnerability management

`SECURITY.md`, canal privado, advisories/CVEs cuando aplique, severity por impacto real, backports según support policy y coordinated disclosure.

## 21. Riesgos residuales

- Un dispositivo completamente comprometido puede acceder al working set del usuario legítimo.
- Plugins mantienen riesgo permanente de supply chain.
- Providers externos heredan disponibilidad y riesgo propios.
- Offline crea ventanas temporales antes de conocer revocaciones remotas.
- Retention, privacidad y fiscalidad dependen de jurisdicción.

## 22. Licencia

La decisión oficial del proyecto es **GNU AGPL v3.0, `AGPL-3.0-only`** para Core y aplicaciones oficiales. Contribuciones mediante DCO inicialmente.

## 23. Próxima fase

Fase 4: UX/UI, Information Architecture y Design System con Workshop Mode, POS, customer portal, responsive/offline states, WCAG 2.2 AA, white labeling y design tokens.
