# PR #58 · Source-bound qualification and pending spec gates

## Current checkpoint

Reconciled on 2026-10-25 using AGENTS.md, Master Agent Loop v0.2, execution state,
the manual checklist, Foundation v0.2, Phase 10, the Increment 2 plan and current
quote-effects/recovery/runtime requirements. This is a documentation-only status
correction, not a new architecture decision or release declaration.

- PR: [#58](https://github.com/IzignaMx/open-cycling-workshop/pull/58), draft and unmerged.
- Qualified product head: `21245faacc991d91c1dd334bd37ba49c17141252`.
- Tested merge: `5e2e5409936bd0ac5b31e7a508b35c433f91ca41`.
- Product/tested tree: `69e1ee2e0f5d73acb5ef805ba4bf47666a29926a`.
- Base main: `8a7eeecc39b0a43097484d10dc30af541ae38156`.
- Active release remains **V0.1, partial**. Automated qualification is not
  physical-device acceptance, installation readiness or quote API/UI activation.

This record qualifies only the named source. A documentation successor has a
different tree and requires its own applicable checks; its PR description must
report those separately. Earlier failures and dated pending-state snapshots are
preserved, not retroactively rewritten as passes or reopened as new trial requests.

## Verified hosted evidence

| Scope                      | Exact run                                                                                    | Result and boundary                                                                                                                                                                                                                                                                           |
| -------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Full Python / aggregate    | [CI 39990179262](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39990179262) | 4,649 unique collected cases; shard A 2,645 passed + 11 expected skips, B 1,946 + 47; total 4,591 passed, 58 expected skips, no unrun/error/deselected cases. Aggregate 27/27 controls passed.                                                                                                |
| Recovery / containment     | Same CI                                                                                      | All six mandatory restore identities passed setup/call/teardown: database, current branding, legacy branding, generated counts, quote repository and service. Both shards' primary and independent manifest-owned container cleanup proved absence. Builder cleanup remains **not assessed**. |
| Security                   | [39990179253](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39990179253)    | Ten scanner canaries, 413-commit full-history scan with zero findings, REUSE, dependency audit and Trivy passed. No advisory suppression added.                                                                                                                                               |
| Local runtime / ARM        | [39990179250](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39990179250)    | Eleven runtime checks, three restarts, authentication recovery and branding restore passed. Native ARM64 decoder and all three ARM64 builds passed; physical hardware explicitly untested.                                                                                                    |
| DCO                        | [39990179190](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39990179190)    | Passed.                                                                                                                                                                                                                                                                                       |
| Bounded quote microfixture | [39990179270](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39990179270)    | Passed; not product-capacity qualification.                                                                                                                                                                                                                                                   |
| Optional QEMU diagnostic   | [39990179217](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39990179217)    | Failed, **NON-QUALIFYING**: original child parent-wall timeout; instrumented second child last reached Pillow import. Original cause remains unproven; this is neither native ARM failure nor physical Raspberry evidence.                                                                    |

Independent read-only evidence review checked downloaded artifacts, exhaustive
ordered collection/skip identities, restore phases and source bindings:

| Artifact                 | ID          | SHA-256                                                            |
| ------------------------ | ----------- | ------------------------------------------------------------------ |
| Full Python shard proofs | 12517954031 | `0fc71f81d9d7d78dbdbcb0a88927eb90d3a4aedb31cbd796203ed4140cef4466` |
| Aggregate qualification  | 12519876047 | `965758e4489fd69347861bc47a5b49a827418c1a335b9438f647828e43615abd` |
| Runtime evidence         | 12517338160 | `06dcc07bc23d2cf45b515bf82983f91806d620b4c44b2805f3178719ea68773a` |

The approved serial route retains **two 900-second workloads**, worker **768 MiB**,
PostgreSQL **1,024 MiB memory / 512 MiB data**, one CPU each and zero swap; the
Python job envelope is 55 minutes. Concurrent candidate caps total 1,792 MiB,
excluding host/daemon/build overhead. These are test-containment limits, not a
measured deployment capacity. This update changes no limits or test bodies and
does not manually rerun a consumed experiment.

## Spec-linked next steps, in priority order

1. **Integration gate:** review the final documentation/source candidate and its
   exact-head checks. Keep PR #58 draft and unmerged unless separately authorized;
   no deployment or real-workshop mutation follows from CI success.
2. **V0.1 physical acceptance — R01-T035, blocked:** execute the actual Windows
   and Android matrix and record source, device/browser versions, install,
   offline/reload/process restart, pending-work preservation, exactly-once
   reconnect, conflict, keyboard/touch and storage-pressure results in the
   [Tier 1 results template](../11-device-qualification/2026-08-31-tier1-results.md).
   Hosted Chromium/native ARM cannot close this task. Manual accessibility and
   assistive-technology evidence remains separate.
3. **Recovery integrity — implementation pending:** implement the full-history
   pre-reopen validator required by the [bounded-effects amendment, sections 6–8](../02-technical-architecture/2026-10-17-bounded-quote-order-effects.md)
   and [semantic closure](2026-10-17-quote-semantic-closure.md). Validate every
   quote-linked pair and complete retained history on isolated restored data;
   refuse corruption/unsupported tuples before reopening, rotate incarnation
   and prove same-ID replay adds no effects. Six valid restore cases do not
   prove this missing validator.
4. **Quote application/exposure — Tasks 5/8 remain partial:** prove every HTTP
   transition, service-order sync update and order-linked inventory ingress
   serializes with enrollment and fails closed for quote-managed orders. Retain
   fresh authority, HTTP/TypeScript transport boundaries, real cancellation,
   separate quote-grant adoption and old-writer rollout gates. Private service
   and finite race passes do not expose or qualify API/UI.
5. **Capacity/latency/contention — unqualified:** prepare an independently reviewed
   plan before any separately authorized trial. Preserve PR #51/#56 failed trials;
   do not repeat them or increase budgets. Installation-scale migration/restore,
   physical corruption, real-volume RPO/RTO and full-history capacity are not
   established by synthetic CI fixtures.
6. **Laptop, then Raspberry — blocked on physical/operator evidence:** follow the
   [current runtime runbook](../07-operations/2026-10-14-local-runtime.md) for
   actual laptop/Docker Desktop, trusted LAN clients, Raspberry storage/power,
   encrypted offsite recovery and password/CA-rotation rehearsals. Preserve
   browser journals, database/assets and TLS identity. Historical disposable
   Tier 1 fixture instructions are not installation instructions: never delete
   installation volumes or weaken browser/TLS security to obtain a pass.
7. **Later Increment 2 work remains dependent:** local drafts/UI, lifecycle E2E
   and increment qualification are still open in the [Increment 2 plan](../superpowers/plans/2026-09-01-v0.2-increment-2-budgets-inventory.md).
   Its original Task 7 quote-sync proposal must follow the accepted online-command
   boundary, not silently introduce offline financial mutation replay. Do not
   mark Tasks 5/6 or the whole increment complete from suite success alone.

No physical computers or saved coding environments were available for this
reconciliation. GitHub evidence and bounded cloud-file documentation validation
are the available proof; no installation, merge, deployment, credential change
or real-data operation was performed.
