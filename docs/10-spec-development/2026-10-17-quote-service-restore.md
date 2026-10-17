# One-case PostgreSQL service-effect restore qualification

Status: prepared; exact implementation review, image preparation and execution
pending. The [three migration integrity cases](2026-10-17-quote-migration-integrity.md#verified-result)
passed independently. They did not prove logical backup restoration.

## Acceptance

Select exactly one synthetic case with three ordered setup/call/teardown phases.
Use the existing disposable source/target database fixture and real backup tools.
The source is PostgreSQL 18.4, revision 0013, with one quote creation and one
valid version-1 order transition produced through the actual private service.
Use real write admission and synthetic tokens. Preserve complete retained rows,
raw JSON bytes, generated counts, financial proofs, effect IDs and outbox metadata.

Close source sessions before dumping. Keep the target empty and unopened until
the restore tool's preflight. Perform one real custom dump and single-transaction
restore, then prove the target's live STORED definitions and exact row equality.
No utility result is relabelled as application qualification: its existing
application_smoke_tested/restore_tested fields retain their meanings.

Explicitly rotate only the restored target's incarnation. Require an old token
to fail with invalid_session, then use a fresh token to replay both original
operation IDs with new commands disabled. Require original receipts/effect IDs,
current authorized order state and unchanged row/effect counts. Fresh sessions
are used for service calls; no replay should silently write a replacement effect.

The final-only observer probes actual source and target identities after the
test body. It must not pre-open the target or intercept migration, backup,
restore or cutover functions. Require the exact owned database pair, public
schema, UTF8, PostgreSQL 18.4, psycopg 3.3.4, revision 0013, and closed probes.
Failure, missing identity or skipped client checks remain nonqualifying.

## Client preparation and diagnostics

Retain the existing Python 3.13.14 slim-trixie proof base. Inside this disposable
image only, configure the official scoped PostgreSQL signing key and historical
trixie-pgdg-archive repository. Verify its full fingerprint and install exact
postgresql-client-18 and libpq5 version 18.4-1.pgdg13+1 through signed apt metadata.
Do not float versions, disable signature checks or install host packages.

Verify package versions, actual pg_dump/pg_restore release 18.4 and dynamic-link
resolution. Fixed symlinks make those clients visible through the existing
sanitized PATH. The contained case retains bounded actual client identities.
Installation and duration remain unmeasured until the hosted run. An unavailable
historical package stops preparation rather than changing the accepted input.

Keep a bounded public build/pull log for each of the three ordinary preparation
commands. The established helper's 16 KiB file limit applies; report when a log
reaches that cap instead of presenting it as complete. These commands process
public source and official packages, without secrets or real workshop fixtures.
No raw database dump or synthetic token is uploaded. Backup subprocess stderr
remains suppressed by the existing product helper, so an underlying backup-tool
failure may have limited diagnostics.

## Limits and publication effects

The distinct workflow runs only on the fixed codex/quote-service-restore branch,
run number 1 and attempt 1. Publishing that branch launches this single case;
it does not open a PR or change main. All earlier consumed workflows remain
unchanged. A skipped or failed first run stops for diagnosis, without a rename,
counter change or blind retry.

Retain the existing aggregate 20-second workload, worker 1 CPU / 512 MiB / 64 PIDs,
database 1 CPU / 768 MiB / 128 PIDs, read-only roots, worker /tmp 64 MiB,
database data 256 MiB and socket 16 MiB tmpfs. The two client processes run inside
the existing worker cgroup. Real cancellation canary, stop/reap and independent
cleanup remain required. Ordinary image preparation is separately bounded by
the existing 12-minute step and 20-minute job. There is no third execution venue.

The backup helper's own timeouts are longer than this workload. The external
aggregate guard is the tested ceiling for the case and descendants; this change
does not claim to shorten production backup timeouts. Hard cancellation may
prevent fixture teardown, so owned ephemeral-container destruction and verified
absence remain essential. No caller database or durable workshop volume is used.

## Remaining scope

This case can establish only tiny synthetic logical restore of generated
metadata and valid version-1 effect replay. Production-size restore/rewrite,
concurrent writers, rollback after restore failure, external assets, browser
queues, HTTP exposure, worker delivery, capacity, physical hardware and actual
installation remain separately gated. Existing failed capacity/profile runs and
the unknown historical restart cause remain preserved. The remaining pure and
guard regressions also need their own execution evidence.

References: [PGDG archive](https://apt-archive.postgresql.org/),
[official Debian key/repository instructions](https://www.postgresql.org/download/linux/debian/),
[PostgreSQL 18 package pool](https://apt.postgresql.org/pub/repos/apt/pool/main/p/postgresql-18/),
and the [bounded full-integrity amendment](../02-technical-architecture/2026-10-17-bounded-quote-order-effects.md).
