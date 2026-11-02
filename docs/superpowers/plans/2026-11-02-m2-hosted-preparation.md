# M2 Hosted Laboratory Preparation Plan

> For agentic workers: execute the approved preparation only, with TDD and independent security review. No workflow publication or execution is authorized.

**Goal:** Prepare an exact-source bounded hosted harness to replace unqualified local surrogates with future PostgreSQL/TLS/process evidence.
**Base:** local19-file checkpoint e4c5a2b8385dbcdfb71aabeac5351aeccb1e08f5; normal main e9c11ad remains untouched.
**Authority:** user18:51UTC approves preparation only; next approval must name candidate and execution/storage/permission bounds.
**Spec:** prior M2 design plus reviewed network-none/UDS refinement retained in artifacts/m2-lab/NEXT-EXECUTION-OPTION.md.

## Fixed interfaces and constraints

Three future containers: database network-none; trusted API shares only database namespace; connector has its own network-none namespace. Connector mounts only exact API socket directory read-only, public CA read-only, machine delivery directory read-only and its own16MiB tmpfs. No Core/DB/Docker socket mount, host port, host network, privileged mode, added capability, host firewall change or real data. API/connector UID:GID equals nonroot runner UID:GID, removing host chown/root helper requirements. PostgreSQL runs its image postgres user; its password-file readable only through an exact file bind from a0700 host-owned directory.

Fixed paths: `/run/m2-api/catalogue.sock`; APIprivate `/run/m2-private/{run.json,pg-password}`; dedicated TLS `/run/m2-tls/{api.crt,api.key}`; public `/run/m2-public/ca.crt`; machine delivery `/run/m2-credential/{credential,scope.json,api-status.json}`; connector store `/run/m2-store/projection.sqlite`. Socket directory0700/socket0600, same nonroot UID; no extra sockets/symlinks. Manifest exactschema1+nonce32lowerhex+source_commit40hex+source_tree40hex; derive fresh DBm2_nonce and require server cluster_name equality before create. No arbitraryDSN.

TLS fixedhostname `ocwp-m2-api`; private CA/leaf keys generated only in a future explicitly approved run, never now. No secrets in command arguments/environment values/logs/artifacts. Closed ASGI lab app, no generalproxy/admin HTTP. Transport:2handlers/noqueue/backlog8; handshake/header/send2seconds each,8seconds total; headers8192/query1024/body0/response65536;120connection attempts/run,20authfailures and120apprequests. Invalid TLS/parser closes onlythatconnection; clock/uncancelledtimeout poisonsrun. Credentials/run max900seconds; five-second graceful interval then hardkill/reap.

Future job max30minutes: checkout1, preparation9, runtime15, independentcleanup2, evidencevalidation1, boundedupload1 and reserve1. Public standard Ubuntu only; contentsread, no stored repository secrets, no cache/paid/largerunner/budget changes. Evidence fixed sanitizedJSON <=1MiB and retention1day. All resource identities declared before create, immutableIDs/nonce/exactimage/source validated before cleanup; uncertainoutcomes reconciled narrowly or fail, never globalprune.

## Tasks

- [x] Authority: RED manifest/version/cluster/ownership/budget tests; protected enginehook preserves existingSQLite; freshPGonly runtimeconstructor and authored actualPGprobes. GREENunits/types, noPGconnectnow.
- [x] Transport/client: RED strictframing/filemetadata/closedDTO tests; bounded TLSUDSadapter +fixedhost client and ownedstore entrypoints, no socket/key/network invocation now. GREEN pureunits; actualTLS remainsunqualified.
- [x] Controller: RED containment/ownership/uncertaincleanup/evidencebudget tests; compose fixedDockercommands and strictownedmanifest, bounded existing subprocess runner, independent cleanupreceipt. No Docker callnow.
- [x] Workflow: RED staticpermission/source/timeout/artifactgates; prepare PR-only/optionaldispatch job without publication/execution.
- [ ] Independent security review, scoped corrective RED/GREEN, full local regressions/static/contracts, exactsourcehash and sanitized Librarybackup.

## Stop and consent boundary

Do not create runtime PG passwords/TLS keys, bind listeners, launch containers, publish/dispatch workflow, change hostsecurity or access production during preparation. Existing approved ephemeral memorylabtests remain allowed. Missing environment/native evidence stays unqualified. Report exact candidate filecount/hash and next proposed bounded run authority, not fullM2 completion.
