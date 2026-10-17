# Finite PostgreSQL 0012 quote-service qualification

## Verified starting point

[Static run 39052034132](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39052034132)
on `559f9f311fe6c4aedf303063df5e697a461c64a7`, tree
`e0505482124317ec8190cd7f0a3985543b30ebc2`, passed repository verification,
Ruff lint/format, strict mypy and OpenAPI/generated-client freshness: six exact
nodes and all 18 ordered reports. Artifact `12108166920` has SHA-256
`7857f1ae69d799ab9eb92687498f8d4a6e452d46386abbc5537675808252834c`.
Workload wall time was 10.169 seconds within the shared 20-second limit.

The preceding OpenAPI three-second subtimeout remains retained. OpenAPI took
2.486 seconds in the successful run; that does not establish why the earlier
execution exceeded three seconds or prove that the allowance change caused
success. These static results do not qualify database transactions or capacity.
Earlier quote-service passes used SQLite and remain scoped to their own sources.

## Selected next workload

Use the existing contained mechanism for exactly six tests:

1. Existing complete command-response DTO round trip.
2. Existing nested-bypass and actual UTF-8 response-byte validation.
3. Existing create/decide/replay complete atomic tuple, on PostgreSQL.
4. Existing response-failure rollback of decision effects, on PostgreSQL.
5. Existing expired-deadline refusal before writer/effects, on PostgreSQL.
6. Existing historical quote-only replay without an invented transition, on
   PostgreSQL.

A small PostgreSQL bridge explicitly imports only those four database test
bodies and their fixtures. It leaves the original SQLite module and fixtures
unchanged. The two pure DTO tests are not placed under an indirect database mark.
The four database fixtures run sequentially in separate synthetic schemas using
the existing test-database safety checks and migrations through revision 0012.
This does not copy or apply the separately prepared schema-0013 amendment.

## Identity and containment evidence

After each fixture's migration and before service sessions, a separate probe
connection verifies PostgreSQL/psycopg, the actual driver connection, the fixed
owned test database, PostgreSQL 18.4, UTF-8 server/client encodings, current
isolated schema/search path and exact Alembic revision 0012. The probe closes
before the test body. The existing report hook carries one closed identity
record per PostgreSQL node; final readback requires four distinct schemas and
rejects missing, duplicate or inconsistent evidence. Do not retain DSNs, secret
values, SQL payloads or workshop data in identity records.

The cleared test-process environment receives only the already-owned synthetic
loopback database URL. It must not inherit an arbitrary caller URL or access an
external database. The server remains inside the existing disposable network
namespace; no account or persistent credential is created outside that fixture.

Keep the shared 20-second workload limit, one-CPU/512-MiB worker and
one-CPU/768-MiB PostgreSQL container, swap/PID/capability restrictions, actual
descendant-cancellation canary, source/image checks, bounded output, stop/reap
ordering and independent cleanup. Preparation and cleanup retain their existing
separate limits. Do not retry or raise bounds if the finite workload fails.

## Acceptance and limits

Require exactly the selected six tests and 18 successful ordered phases, zero
errors/skips, exact source identities, four actual PostgreSQL identity records,
resource evidence and both absence receipts. Preserve any first failure and
unrun scope. The expired-deadline case deliberately refuses before the service
writer; its PostgreSQL fixture does not make it a transaction-effect proof.
The unchanged response-failure case checks the normalized error, retained counts
and order state, but has no explicit callback-reached sentinel. Preserve that
coverage limitation when describing a pass.

This is a small sequential PostgreSQL-0012 service qualification. It does not
prove lock contention, concurrency, real network acknowledgement loss, schema
0013, migration of populated new effect tuples, backup/restore, maximum capacity,
production deadlines, quote API/UI exposure or installation. Those remain
explicit later gates. Independent source review and actual execution are pending;
no candidate imports, collection or tests ran on the authoring host.
