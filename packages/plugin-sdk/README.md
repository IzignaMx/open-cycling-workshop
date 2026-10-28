# Plugin SDK boundary

The TypeScript package remains private and exports **no runtime API**. Nothing
in this directory installs, executes or authorizes third-party code.

## M0: a data-only proposal descriptor

The [closed schema](manifest/descriptor-m0.schema.json) and inert
[official-build](examples/official-descriptor.m0.json) /
[external-connector](examples/external-descriptor.m0.json) examples establish a
small compatible proposal vocabulary. `runtime.type` is a requested integration
class, not a certification of Official status.

From the repository root:

```sh
python3 scripts/plugins/validate_manifest.py packages/plugin-sdk/examples/official-descriptor.m0.json
python3 scripts/plugins/validate_manifest.py packages/plugin-sdk/examples/external-descriptor.m0.json
```

Successful output is deliberately limited:

```text
descriptor valid; runtime not evaluated
```

A valid file grants nothing. There is no loader, registry installer, service
identity, Core database access, migration engine, public event delivery or
extension sync enrollment in M0. All permissions, network hosts, subscriptions,
secrets, data ownership and UI slots must be empty; offline mode is online-only.

## Compatibility and licensing are not inferred

`core.requires` names exactly the reviewed `a960bdd` source baseline. It does not
mean the proposal runs on that source; it is not a SemVer range or a conversion
between Python/npm versions. The `0.0.0-m0` and AGPL constants constrain these
inert prototype descriptors only. They do not change the policy allowing legally
separable external connectors under their reviewed applicable licenses.

Namespace ownership, source provenance, support ownership, licensing and actual
host/module compatibility evidence are future review requirements. A descriptor
cannot self-assert trust through an `official` or `verified` field.

## Input envelope and diagnostics

- At most 16,384 raw bytes; the CLI reads only that limit plus one byte.
- Strict UTF-8 JSON object; no BOM, YAML, duplicate keys or nonfinite values.
- Integer number tokens only, at most ten digits; `1.0` and `1e0` are rejected by
  the parser envelope even though general JSON Schema can regard them as integers.
- Maximum nesting depth eight (root depth zero); printable Unicode keys/strings,
  no controls or unpaired surrogates. IDs/names have the schema's exact bounds.
- Closed keys at every level; Phase 5 aliases and executable hooks/imports/commands
  fail rather than being translated or loaded.
- Errors are fixed `E_*` codes, never input values or tracebacks. Exit status zero
  means descriptor-only validation; one means a validation/I/O failure.

The fixed schema interpreter implements only the vocabulary used by this M0
schema and rejects unknown/inapplicable keywords. It is **not a general JSON
Schema engine**, never accepts a caller schema and never fetches `$schema` URLs.
Byte bounds/duplicate detection/number lexical rules belong to the parser envelope,
not to a claim that JSON Schema alone enforces them.

## What comes next

Read the [normative M0 guide](../../docs/08-open-source/2026-10-27-module-descriptor-m0.md).
Later official modules require explicit reviewed build-time composition; external
connectors require independently authenticated, isolated API access. Neither path
may expand legacy wildcard grants, write another domain's tables, bypass tenant
scope or silently enter offline synchronization. Real migration, recovery,
permission-loss and compatibility tests precede runtime integration.
