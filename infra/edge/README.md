# Inventory query privacy

Both supported Caddyfiles filter only `request>uri` at encoding time in the
**default runtime logger**. Upstream failures emit this field even with HTTP
access logging disabled. The filter retains the path, method, status and other
operational error fields, and leaves unrelated URI queries unchanged. It does
not rewrite forwarded requests or enable HTTP access logging.

The anchored expression matches `/api/v1/inventory` and descendants, including
single-percent-encoded spellings that the backend decodes to that namespace.
Origin-form and HTTP absolute-form targets are covered. It excludes similarly prefixed paths such as `/api/v1/inventory-other`. Keep the
two configurations identical. Their contract test covers each prefix character
encoded with both hexadecimal cases and the encoded child-path separator.

Syntax and semantics were checked against the official
[Caddy global log option](https://caddyserver.com/docs/caddyfile/options#log),
[filter encoder](https://caddyserver.com/docs/caddyfile/directives/log#filter),
[2.11.7 regexp implementation](https://github.com/caddyserver/caddy/blob/v2.11.7/modules/logging/filters.go)
and [original-request capture](https://github.com/caddyserver/caddy/blob/v2.11.7/modules/caddyhttp/server.go).

Source tests are **not actual Caddy runtime qualification**. Before qualifying
this increment, run both supported configs with Caddy 2.11.7, prove normal
upstream query forwarding, then make the upstream unavailable. Capture the
resulting runtime/error logs and assert that synthetic inventory query canaries
are absent, similarly prefixed unrelated query canaries remain, and errors
retain method/path/status. Qualify LAN mode with its isolated internal CA;
never disable TLS verification or install a test CA into the system trust store.

The application has separate real-Uvicorn canary tests, using a disposable
SQLite fixture and synthetic identities. They exercise 200/401/403/404/422/500/
503, malformed/unknown/duplicate/oversized movement queries, generated request
IDs, safe error diagnostics and unchanged ASGI query bytes. Run them with:

```sh
python -m pytest services/platform/tests/inventory/test_inventory_http_privacy.py \
  services/platform/tests/inventory/test_inventory_logging.py \
  tests/operations/test_inventory_edge_logging.py
```

The probe application's synthetic routes exist only in the test module and are
not installed by the production application.

## Actual runtime proof

Run `python scripts/ci/inventory_edge_probe.py` on a Docker-capable, nonroot Linux
host. It builds the existing `infra/docker/web.Dockerfile` using its allowlisted
context and a unique disposable image tag (600-second quiet build budget), then
uses the immutable production image ID and both actual configurations, an isolated
localhost internal CA verified through an explicit trust context, and synthetic
upstream requests. Successful normal forwarding precedes actual upstream failure.
Only `http.log.error` ERROR records qualify; access-only logs cannot substitute.
The runner refuses failed cleanup and initializes a fresh incomplete artifact
before Docker discovery/pull, so a blocked rerun cannot retain old success.
Only `artifacts/inventory-read/edge-runtime-evidence.json` is publishable. Temporary
raw logs and CA material are never uploaded or installed as system trust.

Current local source tests and mocked adversarial checks pass. Actual execution
is blocked here because Docker is unavailable; CI must execute both modes before
this increment is qualified.

On failure the runner retains bounded safe diagnostics before removing the
container: fixed phase, last health status/error category, container status/exit/
OOM fields and separate upstream/container/directory cleanup outcomes. Startup
log hints are fixed categories collected only before private synthetic queries.
Combined command output is capped at 64 KiB while reading; timeout/output overflow
kills and reaps the command. Raw log/exception/request/environment text is not
published. Diagnostic hints do not establish a root cause by themselves, and a
failure or incomplete cleanup still exits nonzero. The readiness limit stays
30 seconds; no diagnostic retry relaxes forwarding, TLS or privacy requirements.

Before private requests, paired raw-upstream/production controls run the identical
explicit binary SHA256/getcap/version command and sandbox flags. Equal binary
hashes, expected raw file capability plus nonzero EPERM/no version, and absent
production capability plus zero/v2.11.7/no EPERM are required; contradictory or
unknown metadata fails closed. Both image IDs and only validated metadata are
recorded. The host UID/GID override exists solely for disposable bind-directory
ownership; read-only root, cap-drop ALL and no-new-privileges stay unchanged.
Build/controls occur before each original 30-second configuration readiness gate.
The unique tag is removed after use without pruning shared Docker cache; cleanup
failure remains separate and prevents success. The first two hosted readiness
failures are retained. Their launch-mismatch cause remains a hypothesis until an
actual paired hosted result establishes it; mocked tests cannot establish it.
