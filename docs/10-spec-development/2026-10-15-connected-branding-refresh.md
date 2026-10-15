# Connected branding: finish the first admitted sync

Date: 2026-10-15. Status: implemented_pending_evidence.
Base local source: `42e1ad34580b7913a8d3c51575aa8a398873ab9a`.
Scope: one source-bound completion request for connected branding admission.
The preceding offline-startup correction remains a separate retained commit.

## Retained aggregate first-attempt failures

[CI38678325955](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38678325955)
ran head `93b9b30e09fa90c9dffc78105b8ef5fbc172852d`, tree
`cb938f964b990d878403ce0ab9a1491f8f7cc270`. Its aggregate finished with **26/27
controls passed, 2375 Python passes / 14 skips, 752 frontend passes**. Browser
results were **60 first-pass cases, two flaky retry passes and one final failure**.
The final offline-reload failure is retained in the
[offline evidence](2026-10-15-offline-branding-refresh.md). The additional flakes
were:

- `late branding response after logout cannot republish an obsolete scope or
session`: first attempt failed at `branding.spec.ts:740`, after fresh login and
  ready state, before releasing the obsolete held response. Expected
  `Nueva sesión y versión actual`, received the OCWP fallback. Retry1 passed.
- `persisted v1 personal palette and local logo survive reads until explicit
workshop inheritance`: first attempt failed at `branding.spec.ts:859`, after
  connected reload and successful personal preference/inheritance actions.
  Expected `Taller con herencia explícita`, received OCWP. Retry1 passed.

These errors show missing current-brand availability. They do not show obsolete
response disclosure or lost v1 records, and passing retries do not erase them.
The direct run had 62 first-pass cases and one final offline-reload failure;
it did not reproduce these two aggregate flakes.

[Aggregate browser artifact11947808664](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/38678325955/artifacts/11947808664)
ZIP SHA-256:
`8b45ab5ac4828037fb48c24dca2dacb980714972943f31a317fd1443d15355ab`.
Repeat phases were skipped. The aggregate result was genuinely pending when the
preceding local offline commit was reviewed; this later evidence caused
publication to be held before adding this connected correction.

## Causal production composition

Connected startup also publishes ready before initial operational reads. Those
reads can fence the first cache read. Unlike offline startup, it then performs a
network branding read and schedules background sync after ready returns. Actual
sync apply/final-page transactions can advance trusted `deviceControl.observedAt`
after the cache write's immutable entry timestamp, including while its logo is
being hashed. The cache correctly returns false; the runtime therefore does not
publish that response. Without a later requested refresh, the ready/synced
workshop can retain a null shared identity.

Advancing-clock production composition reproduced both refused read and refused
write; one observed write entered at NOW+152 before sync advanced control to
NOW+153. A separate deterministic test holds the actual write-side WebCrypto
operation while real sync response/application/final reads finish. Connected
reload then fails the saved-brand assertion even though v1 preferences, explicit
inheritance and operational journal remain intact. Hosted artifacts do not reveal
which writer interleaved in each run; these tests prove the source mechanism.

Simply applying the offline ready-completion request to connected startup would
still race the subsequently scheduled sync. It is not the chosen correction.

## Bounded lifecycle correction

- Record one pending source when connected ready state is published. Initial
  branding still starts normally, so shared display does not wait solely for
  sync completion.
- After the first settled sync publishes its result and finishes operational
  reads, recheck current source identity, consume its pending request, and issue
  one forced refresh using the existing coalescer and fresh kernel/time capture.
- Intermediate `PROGRESSED`, `APPLIED` or `RETRY_LATER` paths do not consume it.
  No settled sync means this completion request has not occurred yet.
- Cancel, offline transition and new admission clear or replace the pending
  source. Recheck after publication because a listener can log out, go offline
  or replace the session synchronously.
- Later periodic/manual syncs and customer/order/issue page reads do not issue
  extra branding requests. They preserve already admitted memory.

The cache implementation, six entry-time rollback regressions, immutable entry
checks, advancing expiry checks, and one-initial/at-most-one-trailing coalescer
are unchanged. No cache-null/write-false retry, new timer, lease extension,
mutation replay or recurring branding poll is introduced. An independently later
writer, or a completion request arriving during an already nonqueueable trailing
flight, may still be conservatively refused. This bounded correction does not
claim universal starvation freedom under arbitrary concurrent work.

## Local proof and boundary

Exact supported Node22.16.0, installed dependencies, real production
controller/kernel/cache over fake IndexedDB and controlled transport:

- **RED: six failures and three passing cancellation controls**, identically
  reproduced in three controlled runs against the offline-only candidate. Four
  failures are availability regressions:
  initial connected login with and without logo, fresh v3 login while an obsolete
  v2 response remains held, and connected reload with v1 personal records plus
  a controlled real logo-write/sync interleaving. The other two prove the missing
  once-per-admission completion after progressed pages and transient failure.
  Advancing-clock-only diagnostic scheduling was insufficient to reproduce
  relogin on every run, so final regressions explicitly gate real transaction
  dispatch/customer-page completion and WebCrypto, without faking results.
- **GREEN: nine focused cases passed** after the connected correction. The four
  availability cases also assert no obsolete v2 publication/cache row, shared
  identity/logo restoration, original personal records until explicit changes,
  preserved journal, and no extra branding requests on later sync/page reads.
- Five lifecycle controls cover real progressed delta pages, an actual transport
  network failure followed by successful sync, and terminal-publication logout,
  offline transition and session replacement. Intermediate work retains the
  one-shot request; obsolete completion cannot add one.
- Full frontend core: **773 passed, zero failures or skips**. Repository
  contracts: **22 passed**. Touched ESLint/Prettier, web/offline typechecks and
  production PWA build passed; the existing large-chunk warning remains.
- Independent isolated candidate review passed **155 cases**: 139 committed
  scope, nine connected lifecycle probes and seven retained adversarial
  queue/security probes. These overlap the core suite and do not add browser
  journeys. The reviewer also independently reproduced exactly six expected
  failures and three passing cancellation controls against the retained
  offline-only source with the final controlled tests. A separate handoff report
  binds the final source and commit before publication.

These results are not native browser execution. The combined offline/connected
candidate still requires fresh exact-head direct and aggregate browser evidence,
retry-free gates and normal integration review. Physical devices, screen readers,
operator installation, real accounts/credentials and deployment remain outside
this correction's evidence.
