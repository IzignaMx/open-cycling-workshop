# Frozen containment helper provenance

This file is an exact, unmodified copy of `scripts/ci/quote_capacity_micro.py`
from local commit `f9849cbca62311d6fe090e5800986307a223cbd9`, tree
`323661ade5a3540f389bfb5b965d4ff63b400d5c`, equivalent to actual main
`8a7eeecc39b0a43097484d10dc30af541ae38156`.

- File: `baseline_323661ad.py`
- Bytes: 33570
- SHA256: `1d7e19e627d9b0506813a12b76829defa9905550537f00a2a8e5d5c359149db6`
- Copyright: 2026 Open Cycling Workshop Platform contributors
- License: AGPL-3.0-only, as provided by the repository's LICENSE and
  LICENSES/AGPL-3.0-only.txt, with aggregate attribution in REUSE.toml.

The bootstrap verifies this digest before loading the module by its exact path.
Import executes its standard-library imports, constants and definitions only;
its guarded main is never invoked. Its business `supervise`, CLI, business
parsers and workload selectors are never called. This is not a candidate guard
import. No edits or substitutions of the frozen helper are permitted.

The finite bootstrap calls only the helper's bounded client, source query,
identifier, ownership inspection/reconciliation/removal, cgroup/privilege
readback, CPU delta and three-generation cancellation-canary helpers. Its
client has up to two seconds of reap grace beyond the requested timeout, and
its ownership inspection makes two direct five-second client calls. The
bootstrap accounts for those limits without changing or monkeypatching this
copy. The new wrapper, parser and workflow remain source-only, unexecuted
preparation until a separately authorized first hosted run.
