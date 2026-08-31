# Fase 9 · Commercial Implementation Playbook v0.1

**Open Cycling Workshop Platform**  
Baseline: Foundation v0.2 · Functional Requirements v0.1 · Technical Architecture v0.2 · Security/Privacy v0.1 · UX/UI v0.1 · Repository & Engineering Architecture v0.1 · QA/Verification v0.1 · Deployment/Operations v0.1 · Governance/Plugin Ecosystem v0.1  
License baseline: `AGPL-3.0-only`

> Este documento convierte la plataforma open source en una oferta profesional, repetible y económicamente sostenible para freelancers, agencias, cooperativas e integradores. El cliente no paga por una licencia propietaria del Core. Paga por diagnóstico, implementación, personalización, white labeling, migración, infraestructura, capacitación, soporte, integraciones, operación administrada y desarrollo especializado.

## 1. Objetivo de la fase

La Fase 9 define cómo llevar una instalación desde el primer contacto comercial hasta una operación estable y transferible. Sus objetivos son:

1. Definir segmentos de cliente y criterios de calificación.
2. Estandarizar discovery, levantamiento, propuesta, alcance y aceptación.
3. Crear paquetes comerciales sin convertir AGPL en una falsa licencia propietaria.
4. Definir pricing en MXN basado en alcance, riesgo, valor y esfuerzo.
5. Integrar trueque, descuentos sociales y esquemas mixtos sin degradar sostenibilidad.
6. Estandarizar white labeling, migraciones, hardware, capacitación y go-live.
7. Diseñar soporte recurrente, hosting administrado y niveles de servicio.
8. Establecer unit economics y márgenes mínimos para implementadores.
9. Reducir customizaciones irrepetibles mediante configuración, plugins y upstreaming.
10. Producir un handover que preserve autonomía y portabilidad del cliente.

## 2. Principios comerciales no negociables

### COM-P01 · Software libre, servicio profesional

El precio de implementación no se presenta como precio de licencia del Core. La propuesta debe distinguir claramente software open source y servicios profesionales.

### COM-P02 · Sin lock-in artificial

El cliente puede obtener sus datos, configuración y código correspondiente. Hosting administrado, soporte o integraciones pueden cancelarse conforme al contrato sin inutilizar deliberadamente el Core.

### COM-P03 · Alcance explícito

Nada se vende bajo descripciones ambiguas como "personalización ilimitada" o "soporte total". Cada entregable tiene límites, exclusiones y criterios de aceptación.

### COM-P04 · Riesgo se cotiza

Migraciones históricas, hardware incierto, integraciones no documentadas, multisucursal y procesos fiscales incrementan precio porque incrementan trabajo y riesgo.

### COM-P05 · No competir sólo por precio

La ventaja comercial es una implementación profesional, offline first, resiliente y adaptable. Reducir precio sin reducir alcance destruye margen y calidad.

### COM-P06 · Reutilizar antes de customizar

Una necesidad se resuelve, en orden de preferencia, mediante configuración, feature flag, plugin existente, plugin nuevo reutilizable y finalmente cambio específico de cliente.

### COM-P07 · Trueque valorizado

El trueque se registra con valor monetario acordado. No se acepta como mecanismo para ocultar descuentos indefinidos ni costes operativos recurrentes.

### COM-P08 · Impacto social con sostenibilidad

Talleres comunitarios, cooperativas y proyectos sociales pueden acceder a paquetes solidarios, pero los descuentos deben financiarse explícitamente mediante capacidad disponible, patrocinio o cross-subsidy.

### COM-P09 · Handover desde el inicio

Credenciales, dominios, backups y datos deben poder quedar bajo control del cliente. La relación comercial se conserva por valor, no por dependencia técnica.

### COM-P10 · Cambios upstream cuando beneficien al ecosistema

Las mejoras generalizables se diseñan para upstream o plugin público cuando sea viable, respetando privacidad y obligaciones contractuales.

## 3. Qué se comercializa

El catálogo comercial se divide en líneas separables:

- discovery y diagnóstico operativo
- instalación y configuración
- white labeling
- migración de datos
- capacitación
- hardware y periféricos
- hosting administrado
- backups y disaster recovery administrados
- integraciones
- plugins personalizados
- soporte y mantenimiento
- observabilidad
- multisucursal
- seguridad y hardening
- auditoría y optimización
- desarrollo de nuevas funciones
- acompañamiento de go-live

## 4. Qué no se comercializa como licencia

No se factura "derecho a usar Open Cycling Workshop Platform" como si el Core fuera propietario.

Es válido cobrar por:

- distribución preparada
- instalación
- infraestructura
- configuración
- mantenimiento
- trabajo de desarrollo
- soporte
- SLA

La factura y propuesta deben describir el servicio real prestado.

## 5. Segmentación comercial

| Segmento                              | Perfil típico                                | Complejidad | Oferta inicial recomendada |
| ------------------------------------- | -------------------------------------------- | ----------- | -------------------------- |
| Microtaller                           | 1 a 2 personas, servicio mecánico            | Baja        | Community / Starter        |
| Taller independiente                  | 2 a 8 personas                               | Media       | Workshop Standard          |
| Tienda + taller                       | ventas, inventario y servicio                | Media/Alta  | Workshop Commerce          |
| Taller móvil                          | operación desde tablet y campo               | Media       | Workshop Mobile            |
| Cooperativa                           | gobernanza compartida y presupuesto sensible | Media       | Community Pro              |
| Bike fitting / servicio especializado | agenda y expediente                          | Media       | Specialist                 |
| Flotilla pequeña                      | mantenimiento interno                        | Alta        | Fleet Module               |
| Multisucursal                         | varias ubicaciones                           | Alta        | Multi-site                 |
| Organización social                   | taller comunitario o educativo               | Variable    | Social Impact              |

## 6. Ideal Customer Profile inicial

El ICP prioritario para primeras implementaciones es un taller o tienda con taller que cumpla la mayoría de estas condiciones:

- 2 a 10 personas trabajando
- al menos 15 órdenes de servicio mensuales
- inventario mantenido en hoja de cálculo, libreta o POS no integrado
- uso frecuente de WhatsApp con clientes
- dolor por seguimiento de estados
- información repetida entre recepción y mecánicos
- voluntad de estandarizar procesos
- una persona responsable de decisiones
- disponibilidad de al menos un PC o tablet razonablemente moderno
- aceptación de una fase de onboarding y capacitación

## 7. Señales de alta oportunidad

- órdenes perdidas o incompletas
- mensajes de clientes preguntando repetidamente por estado
- inventario sin trazabilidad
- cobros y servicios desconectados
- duplicación de registros
- fotografías dispersas en teléfonos
- presupuestos sin autorización auditable
- varias personas usando la misma cuenta
- crecimiento que ya supera libretas o spreadsheets
- interés en profesionalizar la experiencia del cliente

## 8. Señales de riesgo comercial

- cliente exige "todo ilimitado" por un precio fijo bajo
- no existe responsable interno
- se niega a respaldos o capacitación
- requiere reemplazar un ERP completo en una semana
- depende de integraciones propietarias sin API disponible
- solicita ocultar obligaciones AGPL
- desea automatizar comunicaciones sin consentimiento
- exige almacenar credenciales personales de terceros
- no acepta alcance ni criterios de aceptación
- espera soporte 24/7 sin presupuesto correspondiente

## 9. Qualification score

Se adopta una puntuación de 0 a 2 por dimensión:

| Dimensión          | 0            | 1                      | 2             |
| ------------------ | ------------ | ---------------------- | ------------- |
| Dolor operativo    | bajo         | moderado               | crítico       |
| Decisor            | ausente      | parcial                | disponible    |
| Presupuesto        | incierto     | limitado               | alineado      |
| Procesos           | caóticos     | parcialmente definidos | documentables |
| Datos              | inexistentes | dispersos              | migrables     |
| Hardware           | insuficiente | parcial                | adecuado      |
| Apertura al cambio | baja         | media                  | alta          |
| Urgencia           | indefinida   | trimestre              | 30 días       |

Interpretación:

- 0 a 6: nurture o discovery pagado
- 7 a 11: oportunidad viable con riesgos
- 12 a 16: prioridad comercial

## 10. Funnel recomendado

```text
Lead
  ↓
Qualification
  ↓
Discovery pagado o ligero
  ↓
Solution Fit
  ↓
Proposal
  ↓
Contract / SOW
  ↓
Deposit
  ↓
Implementation
  ↓
UAT
  ↓
Go-live
  ↓
Stabilization
  ↓
Managed Support / Handover
```

## 11. Discovery: modalidad

### 11.1 Discovery ligero

Para microtalleres simples puede incluir una sesión remota de 45 a 60 minutos y un cuestionario estructurado.

### 11.2 Discovery profesional

Para tienda + taller, multisucursal o migración compleja se cobra como entregable independiente.

Incluye:

- entrevistas
- shadowing cuando sea viable
- mapa de procesos
- inventario de sistemas actuales
- riesgos
- matriz de roles
- mapa de datos
- alcance recomendado
- propuesta de topología
- estimación

## 12. Precio de discovery

Rangos recomendados en México, antes de IVA cuando corresponda:

| Tipo     | Alcance                                   | Precio recomendado MXN |
| -------- | ----------------------------------------- | ---------------------: |
| Light    | 1 sesión + checklist                      |        $1,500 a $3,000 |
| Standard | 2 a 4 sesiones + diagnóstico              |        $4,000 a $8,000 |
| Complex  | multisucursal / migración / integraciones |      $9,000 a $20,000+ |

El importe de discovery puede acreditarse parcialmente contra implementación cuando mejore cierre comercial, sin regalar análisis complejo.

## 13. Discovery questionnaire mínimo

### Operación

- ¿Cuántas órdenes ingresan por día, semana y mes?
- ¿Cómo se recibe actualmente una bicicleta?
- ¿Quién diagnostica?
- ¿Cómo se autoriza un presupuesto?
- ¿Cómo se registra una pieza utilizada?
- ¿Cómo se notifica que una bicicleta está lista?
- ¿Cómo se cobra?

### Inventario

- ¿Cuántos SKU aproximados existen?
- ¿Hay variantes?
- ¿Se utilizan códigos de barras?
- ¿Cuántos proveedores?
- ¿Cuántas ubicaciones físicas?

### Tecnología

- PCs y sistemas operativos
- tablets
- impresoras
- lectores
- red local
- acceso a Internet
- dominio
- correo
- WhatsApp Business

### Riesgo

- datos personales sensibles o innecesarios
- información fiscal
- backups actuales
- incidentes previos
- personas con acceso administrativo

## 14. Workshop process map

El implementador debe mapear al menos:

```text
Llegada
→ Intake
→ Inspección
→ Diagnóstico
→ Presupuesto
→ Autorización
→ Cola
→ Reparación
→ QC
→ Notificación
→ Cobro
→ Entrega
→ Seguimiento
```

Cada desviación del flujo estándar debe identificarse como configuración, plugin o customización.

## 15. Solution Fit Matrix

| Necesidad             | Core           | Configuración | Plugin          | Custom  |
| --------------------- | -------------- | ------------- | --------------- | ------- |
| Clientes y bicicletas | Sí             | —             | —               | —       |
| Órdenes               | Sí             | Sí            | —               | —       |
| Inventario            | Sí             | Sí            | —               | —       |
| POS                   | Módulo oficial | Sí            | —               | —       |
| WhatsApp              | —              | —             | Connector       | —       |
| CFDI México           | —              | —             | Jurisdictional  | Posible |
| Renta                 | —              | —             | Module          | —       |
| Flotillas             | —              | —             | Module          | Posible |
| Reporte específico    | —              | Posible       | Report provider | Posible |

## 16. Arquitectura comercial por capas

Una implementación se cotiza como suma explícita de capas:

```text
Base Implementation
+ Discovery
+ Branding
+ Data Migration
+ Integrations
+ Hardware
+ Training
+ Go-live
+ Recurring Operations
+ Custom Development
```

Esto evita que un único precio oculte riesgos heterogéneos.

## 17. Marco de pricing

El precio se determina mediante cuatro variables:

### Scope

Cantidad y complejidad de módulos, usuarios, sucursales e integraciones.

### Risk

Calidad de datos, hardware, dependencias externas, migraciones y criticidad.

### Service Level

Velocidad de respuesta, horario, disponibilidad y operación administrada.

### Value

Reducción de errores, trazabilidad, ahorro de tiempo, experiencia de cliente y capacidad de crecimiento.

## 18. Tarifa interna de referencia

Para estimar trabajos no paquetizables se recomienda una tarifa interna efectiva, no necesariamente mostrada al cliente:

| Perfil comercial              | Tarifa efectiva orientativa MXN/h |
| ----------------------------- | --------------------------------: |
| Implementador independiente   |                     $750 a $1,250 |
| Especialista senior           |                   $1,000 a $1,600 |
| Agencia pequeña               |                   $1,100 a $1,800 |
| Trabajo urgente / alto riesgo |                       +25% a +60% |

Estas cifras son una política recomendada, no una tarifa obligatoria del proyecto.

## 19. Calibración externa 2026

Como referencia de mercado, no como regla de pricing, Clutch reporta en 2026 que la mayoría de compañías de software listadas cobra aproximadamente USD 25 a 49 por hora y que proveedores que sirven México aparecen en rangos desde USD 25 hasta USD 99 por hora, dependiendo de firma y especialización.

La plataforma recomienda competir por especialización, cercanía operativa y reducción del riesgo de implementación, no por ser la opción más barata.

## 20. Paquetes comerciales recomendados

### 20.1 Community Launch

Para microtaller, cooperativa pequeña o proyecto social con operación simple.

Incluye:

- discovery ligero
- instalación Standalone o LAN mínima
- branding básico
- clientes y bicicletas
- órdenes de servicio
- 1 plantilla de checklist
- 1 importación CSV simple
- capacitación remota básica
- 14 días de estabilización

**Rango recomendado: $6,900 a $12,900 MXN**

### 20.2 Workshop Standard

Para taller independiente profesional.

Incluye:

- discovery Standard
- topología LAN o Cloud sencilla
- Core de taller
- inventario básico
- portal de cliente
- QR
- plantillas de comunicación
- white labeling
- hasta 5 usuarios configurados
- migración acotada
- 2 sesiones de capacitación
- 30 días de estabilización

**Rango recomendado: $16,900 a $29,900 MXN**

### 20.3 Workshop Commerce

Para tienda + taller.

Incluye lo anterior más:

- catálogo
- inventory ledger completo
- POS
- compras y proveedores
- impresiones operativas
- roles ampliados
- dashboard administrativo
- hasta 10 usuarios iniciales
- integración de comunicación estándar

**Rango recomendado: $32,900 a $59,900 MXN**

### 20.4 Workshop Pro

Para operación con procesos especiales, mayor automatización o soporte intensivo.

Incluye:

- discovery profundo
- arquitectura Cloud o LAN administrada
- automatizaciones
- integrations package
- migration package ampliado
- hardening
- observabilidad
- documentación de operación
- capacitación por rol
- 60 días de estabilización

**Rango recomendado: $55,000 a $95,000 MXN**

### 20.5 Multi-site

Para varias ubicaciones o una organización con alta criticidad.

Incluye:

- discovery complejo
- arquitectura multisucursal
- strategy de sincronización y conectividad
- permisos por location
- migración amplia
- DR administrado
- capacitación por sucursal
- rollout progresivo
- soporte de lanzamiento

**Rango recomendado: $90,000 a $180,000+ MXN**

## 21. Por qué los rangos no son licencias

Dos talleres pueden usar exactamente el mismo Core AGPL y pagar importes diferentes porque el servicio profesional puede variar en:

- número de sesiones
- complejidad de datos
- personalización
- infraestructura
- integraciones
- capacitación
- riesgo
- soporte
- urgencia

## 22. Social Impact Package

Puede aplicarse a:

- talleres comunitarios
- cooperativas
- asociaciones sin fines de lucro
- proyectos educativos
- programas de movilidad sostenible

Mecanismos posibles:

- descuento de 15% a 40% sobre servicios seleccionados
- horas pro bono limitadas
- patrocinio por tercero
- trueque parcial
- implementación comunitaria compartida

El descuento nunca debe eliminar costes recurrentes que el implementador no pueda absorber.

## 23. Trueque

El trueque es aceptable cuando ambas partes lo entienden y valoran explícitamente.

Ejemplos:

- mantenimiento de bicicleta
- componentes
- herramienta
- espacio de trabajo
- servicios profesionales
- alimentos o productos del negocio
- promoción o colaboración verificable

## 24. Regla de valorización del trueque

Ejemplo:

```text
Implementación:            $18,000 MXN
Pago monetario:             $12,000 MXN
Trueque acordado:            $6,000 MXN
Valor total contractual:    $18,000 MXN
```

La descripción del trueque debe indicar cantidad, valor, fecha límite y mecanismo ante incumplimiento.

## 25. Límite recomendado de trueque

Para proyectos comerciales ordinarios:

- hasta 25% del setup como regla segura
- hasta 50% cuando el bien o servicio tenga utilidad directa y liquidez razonable
- 100% sólo en proyectos deliberadamente sociales o estratégicos

Hosting, dominios, proveedores externos y otros costes en efectivo no deberían cubrirse con trueque salvo que el implementador lo decida conscientemente.

## 26. Payment schedule

Para proyectos de implementación fija se recomienda:

```text
40% al contratar
30% al aprobar configuración / staging
20% antes de go-live
10% al cerrar estabilización
```

En proyectos pequeños puede utilizarse 50% / 50%.

En proyectos complejos se prefieren hitos facturables mensuales.

## 27. Change requests

Todo cambio fuera de SOW se clasifica:

- clarification: sin impacto
- minor change: absorbible dentro del contingency
- change request: cotización adicional
- new phase: proyecto separado

Un cliente no obtiene funcionalidades ilimitadas por descubrir nuevas necesidades durante implementación.

## 28. Contingency

Cada propuesta fija debe incluir internamente contingencia:

- bajo riesgo: 10%
- riesgo medio: 15% a 20%
- migración / integración alta: 25% a 35%

La contingencia no se comunica necesariamente como una línea separada al cliente.

## 29. White labeling

Se cotiza por niveles.

### Basic

- logo
- nombre
- colores
- favicon
- datos de contacto

**$1,500 a $4,000 MXN**

### Professional

Basic más:

- design token tuning
- emails
- PDF
- tickets
- portal
- plantillas de mensajes

**$4,500 a $10,000 MXN**

### Brand Extension

Professional más trabajo de diseño específico y assets nuevos.

**$10,000 MXN en adelante**

## 30. Customización visual vs fork

El implementador no debe crear un fork por cambiar colores, logotipo o copy.

White labeling debe resolverse mediante `BrandProfile`, design tokens y configuración.

Un fork sólo se justifica cuando existe una divergencia estructural que no puede resolverse razonablemente mediante extensión.

## 31. Migración de datos

La migración se divide en:

1. inventory
2. customers
3. bicycles
4. suppliers
5. historical orders
6. balances o movimientos cuando aplique
7. media

## 32. Migration tiers

| Tier | Descripción                           | Precio orientativo MXN |
| ---- | ------------------------------------- | ---------------------: |
| M0   | sin migración                         |                     $0 |
| M1   | CSV limpio, hasta 500 registros       |        $1,500 a $4,000 |
| M2   | múltiples archivos / 5,000 registros  |       $5,000 a $12,000 |
| M3   | datos sucios, mapping y deduplicación |      $12,000 a $30,000 |
| M4   | legado / API / histórico complejo     |               $30,000+ |

## 33. Migration dry run

Toda migración M2 o superior requiere:

```text
Extract
→ Normalize
→ Map
→ Dry Run
→ Reconciliation
→ Client Review
→ Final Import
→ Evidence
```

## 34. Reconciliation

Antes de aceptación se comparan al menos:

- registros fuente
- registros importados
- errores
- duplicados
- totales de inventario relevantes
- muestras manuales

No se promete migración "100% automática" sin validar calidad de fuente.

## 35. Integraciones

Cada integración se cotiza por separado según:

- API oficial disponible
- autenticación
- límites de uso
- sandbox
- webhooks
- SLA externo
- coste del proveedor
- mantenimiento esperado

## 36. WhatsApp

Se ofrecen progresivamente:

### WA0 · Link

Abrir conversación con texto prellenado.

### WA1 · Templates

Plantillas operativas copiables.

### WA2 · Business Platform

Automatización mediante proveedor/API oficial cuando corresponda.

### WA3 · Integrated Inbox

Sólo cuando la API y el caso de uso lo justifiquen.

Los cargos variables del proveedor se trasladan o se incluyen mediante una bolsa explícita. Nunca se promete tarifa perpetua porque políticas y precios externos pueden cambiar.

## 37. Email

SMTP puede utilizar infraestructura del cliente o proveedor administrado.

Se separan:

- coste de configuración
- coste del proveedor
- reputación y dominio
- plantillas
- monitoreo de entrega

## 38. Pagos

El Core no almacena datos completos de tarjeta.

Los costes de Stripe, Mercado Pago u otros procesadores se consideran pass-through y no forman parte del fee de implementación salvo acuerdo explícito.

## 39. Fiscalización

Los módulos fiscales son jurisdiccionales.

Para México, cualquier implementación CFDI debe presupuestar:

- proveedor PAC cuando corresponda
- pruebas
- certificados o configuración requerida
- actualizaciones regulatorias
- soporte separado

No debe venderse como parte gratuita del Core general.

## 40. Hardware

Hardware opcional:

- tablet
- mini PC
- UPS
- impresora térmica
- impresora de etiquetas
- scanner de códigos
- router / AP
- almacenamiento externo
- QR labels

## 41. Política de hardware

Se definen tres modelos:

### BYOD

El cliente usa hardware existente validado.

### Recommended Kit

El implementador recomienda modelos compatibles y el cliente compra directamente.

### Managed Hardware

El implementador compra, configura y entrega con margen comercial explícito.

## 42. Margen de hardware

Cuando el implementador asume compra, configuración, garantía logística y riesgo, un margen de 10% a 25% puede ser razonable además de la configuración técnica.

No se recomienda revender hardware sin margen si el implementador asumirá soporte posterior.

## 43. UPS para LAN

En una instalación LAN profesional se recomienda evaluar UPS para:

- servidor local
- router
- switch
- AP principal

Esto protege operaciones ante cortes breves y reduce corrupción por apagados abruptos.

## 44. Site readiness checklist

Antes de instalar:

- [ ] energía estable
- [ ] red disponible
- [ ] dispositivos soportados
- [ ] cuentas administrativas identificadas
- [ ] dominio y DNS cuando aplique
- [ ] inventario de impresoras
- [ ] datos de migración congelados o coordinados
- [ ] usuarios y roles aprobados
- [ ] responsable del cliente designado
- [ ] horario de go-live acordado

## 45. Implementation plan estándar

```text
Kickoff
→ Environment readiness
→ Install
→ Configure
→ Brand
→ Migrate dry run
→ Integrate
→ Train champions
→ UAT
→ Final migration
→ Go-live
→ Stabilization
→ Handover / Managed Service
```

## 46. Roles de implementación

### Implementer Lead

Responsable del resultado técnico y comercial.

### Client Owner

Toma decisiones de alcance y aceptación.

### Operational Champion

Persona del taller que conoce los procesos y participa en UAT.

### Technical Custodian

Responsable de credenciales, infraestructura y backups, puede ser cliente o implementador.

## 47. RACI mínimo

| Actividad     | Implementador | Client Owner | Champion |
| ------------- | ------------- | ------------ | -------- |
| Discovery     | R             | A            | C        |
| Configuración | R             | C            | C        |
| Migración     | R             | A            | C        |
| UAT           | C             | A            | R        |
| Capacitación  | R             | C            | R        |
| Go-live       | R             | A            | R        |
| Handover      | R             | A            | C        |

R = Responsible, A = Accountable, C = Consulted.

## 48. UAT

El cliente debe validar journeys reales, no una demo genérica.

Escenarios mínimos:

1. alta de cliente
2. alta de bicicleta
3. orden completa
4. presupuesto y autorización
5. consumo de inventario
6. QC
7. notificación
8. cobro
9. entrega
10. consulta de historial

Si POS está incluido, se agrega venta y devolución.

## 49. UAT acceptance

Se utiliza un documento de aceptación que registre:

- casos ejecutados
- aprobados
- defectos abiertos
- excepciones conocidas
- items post-go-live
- responsable
- fecha

## 50. Capacitación

Se diseña por rol.

### Owner / Admin

Configuración, usuarios, reportes, backups, excepciones.

### Reception

Clientes, bicicletas, intake, presupuestos y comunicaciones.

### Mechanic

Workshop Mode, tareas, piezas, fotos, checklists y QC.

### Sales

POS, búsqueda, stock, ventas y devoluciones.

## 51. Training format

Cada sesión idealmente incluye:

```text
Explain
→ Demonstrate
→ Guided Practice
→ Independent Practice
→ Questions
→ Quick Reference
```

## 52. Champion model

En talleres con más de cuatro usuarios se recomienda capacitar primero a una o dos personas champion para reducir dependencia del implementador.

## 53. Training pricing

| Modalidad                |     Precio orientativo MXN |
| ------------------------ | -------------------------: |
| Remota 60 a 90 min       |              $900 a $1,800 |
| Presencial media jornada | $2,500 a $5,000 + viáticos |
| Presencial día completo  | $4,500 a $8,000 + viáticos |
| Train-the-trainer        |           $4,000 a $10,000 |

## 54. Go-live strategy

### Big Bang

Adecuado sólo para instalaciones simples.

### Parallel

Sistema nuevo y método anterior conviven brevemente.

### Phased

Se activa por módulo, equipo o ubicación.

Multi-site utiliza phased rollout por defecto.

## 55. Go-live window

Se elige una ventana con menor carga operativa posible y disponibilidad del champion.

Evitar deliberadamente momentos de alta demanda si puede programarse una alternativa.

## 56. Go-live checklist

- [ ] release aprobada
- [ ] backup pre-go-live
- [ ] migración final reconciliada
- [ ] usuarios verificados
- [ ] permisos revisados
- [ ] impresoras probadas
- [ ] offline probado
- [ ] sincronización probada
- [ ] comunicaciones probadas
- [ ] soporte disponible
- [ ] rollback/recovery plan disponible

## 57. Stabilization period

Se recomienda:

- Community: 14 días
- Standard / Commerce: 30 días
- Pro: 60 días
- Multi-site: 60 a 90 días

Stabilization corrige defectos de implementación acordados. Nuevas funciones siguen change control.

## 58. Warranty de implementación

Puede ofrecerse una garantía limitada para defectos atribuibles a la configuración o customización entregada.

No incluye:

- cambios del cliente
- proveedores externos
- hardware defectuoso
- requisitos nuevos
- modificaciones no autorizadas
- versiones fuera de soporte

## 59. Managed Support

El soporte recurrente es una línea comercial independiente.

### Care

**$900 a $1,500 MXN/mes**

- actualización mensual o coordinada
- backup verification básico
- soporte remoto limitado
- revisión de salud

### Workshop Managed

**$1,800 a $3,500 MXN/mes**

- hosting o LAN management según alcance
- backups
- actualizaciones
- monitoreo
- 2 a 4 h de soporte
- reporte mensual breve

### Priority

**$4,000 a $8,000+ MXN/mes**

- mayor bolsa de soporte
- tiempos de respuesta definidos
- observabilidad
- incident coordination
- revisión trimestral

## 60. Hosting

El hosting debe mostrarse como coste o servicio separado.

Opciones:

1. cliente paga infraestructura directamente
2. implementador administra infraestructura del cliente
3. implementador revende servicio administrado

El modelo 1 maximiza portabilidad. El modelo 3 puede generar margen recurrente, pero requiere procesos operativos maduros.

## 61. Pass-through costs

Deben separarse cuando sea razonable:

- dominio
- VPS
- email provider
- object storage
- WhatsApp
- SMS
- PAC
- payment processor
- backup storage
- monitorización externa

## 62. Margin sobre infraestructura

Si el implementador sólo reenvía una factura automática sin valor adicional, el margen debe ser moderado.

Si ofrece provisioning, hardening, backups, soporte, monitoreo y responsabilidad operacional, el margen pertenece al servicio administrado y no sólo al precio bruto del VPS.

## 63. SLA vs support plan

Un plan de soporte no implica automáticamente SLA.

Un SLA debe definir:

- horas de cobertura
- severidades
- tiempo de respuesta
- objetivo de restauración
- exclusiones
- canal
- escalación

## 64. Severidades comerciales

### P1

Operación central completamente detenida o riesgo de corrupción.

### P2

Función central degradada sin workaround razonable.

### P3

Problema parcial con workaround.

### P4

Consulta, mejora o defecto menor.

## 65. SLA ejemplo

| Plan      | P1 respuesta  | P2            | P3          | Cobertura         |
| --------- | ------------- | ------------- | ----------- | ----------------- |
| Community | best effort   | best effort   | best effort | laboral           |
| Managed   | 4 h laborales | 1 día laboral | 2 días      | laboral           |
| Priority  | 1 h laboral   | 4 h laborales | 1 día       | ampliada acordada |

24/7 se cotiza separadamente y no se ofrece por defecto a un microtaller.

## 66. Scope de soporte

Soporte puede cubrir:

- incidentes
- configuración
- actualización
- backups
- dudas
- pequeños ajustes

No debe incluir automáticamente:

- desarrollo de features
- migraciones nuevas
- rediseños
- integraciones nuevas
- capacitación ilimitada

## 67. Support hour bank

Una bolsa de horas puede venderse prepagada con caducidad razonable.

Ejemplo:

| Bolsa | Precio recomendado MXN |
| ----- | ---------------------: |
| 5 h   |        $4,500 a $6,000 |
| 10 h  |       $8,500 a $11,000 |
| 20 h  |      $16,000 a $20,000 |

## 68. Custom development

Desarrollo específico se presupuesta con:

```text
Discovery
+ Design
+ Development
+ Tests
+ Documentation
+ Release
+ Maintenance Impact
```

No se cotizan sólo "horas de código".

## 69. Plugin comercial

Un plugin de cliente puede ser:

### Private deployment

El código correspondiente se entrega conforme a obligaciones aplicables y contrato.

### Public upstream plugin

Se publica y el cliente financia su desarrollo inicial.

### Shared-cost plugin

Varios clientes financian una función reutilizable.

Este tercer modelo puede ser especialmente atractivo para verticales ciclistas.

## 70. Maintenance surcharge

Una customización que genera una rama difícil de actualizar debe tener coste recurrente superior.

La propuesta debe explicar que upstreaming o pluginización reduce TCO.

## 71. Technical debt premium

Si el cliente exige una solución que contradice arquitectura o seguridad, el implementador puede:

1. rechazarla
2. proponer alternativa
3. cotizar un spike

Nunca debe ocultar deuda técnica como si fuera una implementación estándar.

## 72. Unit economics del implementador

Cada proyecto debe registrar:

```text
Revenue
- Direct labor
- External costs
- Travel
- Hardware risk
- Support reserve
- Payment fees
= Contribution Margin
```

## 73. Target contribution margin

Para servicios profesionales pequeños se recomienda apuntar a un contribution margin de al menos **45% a 60%** antes de gastos generales e impuestos.

Proyectos con incertidumbre alta requieren mayor colchón.

## 74. Ejemplo de unit economics

Workshop Standard vendido en $24,900 MXN:

| Concepto                            | Importe MXN |
| ----------------------------------- | ----------: |
| Ingreso                             |     $24,900 |
| 16 h trabajo a costo interno $600/h |     -$9,600 |
| Infra / herramientas iniciales      |       -$600 |
| Reserva soporte                     |     -$1,500 |
| Contingencia utilizada              |     -$1,000 |
| Contribución                        |     $12,200 |
| Margen aproximado                   |         49% |

El objetivo es demostrar si el precio sostiene realmente la atención profesional prometida.

## 75. Internal cost rate

La tarifa de coste no es el salario por hora. Debe incluir:

- tiempo no facturable
- administración
- impuestos
- equipo
- herramientas
- vacaciones
- ventas
- formación
- riesgo

Subestimar este valor produce proyectos aparentemente rentables que consumen caja.

## 76. Minimum project floor

Salvo estrategia deliberada, un proyecto que requiera reuniones, discovery, instalación y soporte no debería venderse por debajo del valor de 6 a 8 horas efectivas más costes y contingencia.

Esto protege especialmente a freelancers frente a pequeños trabajos que consumen más coordinación que ejecución.

## 77. Discount policy

Descuentos sólo se justifican por:

- alcance reducido
- pago anticipado
- caso de estudio autorizado
- proyecto social
- múltiples sucursales repetibles
- reutilización real
- referral

No por presión genérica de negociación.

## 78. Maximum discretionary discount

Como regla comercial, el descuento discrecional sin reducir alcance no debería exceder 10%.

Descuentos mayores requieren una contrapartida explícita o aprobación interna del implementador.

## 79. Referral model

Puede utilizarse:

- crédito para soporte
- comisión 5% a 10%
- descuento en siguiente módulo

Debe evitar crear promesas perpetuas de comisión sobre ingresos sin contrato claro.

## 80. Partner model

Tipos:

- implementation partner
- hardware partner
- cycling association partner
- training partner
- referral partner
- plugin maintainer

Ninguno obtiene exclusividad sobre el proyecto open source.

## 81. Commercial proposal structure

Una propuesta profesional debe contener:

1. contexto
2. problemas observados
3. resultado esperado
4. alcance
5. exclusiones
6. topología
7. entregables
8. cronograma por hitos
9. responsabilidades del cliente
10. inversión
11. pagos
12. aceptación
13. soporte
14. AGPL y source availability
15. protección de datos
16. vigencia de la propuesta

## 82. SOW structure

El Statement of Work debe referenciar requisitos y entregables versionados.

No es necesario insertar todo el spec técnico, pero sí identificar claramente:

- módulos
- plugins
- topología
- usuarios/sucursales incluidas
- volumen de migración
- integraciones
- training
- acceptance criteria

## 83. Client responsibilities

Se documentan al menos:

- proporcionar datos
- designar owner
- participar en UAT
- validar contenido y branding
- gestionar permisos de servicios externos
- mantener hardware acordado
- no compartir credenciales
- informar cambios de procesos

## 84. Commercial assumptions

Ejemplos:

- datos se entregan en fecha acordada
- APIs externas permanecen disponibles
- hardware cumple soporte mínimo
- el cliente responde dentro de ventanas acordadas
- no se modifican requerimientos críticos sin change request

Las assumptions reducen disputas sobre causas externas.

## 85. Contract boundaries

El playbook recomienda asesoría jurídica local para contratos, privacidad, facturación y obligaciones específicas.

El contrato comercial no debe contradecir derechos otorgados por AGPL.

## 86. Data Processing

Cuando el implementador opera infraestructura o accede a datos personales, el contrato debe distinguir:

- responsable del tratamiento
- encargado / processor cuando aplique
- finalidad
- acceso
- retention
- breach process
- subprocesadores

No se utiliza una cláusula genérica como sustituto de análisis jurídico local.

## 87. Security responsibilities

La propuesta define quién controla:

- admin accounts
- OS patching
- container updates
- domain
- DNS
- backup destination
- secrets
- incident response

Responsabilidad difusa equivale a riesgo operativo.

## 88. Source code handoff

Cuando corresponda, el implementador entrega o expone:

- versión
- commit
- upstream URL
- source de modificaciones
- plugin source aplicable
- build instructions razonables

White labeling no elimina esta obligación.

## 89. Credential ownership

Recomendación:

- dominio en cuenta del cliente
- DNS bajo acceso del cliente
- proveedor cloud preferiblemente a nombre del cliente en proyectos importantes
- implementador como administrador delegado

Para microtalleres managed puede aceptarse cuenta del implementador, pero debe existir exit plan.

## 90. Handover package

Debe incluir:

```text
Deployment Manifest
Architecture Summary
Admin Accounts Inventory
Backup Location
Restore Procedure
Version and Commit
Enabled Plugins
Configuration Export
Data Export Procedure
Support Contacts
Known Limitations
AGPL Source Link
```

## 91. Exit plan

Un cliente que cancela managed service debe poder recibir:

- export de datos
- configuración
- backups pactados
- source correspondiente
- instrucciones de transición razonables

Trabajo extraordinario de migración a otro proveedor puede cobrarse, pero no debe bloquearse artificialmente.

## 92. Case study

Con autorización, una implementación puede generar:

- problema inicial
- proceso
- resultados medibles
- capturas anonimizadas
- testimonio

El permiso de marketing debe ser explícito y separado del uso ordinario de la plataforma.

## 93. KPIs de implementación

- tiempo de alta de orden
- porcentaje de órdenes con estado actualizado
- errores de inventario
- tiempo de respuesta al cliente
- porcentaje de autorizaciones digitales
- retrabajos
- adoption rate
- usuarios activos
- incidencias de soporte

## 94. ROI model

No se prometen ahorros ficticios. Se calcula con datos del cliente.

Ejemplo:

```text
horas administrativas ahorradas
× coste real por hora
+
reducción estimada de errores verificables
+
ventas recuperadas atribuibles
-
coste total de implementación
```

## 95. Value review

A los 30 o 90 días puede realizarse una revisión para identificar:

- procesos todavía manuales
- módulos no adoptados
- nuevos cuellos de botella
- automatizaciones
- entrenamiento adicional
- próximos módulos

Esta sesión es una oportunidad comercial legítima cuando aporta valor real.

## 96. Expansion paths

Después de V1 del cliente:

```text
Inventory Advanced
Purchasing
Automations
Analytics
Rental
Fleet
Ecommerce
Fiscal
AI optional
IoT optional
```

No se intenta vender todos los módulos desde el primer día.

## 97. Land and expand responsable

La expansión debe responder a necesidades observadas, no a dark patterns ni dependencia técnica.

La relación recurrente se sostiene por:

- soporte competente
- mejoras
- conocimiento del negocio
- confiabilidad
- respuesta

## 98. Account review cadence

Para Managed y Priority:

- revisión mensual ligera
- revisión trimestral amplia

Incluye:

- salud
- backups
- uso
- incidencias
- roadmap relevante
- riesgos
- oportunidades

## 99. Renewal

Los servicios recurrentes pueden renovarse mensual o anualmente.

El anual puede ofrecer 5% a 10% de ventaja a cambio de prepago y menor administración.

## 100. Price review

Los contratos recurrentes deben permitir revisión de precio, por ejemplo anual, ante inflación, infraestructura o ampliación de alcance.

No se promete precio nominal perpetuo.

## 101. Scope creep signals

- "ya que estás ahí"
- usuarios adicionales con nuevas responsabilidades
- segunda sucursal no cotizada
- histórico completo después de cotizar sólo datos actuales
- integración nueva
- nuevo canal de soporte
- reportes personalizados continuos

El implementador debe identificar estos cambios temprano.

## 102. Anti-pattern: regalar discovery

Una llamada corta de venta puede ser gratuita. Una auditoría de procesos, mapeo, arquitectura o análisis de migración es trabajo profesional y debe poder cobrarse.

## 103. Anti-pattern: soporte ilimitado

"Soporte ilimitado" en proyectos pequeños crea incentivos incorrectos y dificulta capacidad.

Se prefieren:

- bolsa
- fair use cuantificado
- incident scope
- SLA definido

## 104. Anti-pattern: customizar el Core por cliente

Una modificación aislada parece rápida, pero aumenta coste de actualización.

Primero se intenta configuración o plugin.

## 105. Anti-pattern: vender Cloud cuando LAN resuelve mejor

Una suscripción mensual mayor no justifica sacrificar resiliencia offline.

El implementador debe recomendar la topología adecuada incluso si genera menos ingreso recurrente.

## 106. Anti-pattern: administrar todo en cuentas personales

Dominios, repositorios, email, cloud y backup no deben depender de cuentas personales sin plan de continuidad.

## 107. Anti-pattern: no cobrar estabilización

El periodo posterior a go-live consume trabajo real. Debe estar incluido explícitamente o cotizado.

## 108. Pre-sales demo

La demo oficial utiliza `demo-workshop` con datos ficticios y debe mostrar un journey completo:

```text
Cliente
→ Bicicleta
→ Orden
→ Diagnóstico
→ Autorización
→ Reparación
→ Inventory movement
→ Ready
→ Portal
→ Pago
→ Entrega
```

## 109. Demo offline

Una demo comercial diferenciadora debe poder desconectar Internet y continuar creando una operación, luego mostrar la sincronización posterior.

Esto comunica el valor arquitectónico de manera inmediata.

## 110. Proposal calculator

Se recomienda crear posteriormente una herramienta interna con inputs:

- package
- locations
- users
- migration tier
- integrations
- branding
- training
- hardware
- SLA
- urgency
- discount
- barter

Salida:

- precio
- coste estimado
- margen
- payment schedule
- recurring revenue

## 111. Estimation formula interna

```text
Price =
  Base Package
+ Migration
+ Integrations
+ Branding
+ Training
+ Hardware Service
+ Risk Premium
+ Urgency Premium
- Authorized Discount
```

La fórmula es una guía, no un algoritmo que sustituya juicio profesional.

## 112. Risk premium

Puede añadirse 10% a 30% cuando exista:

- datos inciertos
- API externa inestable
- deadline rígido
- hardware no validado
- personalización sustancial
- coordinación con terceros

## 113. Urgency premium

Un proyecto que exige desplazar trabajo planificado o trabajar fuera de horario puede añadir:

- +20% urgente
- +35% muy urgente
- +50% o más para ventana extraordinaria

El implementador también puede rechazar fechas irresponsables.

## 114. Travel and onsite

Viáticos y traslados se presupuestan separados cuando sean materiales.

El trabajo presencial no debe absorber transporte y tiempo no facturable sin consideración.

## 115. Taxes

Los precios del playbook son orientativos y se expresan antes de impuestos salvo indicación distinta.

Cada implementador debe facturar y cumplir obligaciones fiscales conforme a su jurisdicción.

## 116. MXN price maintenance

Los rangos deben revisarse al menos una vez al año o cuando cambien significativamente:

- inflación
- costes de infraestructura
- madurez del producto
- demanda
- capacidad
- alcance estándar

## 117. International pricing

Fuera de México no se realiza una conversión mecánica de MXN.

Se recalibra según:

- mercado local
- complejidad
- soporte
- impuestos
- riesgo contractual
- poder adquisitivo cuando sea parte de una estrategia social

## 118. Procurement readiness

Para clientes empresariales se preparan:

- datos fiscales del proveedor
- SOW
- DPA cuando corresponda
- security overview
- architecture summary
- SLA
- insurance si se exige
- vendor questionnaire

## 119. Supportability gate antes de vender

No se ofrece como paquete estándar una función que no tenga:

- documentación suficiente
- tests
- upgrade path
- observabilidad básica
- owner
- recovery story

La presión comercial no bypassa release qualification.

## 120. Commercial release gates

Antes de declarar V1 comercialmente implementable:

| Gate         | Condición                      |
| ------------ | ------------------------------ |
| COM-GATE-001 | paquetes y alcance publicados  |
| COM-GATE-002 | demo-workshop reproducible     |
| COM-GATE-003 | demo offline reproducible      |
| COM-GATE-004 | discovery checklist versionado |
| COM-GATE-005 | proposal template              |
| COM-GATE-006 | SOW template                   |
| COM-GATE-007 | UAT template                   |
| COM-GATE-008 | handover template              |
| COM-GATE-009 | pricing calculator interno     |
| COM-GATE-010 | migration tiers documentados   |
| COM-GATE-011 | training material por rol      |
| COM-GATE-012 | support plans definidos        |
| COM-GATE-013 | SLA examples definidos         |
| COM-GATE-014 | trueque policy definida        |
| COM-GATE-015 | AGPL language en propuestas    |
| COM-GATE-016 | source handoff procedure       |
| COM-GATE-017 | exit plan documentado          |
| COM-GATE-018 | managed service runbook        |
| COM-GATE-019 | unit economics revisables      |
| COM-GATE-020 | case-study consent separado    |

## 121. Artefactos comerciales objetivo

La Fase 9 debe originar posteriormente plantillas independientes:

```text
docs/09-commercial/
├── implementation-playbook.md
├── discovery-questionnaire.md
├── qualification-scorecard.md
├── proposal-template.md
├── sow-template.md
├── pricing-calculator.md
├── migration-questionnaire.md
├── uat-template.md
├── training-plan.md
├── go-live-checklist.md
├── support-plans.md
├── sla-template.md
├── handover-template.md
├── exit-plan.md
└── case-study-consent.md
```

## 122. Roadmap comercial por madurez

### Commercial Alpha

- 1 a 3 implementaciones controladas
- precio con contingency elevada
- feedback intensivo
- ningún SLA agresivo

### Commercial Beta

- paquetes repetibles
- migration tooling maduro
- soporte normalizado
- primeras referencias

### Commercial V1

- QA y OPS gates completos
- contratos y handover estandarizados
- directorio de implementadores posible
- supportability demostrada

## 123. Early adopter strategy

Las primeras instalaciones deben seleccionarse por capacidad de aprendizaje, no sólo por cierre rápido.

Idealmente incluir:

1. microtaller
2. taller con inventario
3. tienda + taller

Esto valida diferentes patrones sin saltar directamente a multisucursal.

## 124. Feedback loop comercial

```text
Implementation
→ Support Data
→ Customer Feedback
→ Product Issue / RFC
→ Prioritization
→ Release
→ Commercial Playbook Update
```

Las promesas comerciales no se convierten automáticamente en roadmap.

## 125. Ethical sales

No se utilizarán:

- datos falsos de ahorro
- urgencia artificial
- dark patterns
- lock-in oculto
- greenwashing
- claims ambientales no verificables

Cuando el módulo de economía circular exista, sus métricas deben basarse en datos trazables y metodologías documentadas.

## 126. Ciclismo, reparación y economía circular

La narrativa comercial puede destacar legítimamente:

- prolongación de vida útil
- mantenimiento preventivo
- reparación
- reutilización
- trazabilidad de componentes
- movilidad ciclista

sin atribuir impactos ambientales cuantificados cuando no exista metodología válida.

## 127. Cooperative implementation model

Para cooperativas puede ofrecerse:

- capacitación técnica ampliada
- control directo de infraestructura
- documentation-first handover
- soporte decreciente
- contribución upstream

Esto permite que la organización adquiera autonomía real.

## 128. Community sponsorship

Una empresa o asociación puede financiar implementaciones para talleres comunitarios.

El patrocinador no adquiere control sobre los datos del beneficiario ni privilegios de gobernanza sobre el proyecto.

## 129. Commercial neutrality

El proyecto upstream no certifica que un implementador sea el único o mejor proveedor.

Un futuro directorio puede utilizar criterios transparentes como:

- contribuciones
- referencias
- regiones
- idiomas
- servicios
- security training

## 130. Indicadores del negocio del implementador

Además de métricas técnicas:

- lead-to-discovery rate
- discovery-to-close rate
- average setup revenue
- recurring revenue
- gross contribution margin
- support hours por cliente
- revenue por implementation hour
- churn de managed support
- referrals
- expansion revenue
- overdue receivables

## 131. Alertas de rentabilidad

Revisar una cuenta si:

- consume >150% de horas incluidas durante 2 meses
- solicita cambios fuera de scope repetidamente
- infraestructura crece sin ajuste de plan
- soporte reactivo impide mantenimiento preventivo
- margen de contribución cae por debajo del objetivo

La respuesta puede ser re-scope, capacitación, automatización o ajuste de precio.

## 132. Commercial ADRs

| ID          | Decisión                                    | Estado   |
| ----------- | ------------------------------------------- | -------- |
| COM-ADR-001 | vender servicios, no licencia propietaria   | Accepted |
| COM-ADR-002 | pricing por alcance/riesgo/valor            | Accepted |
| COM-ADR-003 | discovery complejo es facturable            | Accepted |
| COM-ADR-004 | paquetes con rangos, no precio universal    | Accepted |
| COM-ADR-005 | trueque valorizado contractualmente         | Accepted |
| COM-ADR-006 | managed support separado de implementación  | Accepted |
| COM-ADR-007 | pass-through costs visibles                 | Accepted |
| COM-ADR-008 | no soporte ilimitado                        | Accepted |
| COM-ADR-009 | handover y exit plan obligatorios           | Accepted |
| COM-ADR-010 | customización vía plugins antes de fork     | Accepted |
| COM-ADR-011 | margen objetivo 45% a 60%                   | Accepted |
| COM-ADR-012 | descuentos sociales explícitos              | Accepted |
| COM-ADR-013 | multisucursal requiere discovery complejo   | Accepted |
| COM-ADR-014 | hardware tiene margen cuando se administra  | Accepted |
| COM-ADR-015 | cloud no se fuerza si LAN es mejor          | Accepted |
| COM-ADR-016 | COM gates bloquean declaración comercial V1 | Accepted |

## 133. Riesgos residuales comerciales

### R-COM-001 · Subpricing

Mitigación: tarifa interna, contingency, unit economics y minimum project floor.

### R-COM-002 · Scope creep

Mitigación: SOW, change control y UAT explícito.

### R-COM-003 · Dependencia del implementador

Mitigación: credential ownership, handover y exit plan.

### R-COM-004 · Integración externa cambia precio o API

Mitigación: adapter architecture, pass-through costs y revisión contractual.

### R-COM-005 · Custom branch imposible de actualizar

Mitigación: plugin-first y maintenance surcharge.

### R-COM-006 · Trueque sin liquidez

Mitigación: límites, valorización y costes externos en efectivo.

### R-COM-007 · Promesas comerciales sobrepasan calidad

Mitigación: supportability gate y release gates.

## 134. Fuentes de calibración pública

Los rangos comerciales de este documento son recomendaciones internas del proyecto, no promedios estadísticos. Como referencia pública de calibración consultada en agosto de 2026:

- Clutch · Software Development Company Pricing Guide 2026: https://clutch.co/developers/pricing
- Clutch · Top Software Developers in Mexico, July 2026: https://clutch.co/mx/developers

Clutch reporta que los proyectos y tarifas varían ampliamente, con muchas firmas listadas en USD 25 a 49 por hora y proveedores que sirven México en bandas superiores según especialización. Estos datos se utilizan sólo para evitar anclar el servicio profesional por debajo del mercado de desarrollo custom.

## 135. Handoff a Fase 10

Con producto, requisitos, arquitectura, seguridad, UX, ingeniería, QA, operaciones, gobernanza y comercialización ya documentados, la siguiente fase será **Spec Development Master & Execution System**.

Fase 10 deberá consolidar todo el material anterior en una especificación maestra ejecutable por humanos y agentes de IA, con:

- source of truth index
- dependency map
- requirements traceability
- implementation epics
- release plans V0.1 a V1.0
- task decomposition
- agent operating rules
- Definition of Ready / Done por tarea
- verification loop
- ADR workflow
- documentation update rules
- prompt maestro tipo loop
- checkpoints
- stop conditions
- recovery from failed implementation

La finalidad es que la construcción pueda avanzar de forma incremental sin perder las decisiones ya consolidadas ni permitir que un agente improvise arquitectura incompatible con el proyecto.
