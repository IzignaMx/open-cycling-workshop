# Branding administration readiness · 2026-10-26

> **2026-10-27 closure:** merged through PR #59 at `a9e161f`; exact-main
> CI 40428504739 passed 27/27, all 4,727 collected Python cases (4,669 pass /
> 58 expected skips), six restores, both cleanup proofs and retry-free direct/
> aggregate browsers. See [terminal evidence and remaining gates](2026-10-27-pr59-postmerge-reconciliation.md).
> The preparation/pending wording below is historical, not a new run or merge
> authorization. Physical, installation, capacity and activation gates stay open.

## Scope and preserved failure

Base PR #58 head: `8a48ecc991247958552fc64f6585ba97cf2cb27e`, tree
`514e9c2006b8ee2c612d7ba011b86d2496c2ff4a`. The draft remains unmerged;
there is no deployment or installation mutation. This test-only increment
follows AGENTS.md and Master Agent Loop v0.2. It preserves the shared-branding
ADR's FR-WL-001/002 and explicit, independent read/write grant boundaries.
No new architecture decision or product behavior is introduced.

[CI 40218677350](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40218677350)
finished successfully, but its aggregate browser report contains **79 clean
passes and one flaky retry pass**, not 80 first-attempt passes. Direct 80/80
and separate retry-free repetitions do not erase that aggregate failure.
Preserved aggregate artifact: `12608733977`; downloaded ZIP SHA-256:
`e1feffcf6b6ad78a06157bdd0602eb94d4c0ef60abb20d3c31a9cddec37cea32`.

`branding.spec.ts:535` (technical-user explicit grants) failed attempt 0 in
10,530 ms. `openBranding:145` waited 10,000 ms for the verification button to
be enabled, but it no longer existed. Its snapshot already showed “Mi sesión”
and the branding no-permission panel. Retry 1 passed in 704 ms. The exact
historical network scheduling is not retained; the report's failure and DOM
state are retained without reclassifying that attempt as successful.

## Demonstrated mechanism and minimal correction

The technical fixture has no capabilities, so its login helper deliberately
does not await an operational READY state. Production runtime login publishes
SELECTOR for a no-sync account and then awaits `verifyAccount()`. Account
verification publishes `verifying` before asynchronously admitting `connected`.
AdministrationPanel displays a disabled verification button while verifying,
then replaces it with the connected session and branding sections.

The old helper accepted the disabled button as visible, observed the session
absent once, and then waited only for the button to become enabled. Automatic
successful admission can remove that button instead. A controlled transition
immediately after the absent-session observation reproduces this failing branch
in the actual checked-in helper. A production authorization/cache change is
neither necessary nor justified by this evidence.

The corrected helper uses the existing Playwright assertion budget to poll for
either the visible session or the visible verification button filtered by
`:enabled`. Both observations are immediate; there is no detached-button
`isEnabled()` wait. It clicks only if the session is still absent. The final
exact session and branding-region assertions, every grant/UI/API assertion,
fixture tenant isolation, timeouts and configured retries remain unchanged.
No catch-and-ignore, forced click, fixed sleep or timeout increase is added.

This follows the existing administration helper's two-outcome readiness pattern
without its separate visibility/enabled lookup. It does not promise to mask
arbitrary subsequent loss of admission: failure to reach the required final
session or branding region must still fail.

## Regression and verification boundaries

The Node control test extracts and executes `openBranding` from the checked-in
TypeScript using its AST; it does not maintain a second implementation. It uses
the installed Playwright assertions and controlled locator observations. Before
the fix, five controls passed and the automatic-admission case failed at the
original `toBeEnabled`. After the fix, all six controls passed, including
already-connected, explicit verification, disabled-to-connected,
disabled-to-enabled, permanently disabled and missing administration cases.
The last two must reject, and the connected cases retain both final assertions.

These controlled observations are not browser/DOM evidence. Six additional
native synthetic-DOM cases execute that same helper with actual Playwright
locators. The transition is explicitly interleaved after the first session read,
not timed with a sleep; the synthetic fixture contains no credentials, storage
or API mutation. They are part of normal direct and aggregate browser execution.
Their native execution remains pending for the successor's normal hosted CI.

Local native launch was blocked by the executor's socket restriction. The
escalated launcher also failed before starting due to its read-only mount setup;
no forbidden path was read or modified. The pinned browser installer returned
HTML rather than a ZIP and was stopped. No sandbox/security policy was changed.

Independent review caught a zero-height empty region in the new native fixture;
visible synthetic heading content corrected it without weakening the assertion.
Independent six-case controls, touched ESLint/Prettier, focused native-spec
TypeScript and diff whitespace checks passed after that correction.

Additional final local checks: all **934 frontend core tests passed** with zero
skips, normal web TypeScript and production PWA build passed, six CI-contract
checks passed, and Playwright collected all six new native cases. The build
retains its existing large-chunk warning. Initial local setup failures were
stale workspace links and absent fake-indexeddb; candidate-only links and the
locked 6.2.5 package (SHA-512 checked against pnpm-lock.yaml) restored the complete
run. A first build invocation used the repository root rather than apps/web and
failed to find index.html; the correctly scoped build passed. No dependency
manifest or lockfile changed, and these local checks do not qualify PostgreSQL,
full Python, native browser execution or the new hosted source.

## Remaining acceptance and unchanged gates

Status: **implemented_pending_evidence** until exact-successor hosted direct,
aggregate and existing retry-free repetition evidence is inspected, including
first-attempt counts. A green exit with retry passes is not clean acceptance.
The successor's PR metadata will record its terminal checks without inventing
a self-referential commit hash or creating a documentation/CI loop.

Retain the approved two serial 900-second Python workloads, 768-MiB worker,
1,024-MiB PostgreSQL memory, 512-MiB data and 55-minute exterior job. This increment
changes no CI configuration, resource policy, dependency, skip, restore proof,
security scanner or acceptance gate. No manual broad workflow dispatch is needed.

V0.1 remains partial. Physical Windows/Android, laptop/Raspberry, assistive
technology, installation recovery and full-history pre-reopen validation remain
separate open gates. Quote API/UI stays closed; capacity/latency and remaining
ingress/authority/adoption/old-writer gates are not closed by this helper fix.
See the [prioritized spec handoff](2026-10-25-pr58-status-reconciliation.md).
