from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def workflow():
    path = ROOT / ".github/workflows/public-pages.yml"
    assert path.is_file(), "manual Pages workflow missing"
    return path.read_text()


def test_manual_exact_source_and_isolated_permissions():
    doc = workflow()
    assert "on:\n  workflow_dispatch:\n" in doc
    assert "pull_request:" not in doc and "\n  push:" not in doc
    assert "required: true" in doc and "expected_source_sha:" in doc
    assert "\npermissions:\n  contents: read\n" in doc
    assert "group: public-pages\n  cancel-in-progress: false" in doc
    assert doc.count("github.ref == 'refs/heads/main'") == 3
    assert doc.count("inputs.expected_source_sha == github.sha") == 3
    assert doc.count("pages: write") == 1 and doc.count("id-token: write") == 1
    deploy = doc.split("\n  deploy:\n")[1].split("\n  verify:\n")[0]
    assert "needs: build" in deploy
    assert "name: github-pages" in deploy
    assert "timeout-minutes: 10" in deploy
    assert deploy.count("uses:") == 1 and "run:" not in deploy
    assert "uses: actions/deploy-pages@d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e" in deploy
    assert doc.count("persist-credentials: false") == 2
    assert doc.count("ref: ${{ github.sha }}") == 2
    assert doc.count("timeout-minutes: 15") == 2
    assert doc.count("contents: read") == 3


def test_upload_only_checked_leaf_and_verify_returned_url():
    doc = workflow()
    build = doc.split("\n  build:\n")[1].split("\n  deploy:\n")[0]
    assert "path: artifacts/public-site/open-cycling-workshop\n" in build
    assert build.index("playwright test") < build.index("actions/upload-pages-artifact@")
    assert "--require-current" in build
    assert "always()" not in build
    verify = doc.split("\n  verify:\n")[1]
    assert "needs: deploy" in verify
    assert "PUBLIC_SITE_URL: ${{ needs.deploy.outputs.page_url }}" in verify
    assert 'verify_public_site.py --url "$PUBLIC_SITE_URL"' in verify
    assert "playwright.public-site-live.config.ts" in verify
    assert "configure-pages" not in doc
    assert "secrets." not in doc


def test_live_browser_requires_exact_provider_destination_and_blocks_other_requests():
    config = ROOT / "apps/web/playwright.public-site-live.config.ts"
    assert config.is_file(), "live browser config missing"
    text = config.read_text()
    assert (
        "process.env.PUBLIC_SITE_URL !== 'https://izignamx.github.io/open-cycling-workshop/'"
        in text
    )
    assert "webServer: undefined" in text
    spec = (ROOT / "apps/web/tools/public-site/public-site.spec.ts").read_text()
    assert "guardPublicSiteNetwork(context, baseURL, rejected)" in spec
    guard = (ROOT / "apps/web/tools/public-site/public-site-network.ts").read_text()
    assert "await context.route('**/*'" in guard
    assert "maxRedirects: 0" in guard
    assert "maxRetries: 0" in guard
    assert "await route.abort()" in guard
    assert "baseURL" in spec


def test_new_workflow_actions_have_immutable_source_pins():
    import re

    actions = re.findall(r"uses: ([^\n]+)", workflow())
    assert len(actions) == 9
    assert all(re.fullmatch(r"[a-z/-]+@[0-9a-f]{40} # v[0-9]+", action) for action in actions)


def test_workflow_contracts_reject_security_mutations(tmp_path, monkeypatch):
    original = workflow()
    mutations = [
        ("workflow_dispatch:", "push:"),
        ("github.ref == 'refs/heads/main'", "true", 1),
        ("inputs.expected_source_sha == github.sha", "true", 1),
        ("cancel-in-progress: false", "cancel-in-progress: true"),
        ("needs: build", "needs: missing"),
        ("name: github-pages", "name: unprotected"),
        ("path: artifacts/public-site/open-cycling-workshop", "path: ."),
        ("--require-current", "", 1),
        ("persist-credentials: false", "persist-credentials: true", 1),
        ("contents: read", "contents: write", 1),
        (
            "actions/deploy-pages@d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e",
            "actions/deploy-pages@v4",
        ),
    ]
    path = tmp_path / ".github/workflows/public-pages.yml"
    path.parent.mkdir(parents=True)
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    for mutation in mutations:
        path.write_text(original.replace(*mutation))
        caught = False
        for contract in (
            test_manual_exact_source_and_isolated_permissions,
            test_upload_only_checked_leaf_and_verify_returned_url,
            test_new_workflow_actions_have_immutable_source_pins,
        ):
            try:
                contract()
            except AssertionError:
                caught = True
        assert caught, mutation
