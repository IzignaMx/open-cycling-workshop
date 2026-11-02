"""Read-only admission checks, not runtime isolation qualification."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch


def load_preflight():
    path = Path(__file__).with_name("preflight.py")
    spec = importlib.util.spec_from_file_location("m2_preflight_test_subject", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_missing_commands_are_explicit_and_execution_is_denied():
    module = load_preflight()
    report = module.assess(module.EnvironmentFacts(False, False, True))
    assert report.execution_authorized is False
    assert {"docker-unavailable", "psql-unavailable"} <= set(report.unmet)


def test_command_presence_never_proves_runtime_policy():
    module = load_preflight()
    report = module.assess(module.EnvironmentFacts(True, True, True))
    assert report.execution_authorized is False
    assert set(module.REQUIRED_RUNTIME_EVIDENCE) <= set(report.unmet)
    assert "docker-unavailable" not in report.unmet
    assert "psql-unavailable" not in report.unmet


def test_missing_suspend_inclusive_clock_is_blocked():
    module = load_preflight()
    report = module.assess(module.EnvironmentFacts(True, True, False))
    assert "suspend-inclusive-clock-unavailable" in report.unmet
    assert not report.execution_authorized


def test_probe_only_checks_command_presence_and_clock_support():
    module = load_preflight()
    with patch.object(module.shutil, "which", side_effect=[None, "/ignored/psql"]) as which:
        facts = module.probe()
    assert which.call_args_list == [(("docker",),), (("psql",),)]
    assert facts.docker_available is False
    assert facts.psql_available is True


def test_public_entry_is_nonzero_and_secret_free(capsys):
    module = load_preflight()
    with patch.object(module, "probe", return_value=module.EnvironmentFacts(True, True, True)):
        assert module.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["execution_authorized"] is False
    assert payload["status"] == "blocked"
    assert set(payload) == {"execution_authorized", "status", "unmet"}


def test_environment_dsn_and_enable_flags_do_not_change_admission(monkeypatch):
    module = load_preflight()
    facts = module.EnvironmentFacts(True, True, True)
    baseline = module.assess(facts)
    monkeypatch.setenv("DATABASE_URL", "must-not-be-read")
    monkeypatch.setenv("M2_ENABLE", "true")
    assert module.assess(facts) == baseline


def test_gate_inventory_requires_real_enforcement_and_teardown():
    module = load_preflight()
    assert set(module.REQUIRED_RUNTIME_EVIDENCE) == {
        "postgresql18-transaction-evidence-missing",
        "verified-tls-endpoint-evidence-missing",
        "separate-nonroot-process-evidence-missing",
        "enforced-egress-and-mount-policy-evidence-missing",
        "enforced-resource-and-transport-limits-evidence-missing",
        "run-deadline-and-clock-integrity-evidence-missing",
        "synthetic-owned-database-evidence-missing",
        "verified-teardown-receipt-missing",
    }
