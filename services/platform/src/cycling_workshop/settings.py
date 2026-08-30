from __future__ import annotations

from dataclasses import dataclass
import os

_DEFAULT_DEV_SECRET = "development-only-secret-change-before-production-0000000000000000"


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str = "development"
    database_url: str = "postgresql+psycopg://ocwp:ocwp@localhost:5432/ocwp"
    log_level: str = "INFO"
    auth_secret: str = _DEFAULT_DEV_SECRET

    @classmethod
    def from_env(cls) -> "Settings":
        environment = os.getenv("OCWP_ENVIRONMENT", "development")
        auth_secret = os.getenv("OCWP_AUTH_SECRET")
        if auth_secret is None and (secret_file := os.getenv("OCWP_AUTH_SECRET_FILE")):
            try:
                auth_secret = open(secret_file, encoding="utf-8").read().strip()
            except OSError as exc:
                raise RuntimeError("OCWP_AUTH_SECRET_FILE could not be read") from exc
        auth_secret = auth_secret or _DEFAULT_DEV_SECRET
        if environment == "production" and auth_secret == _DEFAULT_DEV_SECRET:
            raise RuntimeError("OCWP_AUTH_SECRET or OCWP_AUTH_SECRET_FILE is required in production")
        return cls(
            environment=environment,
            database_url=os.getenv(
                "OCWP_DATABASE_URL",
                "postgresql+psycopg://ocwp:ocwp@localhost:5432/ocwp",
            ),
            log_level=os.getenv("OCWP_LOG_LEVEL", "INFO").upper(),
            auth_secret=auth_secret,
        )
