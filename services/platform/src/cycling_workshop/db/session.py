from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from cycling_workshop.db.url import normalize_database_url
from cycling_workshop.settings import Settings


def build_engine(settings: Settings | None = None, *, database_url: str | None = None) -> Engine:
    settings = settings or Settings.from_env()
    url = normalize_database_url(database_url or settings.database_url)
    return create_engine(url, pool_pre_ping=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def session_scope(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
