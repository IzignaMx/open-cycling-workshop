# Secure bootstrap boundary · 2026-11-20

## Scope and requirement

Security Phase 3 §10 requires TLS outside localhost. The Windows/Android
[preflight](../11-device-qualification/2026-11-19-windows-android-preflight.md)
requires an authorized trusted origin before a physical trial.

The current App now requires `window.isSecureContext === true` before reading
`sessionStorage`, constructing `WorkshopController` or mounting the login App.
The browser, not a hostname/URL heuristic, decides secure-context eligibility.
Loopback remains supported when the browser classifies it as secure.

An inaccessible `sessionStorage` getter separately blocks bootstrap with an
accessible Spanish explanation. No writes, clearing, recovery or persistence
probe is attempted. Constructor/render exceptions are not relabeled as storage
failures. Neither path displays exception details, login controls or a retry that
could change origin. The notice warns against ignoring certificate warnings or
clearing data and explains that changing origin does not transfer drafts.

This boundary does not qualify the configured API endpoint, IndexedDB access,
storage capacity, browser permissions, hardware or LAN security. HTML/assets and
the existing PWA registration machinery are outside the runtime/API prohibition.
It is not a network firewall, migration or exclusion mechanism for older clients.

## Evidence and limits

- Unit regression observed RED against unconditional startup, then GREEN against
  the boundary. Controls include non-true values, getter failure, strict ordering,
  unchanged storage identity, no probing, exception separation and preservation.
- Two authored direct browser cases: actual insecure HTTP reserved `.invalid`
  document fulfilled with the current local preview assets (no external network
  forwarding or security flags), and secure loopback with a throwing storage
  getter. Both require a visible accessible notice, no login and zero API calls.
- Native execution is pending hosted CI. No browser was launched locally. The
  storage getter denial is explicitly injected, not physical device evidence.
- Existing secure-loopback functional journeys remain the positive runtime
  controls. Historical App fixtures and their source pins are unchanged.

G1–G6 and physical T1–T8 remain open. No selector, real data, deployment,
installation, network/TLS/trust-store change or physical acceptance is included.

## Local qualification

Frozen-lockfile dependencies were installed for this checkout. Local checks:
1,805 frontend tests, 223 repository contracts, nine bootstrap controls,
TypeScript for direct E2E, touched-scope ESLint, global Prettier, Ruff formatting
(398 files), production PWA build and collection of two new browser cases.
Collection is not execution. The prior attempt using stale workspace dependency
symlinks stopped at branding compilation and is superseded, not a product failure.
