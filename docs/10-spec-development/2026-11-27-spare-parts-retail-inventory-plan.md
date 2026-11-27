# Inventario de refacciones, tienda y taller: alcance integrado del plan

Fecha: 2026-11-27. Fuente auditada:
`b49f10b1b21240c8682cf3a9ba7ca0f3c9ce4ea8`. Estado: **planificación de alcance**;
V0.1 continúa parcial. Esta precisión responde a la petición de contemplar e
integrar tanto las refacciones como los productos de tienda/taller. Conserva los
requisitos y las decisiones aceptadas; no implementa módulos ni declara stock real.

El alcance ya existe en FR-INV-001–012, FR-POS-001–009 y FR-BIZ-001–003.
Se hace explícito en las 17 tareas originales de V0.3 y las 14 de V0.4 mediante
aceptación, dependencias y escenarios verificables. No se agregan IDs FR/tarea,
ni se cambian contratos vigentes ni se cierra un gate de release.

## Fuentes y orden de implementación

- [Fase 1: inventario, POS y reglas de negocio](../01-functional-requirements/open-cycling-workshop-platform-phase-1-functional-requirements-v0.1.md):
  FR-INV-001–012, FR-POS-001–009, FR-SVC-011, OFF-002, NFR-009 y BR-006/007.
- [Suplemento de perfiles](../01-functional-requirements/2026-11-02-product-description-supplement.md):
  FR-BIZ-001–003, módulos opcionales, preservación de datos/permisos y aceptación
  por perfil.
- [Fase 10: plan canónico](open-cycling-workshop-platform-phase-10-spec-development-master-execution-system-v0.1.md):
  V0.3 Inventory & Purchasing, V0.4 POS & Payments y refinamiento del 2026-11-27.
- [Matriz de este alcance](inventory-scope-plan.json) y
  [cobertura de la descripción](product-description-coverage.json): mapeos de
  planificación, sin sustituir evidencia de comportamiento en `traceability.csv`.
- [ADR de atomicidad de inventario](../02-technical-architecture/2026-10-13-inventory-command-atomicity.md),
  [ADR de lectura conectada](../02-technical-architecture/2026-10-15-connected-inventory-read.md)
  y [ADR de persistencia/comandos de cotización](../02-technical-architecture/2026-10-15-quote-persistence-and-online-command-boundary.md):
  mantienen autoridad, contratos y admisión vigentes.
- [Alineación previa de producto](2026-11-02-product-description-alignment.md):
  conserva prioridad de integridad/readiness V0.1 y calificación posterior por dominio.

La secuencia sigue V0.2 → V0.3 → V0.4. La cotización y su autorización en V0.2
no equivalen a reservar, consumir, vender o cobrar. V0.3 incorpora stock,
compras y consumo de taller; una tienda puede usar ese catálogo/stock antes de
habilitar ventas. V0.4 incorpora la venta transaccional, pagos, devolución y caja
opcional. El tipo de movimiento SALE previsto en R03-T003 es una capacidad del
dominio de inventario: no acredita un POS ni exige implementar V0.4 primero.

La calificación completa de venta minorista/combinada conserva V0.4 y
R09-T028/R10-T004. El asistente de compatibilidad posterior sigue R07-T004;
la extensibilidad del catálogo no adelanta V0.7. La prioridad de ejecución sigue
el Master Agent Loop y los gates actuales; este plan no habilita automáticamente
funciones futuras.

## Productos y perfiles incluidos

Refacciones, accesorios para venta, consumibles de reparación y otra mercancía
legítima del negocio son ejemplos de productos, no una lista cerrada ni categorías
obligatorias. Un mismo artículo puede venderse en mostrador y utilizarse en una
orden. El catálogo debe distinguir variante, SKU, EAN/código, unidad y comportamiento
inventariable, con campos de compatibilidad extensibles cuando proceda. Un servicio
o producto no inventariable no genera por sí mismo una salida física.

| Perfil                     | Aceptación de catálogo/stock                                                                                                          | Frontera comercial y de permisos                                                                                                                             |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Taller                     | Refacciones y consumibles recibidos, reservados, liberados, consumidos y contados por ubicación; servicios separados del stock físico | No exige POS. Cobrar una orden después de consumir sus partes no vuelve a descontarlas                                                                       |
| Tienda sin taller          | Mercancía, variantes, unidades, compras y stock de V0.3 disponibles según módulos/grants habilitados                                  | Venta independiente en V0.4 sin exigir bicicleta ni ServiceOrder; caja sólo cuando corresponda                                                               |
| Tienda y taller combinados | Una identidad de SKU y ledger por organización para el artículo compartido, con saldos por ubicación física                           | Un almacén compartido no crea un stock de tienda y otro de taller; reservas/consumos/ventas compiten sobre la disponibilidad autorizada                      |
| Servicio/cooperativa       | Catálogo, inventario, donación/reuso o servicios sólo según el perfil y módulos habilitados                                           | No obliga a vender, abrir caja, registrar bicicleta ni operar un taller. Cambiar perfil no concede permisos ni elimina historia/datos/intenciones pendientes |

Cuando hay almacenes distintos, transferir mantiene identidad de producto y deja
trazabilidad en origen/destino; no se resuelve duplicando productos para aparentar
stock por ubicación. El modelo actual todavía no entrega esa capacidad completa.
El alcance se califica por organización y ubicación, con autorización de servidor;
un perfil de negocio o una selección de UI no son una concesión de autoridad.

Condición del artículo, disponibilidad y motivo de movimiento son conceptos
separados. FR-INV-009 incluye daño/pérdida/donación/reuso, pero no prescribe una
taxonomía obligatoria de nuevo/usado/reacondicionado. Si un perfil necesita
atributos de condición o procedencia, deben precisarse en el diseño de catálogo
con sus casos de aceptación, sin inventar aquí un enum ni una certificación de
seguridad. Una herramienta vendida puede ser mercancía; eso no implica un módulo
de depreciación, préstamo o mantenimiento de activos propios del taller.

## Estado de implementación inspeccionado

La fuente contiene API montada para `POST`/`GET` de productos, `POST` de movimientos
y `GET` de stock e historial. La composición actual se encuentra en
[`app.py`](../../services/platform/src/cycling_workshop/app.py), el dominio y los
contratos en [`inventory/`](../../services/platform/src/cycling_workshop/inventory/),
y la lectura conectada en
[`features/inventory/`](../../apps/web/src/features/inventory/). No hay router de
proveedores/compras/POS montado en esa composición.

El producto actual conserva ID, organización, una ubicación, SKU, nombre y unidad;
SKU es único por organización. No se debe presentar esto como catálogo completo
multialmacén, variantes/EAN ni transferencia de stock. La UI consulta catálogo,
cantidad disponible e historial paginado, con filtro nombre/SKU de la página
actual. Es volátil y conectada: no hay editor de productos/movimientos, snapshot de
inventario offline ni cola de escritura de stock admitida.

El ledger vigente admite ADJUST, RESERVE, RELEASE y CONSUME. RESERVE resta
la cantidad retenida; RELEASE/CONSUME finalizan la reserva con signo positivo.
El consumo actual agrega atómicamente un ADJUST físico negativo. El saldo
proyectado por la API es disponible, no un nuevo contrato público de existencias
y reservas por separado. Los CONSUME históricos sin enlace conservan su semántica;
no se inventan vínculos ni se reconstruye disponibilidad sumando una página de
historial. Los nombres de movimientos futuros requieren evolución compatible,
no renombrar filas históricas ni cambiar silenciosamente la fórmula vigente.

Las cantidades del contrato actual son enteras; se rechazan fracciones y números
inseguros. Si unidades fraccionarias resultan necesarias, su admisión requiere
ADR, representación de punto fijo validada y migración/contratos/pruebas antes
de exposición. No se permite redondeo silencioso. Costo, precio y margen necesitan
precisión monetaria decimal/punto fijo validada y reglas versionadas; este plan no elige régimen fiscal,
método de valuación, conversiones de empaque ni política contable universal.

### Evidencia existente y límites

La comparación de los directorios de inventario, migraciones y cliente API entre
la fuente auditada `b49f10b` y main `ed8057b` posterior a PR128 no presenta cambios.
Esto establece equivalencia de ese alcance, no del árbol completo ni de una
release. La evidencia hosted previa de PR129 stacked,
[CI45918812340](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/45918812340),
se vincula a sus propias fuentes y no es una ejecución nueva de este plan:

- Artefacto PostgreSQL `15163543965`, SHA-256
  `d07183ef459c64ba65c2ec63fb43c9413fac34183f8d310ef3e4dad16c92a181`:
  43/43 casos de lectura real completados en 35.39 s, sin skips ni errores.
  Sus seis hashes de fuente coinciden con la fuente auditada. El archivo EXPLAIN
  conserva SHA-256 `d02e428ed7e124947f23e04392849345b489be28318408555763a961a5d69330`.
  El log registra retirada del servicio; ese artefacto no contiene un manifiesto
  independiente de limpieza.
- Los dos reportes nativos de esa ejecución contienen 147 casos totales y 17 de
  inventario por fase, cada uno aprobado al primer intento. Corresponden a las
  lecturas y controles existentes, no a compras, conteos físicos, POS ni escritura
  offline de stock.

Estos resultados usan datos sintéticos. No se conectó un inventario operativo,
no se contaron refacciones de un taller real y no se acreditó capacidad física,
calificación de dispositivos ni despliegue. El estado por requisito siguiente
identifica trabajo pendiente aunque ya existan invariantes parciales probados.

## Aceptación por requisito existente

Todos los resultados de esta tabla son objetivos pendientes de implementación o
calificación integral. **Parcial** significa que existe una parte del contrato;
**planificado** significa que el flujo específico todavía debe desarrollarse.

| Requisito  | Estado en la fuente                                                            | Padres existentes                                                                                            | Aceptación para cerrar el alcance                                                                                                                                          |
| ---------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-INV-001 | Parcial: SKU/nombre/unidad; sin catálogo completo de variantes/EAN             | R03-T001, R03-T005, R03-T013, R03-T014                                                                       | Refacción, accesorio/mercancía y consumible distinguen variante/SKU/código/unidad; búsqueda/escaneo no elige silenciosamente una variante ambigua; catálogo accesible      |
| FR-INV-002 | Parcial: producto ligado a una ubicación; no transferencia multialmacén        | R03-T001, R03-T003, R03-T005, R03-T015                                                                       | Mismo SKU en ubicaciones autorizadas con saldos independientes y transferencia correlacionada que conserva el total; aislamiento entre organizaciones                      |
| FR-INV-003 | Parcial: cambios actuales por movimientos; faltan flujos de negocio enumerados | R03-T002, R03-T003, R03-T009, R03-T011, R03-T012, R03-T015, R04-T006, R04-T007, R04-T008, R04-T013, R04-T014 | Cada cambio deja movimiento autorizado e idempotente; recepción/consumo/transferencia/corrección no editan saldo ni historia                                               |
| FR-INV-004 | Parcial: saldo disponible derivado del ledger actual                           | R03-T004, R03-T015, R03-T016, R03-T017, R04-T007, R04-T014                                                   | Reconstrucción completa iguala proyección por producto/ubicación; reservas/finalizaciones, concurrencia y replay no duplican efectos                                       |
| FR-INV-005 | Planificado                                                                    | R03-T006, R03-T014                                                                                           | Umbral/alerta por ubicación y regla declarada para disponible/reservado; sin fuga de costos o stock fuera de alcance                                                       |
| FR-INV-006 | Planificado                                                                    | R03-T010, R04-T002, R04-T003, R04-T013, R04-T014                                                             | Costo/proveedor histórico, precio de referencia y margen con fórmula/precisión/versionado; venta aplica su precio/impuestos/descuentos autorizados sin reescribir historia |
| FR-INV-007 | Planificado                                                                    | R03-T007, R03-T008, R03-T010                                                                                 | Proveedor y datos operativos trazables a artículo, compra y costo, con acceso autorizado                                                                                   |
| FR-INV-008 | Planificado                                                                    | R03-T007, R03-T008, R03-T009, R03-T010, R03-T015, R03-T016                                                   | PO y recepciones parciales/completas actualizan pendientes/stock atómicamente; duplicación o fallo no repite ni deja medio efecto                                          |
| FR-INV-009 | Planificado: ADJUST genérico no prueba los flujos específicos                  | R03-T003, R03-T012, R04-T006, R04-T013, R04-T014                                                             | Devolución/daño/pérdida/donación/reuso conservan motivo, autoridad e historia; devolución comercial relaciona venta/pago y compensaciones sin duplicarlas                  |
| FR-INV-010 | Parcial: ajuste compensatorio, sin proceso de conteo físico                    | R03-T005, R03-T012, R03-T014, R03-T016                                                                       | Captura/revisión de conteo, referencia y movimientos concurrentes explícitos; diferencia aprobada genera compensación auditable, nunca reemplazo directo del saldo         |
| FR-INV-011 | Planificado                                                                    | R03-T001, R04-T001, R04-T002, R04-T007, R04-T008, R04-T014                                                   | Línea de servicio/no inventariable se puede cotizar/vender/cobrar según perfil sin generar cantidad física ni exigir bicicleta/orden en venta independiente                |
| FR-INV-012 | Planificado                                                                    | R03-T001, R07-T004                                                                                           | Atributos de compatibilidad extensibles distinguen información desconocida de compatibilidad confirmada; futura asistencia conserva procedencia y fase V0.7                |

R03-T010 cubre información económica del inventario; R04-T002 cubre cálculo de la
venta. No son dos fuentes que puedan discrepar sin una regla explícita de revisión.
Permisos y auditoría gobiernan correcciones sensibles, descuento, devolución y
cambio de precios según el contrato correspondiente. La mera existencia de
campos/categorías o de una tabla visual no satisface estos recorridos.

## Dependencias reforzadas y admisión

La matriz canónica conserva cada dependencia previa y explicita las faltantes:

- Recepción R03-T009 depende de PO, movimientos y ubicaciones; consumo R03-T011
  depende de movimientos, proyección y ubicaciones además del taller V0.2.
- Conteo R03-T012 depende de proyección/ubicaciones y ledger. Alertas R03-T006
  incluyen ubicación; UI R03-T014 integra esos resultados con costos, conteo y
  búsqueda; incluye crear/editar/archivar catálogo y transferir/contar/ajustar
  mediante comandos autorizados. Compra/recepción tiene recorrido de operador
  en R03-T008/R03-T009 y reserva/consumo en R03-T011. Los estados obsoleto,
  pendiente o desconocido son explícitos; una tabla no concede autoridad y no
  permite editar el ledger ni perder historia al archivar un artículo.
- R03-T015 exige ADR de admisión/conflictos antes de exposición offline y prueba
  los flujos online de recepción, consumo y conteo ya implementados. La aprobación
  del diseño precede la implementación offline aunque la tarea de prueba dependa
  de sus comandos online; no hay dependencia circular. R03-T016 reconcilia esos
  flujos completos y su replay; R03-T017 aplica luego sus presupuestos de carga.
- Venta R04-T007 depende de movimientos/proyección/ubicaciones. Devolución
  R04-T006 depende de venta/pago/stock; cobro de orden R04-T008 depende también
  del consumo R03-T011. Su orden numérico no reemplaza el grafo Depends.
- POS offline R04-T011 se apoya en la política de inventario R03-T015 y conserva
  los límites de proveedores externos R04-T012. R04-T014 integra pagos,
  devoluciones, cobro de orden, caja cuando aplica, ticket, auditoría y
  reconciliación de inventario. No califica sólo el camino de venta feliz.

No hay aristas V0.3→V0.4. La competencia entre comandos de inventario puede
probarse en V0.3; la carrera real entre venta POS y reserva de taller se califica
en R04-T007/R04-T014, después de implementar ambos extremos.

Cualquier nueva escritura UI/offline necesita los contratos, migraciones,
autoridad actual, idempotencia, cola durable, política de conflicto, recuperación
y accesibilidad correspondientes. No se admite stock por registrar genéricamente
una entidad en sync. Desconexión no transforma una intención pendiente en venta,
pago o reserva confirmada; reconexión no duplica recepción, consumo, cobro o retorno.
Los ADR vigentes y los datos anteriores permanecen intactos.

## Escenarios numéricos sintéticos de aceptación

Los números siguientes son **datos de prueba propuestos**, no existencias del
negocio ni pruebas ejecutadas de las funciones futuras. Se usa un SKU inventariable,
una organización y dos ubicaciones autorizadas A/B. “Existencia física” es la
magnitud del modelo futuro que se contrasta con ledger/proyección; la API actual
sólo publica disponible. Cada paso supone una operación aprobada una sola vez.

| Paso futuro                | Existencia A | Reserva A | Disponible A | Existencia B | Total físico | Invariante a demostrar                                                        |
| -------------------------- | ------------ | --------- | ------------ | ------------ | ------------ | ----------------------------------------------------------------------------- |
| Inicio                     | 0            | 0         | 0            | 0            | 0            | Fixture vacía, permisos/scope declarados                                      |
| Recibir 10 en A            | 10           | 0         | 10           | 0            | 10           | Compra/recepción/ledger consistentes; repetir la recepción no agrega otras 10 |
| Reservar 2 en A para orden | 10           | 2         | 8            | 0            | 10           | Reserva reduce disponible, no existencia física                               |
| Consumir las 2 reservadas  | 8            | 0         | 8            | 0            | 8            | Finaliza reserva y registra salida una vez; no suma ni resta dos veces        |
| Transferir 3 de A a B      | 5            | 0         | 5            | 3            | 8            | Salida/entrada correlacionadas; total conservado y alcance autorizado         |
| Contar A: observadas 4     | 5            | 0         | 5            | 3            | 8            | Registrar el conteo no sobreescribe saldo; diferencia propuesta −1            |
| Aprobar diferencia −1 en A | 4            | 0         | 4            | 3            | 7            | Compensación con motivo/autoridad; reconstrucción A4/B3                       |

La transferencia requiere salida y entrada atómicas en su frontera transaccional
o un protocolo explícito aprobado que distinga tránsito y finalización; no se
acepta perder un extremo ni publicar un saldo final sin conciliación. El ejemplo
representa su resultado confirmado, sin escoger una arquitectura distribuida.

Una variante de recepción parcial usa PO de 10 y recepciones de 4 + 6: los saldos
son 4 y después 10, con pendientes 6 y después 0. Repetir cada operación conserva
esos valores. Fallo entre PO/ledger/proyección revierte el conjunto. Si ocurre un
movimiento mientras se cuenta, el diseño declara cómo compara la referencia y
resuelve la diferencia antes de autorizarla; el ejemplo sin concurrencia no
escoge ni prueba esa política.

A partir de A4/B3, la aceptación V0.4 añade:

| Operación                                 | Resultado físico esperado | Evidencia adicional necesaria                                                                                        |
| ----------------------------------------- | ------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Vender 1 de B                             | A4/B2, total 6            | Venta/ledger atómicos; pago registrado idempotentemente según su contrato; sin bicicleta/orden obligatoria en tienda |
| Devolver físicamente esa unidad a B       | A4/B3, total 7            | Compensación vinculada a venta; estado y reembolso explícitos, sin confundir dinero con retorno físico               |
| Vender/cobrar servicio o no inventariable | A4/B3 sin cambio          | Línea y cálculo comercial correctos; ninguna salida física artificial                                                |
| Cobrar la orden que ya consumió 2         | A4/B3 sin cambio          | Mantener vínculo al consumo previo; no generar otra salida de 2 ni duplicar pago al reintentar                       |

Los ejemplos de retorno suponen que la unidad es admisible para volver a stock;
una devolución dañada exige la disposición explícita correspondiente y no se
convierte automáticamente en disponible. El flujo no define aquí una política
comercial o de seguridad universal.

Otro fixture con una sola unidad disponible compite entre dos comandos admitidos.
V0.3 prueba la invariante del dominio según su política aprobada; V0.4 agrega venta
POS frente a reserva de orden. No pueden confirmar dos asignaciones de la misma
unidad ni resolver el conflicto borrando una operación. En cada perfil aplicable
se prueban acceso revocado, ubicación ajena, repetición, fallo transaccional,
reconexión y recuperación; dinero y stock se reconcilian por separado y por sus
vínculos. Caja no se fuerza en perfiles que no la habilitan.

La matriz JSON contiene también variantes aisladas; cada una empieza en su propio
estado inicial y no se concatena con la secuencia A4/B3 anterior:

| Fixture de la matriz               | Objetivo numérico independiente                                                                                                                             |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `shared_stock_workshop_and_retail` | Recibir 10, reservar 2, vender 3 no reservadas, consumir 2, cobrar esa orden sin nueva salida y devolver 1 admisible: existencia 6, reserva 0, disponible 6 |
| `partial_purchase_receipts`        | PO 10, recibir 4 y después 6; repetir cada recepción no cambia el acumulado 4/10                                                                            |
| `location_transfer`                | A10/B0 → transferir 3 → A7/B3, total 10; repetir no cambia el total ni los extremos                                                                         |
| `physical_count`                   | Existencia 10/reserva 2/disponible 8; contar 9 y admitir compensación −1 → 9/2/7, sin liberar reservas ni reescribir historia                               |
| `nonstock_service`                 | Disponibilidad no aplicable, ningún movimiento físico al cobrar la línea; no confundir N/A con falta de stock                                               |
| `last_unit_competition`            | Una unidad: reserva admitida → disponible 0; venta competidora rechazada; consumo → existencia/reserva/disponible 0. Debe probarse también el orden inverso |

## Qué valida este cambio de plan

Los controles de repositorio verifican que la matriz referencia requisitos y
padres existentes, mantiene 17 + 14 tareas, coincide con Depends y conserva un
grafo acíclico. También pueden verificar la aritmética del fixture propuesto y
que todos los FR de inventario estén cubiertos por aceptación. Son validaciones
estructurales del plan: no prueban una recepción, transferencia, conteo, lector
físico, servicio cobrado ni POS real.

Validación local de este refinamiento: 13 controles nuevos RED por ausencia del
contrato de planificación, seguidos de 13 GREEN; 241/241 pruebas de repositorio,
verificador de repositorio, Ruff, Prettier y comprobación del diff satisfactorios.
La revisión independiente confirmó la conservación de los IDs, dependencias
previas y ausencia de ciclos. El candidato de planificación se basa en el sucesor
documental `a2b8379b9d3980052887dffbf5f36c3987ecc874` de PR129; sus pruebas hosted
son independientes de la evidencia de inventario anterior y de
[CI45971834314](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/45971834314).

Cada implementación futura necesita RED/controles, GREEN, contrato, PostgreSQL,
UI/accesibilidad, offline/conflictos y recuperación según su riesgo, con evidencia
ligada a la fuente exacta. Los dispositivos físicos, conteo del negocio,
R01-T035/T1–T8, gates de release y despliegue mantienen su estado independiente.
El trabajo pendiente permanece en sus tareas originales; ninguna funcionalidad
se excluye por no estar implementada hoy.
