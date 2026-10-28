# Public project presentation · execution record

Status: **in progress**, not published. Source baseline:
`a960bddb94189c6c74c7f3d0a72472636c3caced` (PR62). The independent source-bound
postmerge acceptance is [CI40571345621](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40571345621),
not a production deployment or physical-device qualification.

The maintainer delegated technical design and iterative implementation on
2026-10-27. The [assistant-selected design](../superpowers/specs/2026-10-27-public-project-presentation-design.md)
and [implementation plan](../superpowers/plans/2026-10-27-public-project-presentation.md)
record alternatives rather than asserting an unseen human design approval.

## Preflight and rulings

- Live main matched the baseline; no unrelated source changes overwritten. A
  separate local clone/feature branch preserves the prior privacy workspace.
- Initial generic verifier used an unprepared interpreter/checkout: missing
  pytest, SQLAlchemy and Node modules caused Python/runtime/frontend/contract/
  type/lint/format/build/browser failures. These are retained as environment
  failures, not a source regression or passing baseline. Existing locked local
  dependencies are reused for subsequent targeted checks; hosted exact-source
  CI remains required. Repository integrity and committed lockfiles passed.
- Local Chromium cannot open sockets under current sandbox. No escalation or
  permission weakening: actual source-bound hosted screenshot artifact
  `12767187707` from the baseline run is available instead.
- Ruling: reuse the existing `structural-themes.spec.ts` screenshot producer,
  rather than add a duplicate capture implementation. Original unmodified PNGs
  have ZIP-entry CRC, Playwright attachment SHA1 and local SHA256 evidence. This
  does not assert a whole-archive digest. Fixtures are disposable synthetic REST
  data and real baseline/offline flow, not a mocked product UI.
- Independent design review requires runtime tree fingerprinting (docs commits
  must not invalidate their own capture), destination/allowlist hardening, and
  fresh hosted static-site browser/axe/subpath evidence. Existing application
  screenshot evidence does not qualify the new presentation site.
- Pages publication remains separately blocked on specific settings/Pages/OIDC
  permission authorization; no such permissions are introduced by build-only CI.

## Remaining gates

Public site implementation, README accuracy, compatible-module strategy,
independent whole-branch review, exact-source CI and postmerge verification remain
pending. No actual app deployment, quote activation, real grants, physical
acceptance or consumed-capacity rerun is included.

## Implementation and review checkpoint

- Same-repository Spanish executive site, README/onboarding, source-mapped
  architecture and collaboration/security reporting guides implemented. Module
  strategy explicitly stages data-only M0, reviewed official composition and
  later isolated service identities/connectors; no SDK runtime claimed.
- Four original PNGs packaged with SHA256, native attachment identity, fixture,
  viewport and source/run/artifact provenance. Runtime fingerprint includes
  production sources, imported PWA policy, build manifests/config and capture
  producer. Initial `--require-current` build passed. Normal builds label later
  runtime drift historical rather than blocking unrelated Core changes.
- Builder RED: missing implementation observed; first GREEN 27 cases. Destination
  ancestor symlink and added-runtime drift regressions RED 2 / GREEN 30. Review
  CSS string-image fetch and weakened/missing CSP regressions RED 5 / GREEN 35.
  Dark-section focus regression RED 1 / GREEN 36. Final repository scope: 64 pass.
- Independent review found normal-suite freshness coupling, CSS `image-set()` /
  missing-CSP defense and dark focus contrast. All addressed. Actual hosted
  keyboard/axe/reduced-motion/static-site desktop and 320px execution remains
  pending; local source tests do not establish those browser results.
- Ruling: fixture-only runtime snapshots are self-contained and refresh their
  own hashes; real provenance is immutable. Initial current-source verification
  is explicit, not a requirement imposed on every later Core commit.
- Ruling: include the review's additional build inputs in the fingerprint now
  because an omitted imported policy could mislabel changed runtime as current.
- Read-only preview Actions adds no Pages/OIDC permissions and deploys nothing.
  Every upload is a build/browser evidence artifact, not a public deployment.

Whole Python and frontend baseline checks are in progress; exact candidate CI
and postmerge verification remain required. No source/documentation claim
closes the original physical, real-installation or activation gates.

## First hosted presentation and bounded correction · 2026-10-28

Public draft [PR63](https://github.com/IzignaMx/open-cycling-workshop/pull/63)
head `e62336c` has the exact locally reviewed `5db273f` tree
`6aac1995858283176be5c4fcbe4c2a8bf42e5eb9`; authenticated connector publication
changed commit metadata, not file content. PR checkout `bbeefbe9` has the same
tree. No Pages settings, OIDC/deployment or M0 runtime/descriptor were published.

[Preview40633914510](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40633914510)
passed independent artifact review: native desktop1440 and mobile320, 2/2 cases,
zero retries/flakes/skips/errors, keyboard/focus, reduced motion, repository
subpath/assets, no overflow, axe and no unexpected network. Both actual full-page
captures were visually inspected. Artifact12791689965 full ZIP SHA256
`a2014c60f37312f213ca8713f11c13b42ba654dcf4b1c8e541c586baeca82b32` and CRC checked;
all eight public output files match independent current-runtime rebuild. This
qualifies that static preview, not a deployment or a later modified source tree.

[Security40633914472](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/40633914472)
failed before scanning: its existing canary reads the exact `signed/revocable`
identity sentence removed by the README rewrite. The resulting `StopIteration`
is retained as a failure, not a secret finding or completed security scan. The
bounded correction restores the truthful original sentence byte-for-byte, with
a regression observed RED1 then GREEN. Scanner policy, exceptions, real-canary
requirements and skip rules are unchanged.

The preview trigger also now covers README/ARCHITECTURE/CONTRIBUTING changes for
PRs and main pushes (six path-regression cases observed RED then GREEN), ensuring
that changes to these entry documents receive a fresh preview check. Permissions,
runners, dependencies and resource limits are unchanged. This source correction
requires new normal exact-source checks, not an identical-head workflow rerun.
First-run CI/runtime evidence and successor acceptance are recorded separately.

## Exact historical provenance triage · 2026-10-28

Corrected head `dc36fa9` / merge checkout `fa203c2` / tree `367638ed` completed
CI40637352427 with independent source-bound review: 4,895 collected / 4,837
passed / 58 expected skips, eight actual PostgreSQL cases and six restores across
phases, both owned cleanup proofs; aggregate 27/27, direct/aggregate browser
86 each with retry 0, repetitions 20 + 9 + 5 + 10 and kernel 14. Fresh preview
40637352498 passed 2/2 with actual desktop/mobile inspection and all eight output
files matching an independent current-runtime rebuild. Native ARM, runtime,
containment, Caddy privacy and branding passed within existing nonphysical and
noncapacity limits. Optional QEMU failure remains nonqualifying.

Security40637352541 passed ten real policy canaries but failed actual scanning:
three public source SHA256 values in `docs/site/screenshots.json` matched the
generic rule in both historical `e62336c` and merge `fa203c2` (six findings).
Independent recomputation from immutable `a960bdd` confirms the manifest values
for `apps/web/src/auth/workshop-read-access.ts` (1,352 bytes),
`apps/web/src/runtime/account-access.ts` (1,000 bytes) and
`packages/branding/src/tokens.css` (644 bytes). These are file digests, not
credentials. Full-history/all-ref scanning includes the original branch, so a
new branch or later representation change alone cannot remove these findings.

The user explicitly authorized the exact path/three-value false-positive
exception and revalidation. The bounded implementation adds one conjunctive
`generic-api-key` exception: exact escaped provenance path AND fully anchored
alternation of only those three literal digests. Default rules, other paths and
values, full history/all refs, error handling and existing limits remain intact.
No force-push, history rewrite, blanket hash exception or suppression beyond
the explicitly authorized exact path/three-value matches.

Acceptance requires twenty real pinned-scanner probes: original ten, each
public digest's exact original context, one-nibble near miss and different path
(nine), plus an unrelated synthetic credential at the provenance path. Existing
mutation tests independently remove or broaden each of four exceptions (OR,
path and value). The five explicit hosted-scanner skip cases are unchanged.
Static policy guard was observed RED before implementation, then GREEN.
Independent local native Gitleaks 8.30.1 (upstream archive checksum verified)
passed all fifteen policy tests with zero skips: twenty real probes and all
sixteen mutated policies rejected. Local full-history/all-ref scanning passed
432 commits / 22.19 MB; this is local-ref coverage, not hosted coverage. Normal
exact-source CI and the pinned hosted full-history scan are still required;
this record is not a hosted security-pass claim. No Pages/OIDC/deployment,
application/grant/quote activation or separate M0 publication is authorized here.
