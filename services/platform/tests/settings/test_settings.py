from pathlib import Path

from cycling_workshop.settings import Settings


def test_settings_reads_auth_secret_from_file(monkeypatch, tmp_path: Path) -> None:
    secret_file = tmp_path / 'auth_secret'
    secret_file.write_text('file-secret-that-is-long-enough-for-production-1234567890\n')
    monkeypatch.setenv('OCWP_ENVIRONMENT', 'production')
    monkeypatch.delenv('OCWP_AUTH_SECRET', raising=False)
    monkeypatch.setenv('OCWP_AUTH_SECRET_FILE', str(secret_file))
    monkeypatch.setenv('OCWP_DATABASE_URL', 'sqlite+pysqlite:///:memory:')

    settings = Settings.from_env()

    assert settings.auth_secret == 'file-secret-that-is-long-enough-for-production-1234567890'
