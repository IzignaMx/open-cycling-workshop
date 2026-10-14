from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULT_DEV_SECRET = "development-only-secret-change-before-production-0000000000000000"


def database_url_from_env() -> str:
    database_url = os.getenv("OCWP_DATABASE_URL")
    if database_url is None and (database_file := os.getenv("OCWP_DATABASE_URL_FILE")):
        try:
            with open(database_file, encoding="utf-8") as database_handle:
                database_url = database_handle.read().strip()
        except (OSError, UnicodeError):
            raise RuntimeError("OCWP_DATABASE_URL_FILE could not be read") from None
        if not database_url or "\x00" in database_url:
            raise RuntimeError("OCWP_DATABASE_URL_FILE must contain a non-empty URL")
    return (
        database_url
        if database_url is not None
        else "postgresql+psycopg://ocwp:ocwp@localhost:5432/ocwp"
    )


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str = "development"
    database_url: str = "postgresql+psycopg://ocwp:ocwp@localhost:5432/ocwp"
    log_level: str = "INFO"
    auth_secret: str = _DEFAULT_DEV_SECRET
    cutover_enabled: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        environment = os.getenv("OCWP_ENVIRONMENT", "development")
        auth_secret = os.getenv("OCWP_AUTH_SECRET")
        if auth_secret is None and (secret_file := os.getenv("OCWP_AUTH_SECRET_FILE")):
            try:
                with open(secret_file, encoding="utf-8") as secret_handle:
                    auth_secret = secret_handle.read().strip()
            except OSError as exc:
                raise RuntimeError("OCWP_AUTH_SECRET_FILE could not be read") from exc
        auth_secret = auth_secret or _DEFAULT_DEV_SECRET
        if environment == "production" and auth_secret == _DEFAULT_DEV_SECRET:
            raise RuntimeError(
                "OCWP_AUTH_SECRET or OCWP_AUTH_SECRET_FILE is required in production"
            )
        return cls(
            environment=environment,
            database_url=database_url_from_env(),
            log_level=os.getenv("OCWP_LOG_LEVEL", "INFO").upper(),
            auth_secret=auth_secret,
            cutover_enabled=os.getenv("OCWP_CUTOVER_ENABLED", "false") == "true",
        )
