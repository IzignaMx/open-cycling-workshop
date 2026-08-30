from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from cycling_workshop.identity.models import UserRecord


def normalize_username(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("username is required")
    return normalized


@dataclass(frozen=True, slots=True)
class UserAccount:
    user_id: str
    organization_id: str
    location_id: str | None
    username: str
    display_name: str
    password_hash: str
    capabilities: frozenset[str]
    is_active: bool
    session_version: int


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, account: UserAccount) -> None:
        self._session.add(
            UserRecord(
                id=account.user_id,
                organization_id=account.organization_id,
                location_id=account.location_id,
                username=normalize_username(account.username),
                display_name=account.display_name.strip(),
                password_hash=account.password_hash,
                capabilities=sorted(account.capabilities),
                is_active=account.is_active,
                session_version=account.session_version,
            )
        )

    def get_by_username(self, *, organization_id: str, username: str) -> UserAccount | None:
        statement: Select[tuple[UserRecord]] = select(UserRecord).where(
            UserRecord.organization_id == organization_id,
            UserRecord.username == normalize_username(username),
        )
        record = self._session.scalar(statement)
        return self._to_domain(record) if record is not None else None

    def get(self, *, user_id: str, organization_id: str) -> UserAccount | None:
        statement: Select[tuple[UserRecord]] = select(UserRecord).where(
            UserRecord.id == user_id,
            UserRecord.organization_id == organization_id,
        )
        record = self._session.scalar(statement)
        return self._to_domain(record) if record is not None else None

    def increment_session_version(self, *, user_id: str, organization_id: str) -> int:
        statement: Select[tuple[UserRecord]] = select(UserRecord).where(
            UserRecord.id == user_id,
            UserRecord.organization_id == organization_id,
        )
        record = self._session.scalar(statement)
        if record is None:
            raise LookupError("user not found")
        record.session_version += 1
        self._session.flush()
        return record.session_version

    @staticmethod
    def _to_domain(record: UserRecord) -> UserAccount:
        return UserAccount(
            user_id=record.id,
            organization_id=record.organization_id,
            location_id=record.location_id,
            username=record.username,
            display_name=record.display_name,
            password_hash=record.password_hash,
            capabilities=frozenset(record.capabilities or []),
            is_active=record.is_active,
            session_version=record.session_version,
        )
