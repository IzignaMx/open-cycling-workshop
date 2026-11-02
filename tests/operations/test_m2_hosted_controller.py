"""Preparation-only controller contracts: no Docker or credential creation."""

import importlib
import importlib.util
import runpy
import sys
from dataclasses import asdict
from pathlib import Path

import pytest


def module():
    assert importlib.util.find_spec("scripts.ci.m2_lab_hosted") is not None, "controller missing"
    return importlib.import_module("scripts.ci.m2_lab_hosted")


def plan():
    return module().RunPlan(
        "a" * 32, "b" * 40, "c" * 40, "sha256:" + "d" * 64, "sha256:" + "e" * 64, 1001, 1001
    )


def test_connector_has_no_network_database_or_docker_mount():
    p = plan()
    args = module().create_command(p, "connector", "f" * 64)
    assert args[args.index("--network") + 1] == "none"
    assert args[args.index("--user") + 1] == "1001:1001"
    assert "--privileged" not in args and "--publish" not in args
    mounts = [args[i + 1] for i, value in enumerate(args) if value == "--mount"]
    assert len(mounts) == 3 and all("readonly" in item for item in mounts)
    assert not any(
        "private" in item or "docker.sock" in item or "pg-password" in item for item in mounts
    )
    assert args[args.index("--cap-drop") + 1] == "ALL"
    assert "no-new-privileges:true" in args


def test_api_only_shares_exact_owned_db_namespace():
    p = plan()
    args = module().create_command(p, "api", "f" * 64)
    assert args[args.index("--network") + 1] == "container:" + "f" * 64
    with pytest.raises(module().LabFailure):
        module().create_command(p, "api", "foreign-name")


@pytest.mark.parametrize(
    "field,value",
    [("nonce", "../bad"), ("uid", 0), ("image", "mutable:tag"), ("commit", "bad"), ("tree", "bad")],
)
def test_invalid_source_identity_cannot_construct_plan(field, value):
    values = dict(
        nonce="a" * 32,
        commit="b" * 40,
        tree="c" * 40,
        image="sha256:" + "d" * 64,
        pg_image="sha256:" + "e" * 64,
        uid=1001,
        gid=1001,
    )
    values[field] = value
    with pytest.raises(module().LabFailure):
        module().RunPlan(**values)


def test_cleanup_identity_requires_all_bindings_not_labels_alone():
    p = plan()
    m = module()
    row = {
        "Id": "f" * 64,
        "Image": p.image,
        "Name": "/" + p.name("connector"),
        "Config": {"Labels": p.labels("connector")},
    }
    assert m.owned_identity(p, "connector", row) == "f" * 64
    for field in ("Id", "Image", "Name"):
        changed = {**row, field: "foreign"}
        with pytest.raises(m.LabFailure):
            m.owned_identity(p, "connector", changed)


def test_evidence_limit_refuses_extra_files_and_secret_like_fields(tmp_path):
    m = module()
    folder = tmp_path / "evidence"
    folder.mkdir()
    (folder / "result.json").write_text(
        '{"schema":1,"status":"failed","reason":"blocked","checks":{}}'
    )
    (folder / "cleanup.json").write_text(
        '{"schema":1,"status":"failed","reason":"ownership","containers_absent":false,"root_removed":false}'
    )
    assert m.check_evidence(folder) <= 1024 * 1024
    (folder / "credential").write_text("synthetic-canary")
    with pytest.raises(m.LabFailure):
        m.check_evidence(folder)


def test_cleanup_unknown_ownership_cannot_remove_container():
    m, p = module(), plan()
    calls = []

    def execute(args, *, timeout=5):
        calls.append(args)
        if "ps" in args:
            return "f" * 64
        return '{"Id":"' + "f" * 64 + '","Image":"foreign"}'

    with pytest.raises(m.LabFailure):
        m.reconcile_container(p, "connector", execute)
    assert not any("rm" in call for call in calls)


def test_json_rejects_duplicate_keys_and_hardlinks(tmp_path):
    m = module()
    path = tmp_path / "value.json"
    path.write_text('{"schema":1,"schema":2}')
    with pytest.raises(m.LabFailure):
        m.read_json(path)
    path.write_text("{}")
    (tmp_path / "alias").hardlink_to(path)
    with pytest.raises(m.LabFailure):
        m.read_json(path)


def test_atomic_json_write_does_not_modify_hardlinked_file(tmp_path):
    m = module()
    path = tmp_path / "value.json"
    path.write_text("{}")
    (tmp_path / "alias").hardlink_to(path)
    with pytest.raises(m.LabFailure):
        m.write_json(path, {"schema": 1})
    assert path.read_text() == "{}"


def test_evidence_rejects_unbounded_check_names_and_false_cleanup(tmp_path):
    import json

    m = module()
    result = {
        "schema": 1,
        "status": "failed",
        "reason": "blocked",
        "checks": {"synthetic_canary": False},
    }
    cleanup = {
        "schema": 1,
        "status": "passed",
        "reason": "clean",
        "containers_absent": False,
        "root_removed": True,
    }
    (tmp_path / "result.json").write_text(json.dumps(result))
    (tmp_path / "cleanup.json").write_text(json.dumps(cleanup))
    with pytest.raises(m.LabFailure):
        m.check_evidence(tmp_path)


def test_missing_manifest_cleanup_cannot_claim_success(tmp_path):
    m = module()
    output = tmp_path / "evidence" / "cleanup.json"
    assert (
        m.main(["cleanup", "--owned", str(tmp_path / "missing.json"), "--evidence", str(output)])
        == 1
    )
    receipt = m.read_json(output)
    assert receipt["status"] == "failed"
    assert receipt["containers_absent"] is False and receipt["root_removed"] is False
    assert m.read_json(output.with_name("result.json"))["status"] == "failed"
    assert m.check_evidence(output.parent) > 0


def test_evidence_success_requires_full_identity_matching_and_all_checks(tmp_path):
    m, p = module(), plan()
    common = {"schema": 1, "commit": p.commit, "tree": p.tree, "nonce": p.nonce}
    result = {
        **common,
        "status": "passed",
        "reason": "completed",
        "checks": dict.fromkeys(m.CHECKS, True),
    }
    cleanup = {
        **common,
        "status": "passed",
        "reason": "clean",
        "containers_absent": True,
        "root_removed": True,
    }
    m.write_json(tmp_path / "result.json", result)
    m.write_json(tmp_path / "cleanup.json", cleanup)
    assert m.check_evidence(tmp_path) > 0
    cleanup["nonce"] = "f" * 32
    m.write_json(tmp_path / "cleanup.json", cleanup)
    with pytest.raises(m.LabFailure):
        m.check_evidence(tmp_path)


@pytest.mark.parametrize("known", [True, False])
def test_script_entry_preserves_closed_imported_failures(tmp_path, monkeypatch, capsys, known):
    """Execute the actual script entry with both resource-producing paths replaced."""
    m = module()
    runtime = importlib.import_module("scripts.ci.m2_lab_runtime")
    cleanup = importlib.import_module("scripts.ci.m2_lab_cleanup")
    calls = []

    def fake_runtime(p, owned, evidence):
        calls.append("runtime")
        m.write_json(
            owned,
            {
                "schema": 1,
                "plan": asdict(p),
                "root_identity": None,
                "directories": {},
                "containers": dict.fromkeys(m.ROLES),
            },
        )
        if known:
            raise m.LabFailure("source")
        raise RuntimeError("synthetic-private-error-canary")

    def fake_cleanup(p, manifest):
        calls.append("cleanup")
        if known:
            raise m.LabFailure("ownership")
        raise RuntimeError("synthetic-private-error-canary")

    monkeypatch.setattr(runtime, "run", fake_runtime)
    monkeypatch.setattr(cleanup, "cleanup", fake_cleanup)
    output = tmp_path / "evidence" / "result.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(Path(m.__file__)),
            "run",
            "--image",
            "sha256:" + "d" * 64,
            "--pg-image",
            "sha256:" + "e" * 64,
            "--commit",
            "b" * 40,
            "--tree",
            "c" * 40,
            "--owned",
            str(tmp_path / "owned.json"),
            "--evidence",
            str(output),
        ],
    )
    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(str(Path(m.__file__)), run_name="__main__")
    assert stopped.value.code == 1
    assert calls == ["runtime", "cleanup"]
    result = m.read_json(output)
    cleaned = m.read_json(output.with_name("cleanup.json"))
    assert result["reason"] == ("source" if known else "runtime")
    assert cleaned["reason"] == ("ownership" if known else "cleanup")
    assert result["status"] == cleaned["status"] == "failed"
    assert not cleaned["containers_absent"] and not cleaned["root_removed"]
    captured = capsys.readouterr()
    leaked = "synthetic-private-error-canary" in (
        captured.out
        + captured.err
        + output.read_text()
        + output.with_name("cleanup.json").read_text()
    )
    assert not leaked
    assert m.check_evidence(output.parent) > 0
