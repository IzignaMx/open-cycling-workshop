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

Local evidence is component evidence until the final exact tree is qualified.
Observed RED regressions include missing bounded context reads, lease/commit
fences, grouped dependencies, incarnation recovery, installed build provenance,
private response headers, old-fixture preparation and qualified build failure.
Independent source review additionally reproduced and corrected obsolete
implicit recovery dependencies and delta interference with offline/push holds.

The first integrated core runner passed **449 tests** before later review fixes
and acceptance additions; this is not a final-tree count. Separate focused
results overlap and must not be summed. Final aggregate/source review and hosted
results will be recorded against their actual commit/tree.

The seven existing browser specs move from 24 to 26 direct cases using real
login/context/baseline and readonly scoped journal inspection. They retain
customer/order convergence, mixed conflicts, bounded retry, deterministic
commit/ACK barriers, opaque delta rollback, all four themes, focus/drafts,
restricted accounts and accessibility. A separate eighth spec adds actual
old-bundle/service-worker cutover. The former raw-v1 automatic attribution and
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
preservation and late old-tab additions. **Local deterministic builds and unit
checks do not prove that browser journey. Hosted execution remains required.**

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
independent final-source review, native old-SW/reconnect/restore evidence and
existing physical/accessibility/recovery gates remain separate.
