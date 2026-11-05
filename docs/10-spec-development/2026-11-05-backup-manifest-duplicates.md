# Autonomous tests: unambiguous backup manifests

## Scope and accepted baseline

This local hardening continues autonomous testing while physical T1–T8 remain
explicitly deferred. It does not authorize or prove a real restore, deployment,
capacity, M2 or a release. V0.1, R01-T035 and OPS-GATE-006 remain partial/open.

[PR92](https://github.com/IzignaMx/open-cycling-workshop/pull/92) is accepted at main
`fb7b9ce9ad2503c67c2dc1bde7d0ffbc2f091a23`, tree
`505314dabc9e292055ae12c3a2a2ac53c35c343f`.
[Fresh-main CI 42013294946](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/42013294946)
passed aggregate 27/27, Python 6,426 plus 58 exact skips, frontend 1,299, API one,
browser 133 direct/133 aggregate, repeats 20/9/5/10, expiry ten and kernel 14
single-attempt passes. All six new location-validation PostgreSQL cases executed
successfully. Runtime, Security and microfixture also passed; ten main checks
were successful. Bounded receipts and small artifact digests were independently
verified. Large browser archives, traces and screenshots were not inspected.
This supersedes PR92's source-stage pending snapshot only for that accepted source.
It cannot qualify this new parser change.

## Finding and compatibility decision

The PostgreSQL manifest used ordinary `json.loads`, accepting duplicate object
names by selecting the last value. The composed branding manifest already rejects
duplicates. This is ambiguous-input/parser-consistency hardening, not an
authenticity bypass, privilege escalation or demonstrated restore exploit.
The synthetic outer checksum was deliberately recomputed; SHA256 checks integrity
against a manifest and does not establish trusted provenance.

Original version-1 writer `b38c346` and the current writer build dictionaries and
serialize them with `json.dump`. Neither emits duplicate names. The snapshot
observer increment `ba45f4e` preserved that representation. The correction rejects
duplicate decoded names in every object, including nested optional metadata,
through `object_pairs_hook`. It preserves the existing fixed operator-safe error
and all existing resource/path/size/hash/schema and restore compatibility checks.

Unknown additive fields remain accepted in the PostgreSQL manifest. The outer
branding format remains closed. Existing documentation did not unambiguously
require a closed PostgreSQL field set; tightening that set is not bundled here.
No format version, CLI, database schema, dependency, workflow or restore policy
changes. No ADR-level architecture change is required. NFR-006, canonical R01-T033,
OPS-ADR-013/015 and Master Loop integrity/TDD requirements motivate this bounded
validation; none of their full recovery gates is closed by mocks.

The earlier 38 exploratory probes had 23 passing controls and 15 failures of
hypothesized rejection expectations. These were not fifteen established defects.
Duplicate-name ambiguity is now addressed separately from unknown-field policy.

## Tests-first and independent review

85 new retained cases in `tests/operations/test_branding_bundle.py`:

- 80 combinations: five object levels, identical/invalid-first/invalid-last/escaped
  equivalent names, and direct/composed verify/restore preflight entrypoints.
  All refuse before runner/engine creation or target assets, with unchanged bytes.
- Two duplicate-name cases inside additive nested objects/arrays, without echoing
  names or values in the error.
- Three positive controls: current writer, a synthetic legacy version-1 shape,
  and unique additive fields at all five levels. Verification preserves data and
  invokes only the mocked archive-index checks. The legacy control is not a real
  old installation archive or evidence of successful old-schema restoration.

RED before the production change: 62 failed and 23 passed. Twenty invalid-last
cases already failed semantic validation; three positive controls already passed.
GREEN: all 85 passed. Nearest backup/branding suites: 195 passed, no skips, one
existing Starlette warning. Independent review repeated those 195 and passed 25
additional probes, including 96 refusal entrypoint checks and separate-object
compatibility. No blocking finding. Existing CI roots/shard a collect the tests;
no qualification or skip policy changed.

## Local verification receipt

Full local Python completed: 5,893 passed, 677 environment skips, 12 warnings in
429.34 seconds, exit zero. No configured PostgreSQL test URL was available; those
skips are not proof of candidate recovery. Parser and regression hashes remained
unchanged from independent review through the full run. Only documentation
progress/receipt fields changed afterward; repository 193 and nearest operations
195 are rerun against the final receipt.

Full Ruff, ESLint, Prettier, TypeScript, application mypy (125 files), changed
backup-module mypy, OpenAPI/generated-client and repository contracts passed.
Frontend runtime, PWA build and native browser were not repeated for this
parser-only change; accepted PR92 results above remain baseline evidence only.
Local tools are Python 3.13.5, Node 24.22.1 and pnpm 11.25.0; lockfiles unchanged.

No hosted acceptance or publication is claimed for this change. Evidence is
retained in ignored `artifacts/autonomous-backup-parser-20261105/`, not public
download paths.

## Limits and next gate

All new fixtures are tiny synthetic files in owned temporary directories. Every
PostgreSQL runner and engine is mocked/spied; no real PostgreSQL command,
connection, backup or restore was executed. No actual recovery, snapshot durability,
filesystem power-loss or historical installation compatibility is proved.

The prior native-browser socket restriction is not retried or bypassed. New
publication needs applicable authorization; fresh hosted checks would be separate
from the accepted PR92 baseline. T1–T8, R01-T035, OPS-GATE-006, SPENT40927223929,
UNKNOWN41011497919, capacity, M2 and Pages remain unchanged.
