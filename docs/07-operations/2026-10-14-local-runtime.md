# Local workshop runtime: laptop first, then a Raspberry Pi

Status: **hosted runtime verified for `21245faacc991d91c1dd334bd37ba49c17141252`; physical laptop/Raspberry acceptance pending**.
[Local runtime 39990179250](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39990179250)
passed, including the separate native ARM64 decoder and three ARM64 image builds.
This is source-bound hosted evidence, not a pass for later commits or real devices.
See the [current reconciliation](../10-spec-development/2026-10-25-pr58-status-reconciliation.md).
This is an opt-in runtime; `docker-compose.dev.yml` and the Tier 1 development override are unchanged.
The hosted `Local runtime` workflow is the executable qualification path. A build
or static test is not a claim that this ran on a laptop, tablet or Raspberry Pi.

## Scope and boundaries

- Production PWA and API share one Caddy origin. PostgreSQL and API publish no
  host ports. The default entry point is `http://localhost:8080`, bound only to
  `127.0.0.1`. Localhost is a browser secure context; an HTTP LAN IP is not.
- PostgreSQL 18.4 owns connected data in a persistent named volume. A one-shot
  migration must succeed before API, worker or bootstrap starts. The database
  health check uses TCP so the initialization-only Unix socket cannot race it.
- Application and migration connections use `ocwp`, a database owner without
  cluster superuser, create-role, create-database or replication permissions.
  A separate PostgreSQL administrator credential is mounted only into PostgreSQL.
- API, worker, edge and operations run as UID/GID 10001, with read-only roots and
  explicit writable mounts. PostgreSQL uses its official initialization entrypoint
  and then runs as its `postgres` user. Internal networks isolate the database
  from the edge; app services do not need Internet access for workshop operations.
- The worker currently has no registered business-job handlers. Its health check
  proves configuration/database access only, not background business automation.
- This is a source-built candidate, not a signed release distribution. Dependencies
  use committed lockfiles; base image tags specify versions but are mutable.
  Record image IDs and the source commit. Release image-digest/provenance work is
  separate. Core remains AGPL-3.0-only with no required external SaaS.

## Prerequisites

Docker Engine with Compose v2 is needed. The LAN override uses `!override` and
requires Compose **2.24.4 or later**. The reference commands below use a POSIX shell
on rootful Linux. Docker Desktop on Windows/macOS, rootless Docker and physical
Raspberry Pi execution still require target-specific qualification; Windows ACLs
and bind-mount ownership are not interchangeable with Linux mode bits.

A Raspberry Pi candidate needs a **64-bit OS** and Docker `linux/arm64`, adequate
RAM and reliable storage/power. Hosted ARM64 builds prove image construction only;
they do not prove device performance, SD-card resilience, TLS trust or operation.
Do not run this runtime alongside another stack against the same database volume.

Verify versions before making deployment changes:

```sh
docker version
docker compose version
git rev-parse HEAD
```

Initial builds/pulls need Internet. Once built and installed, the local API, PWA
and PostgreSQL can operate without WAN access. First login and first PWA load need
the server; closing/reopening a browser does not promise indefinite offline login.

## 1. Create secrets once

Use an installation directory **outside the checkout**. The target `secrets`
directory must not already exist, including as a symlink. The helper refuses
existing directories rather than overwriting credentials or rotating a database.

```sh
mkdir -p "$HOME/.local/share/ocwp"
python3 scripts/operations/init_local_secrets.py \
  "$HOME/.local/share/ocwp/secrets" --with-admin
export OCWP_SECRETS_DIR="$HOME/.local/share/ocwp/secrets"
export OCWP_BACKUP_DIR="$HOME/.local/share/ocwp/backups"
mkdir -m 700 "$OCWP_BACKUP_DIR"
```

The helper creates a mode-0700 directory and mode-0600 files:

| File                          | Recipient/purpose                                           |
| ----------------------------- | ----------------------------------------------------------- |
| `postgres_admin_password.txt` | PostgreSQL cluster initialization/administration only       |
| `postgres_password.txt`       | Initialize the restricted `ocwp` database role              |
| `database_url.txt`            | API/migration/worker/operations connection URL              |
| `auth_secret.txt`             | API/worker session-signing configuration                    |
| `admin_password.txt`          | Optional first-admin bootstrap only; never API/worker mount |

The database URL uses `postgresql+psycopg://ocwp:...@postgres:5432/ocwp`.
Hand-authored URL passwords must be percent-encoded, not pasted raw around `@`,
`%`, `/`, `:` or `#`. The helper already encodes its randomly generated password.
Never put password values in command arguments, `.env`, issue reports or Git.
Save the first-admin password in your password manager before changing file
ownership. Read it locally without echoing it into logs or sharing it in chat.

### Linux ownership preparation

Compose file-backed secrets are bind mounts. Its `uid`, `gid` and `mode` fields
**do not remap the permissions** of file sources. A mode-0600 file owned by the
host user is normally unreadable by UID 10001 inside a rootful Linux container.
Keep the files private and deliberately give each file to the container account
that needs it. First verify the official image's actual PostgreSQL IDs:

```sh
docker pull postgres:18.4-trixie
PG_UID=$(docker run --rm --entrypoint id postgres:18.4-trixie -u postgres)
PG_GID=$(docker run --rm --entrypoint id postgres:18.4-trixie -g postgres)
printf 'PostgreSQL uid=%s gid=%s\n' "$PG_UID" "$PG_GID"

sudo chown 10001:10001 \
  "$OCWP_SECRETS_DIR/database_url.txt" \
  "$OCWP_SECRETS_DIR/auth_secret.txt" \
  "$OCWP_SECRETS_DIR/admin_password.txt"
sudo chown "$PG_UID:$PG_GID" \
  "$OCWP_SECRETS_DIR/postgres_password.txt" \
  "$OCWP_SECRETS_DIR/postgres_admin_password.txt"
sudo chown 10001:10001 "$OCWP_BACKUP_DIR"
```

These are explicit host ownership changes; review them before running. Preserve
0700 on the secret parent directory and 0600 on every file. Do not use 0644, 0777
or disabling security controls to work around a permission error. On Docker
Desktop or rootless Docker, verify the platform's actual mapping and ACLs first;
if secret reads fail, stop and fix that mapping instead of making secrets public.
Keep recovery copies encrypted and separately accessible to the operator.

## 2. Build and start

Run from the repository root, retaining the environment variables above:

```sh
docker compose -f infra/compose/docker-compose.local.yml build api edge operations
docker compose -f infra/compose/docker-compose.local.yml up -d
docker compose -f infra/compose/docker-compose.local.yml ps -a
curl --fail http://localhost:8080/health/ready
```

Expected: migration exited with code 0; API, worker, PostgreSQL and edge running.
Readiness is HTTP 200 with `status: ready`, `environment: production`. If migration
fails, API and worker must stay stopped; inspect the error and resolve it without
bypassing the gate. Do not delete a volume to make startup succeed.

To change the localhost port, set `OCWP_HTTP_PORT` (for example, `8088`) before
`up`. Do not change the bind address to expose plaintext HTTP on the LAN.

An optional operations image contains the matching PG18 `pg_dump`/`pg_restore`
plus the locked Python workspace. It never receives a Docker socket and does not
start automatically. The backup destination must exist and be writable by 10001;
Compose refuses to silently create the host bind directory.

## 3. Bootstrap the first administrator

Choose your names as non-secret environment settings, then run the single-use
profile. No default login password exists.

```sh
export OCWP_ORGANIZATION_NAME='My bicycle workshop'
export OCWP_LOCATION_NAME='Main'
export OCWP_ADMIN_USERNAME='admin'
export OCWP_ADMIN_DISPLAY_NAME='Workshop administrator'
docker compose -f infra/compose/docker-compose.local.yml run --rm bootstrap
```

Save the returned organization ID: the login form asks for organization, username
and password. Open `http://localhost:8080` in the same computer's browser. The
bootstrap command refuses to run once any user already exists. Do not run multiple
bootstrap jobs simultaneously. Remove the disposable bootstrap container; after
saving the login password securely, the operator can remove `admin_password.txt`
from the installation because ordinary services do not use it.

`postgres-init/10-application-role.sql` runs only for an **empty volume**. Editing
`postgres_password.txt` later does not rotate the actual database role password.
Rotation needs a coordinated PostgreSQL role-password change plus matching URL
secret, followed by service recreation and successful login/readiness checks.
Auth-secret rotation invalidates existing sessions. Do not regenerate the entire
secret directory or reuse development credentials to repair an existing install.

## 4. Check the actual boundary

```sh
curl -i http://localhost:8080/api/does-not-exist
curl -i http://localhost:8080/assets/missing.js
curl -I http://localhost:8080/sw.js
docker compose -f infra/compose/docker-compose.local.yml port api 8000
docker compose -f infra/compose/docker-compose.local.yml port postgres 5432
```

The API response is a JSON 404, not `index.html`; missing assets are 404. Service
worker, index and manifest use revalidation; hashed assets are immutable. No API
or database host-port mapping should exist. Caddy also returns a backend 502 when
the API is unavailable rather than a successful-looking SPA response.

PWA qualification must separately test: first authenticated online load, offline
customer creation, reload with pending queue retained, reconnect, queue drain and
second-client convergence. Installing a PWA or passing an HTTP smoke alone does
not prove this. Do not clear browser storage as a recovery shortcut.

## 5. Optional trusted HTTPS on the LAN

The supplied LAN override uses a managed **Caddy internal CA**. It is appropriate
only when the operator controls every client and can verify/install the CA trust.
For unmanaged devices prefer a real domain, split DNS and publicly trusted TLS;
that public-ACME provisioning is outside this bounded override.

Before changing origin, sync all pending local mutations from the old localhost
origin. IndexedDB and service workers are origin-specific: a new hostname, scheme
or port does not inherit unsynchronized data. Keep the old origin available until
its queue has been safely reconciled. Each new client must first load and log in
online at the final, stable HTTPS origin.

Choose a stable LAN hostname/IP and bind only the server's intended LAN interface:

```sh
export OCWP_LAN_HOST='workshop.home.arpa'
export OCWP_LAN_BIND_IP='192.168.1.50'
# Local DNS must resolve workshop.home.arpa to this server's actual LAN address.
docker compose -f infra/compose/docker-compose.local.yml \
  -f infra/compose/docker-compose.lan.yml up -d
```

Caddy does not install its CA into any trust store automatically.
The override replaces the localhost HTTP mapping with LAN TCP 443 → container 8443. It does not expose PostgreSQL/API or publish a plaintext LAN listener. The
edge's own HTTP health listener remains internal and bound to container loopback.
Use `OCWP_HTTPS_PORT` only if needed; the client URL must include a nonstandard
port. Do not forward this port from an Internet router.

Export the **public root certificate only**, from the operator-controlled server:

```sh
docker compose -f infra/compose/docker-compose.local.yml \
  -f infra/compose/docker-compose.lan.yml exec -T edge \
  cat /data/caddy/pki/authorities/local/root.crt > ocwp-local-root.crt
openssl x509 -in ocwp-local-root.crt -noout -fingerprint -sha256 -subject
```

Verify the fingerprint against the server over a separate trusted channel before
installing the root in each managed device's OS/browser trust store. Never export
`root.key`, share the Caddy private volume, or tell users to ignore a TLS warning.
Trust-store changes are security-sensitive operator actions, not automatic setup.
Use the platform's documented administration procedure, then confirm the browser
shows a trusted certificate and `window.isSecureContext` is true. Only then test
PWA installation, offline reload and reconnect on that device.

Persist `caddy_data`: deleting it replaces the CA and breaks client trust.
Reusing the installation on a Raspberry Pi requires the same carefully preserved
DNS/origin, credentials, verified database recovery and TLS identity, or an
explicit managed origin/trust migration. Copying only the Git checkout is not a
migration procedure.

## 6. Backup, restore, update and stop

See [database recovery procedure](2026-10-14-backup-restore.md) for the full
safety rules and evidence requirements. A minimal backup operation is:

```sh
docker compose -f infra/compose/docker-compose.local.yml run --rm operations \
  backup /backups/first-generation
docker compose -f infra/compose/docker-compose.local.yml run --rm operations \
  verify /backups/first-generation
```

The bundles contain private workshop data; this alone is not encryption or offsite
protection. `verify` checks integrity/readability; only restoring to a fresh,
isolated target and checking schema/counts constitutes a restore drill. Unsynced
browser data is not in a database dump. Keep at least two verified generations
and encrypted off-host copies. The recovery runbook owns restore-target setup.

Before updates: record source commit/image IDs, reconcile pending device work,
create and verify a backup, and rehearse migrations/recovery on an isolated copy.
Stop API/worker before applying migrations. A successful schema migration cannot
be undone safely just by choosing an older image; use a reviewed forward fix or
proven database recovery procedure. This candidate does not automate upgrades.

Ordinary stop and container recreation preserve database and TLS volumes:

```sh
docker compose -f infra/compose/docker-compose.local.yml stop
docker compose -f infra/compose/docker-compose.local.yml up -d
# Or: docker compose -f infra/compose/docker-compose.local.yml down
# Then: docker compose -f infra/compose/docker-compose.local.yml up -d
```

Use the same Compose project name/files and secret directory on every command;
include the LAN override if it is enabled. **Never add `--volumes` to `down` for an
installation containing data.** Docker volumes and local-only backups are not
sufficient protection against host/storage loss.

## Executable evidence and remaining gates

`python scripts/ci/local_compose_smoke.py --browser` creates a random, disposable
Compose project and random synthetic secrets. It checks the resolved network/port
contract, builds images, starts a fresh PG18 volume, migrates, creates an admin,
refuses repeat bootstrap, logs in and writes a customer. It checks edge routing,
cache policy, browser offline/reload/reconnect/convergence, the backend-outage
response, an isolated PG18 backup/restore, rejection of a nonempty restore target,
and persistence/login across `down`/`up`. It checks logs for generated credentials.
Only its own random project/volumes and temporary test data are removed afterward.
This script is a hosted rootful-Linux test, not a Windows setup wizard.

The workflow uploads `local-runtime-evidence` with commit SHA, architecture,
Docker/Compose versions, image IDs and completed checks. Separate ARM64 build jobs build
all three images for `linux/arm64` without publishing them; the native ARM64
decoder job supplies architecture execution evidence. The optional QEMU decoder
diagnostic is NON-QUALIFYING and is not the native or physical-device gate. Running the smoke
without `--browser` explicitly records that browser evidence is absent.

Still required before operational qualification: green hosted runtime/build jobs
on the final commit, actual laptop/Docker Desktop verification where applicable,
verified LAN trust on every real client, Raspberry Pi hardware/storage/power
qualification, real-volume RPO/RTO measurements, encrypted offsite recovery and
managed password/CA-rotation rehearsals. Existing V0.1 physical-device gates stay
open until their own evidence exists.

References: [Docker Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/),
[Compose service secret permission limitation](https://docs.docker.com/reference/compose-file/services/#secrets),
[Caddy official image](https://hub.docker.com/_/caddy),
[Caddy local HTTPS and trust](https://caddyserver.com/docs/automatic-https#local-https),
[uv locked Docker builds](https://docs.astral.sh/uv/guides/integration/docker/).
