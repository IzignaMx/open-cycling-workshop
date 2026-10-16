from __future__ import annotations

import json

import pytest

from scripts.ci import local_compose_smoke as smoke

PROJECT = "ocwp-smoke-0123456789ab"
CONTAINER = "a" * 64
COMMAND = ["docker", "compose", "-p", PROJECT, "-f", "/fixture/compose.yml"]
START = 1_792_108_800_000_000_000
END = START + 10_000_000_000
SECRET = "never-emit-arbitrary-private-text"
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhIn0.signature"


def state(**changes):
    return {
        "id": CONTAINER,
        "project": PROJECT,
        "service": "api",
        "status": "running",
        "running": True,
        "restarting": False,
        "exit_code": 0,
        "oom_killed": False,
        "restart_count": 0,
        "error_present": False,
        "started_at": "2026-10-16T00:00:00.123456789Z",
        "finished_at": "0001-01-01T00:00:00Z",
    } | changes


def event(**changes):
    return {
        "id": CONTAINER,
        "type": "container",
        "action": "die",
        "time_nano": START + 1,
        "exit_code": "143",
        "signal": "",
    } | changes


def fixture(monkeypatch, *, inspect=None, events=None):
    calls = []

    def capture(parts, **kwargs):
        calls.append((parts, kwargs))
        if "ps" in parts:
            output = CONTAINER + "\n"
        elif "inspect" in parts:
            output = json.dumps(state() if inspect is None else inspect)
        else:
            assert parts[:2] == ["docker", "events"]
            output = "\n".join(json.dumps(row) for row in (events or []))
        return {"status": "captured", "returncode": 0, "output": output}

    monkeypatch.setattr(smoke, "diagnostic_capture", capture)
    monkeypatch.setattr(smoke.time, "time_ns", lambda: START)
    collector = smoke.RestartDiagnostics(COMMAND, env={"PATH": "/bin"}, secrets=[SECRET])
    record = {}
    collector.capture(record, "before_stop")
    monkeypatch.setattr(smoke.time, "time_ns", lambda: END)
    return collector, record, calls


def test_restart_diagnostics_are_project_bound_closed_and_finite(monkeypatch):
    collector, record, calls = fixture(
        monkeypatch,
        inspect=state(private=SECRET, config={"Env": JWT}),
        events=[
            event(attributes={"private": SECRET}, unknown=JWT),
            event(id="b" * 64),
            event(type="image"),
            event(action=SECRET),
            event(time_nano=END + 1),
            event(time_nano=START - 1),
        ],
    )
    collector.capture(record, "after_start")
    collector.capture(record, "failed")
    result = record["diagnostics"]
    assert result["container_id"] == CONTAINER
    assert result["snapshots"]["after_start"]["state"] == {
        k: v for k, v in state().items() if k not in ("id", "project", "service")
    }
    assert result["events"]["status"] == "captured"
    assert result["events"]["events"] == [
        {"action": "die", "time_nano": START + 1, "exit_code": 143, "signal": None}
    ]
    assert result["events"]["window_start_ns"] == START
    assert result["events"]["window_end_ns"] == END
    assert SECRET not in json.dumps(record) and JWT not in json.dumps(record)
    assert calls[0][0] == [*COMMAND, "ps", "--all", "--quiet", "api"]
    for parts, kwargs in calls:
        assert kwargs == {"env": {"PATH": "/bin"}, "secrets": [SECRET]}
        if "inspect" in parts:
            assert parts[:4] == ["docker", "inspect", "--type", "container"]
            assert parts[-1] == CONTAINER
            template = parts[parts.index("--format") + 1]
            assert ".Config.Env" not in template and "{{json .}}" not in template
            assert "{{json .State.Error}}" not in template
        if "events" in parts:
            assert ["--since", f"{START // 10**9}.{START % 10**9:09d}"] == parts[2:4]
            assert ["--until", f"{END // 10**9}.{END % 10**9:09d}"] == parts[4:6]
            assert f"container={CONTAINER}" in parts and "type=container" in parts
            assert f"label=com.docker.compose.project={PROJECT}" in parts
            assert "{{json .}}" not in parts


@pytest.mark.parametrize(
    "changes",
    [
        {"project": "operator-project"},
        {"service": "worker"},
        {"id": "b" * 64},
        {"started_at": SECRET},
        {"finished_at": "2026-99-16T00:00:00Z"},
        {"running": 1},
        {"exit_code": True},
        {"oom_killed": SECRET},
        {"restart_count": -1},
        {"error_present": SECRET},
        {"status": SECRET},
    ],
)
def test_invalid_or_foreign_inspect_is_not_retained(monkeypatch, changes):
    collector, record, calls = fixture(monkeypatch, inspect=state(**changes))
    collector.capture(record, "failed")
    assert record["diagnostics"]["snapshots"]["before_stop"]["status"] == "invalid_output"
    assert "container_id" not in record["diagnostics"]
    assert all("events" not in parts for parts, _ in calls)
    assert SECRET not in json.dumps(record) and "operator-project" not in json.dumps(record)


@pytest.mark.parametrize("status", ["timeout", "output_limit", "unavailable"])
def test_capture_failure_is_explicit_and_never_retains_raw_output(monkeypatch, status):
    collector, record, _ = fixture(monkeypatch)
    monkeypatch.setattr(
        smoke,
        "diagnostic_capture",
        lambda *a, **k: {
            "status": status,
            "output": SECRET + JWT,
        },
    )
    collector.capture(record, "failed")
    assert record["diagnostics"]["snapshots"]["failed"] == {"status": status}
    assert record["diagnostics"]["events"] == {"status": status}
    assert SECRET not in json.dumps(record) and JWT not in json.dumps(record)


def test_diagnostics_distinguish_stop143_start_and_later_oom_without_raw_error(monkeypatch):
    collector, record, _ = fixture(
        monkeypatch,
        inspect=state(
            status="exited",
            running=False,
            exit_code=143,
            error_present=True,
        ),
        events=[
            event(),
            event(action="start", exit_code=""),
            event(action="oom", exit_code=""),
            event(exit_code="137"),
        ],
    )
    collector.capture(record, "after_stop")
    collector.capture(record, "failed")
    assert record["diagnostics"]["snapshots"]["after_stop"]["state"]["exit_code"] == 143
    assert record["diagnostics"]["snapshots"]["failed"]["state"]["error_present"] is True
    assert [e["action"] for e in record["diagnostics"]["events"]["events"]] == [
        "die",
        "start",
        "oom",
        "die",
    ]
    assert "cause" not in json.dumps(record)


def test_event_count_overflow_discards_all_events(monkeypatch):
    collector, record, _ = fixture(monkeypatch, events=[event()] * 129)
    collector.capture(record, "complete")
    assert record["diagnostics"]["events"] == {"status": "event_limit"}


def test_bad_clock_or_capture_does_not_raise_or_echo(monkeypatch):
    collector, record, _ = fixture(monkeypatch)

    def unavailable(*args, **kwargs):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(smoke.time, "time_ns", unavailable)
    monkeypatch.setattr(smoke, "diagnostic_capture", unavailable)
    collector.capture(record, "failed")
    assert SECRET not in json.dumps(record)
    assert record["diagnostics"]["snapshots"]["failed"]["status"] == "unavailable"


@pytest.mark.parametrize("failed_phase", [None, "stopping", "starting", "waiting_ready"])
def test_qualifier_captures_in_order_and_preserves_original_failure(monkeypatch, failed_phase):
    from subprocess import CompletedProcess

    calls = []
    cycles = []
    original = RuntimeError("first qualification failure")

    def step(phase):
        calls.append(phase)
        if phase == failed_phase:
            raise original

    def compose(command, service):
        assert service == "api"
        step("stopping" if command == "stop" else "starting")
        return CompletedProcess([], 0, stdout=SECRET + JWT, stderr=SECRET)

    def capture(record, phase):
        calls.append(phase)
        assert record is cycles[-1]

    def request(base, path):
        step("checking_outage" if path.endswith("/me") else "checking_static")
        return (502, {}, b"outage") if path.endswith("/me") else (200, {}, b"pwa")

    monkeypatch.setattr(smoke, "request", request)
    monkeypatch.setattr(smoke, "wait_ready", lambda base: step("waiting_ready"))
    expected = [
        "before_stop",
        "stopping",
        "after_stop",
        "checking_outage",
        "checking_static",
        "starting",
        "after_start",
        "waiting_ready",
        "checking_branding",
        "complete",
    ]
    if failed_phase:
        with pytest.raises(RuntimeError) as error:
            smoke.qualify_api_restarts(
                compose, "fixture", lambda: step("checking_branding"), cycles, diagnostics=capture
            )
        assert error.value is original
        assert calls == [*expected[: expected.index(failed_phase) + 1], "failed"]
        assert cycles[-1]["phase"] == failed_phase
    else:
        smoke.qualify_api_restarts(
            compose, "fixture", lambda: step("checking_branding"), cycles, diagnostics=capture
        )
        assert calls == expected * 3
        for cycle in cycles:
            for command in ("stop", "start"):
                result = cycle["commands"][command]
                assert result["returncode"] == 0 and result["status"] == "passed"
                assert result["finished_monotonic"] >= result["started_monotonic"]
    assert SECRET not in json.dumps(cycles) and JWT not in json.dumps(cycles)


@pytest.mark.parametrize("failure", [False, True])
def test_callback_errors_do_not_skip_qualification_or_replace_failure(monkeypatch, failure):
    original = RuntimeError("original")
    commands = []
    cycles = []

    def broken(*args):
        raise RuntimeError(SECRET)

    def ready(base):
        if failure:
            raise original

    monkeypatch.setattr(
        smoke,
        "request",
        lambda base, path: (502, {}, b"") if path.endswith("/me") else (200, {}, b""),
    )
    monkeypatch.setattr(smoke, "wait_ready", ready)
    if failure:
        with pytest.raises(RuntimeError) as error:
            smoke.qualify_api_restarts(
                lambda *args: commands.append(args),
                "fixture",
                lambda: None,
                cycles,
                diagnostics=broken,
            )
        assert error.value is original
        assert commands == [("stop", "api"), ("start", "api")]
    else:
        smoke.qualify_api_restarts(
            lambda *args: commands.append(args), "fixture", lambda: None, cycles, diagnostics=broken
        )
        assert commands == [("stop", "api"), ("start", "api")] * 3
    assert SECRET not in json.dumps(cycles)


def test_main_connects_collector_without_adding_retries_or_checks():
    source = (smoke.ROOT / "scripts/ci/local_compose_smoke.py").read_text()
    main = source.split("def main()", 1)[1]
    assert "RestartDiagnostics(command, env=env, secrets=secrets).capture" in main
    assert "diagnostics=restart_diagnostics" in main
    assert "range(1, 4)" in source
    assert "time.monotonic() + 180" in source
    assert "time.sleep(2)" in source
    assert "urlopen(req, timeout=5)" in source
    assert main.count("checks.append(") == 11
    assert main.index("qualify_api_restarts(") < main.index("branding_probe.cleanup()")


@pytest.mark.parametrize("bad_time", [None, True, -1, 0, 2**63, float("inf"), float("nan"), SECRET])
def test_invalid_wall_clock_is_omitted_and_no_unbounded_event_query(monkeypatch, bad_time):
    collector, _, calls = fixture(monkeypatch)
    record = {}
    monkeypatch.setattr(smoke.time, "time_ns", lambda: bad_time)
    collector.capture(record, "before_stop")
    collector.capture(record, "failed")
    assert "window_start_ns" not in record["diagnostics"]
    assert record["diagnostics"]["events"] == {"status": "invalid_window"}
    assert all("events" not in parts for parts, _ in calls)
    json.dumps(record, allow_nan=False)


@pytest.mark.parametrize(
    "parts",
    [
        ["docker", "compose", "-p", "operator-project"],
        ["docker", "compose"],
    ],
)
def test_invalid_project_never_launches_probe(monkeypatch, parts):
    calls = []
    monkeypatch.setattr(smoke, "diagnostic_capture", lambda *a, **k: calls.append(a))
    collector = smoke.RestartDiagnostics(parts, env={}, secrets=[])
    record = {}
    collector.capture(record, "before_stop")
    assert not calls and "container_id" not in record["diagnostics"]


@pytest.mark.parametrize("raw", [CONTAINER[:12], CONTAINER + "\n" + "b" * 64, SECRET, ""])
def test_container_resolution_refuses_partial_multiple_or_untrusted_ids(monkeypatch, raw):
    calls = []

    def capture(parts, **kwargs):
        calls.append(parts)
        return {"status": "captured", "returncode": 0, "output": raw}

    monkeypatch.setattr(smoke, "diagnostic_capture", capture)
    collector = smoke.RestartDiagnostics(COMMAND, env={}, secrets=[])
    record = {}
    collector.capture(record, "before_stop")
    collector.capture(record, "failed")
    assert len(calls) == 1
    assert "container_id" not in record["diagnostics"]
    assert SECRET not in json.dumps(record)


@pytest.mark.parametrize("payload", ["{", "[]", "null", SECRET])
def test_invalid_event_json_discards_every_partial_row(monkeypatch, payload):
    collector, record, _ = fixture(monkeypatch)
    original_capture = smoke.diagnostic_capture

    def capture(parts, **kwargs):
        if "events" in parts:
            return {
                "status": "captured",
                "returncode": 0,
                "output": json.dumps(event()) + "\n" + payload,
            }
        return original_capture(parts, **kwargs)

    monkeypatch.setattr(smoke, "diagnostic_capture", capture)
    collector.capture(record, "complete")
    assert record["diagnostics"]["events"] == {"status": "invalid_output"}
    assert SECRET not in json.dumps(record)


@pytest.mark.parametrize("code", [1, -9])
def test_failed_diagnostic_command_discards_even_complete_output(monkeypatch, code):
    collector, record, _ = fixture(monkeypatch)
    monkeypatch.setattr(
        smoke,
        "diagnostic_capture",
        lambda *a, **k: {
            "status": "captured",
            "returncode": code,
            "output": SECRET + JWT,
        },
    )
    collector.capture(record, "failed")
    assert record["diagnostics"]["snapshots"]["failed"] == {"status": "command_failed"}
    assert record["diagnostics"]["events"] == {"status": "command_failed"}
    assert SECRET not in json.dumps(record) and JWT not in json.dumps(record)
