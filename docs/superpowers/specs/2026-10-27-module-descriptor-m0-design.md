# Compatible module descriptor M0 — bounded design

Status: assistant-selected design under the maintainer's 2026-10-27 technical
delegation, independently reviewed design; reconciled-source review remains separate. Not a claim of human approval,
SDK v1 completion, registry trust, installation support or connector authority.
Baseline `a960bddb94189c6c74c7f3d0a72472636c3caced`.

## Problem and authority

The monolith has explicit composition but `packages/plugin-sdk/src/index.ts`
exports nothing. Phase 5 §18 and Phase 8 §56 have different conceptual manifest
vocabularies. A minimal data-only contract can prevent incompatible proposals and
teach safe extension boundaries without adding a loader or permission system.
This is an early prerequisite for R09-T020 / R09-T021 / R10-T014, not completion
or reprioritization of their broad future-release gates.

## Alternatives

1. Selected: closed canonical JSON descriptor, machine-readable schema, pure
   bounded standard-library validator and inert example descriptors. No dependency
   increase, network access, import/discovery or modification of application code.
2. TypeScript-only interfaces: useful later but cannot reject malformed external
   JSON or prove the language-neutral manifest contract.
3. Runtime registry/loader and service identities: defer; these carry authority,
   migration, lifecycle and isolation risks disproportionate to this prerequisite.

## Canonical vocabulary and compatibility

Prefer Phase 8 `schema`, `core.requires`, `runtime.type`, `permissions`,
`network.hosts`, `events.subscribes`; reject legacy `platform`, `capabilities`,
`subscriptions` aliases rather than guess or silently translate their authority.
The current descriptor has a distinct M0 profile and only an exact explicitly
supported development contract identity; it does not evaluate general SemVer
ranges or equate Python `0.1.0.dev0` with npm `0.1.0-dev.0` implicitly. A later
published compatibility matrix and protocol promotion must be separate work.

M0 admits only empty permission/network/event/secret/data/UI declarations and
an online-only/no-offline-integration mode. Validating a descriptor cannot grant
capabilities, change roles or frozen wildcards, install code, create identities,
run migrations, enroll in sync, fetch its source URL or certify its license.
Official reviewed modules and isolated external connectors remain different
runtime classes; a user-supplied class cannot make untrusted code official.

## Input/security invariants

- Strict UTF-8 JSON object, no YAML, duplicate keys, nonfinite numbers or BOM.
- Bounded 16 KiB raw input; bounded strings/lists and closed keys at every level.
- Reject unknown schema/profile, unsupported compatibility and any nonempty
  authority or executable field. Reject path/import/hook/code URLs as execution.
- Errors are bounded fixed validation codes, never echo arbitrary input/secrets.
- No filesystem writes, network calls, dynamic imports, subprocesses or Core
  database access in validation. CLI may read one descriptor and print only a
  validation summary; it never acts on contents.
- Namespace ownership, signing, certification, licensing review and actual
  compatibility evidence are external review duties, never self-asserted trust.

## Deliverables and acceptance

Schema + inert official/external examples; pure validator and CLI; negative tests
for bounds/duplicates/types/aliases/executable/permission requests/compatibility;
positive exact examples; guide with source map, future acceptance and explicit
non-goals. Schema and validator must agree on every supplied fixture; no public
SDK exports changed. Actual router/model/App composition, grants, database and
runtime budgets remain untouched.

Independent review and exact-source CI qualify the descriptor only. Existing
streaming/cancellation/capacity/install/physical gates stay open. Publication of
this new increment requires its own normal repository authorization and checks;
it does not inherit authority from the presentation publication or deployment gates.

## Exact M0 compatibility ruling

`schema` is integer `1`; `profile` is `ocwp.module-descriptor.m0`.
`core.requires` is exactly
`ocwp-source:a960bddb94189c6c74c7f3d0a72472636c3caced`.
This names the proposal's reviewed source baseline, **not an ABI or runtime
compatibility guarantee**. No host version conversion or SemVer range matching
is performed. Changes to this M0 target require explicit profile/schema review;
a new source SHA cannot auto-admit a descriptor. Python/npm package versions
retain their existing meanings and are not rewritten.

The machine-readable schema uses a small documented JSON Schema vocabulary and
is trusted repository data. A pure validator may interpret only that fixed
vocabulary, without accepting caller-supplied schemas or following `$ref`/URLs.
The same schema rules drive both supplied fixtures and CLI validation, avoiding
an untested second contract implementation or a new runtime dependency.

## Complete required descriptor shape and bounds

Every object is closed and every listed key required:

```json
{
  "schema": 1,
  "profile": "ocwp.module-descriptor.m0",
  "id": "org.example.readonly-info",
  "name": "Read-only information example",
  "version": "0.0.0-m0",
  "license": "AGPL-3.0-only",
  "core": { "requires": "ocwp-source:a960bddb94189c6c74c7f3d0a72472636c3caced" },
  "runtime": { "type": "official-build" },
  "permissions": [],
  "network": { "hosts": [] },
  "events": { "subscribes": [] },
  "secrets": [],
  "data": { "owns": [] },
  "ui": { "slots": [] },
  "offline": { "mode": "online-only" }
}
```

`runtime.type` also permits `external-connector`; this is a proposed integration
class, never trusted Official status. `id` is 5–128 ASCII characters matching
`^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9-]*){2,}$`. `name` is 1–80 printable Unicode
characters. Other strings are exact constants/enums shown above; arrays are
empty. No source URL or contact field exists in M0; real artifact provenance,
namespace ownership and support ownership must be reviewed before a later
runtime integration. M0 examples cannot self-assert those properties.

The AGPL/version constants describe this inert prototype profile, **not a new
licensing restriction for legally separable external integrations**. Promotion
requires its own licensing and compatibility decisions; no M0 pass certifies them.

Parser envelope (not claimed expressible by JSON Schema): max 16,384 raw bytes;
strict UTF-8 without BOM; duplicate keys fail even when values equal; JSON number
tokens must be integers with at most ten digits (no decimal/exponent/nonfinite
tokens); nesting depth at most eight (root depth zero); every key/string printable
and free of unpaired surrogates. Boolean is not an integer. CLI reads at most
16,385 bytes before validation. No unbounded read precedes the size check.

Interface: `validate_descriptor(raw: bytes) -> dict[str, object]` raises
`DescriptorError` with fixed `.code` from `E_INPUT_TYPE`, `E_SIZE`, `E_UTF8`,
`E_JSON`, `E_DUPLICATE_KEY`, `E_NUMBER`, `E_DEPTH`, `E_STRING`, `E_SCHEMA`,
`E_SCHEMA_DEFINITION`, `E_IO`. CLI exits zero only for valid descriptors, prints
`descriptor valid; runtime not evaluated`, and prints only fixed error codes on
failure. Neither output contains input values. Unknown trusted-schema keywords
fail closed; the interpreter is M0-specific, not general JSON Schema support.

## Local reconciliation onto the reviewed presentation baseline · 2026-10-28

The presentation is merged at `1946608ac8dae5a5ff160fd74c896f8eba22f540`.
Reconcile this separate descriptor prerequisite locally onto that source while
preserving original `a37186c` and its reviewed design. The only cherry-pick
conflict is insertion order in execution-state: retain the complete main
presentation/privacy records and add the M0 block, never replace main state
with the old baseline's historical status.

Keep `core.requires` pinned to the original exact `ocwp-source:a960bdd...`
identity specified in full above. It labels the descriptor proposal baseline,
not the current checkout or a runtime compatibility promise. Automatically
rewriting it to the newest commit would weaken the explicit profile-review gate;
no host package versions, APIs, grants or runtime exports change. The merged
module strategy agrees with the selected Phase 8 vocabulary; Phase 5 aliases
remain rejected and are not a second accepted dialect.

This reconciliation is local-only. Publication, fresh exact-source hosted
qualification and postmerge verification remain separate future gates. No
Pages settings/permissions, runtime integration, connector identity, module
loading, migrations or activation is included.
