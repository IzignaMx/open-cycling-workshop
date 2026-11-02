# Same-session capture reload recovery · 2026-11-02

Status: **Locally verified candidate; publication authorization and hosted qualification pending**.
Base `02ec2f059e610768cb58ce20812fed33999bfa7a`. V0.1 remains partial.
The accepted [design](../superpowers/specs/2026-11-02-capture-reload-recovery-design.md)
and [implementation plan](../superpowers/plans/2026-11-02-capture-reload-recovery.md)
are authoritative for exact interfaces, fixed feedback and the live implementation
ledger. This record separates policy, historical receipts and new evidence.

## Explicit policy decision and rejected alternatives

The user authorized shared IndexedDB storage at **07:25 UTC, 2026-11-02**:
24 hours of draft-PII retention, purge on logout and expired cleanup on app open.
Design/plan review was accepted at07:37. Earlier indefinite-retention and
sessionStorage-only proposals are unselected historical alternatives, not the
approved policy. This approval does not include publication, merge or deployment.

TTL is **24 hours from first successful persistence of a content generation**;
it is **not sliding** with edits, restore or verification. Protection preserves the
TTL anchor even after deleting content. Later genuinely new input may start a new
generation. Invalid/rolled-back clocks fail closed; no deletion while the browser
is closed, physical-clock authority or guaranteed disk erasure is claimed.

## Prior independently accepted source, not new implementation evidence

Coordinator-supplied PR-body receipts, **not redownloaded** archives by this worker:

- [PR79](https://github.com/IzignaMx/open-cycling-workshop/pull/79), main
  `7cf38e17e1981607287b0d5a41abedeead3bcf5e`: fresh CI41391295843 accepted,
  27/27 aggregate, Python5,559 +58 expected skips, direct111/aggregate111 browsers.
- [PR80](https://github.com/IzignaMx/open-cycling-workshop/pull/80), main
  `02ec2f059e610768cb58ce20812fed33999bfa7a`, tree
  `7ee81665bd50ca8d9851a43e601f16fe04194666`: CI41399878499 attempt1,
  27/27 aggregate, Python5,564 +58 expected skips, frontend1,119/API1,
  direct111/aggregate111 zero retries. Runtime41399878602, Security41399878768,
  micro41399878505 and preview41399878608 accepted; source/archive review retained
  in the coordinator's receipt.

These close the named prior source checkpoints, not this changed tree. Source-
authored pending fields remain historical with supersession links. PR79 volatile
visit protection and PR59 full-history validation are not reopened as missing work.

## Bounded selected behavior and non-replay boundary

Restore existing customer/order input only for the exact same independently
verified session and semantic scope. Shared checkpoint metadata and expiring PII
content are separate. A copied tab hint cannot rearm a shared PROTECTED checkpoint.
Only eligible UNSENT content may restore; restored input never calls create itself.
Legacy sessions without the expected hint require explicit new binding enrollment;
missing expected metadata is not first-time enrollment or proof of an empty draft.

Before dispatch, positively acknowledged current protection must commit and delete
that channel's payload atomically. Uncertain protection means no create invocation.
Trusted saved/not_saved may settle only the exact admitted attempt/generation;
UNKNOWN remains PROTECTED. Missing content, TTL expiry or cleanup never proves
rollback or business commit and never resets protective metadata to sendable.
Late edits while protected cannot be promised recoverable after a crash.

The design bounds each content projection to64KiB without truncation, two content
channels per checkpoint and maintenance pages of64. Oversize remains visible in
memory and refuses dispatch; no total historical metadata capacity claim exists.
Closed/protected metadata is retained without private fields, not evicted to rearm
old bindings. Hashes/IDs are linkable metadata, not anonymization or encryption.

Logout/security closure invalidates volatile writes synchronously and attempts
scoped content purge. Failed deletion is reported truthfully; a single no-content
cleanup locator can support retry, not an unbounded queue. Missing/lost/overlapping
locators limit reliable retry; only later TTL cleanup can then be promised for
undiscoverable content. Existing journals and business evidence are never deleted.

## Migration, compatibility and traceability

The design adds v8 stores to the actual v7 authenticated database, preserving all
existing rows. V8 implementation is not declared complete here. Keep versionchange
close, blocked-upgrade feedback, v7→v8 preservation and actual mixed-writer tests.
The actual old binary can open v8; database-version refusal is not a safety fence.
The existing simulated future-v8 preservation case must move to future-v9 without
losing assertions. The quote plan's future-v8 reservation is explicitly nonbinding;
consuming this version does not implement quotes. No destructive downgrade/DB clear.
Old runtime code does not implement the new guarantees; no universal old-writer
capture idempotency is implied.

FR-CUS-001/R01-T030 and FR-SVC-001/R02-T005 retain unique **partial** ledger rows.
Their current target is `apps/web/e2e/capture-reload-recovery.spec.ts`; authorship or
collection is not native execution. Prior capture-visit and late-receipt coverage
remain retained. UX§22/OFF-007 are only partially addressed: exact-session reload
is not full crash, device-loss, eviction, rollback or physical storage acceptance.
The existing OFF-007/R01-T035 row remains blocked; no global completion is added.

## Initial evidence and outstanding gates

The source owner reported six actual-controller/fake-IDB baseline RED reproductions:
online/offline unsent loss and customer/order pending/unknown readmission. A
separate committed-create/copy-sessionStorage probe showed copied admission can
regain offline READY, rejecting the per-tab-only alternative. These are bounded
reproductions, not native browser evidence or new suite passes. Preserve them under
`artifacts/durable-capture/`; source-owner plan records subsequent RED/GREEN.

Documentation TDD: four expected failures/eight retained passes preceded the new
checkpoint, receipts, ledger and reservation note. An intermediate run had eleven
passes and one missing-E2E-path failure; retained repository suite146/147 failed
on that same honest file-existence contract. After the meaningful native test file
was authored, the repository suite passed147/147 with no skips. Ruff lint/format,
Prettier, repository verifier, local links and diff checks passed. Logs are
`docs-red.log`, `docs-green-attempt.log`, `docs-repository-attempt.log` and
`docs-green-final.log` under `artifacts/durable-capture/`. These results prove only
documentation contracts; the native file is authored, not executed, and its final
source/static review remains owned by the browser author.
Implementation, native reload/clone/upgrade/privacy/accessibility, full retained
suites and independent final review remain gates. No new publication authority.

Physical T1–T8/R01-T035, real installation/recovery/capacity and broader OFF-007 remain
open. Historical cleanup41011497919 stays UNKNOWN; ownership40927223929 stays SPENT.
Pages remains source3c6513d. Server backup does not include these browser-local rows;
no checkpoint export/restore or application encryption is delivered by this slice.

## Blocking mixed-version evidence — 07:50 UTC

Independent actual old-v7/new-v8 runtime reproduction with synthetic fake IndexedDB
created two journal operations with distinct mutation IDs: a v8 acknowledged UNSENT
draft survived a real v7 command, then was restored unblocked and submitted again
by v8. This is a demonstrated persisted synthetic duplicate, not only call-count
evidence. Local passing tests cannot qualify this unsafe state. No publication occurred.

Shared commit version/sequence enforcement requires an expanded reviewed design.
The coordinator requested explicit approval at07:50; the user **approved at07:54**.
The expanded implementation and independent verification remain pending. Preserve
the approved07:25 retention policy separately. No fake
VersionError, test weakening or installation-only relabelling closes this finding.
Evidence: `artifacts/durable-capture/mixed-v7-independent.test.mjs` and
`mixed-v7-independent.log`; the handoff retains the exact question and explicit07:54 approval.

## Corrective implementation checkpoint — 08:05 UTC

The approved atomic writer-epoch correction now has independent synthetic evidence:
actual old-v7 commit followed by new reload refuses the stale draft; an intervening
two genuine new commands cannot heal its old epoch. A protected pending new attempt
also remains fenced after actual old-runtime ownership takeover, including subsequent
new-runtime reverification before its original repository callback resumes. The
original duplicate RED is retained; no fake version refusal or journal reset was used.

Independent review also exposed logout before hydration leaving private content.
The correction resolves only a deletion locator from metadata, never restores fields,
and purges the exact checkpoint generation. Twelve failure-path tests pass; final
independent lookup-failure/new-login race review remains pending at this checkpoint.

Fresh frontend core: **1,214 passed, zero skipped/cancelled** (`core-third.log`).
Earlier interrupted core runs and failures remain evidence, not passes. Ten browser
cases collect and pass strict TypeScript/lint/format checks (`e2e-writer-static.log`),
but **zero native cases have executed locally**. The tenth uses a genuine native
transaction with a narrowly targeted old-writer metadata omission, not an actual old
browser bundle; actual old-runtime evidence above uses synthetic fake IndexedDB.
Repository contracts pass147/147. Full Python invocation, final build/typechecks and
independent mutation/source review remain pending. This is not release acceptance.

### Local Python boundary — 08:07 UTC

The complete local pytest invocation finished **4,954 passed, 671 skipped, 12
warnings** (`python-full.log`). PostgreSQL-dependent tests and hosted scanner
canaries were not executable in this environment; these skips are not accepted as
the hosted full-suite gate. The warnings concern existing Starlette/httpx and
SQLite datetime deprecations. Initial collection failed because only root dev
packages had been installed; frozen offline workspace dependency synchronization
resolved it without changing dependency manifests or locks. Fresh remote main
still equals the recorded base at08:07. Full hosted qualification remains pending.

## Final local source checkpoint — 08:12 UTC

The bounded independent review reports **no unclosed high-severity finding**. Seven
real-controller probes and49 store/authority/migration tests pass; two isolated
copied-source mutations are killed (bypassing epoch checks and reusing stale epochs).
The historical mixed-version duplicate and prehydration logout findings above are
resolved locally, not erased from the evidence history. No universal protection
against manual duplicates or arbitrary older clients is claimed.

A final repeat found one legacy timing assertion completing before actual READY;
its bounded completion wait retains all network, session and journal assertions.
Five isolated repeats and the fresh full suite pass: **1,214/1,214**, zero failures,
skips or cancellations (`core-exact-final.log`). Normal/offline typechecks, PWA build,
clean-product ESLint, full Python Ruff/format/mypy and generated OpenAPI/TypeScript
contracts pass. The existing large-chunk build warning remains. Ignored generated
evidence trees are excluded from the local lint invocation, not product source;
no lint configuration or security checks were relaxed.

The package contains34 source/test/document files, with no dependency, lockfile,
backend, workflow or deployment changes. Ten browser cases remain authored and
collected, **not executed**. PostgreSQL/scanner and complete hosted gates are still
required. Independent source review does not substitute for those gates. A separate
publication/conditional integration authorization is required before any remote PR.

## First hosted attempt and scoped test correction — 09:44 UTC

PR81 first published head `0f0781c551c4ebf46d85b7d7df3ef07f03d211c7`, tree
`74ac222cd5021fcb87360f54b226c5af72034ebc`, ran CI41413376026. Full Python was
independently accepted at5,567 passed plus58 exact expected skips, with both shard
cleanup proofs. Runtime/security/containment/DCO companions passed their separate
source-bound reviews. **The overall attempt failed and is not acceptance.**

The isolated native kernel artifact recorded6 passes and8 failures, all retaining
an obsolete expected native version70 instead of the actual80. Its version/store
expectations and true-v6 fixture are corrected without weakening original-row,
old-client, index, blocked-upgrade or abort assertions. Four structural-theme
journeys independently retain the same obsolete70 expectation and now require80.

The aggregate recorded26/27 controls and92 browser passes/29 failures. Direct
browser/repeat stages were skipped after the kernel failure, so inventory-expiry
repetition correctly reported incomplete; this is not an observed expiry defect.
The large qualification archive exceeded the connector's512MiB transfer limit;
no size/access workaround was used. Available text summarizes failures but does
not retain their first assertions. This diagnostic limit is preserved explicitly.

Independent real ReactDOMServer rendering of both production components and the
actual shared Button, parsed with installed lxml, reproduced four selector REDs:
old exact `aria-describedby` equality matches zero forms because the attribute is
now a valid two-ID token list; generic status matching sees two separate messages.
Token-membership matching and the original command-status ID produce four GREENs.
This is rendered-HTML predicate evidence, **not native browser execution**. The
repair preserves all feedback, privacy, journal, keyboard and accessibility checks.
It does not claim that all29 hosted failures have been resolved before a new run.

The correction changes only six browser-test files, five additional to the original
package: **39 total files**. No production behavior, dependency, workflow, timeout,
retry policy or security control is changed by this repair. Independent diff review
accepted this bounded correction. Complete fresh exact-head CI and native evidence
remain mandatory before ready/merge, followed by fresh-main validation.
