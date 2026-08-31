from cycling_workshop.db.url import normalize_database_url


def test_normalize_database_url_selects_psycopg_v3_for_plain_postgresql_uri() -> None:
    assert (
        normalize_database_url("postgresql://user:secret@example.test:5432/ocwp?sslmode=require")
        == "postgresql+psycopg://user:secret@example.test:5432/ocwp?sslmode=require"
    )


def test_normalize_database_url_preserves_explicit_driver_and_non_postgresql_urls() -> None:
    assert normalize_database_url("postgresql+psycopg://user:secret@example.test/ocwp") == (
        "postgresql+psycopg://user:secret@example.test/ocwp"
    )
    assert normalize_database_url("sqlite+pysqlite:///:memory:") == "sqlite+pysqlite:///:memory:"


def test_normalize_database_url_accepts_legacy_postgres_alias() -> None:
    assert normalize_database_url("postgres://user:secret@example.test/ocwp") == (
        "postgresql+psycopg://user:secret@example.test/ocwp"
    )
