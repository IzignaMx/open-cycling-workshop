# Open Cycling Workshop Platform · Manual Actions & Blockers Checklist

> Living operational checklist for actions that cannot be proven or completed autonomously from every execution environment. Keep this file current until the corresponding evidence exists in `docs/10-spec-development/execution-state.yaml` and the V0.1 qualification artifact.

## Quote persistence · 2026-10-15 planned gates

PR44's first hosted candidate failed direct Python tests and AMD64 runtime.
Direct and aggregate Python each retained two varchar-refusal assertion failures,
2,944 passes and 23 skips. The two tests now require the exact backend-specific
refusal and unchanged retained rows; PostgreSQL requalification is pending.
The runtime passed fresh migration and seven checks, then timed out after the
intentional API stop/start, before any backup. It retained no container logs;
the underlying cause remains unknown. A bounded diagnostic-only runner change
has combined independent source review. Follow-up head `26b589be` passed all
eleven runtime checks and Security on their first attempts, including its single
API restart and generic PostgreSQL restore; this does not explain the original
failure or exercise the new failure diagnostics. A separately reviewed
qualification proposal now requires three consecutive fail-fast restart cycles
with unchanged readiness deadlines. Exact changed-head hosted evidence remains
pending. Do not retry the failed candidate or infer quote-specific restore passes. See the
[retained failure record](docs/10-spec-development/2026-10-15-quote-persistence.md#first-hosted-candidate-and-runtime-diagnostics).

The [accepted boundary](docs/02-technical-architecture/2026-10-15-quote-persistence-and-online-command-boundary.md)
authorizes repository-first Task 6 only. The additive schema has local SQLite
and independent source evidence; PostgreSQL runtime qualification remains open.

- [x] Additive SQL0012 schema, registration and immutable/tenant constraints on SQLite.
- [x] Bounded private storage codecs/semantic commands and independent boundary review.
- [ ] Exact-source hosted aggregate/security/DCO and SQL0011→0012 PostgreSQL
      migration, race, restore and maximum-fixture runtime evidence.
- [ ] Exact-head three-cycle API restart qualification and all remaining runtime
      checks. Retain the unknown original failure cause even if these pass.
- [x] Implement atomic repository/reconstruction and retain discovered failure regressions.
- [x] Final independent source review and available local qualification: 21 pass,
      zero fail, five environment blockers; hosted/runtime gates remain open.
- [ ] Separate application/grant/capability compatibility and all-ingress fences
      before any quote mutation route is exposed.
- [ ] Separate operator authority, backup/restore and replacement of every old
      server/maintenance writer before first real enrollment. Protocol 1 alone
      cannot fence an old server binary.
- [ ] Later line-coverage, work/reservation, post-transition consent and offline
      integration; initial consent is not an operational quote/inventory journey.

## Shared workshop branding · 2026-10-14 candidate gates

The new increment starts from merged main39 `eef9559d8c3e528e79c99898360892188b23b55e`.
Its postmerge 27/27 aggregate controls, 43 direct/aggregate browser cases, runtime,
authenticated restore, security and three ARM64 builds passed. See the separate
[inherited evidence](docs/10-spec-development/2026-10-14-shared-workshop-branding.md#inherited-baseline).
Earlier qualification below does not qualify these new changes. Shared name,
curated palette, canonical logo, explicit inheritance and admitted offline cache
are implemented; exact integrated evidence remains pending. The published
`de5fa029` source passed 63 direct and 63 aggregate browser cases and actual native
ARM64 smoke, but pixel review of 74 original scenes found transparent-logo and
CSS-enlargement word defects. Those results remain tied to that earlier tree;
the corrected renderer and revised ARM criterion require a fresh exact run.

- [ ] Exact-head PostgreSQL0010→0011/migration/lock/revocation tests.
- [ ] Native authenticated schema6→7 preservation, first-admission preferences,
      scope/offline/reload/takeover and old-client regression.
- [ ] Four-theme desktop/tablet/320px and keyboard/zoom/forced-colors screenshots,
      followed by actual pixel review; source/collection is not execution.
- [ ] Same-snapshot database+assets restore into fresh targets, authenticated
      decoded-logo byte comparison, corrupt-latest refusal/earlier recovery and
      stale-token/checkpoint rejection, including mixed-floor operator safeguards.
- [ ] Docker private-volume API save/read, restart ownership/persistence and fresh
      restored byte proof and exact dependency audit.
- [ ] All three ARM64 cross-builds plus actual standard native ARM64 installed-
      decoder execution under unchanged production limits. Missing/skipped native
      execution cannot qualify. Separate QEMU diagnostics retain their true result
      and unproven failure cause; they do not qualify architecture execution.
      Hosted native smoke does not qualify physical Raspberry timing/memory,
      hostile worst-case inputs or installation behavior.
- [ ] Real deployment/content/grant adoption only after separate operator authority;
      no real account, credential, image or installation was changed by implementation.
- [ ] Physical Windows/Android, screen-reader/glare and realistic-capacity recovery
      gates remain open. Public contacts and profile interchange remain follow-on scope.

## Historical administration candidate summary · 2026-10-14

The authoritative inherited source baseline is main38
`79cb4055aeb34344f2182d77e244c8187e9bb71b`. Its authenticated client C **has
executed and passed** exact postmerge CI/browser/native qualification in
[38630382271](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38630382271),
the eleven-check disposable runtime and isolated restore in
[38630382283](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38630382283),
and security in
[38630382252](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38630382252).
See `inherited_base_ci`, `inherited_base_runtime`, and `inherited_base_security`
in the [current administration evidence](docs/10-spec-development/2026-10-14-connected-administration-ui.md).

Earlier C source-checkpoint notes and unchecked hosted browser/restore items below
are historical requests for evidence, subsequently satisfied for this exact
baseline. They do not mean those main38 checks remain unexecuted. Actual
installation changes, real-operator recovery, physical Windows/Android and manual
screen-reader evidence remain open. Cross-built ARM64 images are not hardware
qualification. The new administration source is a separate candidate. Its fourth native run
passed 42 of 43 cases, including user creation/grants and four-theme reflow with
expanded-label focus. The isolated scene-matrix case stopped before its first
capture because a selected radio was asserted after its panel was hidden. The
fixture ordering correction retains all checks and awaits a new exact-tree full
native run and actual state-matrix pixel review. Earlier contaminated images
remain diagnostic, not complete visual-state qualification. No full MVP, production installation or release certification
is claimed.

> **Historical pre-main38 2026-10-14 update:** The historical summary below does not qualify new
> increments. The bounded access-administration API has separate exact-head
> PostgreSQL/upgrade and browser-isolation rollout gates in the
> [current operator section](#2026-10-14--local-account-administration-operator-gates).
> The [isolated identity-kernel rollout section](#2026-10-14--isolated-offline-identity-kernel-and-future-rollout)
> records historical browser/baseline and legacy-recovery gates. New C source
> integrates a distinct authenticated database; its exact-head hosted/browser
> and installation gates remain open in the C section below.
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
  - Coverage qualification (2026-10-14): this preserves the historical workflow conclusion. PR38 later demonstrated that a green badge can conceal zero-history Gitleaks coverage and an audit without project input. Actual history/locked-project coverage requires separate current evidence; no assertion is made that the older run had the same specific failure.
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

- [x] First PR32 head passed all 16 PostgreSQL context lock-wait cases in CI
      `38562738320`, covering both organization/user barriers, persisted authority
      freshness and signed expiry. Exact tree and artifacts are in the context
      increment record; local SQLite tests did not establish this proof.
- [ ] Requalify the combined context/kernel/ordered-feed candidate after merging
      actual main31 `6ad6acc146ec47b7b6bd7bf82b6c850898fb5c0e`. First-head evidence
      is historical and does not substitute for exact integrated-tree checks.
- [ ] Before any production context adapter/activation, qualify authoritative
      baselines, verified endpoint realm binding, old-client/service-worker fencing,
      restore/session invalidation and user-switch isolation. Keep every original
      realm journal and pending mutation; never automatically retarget old work.
      This server-only increment advertises `snapshot_protocol: null` and does not
      close existing browser/device/accessibility/administration rollout gates.

## Ordered feed prerequisite · rollout and acceptance boundary

- [ ] Qualify the organization writer barrier against real PostgreSQL on the
      exact integrated candidate, including commit/rollback ordering, independent
      organizations, concurrent duplicate replay and authorization changes while
      writers wait. First published PR31 head passed all ten real-PostgreSQL
      cases in CI run 38561799721; final main30 combined-tree proof remains pending.
      SQLite functional tests are not concurrency evidence.
- [ ] Before relying on ordered continuity, drain/replace all old server writers;
      the existing numeric feed does not fence older binaries. Historical REST-only
      rows require the separately designed authoritative baseline.
- [ ] Keep multi-user cache activation gated on baseline and a real mixed-client
      writer fence. Old browser bundles can reopen newer IndexedDB and write legacy
      stores; schema version increments alone do not establish safe rollout.
- See `docs/02-technical-architecture/2026-10-14-ordered-change-feed.md`.

## 2026-10-14 · Isolated offline identity kernel and future rollout

Scope: additive isolated Dexie v5 factory/kernel only. Production `App`, the
default singleton and Golden Slice remain on v4. New isolated contexts stop at
`BASELINE_REQUIRED`; authentication-context and authoritative complete-baseline
integration are not implemented. The live UI remains unqualified for shared
browser multi-user isolation. See the
[ADR](docs/02-technical-architecture/2026-10-14-isolated-offline-identity-kernel.md)
and [evidence record](docs/10-spec-development/2026-10-14-isolated-offline-identity-kernel.md).
These open items do not authorize deployment or imply an actual installation has
been migrated. Existing checked evidence remains historical.

- [x] Record the first reviewed tree `22ef13dd` / published head `668a18f5`:
      independent 60/60 focused tests; hosted CI `38559830979` passed 27 checks,
      eight isolated native cases, 23 production PWA cases twice and ten sync
      repetitions. Artifact links/digests and all explicit skips are in the
      evidence record; fake IndexedDB coverage remains identified separately.
- [ ] Requalify the exact combined source after true-merging actual main #29
      `f8720515`. First-head evidence above is not proof of the later server
      prerequisite integration. Preserve the existing Golden Slice.
- [ ] Before production activation, integrate effective authenticated context,
      bounded offline eligibility, reconnect revalidation and a complete
      authorized baseline with ordered handoff. Include historical direct-REST
      data, grant expansion/backfill and contraction. Prove writer commit-order
      and revocation races on real PostgreSQL; a zero-cursor replay is not a
      complete baseline.
- [ ] Qualify production PWA migration, old-bundle/service-worker and versionchange
      behavior, same-workshop A/B switching, two-tab stale commits/ACKs,
      offline/reload/reconnect, quota pressure and accessible held/recovery UX.
      Replace production auth/repositories/sync and the singleton together only
      after that evidence exists; retain compatible rollback/forward repair.
- [ ] Explicitly review the remaining server receipt actor/payload-binding risk
      and any required migration/legacy policy. Browser ownership metadata is
      not proof of historical authorship. Keep the administration UI and
      organization-wide owner navigation gated on integration and a qualified
      concrete-workshop selector.
- [ ] For a future installation with legacy pending work, use a reviewed,
      authorized preservation/reconciliation procedure. Keep all original rows
      and unknown fields. Do not infer an author from a login, actor field,
      matching workshop or conflict-type marker. No automatic claim/replay or
      bulk relabelling is provided. Separate possibly-applied work from
      never-sent work; a new actor's deliberate resubmission is a new audited
      action linked to the preserved original.
- [ ] Before any actual upgrade/recovery/origin change, account for browser
      queues separately from the verified server backup. A server dump does not
      contain local journal/IndexedDB data. Never clear IndexedDB, uninstall the
      PWA, force a schema downgrade or delete ambiguous history as a shortcut.
      Stop affected dispatch on uncertainty; preserve originals for compatible
      forward repair. Any private recovery export requires its own access and
      recipient/security design.

- [ ] Resolve the demonstrated old-bundle compatibility blocker before activation:
      Dexie 4.4.4 with both emulated and native Chromium IndexedDB lets a v4-only
      constructor open native50 and write the legacy queue. Hosted run
      `38559830979` confirmed this blocker. Qualify explicit old-bundle/client-protocol fencing
      and a no-mixed-writers procedure. A lower schema declaration is not a fence.
      A separate database name is a design option awaiting reviewed integration,
      not protection implemented here.

All eight existing stores, personal appearance and device-local logos pass the
exact-value emulator migrations; the first-head native cases additionally prove
queue/preferences preservation. Actual installation and broader native failure/
device qualification remain pending. Future quote
stores reserve v6 after the isolated v5 kernel; no v6 migration is implemented.
PostgreSQL administration `0008` and quote reservation `0009` remain unchanged.
No credentials, new server/wire contracts, physical-device evidence or actual
installation activation are supplied by this increment. Physical Windows,
Android, screen-reader, broader security and existing release gates stay open.

## 2026-10-14 · Bounded authoritative server baseline gates

- [ ] Obtain exact-head PostgreSQL 18.4 evidence for migration 0008→0009 and
      empty→head, ordered lock/revocation/expiry races, cross-worker replay and
      capacity, and EXPLAIN ANALYZE/BUFFERS of large hidden-only feeds. SQLite
      passes and locally skipped PostgreSQL cases do not close this gate.
- [ ] Before advertising baseline-v1, qualify every server path and reconcile
      independent review; context currently remains snapshot_protocol=null.
- [ ] Before any installation upgrade, preserve/verify backup and restore in an
      isolated target, establish no mixed old server writers, and review the
      schema-compatible rollback. Migration 0009 has not run on an installation.
- [ ] Before production client activation, separately qualify durable pre-start
      identity/resume, staged page transactions, full post-commit partition
      fencing, old-client/server write floor and restore/session invalidation.
      Preserve all original local journals/legacy work. Server validation does
      not prove durable browser receipt or authorize replay of unknown work.

Current SQL reservation: bounded baselines implement 0009 after 0008; unimplemented
quote persistence moves to 0010 after 0009. Earlier reservation notes remain
historical. Existing physical Windows/Android, accessibility and recovery gates
remain open. No source increment is installation or rollout evidence.

## 2026-10-14 · Isolated bounded baseline consumer gates

- [ ] Record independent review and exact-final-head hosted Chromium qualification
      for the new actual-FastAPI isolated journey. Local fake IndexedDB and
      type/build results do not establish native browser behavior; local
      Chromium launch is blocked by the execution sandbox.
- [ ] Before ordinary supported-protocol activation, separately qualify genuine
      server advertisement, generated contracts and epoch-consistent context,
      start and activation responses. The server still advertises null; ordinary
      clients remain BASELINE_REQUIRED with zero baseline requests.
- [ ] Before production integration, combine initial baseline, ongoing deltas and
      offline-reload admission with production auth/repositories and existing
      Golden Slice preservation. Keep old-writer/service-worker cutover,
      restore/session invalidation, history-preserving recovery, accessibility
      and physical-device gates open on their own evidence.

No database migration, oldDB deletion, legacy author inference, installation or
production activation is authorized or performed by this source increment. See
[the increment record](docs/10-spec-development/2026-10-14-isolated-baseline-client.md).

## 2026-10-14 · Inventory authority correction qualification

- [ ] Obtain exact-candidate PostgreSQL evidence for inventory product and
      movement authority changes while waiting, rollback, reverse write/revoke
      ordering, independent organizations and the updated two-edge stock/replay
      contention tests. Local functional RED/GREEN is not PostgreSQL proof.
- [ ] Before an actual authorized server update, use the reviewed backup/restore
      and drained-writer upgrade process. No installation was changed; this fix
      has no schema migration and does not fence old server binaries.
- Existing client activation, physical-device and accessibility gates remain
  unchanged. The narrow no-store correction does not qualify an administration
  UI or erase any stored client data. See the
  [scope and evidence](docs/10-spec-development/2026-10-14-inventory-authority-barrier.md).

## 2026-10-14 · Server cutover B qualification

- [ ] Obtain exact integrated-head PostgreSQL artifacts for forward migration and
      unconditional downgrade refusal, two-process organization-barrier ordering,
      cross-org receipt collision/savepoint preservation, operator CAS/rollback
      and restored-counter collision. Local skips and SQLite are not PG evidence.
- [ ] Obtain native Chromium evidence for the separate genuinely enabled floor1
      ordinary adapter/coordinator case, retaining the real floor0/null refusal.
- [ ] Complete C production integration and exact old-bundle/service-worker
      queue preservation before claiming the authenticated production workflow.
      Production App remains v4; no real activation has occurred.
- [ ] For any separately authorized installation: preserve pending journals and
      verified backup, drain/replace every pre-B writer, migrate forward, opt in
      explicitly, and rotate incarnation on isolated restored targets before
      reopening API/edge. Never lower the floor or increment restored counters
      as a substitute for incarnation invalidation.

See [server scope/evidence](docs/10-spec-development/2026-10-14-server-cutover-contract.md)
and [operator procedure](docs/07-operations/2026-10-14-server-cutover.md). Physical
device, screen-reader, real restore and broader product-scope gates are unchanged.

## 2026-10-14 · Authenticated workshop client C gates

- [ ] Qualify the exact integrated tree with genuine PostgreSQL/browser login,
      complete baseline, ongoing checkpoint chain, offline reload, captured
      push/ACK races, account/workshop switching and all four themes/accessibility.
- [ ] Run the pinned real old App/SW journey: legacy-session 401, fresh-login old
      transport 409, offline reload, actual SW update, preserved raw old data and
      late old-tab edits. Reproducible built assets alone do not close this gate.
- [ ] Inspect actual hosted selector/session-held and recovery UI captures at
      desktop and 320px across all four existing themes. Passing test badges or
      collected screenshot assertions alone do not establish visual readiness.
- [ ] Run all eleven disposable runtime checks with floor1 backup/restore,
      stopped writers, expected-incarnation rotation before restored API reopen,
      stale session/checkpoint refusal and preserved pending recovery holds.
- [ ] Before a separately authorized installation change, preserve local work
      from every browser profile and verify backup/isolated restore; replace all
      old server writers, opt in explicitly, and use forward-compatible recovery.
      Never clear IndexedDB, infer authors, replay unknown legacy data or lower
      compatibility floors. Normal Compose still defaults to disabled cutover.

C uses the distinct `ocwp-authenticated-v1` database with additive schema6
lookup indices. Future unimplemented quote-local stores reserve **v7**; prior
v6 notes remain historical. Local emulator/unit/build evidence is not hosted
SW/PG/restore or physical-device evidence. User/role CRUD administration UI and
new domain breadth remain later increments. See the
[C scope and evidence](docs/10-spec-development/2026-10-14-authenticated-workshop-client.md).

## 2026-10-14 · Audited Python dependency remediation

- [ ] Complete independent review and exact integrated-head hosted Security/CI
      with both the project-graph scanner correction and the dependency patch.
      Local pip-audit is clean for all 40 active Linux/Python 3.13 packages;
      all 42 registry packages are represented in the hashed export. This is
      not full-history/image, Windows or deployment qualification.
- [ ] Retain the existing PostgreSQL, native browser/service-worker, restore,
      physical-device and accessibility gates until their own evidence passes.
      The dependency patch changes no production installation or credentials.

The [applicability and evidence record](docs/03-security-privacy/2026-10-14-python-dependency-remediation.md)
accounts for all original 19 advisories, the bounded compatible upgrade and
the advisory with an unset patched-version field. No finding was suppressed.

## 2026-10-14 · Connected administration UI qualification

- [ ] Obtain exact integrated-head CI for the connected account/runtime facade,
      users/permissions/locations/self-session UI and all existing offline/probe
      regressions. Unit/emulator checks do not qualify native storage or sessions.
- [ ] Execute the actual-production administration browser journeys against
      disposable floor1 PostgreSQL; keep direct, repeat and aggregate artifacts
      separate. Verify zero-location/no-sync accounts and unconfirmed commands.
- [ ] Inspect actual four-theme administration screenshots and prove mounted
      drafts/focus, synchronous credential cleanup, keyboard/reflow/zoom/forced
      colors. Source regex checks and axe are partial accessibility evidence.
- [ ] Keep the pinned old-client/service-worker preservation and eleven-check
      runtime/restore gates on their own exact-tree evidence. Never clear local
      work, infer authors or replay ambiguous commands as a qualification shortcut.

No real accounts, passwords, first-owner command, installation update or deployment
was performed. Existing physical-device, screen-reader and operator recovery gates
remain open. See the [evidence record](docs/10-spec-development/2026-10-14-connected-administration-ui.md).

## 2026-10-15 · Administration probe-clock qualification

- [ ] Obtain exact-candidate direct/aggregate browser results and the separate
      five-run administration-clock repetition with zero retries. The main40
      direct artifact records 62 first-pass cases and one retry pass; its
      pre-secret clock exception is retained as evidence, not a clean first pass.
- Installed-Playwright VM RED/GREEN proves the bounded fixture correction, not
  real browser/API/lease-expiry behavior. See the
  [clock evidence record](docs/10-spec-development/2026-10-15-administration-probe-clock.md).
  Existing physical-device, screen-reader and installation gates remain open;
  no new operator action is required to change the test fixture.
- PR41's first hosted run passed all four clock regressions but failed the
  existing branding cache rollback assertion before browser setup. The later
  aggregate core pass does not supersede that failure; direct/repetition browser
  phases were skipped, and aggregate browser launch lacked the skipped Chromium
  installation. See the [bounded production cache correction](docs/10-spec-development/2026-10-15-branding-cache-clock-rollback.md).
- [ ] Obtain fresh exact-head hosted core, native cache/offline/takeover journeys,
      direct/aggregate browser and retry-free clock repetition after the cache
      correction. Local Node 22.16 deterministic/fake-IDB evidence is not native
      browser storage or real installation qualification.
- The next published tree `a57c700a` passed 741 core cases but failed the offline
  branding journey in direct and aggregate browser execution (62/63 each). Both
  direct attempts failed; no flaky pass occurred and repetition phases were
  skipped. These failures remain retained. The [offline refresh correction](docs/10-spec-development/2026-10-15-offline-branding-refresh.md)
  adds finite coalescing of the existing forced request without relaxing cache
  rollback checks. The exact changed-head gates above remain open.

- The next PR41 candidate `93b9b30e09fa90c9dffc78105b8ef5fbc172852d`
  also has a retained 62/63 direct-browser failure in CI38678325955. Both attempts
  now pass the before-reload verified-copy assertion, then fail the saved-brand
  identity after reload at branding.spec.ts494. The [startup completion correction](docs/10-spec-development/2026-10-15-offline-branding-refresh.md#offline-reload-startup-completion-follow-up)
  adds a current-source request after initial operational reads; it does not
  change cache admission or retry budgets. This new local composition evidence
  does not qualify the browser journey. Exact changed-head direct/aggregate and
  retry-free repetition gates remain open.

- CI38678325955's aggregate subsequently finished: 26/27 controls, 2375 Python
  passes / 14 skips and 752 frontend passes. Browser: **60 first-pass, two flaky
  retry passes, one final failure**. Besides the retained offline reload failure,
  connected relogin and connected v1-preference reload first rendered OCWP instead
  of the current saved brand. Their retries passed; this does not erase either
  first failure. The [connected startup correction](docs/10-spec-development/2026-10-15-connected-branding-refresh.md)
  adds one current-admission completion request after the first settled sync.
  New exact-head direct/aggregate and retry-free gates remain required before
  integration; earlier local or hosted results do not qualify this combined tree.

## 2026-10-15 · Pure quote decision-domain boundary

- [ ] Obtain exact integrated-head hosted CI/Security/DCO for this bounded
      domain increment. Local arithmetic/evidence tests do not qualify durable
      timelines, PostgreSQL concurrency, native offline drafts or a live approval.
- [ ] Review persistence/API authority, atomic quote/order association and stock
      command preconditions separately before exposing customer decisions.
      Existing order transitions are not newly quote-gated by this increment.
- No new operator action is required for the pure in-memory module. No migration,
  grants, sync entity or UI is added. Superseded-revision evidence edits remain
  unsupported; immutable historical receipts and exact replay are retained.
  Physical-device, recovery and accessibility gates remain open. See the
  [scope and evidence](docs/10-spec-development/2026-10-15-quote-decision-domain.md).
