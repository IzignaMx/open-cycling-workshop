from pathlib import Path

import pytest
from cycling_workshop.settings import Settings


def test_reads_database_url_from_secret_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret = tmp_path / "database_url"
    secret.write_text("postgresql+psycopg://ocwp:secret@postgres/ocwp\n")
    monkeypatch.delenv("OCWP_DATABASE_URL", raising=False)
    monkeypatch.setenv("OCWP_DATABASE_URL_FILE", str(secret))
    assert Settings.from_env().database_url == "postgresql+psycopg://ocwp:secret@postgres/ocwp"


@pytest.mark.parametrize("content", ["", " \n", "\x00"])
def test_rejects_invalid_database_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, content: str
) -> None:
    secret = tmp_path / "database_url"
    secret.write_text(content)
    monkeypatch.delenv("OCWP_DATABASE_URL", raising=False)
    monkeypatch.setenv("OCWP_DATABASE_URL_FILE", str(secret))
    with pytest.raises(RuntimeError, match="OCWP_DATABASE_URL_FILE"):
        Settings.from_env()


def test_missing_database_secret_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OCWP_DATABASE_URL", raising=False)
    monkeypatch.setenv("OCWP_DATABASE_URL_FILE", "/nonexistent/private-secret-path")
    with pytest.raises(RuntimeError, match="OCWP_DATABASE_URL_FILE") as error:
        Settings.from_env()
    assert "private-secret-path" not in str(error.value)


def test_explicit_database_url_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCWP_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("OCWP_DATABASE_URL_FILE", "/nonexistent")
    assert Settings.from_env().database_url == "sqlite+pysqlite:///:memory:"
