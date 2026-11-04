from __future__ import annotations

import json

import pytest

from scripts.ci import prepare_browser_phase as phase

CID = "a" * 64
IMAGE = "sha256:" + "b" * 64
HEADER = "sl local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode"


def environment():
    return {
        "GITHUB_ACTIONS": "true",
        "GITHUB_JOB": "verify",
        "OCWP_E2E_SERVICE_ID": CID,
        **{key: phase.FIXTURE_DSN for key in phase.DSN_KEYS},
    }


def inspection():
    return {
        "id": CID,
        "image": "postgres:18.4-trixie",
        "image_id": IMAGE,
        "running": True,
        "health": "healthy",
        "network_mode": "fixture-network",
        "privileged": False,
        "binds": None,
        "volumes_from": None,
        "pid_mode": "",
        "cap_add": None,
        "devices": [],
        "mounts": [{"Type": "volume", "Destination": "/var/lib/postgresql"}],
        "ports": {"5432/tcp": [{"HostIp": "0.0.0.0", "HostPort": "5432"}]},
    }


def invoke(*, env=None, detail=None, listeners=False, sessions=0, failure=None):
    calls = []

    def inspect(args, env):
        assert env == environment()
        calls.append("inspect")
        assert args[:3] == ["docker", "--host", "unix:///var/run/docker.sock"]
        assert args[-1] == CID
        if failure == "inspect":
            raise RuntimeError("PRIVATE-CANARY")
        return json.dumps(inspection() if detail is None else detail)

    def idle():
        calls.append("listeners")
        return not listeners

    def clients():
        calls.append("sessions")
        if failure == "sessions":
            raise RuntimeError("PRIVATE-CANARY")
        return sessions

    def prepare(env):
        assert env == environment()
        calls.append("prepare")
        if failure == "prepare":
            raise RuntimeError("PRIVATE-CANARY")

    try:
        result = phase.prepare_phase(
            environment() if env is None else env,
            inspect=inspect,
            listeners_absent=idle,
            other_sessions=clients,
            prepare=prepare,
        )
        return calls, result
    except phase.FixtureRefused as error:
        assert str(error) == "Browser fixture preparation refused"
        assert error.__cause__ is None
        return calls, None


def test_verified_owned_service_prepares_once_in_fixed_order():
    calls, result = invoke()
    assert calls == ["inspect", "listeners", "sessions", "prepare"]
    assert result == {"prepared": True, "container_id": CID, "image_id": IMAGE}


@pytest.mark.parametrize(
    "key,value",
    [
        ("GITHUB_ACTIONS", "false"),
        ("GITHUB_JOB", "other"),
        ("OCWP_E2E_SERVICE_ID", "postgres"),
        ("OCWP_E2E_DATABASE_URL", "postgresql://other/anything_e2e"),
        ("OCWP_DATABASE_URL_FILE", "/private/canary"),
        ("PGHOST", "remote"),
        ("DOCKER_HOST", "tcp://remote"),
    ],
)
def test_ambient_spoof_or_redirect_refused_before_inspection(key, value):
    env = environment()
    env[key] = value
    assert invoke(env=env) == ([], None)


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", "c" * 64),
        ("image", "postgres:latest"),
        ("image_id", "not-immutable"),
        ("running", False),
        ("health", "starting"),
        ("network_mode", "host"),
        ("privileged", True),
        ("binds", ["/operator:/var/lib/postgresql"]),
        ("volumes_from", ["other"]),
        ("pid_mode", "host"),
        ("cap_add", ["SYS_ADMIN"]),
        ("devices", [{"PathOnHost": "/dev/x"}]),
        ("mounts", [{"Type": "bind", "Destination": "/var/lib/postgresql"}]),
        ("ports", {"5432/tcp": [{"HostIp": "0.0.0.0", "HostPort": "6432"}]}),
    ],
)
def test_wrong_service_or_unsafe_runtime_refused_before_database(field, value):
    detail = inspection()
    detail[field] = value
    assert invoke(detail=detail) == (["inspect"], None)


def test_residual_listener_or_any_other_client_stops_before_reset():
    assert invoke(listeners=True) == (["inspect", "listeners"], None)
    assert invoke(sessions=1) == (["inspect", "listeners", "sessions"], None)
    assert invoke(sessions=True) == (["inspect", "listeners", "sessions"], None)


@pytest.mark.parametrize("failure", ["inspect", "sessions", "prepare"])
def test_each_failure_is_content_free_and_does_not_retry(failure):
    calls, result = invoke(failure=failure)
    assert result is None
    assert calls.count(failure if failure != "sessions" else "sessions") == 1
    if failure != "prepare":
        assert "prepare" not in calls


def test_listener_parser_checks_all_three_fixture_ports_without_opening_sockets():
    for port in (8000, 5173, 5174):
        assert not phase.listener_table_clear(
            HEADER + f"\n 0: 0100007F:{port:04X} 00000000:0000 0A 0:0 0:0 0 1 0 0"
        )
    assert phase.listener_table_clear(
        HEADER + "\n 0: 0100007F:1538 00000000:0000 0A 0:0 0:0 0 1 0 0"
    )
    assert not phase.listener_table_clear("unparseable nonheader")


def test_ipv6_only_mapping_cannot_attest_the_fixed_ipv4_destination():
    detail = inspection()
    detail["ports"] = {"5432/tcp": [{"HostIp": "::", "HostPort": "5432"}]}
    assert invoke(detail=detail) == (["inspect"], None)


@pytest.mark.parametrize("raw", ["not json", "[]", "{}", "x" * 16385])
def test_malformed_inspection_never_reaches_any_database_operation(raw):
    calls = []
    with pytest.raises(phase.FixtureRefused, match=r"^Browser fixture preparation refused$"):
        phase.prepare_phase(
            environment(),
            inspect=lambda *_: raw,
            listeners_absent=lambda: calls.append("listener"),
            other_sessions=lambda: calls.append("database"),
            prepare=lambda _: calls.append("prepare"),
        )
    assert calls == []


def test_default_prepare_pins_all_destinations_and_discards_child_output(monkeypatch):
    from types import SimpleNamespace

    calls = []
    monkeypatch.setenv("OCWP_E2E_DATABASE_URL", "untrusted-target-canary")

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(phase.subprocess, "run", run)
    with pytest.raises(phase.FixtureRefused):
        phase.prepare_existing_fixture(environment())
    args, options = calls[0]
    assert args[1:] == ["scripts/e2e/prepare_e2e_database.py"]
    assert options["timeout"] == 120
    assert options["stdout"] == phase.subprocess.DEVNULL
    assert options["stderr"] == phase.subprocess.DEVNULL
    assert all(options["env"][key] == phase.FIXTURE_DSN for key in phase.DSN_KEYS)


@pytest.mark.parametrize("descriptor", [1, 2])
def test_actual_benign_child_output_overflow_is_refused_and_reaped(monkeypatch, descriptor):
    import sys

    original = phase.subprocess.Popen
    children = []

    def launch(*args, **kwargs):
        child = original(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(phase.subprocess, "Popen", launch)
    with pytest.raises(phase.FixtureRefused) as error:
        phase.inspect_service(
            [sys.executable, "-c", f'import os;os.write({descriptor},b"x"*20000)'], {}
        )
    assert str(error.value) == "Browser fixture preparation refused"
    assert len(children) == 1 and children[0].poll() is not None


def test_actual_benign_child_stderr_failure_is_not_disclosed():
    import sys

    with pytest.raises(phase.FixtureRefused) as error:
        phase.inspect_service(
            [sys.executable, "-c", 'import sys;sys.stderr.write("PRIVATE-CANARY");sys.exit(1)'], {}
        )
    assert str(error.value) == "Browser fixture preparation refused"


def test_phase_diagnostics_use_only_closed_stage_codes(monkeypatch, capsys):
    for stage in (
        "environment",
        "inspect",
        "service",
        "listeners",
        "sessions",
        "preparation",
        "PRIVATE-CANARY",
    ):

        def refuse(_, stage=stage):
            raise phase.FixtureRefused(stage)

        monkeypatch.setattr(phase, "prepare_phase", refuse)
        assert phase.main() == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        result = json.loads(captured.err)
        assert result == {
            "prepared": False,
            "stage": stage if stage != "PRIVATE-CANARY" else "unknown",
            "reason": "refused",
        }
        assert "PRIVATE-CANARY" not in captured.err
        assert len(captured.err) < 128


@pytest.mark.parametrize("fail", [False, True])
def test_session_probe_is_read_only_bounded_and_closes_without_real_database(monkeypatch, fail):
    import sqlalchemy

    calls = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            calls.append("connection_closed")

        def execute(self, sql):
            statement = str(sql)
            assert statement.startswith("SELECT count(*) FROM pg_stat_activity")
            assert "pid <> pg_backend_pid()" in statement
            assert "terminate" not in statement and "application_name" not in statement
            if fail:
                raise RuntimeError("PRIVATE-CANARY")
            return self

        def scalar_one(self):
            return 0

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            calls.append("disposed")

    def create(url, **kwargs):
        assert url == phase.FIXTURE_DSN
        assert kwargs["connect_args"] == {
            "connect_timeout": 5,
            "options": "-c statement_timeout=2000",
        }
        return Engine()

    monkeypatch.setattr(sqlalchemy, "create_engine", create)
    if fail:
        with pytest.raises(RuntimeError):
            phase.other_fixture_sessions()
    else:
        assert phase.other_fixture_sessions() == 0
    assert calls == ["connection_closed", "disposed"]


@pytest.mark.parametrize(
    "table",
    [
        "",
        " 0: 0100007F:1F40 00000000:0000 NOT_A_STATE rest",
        HEADER + "\n 0: 0100007F:1F40 00000000:0000 FF rest",
        HEADER + "\n 0: 0100007F:1F40 00000000:0000 0A",
    ],
)
def test_empty_or_malformed_proc_snapshot_is_not_listener_absence(table):
    assert not phase.listener_table_clear(table)


def test_valid_empty_table_and_ipv6_rows_are_parsed_without_runtime_reads():
    header = HEADER.replace("rem_address", "remote_address")
    assert phase.listener_table_clear(header + "\n")
    assert phase.listener_table_clear(
        header + "\n 0: " + "0" * 32 + ":1538 " + "0" * 32 + ":0000 0A 0:0 0:0 0 1 0 0"
    )
    assert not phase.listener_table_clear("sl local_address rem_address st\n")


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        (b"x" * 65537, "oversized"),
        (b"", "malformed"),
        (b"PRIVATE-CANARY", "malformed"),
        (b"\xff", "read_error"),
        ((HEADER + "\n 0: 0100007F:1F40 00000000:0000 0A").encode(), "malformed"),
        (
            (HEADER + "\n 0: 0100007F:1F40 00000000:0000 0A 0:0 0:0 0 1 0 0").encode(),
            "protected_listener",
        ),
        (None, "read_error"),
    ],
)
def test_listener_diagnostic_is_closed_and_stops_before_database(monkeypatch, capsys, raw, reason):
    import io

    reads = []
    downstream = []

    class Source(io.BytesIO):
        def read(self, size=-1):
            reads.append(size)
            return super().read(size)

    def opened(*_args, **_kwargs):
        if raw is None:
            raise OSError("PRIVATE-CANARY")
        return Source(raw)

    monkeypatch.setattr(phase.Path, "open", opened)
    original = phase.prepare_phase

    def prepare(_environment):
        return original(
            environment(),
            inspect=lambda *_: json.dumps(inspection()),
            other_sessions=lambda: downstream.append("sessions") or 0,
            prepare=lambda _: downstream.append("prepare"),
        )

    monkeypatch.setattr(phase, "prepare_phase", prepare)
    assert phase.main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err) == {
        "prepared": False,
        "stage": "listeners",
        "reason": "refused",
        "listener_reason": reason,
    }
    assert "PRIVATE-CANARY" not in output.err
    assert len(output.err) < 160
    assert downstream == []
    assert reads == ([] if raw is None else [65537])


def test_listener_diagnostic_cannot_escape_its_stage_or_allowlist():
    assert (
        phase.FixtureRefused("listeners", listener_reason="PRIVATE-CANARY").listener_reason is None
    )
    assert phase.FixtureRefused("sessions", listener_reason="oversized").listener_reason is None


@pytest.mark.parametrize(
    "stage,reason",
    [
        ("listeners", "PRIVATE-CANARY"),
        ("listeners", []),
        ("sessions", "oversized"),
        ([], "oversized"),
    ],
)
def test_mutated_exception_fields_never_leak_at_output_boundary(monkeypatch, capsys, stage, reason):
    error = phase.FixtureRefused("listeners")
    error.stage = stage
    error.listener_reason = reason
    error.args = ("PRIVATE-CANARY",)

    def refuse(_):
        raise error

    monkeypatch.setattr(phase, "prepare_phase", refuse)
    assert phase.main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err) == {
        "prepared": False,
        "stage": stage if isinstance(stage, str) else "unknown",
        "reason": "refused",
    }
    assert "PRIVATE-CANARY" not in output.err


def test_large_clear_time_wait_snapshot_is_still_refused_at_unchanged_cap(monkeypatch):
    import io

    table = HEADER + "\n" + ("0: 0100007F:1F40 0100007F:C350 06 0:0 0:0 0 1 0 0\n" * 2000)
    assert phase.listener_table_clear(table)
    assert len(table.encode()) > 65536
    monkeypatch.setattr(phase.Path, "open", lambda *_a, **_kw: io.BytesIO(table.encode()))
    with pytest.raises(phase.FixtureRefused) as error:
        phase.fixture_listeners_absent()
    assert error.value.listener_reason == "oversized"


def test_reader_accepts_both_clear_tables_and_preserves_first_refusal(monkeypatch):
    import io

    calls = []

    def opened(path, *_a, **_kw):
        calls.append(str(path))
        return io.BytesIO((HEADER + "\n").encode())

    monkeypatch.setattr(phase.Path, "open", opened)
    assert phase.fixture_listeners_absent() is True
    assert calls == ["/proc/net/tcp", "/proc/net/tcp6"]
    listener = "0: 0100007F:1F40 00000000:0000 0A 0:0 0:0 0 1 0 0"
    assert (
        phase.listener_table_reason(HEADER + "\n" + listener + "\nmalformed")
        == "protected_listener"
    )
    assert phase.listener_table_reason(HEADER + "\nmalformed\n" + listener) == "malformed"
