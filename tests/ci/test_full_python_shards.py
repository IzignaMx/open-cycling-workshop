from __future__ import annotations

import hashlib

import pytest
from test_verify_v01 import MODULE, full_python_receipt


def test_closed_shard_commands_collect_both_original_roots():
    commands = [MODULE.full_python_args(shard) for shard in ("a", "b")]
    for shard, command in zip(("a", "b"), commands, strict=True):
        assert command[-2:] == ("tests", "services/platform/tests")
        assert command.count(f"--ocwp-full-shard={shard}") == 1
        assert not any(arg in command for arg in ("-k", "-m", "--lf", "--ff"))
    assert commands[0] != commands[1]
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.full_python_args("unknown")


def test_fixed_module_partition_is_disjoint_exhaustive_and_closed():
    expected = {
        "a": (
            "tests/",
            "bicycles/",
            "blobs/",
            "branding/",
            "cli/",
            "customers/",
            "db/",
            "events/",
            "identity/",
            "inventory/",
        ),
        "b": (
            "jobs/",
            "ops/",
            "quotes/",
            "service_orders/",
            "settings/",
            "sync/",
            "test_baseline_wire.py",
            "test_health.py",
            "test_model_registration.py",
            "test_openapi.py",
        ),
    }
    for shard, paths in expected.items():
        for path in paths:
            source = path if path == "tests/" else "services/platform/tests/" + path
            source += "test_example.py" if source.endswith("/") else ""
            assert MODULE.full_python_shard(source) == shard
    for source in (
        "services/platform/tests/unlisted/test_x.py",
        "services/platform/tests/test_new.py",
        "tests/../elsewhere.py",
        "/tests/test_x.py",
    ):
        with pytest.raises(MODULE.FullPythonEvidenceError):
            MODULE.full_python_shard(source)


def test_old_monolithic_schema_never_satisfies_shard_proof():
    receipt = full_python_receipt()
    receipt["schema"] = 1
    with pytest.raises(MODULE.FullPythonEvidenceError, match="schema"):
        MODULE.validate_full_python_receipt(receipt, receipt["identity"])


def test_module_hashes_resolve_against_current_source_paths():
    receipt = full_python_receipt()
    ordinary = receipt["collection"]["nodes"][-1]
    assert ordinary["module_sha256"] == hashlib.sha256(b"tests/ci/test_verify_v01.py").hexdigest()


def test_serial_pair_requires_independently_bound_cleanup_and_predecessor():
    from test_verify_v01 import full_python_pair

    receipts, expected, cleanups = full_python_pair()
    digest = MODULE.validate_full_python_cleanup(cleanups["a"], expected["a"])
    assert digest == receipts["b"]["containment"]["predecessor_cleanup_sha256"]
    assert MODULE.validate_full_python_pair(receipts, expected, cleanups)["collected"] == 70
    receipts["b"]["containment"]["predecessor_cleanup_sha256"] = "0" * 64
    with pytest.raises(MODULE.FullPythonEvidenceError, match="pair_predecessor"):
        MODULE.validate_full_python_pair(receipts, expected, cleanups)


def test_plugin_rejects_nodeid_from_a_different_module():
    from types import SimpleNamespace

    from test_verify_v01 import fake_full_python_plugin

    plugin = fake_full_python_plugin()
    item = SimpleNamespace(
        path=MODULE.ROOT / "tests/ci/test_verify_v01.py",
        originalname="test_ordinary",
        nodeid="services/platform/tests/test_health.py::test_ordinary",
        callspec=None,
    )
    with pytest.raises(MODULE.FullPythonEvidenceError, match="node_module"):
        plugin.pytest_collection_finish(SimpleNamespace(items=[item]))


@pytest.mark.parametrize("shard", ["a", "b"])
def test_plugin_seals_complete_inventory_and_keeps_only_ordered_assigned_items(monkeypatch, shard):
    from copy import deepcopy
    from types import SimpleNamespace

    from test_verify_v01 import fake_full_python_plugin

    plugin = fake_full_python_plugin()
    plugin.identity = full_python_receipt(shard)["identity"]
    writes = []
    monkeypatch.setattr(
        MODULE, "write_full_python_json", lambda path, value: writes.append(deepcopy(value))
    )
    items = [
        SimpleNamespace(
            path=MODULE.ROOT / case.source,
            originalname=case.function,
            nodeid=f"{case.source}::{case.function}[{index}]",
            callspec=SimpleNamespace(params=case.params),
        )
        for index, case in enumerate(MODULE.FULL_CASES)
    ]
    original = list(items)
    session = SimpleNamespace(items=items)
    plugin.pytest_collection_finish(session)
    assert len(writes) == 1
    assert len(writes[0]["nodes"]) == len(MODULE.FULL_CASES)
    assert writes[0]["deselected"] == 0
    assert session.items == [
        item
        for item in original
        if MODULE.full_python_shard(item.path.relative_to(MODULE.ROOT).as_posix()) == shard
    ]
    assert list(plugin.outcomes) == [
        hashlib.sha256(item.nodeid.encode()).hexdigest() for item in session.items
    ]
    for item, node in zip(original, writes[0]["nodes"], strict=True):
        source = item.path.relative_to(MODULE.ROOT).as_posix()
        assert node["module_sha256"] == hashlib.sha256(source.encode()).hexdigest()
        assert node["node_sha256"] == hashlib.sha256(item.nodeid.encode()).hexdigest()
    assert sum(
        node["case"] in MODULE.FULL_SKIP_CASES for node in MODULE._full_assigned_nodes(writes[0])
    ) == (11 if shard == "a" else 47)
    assert sum(
        node["case"] in MODULE.FULL_REQUIRED_CASES
        for node in MODULE._full_assigned_nodes(writes[0])
    ) == (4 if shard == "a" else 7)
    foreign = next(item for item in original if item not in session.items)
    with pytest.raises(MODULE.FullPythonEvidenceError, match="unknown_report"):
        plugin.pytest_runtest_logreport(SimpleNamespace(nodeid=foreign.nodeid))


@pytest.mark.parametrize("fault", ["missing", "unknown", "extra", "duplicate", "case_module"])
def test_full_collection_rejects_malformed_module_assignments(fault):
    from copy import deepcopy

    from test_verify_v01 import refresh_inventory

    receipt = full_python_receipt()
    node = receipt["collection"]["nodes"][-1]
    if fault == "missing":
        del node["module_sha256"]
    elif fault == "unknown":
        node["module_sha256"] = "0" * 64
    elif fault == "extra":
        node["shard"] = "b"
    elif fault == "duplicate":
        receipt["collection"]["nodes"].append(deepcopy(node))
    else:
        receipt["collection"]["nodes"][0]["module_sha256"] = hashlib.sha256(
            b"services/platform/tests/test_health.py"
        ).hexdigest()
    refresh_inventory(receipt)
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.validate_full_python_receipt(receipt, receipt["identity"])


def test_partition_rejects_ambiguous_membership(monkeypatch):
    monkeypatch.setitem(
        MODULE.FULL_SHARD_SELECTORS, "b", (*MODULE.FULL_SHARD_SELECTORS["b"], "tests/")
    )
    with pytest.raises(MODULE.FullPythonEvidenceError, match="module_assignment"):
        MODULE.full_python_shard("tests/ci/test_verify_v01.py")


@pytest.mark.parametrize(
    "field",
    [
        "commit",
        "tree",
        "image_id",
        "pg_image_id",
        "run_id",
        "run_attempt",
        "workflow_sha256",
        "helper_sha256",
        "verifier_sha256",
        "uv_lock_sha256",
        "pnpm_lock_sha256",
    ],
)
def test_serial_pair_rejects_individually_valid_but_different_context(field):
    from test_verify_v01 import full_python_pair

    receipts, expected, cleanups = full_python_pair()
    previous = expected["b"][field]
    value = (
        "2"
        if field in ("run_id", "run_attempt")
        else ("sha256:" + "9" * 64 if field.endswith("image_id") else "9" * len(previous))
    )
    for identity in (
        expected["b"],
        receipts["b"]["identity"],
        receipts["b"]["collection"]["identity"],
        receipts["b"]["result"]["identity"],
        cleanups["b"]["identity"],
    ):
        identity[field] = value
    for key in ("commit", "run_id", "run_attempt"):
        cleanups["b"]["expected_commit" if key == "commit" else key] = expected["b"][key]
    with pytest.raises(MODULE.FullPythonEvidenceError, match="pair_context"):
        MODULE.validate_full_python_pair(receipts, expected, cleanups)


@pytest.mark.parametrize(
    "fault",
    ["missing_a", "missing_b", "unknown", "swapped", "same_nonce", "wrong_shard", "wrong_command"],
)
def test_serial_pair_rejects_missing_duplicate_or_wrong_identity(fault):
    from test_verify_v01 import full_python_pair

    receipts, expected, cleanups = full_python_pair()
    if fault.startswith("missing_"):
        receipts.pop(fault[-1])
    elif fault == "unknown":
        receipts["c"] = receipts["a"]
    elif fault == "swapped":
        receipts["a"], receipts["b"] = receipts["b"], receipts["a"]
    elif fault == "same_nonce":
        expected["b"]["nonce"] = expected["a"]["nonce"]
    elif fault == "wrong_shard":
        expected["b"]["shard"] = "a"
    else:
        expected["b"]["command_sha256"] = expected["a"]["command_sha256"]
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.validate_full_python_pair(receipts, expected, cleanups)


@pytest.mark.parametrize(
    "fault", ["missing", "extra", "reordered", "changed_hash", "other_subset", "overlap", "unrun"]
)
def test_serial_pair_rejects_incomplete_or_inconsistent_inventory(fault):
    from copy import deepcopy

    from test_verify_v01 import full_python_pair, refresh_inventory

    receipts, expected, cleanups = full_python_pair()
    b = receipts["b"]
    nodes = b["collection"]["nodes"]
    outcomes = b["result"]["outcomes"]
    ordinary_index = next(index for index, node in enumerate(nodes) if node["case"] is None)
    if fault == "missing":
        # The omitted ordinary A node leaves B's selected results individually valid.
        nodes.pop(ordinary_index)
    elif fault == "extra":
        extra = deepcopy(nodes[ordinary_index])
        extra["node_sha256"] = "8" * 64
        nodes.append(extra)
    elif fault == "reordered":
        # Reorder only A nodes: B itself remains valid, but full order disagrees.
        nodes[0], nodes[1] = nodes[1], nodes[0]
    elif fault == "changed_hash":
        nodes[ordinary_index]["node_sha256"] = "8" * 64
    elif fault == "other_subset":
        outcomes[:] = deepcopy(receipts["a"]["result"]["outcomes"])
    elif fault == "overlap":
        outcomes.append(deepcopy(receipts["a"]["result"]["outcomes"][-1]))
    else:
        outcomes[-1]["phases"] = [None, None, None]
        b["result"]["counts"] = MODULE._full_counts(
            outcomes, MODULE._full_assigned_nodes(b["collection"])
        )
    refresh_inventory(b)
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.validate_full_python_pair(receipts, expected, cleanups)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", 1),
        ("schema", True),
        ("kind", "cleanup"),
        ("status", "passed"),
        ("scope", "all"),
        ("expected_commit", "9" * 40),
        ("run_id", "99"),
        ("run_attempt", "2"),
        ("owner_manifest_present", False),
        ("owner_manifest_present", 1),
        ("owner_token", None),
        ("owner_token", "9" * 32),
        ("identity", None),
        ("outcome", "uncertain"),
        ("build_resource_cleanup", "verified"),
        ("qualification", "passed"),
    ],
)
def test_independent_cleanup_is_strict_and_source_nonce_bound(field, value):
    from test_verify_v01 import full_python_pair

    receipts, expected, cleanups = full_python_pair()
    cleanups["a"][field] = value
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.validate_full_python_pair(receipts, expected, cleanups)


@pytest.mark.parametrize("shard", ["a", "b"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("predecessor_cleanup_sha256", "9" * 64),
        ("worker_stopped", False),
        ("deadline", "timed_out"),
        ("final_probe", "unavailable"),
        ("pressure_events", {"worker": 0, "db": 1}),
    ],
)
def test_either_shard_needs_final_containment_and_serial_link(shard, field, value):
    from test_verify_v01 import full_python_pair

    receipts, expected, cleanups = full_python_pair()
    receipts[shard]["containment"][field] = value
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.validate_full_python_pair(receipts, expected, cleanups)


@pytest.mark.parametrize("shard", ["a", "b"])
@pytest.mark.parametrize("field", ["primary_cleanup", "independent_cleanup"])
def test_each_shard_requires_both_cleanup_proofs(shard, field):
    from test_verify_v01 import full_python_pair

    receipts, expected, cleanups = full_python_pair()
    receipts[shard][field] = "failed"
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.validate_full_python_pair(receipts, expected, cleanups)


def test_valid_absence_gate_does_not_turn_failed_workload_into_success():
    from test_verify_v01 import full_python_pair

    receipts, expected, cleanups = full_python_pair()
    receipts["a"].update(status="failed", failure="wall_budget")
    assert MODULE.validate_full_python_cleanup(cleanups["a"], expected["a"])
    with pytest.raises(MODULE.FullPythonEvidenceError, match="receipt_failed"):
        MODULE.validate_full_python_pair(receipts, expected, cleanups)


@pytest.mark.parametrize("shard", ["a", "b"])
@pytest.mark.parametrize("filename", ["receipt.json", "independent-cleanup.json"])
def test_pair_consumer_fails_all_controls_for_missing_peer_artifact(tmp_path, shard, filename):
    from test_verify_v01 import full_python_pair

    receipts, expected, cleanups = full_python_pair()
    for selected in ("a", "b"):
        (tmp_path / selected).mkdir()
        for name, value in (
            ("receipt.json", receipts[selected]),
            ("independent-cleanup.json", cleanups[selected]),
        ):
            if (selected, name) != (shard, filename):
                MODULE.write_full_python_json(tmp_path / selected / name, value)
    checks = MODULE.consume_full_python_pair(tmp_path, expected)
    assert [check.name for check in checks] == list(MODULE.FULL_CHECK_NAMES)
    assert all(check.status == "fail" for check in checks)


@pytest.mark.parametrize("shard", ["a", "b"])
def test_peer_identity_preserves_context_and_binds_new_command(shard):
    original = full_python_receipt()["identity"]
    peer = MODULE.full_python_peer_identity(original, shard, "9" * 32)
    assert peer["shard"] == shard
    assert peer["nonce"] == "9" * 32
    assert peer["command_sha256"] == MODULE._full_command_hash(shard)
    assert {
        key: value for key, value in peer.items() if key not in {"shard", "nonce", "command_sha256"}
    } == {
        key: value
        for key, value in original.items()
        if key not in {"shard", "nonce", "command_sha256"}
    }


@pytest.mark.parametrize("shard", ["a", "b"])
@pytest.mark.parametrize("fault", ["selection", "roots", "other_shard", "retry", "plugin"])
def test_plugin_rejects_any_command_outside_fixed_full_collection(monkeypatch, shard, fault):
    from types import SimpleNamespace

    identity = full_python_receipt(shard)["identity"]
    monkeypatch.setenv("OCWP_FULL_PYTHON_IDENTITY", MODULE._full_json(identity).decode())
    monkeypatch.setattr(
        MODULE, "_full_worker_preflight", lambda: pytest.fail("bad command reached preflight")
    )
    args = list(MODULE.full_python_args(shard))
    if fault == "selection":
        args += ["-k", "only_one"]
    elif fault == "roots":
        args[-2:] = ["tests/ci/test_verify_v01.py"]
    elif fault == "other_shard":
        args = list(MODULE.full_python_args("b" if shard == "a" else "a"))
    elif fault == "retry":
        args += ["--reruns", "1"]
    else:
        args += ["-p", "unreviewed"]
    with pytest.raises(MODULE.FullPythonEvidenceError, match="pytest_command"):
        MODULE._FullPythonPlugin(SimpleNamespace(invocation_params=SimpleNamespace(args=args)))


@pytest.mark.parametrize("fault", ["interleaved", "reversed_blocks"])
def test_serial_pair_requires_concatenation_to_match_complete_inventory_order(fault):
    from test_verify_v01 import full_python_pair, refresh_inventory

    receipts, expected, cleanups = full_python_pair()
    for receipt in receipts.values():
        a = MODULE._full_assigned_nodes(receipts["a"]["collection"])
        b = MODULE._full_assigned_nodes(receipts["b"]["collection"])
        receipt["collection"]["nodes"] = (
            [a[0], b[0], *a[1:], *b[1:]] if fault == "interleaved" else [*b, *a]
        )
        refresh_inventory(receipt)
        # Each subset's internal order and full set membership are still correct.
        MODULE.validate_full_python_receipt(receipt, expected[receipt["identity"]["shard"]])
    with pytest.raises(MODULE.FullPythonEvidenceError, match="pair_order"):
        MODULE.validate_full_python_pair(receipts, expected, cleanups)
