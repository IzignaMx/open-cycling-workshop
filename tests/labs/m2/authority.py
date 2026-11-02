"""Fresh-memory synthetic authority; not PostgreSQL or production qualification.

No existing engine, DSN, environment credential or backup can initialize this lab.
SQLite ignores FOR UPDATE: the local bounded barrier proves only functional
serialization. Real PostgreSQL locking/timeout qualification remains blocked.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import secrets
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import uuid4

from cycling_workshop.identity.cutover import validate_compatibility
from cycling_workshop.inventory.models import ProductRecord
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from sqlalchemy import Table, create_engine, delete, event, inspect, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool

from tests.labs.m2.models import Audit, Installation, LabBase, Machine

Fixture = Literal["primary", "other_location", "other_org"]
LIFETIME = 900.0
_PATTERN = re.compile(r"Bearer (m2_([0-9a-f]{32})_[A-Za-z0-9_-]{43})\Z")


class LabDenied(Exception):
    """Fixed secret-free error; no raw underlying exception is exposed."""

    def __init__(self, status: int = 401):
        self.status = status
        super().__init__("Laboratory access refused")


@dataclass(frozen=True)
class Credential:
    credential_id: str
    _secret: str = field(repr=False)

    def authorization(self) -> str:
        return "Bearer " + self._secret


@dataclass(frozen=True)
class MachineScope:
    organization_id: str
    location_id: str
    dataset_incarnation: str
    installation_id: str
    machine_id: str
    run_id: str
    generation: int


@dataclass(frozen=True)
class _Witness:
    scope: MachineScope
    issued_at: float
    expires_at: float
    deadline: float


def _clock() -> tuple[float, float]:
    try:
        return time.time(), time.clock_gettime(time.CLOCK_BOOTTIME)
    except (AttributeError, OSError, ValueError):
        raise LabDenied(503) from None


class LabAuthority:
    def __init__(self) -> None:
        self._closed = False
        self._cleanup_complete = False
        self._invalid = False
        self._barrier = threading.RLock()
        self._witnesses: dict[str, _Witness] = {}
        self._run_id = uuid4().hex  # External to the database; never reconstructed.
        self._utc, self._elapsed = _clock()
        if not all(math.isfinite(value) for value in (self._utc, self._elapsed)):
            raise LabDenied(503)
        self._run_until = self._elapsed + LIFETIME
        self._run_utc_until = self._utc + LIFETIME
        self._engine = self._build_engine()
        try:
            self._initialize()
        except Exception:
            self._closed = True
            self._witnesses.clear()
            self._run_id = ""
            self._engine.dispose()
            raise LabDenied(503) from None

    def _build_engine(self) -> Engine:
        return create_engine(
            "sqlite+pysqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
            echo=False,
            hide_parameters=True,
        )

    def _set_transaction_budgets(self, executor: Session | Connection) -> None:
        if self._engine.dialect.name != "sqlite":
            raise LabDenied(503)

    def _initialize(self) -> None:
        if self._engine.dialect.name == "sqlite":
            event.listen(self._engine, "connect", self._foreign_keys)
        for table in (
            OrganizationRecord.__table__,
            LocationRecord.__table__,
            ProductRecord.__table__,
        ):
            cast(Table, table).create(self._engine)
        LabBase.metadata.create_all(self._engine)
        self._fixtures: dict[str, tuple[str, str, str]] = {}
        with Session(self._engine) as session, session.begin():
            self._set_transaction_budgets(session)
            for org_index, label in enumerate(("A", "B"), 1):
                org = f"00000000-0000-4000-8000-{org_index:012d}"
                incarnation = str(uuid4())
                session.add(
                    OrganizationRecord(
                        id=org, name=f"Synthetic {label}", dataset_incarnation=incarnation
                    )
                )
                session.flush()
                for loc_index in (1, 2):
                    location = f"00000000-0000-4000-8001-{org_index * 10 + loc_index:012d}"
                    session.add(
                        LocationRecord(
                            id=location, organization_id=org, name=f"Synthetic {label}/{loc_index}"
                        )
                    )
                    session.flush()
                    key = (
                        "primary"
                        if (org_index, loc_index) == (1, 1)
                        else "other_location"
                        if (org_index, loc_index) == (1, 2)
                        else "other_org"
                        if loc_index == 1
                        else "unused"
                    )
                    self._fixtures[key] = org, location, incarnation
                    for product_index in (1, 2, 3):
                        session.add(
                            ProductRecord(
                                id=(
                                    "00000000-0000-4000-8002-"
                                    f"{org_index * 100 + loc_index * 10 + product_index:012d}"
                                ),
                                organization_id=org,
                                location_id=location,
                                sku=f"LAB-{label}-{loc_index}-{product_index:03d}",
                                name=f"Synthetic {label}/{loc_index} product {product_index}",
                                unit="pieza",
                                version=1,
                                created_at=datetime.now(UTC),
                                updated_at=datetime.now(UTC),
                            )
                        )

    @staticmethod
    def _foreign_keys(connection: sqlite3.Connection, _record: ConnectionPoolEntry) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def cleanup_complete(self) -> bool:
        return self._cleanup_complete

    def _sample(self) -> tuple[float, float]:
        if self._closed or self._invalid:
            raise LabDenied(503)
        try:
            utc, elapsed = _clock()
            if (
                not all(math.isfinite(v) for v in (utc, elapsed))
                or utc < self._utc
                or elapsed < self._elapsed
                or elapsed >= self._run_until
                or utc >= self._run_utc_until
            ):
                raise LabDenied(503)
        except Exception:
            self._invalid = True
            raise LabDenied(503) from None
        self._utc, self._elapsed = utc, elapsed
        return utc, elapsed

    @contextmanager
    def _locked(self) -> Iterator[tuple[float, float]]:
        if not self._barrier.acquire(timeout=2):
            raise LabDenied(503)
        try:
            yield self._sample()
        finally:
            self._barrier.release()

    @staticmethod
    def _credential(machine_id: str) -> Credential:
        return Credential(machine_id, f"m2_{machine_id}_{secrets.token_urlsafe(32)}")

    @staticmethod
    def _verifier(credential: Credential) -> str:
        return hashlib.sha256(credential._secret.encode("ascii")).hexdigest()

    def _audit(self, session: Session, action: str, machine: Machine, utc: float) -> None:
        installation = session.get(Installation, machine.installation_id)
        if installation is None:
            raise LabDenied(503)
        session.add(
            Audit(
                id=uuid4().hex,
                request_id=str(uuid4()),
                action=action,
                actor="fixture_harness",
                organization_id=machine.organization_id,
                installation_id=machine.installation_id,
                machine_id=machine.id,
                generation=machine.generation,
                occurred_at=utc,
                policy=json.dumps(
                    {
                        "enabled": machine.enabled,
                        "catalogue_read": machine.catalogue_read,
                        "revoked": machine.revoked,
                        "installation_read": installation.catalogue_read,
                        "installation_enabled": installation.enabled,
                    },
                    sort_keys=True,
                ),
            )
        )

    def issue(self, fixture: Fixture = "primary") -> Credential:
        if fixture not in ("primary", "other_location", "other_org"):
            raise LabDenied(403)
        with self._locked() as (utc, elapsed):
            org, location, incarnation = self._fixtures[fixture]
            credential = self._credential(uuid4().hex)
            install_id = uuid4().hex
            scope = MachineScope(
                org, location, incarnation, install_id, credential.credential_id, self._run_id, 1
            )
            witness = _Witness(
                scope,
                utc,
                min(utc + LIFETIME, self._run_utc_until),
                min(elapsed + LIFETIME, self._run_until),
            )
            try:
                with Session(self._engine) as session, session.begin():
                    self._set_transaction_budgets(session)
                    organization = session.scalar(
                        select(OrganizationRecord)
                        .where(OrganizationRecord.id == org)
                        .with_for_update()
                    )
                    validate_compatibility(organization)
                    session.add(
                        Installation(
                            id=install_id,
                            organization_id=org,
                            location_id=location,
                            incarnation=incarnation,
                            run_id=self._run_id,
                            enabled=True,
                            catalogue_read=True,
                        )
                    )
                    machine = Machine(
                        id=credential.credential_id,
                        installation_id=install_id,
                        organization_id=org,
                        location_id=location,
                        incarnation=incarnation,
                        run_id=self._run_id,
                        generation=1,
                        verifier=self._verifier(credential),
                        enabled=True,
                        catalogue_read=True,
                        revoked=False,
                        issued_at=utc,
                        expires_at=witness.expires_at,
                    )
                    session.add(machine)
                    self._audit(session, "issue", machine, utc)
                    session.flush()
                    self._sample()
            except Exception:
                raise LabDenied(503) from None
            self._witnesses[credential.credential_id] = witness
            return credential

    def _rows(
        self, session: Session, machine_id: str
    ) -> tuple[OrganizationRecord, Installation, Machine]:
        candidate = session.get(Machine, machine_id)
        if candidate is None:
            raise LabDenied()
        org = session.scalar(
            select(OrganizationRecord)
            .where(OrganizationRecord.id == candidate.organization_id)
            .with_for_update()
        )
        validate_compatibility(org)
        installation = session.scalar(
            select(Installation)
            .where(Installation.id == candidate.installation_id)
            .with_for_update()
        )
        machine = session.scalar(
            select(Machine)
            .where(Machine.id == machine_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if org is None or installation is None or machine is None:
            raise LabDenied()
        return org, installation, machine

    def _validate(
        self,
        org: OrganizationRecord,
        installation: Installation,
        machine: Machine,
        utc: float,
        elapsed: float,
    ) -> _Witness:
        witness = self._witnesses.get(machine.id)
        if witness is None:
            raise LabDenied()
        scope = witness.scope
        if (
            machine.revoked
            or machine.generation != scope.generation
            or machine.run_id != self._run_id
            or installation.run_id != self._run_id
            or scope.run_id != self._run_id
            or machine.organization_id != scope.organization_id
            or installation.organization_id != scope.organization_id
            or machine.location_id != scope.location_id
            or installation.location_id != scope.location_id
            or machine.installation_id != scope.installation_id
            or org.dataset_incarnation != scope.dataset_incarnation
            or machine.incarnation != scope.dataset_incarnation
            or installation.incarnation != scope.dataset_incarnation
            or machine.issued_at != witness.issued_at
            or machine.expires_at != witness.expires_at
            or utc < machine.issued_at
            or utc >= machine.expires_at
            or elapsed >= witness.deadline
        ):
            raise LabDenied()
        return witness

    @contextmanager
    def read(self, authorization: str) -> Iterator[tuple[MachineScope, Session]]:
        if not isinstance(authorization, str) or len(authorization) > 128:
            raise LabDenied()
        match = _PATTERN.fullmatch(authorization)
        if match is None:
            raise LabDenied()
        try:
            entry_utc, started = _clock()
            if not all(math.isfinite(value) for value in (entry_utc, started)):
                raise LabDenied(503)
        except Exception:
            self._invalid = True
            raise LabDenied(503) from None
        with self._locked() as (locked_utc, locked_elapsed):
            if locked_utc < entry_utc or locked_elapsed < started:
                self._invalid = True
                raise LabDenied(503)
            session = Session(self._engine)
            completed = False
            try:
                self._set_transaction_budgets(session)
                org, installation, machine = self._rows(session, match[2])
                verifier = hashlib.sha256(match[1].encode("ascii")).hexdigest()
                if not hmac.compare_digest(verifier, machine.verifier):
                    raise LabDenied()
                utc, elapsed = self._sample()
                witness = self._validate(org, installation, machine, utc, elapsed)
                if not all(
                    (
                        installation.enabled,
                        machine.enabled,
                        installation.catalogue_read,
                        machine.catalogue_read,
                    )
                ):
                    raise LabDenied(403)
                yield witness.scope, session
                utc, elapsed = self._sample()
                self._validate(org, installation, machine, utc, elapsed)
                if elapsed - started >= 8:
                    raise LabDenied(503)
                completed = True
            except LabDenied:
                raise
            except Exception:
                raise LabDenied(503) from None
            finally:
                failed = False
                try:
                    session.rollback()
                except Exception:
                    failed = True
                    with suppress(Exception):
                        session.invalidate()
                try:
                    session.close()
                except Exception:
                    failed = True
                    with suppress(Exception):
                        session.invalidate()
                if failed:
                    self._invalid = True
                    raise LabDenied(503) from None
                if completed:
                    utc, elapsed = self._sample()
                    if utc >= witness.expires_at or elapsed >= witness.deadline:
                        raise LabDenied()
                    if elapsed - started >= 8:
                        raise LabDenied(503)

    def _change(
        self,
        credential_id: str,
        action: Literal["rotate", "revoke", "grants", "enabled"],
        *,
        grants: tuple[bool, bool] | None = None,
        enabled: tuple[bool, bool] | None = None,
    ) -> Credential | None:
        with self._locked() as (utc, elapsed):
            replacement = None
            try:
                with Session(self._engine) as session, session.begin():
                    self._set_transaction_budgets(session)
                    org, installation, machine = self._rows(session, credential_id)
                    witness = self._validate(org, installation, machine, utc, elapsed)
                    if action == "rotate":
                        replacement = self._credential(machine.id)
                        machine.generation += 1
                        machine.verifier = self._verifier(replacement)
                        machine.issued_at = utc
                        machine.expires_at = min(utc + LIFETIME, self._run_utc_until)
                    elif action == "revoke":
                        machine.revoked = True
                        machine.verifier = ""
                    elif action == "grants":
                        if grants is None:
                            raise LabDenied(503)
                        if (grants[0] and not installation.catalogue_read) or (
                            grants[1] and not machine.catalogue_read
                        ):
                            raise LabDenied(403)
                        installation.catalogue_read, machine.catalogue_read = grants
                    elif action == "enabled":
                        if enabled is None:
                            raise LabDenied(503)
                        if (enabled[0] and not installation.enabled) or (
                            enabled[1] and not machine.enabled
                        ):
                            raise LabDenied(403)
                        installation.enabled, machine.enabled = enabled
                    self._audit(session, action, machine, utc)
                    session.flush()
                    self._sample()
                    if replacement:
                        scope = witness.scope
                        next_witness = _Witness(
                            MachineScope(
                                scope.organization_id,
                                scope.location_id,
                                scope.dataset_incarnation,
                                scope.installation_id,
                                scope.machine_id,
                                scope.run_id,
                                machine.generation,
                            ),
                            utc,
                            machine.expires_at,
                            min(elapsed + LIFETIME, self._run_until),
                        )
            except LabDenied:
                raise
            except Exception:
                raise LabDenied(503) from None
            if replacement:
                self._witnesses[credential_id] = next_witness
            return replacement

    def rotate(self, credential_id: str) -> Credential:
        replacement = self._change(credential_id, "rotate")
        assert replacement is not None
        return replacement

    def revoke(self, credential_id: str) -> None:
        self._change(credential_id, "revoke")

    def update_grants(
        self, credential_id: str, *, installation_read: bool, machine_read: bool
    ) -> None:
        self._change(credential_id, "grants", grants=(installation_read, machine_read))

    def set_enabled(self, credential_id: str, *, installation: bool, machine: bool) -> None:
        self._change(credential_id, "enabled", enabled=(installation, machine))

    def close(self) -> None:
        if not self._barrier.acquire(timeout=2):
            self._invalid = True
            raise LabDenied(503)
        try:
            if self._closed:
                if not self._cleanup_complete:
                    raise LabDenied(503)
                return
            self._closed = True
            self._witnesses.clear()
            self._run_id = ""
            try:
                with self._engine.begin() as connection:
                    self._set_transaction_budgets(connection)
                    for table in reversed(LabBase.metadata.sorted_tables):
                        if inspect(connection).has_table(table.name):
                            connection.execute(delete(table))
                self._engine.dispose()
                self._cleanup_complete = True
            except Exception:
                try:
                    self._engine.dispose()
                finally:
                    raise LabDenied(503) from None
        finally:
            self._barrier.release()
