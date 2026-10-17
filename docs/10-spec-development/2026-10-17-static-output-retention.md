# Preserve bounded standard static-tool output

## Observed formatter gate

[Run 39050280067](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39050280067)
on commit `603f7cd2878f616d34e78b0e825db983d064d1b2`, tree
`9c54a8b1b645eb046d540883bae82c3405dd3331`, passed repository verification
and Ruff lint. The formatter exited 1; mypy, OpenAPI and generated-client checks
were unrun. Artifact `12107930877` is 1,605 bytes with SHA-256
`b91b1a909107c20840dc960ee73deff8bc2eb6c16d6cb6285a65cdeb6930954f`.

The wrapper observed 11,498 bytes and 212 unparsed lines, retaining no formatting
locations or changes. The exact discarded output cannot be recovered or treated
as a reviewed patch. The older `Would reformat:` parser does not match the new
default output: [Ruff 0.16 release notes](https://astral.sh/blog/ruff-v0.16.0)
document diagnostic-plus-diff output for `format --check`. This repository pins
Ruff 0.16.5. That establishes the parser's obsolete assumption, without proving
every line of the discarded output. All prior runs remain preserved.

## Selected simplification

Retain the existing six exact static commands and their failure behavior. Replace
the manually enumerated diagnostic parsers with bounded captured output from
those commands. This is reviewed public repository source and its tool output;
no workshop data, private fixtures or credentials are command inputs. Formatting
diffs and source excerpts are permitted for this public source. The fixed cleared
environment and source/configuration provenance must be verified before running.

The tool output remains capped at 16 KiB. Base64 transports those exact bytes in
the existing failure marker without JSON escape inflation. A 24-KiB marker and
32-KiB service stdout spool accommodate encoding and pytest/numeric framing.
These are explicit transport-size changes, not increases to the 20-second work
budget, one-CPU/512-MiB worker, database overhead or per-tool execution ceilings.
Ordinary command output limits remain unchanged. At-cap output is explicitly
marked truncated; no absent or invalid marker qualifies a check.

The host still reads the local spool only after verified stop and client reap.
Strict length, base64, canonical encoding and first-failed-tool numeric binding
remain required. No new exporter, container readback command or child process is
introduced. Any recovered output is evidence to inspect, never executable code.

Independent review and actual qualification of this simplification are pending.
No source formatter changes are guessed in this candidate. After evidence is
retained, apply only the observed deterministic formatting corrections, then
continue type and contract checks. Genuine PostgreSQL-0012 and schema-0013 work
remain pending; no capacity, exposure, main merge or deployment is qualified.
