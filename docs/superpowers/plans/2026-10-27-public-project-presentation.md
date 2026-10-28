# Public Project Presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an honest source-bound public presentation and useful README/contributor entry points, without deploying the application.

**Architecture:** Same-repository static HTML/CSS, allowlisted deterministic build and authentic production-PWA screenshots. Build-only Actions first; protected Pages publication remains separately gated.

**Tech Stack:** Python standard library, HTML/CSS, existing Playwright, Markdown/Mermaid.

**Spec:** `docs/superpowers/specs/2026-10-27-public-project-presentation-design.md`

## Global Constraints

- `AGPL-3.0-only`, DCO 1.1, Offline First / Local First and deny-default authorization unchanged.
- No application deployment, real account/grants, quote activation or runtime plugin loader.
- No new workflow write/OIDC permissions, Pages settings, secrets or external dependencies in this increment.
- Canary creation 15 seconds within 65-second setup; other canaries 5 seconds; Python serial 900 seconds/shard and 768 MiB; PostgreSQL 1 GiB RAM and 512 MiB data; job 55 minutes. No consumed capacity reruns.
- Real screenshots only, synthetic fixtures explicitly labeled, exact source/hash provenance required.

## Review Focus

- Project Pages subpath: relative links/assets remain valid without root-path assumptions.
- Publishing private files accidentally: explicit allowlist, reject traversal and symlinks.
- Stale screenshots: hash/source metadata checked, obsolete captures must not claim latest runtime.
- Misleading maturity: planned SDK/quote UI and physical/manual gates distinct from implemented source.
- Small screens and keyboard-only use: semantic landmarks, focus visibility, no clipped navigation.

### Task 1: Source-backed documentation and plan

**Files:** design/plan above; `docs/10-spec-development/execution-state.yaml`; `MANUAL-ACTIONS-CHECKLIST.md`; `docs/10-spec-development/2026-10-27-public-project-presentation.md`.
**Interfaces:** consumes a960bdd source and existing normative specs; produces scoped status and acceptance record.

- [ ] Record selected alternatives, current main, explicit publication gate and module strategy recommendation.
- [ ] Validate Markdown/YAML and all local document paths; independently review design.
- [ ] Commit signed documentation baseline before implementation.

### Task 2: Authentic screenshot evidence

**Files:** `apps/web/e2e/structural-themes.spec.ts` (existing producer); `docs/site/assets/screenshots/`; `docs/site/screenshots.json`.
**Interfaces:** existing hosted production-PWA capture produces PNGs; packaging preserves original source SHA/run/artifact/viewport/fixture/hash entries and explicit runtime tree fingerprint.

- [ ] Prove real Chromium launch and inspect existing E2E fixture contracts; use hosted actual-browser fallback if local browser is blocked.
- [ ] Reuse and inspect exact-main hosted captures without editing original PNG bytes; no new capture workload when existing authentic evidence is sufficient.
- [ ] Record exact capture source/runtime and limits; verify SHA-256 and prohibit undocumented images.
- [ ] Commit signed reviewed artifacts and repeatable capture source.

### Task 3: Public site and guarded build

**Files:** `docs/site/index.html`, `docs/site/styles.css`, `scripts/docs/build_public_site.py`, `tests/repository/test_public_site.py`, `.github/workflows/public-presentation.yml`, `apps/web/tools/public-site/public-site.spec.ts`, `apps/web/playwright.public-site.config.ts`.
**Interfaces:** `build(source: Path, destination: Path, *, require_current: bool = False) -> None`; only allowlisted site files enter output; validation failures raise `ValueError` before any output. Source is the site directory, runtime fingerprint is checked against its repository.

- [ ] Write failing tests for valid build, missing assets, traversal/symlink/unknown-file rejection, provenance/hash mismatch, source/destination overlap, nonempty destination, active HTML/CSS variants, docs-only freshness and runtime drift.
- [ ] Run `pytest -q tests/repository/test_public_site.py` and observe expected failures.
- [ ] Implement semantic static site and deterministic validating copy; build-only workflow uses read-only token and normal artifact upload.
- [ ] Run same tests GREEN, build to `artifacts/public-site`, run hosted Playwright/axe at `/open-cycling-workshop/` for desktop/320px, keyboard skip-link/focus, overflow, no unexpected network/failed assets, retaining captures. Initial delivery uses `--require-current`; normal build marks runtime drift historical, never latest.
- [ ] Run touched Python/style checks; commit signed.

### Task 4: README, architecture and contributor onboarding

**Files:** `README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `docs/08-open-source/2026-10-27-compatible-modules.md` (coordinate architecture review).
**Interfaces:** links current source, screenshots, plan and actual operational procedures; does not invent a working SDK API.

- [ ] Replace stale capability/blocker statements with reviewed current-source matrix; link tested operational setup rather than duplicate unsafe secret commands.
- [ ] Add accessible real screenshot captions and source-mapped diagrams; role-based getting-started paths and minimal redacted bug template/security route.
- [ ] Check every local link and command path, Mermaid/source correspondence, formatting and licensing.
- [ ] Independent whole-branch review; resolve findings, normal exact-source CI, merge only qualified checks, then verify postmerge and update evidence.

### Task 5: Protected publication (blocked pending explicit authorization)

- [ ] Obtain specific authority before Pages settings or workflow Pages/OIDC write permissions.
- [ ] Review minimal default-branch-only deployment workflow and environment protections; deploy only static allowlisted documentation artifact.
- [ ] Verify returned live URL, subpath assets, screenshot provenance and no app/data exposure. Record actual deployment SHA. No live-site claim before success.
