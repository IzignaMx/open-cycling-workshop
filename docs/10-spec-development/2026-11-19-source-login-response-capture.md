# Test-only early capture of destination login evidence

Baseline: main `654fffe8a584f16b3f4e92761a269b7bedde521c`.
This is separate from the Windows/Android guide. No runtime behavior changes.

## Observed failure, not an inferred browser root cause

Main118 CI `44577565846` direct artifact `14558659854`, SHA256
`5f45c63c0f10a6a4fa8c99db01e4c8f0647de131b129dce4dd732db39a708aa8`,
reported `source-completion-new-work.spec.ts` loginResponse.json failing with
`Network.getResponseBody: No data found for resource with given identifier` on retry zero despite HTTP200.
Retry one passed; that does not erase the first failure. Trace observations supplied
by independent review place goto at438396, login POST/200 at438566 and body read
at438949. These observations do not establish an internal CDP cause or a subsequent
navigation. No old run is rerun or reclassified.

The previous source registered its response waiter before login but postponed body
consumption until login finished READY/baseline/sync checks. The change attaches
capture immediately to that same matched-response promise and waits jointly for
capture and login completion. It retains exact URL/POST matching, HTTP200, nonempty
issued token, equality with destination storage, inequality with source token,
unchanged source session and real auth/context assertions. Body absence, malformed
JSON or missing token remains a failure; there is no fallback to storage evidence.

The helper installs no additional response listener, timeout, retry or network
interception. Playwright owns the existing bounded waiter and fixture context
teardown. Both promise rejection handlers are attached before the action begins,
so action failure followed by waiter rejection during teardown is observed rather
than left unhandled. Captured body/token is never copied into receipts or errors.

## Validation boundary

Fake-response controls prove early consumption before an artificial expiry, waiting
for the action, failure propagation and late rejection handling. RED preserved the
expired-body and unhandled-rejection failures of deferred consumption; GREEN is
local helper evidence only. It does not reproduce Chromium/CDP internals or prove
the native flake fixed. New hosted native execution and independent trace review
remain pending. No product behavior, physical acceptance, deployment, selector,
G1–G6 or Windows/Android qualification changes are claimed.
