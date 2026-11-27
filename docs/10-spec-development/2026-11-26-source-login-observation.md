# Observe the real destination login response in its page · 2026-11-26

## Source and evidence boundary

This test-only candidate starts from
`996f0bb5d55ef5788f557691e3b46169e5dd3778`, the documentation reconciliation
successor for [PR127](https://github.com/IzignaMx/open-cycling-workshop/pull/127).
Its retargeted [CI45912843815](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/45912843815)
is pending at this authored checkpoint; the predecessor has not been integrated
into main. The [stacked inventory evidence](2026-11-26-inventory-workshop-scope.md#pr127-stacked-evidence-and-retarget-to-main--2026-11-26)
qualifies only its named source and scope. It does not qualify this later test
change or erase the source-completion failures.

The existing journey must verify an empty destination session, perform a genuine
independent login, prove the issued token equals the destination's stored token
and differs from the source token, retain the source session and journal, and
confirm actual server context and distinct newly authored work. These acceptance
conditions remain intact. Production App/API authentication, authorization,
inventory behavior, persistence and source/destination work are unchanged.

## Repeated failure and bounded hypothesis

PR126's direct and aggregate archives and stacked PR127's direct archive each
retain a login-body CDP failure followed by a successful retry. Their failed
observations record zero main-frame navigations, an empty session checked, a
response seen that was not from a service worker, a body not validated and login
not completed. The earlier [same-document correction](2026-11-26-source-completion-login-document.md)
preserved the inspected document but did not eliminate the observed intermittent
`Network.getResponseBody` failure. No record establishes Chromium's internal
cause, and a CDP error mentioning navigation is not proof that navigation occurred.

The current native baseline also reproduces the failure against the exact
`996f0bb` predecessor PWA. A fresh pinned build is byte-identical to PR127's
local build receipt. With disposable PostgreSQL **18.4**, Chromium, one worker,
zero retries and three repetitions, **two cases passed and one failed** in
**15.659679 seconds**, with zero skips. The failed case reports
`Network.getResponseBody` at the existing response JSON read, spec line 179,
and the same safe observation booleans above. It is an actual failed trial,
not a flaky result recovered by a test retry. The report is retained at
`apps/web/test-results/source-login-observation-baseline-20261126-report.json`.

The bounded hypothesis is to observe the actual browser-fetch response body in
the destination page, instead of asking the test runner to retrieve that body
through CDP afterward. This changes the test's observation mechanism; it does
not repair or explain Chromium's internal response-body failure.

## Candidate observation contract

Before the single destination navigation, the candidate installs a test-only
observer restricted to the top-level document at the exact destination origin B.
It observes one exact real login POST and clones its actual `Response` for bounded inspection, with a **32 KiB** maximum.
Observation must not await body inspection before returning the original response
to the application. It must not manufacture a response, issue an alternative
login, navigate again, alter the application body or substitute session storage
for independent response evidence.

The clone is read with the byte bound, strict UTF-8 decoding and Bearer-token
validation. The existing Playwright response waiter is created inside the armed
action and independently verifies the exact URL, POST, HTTP200 and absence of
a service-worker response. It does not retrieve response-body bytes through CDP.

Only body-validation and issued-token equality booleans cross the observation
boundary; credentials and response/token bytes must not become assertions,
diagnostic attachments or persisted observation state. The existing destination
token readback, source-token inequality, source-session preservation and real
server-context checks remain. Missing, malformed, oversized, mismatched or
unobserved evidence must fail, not fall back to the stored token. The ordinary
authentication and authoring journey still executes against the actual server.

Observer lifetime and cleanup must be bounded to that one test page. Current
retry counts, timeouts and acceptance assertions are unchanged; no production
auth helper, runtime or normative architecture contract is expanded. The
candidate source review and local native proof are recorded below; exact hosted
qualification remains pending.

## Local verification and limits

Authoring checks produced **three expected failures and three passing controls**.
The missing observer helper was separately observed RED, followed by **20 initial
passing helper cases**. Those intermediate results remain separate from the
final focused results below; none is native acceptance.

The native baseline above is complete. Final focused checks now pass **22
observer cases**, **seven existing response-capture controls** and **six authoring
guards**. An additional origin-gate
regression first produced **one failure and 21 passing controls**, then all 22
observer cases passed. The single missing-helper file failure and original
three authoring failures remain historical RED evidence.

The six changed test/helper/runner/guard source hashes and current PWA asset
hashes are recorded at
`artifacts/source-login-observation-20261126/candidate-source.json`. The built
production distribution is unchanged from the predecessor. Final independent
review found no blocking findings and checked the root/isolated-worktree source
bytes. E2E orders TypeScript, touched ESLint, Ruff, Prettier and diff checks passed.
The full frontend core passed **1,850/1,850**, zero failures or skips, in a
**39.2548-second** test phase. Repository contracts passed **228/228** in
**4.42 seconds** and the repository verifier returned OK. These are overlapping
invocations, not additive unique-test totals.

The native candidate passed **8/8 trials** in **67.913253 seconds**, with one
worker, zero retries, zero flaky cases and zero skips. Every safe observation
records zero main-frame navigations, an empty session checked, a real response
seen/not from the service worker, a validated body, issued-token/stored-token
equality and completed login. Every downstream receipt verifies the independent
destination session, exact restored payload/identity, server context matching
the kernel, preserved source journal, initially empty destination journal and
captures, and exactly two server order creations.

The source/build-bound receipt is
`artifacts/source-login-observation-20261126/native-local-receipt.json`, SHA-256
`3f94d7834b5f61c29840ebe479acd2ad32f61a2584167266017273ac203c0e6b`.
It records Node **22.16.0**, pnpm **11.17.0**, Python **3.13.5**, PostgreSQL
**18.4**, Playwright **1.64.0** and Chromium **156.0.8078.4**, revision **1248**.
The source and distribution hashes remained unchanged through final execution.
The owned PostgreSQL container was stopped/removed and a fresh label query
confirmed its absence. The original general login helper is unchanged; its
seven response-capture controls pass, and no separate adjacent native wrapper
run is claimed.

Local verification is complete for this bounded candidate. Exact successor
hosted qualification remains pending and distinct from PR127's retargeted run.
The eight trials demonstrate this observation mechanism with the full real
journey; they do not prove Chromium was repaired or establish universal absence
of intermittent browser failures. The baseline failure remains preserved.

## Retained product limits

V0.1 remains **partial**. All inventory FR-INV-001–012 gaps, physical
T1–T8/R01-T035 and assistive-technology acceptance, G1–G6, actual installation
restore, quote activation/capacity and deployment gates remain open. The
independent branding-refusal probe and historical administration identity
timeout remain separate. No real workshop or stock data is used or qualified.

## PR128 stacked evidence and retarget to main · 2026-11-27

[PR127's retargeted candidate merged](2026-11-26-inventory-workshop-scope.md#pr127-retargeted-acceptance-and-merge--2026-11-27)
as `971bdd20e14508b5335189b1eb56c4d93ef70cea`. This supersedes the earlier
authored predecessor-pending/unmerged statement, while preserving the local
base and baseline failure. PR127's fresh-main CI remains separately pending.

[PR128](https://github.com/IzignaMx/open-cycling-workshop/pull/128) head
`5acc4342e157b0fe7128cb0c0638b4bb06b897b0`, based on
`996f0bb5d55ef5788f557691e3b46169e5dd3778`, passed its stacked
[CI45913487074](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/45913487074)
and all five companion workflows. The tested synthetic merge is
`4cc6c295d14ce45285b5c6709eeab1687f0dcd5f`; it and the head share tree
`36dd5be60ce11987f11a6e7510f770a7435b1c64`.

Independent Python artifact `15161513670` review, SHA-256
`e50001dab941013e3e7dc6e4fd81332826015b7afce51ec822718e302dce99cb`,
confirms the clean exact source and two shards: **4,413 passes / 11 intentional
skips** and **2,401 passes / 47 intentional skips**, totaling **6,814 / 58**.
There are no failed, error, unrun or unexpected-skipped outcomes. Primary and
independent cleanup receipts confirm owned databases absent in both shards.
Reviewed logs also report **1,850 frontend passes** and **1 API-client pass**.

Actual direct archive `15162142929`, SHA-256
`3a3182a7ef5f585268ecd41dab0f3d5850fb811a286981ffabcca0b0d998b42d`,
and aggregate archive `15162389214`, SHA-256
`8b1a29e867dd4a8966efcd28b2d5feaaa46a729202aefbc7b893e2499fbd6759`,
were independently inspected against the tested source metadata. Both contain
**146 passing cases**, each on its first attempt with no errors, flakes or skips.
Each includes **17 inventory cases** and the **one source-completion journey**.
Both source-completion safe observations report zero main-frame navigations,
empty session checked, response seen, body validated, issued/stored token equality
and login completed; the response is not from a service worker. This qualifies
the actual observed test journey for that source. The prior failures remain
preserved and the internal CDP cause is still unproven.

PR128 is now retargeted to main `971bdd2`. The clean local merge-tree result for
that base and unchanged `5acc434` head is the same
`36dd5be60ce11987f11a6e7510f770a7435b1c64` tree. That check proves source
compatibility, not a new CI run. This documentation reconciliation creates a
later candidate requiring its own exact retargeted CI and review before merge.
The earlier stacked-hosted-pending statement is superseded only for the tested
source above; the new documentation candidate remains pending. No release,
physical, installation or deployment gate is promoted.
