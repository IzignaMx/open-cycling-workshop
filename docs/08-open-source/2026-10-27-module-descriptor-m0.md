# Module descriptor M0: proposal contract, not a plugin runtime

Status: **implemented_pending_evidence** data-only prerequisite, source baseline `a960bdd`. The
[design](../superpowers/specs/2026-10-27-module-descriptor-m0-design.md) and
[implementation plan](../superpowers/plans/2026-10-27-module-descriptor-m0.md)
are assistant-selected under maintainer delegation and independently reviewed.

This resolves the conceptual Phase 5 `platform/capabilities/subscriptions`
versus Phase 8 `core.requires/permissions/events.subscribes` vocabulary in favor
of Phase 8 for a deliberately named M0 profile. Legacy aliases are rejected,
not silently translated. It does not make either conceptual draft a working
installer or published runtime protocol.

M0 supports inert official-build and external-connector proposals, empty
permissions/network/events/secrets/data/UI and no offline integration. A valid
file is not trusted, certified, installed, authorized or runtime-compatible.
Core's frozen wildcard grants, explicit router/model/App composition and public
SDK exports remain unchanged. Independent connector identity and public event
delivery do not exist merely because the descriptor names their future class.

The exact `core.requires` target is a reviewed source identity, not a conversion
between Python and npm versions or a claim that a module executes on that build.
AGPL and `0.0.0-m0` constants bound these inert examples/profile only; they do
not change the architecture's policy for separable external licenses.

This contributes a prerequisite to R09-T020 / R09-T021 / R10-T014 without closing
SDK, registry or compatibility qualification. Namespace/artifact ownership,
reviewed licensing, signed provenance, tenant authority, lifecycle, migrations,
recovery and real host/module evidence remain gates before runtime integration.

## Implemented local checkpoint

The [schema](../../packages/plugin-sdk/manifest/descriptor-m0.schema.json),
[inert examples](../../packages/plugin-sdk/examples/) and
[pure validator](../../scripts/plugins/validate_manifest.py) are now implemented,
**pending exact-source hosted evidence**, not a verified SDK. See
[usage and parser limits](../../packages/plugin-sdk/README.md).

Observed TDD: 73 failures before implementation / 74 initial passes; four
inapplicable-schema/CLI corruption failures / 78 passes; four boolean-root and
constant-type failures / 82 passes; one unanchored-pattern failure / 83 passes.
The trusted pattern subset is explicitly anchored; printable-string envelope
and fixed schema avoid silently promising general JSON Schema search semantics.

Independent review ran 78 source tests and 3,000 deterministic malformed/type
mutations with only bounded validation errors, no unexpected exceptions. Its
minor pattern-semantics concern is now a failing-then-passing guard. Final focused
contract/repository tests pass 113 cases. Strict mypy and Ruff pass. Full local
suite and exact candidate hosted checks remain separate evidence gates.

No public SDK exports, application router/model composition, dependencies,
capabilities, real accounts, migrations or runtime budgets changed. No files
were published remotely by this checkpoint; repository publication is separate
from descriptor validity and from any actual module integration.

## Local-only integration checkpoint · 2026-10-28

Original `a37186c` is preserved. The descriptor-only changes are replayed onto
presentation main `1946608` in an isolated local branch. Current presentation
and privacy execution-state records are retained byte-for-byte; no runtime
implementation, schema field, validator rule, example or SDK export changes.
The [merged module strategy](2026-10-27-compatible-modules.md) agrees with this
canonical vocabulary and staged official-build/external-connector boundary.

The proposal target remains the original exact `ocwp-source:a960bdd...` identity
(as fully specified in the design and fixtures), not an automatically admitted
host version or claim of runtime compatibility with the new checkout. Fresh
reconciled tests/review are required; M0 remote publication and hosted evidence
remain pending. No Pages activation or connector/module installation occurs.

Reconciled local evidence: 153 focused cases (83 descriptor + 70 repository),
Ruff, strict mypy and formatting passed. Independent review exercised 5,000
raw/structured mutations with no unexpected exceptions and confirmed unchanged
runtime/SDK exports and byte-identical original descriptor implementation.
The full local suite collected 4,978: 4,307 passed, 671 explicit environment
skips and 12 warnings. These skips do not establish PostgreSQL, restore,
physical-device or browser runtime acceptance. Reconciled exact-source hosted
validation and postmerge verification remain unperformed and required.
