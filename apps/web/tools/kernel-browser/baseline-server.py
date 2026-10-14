"""Native browser qualification only: disposable SQLite surrogate, never configured data."""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "services/platform/src"))
sys.path.insert(0, str(ROOT / "scripts/e2e"))


def main() -> None:
    import uvicorn
    from cycling_workshop.app import create_app
    from cycling_workshop.db.base import Base
    from cycling_workshop.db.registry import register_models
    from cycling_workshop.identity.models import UserRecord
    from cycling_workshop.settings import Settings
    from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
    from prepare_e2e_database import seed_browser_identity
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker

    with tempfile.TemporaryDirectory(prefix="ocwp_baseline_browser_test_") as directory:
        url = f"sqlite:///{directory}/baseline_test.sqlite"
        register_models()
        engine = create_engine(url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        seed_browser_identity(url)
        # Separate disposable floor-1 tenant: the original null/legacy fixture
        # stays at floor 0. This is test seeding, never installation activation.
        with Session(engine) as session:
            original = session.get(UserRecord, "00000000-0000-7000-8000-000000000003")
            assert original is not None
            session.add(
                OrganizationRecord(
                    id="00000000-0000-7000-8000-000000000101",
                    name="Cutover browser fixture",
                    minimum_write_protocol=1,
                )
            )
            session.flush()
            session.add(
                LocationRecord(
                    id="00000000-0000-7000-8000-000000000102",
                    organization_id="00000000-0000-7000-8000-000000000101",
                    name="Cutover fixture",
                )
            )
            session.flush()
            session.add(
                UserRecord(
                    id="00000000-0000-7000-8000-000000000103",
                    organization_id="00000000-0000-7000-8000-000000000101",
                    location_id="00000000-0000-7000-8000-000000000102",
                    username="e2e-admin",
                    display_name="Cutover fixture",
                    password_hash=original.password_hash,
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


if __name__ == "__main__":
    main()
