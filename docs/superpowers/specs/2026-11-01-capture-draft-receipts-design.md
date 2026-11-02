# Mounted capture draft receipts

Assistant-selected ordinary engineering correction under Foundation v0.2 TA-01,
TA-03 and Master Loop data-integrity priority; not human design approval.
Baseline `cdb44aa`; extends the 2026-10-29 quota-safe capture design only at the
mounted form boundary. V0.1 remains partial.

## Evidence and root cause

`CustomerQuickCreate` and `OrderQuickIntake` keep controls editable while awaiting
their capture callback. Both reset current values on any saved result. Order
also promotes the submitted customer/priority into retained clean defaults.
A late receipt therefore erases input entered after dispatch. The deterministic
unit host executes the actual TSX component and its returned handlers, substituting
hooks, JSX construction and UI Button, with controlled callback results rather
than actual persistence. The real outcome classification remains exercised.

After the second workspace snapshot loss (2026-11-02), this intended six-file
contribution is reconstructed again from retained creation/patch transcript, not
recovered as exact lost candidate bytes. Fresh RED/GREEN evidence is required;
previous lost logs/results do not qualify this second replacement.
This is not React scheduling, DOM, browser, storage or accessibility evidence.

## Approaches

1. Disable every field while busy: prevents edits, but changes the existing editable
   workflow and discards the opportunity to prepare a new draft. Not selected.
2. Compare values with the submitted payload: misses ABA interactions, ignores hidden
   bicycle values and risks normalizing away meaningful draft differences. Rejected.
3. **Selected:** per-mounted-form opaque edit revision in `useRef<object>({})`.
   Every actual onChange handler replaces its identity before setting the field;
   same-value events conservatively count as interaction, as do ABA edits. Capture
   identity immediately after the synchronous submission gate admits the attempt.
   Only a saved receipt matching that identity may reset or adopt retained defaults.

## Invariants and copy

- All customer fields and all order controls (including customer, priority, bicycle
  checkbox, hidden brand/model state) share the form revision.
- If a saved receipt is older, preserve the entire current draft and order retained
  selection baseline. Say exactly: `El envío anterior se guardó localmente. El
formulario actual sigue sin guardar.` No user input or exception text is echoed.
- If unchanged, preserve existing reset, customer/priority retention, success copy
  and clean-draft behavior. A subsequent explicit submission captures the new draft
  and can reset it after its own saved receipt.
- Dirty navigation remains value-based plus existing busy/unknown latch; revision
  itself is not an everlasting dirty latch. An intentionally emptied current form
  may be clean after the prior save finishes.
- Proven not_saved and unknown preserve input. Unknown latch remains independent of
  edits, including emptying all fields; busy reentry stays synchronously refused.
- No automatic retry, dependencies, schema/storage change, runtime/controller/auth
  change, production debug API, durable cross-navigation draft or receipt promise.
- Existing accessible status, labels, focus and editable controls remain unchanged.

## Verification and review

Behavioral unit tests cover each control independently, preserved full drafts,
ABA/same-value edits, unchanged resets, retained baseline, second explicit save,
same-pre-render-handler busy guard, not_saved retry, unknown refusal after
editing/clearing, hidden bicycle reopen and empty-draft dirty policy. Register
with the existing core runner. Run full frontend core, typecheck/build and touched
lint/format. Actual PWA coverage belongs in existing authenticated capture fixtures,
using test-only delayed reads/writes without changing production APIs or native
transaction terminal ordering. Browser qualification remains pending until executed;
no unit result substitutes for it. Parent coordinates browser and whole-tree review.

## Second replacement checkpoint

The original design was independently accepted before its implementation; fresh
independent review of this second replacement remains required. No prior pass or
lost commit/tree identity is inherited. Explicit repeated same-value submissions
remain separate creates, not a new deduplication guarantee.

Fresh second-replacement baseline execution produced 20 failed / 9 passed;
applying the bounded opaque-token fence then produced 29/29 passed. Logs:
`artifacts/spec-continuation/capture-second-replacement-red.log` and
`artifacts/spec-continuation/capture-second-replacement-green.log`.
Fresh touched ESLint/Prettier, web typecheck and production PWA build pass.
The existing >500 kB bundle-size warning remains; no limits were changed.
Fresh full frontend core passes 1,050/1,050 with no skips. Browser qualification and
independent whole-package review remain parent-coordinated gates.

Fresh broad logs under `artifacts/spec-continuation/`:
`capture-second-replacement-full-core.log`, `capture-second-replacement-lint.log`,
`capture-second-replacement-format.log`, `capture-second-replacement-typecheck.log`
and `capture-second-replacement-build.log`.
