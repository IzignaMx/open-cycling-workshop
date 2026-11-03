# M2 synthetic laboratory — partial local functional increment

> Historical local-functional checkpoint. Later preparation-only work is recorded
> [separately](2026-11-02-m2-hosted-preparation.md); it does not convert the runtime
> gaps below into executed evidence. Original counts and constraints are preserved.

Base/source: `e9c11ad11a564c80add99f4dc901ffe2d583c8e6`.
Status: independently reviewed local functional implementation; runtime gates blocked.
No publication or merge authorized. No production route, runtime flag, human permission, schema migration,
credential, installation or deployment added. Temporary synthetic lab credentials
were created only in controlled local test memory under the separate approval.

## Admission and scope

User approved design at15:48UTC and isolated laboratory implementation/testing,
including temporary synthetic credentials, at16:07UTC. The approved boundary is
an independent prerequisite, not V0.1 completion. See the
[design](../superpowers/specs/2026-11-02-m2-synthetic-laboratory-design.md) and
[implementation plan](../superpowers/plans/2026-11-02-m2-synthetic-laboratory.md).

New code lives under `tests/labs/m2`, outside the production wheel/composition:

- Dedicated opaque machine credentials and separately mapped lab tables. Fresh
  memory fixtures only, no DSN/environment/backup or existing database input.
- Exact installation/organization/location/run/incarnation scope; current grant
  intersection, absolute and suspend-inclusive deadlines, rotation/revoke audit.
- A closed five-field Core product projection through a distinct ASGI app;
  bounded query/body/header, concurrent/request/auth-failure admission.
- One-shot explicit TestClient reader with its own scoped memory SQLite projection,
  no retries/refresh/stale-current access; sanitized verified or failed disposal.
- A read-only preflight that **always reports blocked**, never authorizes a runtime
  merely because tools or caller-supplied booleans exist.

This is **not PostgreSQL** transaction/lock qualification and **not a separate-process**
connector runtime. SQLite's local barrier, ASGI and memory stores are functional
surrogates only. Core product fixtures are synthetic; product names/SKUs are not
intrinsically public or safe for future real-data export.

## Evidence and remaining implementation gates

Behavioral RED/GREEN covers actual scoped SQL/ASGI requests, current-grant reduction,
expiry/rotation/revoke, tenant/location separation, privacy limits and owned-store
failure cleanup. Independent review found and reproduced compatibility/cleanup gaps
in the new lab; the corrected probes and focused102-case run passed independently.
Local verification: **102 laboratory tests**, **5060 full Python passes with671
environment skips and12 warnings**, **151 repository tests**, and **1237 frontend
tests** passed. Full source and laboratory mypy, Ruff, formatting, ESLint,
TypeScript/offline checks, build and API contract checks passed. The final targeted
lab/repository runs also cover the sanitized assertion and documentation updates
made while the full Python run was executing. The final review receipt is retained
with the local candidate; no native/runtime test count is claimed here.

Docker and psql are unavailable in this workspace. A16:34UTC catalog check also
found no visible computers or saved coding environments; no alternate environment
was launched. The following are still missing,
not merely hidden behind a success-labelled mock: a capable freshly owned PostgreSQL18
harness, actual lock/timeout/cleanup evidence, separate non-root connector process,
verified TLS/hostname, enforced network/mount/CPU/memory/PID/volume/transport limits,
run kill/reap and crash teardown receipts. No unconstrained server was launched to
substitute for those controls. Production provisioning, operator grants, installation
identity, durable restore fence and operational retention remain separate decisions.

## Cleanup boundaries

Created credentials exist only in controlled local test memory; server state stores
verifiers rather than plaintext and reports never include credentials. Tests close
owned memory databases/projections, and injected cleanup failures remain failures,
not successful deletion claims. No credential file, CA key, container, TLS endpoint,
network, disk database or volume was created, so none is falsely labelled purged.
Python memory retirement is not secure erasure; actual runtime disposal is unqualified.

## Prior M1 acceptance: supersedes source-pending stamps

PR82 was merged and independently fresh-main accepted at this source. Final receipt
is retained in Library `libfile_d5fa10304a5c81918563d2f2c92eda2f` version2; provenance
is the coordinator's retained receipt, not a new artifact download in this increment.
Fresh-main CI41463493290: **27/27**, direct126/aggregate126 browser cases, all retry0;
5570 Python passes plus58 expected skips,1237 frontend tests, repeats20/9/5/10,
kernel14. Runtime41463493633, security41463493725 and micro41463493203 accepted.
Independent receipt SHA256
`b94c53fc5ea5f544e40f19de32ef05ebed0db509cb288942a3e7ca224f2cb8ac`.
The previous source-pending fields remain historical, not grounds to rerun workflows.
First PR82 failed CI41449605372 and unexplained initial local timing failure remain
history; no claim that failure never happened or its cause was resolved.

## Traceability and non-claims

M2 contributes a partial prerequisite to FR-PLG-003, FR-PLG-004, FR-PLG-005, FR-PLG-008 and FR-PLG-009 and
SEC-002/003/005/006/007/010. FR-PLG-007 interfaces are a design consideration, not
implemented hooks. R09-T020/R10-T014 stay incomplete; no SDK/loader/registry claim.
Existing M1 traceability remains unchanged rather than being overwritten by local
unqualified M2 evidence.

R01-T035/T1–T8 and full recovery/capacity/installation gates remain pending.
SPENT40927223929 cannot be repeated; historical cleanup41011497919 remains UNKNOWN.
Pages is unchanged. No advance to V0.2 or whole-project completion is declared.
