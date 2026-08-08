# Repository restore required

The current GitHub tree is a **partial bootstrap/import** and must not be treated as the canonical project source until the authoritative bundle has been restored.

Authoritative consolidation metadata:

- HEAD: `b08a6843c1578236abb0270d15841e511387cd14`
- tree: `d80a8ffc8ea2fe6f0f25b6a66b45ef5c6657fd9c`
- tracked files: `218`
- commits: `30`
- bundle SHA-256: `4d7f14cd143da0ff37bd64bd2eb8c8447d683045fe396d3822f51eb9de85cc96`
- source ZIP SHA-256: `e5a194647196c1f0c060351938ef91f43a76b45d7499889a6be728bad3cd53f8`

## Required restoration

From a machine with authenticated Git access to `IzignaMx/open-cycling-workshop`, use the authoritative bundle and restore helper supplied with the consolidation:

```bash
bash publish-authoritative-bundle.sh \
  /path/to/open-cycling-workshop-final-consolidated.git.bundle \
  git@github.com:IzignaMx/open-cycling-workshop.git
```

The helper verifies the bundle, backs up the current partial `main`/`bootstrap/v0.1` refs under `pre-consolidation/*`, replaces both branches with the authoritative commit, fetches `main` back, and verifies both the commit SHA and tree SHA.

Do not delete this warning manually. It disappears naturally when the complete authoritative tree replaces the partial bootstrap.
