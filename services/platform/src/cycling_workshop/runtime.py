from __future__ import annotations

from cycling_workshop.app import create_app
from cycling_workshop.db.session import build_engine, build_session_factory
from cycling_workshop.settings import Settings

settings = Settings.from_env()
engine = build_engine(settings)
session_factory = build_session_factory(engine)
app = create_app(settings=settings, session_factory=session_factory)
