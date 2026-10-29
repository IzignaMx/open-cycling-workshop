# Manual public Pages publication · 2026-10-28

## Scope and source

This increment continues the same-repository public presentation, not application
hosting. Baseline main is bd2dbd6b5a89631e0f95602220cb861c9a6cccc2 (PR64).
The maintainer authorized the manual workflow, Pages Actions source, main-only
`github-pages` environment and one first validated static publication. The
[implementation plan](../superpowers/plans/2026-10-28-manual-public-pages.md)
records assistant-selected details and acceptance gates.

## Reconciled earlier checkpoints

PR63 merged at 1946608ac8dae5a5ff160fd74c896f8eba22f540. Fresh postmerge
[CI 40652268405](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40652268405)
and [Security 40652268313](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40652268313)
are terminal success. Earlier source records retain historical failures, not a
claim that the final source still fails. PR64 merged at the baseline above;
[CI 40668763286](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40668763286)
and [Security 40668763418](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40668763418)
are terminal success. These are prior-source results, not this increment's proof.
Optional QEMU failure remains nonqualifying and does not prove physical devices.

## Publication boundary

- Only `workflow_dispatch`, exact main ref and matching full expected source SHA.
  A mismatch skips publication; it is not evidence of deployment.
- Read-only build and live verification jobs; deployment alone receives
  `pages: write` and `id-token: write`, with no checkout or repository scripts.
- Immutable direct action pins, same-workflow Pages artifact and serialized,
  non-canceling publication. No PAT, custom domain, credential or bootstrap step.
- Build requires current authentic screenshot runtime fingerprint, runs existing
  desktop/mobile/keyboard/axe preview, then uploads only the public leaf.
- Returned URL must be exactly the approved HTTPS project URL before bounded
  no-redirect retrieval. All eight public content files must match rebuilt bytes;
  `.nojekyll` is checked as an empty local marker, not claimed remotely served.
- Live browser verification is separate from local preview; neither the original
  capture SHA nor a deterministic rebuild is a deployment archive identity.
  Final acceptance must independently bind run/head SHA, deployment, uploaded
  artifact ID/digest and whole ZIP hash/CRC, returned URL, bytes and browser proof.

## Historical implementation checkpoint · 2026-10-28

Initial workflow contracts failed for the absent workflow (two RED tests); after
implementation, the workflow and existing builder suite passed 45 tests. Live
configuration initially failed its missing-file regression. Final focused coverage is 89 passing tests (42 builder, 42 live verifier and five
workflow contracts including 11 security mutations). Independent source review
found no remaining blocker. Strict Python typing, Ruff, Prettier, TypeScript and
ESLint pass. The intermediate full local suite passed 4,350 tests with 671 explicit environment
skips and 12 warnings (5,021 collected). Four later regression cases passed in
the final focused suite; exact final full collection is 5,025. A fresh full final
run, hosted CI and publication remain pending.

Independent review corrected two prepublication risks: direct workflow actions
are pinned to immutable commits; browser interception now uses a context-wide
no-redirect fetch with five-second timeout, zero retries and 32-request cap.
A real two-server canary must show the redirected destination receives zero hits.
Both preview/live configurations collect three tests; local collection is not
actual browser execution. Bad live URL configuration fails before launching.

Local TypeScript and ESLint passed using existing installed locked dependencies.
The local Playwright run could not launch: bundled Chromium was absent; the
installed system Chromium then failed its singleton socket with Operation not
permitted. No privilege escalation or browser flags were added to bypass this.
Actual browser proof must come from ordinary hosted preview and later live job.

Read-only setup inspection: repository `has_pages=false`, Pages endpoint404,
zero environments. Cloud browser is logged out; Pages settings shows Sign in.
No supported connector endpoint offers Pages/environment administration. Setup
is therefore blocked on existing maintainer access, not denied or attempted.

Operator steps (no new credentials):

1. [Pages settings](https://github.com/IzignaMx/open-cycling-workshop/settings/pages):
   Source **GitHub Actions**, leave custom domain empty.
2. [Environments](https://github.com/IzignaMx/open-cycling-workshop/settings/environments):
   create `github-pages`; Deployment branches and tags → **Selected branches and
   tags** → add type **Branch**, name **main** only. No tag rule or secret. Preserve
   stronger protections; do not choose protected-branches-only as a substitute.
3. After qualified merge/postmerge proof, dispatch once from main with the exact
   independently qualified full SHA. Do not rerun a failed attempt blindly.

At that checkpoint no live publication had been performed. Physical acceptance, real installation,
streaming/cancellation/capacity, quote activation and module runtime gates remain
open. This workflow does not close any of them.

## First live publication · 2026-10-29

The previous pending/setup statements are historical, superseded for the static
presentation by this receipt. PR65 merged normally at
`3c6513d685fe659816bd3ddb47dab91003d3a787`, tree
`c8512994d19af082eddfb98ef77121f113218290`. Fresh postmerge
[CI 40711265914](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40711265914)
passed 4,967 tests with 58 expected skips (5,025 collected), all 27 aggregate
controls and direct/aggregate browser 86/86 without retries. Native preview
40711265947 passed three tests. Optional QEMU 40711266047 remains failed and
nonqualifying; native ARM is not physical Raspberry Pi acceptance.

Before dispatch, authenticated inspection confirmed Pages Source GitHub Actions
and selected Branch `main` only on `github-pages`, with no tag rule. Main was
unchanged. One manual dispatch used that exact full expected source SHA.
[Run 40807430478](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40807430478),
attempt 1, completed build (123229617809), deploy (123229871130) and live verify
(123229948886) successfully. Deployment 7402583560 records that same main SHA.
The returned and browser-observed URL is
[the public presentation](https://izignamx.github.io/open-cycling-workshop/).

Independent acceptance checked:

- Pages artifact 12869255568, complete ZIP digest
  `ed148f5fbc9fbf8ffaf069b0e41456d405dc123fd3219d359abd7a000a20ceac`,
  all ZIP CRCs and safe tar entries; all nine leaf files equal a strict-current
  rebuild of the exact deployed source (including empty local `.nojekyll`).
- All eight remotely checked public files match that uploaded payload. No claim
  is made that `.nojekyll` was fetched from the website.
- Live evidence artifact 12868772654, complete ZIP digest
  `b8488b38a028754468f475f14b3d58ffe5dc139c16d1bf6987a36e5a969641b0`,
  all CRCs and exact source binding. Actual live browser passed 3/3, zero retries,
  skips or flaky results: redirect canary plus desktop 1440/mobile 320 keyboard,
  reflow, image and axe checks. Actual live screenshots were visually inspected.
- A separate local direct network probe returned `E_NETWORK`; it is not claimed
  as live transport proof. Hosted remote-byte/browser proof and authenticated
  browser observation establish the result instead.

Only the static presentation is live. No operational PWA/API, customer data,
module execution, real grants or quote activation was deployed. The workflow
remains manual-only; this receipt does not dispatch or authorize another run.
Node action-runtime deprecation and hosted image-migration notices are retained
as maintenance observations, not reasons to change budgets or rerun successful
qualification. Physical, installation/recovery, streaming/cancellation and
capacity gates remain open.
