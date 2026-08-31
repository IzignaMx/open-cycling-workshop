# Open Cycling Workshop Platform · Manual Actions & Blockers Checklist

> Living operational checklist for actions that cannot be proven or completed autonomously from every execution environment. Keep this file current until the corresponding evidence exists in `docs/10-spec-development/execution-state.yaml` and the V0.1 qualification artifact.

### P0 · Restaurar el repositorio remoto desde el bundle autoritativo

> **Completado el 2026-08-30 por vía alternativa y verificada.** En lugar del bundle binario (cuyo fragmento subido a GitHub estaba truncado), se consolidó desde la carpeta local declarada autoritativa por el propietario, con auditoría previa del remoto (solo staging de rescate: 7 archivos, 0 artefactos, 0 releases, 0 tags; el helper ya estaba versionado localmente).

- [x] Consolidación a `main` desde entorno Git autenticado con DCO (commit `390241e`, 218 archivos).
- [x] Verificación de ida y vuelta: `git fetch` de vuelta y comparación de commit SHA + tree SHA (`390241ed…` / `91ea15cc…`) — idénticos.
- [x] Respaldo del estado pre-consolidación en el tag `archive/pre-consolidation-2026-08-30` (contiene también el histórico de `bootstrap/v0.1` como ancestro).
- [x] `bootstrap/v0.1` eliminada tras verificar que era ancestro del estado respaldado; solo queda `main`.
- [x] Confirmado que `_consolidation-probe.txt`, fragmentos `_repo_bundle/` y bootstrap temporales NO aparecen en el árbol final.
- [x] `REPOSITORY-RESTORE-REQUIRED.md` ya no aplica: el árbol completo reemplazó al bootstrap parcial.

> Este paso es manual únicamente cuando el entorno del agente no dispone de transporte Git autenticado capaz de subir el pack binario sin alterarlo. No sustituirlo por copiar archivos individualmente: la verificación de tree SHA es la garantía de integridad.

## How to use this checklist

- Check an item **only after evidence exists**. A command being expected to work is not evidence.
- Prefer attaching or linking evidence from GitHub Actions, release artifacts, screenshots, logs, device test records, restore reports, or ADR/RFC records.
- When a blocker is resolved, update both this checklist and `docs/10-spec-development/execution-state.yaml` in the same pull request/commit.
- Do not delete completed entries; mark them complete and add evidence so the history remains auditable.
- Never paste secrets, passwords, private keys, production tokens, customer PII, payment data, or backup encryption keys into this file.

## P0 · Repository integrity and GitHub governance

- [x] **Confirm `main` contains the complete authoritative repository tree.**
  - Evidence (2026-08-30): root commit `390241e` pushed from the audited local tree; remote fetched back and commit/tree SHAs verified identical; 218 tracked files.
- [x] **Confirm `bootstrap/v0.1` is either intentionally retained or removed after consolidation.**
  - Evidence: deleted 2026-08-30; it was an ancestor of the archived pre-consolidation state (tag `archive/pre-consolidation-2026-08-30`); `main` is the single canonical branch.
- [x] **Protect `main`.** (2026-08-31)
  - Pull requests required; required status checks `verify` (CI) and `security` (Security) on up-to-date branches; force-push and deletion blocked; conversation resolution required.
  - Bootstrap-phase policy: 0 approving reviews required and `enforce_admins` OFF — the Founding Maintainer remains the only custodian, so admin merge is the documented break-glass path until a second custodian exists. Tighten (1 approval, code-owner reviews, enforce for admins) when governance milestones add custodians.
- [x] **Configure CODEOWNERS enforcement for high-risk paths.**
  - Evidence: `.github/CODEOWNERS` versioned mapping auth/identity, sync (server + web), migrations, plugin SDK, CI/security/release tooling and the execution-state documents. Code-owner review _requirement_ stays OFF during the solo-custodian bootstrap (same break-glass rationale).
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

- [x] **Generate and commit `uv.lock` using a runner with PyPI access.**
  - Evidence (2026-08-30): generated via CI artifact then regenerated locally after adding `httpx`; `uv lock --check` clean; `uv sync --all-packages --group dev --locked` passes from scratch.
- [x] **Generate and commit `pnpm-lock.yaml` using the pinned pnpm/Corepack version.**
  - Evidence (2026-08-30): generated by the CI workflow artifact; `pnpm install --frozen-lockfile` passes from scratch locally (pnpm 11.17.0).
- [x] **Download the `v0.1-lockfiles` GitHub Actions artifact if CI generated the initial lockfiles.**
  - Evidence: downloaded, diffed against regenerated local locks, committed.
- [ ] **Run dependency vulnerability audits against committed locks.**
  - Python: `pip-audit`/approved equivalent through the pinned uv environment.
  - JS: the approved pnpm audit/dependency review path.
  - Document accepted exceptions with expiry dates and rationale.

## P0 · Python runtime and PostgreSQL 18.4 qualification

- [x] **Install/verify psycopg v3 in a clean supported Python 3.13 environment.**
  - Evidence (2026-08-30): real connections and transactions against local Docker `postgres:18.4-trixie`.
- [x] **Run the PostgreSQL integration suite against PostgreSQL 18.4.**
  - Evidence: `services/platform/tests/db/` 5/5 passed with `OCWP_TEST_DATABASE_URL` on the dedicated `ocwp_e2e` container (host port 5434).
- [x] **Run Alembic `0001 → HEAD` against an empty PostgreSQL 18.4 database.**
  - Evidence: `test_postgres_18_migrates_to_head_with_expected_v01_tables` passed; E2E seed script repeats the empty→head path on every run.
- [ ] **Run migration preservation tests from every supported prior schema snapshot once those snapshots exist.**
- [x] **Verify `postgresql://` and `postgres://` provider URIs are normalized to psycopg v3 and work end-to-end.**
  - Evidence: `tests/db/test_database_url.py` 3/3 green plus real psycopg connections through the normalized URL.
- [ ] **Verify tenant/location foreign-key invariants on PostgreSQL, not only SQLite surrogate tests.**
  - Partially evidenced 2026-08-30: a real FK violation surfaced and was fixed (users-before-tenancy ordering in the E2E seed and `ocwpctl bootstrap admin`); keep open until negative cross-tenant tests run against PostgreSQL explicitly.
- [ ] **Verify `FOR UPDATE SKIP LOCKED` job-claim semantics with concurrent PostgreSQL workers.**

## P0 · Full static analysis and formatting gates

- [x] **Run Ruff lint in the real uv environment.** — Evidence (2026-08-30): `ruff check` green after fixing 132 violations.
- [x] **Run Ruff format check.** — Evidence: green.
- [x] **Run mypy using the committed configuration.** — Evidence: 0 issues in 48 files.
- [x] **Run ESLint from the installed pnpm workspace.** — Evidence: green after globals/shim/exemption configuration.
- [x] **Run Prettier check from the installed pnpm workspace.** — Evidence: green after formatting and ignoring generated artifacts.
- [x] **Resolve every real error instead of weakening configuration to make CI green.**
  - All fixes are code-level; the only suppressions are the documented `static-shims.d.ts` exemption (ambient module declarations) and underscore omission pattern for rest siblings.
- [x] **Record any intentional suppression with a narrow scope and explanatory comment.** — See `eslint.config.mjs`.

## P0 · Production PWA build and browser E2E

- [x] **Build the real Vite PWA from committed lockfiles.**
  - Evidence (2026-08-30): `pnpm --filter @ocwp/web build` exits 0; `dist/sw.js` + workbox precache generated (5 entries).
- [x] **Inspect generated Service Worker and manifest.**
  - Evidence: generateSW with `navigateFallback: /index.html`; `preview.proxy` added so the production preview reaches the backend (previously missing).
- [x] **Run hosted Playwright + axe Golden Slice.**
  - Evidence (2026-08-30, local Windows, CI-mode against `vite preview` + PostgreSQL 18.4): login with persisted user; SW readiness; offline customer creation; offline reload persistence of customer and pending mutation; reconnect with exactly-once application; queue drains; second browser context converges; zero axe `serious`/`critical` violations. **Pending: repeat green on GitHub-hosted CI.**
- [x] **Persist Playwright traces/screenshots on failure in CI.** — Configured (`trace: retain-on-failure`, artifacts verified on failure).
- [x] **Confirm browser E2E uses production `vite preview`, not only the development server.** — Verified locally with `CI=1`; hosted confirmation pending the CI run.

## P0 · IndexedDB / Dexie qualification

- [x] **Run SPK-001 with at least 100,000 representative local records.**
  - Evidence (2026-08-31, desktop component): real Chromium 151 headless via Playwright — 100,000 records (256-byte payloads) in a single transaction: write **43,250 ms**, count+sample read **149.5 ms**, `status: pass`. The benchmark runner now drives the page through Playwright waiting for the page's real completion signal (`title === DONE`); the previous `--virtual-time-budget` + `--dump-dom` approach never completes on Windows Chromium because virtual time does not advance while IndexedDB IO is pending.
  - Remaining: repeat on Android tablet and on physical Windows hardware to close R01-T035.
- [x] **Run pending-mutation persistence across reload while offline.**
  - Evidence (2026-08-30): Golden Slice reload-while-offline step passed with customer + queued mutation intact. Browser/OS restart persistence still pending (P1 device tests).
- [x] **Prove Dexie migrations preserve queued mutations.**
  - Evidence (2026-08-31, hosted CI green on PR #4, run 33447612587): `e2e/dexie-migration-persistence.spec.ts` seeds a raw version-1 database (v1 store/index layout) with a pending create, the app upgrades the store to schema v2 in place and the preserved mutation syncs with the queue drained.
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

- [x] **Run `docker compose -f infra/compose/docker-compose.dev.yml config`.**
  - Evidence (2026-08-31): valid after fixing the postgres volume mount to the postgres-18+ layout (`/var/lib/postgresql` parent, not `.../data` — the 18.4 image refuses the old layout).
- [x] **Build API and worker images from scratch.**
  - Evidence: `docker compose up -d --build` — uv-based image build (python:3.13-slim-trixie), system user `ocwp`.
- [x] **Start PostgreSQL 18.4 + API + worker via Compose.**
  - Evidence: postgres `healthy`, api `healthy`, worker `Up`.
- [x] **Verify `/health/live` and `/health/ready` semantics.**
  - Evidence: live `{"status":"ok"}` (process) and ready `{"status":"ready","environment":"development"}` (alembic migrated + DB reachable).
- [x] **Verify only intended ports are exposed.**
  - Evidence: only `127.0.0.1:8000->8000` published; postgres `5432/tcp` internal only.
- [x] **Verify containers run non-root where specified.**
  - Evidence: api and worker run as `ocwp` (uid 10001, per Dockerfile); postgres uses the official image's root entrypoint (drops to the `postgres` user for the server process) — documented, image-standard.
- [x] **Verify secrets are provided through the documented mechanism and not committed.**
  - Evidence: `OCWP_AUTH_SECRET_FILE=/run/secrets/auth_secret`, file under gitignored `infra/compose/secrets/`, confirmed with `git check-ignore`.
- [x] **Run smoke after a full `down`/`up` cycle.**
  - Evidence (2026-08-31): full `down` → `up` → ready again, data persisted (organizations=1, users=1), login over HTTP succeeds. Also validated `ocwpctl bootstrap admin` on the fresh install against real PostgreSQL 18.4 (`created: true`) — this exercises the FK parent-flush fix from the consolidation session.
- [ ] **Fresh-install Compose smoke on a clean Linux host** (hosting target topology) — the Windows Docker evidence above covers the stack behavior; repeat on the first production-like host.

## P0 · Backup, restore and recovery evidence

- [x] **Run a real PostgreSQL backup with the repository tooling.**
  - Evidence (2026-08-31): `scripts/database/backup_postgres.py` via its runner indirection executing the official `pg_dump` (custom format, 19,350 bytes) inside the compose `postgres:18.4-trixie` container.
- [x] **Restore that backup into a clean PostgreSQL instance.**
  - Evidence: `pg_restore` into a fresh `postgres:18.4-trixie` container with an empty `ocwp` database.
- [x] **Run consistency/smoke checks against the restored database.**
  - Evidence: public-schema table set identical (9 tables incl. `alembic_version`); row counts identical (organizations/locations/users).
- [x] **Record measured RPO/RTO for the tested topology.**
  - Evidence: backup+verify 0.43 s, restore 0.42 s on the dev dataset (Windows/Docker); RPO equals the operator's backup schedule, dumps are point-in-time consistent. Re-measure on realistic data volume before production claims.
- [ ] **Verify backup encryption and key recovery procedures for managed deployments.** (applies when the managed topology exists)
- [x] **Test failure where the latest backup is corrupt/unavailable and document fallback.**
  - Evidence (2026-08-31): corrupt-generation drill — generation 2 truncated to 25% is rejected by the repository tooling (`pg_restore --list`: end-of-file, 0.19 s), fallback to generation 1 restores into a clean instance (0.29 s) with the generation-1 state and identical schema. Documented procedure: keep ≥2 generations, verify each with `pg_restore --list` after writing, fall back to the previous verified generation, restore into a clean instance and run consistency checks before declaring recovery.
- [x] **Do not mark backup support complete until restore is proven.** — proven for the dev topology above.

## P1 · GitHub Actions qualification artifacts

- [x] **Run `.github/workflows/ci.yml` manually once after repository consolidation.**
  - Evidence (2026-08-31): green on push `d60ed4e`, run 33356009981 — includes PostgreSQL 18.4 service, full static analysis, production PWA build, Playwright golden slice and the qualification verifier.
- [x] **Run `.github/workflows/security.yml` manually once after repository consolidation.**
  - Evidence: green on push `d60ed4e`, run 33356010020 — gitleaks (pinned image v8.30.1), REUSE 216/216, pip-audit, Trivy 0.63.0 with zero CRITICAL/HIGH.
- [x] **Download and inspect `v0.1-qualification.json`.**
  - Evidence: schema 2, `ci: true`, 26/26 checks pass, overall `partial` only on environment/manual gates (psql client, IndexedDB 100k benchmark, physical devices).
- [x] **Ensure the qualification artifact records the exact Git commit SHA and runtime versions.**
  - Evidence: `git_sha d60ed4e493c0827430e77a4c7f4b69c0349cf8b7` with Python/Node/platform metadata.
- [x] **Archive the successful V0.1 qualification artifact as release/checkpoint evidence.**
  - Evidence (2026-08-31): pre-release `v0.1.0-qualification.2026-08-31` on qualified commit `456c7bc` (CI run 33448325753) with `v0.1-qualification.json` attached (status `passed`, 27/27 checks, `ci: true`).
- [x] **Investigate flaky jobs rather than rerunning until green.**
  - Every failure in the loop was root-caused (trivy tag, gitleaks license, REUSE coverage, env-var override in the migration test, pnpm-from-Python tool resolution) and fixed at the cause.

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

- [x] **Duplicate mutation delivery.**
  - Evidence (2026-08-31): service-level chaos baseline plus browser `e2e/sync-chaos.spec.ts` — the same mutation reaches the server three times (two out-of-band replays plus the app retry after a lost response) and applies exactly once: single change-feed entry, server version 1, queue drained.
- [x] **Out-of-order mutation delivery.**
  - Evidence: deterministic reorder coverage in `services/platform/tests/sync/test_chaos_baseline.py` (service level); the browser suite covers the delivery-duplication and retry paths end to end.
- [x] **Temporary 5xx/network failures with retry/backoff.**
  - Evidence (2026-08-31): new bounded exponential backoff policy (`apps/web/src/sync/retry-policy.ts`, core-tested: 2 s→30 s cap, 8 attempts, then stops) applied to both offline and error states; browser chaos spec injects two 503 responses and converges with the queue drained.
- [ ] **Permanent validation failure appears in Conflict Center.**
- [x] **Concurrent edit conflict from two devices.**
  - Evidence (2026-08-31): `e2e/conflict-path.spec.ts` — online create (v1), remote concurrent update via API while the device is offline, stale local edit queued (base_version 1), reconnect push yields a real server conflict; visible in Conflict Center, mutation leaves the retry queue, device converges to the winning edit and the incident persists across reload.
- [ ] **Cursor durability across restart.**
- [ ] **Remote change with wrong tenant/location scope cannot advance local cursor.**
- [x] **Large reconnect batch does not lose valid operations when one mutation conflicts.**
  - Evidence (2026-08-31): service-level batch isolation test (`test_sync_api.py`) plus browser chaos — three queued mutations with a stale middle entry reconnect into one push; both independent valid creates apply, the conflict surfaces in the Conflict Center and the queue drains.

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

| Date       | Item                                   | Evidence                                                                                                                                                                                                                     | Commit / artifact                                      | Notes                                                                                              |
| ---------- | -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| 2026-08-30 | Repository consolidation               | Remote audited (staging only, nothing unique); local tree pushed to `main`, round-trip SHA verified; pre-consolidation state archived in tag                                                                                 | `390241e` · tag `archive/pre-consolidation-2026-08-30` | GitHub canonical from this point                                                                   |
| 2026-08-30 | Lockfiles + frozen installs            | CI-generated, locally regenerated after `httpx`; `uv sync --locked` and `pnpm install --frozen-lockfile` green                                                                                                               | gate-fix commit                                        | unblocks reproducible installs                                                                     |
| 2026-08-30 | Full static analysis                   | Ruff (132 fixes), mypy (48 files), ESLint, Prettier all green locally                                                                                                                                                        | gate-fix commit                                        | no configuration weakened                                                                          |
| 2026-08-30 | PostgreSQL 18.4 integration            | Docker `postgres:18.4-trixie`; db tests 5/5; empty→head migrations; FK ordering bug found & fixed                                                                                                                            | gate-fix commit                                        | host port 5434 (5432/5433 occupied)                                                                |
| 2026-08-30 | Production PWA build                   | `vite build` green with SW + precache; `preview.proxy` added                                                                                                                                                                 | gate-fix commit                                        | build was never previously executable                                                              |
| 2026-08-30 | Golden Slice E2E                       | CI-mode `vite preview` + PG 18.4: offline create, reload persistence, exactly-once reconnect sync, two-browser convergence, axe zero critical/serious                                                                        | gate-fix commit                                        | browser `fetch` Illegal-invocation bug fixed; retry-while-offline added                            |
| 2026-08-31 | Compose fresh-install smoke            | Build from scratch; live/ready health; ports audit (only 127.0.0.1:8000); api+worker as `ocwp`; secrets gitignored; down/up cycle with persisted data and successful login; `ocwpctl bootstrap admin` on real PG 18.4        | runtime-gates commit                                   | postgres-18+ volume-mount fix (`/var/lib/postgresql`)                                              |
| 2026-08-31 | Backup + restore drill                 | Repository tooling → real `pg_dump`/`pg_restore` in postgres:18.4 containers; clean-instance restore; identical tables (9) and row counts; 0.43 s backup / 0.42 s restore (dev dataset)                                      | runtime-gates commit                                   | RPO = operator schedule; re-measure on production-like volume                                      |
| 2026-08-31 | IndexedDB 100k benchmark               | Real Chromium 151 via Playwright: 100k records, write 43,250 ms, count+sample 149.5 ms, status pass                                                                                                                          | runtime-gates commit                                   | `--virtual-time-budget` never completes with pending IDB IO; driver now waits for `title === DONE` |
| 2026-08-31 | `main` protection + CODEOWNERS         | PRs required, checks `verify`+`security` required, force-push/deletion blocked, conversation resolution; CODEOWNERS for high-risk paths                                                                                      | governance config + CODEOWNERS commit                  | solo-custodian bootstrap: 0 approvals, enforce_admins OFF (documented break-glass)                 |
| 2026-08-31 | V0.1 qualification artifact **passed** | Hosted run 33358054057 on `31518cc`: overall **passed** — IndexedDB 100k hosted (100k records, 39,412 ms write, 104.7 ms read, ubuntu) and browser E2E hosted green                                                          | `31518cc` artifact `v0.1-qualification`                | first overall-passed artifact in project history                                                   |
| 2026-08-31 | `main` protection active               | API PUT branches/main/protection: PRs required, checks `verify`+`security` required (strict), force-push/deletion blocked, conversation resolution required, `enforce_admins=false` (documented break-glass)                 | repository settings                                    | solo-custodian bootstrap policy recorded above                                                     |
| 2026-08-31 | R01-T021 browser conflict-path         | New `e2e/conflict-path.spec.ts` green locally with the golden slice (2/2, 9.7 s) and on hosted CI: real stale-base_version conflict → visible Conflict Center → queue drain → convergence → persistence after reload         | `feat/e2e-conflict-path` PR                            | first explicit hosted browser conflict evidence                                                    |
| 2026-08-31 | R01-T036 browser chaos                 | `e2e/sync-chaos.spec.ts`: triple delivery of one mutation → exactly once (1 feed entry, server v1, queue drained); two injected 503 → bounded backoff (retry-policy, core-tested) → convergence. Suite 4/4 in 19.9 s locally | PR `feat/sync-retry-backoff-browser-chaos`             | closes duplicate/out-of-order/5xx-retry chaos items                                                |
| 2026-08-31 | Dexie migration + batch isolation      | New `e2e/dexie-migration-persistence.spec.ts` (raw v1 DB → in-place upgrade → preserved queue entry syncs) and large-batch conflict isolation (service test + browser chaos). Local suite 6/6 in 26.7 s; pytest 100/100      | PR `feat/dexie-migration-and-batch-isolation`          | Dexie item flips to checked once this PR's hosted CI is green                                      |
