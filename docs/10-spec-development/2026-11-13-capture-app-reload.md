# Actual capture App and service-worker reload qualification

## Bounded decision

Baseline main is `bf61d4508e52cfc5299c6b65f0c4437502413475`, tree
`8e35297648181c46d221639e120ad35d957b05e5`. PR106 CI 43383631535 passed
three isolated native reducer/storage cases without retry. Those results do not
qualify the actual historical App or service worker. This increment adds that
missing test surface, not a new bicycle selector or a rollout mechanism.

Keep exact-v1 production writes and the current shared-origin behavior. An
instantaneous existing-bicycle action was considered but rejected for this task:
it would not recover a selected bicycle after a definitive not-saved outcome and
reload. Redefining that intent as disposable would not solve recoverable intake.

## Executable scope

Build the unmodified historical `cc18a203a8c754284fc14ef3570d94d7d98fac23`
App and generated SW, and separately the actual current checkout HEAD App/SW.
Both builds archive Git source, verify the source tree and frozen dependency lock,
use archived workspace packages, verify source bytes before/after compilation,
and hash every emitted asset. Repeated builds must match. The earlier `714342`
fixture remains separately pinned and retains its original contract.

A loopback-only static host serves each complete distribution on a distinct port.
It has no backend proxy, account, production data or fallback API route. Test
contexts are disposable. Native IndexedDB seeding requires the actual App to have
initialized its database first; the test does not create a replacement schema or
invoke the reducer manually. Seeded content is synthetic, valid and unexpired:
one unknown-format order, an exact-v1 customer control, matching metadata and a
journal preservation control.

Before opening the App, the case creates a synthetic legacy-presence sentinel from
an inert same-origin manifest page. The existing legacy notice is published only
after startup capture cleanup completes. Waiting for that notice before seeding
the authenticated fixture prevents initial cleanup from consuming the reload
scenario. The notice is awaited again after reload; an expired orphan also acts
as a maintenance witness. No test hook is added to the App.

Each native case verifies local and served artifact provenance, installs the SW,
checks control, goes offline, and requires a failed uncached network request.
A page reload must be served by the SW. The historical startup cleanup should
remove the unknown row and mark it unavailable; the compatibility-aware current
startup should preserve it byte-for-byte. Both must preserve the v1 control and
journal. Before/after snapshots, SW identity, browser version and network failures
are retained with the test trace. Context disposal removes only synthetic data.

## Claims and pending evidence

This is **page reload**, not browser-process restart. Separate contexts compare
old and current startup; they do not simulate an in-place update, partial SW
installation, concurrent old/new tabs, profile restore or migration. A successful
historical deletion case is a counterexample, not a safety fix. No application
runtime, database schema, production payload writer or SW policy is changed.

Native execution is pending for this candidate. The previous local browser launch
was unavailable under the environment restriction and was not bypassed or retried.
Compilation, build reproducibility, test collection and validator tests are not
native execution. Hosted CI is authored but requires separate publication authority.
No process restart or native App outcome is claimed before that run succeeds.

G1–G6 in [the rollout boundary](2026-11-13-capture-rollout-boundary.md) remain open.
Even a passing hosted run supplies only a bounded part of G2: actual App/SW offline
reload behavior. It cannot exclude old offline JavaScript, authorize a new origin,
prove lossless handover or establish a safe downgrade floor. Physical V0.1, recovery,
privacy, capacity and financial/quote gates are unchanged. No deployment is requested.

## Local validation ledger

Frozen local checks: frontend **1,550 passed**, repository **208 passed**;
repository contract, ESLint, formatting, Ruff, real frontend typecheck and the two
production-isolation checks pass. Historical cc18, current HEAD and the unchanged
714 legacy fixture each reproduced seven assets. Seventeen focused provenance,
startup-barrier and fixture controls pass. Two native cases are collected and
**zero executed locally**; hosted execution remains pending.

Independent review accepted the final causal barrier, provenance and documentation
without blocking findings. The original race-prone candidate receipts and the
superseded checkpoint-documentation failure are preserved separately. No earlier
source qualification is reused. Final commit/tree and exact source/receipt hashes
are retained in the durable review archive. Rebuild the current artifact after
committing so its provenance identifies that exact HEAD.
