"""Six synthetic selection regressions for the fixed contained integrity groups.

Source preparation is not execution evidence. These hooks and receipts launch no
subprocess, open no database and never run the selected product tests themselves.
"""

import importlib.util
import json
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
METADATA = "services/platform/tests/quotes/test_quote_effect_metadata.py"
BRIDGE = "services/platform/tests/quotes/test_quote_application_service_postgres.py"
WRITER = "services/platform/tests/sync/test_prepared_order_change.py"
BOUNDED = "services/platform/tests/quotes/test_quote_bounded_effects_postgres.py"
MALFORMED = "test_runtime_count_verifier_refuses_malformed_postgres_metadata"
RELATIONS = "test_runtime_count_verifier_refuses_nonordinary_relations"
SHADOWS = "test_runtime_count_verifier_refuses_shadowed_generated_dependencies"
DEPENDENCIES = "test_postgres_generated_dependency_rows_are_exact"
PG_SELECTIONS = {
    "metadata_sync": (METADATA, ((MALFORMED, 7),), "not sqlite and sync_changes"),
    "metadata_outbox": (METADATA, ((MALFORMED, 7),), "not sqlite and outbox_events"),
    "metadata_relations": (
        METADATA,
        ((RELATIONS, 6), (SHADOWS, 2), (DEPENDENCIES, 1)),
        "not sqlite",
    ),
    "service_bridge": (
        BRIDGE,
        (
            ("test_create_decide_replay_commits_one_complete_tuple", 1),
            ("test_expired_deadline_refuses_before_writer_or_effects", 1),
            ("test_historical_quote_only_decision_replay_does_not_invent_transition", 1),
            ("test_response_failure_rolls_back_all_decision_effects", 1),
        ),
        "not sqlite",
    ),
    "writer5": (
        WRITER,
        (
            ("test_prepared_writer_retains_both_exact_raw_copies_and_generated_counts", 1),
            ("test_prepared_inserts_are_owned_by_caller_rollback", 3),
            ("test_ordinary_dictionary_writers_keep_payload_and_unbounded_contract", 1),
        ),
        "not sqlite",
    ),
    "admission9": (
        BOUNDED,
        (
            ("test_common_repository_create_checks_source_before_first_write", 1),
            ("test_invalid_part_reference_refuses_before_order_text_admission", 1),
            ("test_exhausted_version_refuses_new_enrollment_but_preserves_replay", 2),
            ("test_actual_projection_preparation_refuses_before_savepoint_or_write", 1),
            ("test_quote_writer_never_calls_generic_order_save", 1),
            ("test_source_utf8_boundary_is_checked_before_enrollment", 3),
        ),
        "not sqlite",
    ),
    "history9": (
        BOUNDED,
        (
            ("test_historical_replay_does_not_hydrate_oversized_current_text", 1),
            ("test_invalid_version_refuses_before_generic_payload_fetch", 6),
            ("test_two_transition_claims_refuse_before_generic_payload_fetch", 1),
            ("test_quote_outbox_pointer_cannot_prefetch_generic_order_json", 1),
        ),
        "not sqlite",
    ),
    "guards9": (
        BOUNDED,
        (
            ("test_order_timestamp_guard_refuses_before_driver_conversion", 3),
            ("test_order_row_lock_is_retained_during_prepare_and_persist", 1),
            ("test_small_compressed_text_is_refused_by_length_without_hydration", 1),
            ("test_bypassed_prepared_projection_refuses_before_any_write", 4),
        ),
        "not sqlite",
    ),
}
PG_COUNTS = {
    "metadata_sync": 7,
    "metadata_outbox": 7,
    "metadata_relations": 9,
    "service_bridge": 4,
    "writer5": 5,
    "admission9": 9,
    "history9": 9,
    "guards9": 9,
}
JUNIT_COUNTS = {
    "service27": 27,
    "atomic18_corruption": 18,
    "atomic18_other": 18,
    "response50": 50,
    "response64": 64,
    "static6": 6,
    "selection_static12": 12,
}
CHECK_NAMES = (
    "test_fixed_postgres_selection_and_argv",
    "test_typed_postgres_collection_contract",
    "test_closed_postgres_reports_and_identities",
    "test_metadata_observer_and_bridge_registration",
    "test_numeric_failure_bounds_and_static_exactness",
    "test_fixed_junit_maps_and_parser",
)
STATIC_NAMES = (
    "test_repository_contract",
    "test_python_lint",
    "test_python_format",
    "test_production_types",
    "test_openapi_contract",
    "test_generated_client_contract",
)


def load_recipe(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/ci" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def pg(monkeypatch):
    monkeypatch.setenv("OCWP_INTEGRITY_GROUP", "metadata_relations")
    return load_recipe("quote_integrity_postgres")


def pg_items(module):
    source, functions, _ = module.selection()
    names = [name for name, count in functions for _ in range(count)]
    parameters = zip(names, module.expected_parameters(), strict=True)
    items = []
    for index, (name, params) in enumerate(parameters):
        suffix = "[postgres]" if source == BRIDGE else f"[observed-{index}]"
        items.append(
            SimpleNamespace(
                path=ROOT / source,
                originalname=name,
                nodeid=f"{source}::{name}{suffix}",
                callspec=SimpleNamespace(params=params.copy()),
            )
        )
    return items


def pg_identity(node, index=0):
    schema = f"ocwp_identity_migration_{index:032x}"
    return {
        "node": node,
        "dialect": "postgresql",
        "driver": "psycopg",
        "driver_version": "3.3.4",
        "database": "ocwp_quote_micro_test",
        "server_version_num": 180004,
        "server_encoding": "UTF8",
        "client_encoding": "UTF8",
        "schema_revision": "0013",
        "probe_connection_closed": True,
        "schema": schema,
        "search_path": schema,
    }


def pg_report(module):
    nodes = [item.nodeid for item in pg_items(module)]
    return {
        "schema": 1,
        "nodes": nodes,
        "postgres_identities": [pg_identity(node, i) for i, node in enumerate(nodes)],
        "collection_count": len(nodes),
        "collection_errors": 0,
        "unhandled_errors": 0,
        "protocol_errors": 0,
        "session_finished": True,
        "session_exitstatus": 0,
        "reports": [
            {"node": node, "when": when, "outcome": "passed", "seconds": 0.01}
            for node in nodes
            for when in ("setup", "call", "teardown")
        ],
    }


def failure_summary(count):
    return {
        "schema": 1,
        "stage": 3,
        "session_exitstatus": 1,
        "collection_count": count,
        "collection_errors": 0,
        "unhandled_errors": 0,
        "protocol_errors": 0,
        "report_count": count * 3,
        "setup_reports": count,
        "call_reports": count,
        "teardown_reports": count,
        "failed_reports": 1,
        "skipped_reports": 0,
    }


def marker(prefix, value):
    return (
        prefix
        + json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
        + b"\n"
    )


def test_fixed_postgres_selection_and_argv(pg, monkeypatch):
    assert pg.PG_GROUPS == PG_SELECTIONS
    for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PGHOST", "PGOPTIONS"):
        monkeypatch.setenv(name, "untrusted-setting")
    fixture = {"identity_migration_database": "postgres"}
    pairs = (("sync_changes", "entity_type"), ("outbox_events", "aggregate_type"))
    faults = (
        "mutable",
        "wrong_type",
        "wrong_expression",
        "wrong_discriminator",
        "jsonb",
        "virtual",
        "inherited",
    )
    expected = {
        group: [
            fixture | {"table": table, "discriminator": discriminator, "fault": fault}
            for fault in faults
        ]
        for group, (table, discriminator) in zip(
            ("metadata_sync", "metadata_outbox"), pairs, strict=True
        )
    }
    expected["metadata_relations"] = [
        fixture | {"table": table, "discriminator": discriminator, "replacement": replacement}
        for table, discriminator in pairs
        for replacement in ("partitioned", "view", "missing")
    ]
    expected["metadata_relations"].extend(
        fixture | {"shadow": shadow} for shadow in ("function", "operator")
    )
    expected["metadata_relations"].append(fixture)
    expected["service_bridge"] = [fixture] * 4
    expected["writer5"] = [
        fixture,
        fixture | {"failure_after": "sync_changes"},
        fixture | {"failure_after": "outbox_events"},
        fixture | {"failure_after": "caller"},
        fixture,
    ]
    expected["admission9"] = [
        fixture,
        fixture,
        fixture | {"replay": False},
        fixture | {"replay": True},
        fixture,
        fixture,
        fixture | {"delta": -1},
        fixture | {"delta": 0},
        fixture | {"delta": 1},
    ]
    expected["history9"] = [
        fixture,
        fixture | {"version": None},
        fixture | {"version": 0},
        fixture | {"version": 2},
        fixture | {"version": -1},
        fixture | {"version": True},
        fixture | {"version": "1"},
        fixture,
        fixture,
    ]
    expected["guards9"] = [
        fixture | {"value": "infinity"},
        fixture | {"value": "-infinity"},
        fixture | {"value": "10000-01-01 00:00:00+00"},
        fixture,
        fixture,
        fixture | {"field": "raw_json", "value": "{}"},
        fixture | {"field": "raw_octets", "value": 1},
        fixture | {"field": "canonical_utf8", "value": b"{}"},
        fixture | {"field": "payload", "value": {"version": True}},
    ]
    for group, selection in PG_SELECTIONS.items():
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        source, functions, expression = selection
        assert pg.selection() == selection
        assert pg.case_count() == PG_COUNTS[group]
        assert pg.expected_parameters() == expected[group]
        for actual, wanted in zip(pg.expected_parameters(), expected[group], strict=True):
            assert type(actual) is dict and actual.keys() == wanted.keys()
            assert all(type(key) is str for key in actual)
            for key, value in wanted.items():
                assert type(actual[key]) is type(value)
                if type(value) is dict:
                    assert list(actual[key]) == ["version"]
                    assert type(next(iter(actual[key]))) is str
                    assert actual[key]["version"] is True
        args = pg.service_argv("a" * 64)
        assert args[:5] == ["docker", "exec", "a" * 64, "env", "-i"]
        assert args[-len(functions) :] == [f"{source}::{name}" for name, _ in functions]
        assert args[args.index("-k") + 1] == expression
        assert f"OCWP_INTEGRITY_GROUP={group}" in args
        assert "scripts.ci.quote_integrity_postgres" in args
        assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1" in args
        assert {
            "--tb=short",
            "--no-showlocals",
            "--show-capture=no",
            "--capture=fd",
            "--maxfail=1",
        } <= set(args)
        assert [arg for arg in args if arg.startswith("OCWP_TEST_DATABASE_URL=")] == [
            "OCWP_TEST_DATABASE_URL=postgresql+psycopg://ocwp:ocwp-synthetic"
            "@127.0.0.1:5432/ocwp_quote_micro_test"
        ]
        assert "untrusted-setting" not in " ".join(args)
        assert not any("[postgres]" in arg for arg in args)
    for group in ("", "metadata", "postgres", "static6", "service27", "selection_static12"):
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        with pytest.raises(pg.ProofFailure, match="service_selection"):
            pg.selection()


def test_typed_postgres_collection_contract(pg, monkeypatch):
    for group in PG_SELECTIONS:
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        items = pg_items(pg)
        offset = 0
        for _, count in PG_SELECTIONS[group][1]:
            items[offset : offset + count] = reversed(items[offset : offset + count])
            offset += count
        hook = pg.ServiceReportHook()
        hook.pytest_collection_finish(SimpleNamespace(items=items))
        assert hook.value["nodes"] == [item.nodeid for item in items]
        assert hook.value["collection_count"] == PG_COUNTS[group]
        assert hook.value["protocol_errors"] == 0
    monkeypatch.setenv("OCWP_INTEGRITY_GROUP", "metadata_relations")
    for fault in (
        "source",
        "function",
        "keys",
        "duplicate_row",
        "missing",
        "extra",
        "duplicate_node",
        "function_order",
        "missing_callspec",
        "wrong_pair",
        "wrong_shadow",
    ):
        items = pg_items(pg)
        if fault == "source":
            items[0].path = ROOT / BRIDGE
        elif fault == "function":
            items[0].originalname = MALFORMED
        elif fault == "keys":
            items[0].callspec.params["extra"] = "postgres"
        elif fault == "duplicate_row":
            items[1].callspec.params = items[0].callspec.params.copy()
        elif fault == "missing":
            items.pop()
        elif fault == "extra":
            items.append(deepcopy(items[-1]))
        elif fault == "duplicate_node":
            items[1].nodeid = items[0].nodeid
        elif fault == "function_order":
            items[0], items[6] = items[6], items[0]
        elif fault == "missing_callspec":
            del items[0].callspec
        elif fault == "wrong_pair":
            items[0].callspec.params["discriminator"] = "aggregate_type"
        else:
            items[6].callspec.params["shadow"] = "unknown"
        hook = pg.ServiceReportHook()
        with pytest.raises(pytest.UsageError, match="service_selection"):
            hook.pytest_collection_finish(SimpleNamespace(items=items))
        assert hook.value["nodes"] == []
        assert hook.value["protocol_errors"] == 1
    for value in (True, 1, b"postgres", ["postgres"], "sqlite"):
        items = pg_items(pg)
        items[0].callspec.params["identity_migration_database"] = value
        with pytest.raises(pytest.UsageError, match="service_selection"):
            pg.ServiceReportHook().pytest_collection_finish(SimpleNamespace(items=items))

    class OtherString(str):
        pass

    for replace_key in (False, True):
        items = pg_items(pg)
        params = items[0].callspec.params
        if replace_key:
            params[OtherString("table")] = params.pop("table")
        else:
            params["table"] = OtherString(params["table"])
        with pytest.raises(pytest.UsageError, match="service_selection"):
            pg.ServiceReportHook().pytest_collection_finish(SimpleNamespace(items=items))
    prefix = f"{METADATA}::{RELATIONS}"
    assert pg.selected_node(prefix + "[" + "x" * 62 + "]", RELATIONS)
    for suffix in ("[" + "x" * 63 + "]", "[" + "\\" * 32 + "]", "[é]", "[x\n]", "x"):
        assert not pg.selected_node(prefix + suffix, RELATIONS)
    for group in ("metadata_sync", "metadata_outbox"):
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        for value in (True, "unknown"):
            items = pg_items(pg)
            items[0].callspec.params["fault"] = value
            with pytest.raises(pytest.UsageError, match="service_selection"):
                pg.ServiceReportHook().pytest_collection_finish(SimpleNamespace(items=items))
        items = pg_items(pg)
        items[1].callspec.params = items[0].callspec.params.copy()
        with pytest.raises(pytest.UsageError, match="service_selection"):
            pg.ServiceReportHook().pytest_collection_finish(SimpleNamespace(items=items))
    monkeypatch.setenv("OCWP_INTEGRITY_GROUP", "service_bridge")
    function = PG_SELECTIONS["service_bridge"][1][0][0]
    assert pg.selected_node(f"{BRIDGE}::{function}[postgres]", function)
    assert not pg.selected_node(f"{BRIDGE}::{function}[sqlite]", function)
    for group, index, key, value in (
        ("writer5", 1, "failure_after", True),
        ("writer5", 1, "failure_after", "unknown"),
        ("admission9", 2, "replay", 0),
        ("admission9", 3, "replay", 1),
        ("admission9", 2, "replay", "False"),
        ("admission9", 6, "delta", -1.0),
        ("admission9", 7, "delta", False),
        ("admission9", 8, "delta", True),
        ("admission9", 8, "delta", 2),
        ("history9", 1, "version", "None"),
        ("history9", 2, "version", False),
        ("history9", 3, "version", 2.0),
        ("history9", 4, "version", -1.0),
        ("history9", 5, "version", 1),
        ("history9", 6, "version", 1),
        ("guards9", 0, "value", b"infinity"),
        ("guards9", 0, "value", "unknown"),
        ("guards9", 5, "field", OtherString("raw_json")),
        ("guards9", 5, "value", b"{}"),
        ("guards9", 5, "value", bytearray(b"{}")),
        ("guards9", 6, "value", True),
        ("guards9", 6, "value", 1.0),
        ("guards9", 7, "value", "{}"),
        ("guards9", 7, "value", bytearray(b"{}")),
        ("guards9", 7, "value", b"{ }"),
        ("guards9", 8, "value", {"version": 1}),
        ("guards9", 8, "value", {"version": False}),
        ("guards9", 8, "value", {"version": "true"}),
        ("guards9", 8, "value", {"other": True}),
        ("guards9", 8, "value", {b"version": True}),
        ("guards9", 8, "value", {OtherString("version"): True}),
        ("guards9", 8, "value", {"version": True, "extra": True}),
        ("guards9", 8, "value", []),
    ):
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        items = pg_items(pg)
        items[index].callspec.params[key] = value
        hook = pg.ServiceReportHook()
        with pytest.raises(pytest.UsageError, match="service_selection"):
            hook.pytest_collection_finish(SimpleNamespace(items=items))
        assert hook.value["nodes"] == [] and hook.value["protocol_errors"] == 1
    for group, first, second in (
        ("writer5", 1, 2),
        ("admission9", 2, 3),
        ("admission9", 6, 7),
        ("history9", 1, 2),
        ("guards9", 0, 1),
        ("guards9", 5, 6),
        ("guards9", 5, 7),
        ("guards9", 5, 8),
        ("guards9", 6, 7),
        ("guards9", 6, 8),
        ("guards9", 7, 8),
    ):
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        items = pg_items(pg)
        items[second].callspec.params = items[first].callspec.params.copy()
        with pytest.raises(pytest.UsageError, match="service_selection"):
            pg.ServiceReportHook().pytest_collection_finish(SimpleNamespace(items=items))
        if group == "guards9" and first >= 5:
            items = pg_items(pg)
            left, right = items[first].callspec.params, items[second].callspec.params
            left["value"], right["value"] = right["value"], left["value"]
            with pytest.raises(pytest.UsageError, match="service_selection"):
                pg.ServiceReportHook().pytest_collection_finish(SimpleNamespace(items=items))
    for group in ("writer5", "admission9", "history9", "guards9"):
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        for fault in ("function_order", "extra_key", "missing_key"):
            items = pg_items(pg)
            if fault == "function_order":
                items[0], items[-1] = items[-1], items[0]
            elif fault == "extra_key":
                items[0].callspec.params["extra"] = True
            else:
                del items[0].callspec.params["identity_migration_database"]
            with pytest.raises(pytest.UsageError, match="service_selection"):
                pg.ServiceReportHook().pytest_collection_finish(SimpleNamespace(items=items))


def test_closed_postgres_reports_and_identities(pg, monkeypatch, tmp_path):
    assert pg.LIMIT == 16 * 1024
    for group in PG_SELECTIONS:
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        good = pg_report(pg)
        assert pg.service_result(json.dumps(good)) == good
        assert len(good["reports"]) == PG_COUNTS[group] * 3
    monkeypatch.setenv("OCWP_INTEGRITY_GROUP", "metadata_relations")
    good = pg_report(pg)
    for field, value in (
        ("collection_count", True),
        ("collection_errors", 1),
        ("protocol_errors", 1),
        ("unhandled_errors", 1),
        ("session_finished", False),
        ("session_exitstatus", 1),
    ):
        with pytest.raises(pg.ProofFailure):
            pg.service_result(json.dumps(good | {field: value}))
    for field, value in (
        ("when", "teardown"),
        ("node", good["nodes"][1]),
        ("outcome", "skipped"),
        ("outcome", "failed"),
        ("seconds", True),
        ("seconds", 20),
        ("captured", "private"),
    ):
        bad = deepcopy(good)
        bad["reports"][0][field] = value
        with pytest.raises(pg.ProofFailure):
            pg.service_result(json.dumps(bad))
    for field in ("reports", "nodes", "postgres_identities"):
        for duplicate in (False, True):
            bad = deepcopy(good)
            if duplicate:
                bad[field][1] = deepcopy(bad[field][0])
            else:
                bad[field].pop()
            with pytest.raises(pg.ProofFailure):
                pg.service_result(json.dumps(bad))
    for field, value in (
        ("node", good["nodes"][1]),
        ("database", "external_test"),
        ("server_version_num", "180004"),
        ("schema_revision", "0012"),
        ("probe_connection_closed", 1),
        ("client_encoding", "LATIN1"),
        ("search_path", "public"),
        ("payload", "private"),
    ):
        bad = deepcopy(good)
        bad["postgres_identities"][0][field] = value
        with pytest.raises(pg.ProofFailure, match="service_postgres_identity"):
            pg.service_result(json.dumps(bad))
    bad = deepcopy(good)
    for key in ("schema", "search_path"):
        bad["postgres_identities"][1][key] = bad["postgres_identities"][0][key]
    with pytest.raises(pg.ProofFailure, match="service_postgres_identity"):
        pg.service_result(json.dumps(bad))
    raw = json.dumps(good)
    assert pg.service_result(raw + " " * (pg.LIMIT - len(raw) - 1)) == good
    for invalid in (raw + " " * (pg.LIMIT - len(raw)), raw[:-1] + ', "schema": 1}'):
        with pytest.raises(pg.ProofFailure):
            pg.service_result(invalid)
    hook = pg.ServiceReportHook()
    hook.pytest_collection_finish(SimpleNamespace(items=pg_items(pg)))
    by_node = {identity["node"]: identity for identity in good["postgres_identities"]}
    for row in good["reports"]:
        hook.pytest_runtest_logreport(
            SimpleNamespace(
                nodeid=row["node"],
                when=row["when"],
                outcome="passed",
                duration=0.01,
                user_properties=[("ocwp_postgres_identity", by_node[row["node"]])],
                longrepr="private",
                capstdout="private",
            )
        )
    target = tmp_path / "closed.json"
    monkeypatch.setattr(pg, "SERVICE_REPORT", str(target))
    hook.pytest_sessionfinish(SimpleNamespace(), 0)
    assert pg.service_result(target.read_text()) == good
    assert len(hook.value["reports"]) == 27 and hook.value["protocol_errors"] == 0
    assert "private" not in target.read_text()
    hook.pytest_runtest_logreport(
        SimpleNamespace(
            nodeid=good["nodes"][-1],
            when="call",
            outcome="passed",
            duration=0.01,
        )
    )
    assert len(hook.value["reports"]) == 27 and hook.value["protocol_errors"] == 1
    for fault in ("missing", "duplicate", "foreign", "xfail"):
        node = good["nodes"][0]
        properties = [("ocwp_postgres_identity", pg_identity(node))]
        if fault == "missing":
            properties = []
        elif fault == "duplicate":
            properties *= 2
        elif fault == "foreign":
            properties[0][1]["node"] = good["nodes"][1]
        row = SimpleNamespace(
            nodeid=node,
            when="teardown",
            outcome="passed",
            duration=0.01,
            user_properties=properties,
        )
        if fault == "xfail":
            row.wasxfail = "private"
        hook = pg.ServiceReportHook()
        hook.pytest_collection_finish(SimpleNamespace(items=pg_items(pg)))
        hook.pytest_runtest_logreport(row)
        assert hook.value["protocol_errors"] == 1
        assert hook.value["postgres_identities"] == []


def test_metadata_observer_and_bridge_registration(pg, monkeypatch):
    engine = object()
    events = []

    def probe(actual_engine, actual_node):
        assert actual_engine is engine and actual_node == node
        events.append("final_probe")
        return pg_identity(node)

    monkeypatch.setattr(pg, "probe_postgres_identity", probe)
    for group in PG_SELECTIONS:
        if group == "service_bridge":
            continue
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        node = pg_items(pg)[0].nodeid
        events.clear()
        request = SimpleNamespace(node=SimpleNamespace(nodeid=node, user_properties=[]))
        observer = pg.observe_postgres((object(), engine), request)
        next(observer)
        assert events == [] and request.node.user_properties == []
        events.append("body_transaction_closed")
        with pytest.raises(StopIteration):
            next(observer)
        assert events == ["body_transaction_closed", "final_probe"]
        assert request.node.user_properties == [("ocwp_postgres_identity", pg_identity(node))]
    monkeypatch.setenv("OCWP_INTEGRITY_GROUP", "metadata_relations")
    node = pg_items(pg)[0].nodeid
    request = SimpleNamespace(node=SimpleNamespace(nodeid=node, user_properties=[]))
    monkeypatch.setattr(
        pg,
        "probe_postgres_identity",
        lambda *_args: pg_identity(node) | {"schema_revision": "0012"},
    )
    request.node.user_properties.clear()
    observer = pg.observe_postgres((object(), engine), request)
    next(observer)
    with pytest.raises(pg.ProofFailure, match="service_postgres_identity"):
        next(observer)
    assert request.node.user_properties == []
    for group in PG_SELECTIONS:
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        calls = []
        observer_plugin = object()
        monkeypatch.setattr(pg, "postgres_observer_plugin", lambda plugin=observer_plugin: plugin)
        config = SimpleNamespace(
            pluginmanager=SimpleNamespace(register=lambda *args, saved=calls: saved.append(args))
        )
        monkeypatch.delenv("OCWP_QUOTE_SERVICE_INITIAL", raising=False)
        with pytest.raises(pg.ProofFailure, match="service_hook_context"):
            pg.pytest_configure(config)
        assert calls == []
        monkeypatch.setenv("OCWP_QUOTE_SERVICE_INITIAL", "contained")
        pg.pytest_configure(config)
        assert isinstance(calls[0][0], pg.ServiceReportHook)
        assert calls[0][1] == "quote-service-closed-report"
        expected = (
            [] if group == "service_bridge" else [(observer_plugin, "quote-postgres-observer")]
        )
        assert calls[1:] == expected
    monkeypatch.setenv("OCWP_INTEGRITY_GROUP", "service_bridge")
    bridge_node = pg_items(pg)[0].nodeid
    request.node.nodeid = bridge_node
    with pytest.raises(pg.ProofFailure, match="service_selection"):
        next(pg.observe_postgres((object(), engine), request))
    assert request.node.user_properties == []


def test_numeric_failure_bounds_and_static_exactness(pg, monkeypatch):
    assert pg.STATIC_FAILURE_LIMIT == 24 * 1024
    for group, ceiling in (
        ("metadata_sync", 21),
        ("metadata_outbox", 21),
        ("metadata_relations", 27),
        ("service_bridge", 18),
        ("writer5", 18),
        ("admission9", 27),
        ("history9", 27),
        ("guards9", 27),
    ):
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        boundary = failure_summary(ceiling // 3) | {"collection_count": PG_COUNTS[group]}
        raw = marker(pg.SERVICE_FAILURE_MARKER, boundary)
        assert pg.service_failure_diagnostic(raw, returncode=1) == boundary
        overflow = boundary | {
            "report_count": ceiling + 1,
            "setup_reports": boundary["setup_reports"] + 1,
        }
        with pytest.raises(pg.ProofFailure):
            pg.service_failure_diagnostic(marker(pg.SERVICE_FAILURE_MARKER, overflow), returncode=1)
    monkeypatch.setenv("OCWP_INTEGRITY_GROUP", "metadata_relations")
    good = failure_summary(9)
    assert good["report_count"] == 27
    raw = marker(pg.SERVICE_FAILURE_MARKER, good)
    assert pg.service_failure_diagnostic(raw, returncode=1) == good
    for change in (
        {"report_count": 28, "setup_reports": 10},
        {"report_count": True},
        {"failed_reports": 28},
        {"skipped_reports": -1},
        {"report_count": 26},
        {"private": "text"},
    ):
        with pytest.raises(pg.ProofFailure):
            pg.service_failure_diagnostic(
                marker(pg.SERVICE_FAILURE_MARKER, good | change), returncode=1
            )
    for tool in range(6):
        output = {
            "schema": 2,
            "tool": tool,
            "kind": 1,
            "returncode": 1,
            "output_bytes": 0,
            "output_truncated": False,
            "output_base64": "",
        }
        protocol = failure_summary(tool + 1) | {"collection_count": 6}
        raw = marker(pg.STATIC_FAILURE_MARKER, output)
        assert pg.static_failure_diagnostic(raw, failure=protocol) == output
        for change in (
            {"collection_count": 9},
            {"report_count": 27, "setup_reports": 9, "call_reports": 9, "teardown_reports": 9},
            {"failed_reports": 2},
            {"schema": True},
        ):
            with pytest.raises(pg.ProofFailure, match="static_diagnostic_protocol"):
                pg.static_failure_diagnostic(raw, failure=protocol | change)
    assert protocol["report_count"] == 18


def junit_document(module):
    root = ET.Element("testsuites", name="pytest tests")
    suite = ET.SubElement(
        root,
        "testsuite",
        name="pytest",
        errors="0",
        failures="0",
        skipped="0",
        tests=str(module.CASE_COUNT),
        time="0.010",
        timestamp="2026-10-17T00:00:00",
        hostname="synthetic",
    )
    for path, cases in module.SELECTION:
        for name, count, suffix_limit in cases:
            for index in range(count):
                ET.SubElement(
                    suite,
                    "testcase",
                    classname=module.SOURCE_CLASSES[path],
                    name=f"{name}[{index}]" if suffix_limit else name,
                    time="0.000",
                )
    return root


def xml_text(root):
    return ET.tostring(root, encoding="unicode")


def test_fixed_junit_maps_and_parser(monkeypatch, tmp_path):
    modules = {}
    base = "services/platform/tests/quotes/"
    sources = {
        "service27": (
            base + "test_quote_application_service.py",
            "tests/operations/test_quote_integrity_selection.py",
        ),
        "atomic18_corruption": (base + "test_quote_atomic_effects.py",),
        "atomic18_other": (base + "test_quote_atomic_effects.py",),
        "response50": (base + "test_quote_command_response.py",),
        "response64": (base + "test_quote_command_response.py",),
        "static6": ("tests/operations/test_quote_integrity_static_contracts.py",),
        "selection_static12": (
            "tests/operations/test_quote_integrity_selection.py",
            "tests/operations/test_quote_integrity_static_contracts.py",
        ),
    }
    for group, count in JUNIT_COUNTS.items():
        # The JUnit recipe freezes group constants at import time.
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        module = load_recipe("quote_integrity_checks")
        modules[group] = module
        assert module.GROUP_COUNTS == JUNIT_COUNTS
        assert set(module.GROUPS) == set(JUNIT_COUNTS)
        assert group == module.GROUP_KEY and count == module.CASE_COUNT
        assert sum(module.EXPECTED_COUNTS.values()) == count
        assert tuple(path for path, _ in module.SELECTION) == sources[group]
        assert [
            path.removesuffix(".py").replace("/", ".") for path in sources[group]
        ] == module.CLASS_NAMES
        assert (
            tuple(f"{path}::{name}" for path, cases in module.SELECTION for name, _, _ in cases)
            == module.NODES
        )
        assert module.PYTEST[-len(module.NODES) :] == list(module.NODES)
        assert module.PYTEST[:2] == ["env", "-i"] and "-k" not in module.PYTEST
        static = group in ("static6", "selection_static12")
        assert module.LIMIT == 16 * 1024
        assert (32 * 1024 if static else 16 * 1024) == module.SPOOL_LIMIT
        assert ("OCWP_QUOTE_SERVICE_INITIAL=contained" in module.PYTEST) is static
        assert not any(
            "DATABASE_URL=" in arg or "quote_integrity_postgres" in arg for arg in module.PYTEST
        )
        assert all("[" not in node for node in module.NODES)
        root = junit_document(module)
        value = module.parse_junit(xml_text(root))
        assert value["tests"] == count and value["expected_counts"] == module.EXPECTED_COUNTS
        assert value["class_names"] == module.CLASS_NAMES
        assert value["observed_cases"] == [case.attrib["name"] for case in root[0]]
        assert value["failures"] == value["errors"] == value["skipped"] == 0
        assert value["session_finished"] is True
        for fault in (
            "missing",
            "duplicate",
            "source",
            "function",
            "order",
            "skipped",
            "failure",
            "duration",
            "capture",
            "extra_attribute",
            "text",
        ):
            bad = deepcopy(root)
            suite = bad[0]
            if fault == "missing":
                suite.remove(suite[-1])
            elif fault == "duplicate":
                suite[1].attrib["name"] = suite[0].attrib["name"]
            elif fault == "source":
                suite[0].attrib["classname"] = "tests.foreign"
            elif fault == "function":
                suite[0].attrib["name"] = "test_foreign[0]"
            elif fault == "order":
                if len(module.NODES) > 1:
                    suite[0], suite[-1] = suite[-1], suite[0]
                else:
                    # The sole function has no function sequence to swap.
                    suite[0].attrib["name"] = "test_foreign[0]"
            elif fault == "skipped":
                suite.attrib["skipped"] = "1"
            elif fault == "failure":
                ET.SubElement(suite[0], "failure", message="private")
            elif fault == "duration":
                suite[0].attrib["time"] = "20.000"
            elif fault == "capture":
                ET.SubElement(suite[0], "system-out").text = "private"
            elif fault == "extra_attribute":
                suite[0].attrib["file"] = "foreign.py"
            else:
                suite[0].text = "private"
            with pytest.raises(module.Refusal):
                module.parse_junit(xml_text(bad))
        function, _, suffix_limit = module.SELECTION[0][1][0]
        bad = deepcopy(root)
        if suffix_limit:
            bad[0][0].attrib["name"] = function + "[" + "x" * (suffix_limit - 2) + "]"
            module.parse_junit(xml_text(bad))
            bad[0][0].attrib["name"] = function + "[" + "x" * (suffix_limit - 1) + "]"
        else:
            bad[0][0].attrib["name"] = function + "[0]"
        with pytest.raises(module.Refusal):
            module.parse_junit(xml_text(bad))
        raw = xml_text(root)
        size = len(raw.encode("utf-8"))
        assert size < module.LIMIT
        module.parse_junit(raw + " " * (module.LIMIT - size - 1))
        for invalid in (
            raw + " " * (module.LIMIT - size),
            '<!DOCTYPE testsuites [<!ENTITY value "private">]>' + raw,
        ):
            with pytest.raises(module.Refusal):
                module.parse_junit(invalid)
    service = modules["service27"]
    assert service.EXPECTED_COUNTS["test_nul_order_reference_refuses_before_text_hydration"] == 2
    assert service.SELECTION[1] == (
        "tests/operations/test_quote_integrity_selection.py",
        tuple((name, 1, 0) for name in CHECK_NAMES),
    )
    assert service.CLASS_NAMES == [
        "services.platform.tests.quotes.test_quote_application_service",
        "tests.operations.test_quote_integrity_selection",
    ]
    combined = modules["selection_static12"]
    assert (
        (
            "tests/operations/test_quote_integrity_selection.py",
            tuple((name, 1, 0) for name in CHECK_NAMES),
        ),
        (
            "tests/operations/test_quote_integrity_static_contracts.py",
            tuple((name, 1, 0) for name in STATIC_NAMES),
        ),
    ) == combined.SELECTION
    assert dict.fromkeys((*CHECK_NAMES, *STATIC_NAMES), 1) == combined.EXPECTED_COUNTS
    assert combined.CLASS_NAMES == [
        "tests.operations.test_quote_integrity_selection",
        "tests.operations.test_quote_integrity_static_contracts",
    ]
    assert (combined.SELECTION[1],) == modules["static6"].SELECTION
    assert modules["response50"].EXPECTED_COUNTS == {
        "test_numeric_fields_refuse_coercion_and_unsafe_values": 50
    }
    response_counts = modules["response64"].EXPECTED_COUNTS
    assert response_counts["test_service_projector_preserves_four_digit_receipt_year"] == 8
    for left, right in (("response50", "response64"), ("atomic18_corruption", "atomic18_other")):
        assert set(modules[left].NODES).isdisjoint(modules[right].NODES)
    assert sum(JUNIT_COUNTS.values()) + sum(PG_COUNTS.values()) == 254
    assert (
        sum(PG_COUNTS[group] for group in ("writer5", "admission9", "history9", "guards9"))
        + JUNIT_COUNTS["selection_static12"]
        == 44
    )
    assert (
        sum(count for group, count in JUNIT_COUNTS.items() if group != "selection_static12")
        + sum(
            PG_COUNTS[group]
            for group in (
                "metadata_sync",
                "metadata_outbox",
                "metadata_relations",
                "service_bridge",
            )
        )
        == 210
    )
    assert combined.LOADER_BRANCH == "refs/heads/codex/quote-loader-writer-checks"
    assert combined.LOADER_WORKFLOW == ".github/workflows/quote-loader-writer-checks.yml"
    monkeypatch.chdir(ROOT)
    for key, value in (
        ("GITHUB_EVENT_NAME", "push"),
        ("GITHUB_REPOSITORY", "synthetic/ocwp"),
        ("GITHUB_RUN_ID", "123"),
        ("GITHUB_RUN_NUMBER", "1"),
        ("GITHUB_RUN_ATTEMPT", "1"),
        ("GITHUB_SHA", "a" * 40),
        ("RUNNER_TEMP", str(tmp_path)),
    ):
        monkeypatch.setenv(key, value)
    branches = (
        (combined.BRANCH, combined.WORKFLOW),
        (combined.STYLE_BRANCH, combined.STYLE_WORKFLOW),
        (combined.FORMAT_BRANCH, combined.FORMAT_WORKFLOW),
        (combined.LOADER_BRANCH, combined.LOADER_WORKFLOW),
    )
    for group, module in modules.items():
        for branch, workflow in branches:
            monkeypatch.setenv("GITHUB_REF", branch)
            monkeypatch.setenv("GITHUB_WORKFLOW_REF", f"synthetic/ocwp/{workflow}@{branch}")
            accepted = (
                (branch == combined.BRANCH and group != "selection_static12")
                or (
                    branch in (combined.STYLE_BRANCH, combined.FORMAT_BRANCH) and group == "static6"
                )
                or (branch == combined.LOADER_BRANCH and group == "selection_static12")
            )
            if accepted:
                module.gate()
            else:
                with pytest.raises(module.Refusal):
                    module.gate()
            for _, foreign_workflow in branches:
                if foreign_workflow != workflow:
                    monkeypatch.setenv(
                        "GITHUB_WORKFLOW_REF", f"synthetic/ocwp/{foreign_workflow}@{branch}"
                    )
                    with pytest.raises(module.Refusal):
                        module.gate()
