"""Static documentation contracts, never physical-device qualification."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "docs/11-device-qualification/"
PROTOCOL = BASE + "2026-10-31-safe-tier1-protocol.md"
RESULTS = BASE + "2026-10-31-safe-tier1-results.md"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_current_protocol_exists_and_declares_unexecuted_scope() -> None:
    text = read(PROTOCOL)
    assert "NO EJECUTADO" in text
    assert "documentación" in text
    assert "R01-T035" in text and "100,000" in text


def test_current_protocol_has_eight_safe_cases() -> None:
    text = read(PROTOCOL)
    assert re.findall(r"^### (T[1-8]) ", text, re.M) == [f"T{i}" for i in range(1, 9)]


def test_new_results_are_pending_on_both_devices() -> None:
    text = read(RESULTS)
    rows = re.findall(r"^\|\s+(T[1-8])\s+\|\s+PENDIENTE\s+\|\s+PENDIENTE\s+\|", text, re.M)
    assert rows == [f"T{i}" for i in range(1, 9)]
    assert "NO EJECUTADO" in text
    assert "Copiar esta plantilla a un nuevo registro" in text
    assert "conservar esta plantilla con todos los casos PENDIENTE" in text


def test_preflight_requires_preserving_unsynced_work_and_no_default_login() -> None:
    text = read(PROTOCOL)
    for phrase in (
        "mutaciones pendientes",
        "IndexedDB",
        "no incluye",
        "No hay contraseña predeterminada",
    ):
        assert phrase in text
    assert "2026-10-14-backup-restore.md" in text


def test_real_runtime_and_secure_origin_are_required() -> None:
    text = read(PROTOCOL)
    assert "2026-10-14-local-runtime.md" in text
    assert "http://localhost:8080" in text
    assert "HTTPS" in text and "contexto seguro" in text
    assert "window.isSecureContext" in text
    assert "base general 44" in text
    assert "primarios 56" in text and "secundarios\nmínimo 48" in text


def test_no_executable_destructive_or_security_bypass_steps() -> None:
    text = read(PROTOCOL)
    assert "```" not in text  # Preconditions and observations, not deployment commands.
    for forbidden in ("down -v", "chrome://flags", "--no-sandbox", "--host 0.0.0.0"):
        assert forbidden not in text
    for forbidden in ("compose-smoke-password", "adb reverse", "winget install"):
        assert forbidden not in text


def test_disallowed_experiments_remain_separate() -> None:
    text = read(PROTOCOL)
    for phrase in ("conflicto", "reinstalación", "presión", "NO EJECUTAR", "autorización"):
        assert phrase.lower() in text.lower()
    assert "no desinstalar" in text
    assert "no llenar el disco" in text


def test_network_loss_is_observed_not_assumed() -> None:
    text = read(PROTOCOL)
    assert "modo avión no demuestra" in text
    assert "USB" in text and "servidor inaccesible" in text
    assert "no usar cerrar sesión" in text


def test_results_require_source_and_privacy_bound_evidence() -> None:
    text = read(RESULTS)
    for phrase in ("SHA", "origen", "versiones", "sanitizada", "NO EJECUTADO"):
        assert phrase in text
    assert "no publicar" in text


def test_historical_documents_warn_before_old_commands() -> None:
    for name in ("2026-08-31-tier1-protocol.md", "2026-08-31-tier1-results.md"):
        text = read(BASE + name)
        warning = text.index("HISTÓRICO; NO EJECUTAR")
        assert warning < 300
        assert "compose-smoke-password" not in text
        assert "2026-10-31-safe-tier1-protocol.md" in text[:1500]
        assert "2026-10-31-safe-tier1-results.md" in text[:1500]


def test_active_checklist_routes_to_safe_protocol() -> None:
    text = read("MANUAL-ACTIONS-CHECKLIST.md")
    assert PROTOCOL in text and RESULTS in text
    assert "**Ejecutar el protocolo** `docs/11-device-qualification/2026-08-31" not in text
    assert "**Protocolo operativo listo (2026-08-31):** ejecuta" not in text
    assert "No cierra R01-T035" in text


def test_execution_state_points_to_current_documents_without_lan_override() -> None:
    text = read("docs/10-spec-development/execution-state.yaml")
    section = text.split("\ntier1_protocol:\n", 1)[1].split("\nnext_focus:", 1)[0]
    assert f"document: {PROTOCOL}" in section
    assert f"results_template: {RESULTS}" in section
    assert "lan_override:" not in section
    assert "physical_execution: not_performed" in section
    assert "R01_T035: open_requires_separate_100k_and_device_evidence" in section


def test_current_document_relative_links_exist() -> None:
    for path in (PROTOCOL, RESULTS):
        for target in re.findall(r"\]\(([^)]+)\)", read(path)):
            assert not target.startswith(("http:", "https:"))
            assert (ROOT / path).parent.joinpath(target.split("#", 1)[0]).is_file(), target
