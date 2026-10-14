from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_branding_named_volume_is_narrow_and_restore_is_explicit() -> None:
    compose = (ROOT / "infra/compose/docker-compose.local.yml").read_text()

    def service(name: str) -> str:
        return compose.split(f"\n  {name}:\n", 1)[1].split("\n\n", 1)[0]

    assert "branding_assets:/var/lib/ocwp/branding-assets" in service("api")
    assert "branding_assets:/var/lib/ocwp/branding-assets:ro" in service("operations")
    assert "branding_assets" not in service("worker")
    assert "branding_assets" not in service("edge")
    assert "branding-assets-init:" in service("api")
    assert "condition: service_completed_successfully" in service("api")
    assert "profiles: ['branding-restore']" in service("operations-restore")
    assert "branding_assets:/restore-branding-assets" in service("operations-restore")
    assert "scripts.database.branding_bundle" in service("operations-restore")
    assert "OCWP_RESTORE_DATABASE_URL_FILE" in service("operations-restore")


def test_asset_directories_are_private_nonroot_owned_in_built_images() -> None:
    for name in ("platform.local.Dockerfile", "platform.Dockerfile", "operations.Dockerfile"):
        source = (ROOT / "infra/docker" / name).read_text()
        assert "install -d -m 0700 -o 10001 -g 10001" in source
        assert "/var/lib/ocwp/branding-assets" in source
        assert "USER ocwp" in source


def test_development_api_also_has_persistent_private_assets() -> None:
    compose = (ROOT / "infra/compose/docker-compose.dev.yml").read_text()
    api, worker = compose.split("\n  api:\n", 1)[1].split("\n  worker:\n", 1)
    assert "OCWP_BRANDING_ASSET_ROOT: /var/lib/ocwp/branding-assets" in api
    assert "branding_assets:/var/lib/ocwp/branding-assets" in api
    assert "branding_assets:/var/lib/ocwp/branding-assets" not in worker
