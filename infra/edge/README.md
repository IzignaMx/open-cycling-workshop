# Inventory query privacy

Both supported Caddyfiles filter only `request>uri` at encoding time in the
**default runtime logger**. Upstream failures emit this field even with HTTP
access logging disabled. The filter retains the path, method, status and other
operational error fields, and leaves unrelated URI queries unchanged. It does
not rewrite forwarded requests or enable HTTP access logging.

The anchored expression matches `/api/v1/inventory` and descendants, including
single-percent-encoded spellings that the backend decodes to that namespace.
It excludes similarly prefixed paths such as `/api/v1/inventory-other`. Keep the
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
