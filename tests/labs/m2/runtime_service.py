"""Prepared closed runtime entrypoint. Never launched by imports or ordinary tests.

PostgreSQL/TLS/process checks remain authored, not executed, until separately
approved runtime execution. Receipts contain fixed booleans, never credentials,
SQL exceptions, audit rows or catalogue contents.
"""

from __future__ import annotations

import json
import os
import re
import signal
import stat
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from cycling_workshop.inventory.models import ProductRecord
from cycling_workshop.tenancy.models import OrganizationRecord
from sqlalchemy import event, select, text
from sqlalchemy.engine import Engine, ExceptionContext
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from tests.labs.m2.application import PATH, create_lab_app
from tests.labs.m2.authority import Credential, LabAuthority, LabDenied
from tests.labs.m2.runtime_authority import (
    MANIFEST_FILE,
    OwnedRun,
    PostgresLabAuthority,
    parse_run_manifest,
    read_private_file,
)

DELIVERY = Path("/run/m2-credential")
STATUS = DELIVERY / "api-status.json"
CREDENTIAL = DELIVERY / "credential"
SCOPE = DELIVERY / "scope.json"
_CHECKS = frozenset(
    {
        "scope",
        "current_grants",
        "rotation",
        "revocation",
        "closed_response",
        "postgresql_18_4",
        "fresh_database",
        "row_lock_timeout",
        "statement_timeout",
        "transaction_timeout",
        "pool_recovered",
        "revoke_before_read",
        "read_before_revoke",
    }
)
Phase = Literal["preparing", "ready", "stopped", "failed"]


API_STAGES = (
    "authority_initialization",
    "functional_scope",
    "functional_response",
    "functional_rotation",
    "functional_grants",
    "functional_revocation",
    "postgres_revoke_before_read",
    "postgres_read_before_revoke",
    "postgres_lock_timeout",
    "postgres_statement_timeout",
    "postgres_transaction_timeout",
    "postgres_pool_recovery",
    "credential_delivery",
    "listener_start",
    "serving",
    "database_cleanup",
)


STAGE_CHECKS = {
    "authority_initialization": frozenset({"postgresql_18_4", "fresh_database"}),
    "functional_scope": frozenset({"scope"}),
    "functional_response": frozenset({"closed_response"}),
    "functional_rotation": frozenset({"rotation"}),
    "functional_grants": frozenset({"current_grants"}),
    "functional_revocation": frozenset({"revocation"}),
    "postgres_revoke_before_read": frozenset({"revoke_before_read"}),
    "postgres_read_before_revoke": frozenset({"read_before_revoke"}),
    "postgres_lock_timeout": frozenset({"row_lock_timeout"}),
    "postgres_statement_timeout": frozenset({"statement_timeout"}),
    "postgres_transaction_timeout": frozenset({"transaction_timeout"}),
    "postgres_pool_recovery": frozenset({"pool_recovered"}),
    "credential_delivery": frozenset(),
    "listener_start": frozenset(),
    "serving": frozenset(),
    "database_cleanup": frozenset(),
}


def valid_check_prefix(stage: str, checks: dict[str, bool]) -> bool:
    if stage not in API_STAGES:
        raise LabDenied(503)
    index = API_STAGES.index(stage)
    before = set().union(*(STAGE_CHECKS[item] for item in API_STAGES[:index]))
    return set(checks) in (before, before | STAGE_CHECKS[stage])


class ApiProgress:
    """Bounded self-report, not authority or independent runtime qualification."""

    def __init__(self, publish: Callable[[str, dict[str, bool]], None] | None = None):
        self.stage = "authority_initialization"
        self.checks: dict[str, bool] = {}
        self._publish = publish

    def advance(self, stage: str) -> None:
        if stage not in API_STAGES:
            raise LabDenied(503)
        self.stage = stage
        self.publish()

    def complete(self, *names: str) -> None:
        if not names or set(names) - STAGE_CHECKS[self.stage]:
            raise LabDenied(503)
        self.checks.update(dict.fromkeys(names, True))
        self.publish()

    def publish(self) -> None:
        if self._publish is not None:
            self._publish(self.stage, dict(self.checks))


def status_payload(
    run: OwnedRun,
    phase: Phase,
    checks: dict[str, bool],
    *,
    cleanup: bool,
    stage: str = "authority_initialization",
) -> bytes:
    if (
        phase not in ("preparing", "ready", "stopped", "failed")
        or set(checks) - _CHECKS
        or any(value is not True for value in checks.values())
        or stage not in API_STAGES
        or not valid_check_prefix(stage, checks)
        or (phase == "ready" and stage != "serving")
        or (phase == "stopped" and stage != "database_cleanup")
        or (phase in ("ready", "stopped") and set(checks) != _CHECKS)
        or (phase in ("preparing", "ready") and cleanup is not False)
        or (phase == "stopped" and cleanup is not True)
        or any(
            type(value) is not str or re.fullmatch(pattern, value) is None
            for value, pattern in (
                (run.nonce, r"[0-9a-f]{32}"),
                (run.source_commit, r"[0-9a-f]{40}"),
                (run.source_tree, r"[0-9a-f]{40}"),
            )
        )
        or type(cleanup) is not bool
    ):
        raise LabDenied(503)
    data = json.dumps(
        {
            "schema": 2,
            "stage": stage,
            "nonce": run.nonce,
            "source_commit": run.source_commit,
            "source_tree": run.source_tree,
            "phase": phase,
            "checks": checks,
            "database_cleanup_complete": cleanup,
        },
        sort_keys=True,
    ).encode("ascii")
    if len(data) > 65536:
        raise LabDenied(503)
    return data


def credential_payload(credential: Credential) -> bytes:
    return credential.authorization().removeprefix("Bearer ").encode("ascii")


def functional_checks(
    authority: LabAuthority, progress: ApiProgress | None = None
) -> dict[str, bool]:
    """Real scoped SQL and closed ASGI; caller determines SQLite versus PG evidence."""
    progress = progress or ApiProgress()
    progress.advance("functional_scope")
    primary = authority.issue()
    with authority.read(primary.authorization()) as (scope, session):
        rows = session.scalars(
            select(ProductRecord).where(
                ProductRecord.organization_id == scope.organization_id,
                ProductRecord.location_id == scope.location_id,
            )
        ).all()
        if len(rows) != 3 or any(not row.sku.startswith("LAB-A-1-") for row in rows):
            raise LabDenied(503)
    progress.complete("scope")
    progress.advance("functional_response")
    with TestClient(create_lab_app(authority)) as client:
        response = client.get(PATH, headers={"Authorization": primary.authorization()})
        if (
            response.status_code != 200
            or response.headers.get("cache-control") != "private, no-store"
            or len(response.json().get("items", [])) != 3
            or any(
                set(item) != {"product_id", "sku", "name", "unit", "version"}
                for item in response.json()["items"]
            )
            or client.get("/docs").status_code != 404
        ):
            raise LabDenied(503)
    progress.complete("closed_response")
    progress.advance("functional_rotation")
    replacement = authority.rotate(primary.credential_id)
    try:
        with authority.read(primary.authorization()):
            pass
    except LabDenied as error:
        if error.status != 401:
            raise LabDenied(503) from None
    else:
        raise LabDenied(503)
    with authority.read(replacement.authorization()):
        pass
    progress.complete("rotation")
    progress.advance("functional_grants")
    authority.update_grants(replacement.credential_id, installation_read=False, machine_read=True)
    try:
        with authority.read(replacement.authorization()):
            pass
    except LabDenied as error:
        if error.status != 403:
            raise LabDenied(503) from None
    else:
        raise LabDenied(503)
    progress.complete("current_grants")
    progress.advance("functional_revocation")
    authority.revoke(replacement.credential_id)
    try:
        with authority.read(replacement.authorization()):
            pass
    except LabDenied as error:
        if error.status != 401:
            raise LabDenied(503) from None
    else:
        raise LabDenied(503)
    progress.complete("revocation")
    return {
        "scope": True,
        "current_grants": True,
        "rotation": True,
        "revocation": True,
        "closed_response": True,
    }


def timeout_evidence(
    expected: str, observed: list[str], elapsed: float, minimum: float, maximum: float
) -> bool:
    return observed == [expected] and minimum <= elapsed < maximum


def postgres_revoke_ordering(
    authority: PostgresLabAuthority, progress: ApiProgress | None = None
) -> dict[str, bool]:
    """External SQL sessions bypass the local RLock but take canonical DB locks."""

    def revoke_in_session(credential_id: str) -> None:
        with Session(authority._engine) as session, session.begin():
            authority._set_transaction_budgets(session)
            _org, _install, machine = authority._rows(session, credential_id)
            machine.revoked, machine.verifier = True, ""
            authority._audit(session, "revoke", machine, time.time())

    progress = progress or ApiProgress()
    progress.advance("postgres_revoke_before_read")
    first = authority.issue()
    revoke_in_session(first.credential_id)
    try:
        with authority.read(first.authorization()):
            pass
    except LabDenied as error:
        if error.status != 401:
            raise LabDenied(503) from None
    else:
        raise LabDenied(503)

    progress.complete("revoke_before_read")
    progress.advance("postgres_read_before_revoke")
    second = authority.issue()
    started = threading.Event()
    writer_pid: list[int] = []
    outcome: list[bool] = []

    def waiting_writer() -> None:
        try:
            with Session(authority._engine) as session, session.begin():
                authority._set_transaction_budgets(session)
                pid = session.scalar(text("SELECT pg_backend_pid()"))
                if type(pid) is not int:
                    raise LabDenied(503)
                writer_pid.append(pid)
                started.set()
                _org, _install, machine = authority._rows(session, second.credential_id)
                machine.revoked, machine.verifier = True, ""
                authority._audit(session, "revoke", machine, time.time())
            outcome.append(True)
        except Exception:
            outcome.append(False)
            started.set()

    writer = threading.Thread(target=waiting_writer, daemon=True)
    try:
        with authority.read(second.authorization()) as (_scope, session):
            reader_pid = session.scalar(text("SELECT pg_backend_pid()"))
            writer.start()
            if not started.wait(1) or len(writer_pid) != 1:
                raise LabDenied(503)
            until = time.clock_gettime(time.CLOCK_BOOTTIME) + 1
            while True:
                blockers = session.scalar(
                    text("SELECT pg_blocking_pids(:pid)"), {"pid": writer_pid[0]}
                )
                if isinstance(blockers, list) and reader_pid in blockers:
                    break
                if time.clock_gettime(time.CLOCK_BOOTTIME) >= until:
                    raise LabDenied(503)
                time.sleep(0.01)
            if outcome:
                raise LabDenied(503)
            # Actual query materialization while the external revoker waits.
            if session.scalar(select(ProductRecord.id).limit(1)) is None:
                raise LabDenied(503)
    finally:
        if writer.ident is not None:
            writer.join(3)
    if writer.is_alive() or outcome != [True]:
        raise LabDenied(503)
    try:
        with authority.read(second.authorization()):
            pass
    except LabDenied as error:
        if error.status != 401:
            raise LabDenied(503) from None
    else:
        raise LabDenied(503)
    progress.complete("read_before_revoke")
    return {"revoke_before_read": True, "read_before_revoke": True}


@contextmanager
def _sqlstate_observation(engine: Engine) -> Iterator[list[str]]:
    observed: list[str] = []

    def record_sqlstate(context: ExceptionContext) -> None:
        code = getattr(context.original_exception, "sqlstate", None)
        observed.append(code if code in ("55P03", "57014", "25P04") else "other")

    event.listen(engine, "handle_error", record_sqlstate)
    try:
        yield observed
    finally:
        event.remove(engine, "handle_error", record_sqlstate)


def postgres_checks(
    authority: PostgresLabAuthority, progress: ApiProgress | None = None
) -> dict[str, bool]:
    """Runtime-only actual PostgreSQL locks/timeouts, not substituted by SQLite tests."""
    if authority._engine.dialect.name != "postgresql":
        raise LabDenied(503)
    progress = progress or ApiProgress()
    # create_owned has already verified server identity and fresh owned database.
    progress.complete("postgresql_18_4", "fresh_database")
    checks = {
        **functional_checks(authority, progress),
        **postgres_revoke_ordering(authority, progress),
    }
    progress.advance("postgres_lock_timeout")
    with _sqlstate_observation(authority._engine) as observed:
        credential = authority.issue()
        with authority.read(credential.authorization()) as (scope, _session):
            organization_id = scope.organization_id
        # A separate actual SQLAlchemy session owns the organization row, not the
        # Python authority barrier. The authority must hit PostgreSQL lock_timeout.
        holder = Session(authority._engine)
        try:
            authority._set_transaction_budgets(holder)
            holder.scalar(
                select(OrganizationRecord)
                .where(OrganizationRecord.id == organization_id)
                .with_for_update()
            )
            started = time.clock_gettime(time.CLOCK_BOOTTIME)
            try:
                with authority.read(credential.authorization()):
                    pass
            except LabDenied as error:
                elapsed = time.clock_gettime(time.CLOCK_BOOTTIME) - started
                if error.status != 503 or not timeout_evidence(
                    "55P03", observed, elapsed, 1.5, 4.5
                ):
                    raise LabDenied(503) from None
            else:
                raise LabDenied(503)
        finally:
            try:
                holder.rollback()
            finally:
                holder.close()
        checks["row_lock_timeout"] = True
        progress.complete("row_lock_timeout")
        progress.advance("postgres_statement_timeout")
        observed.clear()
        started = time.clock_gettime(time.CLOCK_BOOTTIME)
        try:
            with authority.read(credential.authorization()) as (_scope, session):
                session.execute(text("SELECT pg_sleep(6)"))
        except LabDenied as error:
            elapsed = time.clock_gettime(time.CLOCK_BOOTTIME) - started
            if error.status != 503 or not timeout_evidence("57014", observed, elapsed, 4.5, 7):
                raise LabDenied(503) from None
        else:
            raise LabDenied(503)
        checks["statement_timeout"] = True
        progress.complete("statement_timeout")
        progress.advance("postgres_transaction_timeout")
        # Fatal transaction timeout is probed through another real session using the
        # identical budget installer, then invalidated; it cannot poison the API owner.
        observed.clear()
        timed = Session(authority._engine)
        started = time.clock_gettime(time.CLOCK_BOOTTIME)
        try:
            authority._set_transaction_budgets(timed)
            timed.execute(text("SELECT pg_sleep(4)"))
            timed.execute(text("SELECT pg_sleep(4.5)"))
        except SQLAlchemyError:
            elapsed = time.clock_gettime(time.CLOCK_BOOTTIME) - started
            if not timeout_evidence("25P04", observed, elapsed, 7.5, 10):
                raise LabDenied(503) from None
            timed.invalidate()
        else:
            raise LabDenied(503)
        finally:
            timed.close()
        checks["transaction_timeout"] = True
        progress.complete("transaction_timeout")
        progress.advance("postgres_pool_recovery")
        with authority.read(credential.authorization()) as (scope, session):
            if (
                session.scalar(
                    select(ProductRecord.id).where(ProductRecord.location_id == scope.location_id)
                )
                is None
            ):
                raise LabDenied(503)
        authority.revoke(credential.credential_id)
        progress.complete("pool_recovered")
        return {**checks, "pool_recovered": True, "postgresql_18_4": True, "fresh_database": True}


def _delivery_directory() -> None:
    info = DELIVERY.lstat()
    if (
        os.geteuid() <= 0
        or not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise LabDenied(503)
    if set(os.listdir(DELIVERY)) - {"api-status.json", "credential", "scope.json"}:
        raise LabDenied(503)


def _write_new(path: Path, payload: bytes, mode: int) -> None:
    if path not in (STATUS, CREDENTIAL, SCOPE) or len(payload) > 65536:
        raise LabDenied(503)
    _delivery_directory()
    descriptor = None
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise LabDenied(503)
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, mode)
    except Exception:
        raise LabDenied(503) from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _status(payload: bytes) -> None:
    _delivery_directory()
    if not STATUS.exists():
        _write_new(STATUS, payload, 0o600)
        return
    descriptor = None
    try:
        descriptor = os.open(STATUS, os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise LabDenied(503)
        os.ftruncate(descriptor, 0)
        view = memoryview(payload)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise LabDenied(503)
            view = view[count:]
        os.fsync(descriptor)
    except Exception:
        raise LabDenied(503) from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def main() -> int:
    # The workflow must invoke this explicitly ONLY after separate execution consent.
    from tests.labs.m2.runtime_transport import serve

    authority: PostgresLabAuthority | None = None
    run: OwnedRun | None = None
    phase: Phase = "preparing"

    def publish(stage: str, checks: dict[str, bool]) -> None:
        if run is None:
            raise LabDenied(503)
        _status(status_payload(run, phase, checks, cleanup=False, stage=stage))

    progress = ApiProgress(publish)
    stopped = threading.Event()
    failure = False

    def stop(_signal: int, _frame: object) -> None:
        stopped.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        run = parse_run_manifest(read_private_file(MANIFEST_FILE, 4096))
        progress.advance("authority_initialization")
        authority = PostgresLabAuthority.create_owned()
        if authority.owned_run != run:
            raise LabDenied(503)
        checks = postgres_checks(authority, progress)
        if checks != progress.checks or set(checks) != _CHECKS:
            raise LabDenied(503)
        if stopped.is_set():
            raise LabDenied(503)
        progress.advance("credential_delivery")
        credential = authority.issue()
        with authority.read(credential.authorization()) as (scope, _session):
            binding = json.dumps(
                {"scope": asdict(scope), "run_deadline": authority.run_deadline}, sort_keys=True
            ).encode("ascii")
        try:
            _write_new(SCOPE, binding, 0o400)
            _write_new(CREDENTIAL, credential_payload(credential), 0o400)
        except Exception:
            authority.revoke(credential.credential_id)
            raise LabDenied(503) from None

        def ready() -> None:
            nonlocal phase
            phase = "ready"
            progress.advance("serving")

        progress.advance("listener_start")
        serve(
            create_lab_app(authority),
            run_deadline=authority.run_deadline,
            stop_event=stopped,
            on_ready=ready,
        )
    except Exception:
        failure = True
    finally:
        if authority is not None:
            if not failure:
                try:
                    phase = "preparing"
                    progress.advance("database_cleanup")
                except Exception:
                    failure = True
            try:
                authority.close()
            except Exception:
                failure = True
        if run is not None:
            cleanup = (
                authority is not None and authority.cleanup_complete and authority.database_removed
            )
            try:
                _status(
                    status_payload(
                        run,
                        "failed" if failure else "stopped",
                        progress.checks,
                        cleanup=cleanup,
                        stage=progress.stage,
                    )
                )
            except Exception:
                failure = True
    return 1 if failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
