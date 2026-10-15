"""Failure evidence must be bounded, private and preserve both failure causes."""

from __future__ import annotations

import http.client
import json
import sys
from unittest.mock import MagicMock

import pytest

from scripts.ci import inventory_edge_probe as probe

CANARY = "private-query-header-body-environment-canary"


@pytest.mark.parametrize(
    "program,timeout,reason,exit_code",
    [
        (f"import sys; print({CANARY!r}); sys.exit(7)", 2, "exit", 7),
        (f"import time; print({CANARY!r}, flush=True); time.sleep(10)", 0.1, "timeout", None),
        (f"print({CANARY!r} * 10000)", 2, "output_limit", None),
    ],
)
def test_subprocess_failure_never_retains_raw_output(program, timeout, reason, exit_code):
    with pytest.raises(probe.CommandFailure) as caught:
        probe.run_bounded_command([sys.executable, "-c", program], timeout=timeout)
    assert caught.value.reason == reason
    assert caught.value.exit_code == exit_code
    assert CANARY not in str(caught.value)
    assert not hasattr(caught.value, "stdout") and not hasattr(caught.value, "stderr")


def test_bounded_subprocess_preserves_success_output():
    assert probe.run_bounded_command(
        [sys.executable, "-c", "print('safe version')"], timeout=2
    ) == ("safe version\n")


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_readiness_failure_preserves_safe_original_and_separate_cleanup(
    tmp_path, monkeypatch, cleanup_fails
):
    calls = []

    def docker(*args, **kwargs):
        calls.append(args[0])
        if args[0] == "inspect":
            return '{"status":"exited","exit_code":1,"oom_killed":false}'
        if args[0] == "rm" and cleanup_fails:
            raise probe.CommandFailure("exit", 9)
        return "synthetic-container"

    monkeypatch.setattr(probe, "ThreadingHTTPServer", MagicMock())
    monkeypatch.setattr(probe.threading, "Thread", MagicMock())
    monkeypatch.setattr(probe, "docker", docker)
    monkeypatch.setattr(probe.time, "monotonic", MagicMock(side_effect=[0, 0, 31]))
    monkeypatch.setattr(probe.time, "sleep", lambda _: None)
    monkeypatch.setattr(probe, "request", MagicMock(side_effect=http.client.BadStatusLine(CANARY)))
    with pytest.raises(probe.EdgeProbeFailure) as caught:
        probe.probe("Caddyfile", tmp_path)
    failure = caught.value.evidence
    assert failure["phase"] == "readiness"
    assert failure["error"] == "assertion"
    assert failure["last_health"] == {"error": "http_error"}
    assert failure["container"] == {"status": "exited", "exit_code": 1, "oom_killed": False}
    assert failure["cleanup"]["upstream"] is True
    assert failure["cleanup"]["container"] is (not cleanup_fails)
    if cleanup_fails:
        assert failure["cleanup"]["container_error"] == {
            "error": "command",
            "reason": "exit",
            "exit_code": 9,
        }
    assert calls == ["run", "inspect", "logs", "rm"]
    assert CANARY not in json.dumps(failure) and CANARY not in str(caught.value)


def test_untrusted_container_state_is_not_copied(monkeypatch):
    monkeypatch.setattr(
        probe,
        "docker",
        lambda *args, **kwargs: json.dumps(
            {"status": CANARY, "exit_code": 0, "oom_killed": False, "Env": CANARY}
        ),
    )
    assert probe.container_state("synthetic") == {"status": "unavailable"}


def test_main_writes_only_safe_failure_and_still_exits_nonzero(tmp_path, monkeypatch):
    for name in (
        "infra/edge/Caddyfile",
        "infra/edge/Caddyfile.lan",
        "infra/edge/routes.caddy",
        "scripts/ci/inventory_edge_probe.py",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic source")
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(probe, "docker", lambda *args, **kwargs: "synthetic")
    failure = {
        "configuration": "Caddyfile",
        "phase": "readiness",
        "error": "assertion",
        "cleanup": {"upstream": True, "container": True},
    }
    monkeypatch.setattr(probe, "probe", MagicMock(side_effect=probe.EdgeProbeFailure(failure)))
    with pytest.raises(SystemExit) as caught:
        probe.main()
    assert caught.value.code != 0
    result = json.loads(
        (tmp_path / "artifacts/inventory-read/edge-runtime-evidence.json").read_text()
    )
    assert result["status"] == "failed" and result["cases"] == []
    assert result["failure"] == failure


def test_startup_log_hints_are_fixed_categories_never_raw_text(monkeypatch):
    raw = (
        CANARY + " Error: adapting config using caddyfile: permission denied; "
        "listen tcp: address already in use; dial tcp: connection refused"
    )
    monkeypatch.setattr(probe, "docker", lambda *args, **kwargs: raw)
    result = probe.startup_log_hints("synthetic")
    assert result == {
        "status": "captured",
        "categories": [
            "config_error",
            "permission_denied",
            "address_in_use",
            "bind_listen_error",
            "upstream_connection_refused",
        ],
    }
    assert CANARY not in json.dumps(result)


def test_failed_startup_log_capture_is_safe_and_explicit(monkeypatch):
    monkeypatch.setattr(
        probe, "docker", MagicMock(side_effect=probe.CommandFailure("output_limit"))
    )
    assert probe.startup_log_hints("synthetic") == {
        "status": "unavailable",
        "error": "command",
        "reason": "output_limit",
        "exit_code": None,
    }


@pytest.mark.parametrize(
    "error,category",
    [
        (ConnectionRefusedError(CANARY), "connection_refused"),
        (TimeoutError(CANARY), "timeout"),
        (OSError(CANARY), "os_error"),
    ],
)
def test_safe_health_error_keeps_useful_fixed_distinctions(error, category):
    assert probe.safe_error(error) == {"error": category}


@pytest.mark.parametrize("original_failure", [False, True])
def test_directory_cleanup_does_not_mask_probe_failure(tmp_path, monkeypatch, original_failure):
    for name in (
        "infra/edge/Caddyfile",
        "infra/edge/Caddyfile.lan",
        "infra/edge/routes.caddy",
        "scripts/ci/inventory_edge_probe.py",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic")

    class Directory:
        def __enter__(self):
            return str(tmp_path)

        def __exit__(self, *args):
            raise OSError(CANARY)

    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(probe, "docker", lambda *args, **kwargs: "synthetic")
    monkeypatch.setattr(probe.tempfile, "TemporaryDirectory", lambda **kwargs: Directory())
    failure = {
        "configuration": "Caddyfile",
        "phase": "readiness",
        "error": "assertion",
        "cleanup": {"upstream": True, "container": True},
    }
    monkeypatch.setattr(
        probe,
        "probe",
        MagicMock(
            side_effect=probe.EdgeProbeFailure(failure) if original_failure else None,
            return_value={"configuration": "synthetic"},
        ),
    )
    with pytest.raises(SystemExit) as caught:
        probe.main()
    result = json.loads(
        (tmp_path / "artifacts/inventory-read/edge-runtime-evidence.json").read_text()
    )
    assert caught.value.code != 0 and result["status"] == "failed"
    assert result["failure"]["phase"] == (
        "readiness" if original_failure else "temporary_directory"
    )
    assert result["failure"]["cleanup"]["temporary_directory"] is False
    assert result["failure"]["cleanup"]["temporary_directory_error"] == {"error": "os_error"}
    if original_failure:
        assert result["failure"]["error"] == "assertion"
        assert result["cases"] == []
    else:
        assert len(result["cases"]) == 2
    assert CANARY not in json.dumps(result) and CANARY not in str(caught.value)


def test_setup_failure_is_safe_and_still_attempts_container_cleanup(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "ThreadingHTTPServer", MagicMock(side_effect=OSError(CANARY)))
    docker = MagicMock(return_value="synthetic")
    monkeypatch.setattr(probe, "docker", docker)
    with pytest.raises(probe.EdgeProbeFailure) as caught:
        probe.probe("Caddyfile", tmp_path)
    assert caught.value.evidence["phase"] == "setup"
    assert caught.value.evidence["error"] == "os_error"
    assert CANARY not in json.dumps(caught.value.evidence)
    assert any(call.args[0] == "rm" for call in docker.call_args_list)


def test_upstream_cleanup_attempts_close_and_join_after_shutdown_failure(tmp_path, monkeypatch):
    server, thread = MagicMock(), MagicMock()
    server.shutdown.side_effect = OSError(CANARY)
    monkeypatch.setattr(probe, "ThreadingHTTPServer", MagicMock(return_value=server))
    monkeypatch.setattr(probe.threading, "Thread", MagicMock(return_value=thread))
    monkeypatch.setattr(probe, "docker", MagicMock(return_value="synthetic"))
    monkeypatch.setattr(probe.time, "monotonic", MagicMock(side_effect=[0, 31]))
    with pytest.raises(probe.EdgeProbeFailure) as caught:
        probe.probe("Caddyfile", tmp_path)
    server.server_close.assert_called_once()
    thread.join.assert_called_once_with(timeout=5)
    failure = caught.value.evidence
    assert failure["phase"] == "readiness" and failure["error"] == "assertion"
    assert failure["cleanup"]["upstream"] is False
    assert failure["cleanup"]["upstream_errors"] == {"shutdown": {"error": "os_error"}}
    assert failure["cleanup"]["container"] is True
    assert CANARY not in json.dumps(failure)


def test_startup_hints_never_read_logs_after_private_probe_started(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "ThreadingHTTPServer", MagicMock())
    monkeypatch.setattr(probe.threading, "Thread", MagicMock())

    def docker(*args, **kwargs):
        assert args[0] != "logs"
        return "v2.11.7 synthetic" if args[0] == "exec" else "synthetic"

    monkeypatch.setattr(probe, "docker", docker)
    monkeypatch.setattr(
        probe, "request", MagicMock(side_effect=[(200, {}, b""), ConnectionRefusedError(CANARY)])
    )
    with pytest.raises(probe.EdgeProbeFailure) as caught:
        probe.probe("Caddyfile", tmp_path)
    assert caught.value.evidence["phase"] == "forwarding"
    assert "startup_log_hints" not in caught.value.evidence


def test_failed_thread_start_closes_real_base_server_without_waiting_forever():
    program = """
import json, socketserver, tempfile
from pathlib import Path
from scripts.ci import inventory_edge_probe as probe
server = socketserver.BaseServer(("unused", 0), None)
probe.ThreadingHTTPServer = lambda *args: server
class FailedThread:
    def __init__(self, **kwargs): pass
    def start(self): raise RuntimeError("synthetic start failure")
    def join(self, **kwargs): raise AssertionError("unstarted thread must not be joined")
probe.threading.Thread = FailedThread
probe.docker = lambda *args, **kwargs: "synthetic"
with tempfile.TemporaryDirectory() as directory:
    try:
        probe.probe("Caddyfile", Path(directory))
    except probe.EdgeProbeFailure as failure:
        print(json.dumps(failure.evidence))
"""
    result = json.loads(probe.run_bounded_command([sys.executable, "-c", program], timeout=1))
    assert result["phase"] == "setup" and result["error"] == "unexpected_error"
    assert result["cleanup"] == {"upstream": True, "container": True}
