# Authenticated workshop client C: scope and qualification

## Source scope

C starts from integrated server B `14f4bf005f2b28ded5d31c45c9c532d50597aefc`
(tree `eb8f2575d06109916b38d6f3d579899d795cd943`). The
[accepted architecture](../02-technical-architecture/2026-10-14-authenticated-workshop-client.md)
combines the existing customer/bicycle/order vertical slice with genuine
session/context admission and a concrete workshop selector. It does not add an
administration UI, inventory/quote workflows or shared branding.

Production composition now uses `ocwp-authenticated-v1`; its additive schema 6
adds bounded journal/delivery/event lookup indices. Existing v1–v5 history is
unchanged. **Unimplemented quote-local persistence now reserves v7**. Older v6
reservation notes describe historical increments, not a migration to rewrite.

The old `ocwp` database remains raw, readonly and versionless from the new
composition. An absent old database is not created. Original unknown fields,
pending work and late old-tab additions remain evidence; none becomes a new
user's command. Safe preference copying requires exact organization/user
ownership, with organization/user/location additionally required for logos.

## Admission and transport

- Login, user, locations, context, baseline, ongoing deltas, push and timeline
  responses have bounded reads and captured credentials/identity.
- Durable offline admission is tied to the exact stored session binding and
  completed baseline. Reload and reconnect use owner compare-and-swap; clocks,
  lease expiry, idle visibility and takeover are checked again before display.
- Immutable authored commands include dataset incarnation. Recovery-held work
  remains preserved and excluded from overlays/replay; a new confirmed baseline
  can support independent newly authored commands.
- Deltas preserve initial completion evidence and the latest exact durable
  continuation chain. They never manufacture online authority from offline
  admission or clear another coordinator's hold. Transient delta backoff owns
  only its metadata and preserves any concurrent captured push owner.
- Server mutation and order-timeline responses are explicitly no-store,
  including authentication/permission/error responses. The production client
  does not relax its strict private-response requirement.

## Acceptance evidence and limits

Local source qualification is complete for the recorded checkpoint below; hosted
runtime qualification remains pending.
Observed RED regressions include missing bounded context reads, lease/commit
fences, grouped dependencies, incarnation recovery, installed build provenance,
private response headers, old-fixture preparation and qualified build failure.
Independent source review additionally reproduced and corrected obsolete
implicit recovery dependencies, delta interference with offline/push holds,
hidden recovery issues beyond the first history page, offline in-flight network
races, premature synchronized status during retry backoff, and shared browser
fixture principals exhausting the unchanged server family quota.

The fresh aggregate at source checkpoint
`23c628fd76fc4adb966851eed344954379876f51` (tree
`4705573327371506635402c2a2e70651fad1b41a`) passed **21 checks, zero failures**:
**1,581 Python tests**, **473 frontend tests**, one API-client test, repository
and API contracts, offline/API types, Python and frontend static checks, the
current production PWA and two reproducible actual historical builds. Python
reported **189 explicit local PostgreSQL-dependent skips**. Five environmental
blockers remain: PostgreSQL test URL, Docker, psql, managed Chromium navigation
policy and browser E2E database URL. The earlier 3e12de7 aggregate also contains
21 passing checks; a previously reported count of 22 was a counting error.

Independent component reviews closed all concrete findings. Kernel/delta fixes
are integrated in `b374dca`, `17c1875`, `23b362b` and `cfd2d62`; runtime issue and
network fencing fixes in `f106b45` and `5d64b37`; fixture identity, native schema
and restore corrections in `6bb191e`, `772e26a` and `6c2dc5b`. The acceptance-only
23c628f delta was independently reviewed with seven Python fixture tests and
strict E2E typing/static checks passing. A subsequent explicit missing-journal
assertion in `467fd84` removes its newly introduced optional-index typing
observation without relaxing preservation assertions. Separate focused results
overlap and must not be summed with the aggregate.

The attempted final documentation-head aggregate was interrupted and produced
no completed artifact. Its SHA must not be substituted for the source checkpoint
above; the source checkpoint remains the recorded local aggregate evidence. Hosted CI and
actual screenshot inspection must be tied to the published candidate tree.
Configured types pass; an exploratory E2E compile with both optional/index
strictness flags exposes pre-existing test diagnostics, so it is not claimed
as a green configured gate.

The seven existing browser specs move from 24 to 26 direct cases using real
login/context/baseline and readonly scoped journal inspection. They retain
customer/order convergence, mixed conflicts, bounded retry, deterministic
commit/ACK barriers, opaque delta rollback, all four themes, focus/drafts,
restricted accounts and accessibility. A separate eighth spec adds actual
old-bundle/service-worker cutover and genuine recovery visibility. All **27 cases
in eight files** collect; collection is not execution. The isolated native
IndexedDB harness has **11 collected cases**, including additive v5→v6 evidence. The former raw-v1 automatic attribution and
replay assertion is deliberately superseded by exact preservation/non-replay;
known-author unchanged-ID reload and lost-ACK replay remain required.

### Exact old App/SW fixture

`fixtures/legacy-client/manifest.json` pins pre-cutover source
`714342c60f4163c7b4c1ebec8433995dccbeea01`, exact tree and lock. The builder checks
all archived tracked source before/after building, resolves workspace packages
to the archive, validates the installed dependency lock (only the explicitly
recorded test-only fake-indexeddb omission is permitted), checks tool versions,
forces production environment, and records every asset hash. Two actual local
builds produced seven identical assets, including generated SW/Workbox. Local
Node 24.19.0 is within the archived supported range; hosted qualification uses
the preferred Node 22.16.0 and frozen pnpm 11.17.0 installation.

The browser fixture uses a separate disposable floor-zero tenant. A valid
signed legacy token is issued with the exact pinned pre-B codec: current B
login already includes incarnation even at floor zero and must not be mislabeled
as a legacy token. The required journey proves legacy-session 401, fresh-login
old-transport 409, actual old SW offline reload, new SW takeover, raw old-work
preservation and late old-tab additions. It also creates fresh pending work
through the normal offline UI, rotates this fixed synthetic tenant through the
supported recovery operation, signs in again and verifies preserved held work
with no obsolete overlay. Eight actual recovery-UI captures are required across
Banco/Plano/Ritmo/Noche at 1440px and 320px; selector/session-held captures and
existing draft/focus, axe and reflow assertions remain. Captures are generated
only when those real journeys execute, then require visual inspection.
**Local deterministic builds and unit checks do not prove that browser journey.
Hosted execution and pixel inspection remain required.**

### Runtime restore

The generated disposable Docker fixture alone opts into floor1. Its restore
journey must keep a live browser pending journal and a backed-up checkpoint,
stop writers, restore an empty isolated target, rotate its expected incarnation
before reopening API, then prove stale session/checkpoint refusal and preserved
recovery holds before independent new work. All eleven original runtime checks
remain substantive. Docker/native execution is unavailable in this local
execution environment; no physical Windows/Android/ARM64 hardware qualification
or actual installation activation is claimed.

## Release and operator gates

Normal Compose opt-in remains disabled. Source publication is not permission to
activate an installation, configure credentials, discard browser storage or
restore over existing data. Follow the
[server cutover procedure](../07-operations/2026-10-14-server-cutover.md) and the
[current checklist](../../MANUAL-ACTIONS-CHECKLIST.md). Exact-head hosted CI,
native old-SW/reconnect/restore evidence, actual screenshot inspection and
existing physical/accessibility/recovery gates remain separate. Independent
source review is closed; it does not substitute for those runtime gates.

## First hosted candidate and reviewed corrections

PR38 published head `b9da73fa7c764b7a3592688db7199e77457e44a0`
(tree `0b5bd4e399dd577b879f2f2a8c7bf524f54cccc6`) reached genuine
floor1 Docker/browser execution. Runtime run
[38611518026](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38611518026)
failed during `offline_create_reload` after **six of eleven checks**. Its
artifact `11918391432` was downloaded and ZIP SHA-256 verified as
`1bf787bdb0c065cd9cb48d96abff1c851599180c57f73d34487f851a6cbf9673`.
All three ARM64 cross-builds passed, but restore and the remaining runtime
checks were not reached. No physical ARM runtime evidence is implied.

The safe failure envelope did not identify the individual offline assertion.
The reviewed diagnostic correction adds fourteen fixed, content-free subphase
labels; removing only label assignments leaves the browser script byte-identical.
Every assertion, timeout, operation order and redaction rule is preserved. This
is improved diagnosis, not a claimed fix of the underlying offline failure.

A separate real floor1 route probe demonstrated that captured logout-all omitted
its required write-protocol header: HTTP409, unchanged session version1, and the
old token still valid. The minimal correction sends protocol1 and independently
proves HTTP204, session version2 and old-token HTTP401 through the compiled
production transport and actual FastAPI routes with synthetic SQLite data.
This is route evidence, not PostgreSQL concurrency or browser evidence.

Both corrections are independently reviewed and integrated at local
`501bb689db21aa8828f72ee1e7477e7f3909376c` (tree
`f1afe1b859ae144dc245f6c687f222f31de4f68e`). Focused combined checks passed
477 frontend core tests, 23 runtime Python tests, web/offline types, touched
ESLint/Prettier and whitespace checks. These overlap earlier suites and are not
an additional complete aggregate. Exact corrected-head hosted qualification,
underlying offline diagnosis and actual screenshot inspection remain required.

The first Security workflow's green conclusion did not establish scan coverage:
Gitleaks logged a Git ownership error and zero scanned commits/bytes; pip-audit
was not explicitly supplied the project graph. This coverage defect is tracked
in the separate security-scan correction; no green badge substitutes for actual
history and locked-dependency coverage evidence.
