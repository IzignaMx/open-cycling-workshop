from cycling_workshop.cli import doctor_report
from cycling_workshop.settings import Settings


def test_doctor_report_checks_database_and_runtime() -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        log_level="WARNING",
        auth_secret="test-secret-that-is-long-enough-for-tests",
    )

    report = doctor_report(settings)

    assert report["ok"] is True
    assert report["environment"] == "test"
    assert report["checks"]["database"] == "ok"
    assert report["checks"]["auth_secret"] == "ok"
