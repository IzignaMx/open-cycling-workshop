# Open Cycling Workshop Platform · Manual Actions & Blockers Checklist

> Living operational checklist for actions that cannot be proven or completed autonomously from every execution environment. Keep this file current until the corresponding evidence exists in `docs/10-spec-development/execution-state.yaml` and the V0.1 qualification artifact.

### P0 · Restaurar el repositorio remoto desde el bundle autoritativo

- [ ] Descargar/copiar en la misma máquina el bundle autoritativo entregado con esta consolidación.
- [ ] Ejecutar desde una máquina con acceso GitHub autenticado: `bash scripts/repository/publish-authoritative-bundle.sh /ruta/al/open-cycling-workshop-final-consolidated.git.bundle git@github.com:IzignaMx/open-cycling-workshop.git`.
- [ ] Confirmar que el script termina con `Repository restore verified`.
- [ ] Confirmar que `main` y `bootstrap/v0.1` apuntan al mismo commit autoritativo.
- [ ] Conservar temporalmente las ramas `pre-consolidation/*` creadas por el script hasta validar GitHub Actions y después archivarlas/eliminarlas deliberadamente.
- [ ] Confirmar que `_consolidation-probe.txt`, fragmentos `_repo_bundle/` y cualquier bootstrap temporal NO aparecen en el árbol autoritativo final.

> Este paso es manual únicamente cuando el entorno del agente no dispone de transporte Git autenticado capaz de subir el pack binario sin alterarlo. No sustituirlo por copiar archivos individualmente: la verificación de tree SHA es la garantía de integridad.

## How to use this checklist

- Check an item **only after evidence exists**. A command being expected to work is not evidence.
- Prefer attaching or linking evidence from GitHub Actions, release artifacts, screenshots, logs, device test records, restore reports, or ADR/RFC records.
- When a blocker is resolved, update both this checklist and `docs/10-spec-development/execution-state.yaml` in the same pull request/commit.
- Do not delete completed entries; mark them complete and add evidence so the history remains auditable.
- Never paste secrets, passwords, private keys, production tokens, customer PII, payment data, or backup encryption keys into this file.

## P0 · Repository integrity and GitHub governance

- [ ] **Confirm `main` contains the complete authoritative repository tree.**
  - Evidence: remote tree/file audit matches the current verified local tree; all normative docs, code, fixtures, workflows, governance files, licenses and scripts are present.
  - Required before: treating GitHub as the canonical source of truth.
- [ ] **Confirm `bootstrap/v0.1` is either intentionally retained or removed after consolidation.**
  - It must not silently diverge from `main` without a documented purpose.
- [ ] **Protect `main`.**
  - Require pull requests.
  - Require relevant status checks once CI has a successful baseline.
  - Block force-push and deletion.
  - Require conversation resolution where available.
  - Preserve emergency admin access only for documented break-glass use.
- [ ] **Configure CODEOWNERS enforcement for high-risk paths.**
  - Auth/RBAC, sync, migrations, inventory ledger, payments, plugin permissions, security workflows and release tooling require the review policy defined by governance.
- [ ] **Enable GitHub security capabilities available to the repository/account.**
  - Dependabot alerts/updates where appropriate.
  - Secret scanning and push protection where available.
  - Code scanning / CodeQL or an equivalent SAST path.
- [ ] **Verify DCO enforcement on hosted CI.**
  - Evidence: a compliant PR passes and a deliberately unsigned test commit is rejected in a safe test branch/fixture workflow.
- [ ] **Review repository visibility, organization ownership and recovery administrators.**
  - At least two independent custodians before V1 where governance requires it.
- [ ] **Set repository description, topics and project links.**
  - Avoid calling the software production-ready before V1 release gates pass.

## P0 · Lockfiles and reproducible dependency installation

- [ ] **Generate and commit `uv.lock` using a runner with PyPI access.**
  - Run the CI workflow or locally: `uv lock` followed by `uv sync --frozen --all-packages --group dev` (or the exact frozen command adopted by CI).
  - Review the diff before commit.
  - Evidence: clean frozen install in a fresh environment.
- [ ] **Generate and commit `pnpm-lock.yaml` using the pinned pnpm/Corepack version.**
  - Run the CI workflow or `corepack enable && pnpm install --lockfile-only` in a clean environment.
  - Evidence: `pnpm install --frozen-lockfile` succeeds from scratch.
- [ ] **Download the `v0.1-lockfiles` GitHub Actions artifact if CI generated the initial lockfiles.**
  - Review before committing; do not blindly trust generated dependency changes.
- [ ] **Run dependency vulnerability audits against committed locks.**
  - Python: `pip-audit`/approved equivalent through the pinned uv environment.
  - JS: the approved pnpm audit/dependency review path.
  - Document accepted exceptions with expiry dates and rationale.

## P0 · Python runtime and PostgreSQL 18.4 qualification

- [ ] **Install/verify psycopg v3 in a clean supported Python 3.13 environment.**
  - Evidence: `python_psycopg = pass` in `scripts/ci/verify_v01.py` output.
- [ ] **Run the PostgreSQL integration suite against PostgreSQL 18.4.**
  - Set `OCWP_TEST_DATABASE_URL` to a dedicated `_test`/`_e2e` database only.
  - Evidence: `postgresql_integration = pass`.
- [ ] **Run Alembic `0001 → HEAD` against an empty PostgreSQL 18.4 database.**
- [ ] **Run migration preservation tests from every supported prior schema snapshot once those snapshots exist.**
- [ ] **Verify `postgresql://` and `postgres://` provider URIs are normalized to psycopg v3 and work end-to-end.**
- [ ] **Verify tenant/location foreign-key invariants on PostgreSQL, not only SQLite surrogate tests.**
- [ ] **Verify `FOR UPDATE SKIP LOCKED` job-claim semantics with concurrent PostgreSQL workers.**

## P0 · Full static analysis and formatting gates

- [ ] **Run Ruff lint in the real uv environment.**
  - `uv run ruff check ...`
- [ ] **Run Ruff format check.**
  - `uv run ruff format --check ...`
- [ ] **Run mypy using the committed configuration.**
- [ ] **Run ESLint from the installed pnpm workspace.**
- [ ] **Run Prettier check from the installed pnpm workspace.**
- [ ] **Resolve every real error instead of weakening configuration to make CI green.**
- [ ] **Record any intentional suppression with a narrow scope and explanatory comment.**

## P0 · Production PWA build and browser E2E

- [ ] **Build the real Vite PWA from committed lockfiles.**
  - Evidence: `pnpm --filter @ocwp/web build` exits 0 in a clean runner.
- [ ] **Inspect generated Service Worker and manifest.**
  - App shell must be available offline after first load.
  - Update strategy must not discard unsynced local mutations.
- [ ] **Run hosted Playwright + axe Golden Slice.**
  - Login with persisted user.
  - Wait for Service Worker readiness.
  - Go offline.
  - Create a Customer locally.
  - Reload while still offline.
  - Verify app shell, Customer and pending mutation survive reload.
  - Reconnect.
  - Verify mutation is applied exactly once to PostgreSQL.
  - Verify local pending queue drains correctly.
  - Open a second browser context/device scope.
  - Verify convergence.
  - Verify no axe `serious`/`critical` violations in the covered journey.
- [ ] **Persist Playwright traces/screenshots on failure in CI.**
- [ ] **Confirm browser E2E uses production `vite preview`, not only the development server.**

## P0 · IndexedDB / Dexie qualification

- [ ] **Run SPK-001 with at least 100,000 representative local records.**
  - Current ChatGPT execution environment cannot prove this because managed Chromium policy blocks navigation.
  - Measure write, query, migration and startup behavior on supported desktop/mobile browsers.
- [ ] **Run pending-mutation persistence across reload, browser restart and OS restart.**
- [ ] **Prove Dexie migrations preserve queued mutations.**
- [ ] **Test quota pressure and clear user-facing recovery behavior.**
- [ ] **Document Android storage-eviction behavior and recovery procedure.**
- [ ] **Never use “delete IndexedDB” as the normal migration/recovery strategy.**

## P0 · Tier 1 physical device qualification

- [ ] **Windows Tier 1 test.**
  - Supported Chromium-based browser.
  - Install PWA.
  - Offline create/update.
  - Reload offline.
  - Reconnect/sync.
  - Conflict path.
  - Accessibility/keyboard smoke.
  - Update/reinstall behavior.
- [ ] **Android tablet Tier 1 test.**
  - Install PWA.
  - Touch targets and Workshop Mode usability.
  - Offline persistence across app/process restart.
  - Connectivity switching Wi‑Fi ↔ offline ↔ Wi‑Fi.
  - Storage pressure/eviction behavior.
  - Camera/file permission behavior when implemented.
- [ ] **Record actual models, OS versions, browser versions and results.**
- [ ] **Do not claim Tier 1 support from emulator-only evidence.**

## P0 · Docker Compose and server runtime

- [ ] **Run `docker compose -f infra/compose/docker-compose.dev.yml config`.**
- [ ] **Build API and worker images from scratch.**
- [ ] **Start PostgreSQL 18.4 + API + worker via Compose.**
- [ ] **Verify `/health/live` and `/health/ready` semantics.**
  - Liveness proves process.
  - Readiness proves DB connectivity.
- [ ] **Verify only intended ports are exposed.**
- [ ] **Verify containers run non-root where specified.**
- [ ] **Verify secrets are provided through the documented mechanism and not committed.**
- [ ] **Run smoke after a full `down`/`up` cycle.**

## P0 · Backup, restore and recovery evidence

- [ ] **Run a real PostgreSQL backup with the repository tooling.**
- [ ] **Restore that backup into a clean PostgreSQL instance.**
- [ ] **Run consistency/smoke checks against the restored database.**
- [ ] **Record measured RPO/RTO for the tested topology.**
- [ ] **Verify backup encryption and key recovery procedures for managed deployments.**
- [ ] **Test failure where the latest backup is corrupt/unavailable and document fallback.**
- [ ] **Do not mark backup support complete until restore is proven.**

## P1 · GitHub Actions qualification artifacts

- [ ] **Run `.github/workflows/ci.yml` manually once after repository consolidation.**
- [ ] **Run `.github/workflows/security.yml` manually once after repository consolidation.**
- [ ] **Download and inspect `v0.1-qualification.json`.**
- [ ] **Ensure the qualification artifact records the exact Git commit SHA and runtime versions.**
- [ ] **Archive the successful V0.1 qualification artifact as release/checkpoint evidence.**
- [ ] **Investigate flaky jobs rather than rerunning until green.**

## P1 · Security and privacy manual review

- [ ] **Review authentication/session lifecycle manually.**
  - disabled users
  - `session_version` revocation
  - expired JWT
  - tenant scope changes after token issuance
- [ ] **Run authorization abuse tests for cross-organization and cross-location access.**
- [ ] **Review logs for secrets/PII leakage.**
- [ ] **Review upload/file handling before exposing customer attachments publicly.**
- [ ] **Threat-model any new external integration before enabling it by default.**
- [ ] **Perform a dependency/supply-chain review before the first public stable release.**
- [ ] **Establish private security-reporting contact and test the handling process.**

## P1 · Accessibility manual qualification

- [ ] **Keyboard-only review of all V0.1 interactive UI.**
- [ ] **Visible focus review.**
- [ ] **Screen-reader smoke with at least one Windows and one Android-supported path before V1.**
- [ ] **Contrast review for default and white-label branding paths.**
- [ ] **Reduced-motion behavior review when animations are introduced.**
- [ ] **Touch-target review on physical Android tablet.**

## P1 · Sync chaos/recovery qualification

- [ ] **Duplicate mutation delivery.**
- [ ] **Out-of-order mutation delivery.**
- [ ] **Temporary 5xx/network failures with retry/backoff.**
- [ ] **Permanent validation failure appears in Conflict Center.**
- [ ] **Concurrent edit conflict from two devices.**
- [ ] **Cursor durability across restart.**
- [ ] **Remote change with wrong tenant/location scope cannot advance local cursor.**
- [ ] **Large reconnect batch does not lose valid operations when one mutation conflicts.**

## P1 · GitHub/community administration

- [ ] **Publish/verify `SECURITY.md`, `GOVERNANCE.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `MAINTAINERS.md` and license files on `main`.**
- [ ] **Configure issue/PR templates and labels once the project opens to external contributions.**
- [ ] **Publish `TRADEMARKS.md` before V1 branding/certification is used publicly.**
- [ ] **Establish at least two custodians for release/security/domain/package assets per governance milestones.**
- [ ] **Decide when the Founding Maintainer bootstrap conditions are satisfied and record the transition.**

## P1 · Operational environment decisions that require a human/operator

- [ ] **Choose the first supported installation topology to qualify operationally:** LAN recommended for multi-user/no-WAN, or a controlled Cloud instance.
- [ ] **Provide real DNS/domain when testing TLS/production edge behavior.**
- [ ] **Provision backup storage owned/recoverable by the operator/customer.**
- [ ] **Choose email/WhatsApp/payment providers only when the implementation milestone actually requires them.**
- [ ] **Keep provider credentials outside Git and document rotation/revocation.**
- [ ] **Validate jurisdiction-specific fiscal/payment requirements with appropriate local professionals before selling them as compliant functionality.**

## P2 · Release/handoff readiness before declaring V0.1 complete

- [ ] `uv.lock` committed and frozen install proven.
- [ ] `pnpm-lock.yaml` committed and frozen install proven.
- [ ] All Python/TS static checks pass.
- [ ] PostgreSQL 18.4 integration passes.
- [ ] Production PWA build passes.
- [ ] Golden Slice browser E2E passes.
- [ ] IndexedDB 100k spike evidence recorded.
- [ ] Windows physical qualification recorded.
- [ ] Android tablet physical qualification recorded.
- [ ] Compose runtime smoke passes.
- [ ] Backup + restore drill passes.
- [ ] Security workflow passes or has explicitly accepted, time-bounded risk records.
- [ ] Accessibility gates for V0.1 scope pass.
- [ ] `v0.1-qualification.json` is tied to the exact release candidate SHA.
- [ ] `execution-state.yaml` contains no unresolved V0.1 blocker that is a release gate.
- [ ] Only then change V0.1 from `partial` to its completed/qualified state and begin V0.2 Workshop Core.

## Evidence log

Add durable evidence below instead of editing completed checklist history away.

| Date | Item | Evidence | Commit / artifact | Notes |
|---|---|---|---|---|
| _pending_ | Repository consolidation | _pending_ | _pending_ | GitHub must match authoritative local tree before canonical handoff. |
