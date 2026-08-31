# Fase 4 · UX/UI, Information Architecture & Design System v0.1

**Open Cycling Workshop Platform**  
Baseline: Foundation v0.2 · Functional Requirements v0.1 · Technical Architecture v0.2 · Security/Privacy v0.1  
License baseline: `AGPL-3.0-only`

## 1. Purpose

This phase turns product requirements into a verifiable operational experience architecture. It defines how the system behaves during reception, workshop work, sales, administration, customer authorization and network failure, not only how it looks.

### UX principles

| ID    | Principle                  | Rule                                                                             |
| ----- | -------------------------- | -------------------------------------------------------------------------------- |
| UX-01 | Operational clarity        | Urgent, actionable and irreversible information outranks decoration.             |
| UX-02 | Local confidence           | The user can tell whether work is local, syncing, synced, conflicted or blocked. |
| UX-03 | Workshop-grade touch       | Mechanic flows use large targets, quick reading and one-hand operation.          |
| UX-04 | Progressive disclosure     | Complexity appears only when a task, module or capability needs it.              |
| UX-05 | Role-aware                 | Capabilities adapt navigation without creating separate apps per role.           |
| UX-06 | Accessible by construction | WCAG 2.2 AA is an acceptance criterion.                                          |
| UX-07 | Semantic white label       | Brand tokens never redefine critical operational meaning.                        |
| UX-08 | Fast paths first           | Frequent workflows minimize re-entry, steps and unnecessary confirmation.        |
| UX-09 | Undo before confirmation   | Reversible actions prefer undo; confirmation is for high-impact commits.         |
| UX-10 | No hidden failure          | Sync, payment, inventory and permission failures remain visible until resolved.  |

## 2. Contexts of use

| Context                 | Conditions                                              | UX consequence                                         |
| ----------------------- | ------------------------------------------------------- | ------------------------------------------------------ |
| Reception on Windows    | Keyboard + mouse, large display, frequent interruptions | Instant search, shortcuts, rapid forms, split view     |
| Workshop Android tablet | Touch, gloves/dirty hands, variable light               | Workshop Mode, 56 px primary targets, high visibility  |
| Sales floor             | Mouse/touch/barcode scanner                             | Fast POS, scan-first focus, tolerant search            |
| Administration          | Desktop, data-dense                                     | Tables, saved filters, exports, analytics              |
| Customer                | Personal phone                                          | Mobile-first portal, plain language, no installation   |
| Technical admin         | Desktop                                                 | Settings, diagnostics, backups, plugins, system health |

## 3. Global information architecture

```text
Overview
Workshop
  ├─ Queue / Board
  ├─ Service Orders
  ├─ Schedule
  └─ Quality Control
Customers
Bicycles
Inventory
  ├─ Catalog
  ├─ Stock
  ├─ Movements
  └─ Locations
Sales
Purchasing
Communications
Knowledge
Analytics
Automations
Administration
  ├─ Users & Roles
  ├─ Locations
  ├─ Branding
  ├─ Integrations
  ├─ Plugins
  ├─ Backups
  └─ System Health
```

Navigation is capability-aware but keeps a stable conceptual order. Global search covers customer, bicycle, order, SKU and serial identifiers. Desktop supports `Ctrl/Cmd + K`, but command palette is never required for operation.

## 4. Responsive shell

| Viewport     | Behavior                                                                  |
| ------------ | ------------------------------------------------------------------------- |
| ≥1280 px     | 248 px sidebar, 56 px top bar, fluid content, optional context panel      |
| 1024–1279 px | Collapsible 72/232 px sidebar, drawer secondary content                   |
| 768–1023 px  | Tablet landscape, navigation drawer, sticky actions, selected split views |
| 640–767 px   | One column internal UI, bottom action bar for frequent actions            |
| <640 px      | Internal contingency support; Customer Portal is first-class              |

Use responsive breakpoints plus container queries so components adapt to available space, including plugin slots and context panels.

## 5. Role-aware home

- **Owner/Admin:** revenue, cash, active orders, inventory risks, capacity, alerts, system health.
- **Manager:** workshop queue, mechanic workload, pending approvals, missing parts, today's pickups.
- **Reception:** new order, appointments, ready orders, payments and messages.
- **Mechanic:** my work, in-progress, waiting parts, checklists, QC and Knowledge.
- **Sales:** new sale, SKU/stock search, authorized discounts, returns, cash.
- **Viewer:** read-only widgets allowed by capabilities.

Dashboards are capability-composed widgets, not hardcoded apps by role name.

## 6. Workshop Mode

Workshop Mode is an official interaction mode for mechanic/tablet operation.

- Primary actions: minimum **56 × 56 CSS px**.
- Secondary touch controls: minimum 48 px.
- Effective base type: 17–18 px.
- Maximum four persistent action groups.
- Notes, checks and measurements save locally immediately.
- Camera flow includes preview, category and pre-upload compression.
- Optional Glove Mode increases targets and spacing.
- Future voice/hardware hooks are allowed but not required in V1.

## 7. Offline and sync UX

| State       | Meaning                             | UI                                        |
| ----------- | ----------------------------------- | ----------------------------------------- |
| Synced      | Local and server confirmed          | Check + “Synced” when relevant            |
| Local saved | Persisted on device, not yet remote | “Saved on this device”                    |
| Syncing     | Mutations in transit                | Discreet progress                         |
| Offline     | Server unreachable                  | Persistent compact banner, work continues |
| Conflict    | Resolution required                 | Persistent Issue Center action            |
| Blocked     | Invalid mutation/permission change  | Explain, preserve data, guide resolution  |

```text
local transaction
→ immediate local success
→ durable mutation_queue
→ background sync
→ server confirmation / persistent issue center
```

## 8. Critical flows

| ID    | Flow                   | Happy path                                                                                |
| ----- | ---------------------- | ----------------------------------------------------------------------------------------- |
| FL-01 | Bicycle intake         | Find/create customer → bike → intake → photos → symptom → priority/date → order → receipt |
| FL-02 | Diagnosis/estimate     | Inspection → findings → work/parts → estimate → preview → publish/send                    |
| FL-03 | Customer authorization | Secure link → review → approve/decline → evidence → notify shop                           |
| FL-04 | Repair                 | Claim work → tasks/checks → parts → notes/photos → complete → QC                          |
| FL-05 | Quality control        | QC checklist → pass/rework → ready → communication                                        |
| FL-06 | Delivery               | Order → balance → payment → docs → delivered → closed                                     |
| FL-07 | POS                    | Scan/search → cart → payment → receipt → stock ledger                                     |
| FL-08 | Purchasing             | Supplier → PO → receive → cost → inventory movement → close                               |
| FL-09 | Inventory              | Find → per-location stock → movements → compensating adjustment                           |
| FL-10 | Communication          | Context → channel → template → preview → send/queue → delivery state                      |
| FL-11 | Automation             | Trigger → conditions → actions → test → enable → log                                      |
| FL-12 | Backup/restore         | Health → backup → verify → rehearsal/controlled restore                                   |

## 9. Screen inventory

- `SCR-001` Overview
- `SCR-010` Workshop Board
- `SCR-011` My Work
- `SCR-012` Service Order Detail
- `SCR-013` Workshop Task
- `SCR-014` Quality Control
- `SCR-020` Customers
- `SCR-021` Customer Detail
- `SCR-030` Bicycles
- `SCR-031` Bicycle Passport
- `SCR-040` Catalog
- `SCR-041` Stock
- `SCR-042` Inventory Ledger
- `SCR-050` POS
- `SCR-060` Purchasing
- `SCR-070` Communication Hub
- `SCR-080` Knowledge
- `SCR-090` Analytics
- `SCR-100` Automations
- `SCR-110` Administration
- `PORT-001` Customer Tracking
- `PORT-002` Estimate Authorization
- `PORT-003` Documents/Receipt

## 10. Service Order layout

```text
┌────────────────────────────────────────────────────────────────┐
│ #1047 · Trek Marlin 7     IN PROGRESS       $1,280   Sync ✓  │
│ Customer · promised time · mechanic                            │
├────────────────────────────────────────────────────────────────┤
│ Intake | Diagnosis | Work | Parts | Photos | Payments | History│
├───────────────────────────────────────┬────────────────────────┤
│ Main task workspace                   │ Context panel          │
│ checklist / notes / parts / actions   │ customer / bike        │
│                                       │ alerts / authorization │
└───────────────────────────────────────┴────────────────────────┘
```

The status always has text semantics. Irreversible actions such as payment, delivery and cancellation require explicit review. Tablet converts context to drawer and keeps primary actions sticky.

## 11. Intake performance path

1. Find customer by phone/name/QR/serial.
2. Select bike or minimal capture.
3. Record customer's symptom, quick tags and photos.
4. Select service template or open diagnosis.
5. Set priority/estimated date.
6. Confirm summary and issue receipt/QR.

**UX target:** for an existing customer and bicycle, a basic service order should be achievable in under 60 seconds in happy-path usability testing.

## 12. POS and data-dense UI

- Search/scan receives initial focus.
- Cart shows quantities, stock warnings, price origin and discount traceability.
- Payment is a separate commit surface.
- Tables use controlled sorting/filtering/pagination and saved column settings.
- Virtualization is introduced only when needed and after accessibility validation.
- Comfortable density is default. Compact is desktop-only opt-in. Touch preserves ≥44 px targets.

## 13. Customer Portal

Mobile-first, low cognitive load, no mandatory app installation.

- Current status and next action first.
- Estimate shows work, rationale, price by item, photos and total.
- Secure capability token only exposes allowed order/customer data.
- Expired links provide safe recovery.
- Mechanical jargon gets plain-language explanation where useful.

## 14. Visual design direction

**Workshop-grade, precise, calm.** Hierarchy relies on typography, spacing, borders and surfaces instead of excessive cards/shadows.

- Typography: **Inter Variable**, bundled locally; system fallback.
- Base spacing unit: **4 px**.
- Radius: 6 px small controls, 10 px panels, 14 px large dialogs.
- Borders: 1 px structural, 2 px focus/emphasis.
- Elevation: max three levels.
- Icon system: consistent line icons such as Lucide.
- Motion: 120–200 ms local feedback, 200–280 ms overlays, reduced-motion compliant.

## 15. Semantic tokens and white labeling

Branding can alter brand identity but not operational semantics.

```css
@theme {
  --font-sans: 'Inter Variable', ui-sans-serif, system-ui, sans-serif;
  --spacing-unit: 0.25rem;
}

:root {
  --brand-primary: oklch(0.57 0.19 252);
  --brand-secondary: oklch(0.54 0.1 210);
  --surface-canvas: oklch(0.985 0.004 250);
  --surface-panel: oklch(1 0 0);
  --text-primary: oklch(0.23 0.02 255);
  --text-muted: oklch(0.48 0.02 255);
  --border-default: oklch(0.88 0.01 255);
  --state-success: oklch(0.52 0.15 145);
  --state-warning: oklch(0.63 0.14 75);
  --state-danger: oklch(0.54 0.2 27);
  --state-info: oklch(0.55 0.17 250);
}
```

Protected: danger, success, warning, info, focus and disabled semantics. Brand editor must reject configurations that break contrast in critical surfaces.

## 16. Color schemes

- Light
- Dark
- High Contrast
- Workshop High Visibility optional preset

## 17. Component architecture

### Primitives

Button, Input, Label, Checkbox, Radio, Switch, Select, Combobox, Dialog, AlertDialog, Popover, Tooltip, Tabs.

### Navigation

AppShell, Sidebar, Breadcrumbs, Tabs, CommandPalette, ContextDrawer.

### Data

DataTable, FilterBar, ColumnPicker, Pagination, EmptyState, Skeleton, MetricCard.

### Domain

OrderStatus, BicycleIdentity, CustomerSummary, EstimateLines, InventoryMovement, PaymentPanel.

### Offline

SyncBadge, OfflineBanner, MutationIssueCenter, ConflictResolver.

### Workshop

WorkshopTask, LargeChecklist, TorqueEntry, PhotoCapture, PartConsume.

### Portal

TrackingTimeline, AuthorizationCard, SecureLinkError.

Radix Primitives provide behavior/accessibility foundations while the project owns styling, tokens, APIs and tests.

## 18. Forms

- Visible labels for important inputs.
- Placeholder never substitutes label.
- Validate at sensible timing, not while the first character is being typed.
- Autosave reversible operational data.
- Payment, delivery, cancellation, authorization and destructive adjustments use review/commit.
- Reuse existing data to reduce redundant entry.
- Scan/photo inputs always have manual alternatives.

## 19. Accessibility

Target: **WCAG 2.2 AA** for complete Core and Portal workflows.

- Full keyboard operation for Core flows.
- Proper accessible name/role/value/status messages.
- General touch baseline **44 × 44 CSS px**.
- Workshop primary controls **56 × 56 CSS px**.
- Color never carries meaning alone.
- Focus ring is visible and never hidden under sticky UI.
- 200% zoom and narrow-width reflow without loss of functionality.
- `prefers-reduced-motion` respected.
- Errors identified next to fields and summarized for long forms.

## 20. Content and i18n

- Direct, neutral, professional operational language.
- Errors explain what happened, what was preserved and next action.
- Locale-aware dates/money/numbers.
- Units are explicit.
- Translation uses semantic keys.
- Layout tolerates 30–40% text expansion.

## 21. Status vocabulary

- Work Order: Draft, Received, Inspection, Diagnosis, Awaiting estimate, Awaiting authorization, Authorized, Queued, In progress, Waiting parts, On hold, QC, Rework, Ready, Delivered, Closed, Cancelled, Declined.
- Inventory: In stock, Low, Out, Reserved, Incoming, Damaged, Quarantined.
- Payment: Unpaid, Partial, Paid, Refunded, Failed, Voided.
- Communication: Draft, Queued, Sent, Delivered, Read when available, Failed.
- Sync: Local saved, Syncing, Synced, Offline, Conflict, Blocked.

## 22. Feedback and recovery

- Toast: non-critical ephemeral confirmation only.
- Inline: form problems.
- Banner: connectivity/degraded service/stale data.
- Issue Center: conflicts, blocked mutations, failed uploads.
- Dialog: high-risk irreversible decision.
- Undo: preferred for reversible actions.
- Crash recovery: restore drafts/local changes and explain pending state.

## 23. Data visualization

Prefer bars, lines and direct metrics. Avoid decorative gauges and donuts when a number plus delta answers the question more clearly. Critical charts also expose a table or textual summary. Forecasts show uncertainty.

## 24. Print and labels

- 58/80 mm receipts plus A4/Letter fallback.
- Service-order print view without unnecessary backgrounds.
- Bike QR label contains ID/QR + human-readable short code, no PII by default.
- Stock labels support SKU/barcode and location.
- Customer documents use configurable white-label tokens.

## 25. Plugin UI

Plugins may extend approved slots: dashboard widgets, detail tabs, settings, actions and reports. They cannot replace the Core shell, auth UI or semantic status renderer. Official/Verified plugins consume tokens, remain inside error boundaries and pass the same accessibility gates.

## 26. Privacy-respecting UX telemetry

External telemetry is optional. Measure aggregate task duration, error rates, sync issues and performance. Do not collect customer names, phones, messages, notes, photos or payment data by default.

## 27. Perceived performance budgets

- Cached app shell: visible interaction target <1 s on target devices.
- Local navigation: immediate feedback <100 ms and perceived completion <300 ms.
- Local search: initial results <150 ms for typical datasets.
- Local save acknowledgement: <100 ms after local commit.
- Avoid repeated main-thread tasks >50 ms.
- Image processing should not block the primary flow.

## 28. Usability research

| Test  | Profile       | Acceptance                                               |
| ----- | ------------- | -------------------------------------------------------- |
| UT-01 | Reception     | Existing customer/bike order in <60 s                    |
| UT-02 | Mechanic      | Checklist + photo + part with glove simulation           |
| UT-03 | Offline       | Continue work and understand sync state without training |
| UT-04 | Conflict      | Resolve guided conflict without data loss                |
| UT-05 | POS           | Scan 5 products, correct quantity, charge                |
| UT-06 | Customer      | Authorize estimate on mobile and understand total/scope  |
| UT-07 | Accessibility | Intake/authorization via keyboard + screen reader        |
| UT-08 | Admin         | White-label configuration without contrast failure       |

## 29. Cross-cutting acceptance

- `AC-UX-001`: Core flows do not require Internet except intrinsically connected integrations.
- `AC-UX-002`: Every mutation communicates local and eventual sync state where relevant.
- `AC-UX-003`: No drag-only functionality.
- `AC-UX-004`: Critical states never use color alone.
- `AC-UX-005`: Core targets ≥44×44, Workshop primary ≥56×56 unless documented exception.
- `AC-UX-006`: Branding cannot break contrast or protected semantic states.
- `AC-UX-007`: Customer Portal works at 320 CSS px and 200% zoom.
- `AC-UX-008`: Keyboard path for reception, service order, inventory and POS.
- `AC-UX-009`: Issue Center retains actionable failures until resolved/acknowledged.
- `AC-UX-010`: Plugin visual failures are locally isolated.
- `AC-UX-011`: Empty/loading/local/error/offline/permission states are defined where applicable.
- `AC-UX-012`: Modals are not used for routine navigation/information.

## 30. Definition of Done for UI features

1. Uses design tokens instead of repeated arbitrary values.
2. Light/dark/high-contrast state evaluated where applicable.
3. Keyboard and focus order verified.
4. Accessible labels, roles, states and messages verified.
5. Windows desktop and Android tablet responsive QA passed.
6. Offline/local/sync/conflict/error states implemented.
7. Pending local work survives close/reopen.
8. Component tests cover meaningful states.
9. Visual regression coverage for critical screens/components.
10. Relevant usability acceptance passed.
11. Localization/text expansion checked.
12. No accidental PII in analytics/logs.

## 31. Accepted Design ADRs

| ADR      | Decision                                                                | Status   |
| -------- | ----------------------------------------------------------------------- | -------- |
| DADR-001 | Workshop-grade, precise, calm custom design language                    | Accepted |
| DADR-002 | Tailwind CSS 4.x + CSS theme variables/container queries                | Accepted |
| DADR-003 | Radix Primitives under project-owned component layer                    | Accepted |
| DADR-004 | TanStack Table stable v8 until v9 exits beta and migration is justified | Accepted |
| DADR-005 | Inter Variable bundled locally                                          | Accepted |
| DADR-006 | 44 px general touch baseline, 56 px Workshop primary                    | Accepted |
| DADR-007 | Comfortable default, compact desktop opt-in, Workshop enlarged          | Accepted |
| DADR-008 | Configurable brand tokens; protected semantic operational tokens        | Accepted |
| DADR-009 | Light + dark + high contrast + optional Workshop high visibility        | Accepted |
| DADR-010 | Separate mobile-first Customer Portal experience                        | Accepted |
| DADR-011 | Explicit persistent sync state + Issue Center                           | Accepted |
| DADR-012 | Versioned plugin UI slots and local error isolation                     | Accepted |

## 32. Outputs for Phase 5

- Frontend route map and capability matrix.
- Component package structure and component documentation architecture.
- Screen-state fixtures for Playwright and visual regression.
- Design-token source and brand schema.
- Prototypes for Intake, Service Order, Workshop Task, POS and Customer Authorization.
- Automated + manual accessibility matrix.
- Plugin UI extension contract.
- Print stylesheet and document tokens.

## 33. Technical references

- W3C, WCAG 2.2: https://www.w3.org/TR/WCAG22/
- Radix Primitives accessibility: https://www.radix-ui.com/primitives/docs/overview/accessibility
- Tailwind CSS responsive design: https://tailwindcss.com/docs/responsive-design
- TanStack Table React: https://tanstack.com/table/latest/docs/framework/react/react-table
