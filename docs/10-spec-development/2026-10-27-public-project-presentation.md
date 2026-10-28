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
