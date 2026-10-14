import os
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from scripts.operations.init_local_secrets import initialize_secrets


def test_creates_private_secret_bundle(tmp_path: Path) -> None:
    destination = tmp_path / "secrets"
    initialize_secrets(destination, include_admin=True)
    expected = {
        "auth_secret.txt",
        "postgres_password.txt",
        "postgres_admin_password.txt",
        "database_url.txt",
        "admin_password.txt",
    }
    assert {path.name for path in destination.iterdir()} == expected
    if os.name == "posix":
        assert destination.stat().st_mode & 0o777 == 0o700
    for path in destination.iterdir():
        if os.name == "posix":
            assert path.stat().st_mode & 0o777 == 0o600
        assert len(path.read_text().strip()) >= 32
    url = make_url((destination / "database_url.txt").read_text().strip())
    assert url.password == (destination / "postgres_password.txt").read_text().strip()
    assert url.host == "postgres"
    assert url.username == url.database == "ocwp"
    assert len({(destination / name).read_text() for name in expected - {"database_url.txt"}}) == 4


def test_refuses_any_existing_directory_and_preserves_contents(tmp_path: Path) -> None:
    destination = tmp_path / "existing"
    destination.mkdir()
    original = destination / "auth_secret.txt"
    original.write_text("existing-value")
    with pytest.raises(FileExistsError):
        initialize_secrets(destination)
    assert original.read_text() == "existing-value"


def test_admin_secret_is_opt_in(tmp_path: Path) -> None:
    destination = tmp_path / "secrets"
    initialize_secrets(destination)
    assert not (destination / "admin_password.txt").exists()
