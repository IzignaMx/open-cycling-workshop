"""Additive head migration and same-tenant profile constraints."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from test_identity_migration import identity_migration_database as identity_migration_database


def test_branding_upgrade_preserves_accounts_and_qualifies_cutover_recovery(
    identity_migration_database,
):
    from cycling_workshop.identity.cutover_cli import require_cutover_schema
    from sqlalchemy.orm import Session

    config, engine = identity_migration_database
    command.upgrade(config, "0010")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organizations (id,name,dataset_incarnation) VALUES "
                "('a','A','00000000-0000-0000-0000-000000000001'),('b','B','00000000-0000-0000-0000-000000000002')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO locations (id,organization_id,name) VALUES "
                "('a1','a','A1'),('b1','b','B1')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO users "
                "(id,organization_id,location_id,username,display_name,password_hash,capabilities,is_active,session_version,is_owner,version)"
                " VALUES ('u','a',NULL,'u','Owner','untouched','[\"*\"]',true,9,true,7)"
            )
        )
        before = list(connection.execute(text("SELECT * FROM users")).mappings())
    command.upgrade(config, "head")
    assert "workshop_brand_profiles" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert list(connection.execute(text("SELECT * FROM users")).mappings()) == before
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0011"
    with Session(engine) as session:
        require_cutover_schema(session)
    with pytest.raises(RuntimeError, match="forward-only"):
        command.downgrade(config, "0010")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0011"
    params = {"now": datetime.now(UTC)}
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO workshop_brand_profiles "
                "(organization_id,location_id,schema_version,version,display_name,palette_id,updated_at,updated_by)"
                " VALUES ('a','b1',1,1,'Cross tenant','bosque',:now,'u')"
            ),
            params,
        )
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO workshop_brand_profiles "
                "(organization_id,location_id,schema_version,version,display_name,palette_id,updated_at,updated_by)"
                " VALUES ('a','a1',1,1,'Brand','bosque',:now,'u')"
            ),
            params,
        )
