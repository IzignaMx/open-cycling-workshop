"""Native browser qualification only: disposable SQLite surrogate, never configured data."""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "services/platform/src"))


def main() -> None:
    import uvicorn
    from cycling_workshop.app import create_app
    from cycling_workshop.db.base import Base
    from cycling_workshop.db.registry import register_models
    from cycling_workshop.identity.models import UserRecord
    from cycling_workshop.identity.security import PasswordService
    from cycling_workshop.settings import Settings
    from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker

    with tempfile.TemporaryDirectory(prefix="ocwp_baseline_browser_test_") as directory:
        url = f"sqlite:///{directory}/baseline_test.sqlite"
        register_models()
        engine = create_engine(url, connect_args={"check_same_thread": False})
        try:
            Base.metadata.create_all(engine)
            # Seed only the session bound to this internally created temporary DB.
            # Shared URL-taking reset/seed tools remain PostgreSQL-only; there is
            # no SQLite opt-out or caller-supplied persistent target here.
            with Session(engine) as session:
                password_hash = PasswordService().hash("ocwp-e2e-password")
                fixtures = (
                    (1, "OCWP Browser E2E", "Taller E2E", "Admin E2E", 0),
                    (101, "Cutover browser fixture", "Cutover fixture", "Cutover fixture", 1),
                )
                for first, organization_name, location_name, display_name, floor in fixtures:
                    organization_id = f"00000000-0000-7000-8000-{first:012d}"
                    location_id = f"00000000-0000-7000-8000-{first + 1:012d}"
                    user_id = f"00000000-0000-7000-8000-{first + 2:012d}"
                    session.add(
                        OrganizationRecord(
                            id=organization_id,
                            name=organization_name,
                            minimum_write_protocol=floor,
                        )
                    )
                    session.flush()
                    session.add(
                        LocationRecord(
                            id=location_id,
                            organization_id=organization_id,
                            name=location_name,
                        )
                    )
                    session.flush()
                    session.add(
                        UserRecord(
                            id=user_id,
                            organization_id=organization_id,
                            location_id=location_id,
                            username="e2e-admin",
                            display_name=display_name,
                            password_hash=password_hash,
                            capabilities=["*"],
                            is_active=True,
                        )
                    )
                session.commit()
            app = create_app(
                Settings(environment="test", database_url=url, cutover_enabled=True),
                session_factory=sessionmaker(engine),
            )
            uvicorn.run(app, host="127.0.0.1", port=8007, log_level="warning", access_log=False)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
