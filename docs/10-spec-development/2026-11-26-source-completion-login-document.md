# Preserve the checked destination document during login · 2026-11-26

## Scope and baseline

Baseline: merged main `810a4623a64c28d1abf0e40454129df780adb328` (PR122).
The [project and inventory audit](2026-11-25-project-inventory-audit.md#pr122-postmerge-evidence--2026-11-26)
records this exact main's successful CI separately from the known candidate and
older-baseline browser flakes. Inventory product scope and all FR-INV-001–012
remaining work are retained there. V0.1 remains **partial**.

This change is confined to browser-test authentication and its evidence. The
source-completion journey must inspect an empty destination session, authenticate
independently in that same document and verify its issued token and new work.
It must not navigate away from the inspected document before login. Production
App, API, persistence, authentication policy and inventory behavior are unchanged.

## Reproduction and bounded hypothesis

The initial native baseline trial reproduced the failure at
`loginResponse.json()`: HTTP200 was observed, then `Network.getResponseBody`
failed. It ran with retries zero and stopped at its first failure; the other two
planned trials did not execute. Trace SHA-256:
`cdb12401b0f11f83376e658d33cdf5e657ee8e317e19a47e594b8cfa7d6179ae`.

The trace contains two navigations to destination B; the second occurs before
the login POST. There is **no observed document request after that POST and
before the response-body failure**. These observations do not establish Chromium's
internal CDP cause or show that navigation after login caused the failure.
The earlier [early-response-capture change](2026-11-19-source-login-response-capture.md)
remains in place; the newly reproduced failure shows it did not eliminate the
intermittent native problem.

The test called the general `login` helper after an explicit destination
navigation and empty-session check. That helper navigated again before filling
the form, so the inspected document was not preserved. The bounded hypothesis
is that removing this unnecessary navigation gives the test one stable document
through session inspection and response capture. It corrects the test's own
same-document invariant; a CDP root-cause claim requires separate evidence.

## Test-only correction and evidence

The existing navigating `login` helper delegates its form/login steps to
`loginOnCurrentPage`, preserving other callers' navigation behavior. This journey
uses `loginOnCurrentPage` after its one explicit destination navigation.
It retains exact URL/POST response matching, HTTP200, nonempty response token,
equality with destination session storage, inequality with the source token,
unchanged source session, server auth/context readback and distinct newly authored
work. Missing response bodies or tokens still fail; storage is not a substitute
for independently observed issued-token evidence.

A temporary `framenavigated` observer starts after the initial navigation and
counts destination main-frame navigations. The test requires zero through empty
session inspection, response-body capture and login completion. The observer is
removed in `finally`; a bounded receipt records only the navigation count and
boolean progress/service-worker fields, including on failure. No token, response
body, account identifier or credential is added to that receipt.

A repository authoring guard first failed against the navigating call, then all
five source-completion authoring guards passed after the change. They check the
same-document structure and retained identity assertions; source tests are not
native-browser proof. Orders, inventory and branding E2E TypeScript checks and
touched lint passed. The full repository suite passed **227 tests**; frontend
core passed **1,805/1,805**, zero failures or skips (32.37-second test phase).

The bounded native candidate run then passed **3/3** trials in **17.5 seconds**,
with **zero retries, zero flaky cases and zero skips**. Every trial recorded
`mainFrameNavigations: 0`, `emptySessionChecked: true`, `responseSeen: true`,
`responseFromServiceWorker: false`, `bodyValidated: true` and
`loginCompleted: true`; each retained its full causal trace and the existing
source/new-work receipt. This is observed local improvement in the selected
journey, not proof of Chromium's internal root cause or all future runs.

Two adjacent wrapper journeys (workshop and local-only) also passed **2/2** in
**15.2 seconds**, retries zero. The dedicated PostgreSQL container was removed and
its absence confirmed. Independent source review found no blocking findings.
Fresh hosted qualification of the exact successor remains pending.

Local receipts and native reports are retained separately from source documents:

- `artifacts/source-completion-20261126/baseline-local-receipt.json`
- `artifacts/source-completion-20261126/candidate-local-receipt.json`
- `apps/web/test-results/source-completion-baseline-20261126-report.json`
- `apps/web/test-results/source-completion-candidate-20261126-report.json`
- `apps/web/test-results/source-completion-wrapper-20261126-report.json`

The baseline receipt retains the trace path and SHA-256 above; the candidate
receipt binds its results to the hashes of both changed TypeScript files and the
unchanged response-capture helper. The retained receipt SHA-256 values were independently checked:

- Baseline: `f75d49c49bf0bef89c4a117c79d097f8644acadea8e34c04f83f642e4d42f074`
- Candidate: `e47824c372379154bd019cc9cc68847c0dea13eaa90c6657242a5dbe14ed6e01`

Raw authenticated traces remain local test artifacts rather than public
documentation attachments.

No timeout, retry count, network interception, browser-security flag, fixture
scope or acceptance assertion is relaxed. Existing failure artifacts remain
historical failures. The bounded local native trials and independent review are
complete; the next evidence step is exact-source hosted candidate CI.

## Release and operational boundaries

This test correction does not change product behavior, grant permissions, migrate
local data, enable the existing-bicycle selector or deploy an installation.
G1–G6, physical T1–T8/R01-T035, actual inventory reconciliation, installation
restore and quote capacity/activation remain open. The original flaky failure's
internal cause remains unproven despite the bounded passing candidate trials.
