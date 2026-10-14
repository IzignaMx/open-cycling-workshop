# Open Cycling Workshop Platform · Manual Actions & Blockers Checklist

> Living operational checklist for actions that cannot be proven or completed autonomously from every execution environment. Keep this file current until the corresponding evidence exists in `docs/10-spec-development/execution-state.yaml` and the V0.1 qualification artifact.

> **2026-10-14 update:** The historical summary below does not qualify new
> increments. The bounded access-administration API has separate exact-head
> PostgreSQL/upgrade and browser-isolation rollout gates in the
> [current operator section](#2026-10-14--local-account-administration-operator-gates).
> Neither a complete MVP nor a production/release qualification is claimed.

# Open Cycling Workshop Platform · Manual Actions & Blockers Checklist

> **RESUMEN EJECUTIVO DE ACCIONES MANUALES PENDIENTES (2026-09-01).** Todo lo automatizable está probado y en verde (V0.1 completo salvo físico; V0.2 Increment 1 completo; Increment 2 en curso). Lo único que avanza este proyecto ahora requiere manos humanas, en este orden de prioridad:

## 1 · Cerrar V0.1 — Calificación física Tier 1 (ÚNICO bloqueador de release)

- **Ejecutar el protocolo** `docs/11-device-qualification/2026-08-31-tier1-protocol.md`:
  - **Windows (este equipo)**: pasos W1–W8 (~20 min): login → instalar PWA → offline create → reload offline → reconexión exactly-once (verificar `count(*) = 1` en PG) → conflicto → teclado → reinstalación.
  - **Android tablet**: pasos A1–A7 (~25 min) con **Opción A recomendada** (`adb reverse tcp:5173 tcp:5173` mantiene localhost como contexto seguro) o B (flag de origen seguro + `docker-compose.tier1.yml`).
- **Registrar evidencia** en `docs/11-device-qualification/2026-08-31-tier1-results.md` + capturas en `evidence/`.
- Al entregar resultados: se cierra R01-T035, V0.1 se declara calificado y se archiva el checkpoint de release.

## 2 · Revisiones manuales de accesibilidad (P1, cierran gates de V0.1)

- Teclado-only sobre toda la UI V0.1+V0.2 (login, alta cliente/orden, acciones de orden, Conflict Center).
- Lector de pantalla: 1 ruta Windows + 1 ruta Android.
- Contraste (default + branding), reduced-motion cuando exista animación.
- Touch targets en la tablet (cubierto parcialmente por A3 del protocolo).

## 3 · Observación de almacenamiento (P0 pendiente parcial)

- Presión de cuota IndexedDB (protocolo A6) y **decisión sobre `navigator.storage.persist()`** — hallazgo recurrente; si el desalojo ocurre, abre issue y lo implementamos.

## 4 · Gobernanza (cuando aplique)

- **Segundo custodio** → entonces ajustar protección de `main` (1 aprobación, code-owner reviews, `enforce_admins=true`) y trabajar solo vía PR.
- Verificar rechazo DCO de un commit sin firmar en rama de prueba (gate hospedado).
- Revisar visibilidad/owners del repo y administradores de recuperación.
- Descripciones/topics del repo (sin llamarlo producción antes de V1).

## 5 · Operación (cuando exista el host de destino)

- **Compose fresh-install smoke en host Linux limpio** (primera topología real: LAN o Cloud).
- DNS real / TLS cuando se pruebe el borde de producción.
- Re-medir RPO/RTO del drill de backup con volumen realista.
- Backup encryption para la topología administrada (si aplica).
- Decidir y documentar rotación de credenciales/secretos del deploy.

## 6 · Limpieza local discrecional (sin urgencia)

- Ramas locales desechables (los permisos del agente bloquean `git branch -D`): `git branch -D feat/inc2-t1-t2-inventory feat/v02-* docs/* feat/e2e-conflict-path ...`
- Tag `archive/pre-consolidation-2026-08-30` borrable tras validar Actions.
- Contenedores Docker locales (`ocwp-pg-e2e`, `ocwp-dev-postgres-1`) apagables si no se sigue desarrollando.
- Ruta de drift: `apps/web/.tmp-*` y `test-results/` ya están gitignored.

> Detalle completo y evidencia histórica de cada ítem: secciones siguientes de este archivo.

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

> **Protocolo operativo listo (2026-08-31):** ejecuta `docs/11-device-qualification/2026-08-31-tier1-protocol.md` (Windows en este equipo + tablet Android con las dos opciones de conectividad) y registra la evidencia en `docs/11-device-qualification/2026-08-31-tier1-results.md`. Para la opción sin cable usa `infra/compose/docker-compose.tier1.yml`.

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
- [x] **Remote change with wrong tenant/location scope cannot advance local cursor.**
  - Evidence (2026-10-13): PR #21; 29 new core cases plus two production-PWA
    rollback/reload/recovery journeys. Hosted CI run 38380494341 passed all nine
    E2E tests and 27 qualification checks; exact head/merge/tree evidence is in
    `docs/10-spec-development/2026-10-13-sync-pull-scope-integrity.md`.
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

## 2026-10-13 · Scoped pull integrity evidence

- [x] Hosted `sync-scope-integrity.spec.ts` journeys verified for PR #21.
      CI run 38380494341: 177 Python tests, 72 frontend tests, nine browser journeys,
      and 27 qualification checks passed. Both foreign-payload cases prove atomic
      rollback and durable client reload/recovery. Head, synthetic test merge, tree,
      and artifact IDs are recorded in the increment specification. The local
      Chromium policy block was respected. Physical-device qualification and
      TC-SYNC-003 server-restart evidence remain separate, unresolved gates.

## 2026-10-13 · Quote domain Task 4

- Quote arithmetic and immutable revisions have 106 focused tests passing locally;
  [Task 4 evidence](docs/10-spec-development/2026-10-13-quote-domain.md) tracks final
  qualification and hosted CI. This is a pure-domain increment, not a working
  quote workflow or a qualified release.
- No new operator action is required for the pure calculations. PostgreSQL,
  browser, physical-device and other existing manual release gates remain open
  where their own evidence is absent. Inventory API Task 3 was integrated through PR #22 on 2026-10-14.

## Inventory API · Migration 0007 operator boundary

- If migration 0007 reports duplicate reservation finalizations, stop inventory
  writes, take a verified backup, and review the conflicting RELEASE/CONSUME
  history before retrying. The migration deliberately blocks instead of
  deleting or rewriting movements. Do not bypass the guard by removing rows.
- Legacy standalone CONSUME entries are not automatically repaired: an existing
  physical-issue ADJUST may be unlinked. Reconciliation needs operator evidence
  and a reviewed history-preserving procedure.
- See `docs/02-technical-architecture/2026-10-13-inventory-command-atomicity.md`.
  This is a conditional operational boundary, not evidence that deployed data
  contains duplicates. Existing physical-device qualification remains open.

## Local workshop MVP / laptop-to-Raspberry (2026-10-14)

- [ ] Qualify the additive local Compose runtime on the actual laptop and Docker installation; hosted Linux results do not prove Docker Desktop permissions or host behavior.
- [ ] Identify Raspberry model, RAM, 64-bit OS, SSD/storage capacity, network and power resilience before promising suitability.
- [ ] Prepare secret-file ownership for the container identities on the destination; do not make credentials world-readable. Review Windows/Docker Desktop ACL behavior separately.
- [ ] Establish trusted LAN HTTPS before using PWA features from other devices; do not bypass browser certificate/security warnings.
- [ ] Execute clean-target restore and asset transfer with realistic data, verify identities/counts and business workflows, and measure RPO/RTO.
- [ ] Drain or preserve browser mutation queues before changing origins; a database dump does not include unsynchronized IndexedDB records.
- [ ] Establish encrypted off-device backup and verified retention; database-only tooling is not full installation recovery.

See [MVP acceptance plan](docs/10-spec-development/2026-10-14-local-workshop-mvp.md).
These entries do not close existing physical/manual V0.1 gates or authorize deployment.

## Effective identity/sync hardening: malformed legacy identities

- If a previously queued operation or stored receipt contains blank/whitespace
  identity fields, the hardened sync service returns a permanent conflict. Keep
  the queue, receipt and original business/event history intact for reviewed
  reconciliation. Do not clear IndexedDB, delete the receipt, substitute a
  normalized ID or retry under a new mutation ID as an automatic workaround.
- This is a conditional recovery boundary, not evidence that a real installation
  has malformed data or a new setup step for canonical IDs. See the
  [scope and evidence](docs/10-spec-development/2026-10-14-effective-identity-sync-authority.md).

## 2026-10-14 · Sync chaos setup regression

- [x] Verify the corrected large-batch setup and deterministic regression on
      hosted CI. PR #24 red run 38541165450 reproduces the legacy readiness
      helper resolving with a pending create. Green checkpoint 01f7c5e, run
      38542610878, passed all ten browser journeys, ten retry-free repetitions
      (five per affected journey), and a further ten-journey qualification pass.
      Artifact 11883580431 passed all 27 checks with zero blockers. Security and
      DCO passed. The exact-three conflict assertions remain intact. Subsequent
      base/evidence reconciliation commits require their own exact-head CI;
      see the dedicated sync-chaos setup document and current PR #24 checks.

## 2026-10-14 · Structural themes and personal presentation

- [ ] Review hosted screenshots for Banco, Plano, Ritmo and Noche at desktop,
      touch-tablet and 320px widths. Confirm the same data/actions remain
      accessible and that layout changes are structural, not only palette swaps.
- [ ] Run the existing physical Windows/Android and screen-reader protocols on
      the four themes, including 200% zoom, glare and touch use. Numeric palette
      checks and hosted Chromium/axe do not close these manual gates.
- Local implementation evidence and exact hosted/review status are tracked in
  `docs/10-spec-development/2026-10-14-structural-workshop-themes.md`.
- Shared organization/workshop branding is still pending; the current logo is an
  explicitly personal, device-local override. No operator should treat it as
  organization-wide branding or assume cross-device synchronization.

- Administrative rollout still needs offline-permission freshness and safe cache
  revocation/resnapshot with pending-mutation reconciliation. Presentation read
  gates preserve stored data and do not secure IndexedDB against a device owner.
- Legacy conflicts whose entity type was hardcoded remain stored with hidden details.
  Safe provenance reconciliation/recovery is pending; never infer their kind from
  the legacy customer label or discard the records as a shortcut.

## 2026-10-14 · Local account administration operator gates

Scope: server/API-only local users, role snapshots and locations. Design and
acceptance are recorded in the
[administration ADR](docs/02-technical-architecture/2026-10-14-access-administration.md)
and [increment specification](docs/10-spec-development/2026-10-14-access-administration.md).
These unchecked items are conditional installation/qualification work, not
evidence of a problem in a deployed database or authority to modify one.

### Integration and exact-head evidence

- [x] Verify the prerequisite PR #26 sync read-authorization fix is integrated:
      merged at `c1e2230` after all seven checks passed. The administration
      branch includes that main ancestry, merged runtime PR #25 (`0342799`)
      and migration target-isolation fixes; theme changes are independent.
- [x] Record the initial hosted PostgreSQL 18.4 proof at PR #27 head `0c37d46`:
      CI run `38550525461`, qualification artifact `11886836617`, 812 Python
      passed and three explained skips; all administration PostgreSQL cases ran.
      Runtime run `38550525483` and artifact `11885889541` passed all 11 checks,
      including PostgreSQL 18.4 backup/restore. See the increment specification
      for the exact merge-ref/tree match and browser/ARM64 evidence.
- [x] Repeat exact-head hosted PostgreSQL 18.x tests after the final main/evidence
      reconciliation: head `efe42eb7`, CI `38552076814`, artifact `11886948706`
      passed all 27 checks, 812 Python tests and 30 browser executions. Runtime
      `38552076701` / artifact `11886678534` passed 11 Docker checks and all three
      ARM64 image builds. Integrated at main `59ad7e9`. Coverage includes empty database → head and
      representative `0007` → `0008` preservation. Prove tenant FKs, audit
      UPDATE/DELETE/TRUNCATE rejection, mutation/audit rollback, first-owner and
      last-owner races, stale versions and actor revocation while waiting for
      the organization lock. Use only isolated `_test`/`_e2e` databases and
      record exact SHA, run/artifact link, versions, counts and failures/skips.
      Local SQLite evidence cannot close the PostgreSQL lock/migration gate;
      the current local execution environment has no server/Docker runtime.
- [x] Record local implementation static/full-test/OpenAPI/generated-client
      evidence and independent reconciliation review at `a077243`: 755 Python
      passed, 60 documented skips, 74 frontend core passed, 21 aggregate checks
      passed, zero failures and five environment blockers. The local branch
      was reconciled onto `833bf6e`; the final-head gate above records the later
      verified main/evidence reconciliation. See
      the increment specification for the historical checkpoint and review scope.

### Safe conditional upgrade to identity migration 0008

1. Confirm the selected installation, configured database and application image
   versions. Use the existing secret-injection mechanism; do not paste a
   credential-bearing database URL into commands, tickets or this checklist.
   Inspect current Alembic revision and verify a single chain:
   `0007 → 0008_identity_administration`. Future quote persistence is `0009`
   following `0008`; do not create an empty reservation or rewrite history.
2. Take a pre-upgrade backup with the supported tooling, verify it, and prove a
   restore into an isolated instance before relying on it. Record safe metadata
   and a recovery plan that accounts for changes after the backup.
3. Arrange a coordinated maintenance/read-only window for server writes and
   drain active writers before the migration. Preserve browser data and pending
   local mutations. This increment does not introduce a maintenance-mode switch
   or automate deployment; use the installation's supported operating process.
4. With the intended `OCWP_DATABASE_URL` already securely configured, run the
   migration from `services/platform`, using the pinned project environment:

   ```sh
   uv run alembic current
   uv run alembic upgrade head
   uv run alembic current
   ```

   Confirm the candidate's expected head and readiness before resuming writes.
   Do not accidentally use the example URL in `alembic.ini` or another project's
   database. Running with `--sql` is not proof of migration success.

5. If migration 0008 reports invalid legacy `session_version` values, keep
   server writes stopped, preserve the verified backup and investigate the
   affected identities. Review an explicit history-preserving reconciliation
   and session-revocation plan before retrying. Do not normalize versions
   blindly, delete users/audit/history, disable constraints/triggers or mark the
   revision applied without running it. Migration 0007's independent inventory
   guard remains in force.
6. Verify existing account IDs, organization/location, active state, grant
   snapshots, password hashes and session versions are unchanged by migration;
   new `is_owner` values are false and account `version` values are 1. Check the
   audit table/guards and owner-scope/positive-version constraints. Keep raw
   credentials and private account data out of evidence artifacts.

- [ ] Record backup/restore, maintenance window, migration and preservation
      evidence for the first actual supported installation upgrade.
- [ ] Record post-upgrade health, existing workshop-account login and API smoke
      results. No real-install migration is performed by this source increment.

Do not automatically downgrade schema 0008: removing the audit table/owner
metadata discards security history. Prefer a schema-compatible application
rollback or a separately reviewed forward fix/restore. Preserve audit and
post-backup work; do not bypass immutability guards to make rollback easier.

### Explicit first-owner setup, only when an operator elects to enable it

The migration does not promote the bootstrap user. The existing
`ocwpctl bootstrap admin` workflow remains unchanged and location-bound. After
the upgrade is qualified, an authorized local operator can create a separate
organization-wide owner using the existing installation configuration:

```text
ocwpctl access create-first-owner --organization-id ORGANIZATION_ID --username OWNER_USERNAME --display-name OWNER_DISPLAY_NAME --password-file PASSWORD_FILE
```

- Replace placeholders with the verified organization and a new unique account.
  Prepare the password file using an approved protected local mechanism; limit
  file access to the operator/runtime. Never place the password in shell
  arguments/history, command output, logs, tickets or repository files.
- The command creates a distinct account with `is_owner = true`, null location
  and all implemented concrete capabilities. It does not promote, rename,
  widen or reset the existing bootstrap account.
- It refuses if **any** owner record already exists in that organization, even
  inactive. A refusal is not permission to delete owner records, clear owner
  flags or rerun bootstrap. Existing owner credential loss requires a separately
  reviewed recovery path; this command is not recovery/rebootstrap.
- Verify one success audit and a new-owner API login without exposing secrets.
  Confirm an accidental repeat refuses and the original workshop account
  retains its scope. Handle the password file with the installation's approved
  secret-retention/disposal procedure after successful setup.
- [ ] Record explicit setup and API smoke evidence only if a real operator
      chooses to run this command. It has not been invoked against an actual
      installation by this source increment.

### End-user rollout gate: browser isolation and permission changes

- [ ] Isolate cached data by authenticated user, capability snapshot and scope;
      prove user switching and grant/scope contraction cannot expose another
      user's previously downloaded data. Server revocation alone is insufficient.
- [ ] Define and prove authorization-epoch cursor reset/resnapshot/backfill for
      grant/scope expansion so older newly permitted records are not skipped.
      Preserve and explicitly reconcile pending mutations across account,
      permission and location changes, offline/reload and reconnect. Never
      clear IndexedDB or discard pending writes as the normal recovery path.
- [ ] Implement and qualify the organization-wide workshop selector before
      offering owner navigation in the PWA. Until then, organization-wide
      owners are API-only. This increment changes no App/Dexie/Compose/theme
      behavior and is not a complete administration UI or full MVP.

Physical Windows/Android, accessibility, broader security/session and all other
unproven release gates above remain open on their own evidence.

### Authenticated context prerequisite qualification

- [ ] Run the 16 real PostgreSQL context lock-wait cases on the exact integration
      candidate with the existing dedicated `OCWP_TEST_DATABASE_URL` fixture.
      Verify both organization/user barriers, persisted authority freshness and
      signed expiry rejection. Local skips are not contention evidence.
- [ ] Before any production context adapter/activation, qualify authoritative
      baselines, verified endpoint realm binding, old-client/service-worker fencing,
      restore/session invalidation and user-switch isolation. Keep every original
      realm journal and pending mutation; never automatically retarget old work.
      This server-only increment advertises `snapshot_protocol: null` and does not
      close existing browser/device/accessibility/administration rollout gates.
