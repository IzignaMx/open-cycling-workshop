# Public project presentation and contributor entry points

## Decision and authority

Assistant-selected implementation under the maintainer's 2026-10-27 explicit
technical delegation and continuous spec-development request; this is not a claim
that the maintainer reviewed or approved this document. Foundation TA-01–07,
accepted ADR-001/002/010/015/016 and Phase 8 governance remain authoritative.

## Intent

Help workshop operators understand OCWP, implementers assess its actual maturity,
and contributors find reproducible setup, architecture, module and bug-report
paths. Replace stale README statements with source-linked current boundaries.
A public presentation is documentation, not deployment of the workshop app.

## Alternatives and selected approach

1. **Selected: same repository, small static HTML/CSS site under `docs/site/`.**
   Source, screenshots and claims are reviewed together; no extra runtime package,
   proprietary dependency, credential or duplicated release process. A Python
   standard-library validator/build copies only an explicit public allowlist.
   Relative assets work under the repository Pages subpath and offline.
2. Separate presentation repository: useful if editorial ownership/release cadence
   later separates, but currently adds permissions, cross-repository provenance,
   duplicated issues and version drift without a demonstrated benefit.
3. Full documentation framework: useful for a large versioned multilingual manual,
   but unnecessary build/dependency surface for this initial executive landing page.

Reversible: the static output can move to another repository/host without touching
application code or data. Spanish-first presentation matches current maintainer
and product context; source/contributor docs can retain existing English.

## Scope and truthful boundaries

- Executive value proposition, audiences, implemented-versus-planned capability
  matrix, use/onboarding, implementation safety, architecture, modules,
  collaboration, bug reports and private security-report route.
- README with focused navigation, real screenshots and Mermaid architecture;
  site uses an accessible HTML architecture diagram with the same source map.
- Actual latest-source production-PWA runtime captures using only disposable
  synthetic data. Record source SHA, capture command/runtime, viewport, fixture
  identity and SHA-256 for each image. No mockup, AI-generated UI, private data,
  hidden screenshot substitutions or implied production customers.
- Screenshots prove their rendered state only, not offline correctness, device
  acceptance, accessibility conformance, quote activation or production readiness.
- Public site cannot include API clients, credentials, real workshop data, login,
  analytics, third-party fonts/scripts, operational environment files or app SW.
- Module section distinguishes implemented boundaries from future contract SDK,
  registration and isolated connectors. `packages/plugin-sdk` is a placeholder;
  no installable plugin ecosystem or runtime loader is advertised or added here.
- Preserve all pending streaming/cancellation/capacity/install/physical gates.
  No consumed capacity reruns or changes to fixed runtime budgets.

## Architecture and publication safety

`docs/site/` is inert documentation. `scripts/docs/build_public_site.py` validates
links, local assets, capture provenance and forbidden active/publication content,
then copies only selected public files into a disposable output directory. Build
must not copy all of `docs/`, repository secrets or the operational PWA `dist/`.

The first Actions workflow builds/tests/uploads a preview artifact with
`contents: read` only. It does not enable Pages, configure a domain, obtain OIDC or
publish a deployment. A separate explicit protected publication decision is needed
before adding `pages: write` / `id-token: write` and enabling Pages. That later
workflow must publish only reviewed default-branch artifacts, use the
`github-pages` environment and bind evidence to the deployed SHA. This separation
keeps public documentation possible without expanding persistent/security access.
GitHub's [custom workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
confirms Pages deploy jobs require both permissions; checked 2026-10-27.

## Acceptance and limitations

- Existing onboarding commands checked against manifests/scripts; no plaintext
  example password persisted in `/tmp`, no ambiguous destructive E2E reset.
- Tests fail first for bad assets, escaping paths/symlinks, unexpected files,
  missing/stale screenshot hashes/source binding and unsafe active content.
- Build deterministic and network-free; desktop/mobile reflow, keyboard/focus,
  readable contrast and reduced-motion verified separately from application QA.
- Independent review, exact-source normal CI and postmerge checks required.
- Public URL remains explicitly unpublished until an actual authorized deployment
  succeeds and its URL/assets are verified. No guessed URL presented as live.

## Independent builder review corrections

Accepted technical corrections: compare screenshot freshness using an explicit
runtime tree fingerprint, not whole repository SHA; docs-only commits do not
invalidate their own captures. Always retain dated capture SHA. A normal build
labels runtime drift historical; `--require-current` rejects it for initial
current-version delivery. Validate all inputs before output; refuse symlink,
nonempty or overlapping destinations. Hosted static-site Playwright/axe proves
repository-subpath assets, desktop/320px, keyboard focus/skip-link and no overflow
or unexpected network. Existing app captures cannot prove new-site accessibility.
Private security reporting remains conditional as in `SECURITY.md`.
