# M2 hosted laboratory: prepared source, not runtime acceptance

## Authority and admission

The 18:51 UTC authorization permits local preparation of the isolated harness and
workflow only. It does not permit publication, workflow execution, deployment,
production access, host firewall changes or additional human permissions. The
16:07 synthetic-memory laboratory approval remains the authority for local tests.
The earlier 19-file local checkpoint `e4c5a2b` is preserved; main `e9c11ad` is not
changed by this work. This remains an independent modularity prerequisite while
V0.1 physical acceptance is pending, not admission to V0.2 or full M2 completion.

## Prepared topology

- Fresh PostgreSQL 18.4 container, network `none`, non-root image user; no published
  port. A trusted, test-only API shares exactly that owned network namespace.
- A distinct non-root connector container has its own `none` network namespace.
  Only the exact TLS-wrapped Unix API socket, public CA and synthetic credential
  delivery directory are bound read-only. No database, Core or Docker socket is
  mounted. The API is a closed application, not a general network proxy.
- The connector checks actual UID, capabilities, no-new-privileges, interfaces,
  cgroups and tmpfs bounds before fixed negative connection probes. Its namespace
  must differ from the API/database namespace. These are authored checks, not
  observed operating-system evidence in this environment.
- Credentials retain the approved absolute 15-minute maximum, one-location scope,
  read-only projection, per-request current grants, no automatic retry, rotation
  without overlap and restart invalidation. A private CA and ephemeral leaf keys
  are generated only inside a future approved run. No secret is committed,
  supplied through command-line values or uploaded as evidence.
- The fixed PostgreSQL endpoint/cluster identity precedes database creation.
  Actual-session row-lock, statement/transaction timeout and read/revoke orderings
  are prepared rather than replaced with a local mutex or caller-supplied success.

No normal route, production schema, service entrypoint, dependency lock or human
authorization model is changed. Runtime helpers live in the test-only package.

## Proposed future execution bounds — not yet authorized

The workflow would run on a same-repository PR in a public repository; publishing
that PR is therefore also an execution request, not an inert upload. Fork PRs and
`pull_request_target` are excluded. A separate manual trigger is restricted to
main. The next approval must explicitly cover publication and this bounded run.

One standard Ubuntu job, `contents: read`, no stored repository secrets, no cache,
no larger/paid runner or budget change: 30 minutes maximum. Step maxima are
checkout 1, preparation 9, runtime 15, independent cleanup 2, evidence validation 1
and upload 1 minute, leaving one minute reserve. Runtime has an outer 880-second
TERM deadline and ten-second kill grace. Its internal workload budget is 760
seconds, followed by at most 90 seconds of cleanup, leaving 30 seconds reserve.
The independent cleanup step has a 90-second internal budget inside its
110-second outer deadline. Hard runner termination can prevent an
`always()` step: missing cleanup evidence is failure/unknown, never verified purge.

Container memory/CPU/PIDs: database 768 MiB/1/128; API 512 MiB/1/64; connector
128 MiB/0.5/32. Read-only roots, all capabilities dropped, no-new-privileges,
private cgroup/IPC namespaces and no container log persistence. Each `/tmp` is
64 MiB; database data/socket tmpfs are 256/16 MiB; connector store is 16 MiB.
Host-side private files use a fresh owner-only directory in `/dev/shm`.

Only two closed-schema JSON receipts may be uploaded, combined at most 1 MiB,
retained one day. Final immutable images must total at most 4 GiB and preparation
requires at least 4 GiB free disk. These are admission checks, **not a hard quota
on peak build/pull disk usage**: layers, unpacking, cache and existing runner use
share the standard ephemeral runner's capacity. No Docker daemon or host storage
policy is changed. Artifact allowance has not been inspected; no unconditional
zero-cost guarantee or permission to increase a budget is implied.

## Cleanup and evidence semantics

Ownership manifests bind the nonce, exact source commit/tree, immutable image,
predeclared container names, full container IDs and original directory identities.
Uncertain creation is reconciled only at that exact name and identity. Unknown
resources are not removed; there is no global prune or broad recursive deletion.

The API's `database_cleanup_complete` proves only its owned database disposal.
A separate supervisor must verify all owned containers absent and remove the
exact owned credential, key, socket and fixture paths. Missing ownership,
substituted inodes, unexpected files, symlinks and incomplete cleanup fail closed.
Process-memory retirement or file unlinking is not secure erasure; runner-loss
cleanup and complete equipment-crash recovery are not promised.

## Qualification status

No live runtime was invoked locally: no PostgreSQL connection, TLS key/password
generation, listener, Docker container or GitHub run. Fake-executor tests exercise
the supervisor using fixed public file fixtures, not usable credentials or keys. Local
functional, parser, file-metadata, source-contract and fake-controller tests cannot
qualify actual PostgreSQL, TLS, OS isolation, kill/reap or disposal. The final
local test and independent review receipt will accompany the frozen candidate.

R09-T020/R10-T014 and full SDK remain incomplete. R01-T035/T1–T8 physical and
capacity/recovery/install gates remain pending. Ownership run40927223929 remains
**SPENT**, cleanup41011497919 remains historical **UNKNOWN**, Pages is unchanged.
