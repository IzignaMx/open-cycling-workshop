from __future__ import annotations

from collections.abc import Generator

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker


def get_session(request: Request) -> Generator[Session]:
    factory: sessionmaker[Session] | None = request.app.state.session_factory
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database session factory is not configured",
        )
    with factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
