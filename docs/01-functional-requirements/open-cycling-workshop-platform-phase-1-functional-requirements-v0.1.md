# Fase 1 · Functional Architecture & Requirements Engineering v0.1

## Objetivo

Convertir la visión aprobada en requisitos verificables y trazables antes de ADRs, threat modeling, UX, repositorio y QA.

## Convenciones

- `FR`: Functional Requirement
- `NFR`: Non Functional Requirement
- `BR`: Business Rule
- `SEC`: Security Requirement
- `OFF`: Offline / Sync Requirement
- `ACC`: Accessibility Requirement

## Roles iniciales

Owner, Administrator, Manager, Mechanic, Sales, Reception, Viewer y Technical Admin. La autorización final será capability based y los roles serán bundles configurables.

## Functional Requirements

### Identity & Access

- `FR-IAM-001` Crear usuarios locales con rol y estado.
- `FR-IAM-002` Autenticar en standalone, LAN y conectado.
- `FR-IAM-003` Recuperación de credenciales compatible con topología.
- `FR-IAM-004` Autorización por capability.
- `FR-IAM-005` Auditoría de autenticación y administración sensible.
- `FR-IAM-006` Cierre de sesiones conectadas cuando exista servidor.
- `FR-IAM-007` MFA opcional en modos conectados.
- `FR-IAM-008` Separar permisos técnicos de acceso comercial y personal.

### Customers

- `FR-CUS-001` Crear cliente con información mínima configurable.
- `FR-CUS-002` Buscar por nombre, teléfono, email, identificadores y tags.
- `FR-CUS-003` Editar con auditoría cuando corresponda.
- `FR-CUS-004` Múltiples medios y preferencia de contacto.
- `FR-CUS-005` Consentimiento por propósito y canal.
- `FR-CUS-006` Múltiples bicicletas por cliente.
- `FR-CUS-007` Historial unificado.
- `FR-CUS-008` Fusión auditable de duplicados.
- `FR-CUS-009` Exportación interoperable.
- `FR-CUS-010` Anonimización o eliminación conforme a política.

### Bicycles

- `FR-BIK-001` Crear bicicleta sin orden activa.
- `FR-BIK-002` Propietario actual e historial de transferencia cuando aplique.
- `FR-BIK-003` Datos técnicos y custom fields.
- `FR-BIK-004` Fotografías categorizadas.
- `FR-BIK-005` Componentes y cambios históricos.
- `FR-BIK-006` Historial de servicio.
- `FR-BIK-007` QR interno.
- `FR-BIK-008` Exportación del Bicycle Passport.
- `FR-BIK-009` El QR no expone PII.
- `FR-BIK-010` Bicicletas y piezas no catalogadas soportadas.

### Service Orders

- `FR-SVC-001` Orden desde entidades existentes o nuevas.
- `FR-SVC-002` Separar problema reportado de diagnóstico técnico.
- `FR-SVC-003` Intake con condición, accesorios y evidencia.
- `FR-SVC-004` Prioridad, responsable, fecha y ubicación.
- `FR-SVC-005` State machine validada.
- `FR-SVC-006` Diagnóstico y recomendaciones.
- `FR-SVC-007` Presupuesto con labor, parts, taxes y discounts.
- `FR-SVC-008` Versionado de presupuestos.
- `FR-SVC-009` Autorización, rechazo o autorización parcial con evidencia.
- `FR-SVC-010` Tareas y checklists.
- `FR-SVC-011` Reserva y consumo de inventario.
- `FR-SVC-012` Pausas y WAITING_FOR_PARTS.
- `FR-SVC-013` QC configurable antes de READY.
- `FR-SVC-014` Retrabajo sin pérdida de evidencia.
- `FR-SVC-015` Cierre sujeto a condiciones.
- `FR-SVC-016` Timeline auditable.
- `FR-SVC-017` Notas internas y visibles separadas.
- `FR-SVC-018` Comprobantes de recepción y entrega.

### Inventory & Purchasing

- `FR-INV-001` Productos, variantes, SKU, EAN, categorías y unidades.
- `FR-INV-002` Ubicaciones y stock por ubicación.
- `FR-INV-003` Todo cambio mediante InventoryMovement.
- `FR-INV-004` Stock derivado del ledger.
- `FR-INV-005` Stock mínimo y alertas.
- `FR-INV-006` Costo, precio y margen.
- `FR-INV-007` Proveedores.
- `FR-INV-008` Purchase orders y recepciones parciales.
- `FR-INV-009` Devolución, daño, pérdida, donación y reuse.
- `FR-INV-010` Inventario físico con ajustes compensatorios.
- `FR-INV-011` Productos no inventariables y servicios.
- `FR-INV-012` Compatibilidad extensible.

### POS & Payments

- `FR-POS-001` Venta independiente o vinculada a orden.
- `FR-POS-002` Productos, servicios, descuentos e impuestos.
- `FR-POS-003` Múltiples métodos de pago.
- `FR-POS-004` Pagos parciales.
- `FR-POS-005` Ticket configurable.
- `FR-POS-006` Devoluciones compensatorias.
- `FR-POS-007` Caja opcional.
- `FR-POS-008` No almacenar secretos PCI.
- `FR-POS-009` Registro offline conciliable cuando aplique.

### Communications

- `FR-COM-001` Provider interface común.
- `FR-COM-002` Templates con variables seguras.
- `FR-COM-003` WhatsApp deep link como fallback.
- `FR-COM-004` Envío automatizado con provider.
- `FR-COM-005` Estado de entrega cuando exista.
- `FR-COM-006` Respetar consentimientos.
- `FR-COM-007` Queue offline.
- `FR-COM-008` Idempotencia anti duplicados.
- `FR-COM-009` Templates white label e i18n.
- `FR-COM-010` Separar transactional, operational y marketing.

### Customer Portal

- `FR-PRT-001` Enlace seguro y revocable.
- `FR-PRT-002` Solo datos customer visible.
- `FR-PRT-003` Aprobar, rechazar o aprobar parcialmente.
- `FR-PRT-004` Evidencia de versión y timestamp.
- `FR-PRT-005` Fotos, saldo, documentos y recomendaciones.
- `FR-PRT-006` Rotación de enlace.
- `FR-PRT-007` Prevención de enumeración.

### Knowledge

- `FR-KNW-001` Artículos y procedimientos versionados.
- `FR-KNW-002` Fuente Manufacturer, Workshop o Community.
- `FR-KNW-003` Checklists por servicio o bicicleta.
- `FR-KNW-004` Torques y especificaciones con procedencia.
- `FR-KNW-005` Relación con componentes y tareas.
- `FR-KNW-006` Búsqueda offline.
- `FR-KNW-007` Advertencias sobre datos no oficiales o desactualizados.

### Automation

- `FR-AUT-001` Evento + condiciones + acciones.
- `FR-AUT-002` Versionar y habilitar reglas.
- `FR-AUT-003` Acciones idempotentes.
- `FR-AUT-004` Log de ejecución.
- `FR-AUT-005` Retries configurables.
- `FR-AUT-006` Dead letter o revisión manual.
- `FR-AUT-007` Communication, reminder, webhook, update y task actions.
- `FR-AUT-008` Permisos al ejecutar plugins.

### Plugins

- `FR-PLG-001` Manifest versionado.
- `FR-PLG-002` Validar compatibilidad.
- `FR-PLG-003` Mostrar permisos.
- `FR-PLG-004` Enable, disable y update.
- `FR-PLG-005` Aislar fallos cuando sea viable.
- `FR-PLG-006` Migraciones y rollback cuando corresponda.
- `FR-PLG-007` Hooks documentados.
- `FR-PLG-008` Sin acceso implícito a secretos o datos.
- `FR-PLG-009` Fixtures y contract tests.

### White Label

- `FR-WL-001` Branding sin editar código.
- `FR-WL-002` Dominio y contacto configurables.
- `FR-WL-003` Branding en portal, documentos y mensajes.
- `FR-WL-004` Feature flags.
- `FR-WL-005` Import/export de BrandProfile.
- `FR-WL-006` Validación de contraste cuando sea viable.

## Offline & Sync Requirements

- `OFF-001` CRUD crítico offline.
- `OFF-002` Inventario y ventas offline según políticas.
- `OFF-003` Queue persistente.
- `OFF-004` UUID locales.
- `OFF-005` Idempotencia.
- `OFF-006` Estado de sync visible.
- `OFF-007` Persistencia tras reinicios.
- `OFF-008` Conflictos por estrategia de entidad.
- `OFF-009` Append only o compensación para datos sensibles.
- `OFF-010` Adjuntos grandes en background.
- `OFF-011` Fallo externo no bloquea Core.
- `OFF-012` Resolución manual cuando no haya merge seguro.
- `OFF-013` Evitar mensajes y cobros duplicados al reconectar.
- `OFF-014` Soporte de topología LAN.

## Non Functional Requirements

- `NFR-001` PWA instalable.
- `NFR-002` Windows + Android tablet como targets principales.
- `NFR-003` Cero API comercial obligatoria para arrancar.
- `NFR-004` API versionada.
- `NFR-005` Migraciones probadas.
- `NFR-006` Backup y restore verificables.
- `NFR-007` Test coverage por criticidad.
- `NFR-008` i18n desde diseño.
- `NFR-009` Moneda, timezone, tax y units configurables.
- `NFR-010` Graceful degradation.
- `NFR-011` Rendimiento en hardware modesto.
- `NFR-012` Observability opcional y privacy preserving.
- `NFR-013` Desarrollo local reproducible.
- `NFR-014` Docs versionadas con código.

## Security Requirements

- `SEC-001` Argon2id.
- `SEC-002` Least privilege.
- `SEC-003` Audit log de operaciones sensibles.
- `SEC-004` Anti enumeration.
- `SEC-005` Secret management.
- `SEC-006` TLS remoto.
- `SEC-007` Plugin permissions.
- `SEC-008` Dependency scanning.
- `SEC-009` Validación de attachments.
- `SEC-010` Threat model obligatorio antes de V1.0.

## Accessibility Requirements

- `ACC-001` WCAG 2.2 AA.
- `ACC-002` Keyboard operability.
- `ACC-003` Focus visible.
- `ACC-004` No color only state.
- `ACC-005` Touch targets para Workshop Mode.
- `ACC-006` Reduced motion.
- `ACC-007` Zoom.
- `ACC-008` Accessible names.
- `ACC-009` Theme contrast validation.
- `ACC-010` Sync y error states anunciables.

## Business Rules

- `BR-001` Bicycle puede existir sin orden.
- `BR-002` Orden referencia bicicleta y responsable del momento.
- `BR-003` Problema reportado y diagnóstico son datos distintos.
- `BR-004` Presupuesto enviado conserva versión.
- `BR-005` Autorización referencia versión concreta.
- `BR-006` Stock solo cambia por movimientos.
- `BR-007` Correcciones financieras son compensatorias.
- `BR-008` READY puede exigir QC.
- `BR-009` Notas internas nunca salen al portal por defecto.
- `BR-010` Marketing respeta consentimiento.
- `BR-011` Fallo externo no revierte operación local válida.
- `BR-012` Plugin no adquiere permisos implícitos.
- `BR-013` Transferencia de bicicleta no transfiere PII anterior automáticamente.
- `BR-014` Conocimiento comunitario muestra procedencia.
- `BR-015` Cierre no elimina timeline.

## Workflows críticos

### Recepción a entrega

```text
Cliente → Bicicleta → Intake → Inspección → Diagnóstico → Presupuesto → Autorización → Cola → Reparación → Inventario → QC → READY → Notificación → Pago → Entrega → CLOSED
```

### Falla de Internet

```text
Offline → persist local mutation → pending sync → reconnect → retry idempotent → resolve conflicts → synced
```

### Waiting for parts

```text
DIAGNOSIS / IN_PROGRESS → WAITING_FOR_PARTS → purchase/reservation → receive → QUEUED / IN_PROGRESS
```

### Rework

```text
QUALITY_CONTROL → failed → REWORK → task/evidence → QUALITY_CONTROL → READY
```

## Edge cases prioritarios

Cliente sin contacto, bicicleta sin serial, duplicados creados offline, ventas concurrentes sobre última unidad, presupuesto cambiado después de autorización, pago offline, mensaje manual y automático duplicado, attachments sin sincronizar, cambio de propietario, plugin fallando, reloj de dispositivo incorrecto, restore sobre datos nuevos, cambio de SKU, múltiples rechazos de QC y revocación de consentimiento con comunicaciones programadas.

## Criterios transversales de aceptación

- `AC-001` Mutations críticas confirmadas localmente sobreviven cierre inesperado.
- `AC-002` Reconexión no duplica órdenes, movimientos, pagos ni mensajes.
- `AC-003` Estados synced, pending y conflict son visibles.
- `AC-004` Cambios sensibles quedan auditados.
- `AC-005` Fallo de WhatsApp no bloquea reparación ni venta.
- `AC-006` La instalación arranca sin SaaS comercial.
- `AC-007` White label no rompe mínimos de accesibilidad.
- `AC-008` API documenta errores, idempotency y versionado.
- `AC-009` Cada FR de V1 se enlaza a pruebas.
- `AC-010` Restore probado en entorno limpio antes de V1.0.

## Definition of Done

Implementación trazable, permisos, pruebas unitarias e integración según criticidad, E2E para flujos críticos, prueba offline y reconexión cuando aplique, accesibilidad, documentación, migraciones, logging seguro y criterios de aceptación satisfechos.

## Decisiones abiertas controladas

- IndexedDB vs SQLite WASM: spike técnico V0.1.
- Sync exacto: ADR + prototipo de conflictos.
- AGPLv3: revisión jurídica final.
- Monorepo vs multi repo: Fase 5.
- Tauri: solo cuando PWA no cubra hardware.
- WhatsApp provider: nunca dependencia del Core.
- Portable Bicycle Passport: después de estabilizar el modelo interno.

## Próximas fases

Fase 2 Technical Architecture & ADRs, Fase 3 Security / Privacy / Threat Model, Fase 4 UX/UI & Design System, Fase 5 Repository & Engineering Architecture, Fase 6 QA / Testing Strategy, Fase 7 Deployment & Operations, Fase 8 Open Source Governance, Fase 9 Commercial Implementation Playbook y consolidación final del Spec Development maestro.
