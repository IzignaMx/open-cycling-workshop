# Product description → executable development coverage

## Decision and evidence boundary

The maintainer requested this audit and adjustment on 2026-11-02. GitHub's
repository API independently returned the same description supplied by the
maintainer (repository `IzignaMx/open-cycling-workshop`, ID `1327018760`).
Initial source inspected: `b88c4eee78d0603bb47368bcec83cd9567eac495` (PR78 main).
Reconciled source: `7cf38e17e1981607287b0d5a41abedeead3bcf5e` (PR79 merged main).
PR79 candidate qualification and merge are recorded by the coordinator in the
[PR79 receipt](https://github.com/IzignaMx/open-cycling-workshop/pull/79); its
fresh-main qualification is still pending at reconciliation. This is not new
archive validation. The matrix is a dated source inventory, not an automatically
refreshed deployment or postmerge acceptance claim.

**Outcome: complete planning coverage of the 20 description claims, not complete
implementation.** Existing Phase 1/10 already planned most business domains.
Missing links were agenda (UX named Schedule/appointments, but no FR/task),
staff availability/workload beyond IAM/Mechanic role, and specific acceptance
for operational metrics, business documents and retail-only profiles.

The [machine-readable coverage matrix](product-description-coverage.json) maps
all 20 claims to requirements, canonical tasks, phase, current source evidence,
acceptance scenarios and remaining work. Paths under `evidence_paths` are source
inventory or specifications, **not passed test receipts**. Planned claims cite
composition/spec files to demonstrate the inspected boundary, not prove absence
of every possible helper. The existing `traceability.csv` remains a bounded
verified/partial evidence ledger; do not fill it with invented test IDs for
planned modules. AC-009 still requires actual behavior tests for every V1 FR.

## Source-of-truth adjustments

- [Additive Phase 1 supplement](../01-functional-requirements/2026-11-02-product-description-supplement.md)
  defines 24 new FRs for agenda, staff operations, metrics, documents and profiles.
  All existing IDs and accepted ADRs remain unchanged.
- Phase 10 adds E27 Scheduling/E28 Staff Operations and R02-T024–R02-T029 after
  the existing 23 V0.2 tasks. Six new tasks, total 29; no old ID is reused.
- Existing document/white-label/analytics/profile tasks get explicit additional
  acceptance, not duplicate competing implementations or fabricated completion.
- No release gate is relaxed. Active V0.1 remains partial. Extending the future
  V0.2 plan does not authorize jumping over automatable V0.1 blockers.
- This plan amendment implements the explicit product-description instruction.
  New sync/domain architecture (notably schedule admission/conflict handling)
  requires its own ADR/design before code. No grants, schema or runtime change
  is introduced by this amendment.

## Claim summary and honest product state

| Claim group                     | Current evidence boundary                                                | Planned completion                                                                                                |
| ------------------------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| Open source                     | AGPL-3.0-only, DCO and source files exist                                | Full source/distribution/SBOM/governance qualification remains per release                                        |
| Offline first                   | Admitted operational records and journal/sync; bounded identity/recovery | Per-domain offline policy, durable intent, conflicts, physical restore and capacity                               |
| Modular                         | Explicit modular monolith; M0 descriptor data contract                   | M1 official reference, then isolated connectors/events and SDK/registry qualification; not a plugin runtime       |
| White label                     | App themes and shared workshop branding                                  | BrandProfile import/export, domain/contact and app/portal/print/message regression; not full white label today    |
| Workshop/store/related business | Workshop-oriented source, future POS and specialty boundaries            | Retail-only, workshop, combined and service/cooperative journeys; rental/fleet/ecommerce separate post-V1 modules |
| Customers/bicycles/orders       | Partial domain/API/UI/sync slices                                        | All FRs including privacy, transfer/passport, diagnosis/quote/authorization/repair/QC                             |
| Mechanics/knowledge             | Mechanic role and service-order foundations                              | Task assignment, QC, sourced procedures/torques, offline knowledge and workload                                   |
| Inventory/purchases/sales       | Ledger and scoped online reads; no full commerce UI                      | All movement types, supplier/PO receipts, atomic POS/payment/refund/cash and offline policy                       |
| Communication/automation        | Internal outbox and durable jobs, no business handler proof              | Consent/templates/providers/delivery and safe rules/conditions/actions/dry run                                    |
| Documents                       | Repository/operations docs and blob foundations                          | Revisioned business print/QR/export, privacy, retention and technical knowledge                                   |
| Agenda/personal                 | IAM exists; UX names appointments, no schedule domain                    | New staff/availability/appointment/conflict/list flows with separate offline admission design                     |
| Metrics                         | Broad E18/R09-T023, no operational dashboard                             | Versioned metric formulas, exact fixtures, privacy/freshness and accessible exports                               |
| Accessible/multiplatform        | PWA and automated source/browser evidence                                | WCAG 2.2 AA, physical Tier1 Windows/Android, actual LAN/install/restore and supported-version matrix              |

## Consistency rules for offline first

Offline first is mandatory, not a boolean marketing badge. It does not mean
all actions work offline or bypass authorization. Each vertical slice declares
read, draft, committed mutation, external side effect and reconciliation states.

1. Customer/bicycle/order records use only admitted identity/scope and existing
   journal policies; saving a form and retaining an unsent draft are distinct.
2. Connected administration and inventory reads remain **online-only** today.
   New stock or financial sync needs its domain-specific ADR, migration,
   idempotency, authority, conflict and multi-device tests first.
3. Accepted quote initial-command ADR remains authoritative: no automatic replay
   of quote authorization, stock consumption, financial effects or unknown
   receipts. Local preparation cannot be advertised as confirmed authorization.
4. Payment provider calls, message delivery and public portal access need network.
   Explicitly provisional records/queues cannot be labelled paid/delivered or
   globally conflict-free. Optional provider outage never blocks valid Core work.
5. Agenda offline booking is a provisional intent until constrained occupancy
   and current grants are checked; no silent double-confirmation. R02-T027 is a
   design/implementation gate, not a generic sync registration flag.
6. Server backup is not a browser-journal backup. Storage pressure, eviction,
   crash recovery, supported update migration and device loss require specific
   recovery evidence, never clearing local data to make a test green.

## Sustainable execution sequence

| Stage                           | Dependency / admission                                            | Deliverable and stop boundary                                                                                                                                                                                                  |
| ------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| S0 · Current integrity          | Exact PR79 source/CI/independent review, then fresh main          | Candidate merged; qualify its exact fresh main separately, not durable reload or global V0.1 qualification                                                                                                                     |
| S1 · V0.1 readiness             | Master Loop selection rule; retain R01-T035/T1–T8 blocks          | Highest-risk reproducible integrity/recovery gap first. Durable unsent draft/intent ownership requires separate design. If all automatable readiness is exhausted, report physical gates; do not manufacture more abstractions |
| S2 · Workshop core              | V0.1 acceptance or explicitly documented independent prerequisite | R02 original tasks, exact quote activation fences, repair/QC, then staff/agenda R02-T024–029. Do not expose quote routes before authority/receipt/coverage gates                                                               |
| S3 · Inventory/purchasing/POS   | Qualified workshop and authoritative stock/cost model             | V0.3→V0.4 ledger, procurement, sales/refunds and retail-only journey; money/stock atomicity before convenience UI                                                                                                              |
| S4 · Communications/portal      | Consent + scoped provider identity + durable delivery evidence    | V0.5→V0.6; schedule reminders remain disabled/unavailable until this stage, avoiding a V0.2/V0.5 cycle                                                                                                                         |
| S5 · Knowledge/automation       | Versioned domain events and action authorization                  | V0.7→V0.8 with provenance, idempotency, dry run, loop bounds and dead-letter visibility                                                                                                                                        |
| S6 · Full product qualification | All relevant domains plus source-bound evidence                   | V0.9→V1 white-label outputs, metric correctness, plugin compatibility, accessibility/platform/restore/security/pilots                                                                                                          |

M0 is already a historically qualified data-only prerequisite, not a future task
to reimplement. M1 is an independent optional reference only after current
higher-risk readiness work; no runtime SDK or connector identity follows from
M0. The full-history validator already has PR59 evidence and must not be
recreated because an old narrative says pending. Apply the newest source-bound
receipt before selecting work.

## Verification and next actionable work

The companion [implementation plan](../superpowers/plans/2026-11-02-product-description-alignment.md)
checks the mapping, all referenced IDs/paths, additive-task dependency graph and
truthful status boundaries. Those deterministic checks validate **planning
coverage**; they do not verify POS, appointment, metrics or other runtime behavior.

After PR79 qualification, inspect remaining unsent draft lifetime across full
reload/crash and durable intent/receipt correlation against UX §22 and OFF-007.
Reproduce behavior before selecting a fix, and preserve unknown/pending refusal.
Do not add a generic global store or extend financial sync as a shortcut. Select
only a bounded independently verifiable V0.1 readiness slice. The concrete next
implementation must state its invariant, design/ADR need, expected RED, migration
impact and acceptance before code; the matrix is not a giant all-at-once build.

## Still blocked or externally qualified

T1–T8 physical Windows/Android, R01-T035 100k storage/device qualification,
trusted LAN onboarding, laptop/Raspberry installation, power/storage recovery,
manual assistive technology and real capacity remain distinct. The historical
cleanup `41011497919` stays UNKNOWN. Measurement `40927223929` stays SPENT;
this plan does not authorize replay. Pages source `3c6513d` is unchanged.
No deployment, new account/credential, real provider request, legal/fiscal
certification or physical/destructive operation is performed by this audit.

## Local planning qualification — 2026-11-02

Baseline repository suite: 136 passed. The five new coverage contracts first
failed against missing planning artifacts (RED), then the final repository suite
passed 141 tests, including all five new contracts. Ruff lint and format, repository
verifier, JSON parsing, Prettier Markdown/JSON/YAML checks and `git diff --check`
passed. YAML syntax was checked through Prettier, not an unavailable PyYAML runtime.

Independent review accepted the documentation scope after resolving task-table
adjacency, workshop-only R02-T029 qualification (not premature retail acceptance),
canonical dependency equality/cycle checks and the E27/E28 macro dependency branch.
No runtime implementation, frontend suite, physical test, hosted CI, publication,
merge or release is qualified by these repository-contract results.

## Reconciliation after PR79 merge

The candidate was rebased on `7cf38e17e1981607287b0d5a41abedeead3bcf5e`. Both overlapping
files retain PR79 material: execution state preserves the active capture-visit
checkpoint and historical source-authored pending fields; the checklist retains
its original evidence with an explicit receipt boundary. All PR79 runtime files,
browser tests and its repository test remain byte-identical to merged main.
The new five planning contracts run together with the merged repository suite:
144 passed (139 merged baseline contracts plus five new planning contracts).
The original 141-test local receipt above remains tied to the earlier base.
PR79 supports volatile same-scope capture continuity, not durable reload/crash
recovery; no claim status is promoted to complete.

Independent reconciliation review accepted all 20 claims and the exact 12-file
scope, confirmed PR79 runtime/test preservation and independently ran 144 passing
repository tests. Fresh-main and publication gates remain separate.
