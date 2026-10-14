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
    from cycling_workshop.settings import Settings
    from prepare_e2e_database import seed_browser_identity
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    with tempfile.TemporaryDirectory(prefix="ocwp_baseline_browser_test_") as directory:
        url = f"sqlite:///{directory}/baseline_test.sqlite"
        register_models()
        engine = create_engine(url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        seed_browser_identity(url)
        app = create_app(
            Settings(environment="test", database_url=url), session_factory=sessionmaker(engine)
        )
        uvicorn.run(app, host="127.0.0.1", port=8007, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
