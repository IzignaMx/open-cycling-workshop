# OpenAPI tool subtimeout within the unchanged static budget

[Run 39051546208](https://github.com/IzignaMx/open-cycling-workshop/actions/runs/39051546208)
tested commit `512df3d47132f9c14c1e33ce4fac9efe03d35fac`, tree
`c1eda35969f1ec78831a5a455a7b3d5388700836`. Repository verification, Ruff lint,
Ruff format-check and strict mypy passed. The OpenAPI command exceeded its
three-second subprocess limit and was killed/reaped; generated-client checking
was unrun. Artifact `12107922284` is 1,591 bytes with SHA-256
`c94e357da5a75dc4bdcd2018fa7bbd92af9a2e077b1621ac5d79c45c86bb6e95`.

The retained diagnostic has kind 2, return code -9 and zero output bytes. It
does not demonstrate OpenAPI drift or a product defect. The exporter imports
the application, creates its contract-configured app and renders its schema
before printing a result; these observations cannot identify the timed-out
phase. No application code or contract bytes are changed to accelerate the check.

The supervisor interval was 16.339 seconds, including 2.314 seconds of setup and
0.105 seconds of cancellation. Subtracting those yields an approximately
13.920-second interval, including the three-second OpenAPI wait and supervisory
overhead. It is not an exact tool CPU time or future duration guarantee.

Select a six-second OpenAPI subprocess ceiling, leaving the client's two-second
ceiling and the shared 20-second workload deadline unchanged. This adds at most
three seconds to that tool's allowance inside the observed aggregate headroom;
the global guard still wins if the combined work takes too long. Other tool
ceilings, worker CPU/memory, database overhead, output bounds, cancellation,
independent cleanup, commands, assertions, configurations and dependencies stay
unchanged. Subprocess ceilings are technical test scheduling bounds, not accepted
product latency or UX limits. They are not an additive work allocation.

Independent source review and actual execution of the adjusted candidate are
pending. Preserve the earlier timeout even if this candidate passes. If the
combined gate still exceeds its bounds, inspect that evidence before another
change; no automatic budget increase or retry is authorized by this document.
This remains a static/contract gate. PostgreSQL semantics, schema 0013, capacity,
API exposure and deployment are separate and unqualified here.
