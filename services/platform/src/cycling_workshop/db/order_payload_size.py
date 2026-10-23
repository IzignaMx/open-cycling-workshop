"""Generated raw-byte metadata; SQLite is a functional-test surrogate only.

PostgreSQL must persist this value before a bounded reader uses it. The SQLite
VIRTUAL expression intentionally makes no database-memory/prefetch guarantee.
"""

from typing import Any, Literal, Protocol, cast

from sqlalchemy import Computed, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.engine.interfaces import ReflectedColumn
from sqlalchemy.exc import CompileError
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.compiler import DDLCompiler


class _ComputedColumnVisitor(Protocol):
    # SQLAlchemy 2.0.52's base and PostgreSQL visitors return str but are untyped.
    def __call__(self, generated: Computed, **kw: Any) -> str: ...


class OrderPayloadRawOctets(Computed):
    """One finite dialect-specific generated column, never an application count."""

    def __init__(self, discriminator: Literal["entity_type", "aggregate_type"]) -> None:
        self.discriminator = discriminator
        super().__init__(
            f"CASE WHEN {discriminator}::pg_catalog.text OPERATOR(pg_catalog.=) "
            "'service_order'::pg_catalog.text THEN "
            "pg_catalog.octet_length(payload::pg_catalog.text)::pg_catalog.int8 ELSE NULL END",
            persisted=True,
        )


@compiles(OrderPayloadRawOctets, "postgresql")
def _postgresql(element: OrderPayloadRawOctets, compiler: DDLCompiler, **kw: Any) -> str:
    visit_computed = cast(_ComputedColumnVisitor, compiler.visit_computed_column)
    return visit_computed(element, **kw)


@compiles(OrderPayloadRawOctets, "sqlite")
def _sqlite(element: OrderPayloadRawOctets, compiler: DDLCompiler, **kw: Any) -> str:
    surrogate = Computed(
        f"CASE WHEN {element.discriminator} = 'service_order' "
        "THEN length(CAST(payload AS BLOB)) ELSE NULL END",
        persisted=False,
    )
    visit_computed = cast(_ComputedColumnVisitor, compiler.visit_computed_column)
    return visit_computed(surrogate, **kw)


@compiles(OrderPayloadRawOctets)
def _unsupported(element: OrderPayloadRawOctets, compiler: DDLCompiler, **kw: Any) -> str:
    raise CompileError("Order payload byte metadata supports PostgreSQL or SQLite tests only")


class OrderPayloadCountSchemaError(ValueError):
    """The resolved tables cannot support bounded raw projection reads."""


_PAIRS = (("sync_changes", "entity_type"), ("outbox_events", "aggregate_type"))


def _pg_expression(discriminator: str) -> str:
    # Complete pg_get_expr(..., pretty_bool=false) representation for migration
    # 0013's VARCHAR discriminator, JSON payload and BIGINT generated count.
    return (
        f"CASE WHEN (({discriminator})::text = 'service_order'::text) "
        "THEN (octet_length((payload)::text))::bigint ELSE NULL::bigint END"
    )


def require_order_payload_count_schema(connection: Connection) -> None:
    """Check live resolved metadata on every use; never trust an ORM declaration.

    PostgreSQL count checks precede any raw cast. SQLite checks only the declared
    VIRTUAL equivalent and provides no prefetch/resource guarantee. No metadata
    cache survives a call or transaction. Privileged concurrent DDL is outside
    the ordinary-SQL contract.
    """
    dialect = connection.dialect.name
    if dialect == "postgresql":
        if any(
            connection.scalar(text(f"SHOW {setting}")) != "UTF8"
            for setting in ("server_encoding", "client_encoding")
        ):
            raise OrderPayloadCountSchemaError("order payload counts require UTF8")
        for table, discriminator in _PAIRS:
            # Initdb-pinned builtin dependencies are omitted by PostgreSQL.
            # Only the generated-column INTERNAL reference and the two input
            # column NORMAL references are allowed; user functions/operators
            # or types add dependency rows even if deparsed names look equal.
            row = (
                connection.execute(
                    text(
                        "SELECT c.relkind, c.relispartition, "
                        "EXISTS (SELECT 1 FROM pg_catalog.pg_inherits i "
                        "WHERE i.inhrelid OPERATOR(pg_catalog.=) c.oid "
                        "OR i.inhparent OPERATOR(pg_catalog.=) c.oid) AS inherited, "
                        "p.atttypid OPERATOR(pg_catalog.=) "
                        "'pg_catalog.json'::pg_catalog.regtype AS payload_json, "
                        "a.atttypid OPERATOR(pg_catalog.=) "
                        "'pg_catalog.int8'::pg_catalog.regtype AS count_bigint, "
                        "s.atttypid OPERATOR(pg_catalog.=) "
                        "'pg_catalog.varchar'::pg_catalog.regtype AS discriminator_varchar, "
                        "EXISTS (SELECT 1 FROM pg_catalog.pg_depend dep "
                        "WHERE dep.classid OPERATOR(pg_catalog.=) "
                        "'pg_catalog.pg_attrdef'::pg_catalog.regclass "
                        "AND dep.objid OPERATOR(pg_catalog.=) d.oid AND NOT ("
                        "dep.objsubid OPERATOR(pg_catalog.=) 0 AND "
                        "dep.refclassid OPERATOR(pg_catalog.=) "
                        "'pg_catalog.pg_class'::pg_catalog.regclass "
                        "AND dep.refobjid OPERATOR(pg_catalog.=) c.oid AND ("
                        "(dep.deptype OPERATOR(pg_catalog.=) 'i' AND "
                        "dep.refobjsubid OPERATOR(pg_catalog.=) a.attnum) OR ("
                        "dep.deptype OPERATOR(pg_catalog.=) 'n' AND ("
                        "dep.refobjsubid OPERATOR(pg_catalog.=) p.attnum "
                        "OR dep.refobjsubid OPERATOR(pg_catalog.=) s.attnum))))) "
                        "AS unsafe_dependency, "
                        "a.attgenerated, "
                        "pg_catalog.pg_get_expr(d.adbin,d.adrelid,false) AS expression "
                        "FROM pg_catalog.pg_class c "
                        "JOIN pg_catalog.pg_attribute p "
                        "ON p.attrelid OPERATOR(pg_catalog.=) c.oid "
                        "AND p.attname OPERATOR(pg_catalog.=) 'payload' AND NOT p.attisdropped "
                        "JOIN pg_catalog.pg_attribute a "
                        "ON a.attrelid OPERATOR(pg_catalog.=) c.oid "
                        "AND a.attname OPERATOR(pg_catalog.=) 'order_payload_raw_octets' "
                        "AND NOT a.attisdropped JOIN pg_catalog.pg_attribute s "
                        "ON s.attrelid OPERATOR(pg_catalog.=) c.oid "
                        "AND s.attname OPERATOR(pg_catalog.=) :discriminator "
                        "AND NOT s.attisdropped "
                        "JOIN pg_catalog.pg_attrdef d "
                        "ON d.adrelid OPERATOR(pg_catalog.=) a.attrelid "
                        "AND d.adnum OPERATOR(pg_catalog.=) a.attnum "
                        "WHERE c.oid OPERATOR(pg_catalog.=) pg_catalog.to_regclass(:table)"
                    ),
                    {"table": table, "discriminator": discriminator},
                )
                .mappings()
                .one_or_none()
            )
            if (
                row is None
                or row["relkind"] != "r"
                or row["relispartition"]
                or row["inherited"]
                or row["payload_json"] is not True
                or row["count_bigint"] is not True
                or row["discriminator_varchar"] is not True
                or row["unsafe_dependency"] is not False
                or row["attgenerated"] != "s"
                or " ".join(str(row["expression"]).split()) != _pg_expression(discriminator)
            ):
                raise OrderPayloadCountSchemaError("order payload count schema mismatch")
        return
    if dialect == "sqlite" and connection.dialect.driver == "pysqlite":
        if connection.scalar(text("PRAGMA encoding")) != "UTF-8":
            raise OrderPayloadCountSchemaError("order payload surrogate requires UTF8")
        inspector = inspect(connection)
        for table, discriminator in _PAIRS:
            if (
                connection.execute(
                    text("SELECT 1 FROM sqlite_temp_master WHERE name COLLATE NOCASE = :table"),
                    {"table": table},
                ).first()
                is not None
            ):
                raise OrderPayloadCountSchemaError("order payload surrogate TEMP shadow")
            if table not in inspector.get_table_names(schema="main"):
                raise OrderPayloadCountSchemaError("order payload surrogate table missing")
            columns = {
                column["name"]: column for column in inspector.get_columns(table, schema="main")
            }
            payload: ReflectedColumn | dict[str, Any] = columns.get("payload", {})
            count: ReflectedColumn | dict[str, Any] = columns.get("order_payload_raw_octets", {})
            computed = count.get("computed", {})
            expected = (
                f"CASE WHEN {discriminator} = 'service_order' "
                "THEN length(CAST(payload AS BLOB)) ELSE NULL END"
            )
            if (
                str(payload.get("type")) != "JSON"
                or str(count.get("type")) != "BIGINT"
                or computed.get("persisted") is not False
                or " ".join(str(computed.get("sqltext", "")).split()) != expected
            ):
                raise OrderPayloadCountSchemaError("order payload surrogate schema mismatch")
        return
    raise OrderPayloadCountSchemaError("unsupported order payload count dialect")
