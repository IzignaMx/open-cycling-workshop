# Fase 8 · Open Source Governance, Contribution & Plugin Ecosystem v0.1

**Open Cycling Workshop Platform**  
Baseline: Foundation v0.2 · Functional Requirements v0.1 · Technical Architecture v0.2 · Security/Privacy v0.1 · UX/UI v0.1 · Repository & Engineering Architecture v0.1 · QA/Verification v0.1 · Deployment/Operations v0.1  
License baseline: `AGPL-3.0-only`

> Este documento define cómo gobernar, extender y sostener el proyecto como infraestructura open source para la industria ciclista. La gobernanza debe permitir decisiones técnicas rápidas sin volver el proyecto dependiente de una sola persona, proteger la libertad de usuarios y contribuidores, mantener seguridad del Core y hacer posible que implementadores independientes generen ingresos legítimos mediante servicios alrededor del software.

## 1. Objetivo de la fase

La Fase 8 establece la constitución operativa del proyecto y del ecosistema de extensiones. Sus objetivos son:

1. Formalizar el uso de GNU Affero General Public License v3.0 only como licencia del Core y aplicaciones oficiales.
2. Definir una ruta de contribución clara basada en DCO, revisión pública y trazabilidad.
3. Crear una estructura de roles que pueda evolucionar de proyecto fundador a gobernanza comunitaria distribuida.
4. Definir RFCs, ADRs, votaciones, conflictos de interés y autoridad de releases.
5. Diseñar un plugin ecosystem seguro, versionado, verificable y compatible con implementaciones comerciales.
6. Separar claramente código libre, trademarks, branding de clientes y servicios profesionales.
7. Establecer mecanismos de seguridad, moderación y respuesta ante plugins maliciosos o abandonados.
8. Evitar incentivos pay-to-merge o captura comercial del roadmap.
9. Crear vías legítimas de sostenibilidad para maintainers, desarrolladores, agencias e implementadores.
10. Reducir progresivamente el bus factor y publicar suficiente información para que el proyecto pueda sobrevivir a cambios de liderazgo.

## 2. Principios de gobernanza no negociables

### GOV-P01 · Libertad de uso y modificación

El Core permanece software libre bajo `AGPL-3.0-only`. No se añaden restricciones de campo de uso, cliente, industria, país o finalidad dentro de la licencia del programa.

### GOV-P02 · Transparencia por defecto

Roadmap, decisiones técnicas, RFCs, cambios de gobernanza, release notes y criterios de promoción de plugins son públicos salvo información temporalmente reservada por seguridad o privacidad.

### GOV-P03 · Mérito verificable

La autoridad comunitaria se obtiene mediante contribuciones sostenidas, revisión responsable y conducta consistente, no por patrocinio económico.

### GOV-P04 · Autoridad mínima necesaria

Los permisos de repositorio, releases, registry y seguridad se conceden según función y se revisan periódicamente.

### GOV-P05 · Sin pay-to-merge

Una organización puede financiar trabajo, pero no comprar aprobación técnica, prioridad de seguridad, inclusión en Core ni promoción a Official.

### GOV-P06 · Derecho a competir

Cualquier implementador puede vender instalación, soporte, personalización, hosting, capacitación o desarrollo sin pagar regalías al proyecto.

### GOV-P07 · Core conservador, ecosistema expansivo

El Core sólo absorbe capacidades universales. Funcionalidades verticales, jurisdiccionales o comerciales permanecen como módulos o plugins mientras sea técnicamente razonable.

### GOV-P08 · Seguridad antes que conveniencia

La extensibilidad no justifica ejecutar código comunitario arbitrario con privilegios del Core.

### GOV-P09 · Reversibilidad

Las decisiones relevantes deben documentar contexto y ruta de reversión. La comunidad puede sustituir una decisión cuando nueva evidencia técnica lo justifique.

### GOV-P10 · Continuidad institucional

Ningún secreto, dominio, release key, registry, backup o proceso esencial debe depender permanentemente de una única persona.

## 3. Licencia oficial

Se adopta de manera definitiva:

```text
SPDX-License-Identifier: AGPL-3.0-only
```

El repositorio raíz incluye el texto completo de GNU Affero General Public License versión 3 y cada archivo fuente propio utiliza encabezados SPDX compatibles con REUSE.

El identificador `AGPL-3.0-only` significa que el proyecto concede derechos bajo exactamente la versión 3, no automáticamente bajo versiones futuras.

## 4. Alcance de AGPL dentro del proyecto

### 4.1 Componentes oficiales bajo AGPL

Como política del proyecto, se publican bajo `AGPL-3.0-only`:

- backend Python
- PWA oficial
- worker y CLI operacionales
- Sync Engine
- paquetes UI propios con conocimiento sustancial del producto
- plugin SDK cuando contenga código derivado o estrechamente acoplado al Core
- plugins oficiales ejecutados in-process
- Customer Portal oficial
- herramientas oficiales de administración de la plataforma

### 4.2 Documentación

La documentación original del proyecto podrá utilizar `CC-BY-SA-4.0` cuando resulte conveniente para reutilización editorial, manteniendo ejemplos de código bajo la licencia indicada en cada archivo.

### 4.3 Assets y marcas

Logotipos, nombres, marcas y otros identificadores oficiales no quedan licenciados automáticamente por AGPL. Se administrarán mediante una política de trademarks independiente.

## 5. Cumplimiento de interacción remota

AGPL v3 exige que una versión modificada que permita interacción remota ofrezca a esos usuarios una oportunidad clara de obtener el Corresponding Source de esa versión.

La distribución oficial implementará de forma visible:

```text
About / Acerca de
  → Version
  → License
  → Source Code
```

La entrada **Source Code** debe apuntar a la fuente correspondiente de la versión efectivamente ejecutada o a un mecanismo equivalente que satisfaga la obligación aplicable.

El white labeling no puede eliminar el acceso requerido a licencia y fuente correspondiente cuando la obligación de AGPL resulte aplicable.

## 6. Política de modificaciones de clientes

Los implementadores pueden modificar y personalizar el software para clientes. Cuando esas modificaciones desencadenen obligaciones de AGPL, el implementador será responsable de proporcionar el Corresponding Source conforme a la licencia.

El proyecto facilitará esta obligación mediante:

- página Source Code configurable
- export de manifest de versión
- SBOM
- commit SHA visible para administradores
- archivo `SOURCE-OFFER.md` generado en builds
- tooling para producir source bundle de una release

La plataforma no debe inducir a implementadores a ocultar obligaciones de licencia.

## 7. Contributor legal pathway

Se adopta **Developer Certificate of Origin 1.1** mediante sign-off en commits.

Ejemplo:

```text
Signed-off-by: Nombre Apellido <correo@example.com>
```

El sign-off certifica que la persona tiene derecho a enviar la contribución bajo la licencia indicada y acepta que el registro de la contribución sea público.

No se adopta un Contributor License Agreement en V1.

## 8. Regla DCO en CI

Todo commit de contribución externa debe incluir sign-off válido.

CI verifica:

- existencia del trailer
- identidad sintácticamente válida
- correspondencia razonable con el autor del commit
- ausencia de commits sin certificación dentro del PR

Los maintainers pueden solicitar rebase o corrección del sign-off. No añadirán un sign-off en nombre de otra persona.

## 9. Copyright ownership

Cada contribuidor conserva el copyright sobre su contribución salvo acuerdo distinto explícito.

El proyecto no exige transferencia centralizada de copyright.

Esto reduce dependencia institucional y evita que una única entidad pueda relicenciar unilateralmente todo el código comunitario.

## 10. Relicensing

Cambiar la licencia del Core requeriría consentimiento suficiente de titulares de copyright o una base jurídica equivalente. La gobernanza no asumirá que un voto del Steering Council puede relicenciar contribuciones ajenas.

Una propuesta de relicensing se clasifica como **Constitutional RFC** y requiere revisión legal especializada antes de cualquier ejecución.

## 11. Código de Conducta

Se adopta **Contributor Covenant 2.1** como baseline, con un archivo `CODE_OF_CONDUCT.md` versionado.

La política se aplica a:

- repositorios
- issue trackers
- revisiones
- chats y foros oficiales
- reuniones
- eventos
- canales de soporte comunitario
- representación pública oficial del proyecto

Los reportes de conducta no deben realizarse mediante issues públicos cuando expongan a la persona afectada.

## 12. Enforcement de conducta

Se crea un pequeño **Community Conduct Team** separado, cuando sea posible, de las personas directamente involucradas en un conflicto.

El proceso mínimo incluye:

1. recepción privada
2. acknowledgement
3. evaluación de conflicto de interés
4. recopilación proporcional de evidencia
5. decisión documentada internamente
6. medida correctiva
7. comunicación a las partes cuando sea apropiado
8. registro privado de enforcement

No se publican detalles personales innecesarios.

## 13. Contributor ladder

La comunidad utiliza una progresión explícita:

```text
User
  ↓
Contributor
  ↓
Trusted Contributor
  ↓
Reviewer
  ↓
Module Maintainer
  ↓
Core Maintainer
  ↓
Steering Council eligibility
```

Los títulos son responsabilidades, no rangos sociales.

## 14. User

Puede utilizar, desplegar, reportar problemas, proponer ideas y participar en discusiones sin haber contribuido código.

El proyecto considera feedback operativo de talleres e implementadores una contribución válida al producto.

## 15. Contributor

Persona con al menos una contribución aceptada, como:

- código
- documentación
- traducción
- test case
- diseño
- reproducción de bug
- threat report responsable
- benchmark
- mejoras de accesibilidad

No obtiene permisos especiales de repositorio automáticamente.

## 16. Trusted Contributor

Puede obtener capacidad de triage después de demostrar contribuciones correctas y conducta estable.

Facultades típicas:

- etiquetar issues
- confirmar reproducciones
- organizar documentación
- solicitar información faltante
- participar en planning

No puede fusionar PRs al Core.

## 17. Reviewer

Un Reviewer puede emitir aprobación técnica reconocida en áreas específicas.

Requisitos orientativos:

- historial sostenido de contribuciones
- conocimiento del área
- calidad consistente de reviews
- comprensión de seguridad y compatibilidad
- ausencia de sanciones activas

La promoción requiere nominación por un maintainer y consentimiento de al menos otro maintainer cuando exista.

## 18. Module Maintainer

Responsable de uno o más bounded contexts, paquetes o plugins oficiales.

Ejemplos:

```text
workshop
inventory
sync
payments
plugin-sdk
customer-portal
```

Puede aprobar y fusionar cambios dentro de su scope cuando branch protection y CODEOWNERS lo permitan.

## 19. Core Maintainer

Responsable de coherencia transversal del producto.

Puede:

- revisar cambios cross-domain
- aprobar ADRs
- participar en releases
- aprobar cambios del plugin contract
- nombrar Reviewers y Module Maintainers conforme al proceso

No puede ignorar gates de seguridad o release sin documentar una excepción formal permitida.

## 20. Security Maintainer

Rol especializado con acceso a vulnerabilidades privadas, advisories y coordinación de disclosure.

Debe usar autenticación fuerte y no compartir material de embargo fuera del security response group.

## 21. Release Manager

Responsable de una release concreta, no propietario permanente del proceso.

Funciones:

- verificar qualification gates
- coordinar release candidate
- validar SBOM y provenance
- comprobar migration notes
- firmar o coordinar firma de artefactos
- publicar release notes

## 22. Steering Council

Órgano de última instancia para gobernanza, no para sustituir las decisiones técnicas ordinarias.

Responsabilidades:

- cambios constitucionales
- disputas de gobernanza no resueltas
- política de trademarks
- presupuesto comunitario
- elección y remoción de Core Maintainers
- custodios institucionales
- acuerdos con fundaciones u organizaciones anfitrionas

## 23. Fase de bootstrap

Durante la etapa temprana puede existir un **Founding Maintainer** con autoridad técnica final para evitar parálisis.

Esa autoridad debe disminuir automáticamente cuando se cumplan simultáneamente estos mínimos:

- al menos 3 Core Maintainers activos
- al menos 2 de ellos sin relación laboral directa entre sí
- al menos 2 Module Maintainers adicionales
- 90 días de actividad comunitaria sostenida
- proceso de release reproducible
- dos custodios independientes para activos críticos

Al alcanzar el umbral se activa el Steering Council ordinario.

## 24. Bus factor objetivo

Antes de V1.0 ningún sistema crítico debe tener únicamente una persona capaz de operarlo.

Objetivos:

| Activo | Mínimo V1 |
|---|---:|
| Release pipeline | 2 personas |
| Security advisories | 2 personas |
| Registry de plugins | 2 personas |
| Dominio y DNS | 2 custodios |
| Package publishing | 2 custodios |
| Backup de activos comunitarios | 2 custodios |
| Steering decisions | 3 miembros |

## 25. Recertificación de permisos

Trimestralmente se revisan:

- organización GitHub
- teams
- CODEOWNERS
- package registries
- container registry
- DNS
- secrets administrativos
- signing identities
- community moderation

Permisos no utilizados se reducen o eliminan.

## 26. Modelo de decisiones

Se utilizan cuatro mecanismos:

```text
Issue / discussion       → decisiones operativas pequeñas
ADR                      → decisión técnica interna
RFC                      → cambio significativo y público
Constitutional RFC       → licencia, gobernanza o trademarks
```

No todo cambio necesita una votación.

## 27. Lazy consensus

Para decisiones comunitarias ordinarias se prefiere lazy consensus.

Una propuesta pública con periodo definido puede aceptarse si:

- no existen objeciones técnicas bloqueantes justificadas
- los reviewers requeridos participaron
- CI y gates son verdes

Un simple silencio no puede aprobar un cambio constitucional.

## 28. RFC process

Todo RFC utiliza un identificador:

```text
RFC-0042-plugin-permission-model.md
```

Estados:

```text
Draft
Discussion
Final Comment Period
Accepted
Rejected
Withdrawn
Superseded
Implemented
```

## 29. Contenido mínimo de RFC

Un RFC debe contener:

- contexto
- problema
- objetivos
- no objetivos
- propuesta
- alternativas
- seguridad
- privacidad
- accesibilidad
- impacto offline
- compatibilidad
- migración
- operabilidad
- impacto en plugins
- plan de rollout
- reversibilidad

## 30. ADR frente a RFC

Un ADR registra la decisión técnica implementada.

Un RFC obtiene consenso para una modificación significativa del contrato público o del rumbo del proyecto.

Un RFC aceptado puede producir varios ADRs.

## 31. Final Comment Period

Cambios significativos reciben un FCP mínimo de 7 días naturales salvo incidente de seguridad.

Constitutional RFCs reciben al menos 21 días.

La fecha de cierre debe ser visible desde el inicio del FCP.

## 32. Votación

Cuando no sea posible alcanzar consenso:

- decisiones técnicas ordinarias: mayoría simple de Core Maintainers elegibles
- governance policy: mayoría de dos tercios del Steering Council
- Constitutional RFC: dos tercios del Steering Council y mayoría de Core Maintainers activos

Empates mantienen el estado existente mientras se obtiene nueva evidencia.

## 33. Conflictos de interés

Una persona debe declararse cuando una decisión pueda afectar materialmente a:

- su empresa
- un cliente
- un plugin que comercializa
- una organización que financia su trabajo
- una disputa personal relevante

Declarar conflicto no implica exclusión automática, pero puede requerir recusación.

## 34. Recusación

Es obligatoria para:

- enforcement de conducta donde la persona sea parte
- security disclosure de un producto competidor bajo relación contractual conflictiva
- decisiones sobre promoción de un plugin propio cuando exista alternativa razonable de reviewers independientes

## 35. Roadmap governance

El roadmap público se divide en:

```text
Committed
Candidate
Exploration
Community Proposed
```

`Committed` significa que existe capacidad real y criterios de aceptación. No se utiliza para promesas aspiracionales.

## 36. Fuentes de priorización

El roadmap considera:

- seguridad
- pérdida de datos
- necesidades de talleres reales
- deuda técnica
- accesibilidad
- maintainability
- adopción
- contributor capacity
- implementer feedback
- patrocinio económico

El patrocinio es una señal, no autoridad de decisión.

## 37. Issue taxonomy

Labels mínimos:

```text
kind/bug
kind/feature
kind/security
kind/docs
kind/accessibility
kind/performance
kind/refactor
kind/rfc
kind/plugin
area/sync
area/workshop
area/inventory
area/pos
area/platform
priority/p0..p3
status/needs-info
status/blocked
status/ready
status/help-wanted
status/good-first-issue
```

## 38. Triage

Objetivos comunitarios, no SLA contractual:

| Tipo | Primera revisión objetivo |
|---|---:|
| Security privada | 2 días hábiles |
| Pérdida de datos | 2 días hábiles |
| Bug crítico | 3 días hábiles |
| Bug ordinario | 7 días |
| Feature request | 14 días |

El incumplimiento no implica automáticamente soporte comercial debido.

## 39. Pull Request lifecycle

```text
Draft
  ↓
Ready for Review
  ↓
Automated Gates
  ↓
Codeowner Review
  ↓
Security / UX review if required
  ↓
Approved
  ↓
Merge Queue
  ↓
Merged
```

## 40. Revisión mínima

Para cambios ordinarios se requiere una aprobación de persona autorizada por CODEOWNERS.

Para cambios de alto riesgo se requieren dos aprobaciones independientes.

Alto riesgo incluye:

- authn/authz
- Sync Engine
- ledger
- pagos
- migraciones destructivas
- plugin permissions
- release tooling
- cryptography
- security boundaries

## 41. Self merge

Un maintainer no realiza self-merge de cambios de alto riesgo.

Cambios triviales de documentación pueden ser self-merged cuando todos los gates sean verdes y no modifiquen políticas.

## 42. Branch protection

`main` requiere:

- pull request
- CI verde
- CODEOWNERS cuando aplique
- DCO
- secret scanning
- no force push
- no branch deletion
- merge queue cuando el volumen lo justifique

## 43. CODEOWNERS

CODEOWNERS refleja responsabilidad real y evita listas nominales obsoletas.

Scopes importantes:

```text
/services/platform/src/.../sync/
/services/platform/src/.../identity/
/packages/plugin-sdk/
/.github/workflows/
/infra/
/docs/03-security-privacy/
```

## 44. Release authority

Una release estable requiere como mínimo:

1. Release Manager
2. aprobación adicional de otro Core Maintainer
3. qualification gates verdes
4. artefactos reproducibles o verificables
5. SBOM
6. checksums
7. provenance disponible
8. notas de migración

No existe botón personal de release sin peer review.

## 45. Release signing y provenance

El proyecto utilizará firmas y provenance verificables para artefactos publicados.

La implementación puede apoyarse en mecanismos keyless compatibles con Sigstore o tecnología equivalente seleccionada por el pipeline, evitando claves privadas de larga duración cuando resulte práctico.

Cada release debe poder relacionarse con:

```text
Git tag
Commit SHA
CI run
Source archive
Container digest
SBOM
Provenance
Checksums
```

## 46. Security disclosure

`SECURITY.md` define:

- versiones soportadas
- canal privado de reporte
- información útil para reproducir
- expectativas de acknowledgement
- política de coordinación
- safe harbor de buena fe en términos razonables

Los secretos, datos personales y exploits activos no se publican en issues.

## 47. Security response lifecycle

```text
Report
  ↓
Acknowledge
  ↓
Triage
  ↓
Severity
  ↓
Fix branch / private advisory
  ↓
Validation
  ↓
Coordinated release
  ↓
Advisory
  ↓
Postmortem when appropriate
```

## 48. Embargo

Un embargo sólo se mantiene el tiempo necesario para producir y distribuir una corrección razonable.

El grupo privado se limita a personas necesarias.

No se utiliza embargo para ocultar defectos reputacionales sin riesgo de explotación.

## 49. Security advisories

GitHub Security Advisories será el mecanismo de referencia inicial para coordinación privada y publicación, complementado por CVE cuando proceda y sea posible.

## 50. OpenSSF posture

El proyecto perseguirá progresivamente:

- OpenSSF Scorecard sin regresiones críticas
- OpenSSF Best Practices Badge
- criterios OSPS Baseline apropiados a su madurez

Estas herramientas sirven como indicadores, no sustituyen threat modeling ni revisión humana.

## 51. Ecosistema de plugins

El ecosistema busca permitir extensiones sin convertir el Core en un runtime arbitrario.

Categorías iniciales:

```text
In-process official module
Out-of-process connector
Frontend extension
Automation action provider
Import / Export adapter
Hardware adapter
Report provider
Jurisdictional module
```

## 52. Regla de confianza

Default:

> Community code is untrusted until verified.

Un plugin comunitario no obtiene automáticamente acceso a filesystem, secretos, base de datos, red o datos personales.

## 53. In-process plugins

Sólo se permite ejecución in-process para componentes oficiales o explícitamente trusted.

Política V1:

- licencia oficial `AGPL-3.0-only`
- review completo
- dependency scanning
- capability manifest
- migration tests
- compatibility suite
- release coordinada

Community plugins ordinarios se ejecutarán preferentemente fuera del proceso principal.

## 54. Out-of-process connectors

El modelo recomendado para extensiones independientes es un proceso o servicio separado que interactúe mediante interfaces públicas y autenticadas.

Ventajas:

- isolation boundary
- crash containment
- permisos explícitos
- menor acoplamiento de releases
- mayor flexibilidad de lenguaje
- boundary legal y técnico más claro

La licencia concreta de un connector externo se declara en su manifest y no se presume automáticamente por este documento.

## 55. Plugin API

El Core expone un contrato versionado para:

- eventos
- commands autorizados
- lectura de recursos permitidos
- acciones de automatización
- webhooks
- UI extension points restringidos
- health
- metadata

No se permite acceso SQL directo como API pública de plugins.

## 56. Plugin Manifest v1

Ejemplo conceptual:

```yaml
schema: 1
id: org.example.whatsapp
name: WhatsApp Connector
version: 1.2.0
license: AGPL-3.0-only
source: https://example.org/source
core:
  requires: ">=1.0.0 <2.0.0"
runtime:
  type: connector
permissions:
  - customers.contact.read
  - communications.send
network:
  hosts:
    - graph.facebook.com
events:
  subscribes:
    - service_order.ready
```

## 57. Identidad de plugin

Los IDs utilizan reverse DNS o namespace equivalente para evitar colisiones:

```text
org.openbikeshop.email-smtp
mx.example.cfdi
com.vendor.payment-terminal
```

El display name puede cambiar. El ID publicado no se reutiliza para otro producto.

## 58. Capability permissions

Permisos son granulares y deny-by-default.

Ejemplos:

```text
customers.read
customers.contact.read
bicycles.read
work_orders.read
work_orders.write
inventory.read
inventory.adjust
communications.send
payments.read
payments.create
files.read
files.write
```

`payments.create`, `inventory.adjust` y otros permisos sensibles requieren advertencia reforzada.

## 59. Network policy

Un connector debe declarar dominios o categorías de red requeridas.

La instalación muestra al administrador:

- destinos
- propósito
- datos potencialmente enviados
- necesidad de Internet

Un cambio material de network permissions requiere nueva aprobación.

## 60. Secret handling para plugins

Plugins nunca reciben el secret store completo.

Reciben únicamente secretos concedidos a su identidad y propósito.

El Core debe permitir:

- creación
- rotación
- revocación
- audit trail
- invalidación al desinstalar

Los secretos no forman parte de exports ordinarios del plugin.

## 61. Plugin data

Cada plugin posee un namespace de datos claramente identificable.

No puede modificar tablas internas de otro bounded context directamente.

Persistencia oficial se realiza mediante APIs o migraciones registradas por el framework de plugins.

## 62. Instalación

Flujo V1:

```text
Select plugin
  ↓
Verify manifest
  ↓
Verify source + artifact metadata
  ↓
Compatibility check
  ↓
Show permissions
  ↓
Administrator approval
  ↓
Install
  ↓
Migrate
  ↓
Health check
  ↓
Enable
```

Una falla antes de `Enable` debe dejar la instalación recuperable.

## 63. Desinstalación

Desinstalar no significa destruir datos inmediatamente.

Se ofrecen opciones:

```text
Disable only
Uninstall runtime, retain data
Export data then purge
Purge after retention window
```

El comportamiento depende de clasificación de datos y obligaciones legales aplicables.

## 64. Plugin Registry

El registry oficial será inicialmente **Git-backed y reviewable**.

Fuente de verdad:

```text
registry/
├── schema/
├── entries/
│   └── org.example.plugin.yaml
├── maintainers/
├── advisories/
└── revoked/
```

Una web o API de búsqueda se genera desde ese repositorio.

## 65. Motivo del registry Git-backed

Ventajas para V1:

- historial inmutable práctico
- revisión por PR
- DCO
- CI
- rollback
- mirrors
- forkabilidad
- bajo costo operativo

No se necesita un marketplace propietario para comenzar.

## 66. Metadata obligatoria del registry

Cada entrada contiene:

- plugin ID
- nombre
- descripción
- maintainers
- source repository
- release artifact location
- licencia
- core compatibility
- runtime model
- permissions
- network destinations
- data categories
- support URL o canal
- security contact
- trust level
- latest verified version
- checksums o provenance

## 67. Trust levels

Se adoptan:

```text
Experimental
Community
Verified
Official
Core Candidate
Deprecated
Quarantined
Revoked
```

`Trust level` describe revisión del proyecto, no garantiza ausencia de defectos.

## 68. Experimental

Proyecto en desarrollo o prueba.

Puede aparecer únicamente en canales de desarrollo y nunca se activa por defecto en instalaciones productivas.

## 69. Community

Plugin publicado por terceros que satisface requisitos mínimos de metadata y licencia, pero no ha recibido auditoría profunda del proyecto.

La interfaz debe mostrar claramente su condición.

## 70. Verified

Requiere como mínimo:

- source disponible
- licencia declarada
- maintainer contact
- manifest válido
- CI pública o evidencia equivalente
- compatibility suite
- malware scan
- dependency scan
- permissions review
- reproducible source-to-artifact relationship razonable
- security policy
- al menos dos reviewers del registry

## 71. Official

Plugin mantenido dentro de la organización oficial o bajo responsabilidad formal de maintainers designados.

Requiere:

- `AGPL-3.0-only` para componentes in-process oficiales
- release gates equivalentes al Core según riesgo
- ownership documentado
- soporte de versiones definido
- security response integrado

## 72. Core Candidate

Una extensión Official puede ser Core Candidate cuando:

- resuelve un problema casi universal
- mantiene adopción sostenida
- no introduce dependencia propietaria obligatoria
- su API está madura
- simplificaría arquitectura al integrarse
- el costo permanente de mantenimiento es aceptable

Ser popular no basta.

## 73. Deprecated

Plugin funcional pero con reemplazo recomendado o fin de soporte anunciado.

Debe publicar:

- fecha de deprecación
- última versión soportada
- alternativa
- ruta de migración

## 74. Quarantined

Se utiliza cuando existe riesgo activo que requiere impedir nuevas instalaciones mientras se investiga.

Razones:

- malware sospechado
- credenciales expuestas
- account takeover
- vulnerabilidad crítica explotable
- artifact/source mismatch

Quarantine no equivale necesariamente a culpabilidad del maintainer.

## 75. Revoked

Estado para plugins que no deben utilizarse por evidencia suficiente de comportamiento malicioso, suplantación o riesgo no mitigado.

El registry conserva el historial y advisory correspondiente.

## 76. Promotion pipeline

```text
Community
  ↓ application
Automated checks
  ↓
Registry review
  ↓
Security review
  ↓
Compatibility review
  ↓
Verified
```

La promoción a Official requiere además aceptación explícita de mantenimiento por la organización del proyecto.

## 77. No paid verification

Verified y Official no pueden comprarse.

Puede existir patrocinio para financiar una auditoría, pero reviewers y criterios permanecen independientes del patrocinador.

## 78. Plugin compatibility

Cada plugin declara rango SemVer compatible.

El Core publica:

- compatibility matrix
- deprecated APIs
- removal schedule
- migration guides

Una API pública de plugin no se elimina en una minor release estable.

## 79. Compatibility test kit

`packages/plugin-sdk` incluirá un kit ejecutable por terceros:

```text
manifest validation
contract tests
permission tests
mock event source
core compatibility checks
migration tests
health protocol tests
```

Verified requiere pasar una versión soportada del kit.

## 80. Plugin migrations

Las migraciones deben:

- ser versionadas
- ser idempotentes cuando corresponda
- no modificar datos ajenos
- ofrecer preflight
- soportar backup previo cuando el riesgo sea material
- reportar rollback safety

## 81. Plugin failure isolation

Un plugin fallido no debe:

- bloquear login
- impedir abrir órdenes
- corromper Sync Engine
- detener el worker completo
- romper backups

Connectors se aíslan mediante health state y circuit breaker.

## 82. UI extensions

No se permite HTML o JavaScript arbitrario inyectado directamente en cualquier pantalla.

Los extension points oficiales usan componentes y contratos limitados, por ejemplo:

```text
work-order.action
customer.sidebar-card
settings.integration-panel
inventory.product-action
```

El host conserva control de accesibilidad, navegación y seguridad.

## 83. Plugin accessibility

Verified y Official deben cumplir requisitos de accesibilidad equivalentes a la superficie donde se integran.

Un plugin no puede degradar un flujo Tier 1 por debajo de WCAG 2.2 AA crítica.

## 84. Plugin privacy declaration

Manifest y registry indican categorías de datos tratadas:

```text
contact-data
bicycle-data
workshop-orders
inventory
financial-metadata
photos
location
```

Si transmite datos externamente, debe declararlo de forma legible antes de la instalación.

## 85. Telemetry de plugins

Telemetry está deshabilitada por defecto salvo comportamiento estrictamente necesario para prestar el servicio elegido.

Analytics opcional requiere opt-in coherente con la política global del producto.

## 86. Plugin security advisories

El registry puede asociar advisories a:

- plugin
- rango de versiones
- severidad
- mitigación
- versión corregida

El administrador recibe aviso local cuando un plugin instalado coincide con un advisory relevante, si la instalación tiene conectividad y actualización de metadata habilitada.

## 87. Malicious plugin response

Ante evidencia fuerte:

1. quarantine registry entry
2. preserve evidence
3. notify maintainers si es seguro
4. publish advisory proporcional
5. mark affected versions
6. provide disable/uninstall guidance
7. revoke metadata when necessary
8. investigate compromise path

No se ejecuta remote kill de plugins sin una política explícita futura y consentimiento arquitectónico.

## 88. Registry moderation

Una denegación debe indicar el criterio incumplido.

El autor puede corregir y reenviar.

Existe apelación ante dos maintainers no involucrados originalmente.

## 89. Trademark policy

La licencia de software y las marcas son independientes.

Hasta definir el branding final, el proyecto reservará:

- nombre oficial
- logo
- nombres de eventos oficiales
- badges `Verified` y `Official`

La política definitiva se publicará en `TRADEMARKS.md` antes de V1.0.

## 90. Uso permitido de marca

Sin autorización especial se permitirá razonablemente:

- referirse al proyecto por su nombre
- decir “compatible con”
- enlazar documentación
- mostrar screenshots para educación o review
- mencionar que un servicio implementa el software

No se permite sugerir certificación, partnership u oficialidad inexistente.

## 91. Forks y white labeling

Un fork puede conservar avisos de copyright y licencia, pero deberá evitar identidad visual que produzca confusión con una distribución oficial cuando existan modificaciones materiales.

La función de white labeling está diseñada para que implementadores utilicen marcas propias de sus clientes sin eliminar atribuciones o accesos de licencia exigibles.

## 92. Badges del ecosistema

Los badges tendrán significado verificable:

```text
Community
Verified
Official
Compatible with Core 1.x
Accessibility Reviewed
Security Reviewed
```

No se crearán badges meramente promocionales que parezcan certificaciones técnicas.

## 93. Directorio de implementadores

Podrá existir un directorio comunitario de freelancers, cooperativas, agencias y empresas que ofrezcan servicios.

Requisitos mínimos:

- aceptar reglas de marca
- identificar territorio o modalidad remota
- declarar servicios
- no presentarse como representante exclusivo
- mantener canal de contacto

La inclusión no implica garantía comercial del proyecto.

## 94. Neutralidad comercial

El proyecto no obligará a contratar un implementador específico.

Los clientes conservan libertad para:

- autohospedar
- cambiar proveedor
- exportar datos
- contratar otro desarrollador
- mantener un fork

## 95. Revenue models compatibles

Ejemplos expresamente compatibles con la filosofía del proyecto:

- instalación
- discovery
- white labeling
- migración de datos
- capacitación
- soporte
- hosting
- backup administrado
- integraciones
- hardware
- custom plugins
- auditorías
- SLA
- mantenimiento

El software libre no convierte esos servicios en gratuitos.

## 96. Sponsorship

La comunidad puede recibir patrocinio para:

- infraestructura
- security audits
- accessibility audits
- documentación
- traducciones
- hardware lab
- contributor grants
- eventos
- desarrollo priorizado públicamente

Todo patrocinio material debe ser visible.

## 97. Fondo comunitario

Cuando exista volumen suficiente se recomienda una cuenta o estructura fiscal transparente administrada mediante sponsor fiscal, fundación o entidad apropiada.

El ledger público del fondo debe mostrar categorías de ingresos y gastos sin publicar datos personales innecesarios.

## 98. Compensación de maintainers

Ser maintainer puede coexistir con trabajo remunerado.

Las decisiones técnicas no pierden validez porque alguien cobre por implementarlas.

Debe declararse cuando el pago cree un conflicto de interés material.

## 99. Bounties

Bounties pueden utilizarse para issues definidos, pero:

- no sustituyen review
- no garantizan merge
- no permiten saltar arquitectura
- deben definir criterios de aceptación
- deben declarar quién financia

## 100. No exclusividad

Un sponsor no obtiene exclusividad sobre una feature financiada que entre al repositorio open source.

Customizaciones específicas pueden permanecer fuera del upstream si el cliente y la licencia lo permiten, pero upstream inclusion sigue criterios técnicos ordinarios.

## 101. Community translations

Las traducciones se administran como contribuciones versionadas.

Reglas:

- mensajes fuente estables
- glossary por dominio ciclista
- review por hablantes competentes
- no bloquear release por idiomas no Tier 1 salvo regresión
- mantener accesibilidad de textos

## 102. Documentation ownership

Cada área técnica importante tiene al menos un owner documental.

Un cambio de comportamiento que afecte operación, API, plugin contract o UX no se considera completo sin documentación correspondiente.

## 103. Knowledge Base comunitaria

El futuro Open Cycling Knowledge Base tendrá gobernanza separada de datos de producto.

Debe distinguir:

```text
Manufacturer sourced
Community verified
Workshop local
Experimental
```

No se copiarán manuales o bases propietarias sin derechos adecuados.

## 104. Inclusión y accesibilidad comunitaria

La comunidad promoverá:

- lenguaje respetuoso
- documentación accesible
- participación asincrónica
- horarios rotativos cuando haya reuniones globales
- decisiones importantes por escrito
- captions o transcript cuando sea viable

La capacidad de participar no debe depender de asistir a videollamadas.

## 105. Reuniones

Las reuniones comunitarias son auxiliares.

Toda decisión vinculante tomada en reunión debe quedar reflejada posteriormente en issue, RFC, ADR o minutes públicas.

## 106. Community health metrics

Se observan tendencias, no rankings personales.

Métricas útiles:

- active contributors
- returning contributors
- review latency
- issue response time
- maintainer concentration
- releases por periodo
- bus factor
- plugin maintainers activos
- security response time
- documentation freshness

No se utiliza número bruto de commits como medida de mérito.

## 107. Inactividad de maintainers

Un maintainer puede pasar a `Emeritus` tras inactividad prolongada o a solicitud propia.

Umbral orientativo:

- 6 meses sin actividad material y sin aviso

Emeritus conserva reconocimiento histórico, pero no permisos administrativos críticos.

Puede solicitar reactivación mediante proceso simplificado.

## 108. Removal de maintainer

Causas posibles:

- solicitud voluntaria
- inactividad
- incumplimiento grave de seguridad
- abuso persistente de permisos
- violación severa del Code of Conduct
- conflicto de interés no gestionado

La remoción involuntaria requiere revisión colegiada y derecho razonable a responder, salvo emergencia de seguridad donde primero se revocan credenciales.

## 109. Succession plan

Antes de cada release major se verifica:

- mínimo de release custodians
- security contacts activos
- acceso a DNS y registries
- backup de documentación comunitaria
- recuperación de signing workflow
- owners de Core y Sync

La continuidad se considera una propiedad de release.

## 110. Project archive policy

Si el proyecto dejara de mantenerse, los maintainers deben intentar:

1. anunciar estado
2. publicar última release verificable
3. conservar repositorio y documentación
4. marcar plugins Official sin soporte
5. transferir activos a una comunidad sucesora cuando sea legítimo
6. evitar borrar historial o security advisories

## 111. Governance security

Activos administrativos importantes requieren:

- MFA resistente a phishing cuando el proveedor lo soporte
- mínimo privilegio
- audit logs
- recuperación documentada
- dos custodios

Cuentas compartidas se evitan.

## 112. Supply chain de contribuciones

Además de DCO:

- dependency review
- secret scanning
- protected branches
- signed release provenance
- SBOM
- pinning de actions críticas
- OpenSSF Scorecard

La confianza no se basa únicamente en reputación del contribuidor.

## 113. Automatización de gobernanza

Se automatiza lo repetible, no la legitimidad humana.

Buenos candidatos:

- DCO
- stale metadata warnings
- CODEOWNERS
- plugin manifest validation
- compatibility checks
- release evidence
- permission recertification reminders

No se automatiza una expulsión comunitaria basada únicamente en métricas.

## 114. Governance repository layout

```text
docs/08-open-source/
├── GOVERNANCE.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── TRADEMARKS.md
├── MAINTAINERS.md
├── COMMUNITY.md
├── SUPPORT.md
├── FUNDING.md
├── rfc-process.md
├── plugin-governance.md
└── registry-policy.md

rfcs/
registry/
.github/
├── CODEOWNERS
├── ISSUE_TEMPLATE/
├── DISCUSSION_TEMPLATE/
└── PULL_REQUEST_TEMPLATE.md
```

## 115. Governance decision records

Se añaden los siguientes registros aceptados:

| ID | Decisión |
|---|---|
| GOV-ADR-001 | Core y aplicaciones oficiales usan `AGPL-3.0-only` |
| GOV-ADR-002 | Contribuciones mediante DCO 1.1, sin CLA en V1 |
| GOV-ADR-003 | Contributor Covenant 2.1 como Code of Conduct baseline |
| GOV-ADR-004 | Contributor ladder explícito |
| GOV-ADR-005 | Bootstrap governance con transición automática a Steering Council |
| GOV-ADR-006 | RFCs públicos para cambios significativos |
| GOV-ADR-007 | Dos approvals para cambios de alto riesgo |
| GOV-ADR-008 | Stable releases requieren two-person rule |
| GOV-ADR-009 | Registry oficial Git-backed en V1 |
| GOV-ADR-010 | Community plugins untrusted by default |
| GOV-ADR-011 | In-process Official plugins bajo AGPL y review equivalente al Core |
| GOV-ADR-012 | Out-of-process connector como extensión preferida para terceros |
| GOV-ADR-013 | Registry trust levels normalizados |
| GOV-ADR-014 | Verified y Official no pueden comprarse |
| GOV-ADR-015 | Trademarks separados de licencia del código |
| GOV-ADR-016 | Directorio comercial neutral de implementadores permitido |
| GOV-ADR-017 | OpenSSF Scorecard y Best Practices como objetivos de madurez |
| GOV-ADR-018 | Bus factor y sucesión forman parte de release readiness |

## 116. Governance gates para V1.0

| Gate | Condición |
|---|---|
| GOV-GATE-V1-001 | `LICENSE` contiene AGPL v3 y SPDX usa `AGPL-3.0-only` |
| GOV-GATE-V1-002 | `CONTRIBUTING.md` documenta DCO y flujo de PR |
| GOV-GATE-V1-003 | DCO check bloqueante activo |
| GOV-GATE-V1-004 | `CODE_OF_CONDUCT.md` y canal privado de enforcement disponibles |
| GOV-GATE-V1-005 | `SECURITY.md` con versiones soportadas y disclosure privado |
| GOV-GATE-V1-006 | `GOVERNANCE.md` publica roles y decisión process |
| GOV-GATE-V1-007 | `MAINTAINERS.md` refleja owners vigentes |
| GOV-GATE-V1-008 | CODEOWNERS protege scopes críticos |
| GOV-GATE-V1-009 | release stable requiere dos personas |
| GOV-GATE-V1-010 | Source Code link AGPL probado en PWA/portal cuando aplique |
| GOV-GATE-V1-011 | `TRADEMARKS.md` publicado antes de branding estable |
| GOV-GATE-V1-012 | plugin manifest schema versionado |
| GOV-GATE-V1-013 | registry policy publicada |
| GOV-GATE-V1-014 | compatibility test kit ejecutable |
| GOV-GATE-V1-015 | proceso Quarantined/Revoked probado administrativamente |
| GOV-GATE-V1-016 | security advisory flow de plugins documentado |
| GOV-GATE-V1-017 | activos críticos tienen dos custodios o excepción de bootstrap publicada |
| GOV-GATE-V1-018 | release artifacts incluyen SBOM y provenance |
| GOV-GATE-V1-019 | OpenSSF Scorecard habilitado y revisado |
| GOV-GATE-V1-020 | ruta de export y cambio de proveedor documentada para clientes |

## 117. Definition of Done de la fase

La Fase 8 se considera suficientemente especificada cuando:

1. la licencia oficial no es ambigua
2. la contribución legal no requiere acuerdos privados innecesarios
3. los roles comunitarios tienen facultades y límites claros
4. existe transición documentada desde bootstrap hacia gobernanza distribuida
5. decisiones importantes pueden trazarse mediante RFC y ADR
6. releases no dependen de una sola persona
7. seguridad dispone de canal privado y authority definida
8. plugins tienen trust model, permisos y lifecycle
9. registry puede operarse sin marketplace propietario
10. trademarks y white labeling no se confunden con licencia del código
11. modelos comerciales siguen siendo compatibles con libertad de usuarios
12. V1 dispone de governance gates verificables

## 118. Orden de implementación

### G0 · Legal baseline

`LICENSE`, SPDX, REUSE, DCO, contribution notices.

### G1 · Community baseline

`CONTRIBUTING`, Code of Conduct, Security, Support.

### G2 · Repository authority

CODEOWNERS, protected branches, roles, two-person release rule.

### G3 · RFC governance

Templates, states, FCP y decision records.

### G4 · Plugin contract

Manifest schema, permissions y compatibility kit.

### G5 · Registry

Git-backed registry, CI, trust levels y promotion flow.

### G6 · Supply-chain maturity

SBOM, provenance, Scorecard y Best Practices.

### G7 · Community sustainability

Implementer directory, funding transparency, maintainer succession y governance transition.

## 119. Riesgos residuales

### R-GOV-001 · Captura por una sola organización

Mitigación: diversidad de maintainers, disclosures de conflicto, no pay-to-merge y Steering Council distribuido.

### R-GOV-002 · Plugin registry como falsa garantía

Mitigación: trust levels explícitos, lenguaje de riesgo y advisories.

### R-GOV-003 · Supply-chain compromise

Mitigación: branch protection, two-person release, provenance, SBOM y revocación.

### R-GOV-004 · Fragmentación por forks

Mitigación: APIs estables, gobernanza abierta, upstreaming sencillo y política de trademarks clara.

### R-GOV-005 · Burnout de maintainers

Mitigación: contributor ladder, financiación transparente, scope conservador y rotación de responsabilidades.

### R-GOV-006 · Obligaciones AGPL mal implementadas por terceros

Mitigación: tooling de source bundle, documentación y UI Source Code. El proyecto no sustituye asesoría jurídica profesional.

## 120. Referencias normativas y operativas

Fuentes de referencia para esta fase:

- GNU Affero General Public License v3, Free Software Foundation: https://www.gnu.org/licenses/agpl
- SPDX identifier `AGPL-3.0-only`: https://spdx.org/licenses/AGPL-3.0-only
- Developer Certificate of Origin 1.1: https://developercertificate.org/
- Contributor Covenant 2.1: https://www.contributor-covenant.org/version/2/1/code_of_conduct.html
- OpenSSF Scorecard: https://openssf.org/projects/scorecard/
- OpenSSF Best Practices Badge: https://openssf.org/projects/best-practices-badge/

## 121. Handoff a Fase 9

Con producto, arquitectura, seguridad, UX, ingeniería, QA, operaciones y gobernanza definidos, la siguiente fase será **Commercial Implementation Playbook**.

Fase 9 deberá convertir la plataforma en una oferta profesional repetible para implementadores, incluyendo discovery comercial, levantamiento de taller, packages, pricing, white labeling, migración, hardware, capacitación, contratos de servicio, SLA, soporte, mantenimiento, trueque, handover, checklist de go-live y unit economics.

La finalidad no será crear una licencia comercial paralela, sino demostrar cómo generar ingresos sostenibles alrededor de un producto AGPL sin encerrar al cliente ni apropiarse del trabajo comunitario.
