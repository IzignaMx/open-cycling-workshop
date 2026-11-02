# M1 · Source-owned module information reference

Date: 2026-11-02. Baseline: `aa43206` (PR81 merged). Status: coordinator and independent builder check accepted. Implementation and qualification
remain separate. This is an ordinary delegated technical choice under Master
Loop v0.2, not a claim that the user selected this particular design.

## Purpose and boundary

Implement the smallest useful M1 official reference described in
[the source-bound modularity strategy](../../08-open-source/2026-10-27-compatible-modules.md).
Operators can inspect what this built-in reference declares: no permissions,
operational data, secrets or network destinations; explicit build-time
composition, AGPL-3.0-only and an online-only declared operational mode. Authors
get an actual typed, source-reviewed host presentation seam without receiving
Core authority. The inspection is public static information, not an operational
module action: it remains readable offline. No network availability signal or
verification request is necessary or introduced.

This is not an installer, discovery mechanism, public SDK, connector, compatibility
certification, sandbox, security boundary or authority grant. It does not complete
R09-T020/R10-T014 or all M1/runtime qualification. Frozen M0 schema/examples and
its `a960bdd` source assessment remain unchanged; no manifest JSON is imported as
executable metadata.

## Alternatives and delegated decision

1. **Native disclosure with typed local metadata (selected):** useful scope
   inspection without permanent workspace clutter; native keyboard/focus behavior
   and a narrow source-owned interface.
2. Always-visible metadata card: fewer interactions, but adds permanent secondary
   content to reception. No additional modularity value.
3. Generic catalog/loader or inventory connector: materially broader authority,
   transport and lifecycle work; rejected for this bounded reference.

## Source shape and composition

- `apps/web/src/features/module-information/reference.ts`: closed readonly type
  and one source-owned descriptor. Stable reference ID, display name, license,
  explicit-build composition, online-only operational declaration and empty
  permission/data/secret/network tuples. These describe only this reference,
  never the whole application or arbitrary future modules.
- `ModuleInformation.tsx`: semantic section, native `details`/`summary` and `dl`
  rendering the declared scope and explicit limitations. No fetch, controller,
  storage, auth, queue, telemetry, imported manifests or mutable module registry.
- `App.tsx`: explicit imports and sibling composition after reception, not a
  wrapper around capture. Opening/closing never changes capture keys, children,
  ownership or handlers. No new runtime/controller/public extension API.
- A nullable source descriptor supports a build that omits this reference; null
  shows a truthful fixed omission message. It is not a user enable/disable switch
  or runtime installation state. Production explicitly supplies the one descriptor.

A localized React error boundary surrounds only the descriptor detail body.
Render failure yields fixed content-free UI copy, with no exception text or explicit
module logging callback. This does not promise suppression of React framework diagnostics. Native disclosure and ordinary capture remain outside the boundary.
There is one immutable source descriptor: a failed body remains failed through
open/close; no automatic retry or identity-based reset is needed. App unmount or
actual build replacement follows ordinary React lifecycle, not a module updater.

## Accessibility and failure semantics

Use existing host classes/tokens and a scoped CSS file (`module-information.css`)
for a 44px summary target, 56px workshop-density target and token-based visible focus, a meaningful heading, native summary disclosure
and term/value relationships. Summary remains available in omission/failure
states. Keyboard activation and focus are native; no automatic focus movement,
modal trap or synthetic loading state. Offline inspection does not imply offline
operations, installation or permission approval. No unavailable-network state is
invented for static data.

## Evidence plan and explicit limitations

TDD begins with real React server rendering, using existing React/ReactDOM and
TypeScript only, to prove the operator-visible declaration and limitation copy.
A missing component import alone is not behavioral RED: a minimal no-feature
baseline must render and fail on expected content. Add exact declaration,
build-omission and HTML-escaping assertions; integrate into the existing core test
runner without altering retained test assertions.

Server rendering does not establish client error-boundary recovery, focus,
keyboard behavior or reconciliation. Native browser coverage separately proves
open/close and error/omission isolation, retained customer/order values and DOM
identity, focus, themes and accessibility. Test-only component harnesses may
inject a throwing child/descriptor; no production debug API or query flag.
No fake asynchronous work or stale-response test is appropriate: there is no
request or external data response. Local browser sandbox restrictions remain
intact; collection/static checks are not native execution evidence.

Normal/offline typechecking, full core tests, build, lint/format and independent
diff review qualify the local candidate. Publication, hosted execution, merge and
deployment are not authorized by this design. Coordinator owns current-state,
plan and qualification reconciliation.
