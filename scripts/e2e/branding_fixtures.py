"""Finite synthetic branding identities; never modify existing fixture or operator grants."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

BRANDING_CASES = (
    "convergence",
    "offline",
    "grants-none",
    "grants-legacy",
    "grants-read",
    "grants-write",
    "grants-legacy-read",
    "grants-legacy-write",
    "grants-both",
    "grants-concrete-old",
    "grants-technical",
    "conflict",
    "unconfirmed",
    "scope-race",
    "logout-race",
    "legacy-preference",
    "visual-banco",
    "visual-plano",
    "visual-ritmo",
    "visual-noche",
)
WORKSHOP_GRANTS = {
    "customers.read",
    "customers.write",
    "bicycles.read",
    "bicycles.write",
    "orders.read",
    "orders.write",
    "sync.pull",
    "sync.push",
}


def branding_fixture_id(case_index: int, retry: int, entity: int) -> str:
    return f"00000000-0000-7000-8000-{20000 + retry * 1000 + case_index * 10 + entity:012d}"


def seed_branding_identities(database_url: str) -> None:
    from cycling_workshop.db.url import normalize_database_url
    from cycling_workshop.identity.cutover_cli import activate_cutover, cutover_status
    from cycling_workshop.identity.models import UserRecord
    from cycling_workshop.identity.roles import CAPABILITIES, LEGACY_WILDCARD_CAPABILITIES
    from cycling_workshop.identity.security import PasswordService
    from cycling_workshop.settings import Settings
    from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord

    if __package__:
        from .prepare_e2e_database import E2E_PASSWORD, validate_e2e_database_url
    else:
        from prepare_e2e_database import E2E_PASSWORD, validate_e2e_database_url

    validate_e2e_database_url(database_url)
    variants = {
        "grants-none": WORKSHOP_GRANTS,
        "grants-legacy": {"*"},
        "grants-read": WORKSHOP_GRANTS | {"branding.read"},
        "grants-write": WORKSHOP_GRANTS | {"branding.write"},
        "grants-legacy-read": {"*", "branding.read"},
        "grants-legacy-write": {"*", "branding.write"},
        "grants-both": WORKSHOP_GRANTS | {"branding.read", "branding.write"},
        "grants-concrete-old": LEGACY_WILDCARD_CAPABILITIES,
        "grants-technical": set(),
    }
    password_hash = PasswordService().hash(E2E_PASSWORD)
    settings = Settings(database_url=database_url, cutover_enabled=True)
    engine = create_engine(normalize_database_url(database_url))
    try:
        for retry in range(2):
            for index, case in enumerate(BRANDING_CASES):
                organization_id = branding_fixture_id(index, retry, 0)
                with Session(engine) as session:
                    session.add(
                        OrganizationRecord(
                            id=organization_id, name=f"Disposable branding {case} {retry}"
                        )
                    )
                    session.flush()
                    session.add_all(
                        LocationRecord(
                            id=branding_fixture_id(index, retry, entity),
                            organization_id=organization_id,
                            name=f"Taller marca {letter}",
                        )
                        for entity, letter in ((1, "A"), (2, "B"))
                    )
                    session.flush()
                    session.add_all(
                        [
                            UserRecord(
                                id=branding_fixture_id(index, retry, 3),
                                organization_id=organization_id,
                                location_id=None,
                                username="e2e-branding-owner",
                                display_name="Responsable marca sintética",
                                password_hash=password_hash,
                                capabilities=sorted(CAPABILITIES),
                                is_owner=True,
                                is_active=True,
                                session_version=1,
                            ),
                            UserRecord(
                                id=branding_fixture_id(index, retry, 4),
                                organization_id=organization_id,
                                location_id=branding_fixture_id(index, retry, 1),
                                username="e2e-branding-scoped",
                                display_name="Cuenta sintética del taller A",
                                password_hash=password_hash,
                                capabilities=sorted(
                                    variants.get(case, WORKSHOP_GRANTS | {"branding.read"})
                                ),
                                is_active=True,
                                session_version=1,
                            ),
                        ]
                    )
                    session.commit()
                activated = activate_cutover(settings, organization_id=organization_id)
                assert activated["changed"] is True
                persisted = cutover_status(settings, organization_id=organization_id)
                assert persisted["minimum_write_protocol"] == 1
                assert persisted["dataset_incarnation"] == activated["dataset_incarnation"]
    finally:
        engine.dispose()
