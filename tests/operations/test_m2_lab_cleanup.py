"""Fake Docker plus owned public-text temporary files; never real Docker/secrets."""

import importlib
import json
import os
import stat
from dataclasses import asdict

import pytest

from scripts.ci import m2_lab_hosted as host


def subject():
    return importlib.import_module("scripts.ci.m2_lab_cleanup")


@pytest.fixture
def owned(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "ROOT", tmp_path)
    plan = host.RunPlan(
        "a" * 32, "b" * 40, "c" * 40, "sha256:" + "d" * 64, "sha256:" + "e" * 64, 1001, 1001
    )
    plan.root.mkdir(mode=0o700)
    info = plan.root.stat()
    manifest = {
        "schema": 1,
        "plan": asdict(plan),
        "root_identity": {
            "dev": info.st_dev,
            "ino": info.st_ino,
            "uid": info.st_uid,
            "mode": stat.S_IMODE(info.st_mode),
        },
        "directories": {},
        "containers": dict.fromkeys(host.ROLES),
    }
    return plan, manifest


class Docker:
    def __init__(self, plan, roles=()):
        self.rows = {}
        self.calls = []
        for index, role in enumerate(roles, 1):
            cid = str(index) * 64
            self.rows[cid] = {
                "Id": cid,
                "Image": plan.image_for(role),
                "Name": "/" + plan.name(role),
                "Config": {"Labels": plan.labels(role)},
            }

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        assert kwargs["timeout"] <= 10
        if args[1] == "ps":
            filter_value = args[args.index("--filter") + 1]
            if filter_value.startswith("id="):
                return "\n".join(cid for cid in self.rows if cid == filter_value[3:])
            name = filter_value.removeprefix("name=^/").removesuffix("$")
            return "\n".join(cid for cid, row in self.rows.items() if row["Name"] == "/" + name)
        if args[1] == "inspect":
            return json.dumps(self.rows[args[-1]])
        if args[1:3] == ["rm", "--force"]:
            self.rows.pop(args[-1])
            return ""
        raise AssertionError("unapproved fake command")


def test_exact_owned_containers_and_root_removed(owned):
    plan, manifest = owned
    docker = Docker(plan, ("db", "api", "connector"))
    manifest["containers"] = dict(zip(host.ROLES, docker.rows, strict=True))
    result = subject().cleanup(plan, manifest, execute=docker)
    assert result == {"containers_absent": True, "root_removed": True}
    assert not plan.root.exists() and not docker.rows


def test_uncertain_create_reconciles_exact_name_and_identity(owned):
    plan, manifest = owned
    docker = Docker(plan, ("api",))
    assert subject().cleanup(plan, manifest, execute=docker)["containers_absent"]
    assert not docker.rows


def test_identity_mismatch_never_removed(owned):
    plan, manifest = owned
    docker = Docker(plan, ("api",))
    next(iter(docker.rows.values()))["Config"]["Labels"]["ocwp.m2.run"] = "f" * 32
    with pytest.raises(host.LabFailure):
        subject().cleanup(plan, manifest, execute=docker)
    assert not any(call[1] == "rm" for call in docker.calls)
    assert plan.root.exists()


def test_recorded_cid_cannot_be_replaced_by_same_name(owned):
    plan, manifest = owned
    manifest["containers"]["api"] = "f" * 64
    with pytest.raises(host.LabFailure):
        subject().cleanup(plan, manifest, execute=Docker(plan, ("api",)))
    assert plan.root.exists()


@pytest.mark.parametrize("intrusion", ["unknown", "symlink", "hardlink", "directory"])
def test_unknown_or_alias_files_are_not_deleted(owned, tmp_path, intrusion):
    plan, manifest = owned
    outside = tmp_path / "outside-public"
    outside.write_text("public fixture")
    directory = plan.root / "credential"
    directory.mkdir(mode=0o700)
    info = directory.stat()
    manifest["directories"]["credential"] = {
        "dev": info.st_dev,
        "ino": info.st_ino,
        "uid": info.st_uid,
        "mode": stat.S_IMODE(info.st_mode),
    }
    target = directory / "credential"
    if intrusion == "unknown":
        (directory / "unexpected").write_text("public fixture")
    elif intrusion == "symlink":
        target.symlink_to(outside)
    elif intrusion == "hardlink":
        os.link(outside, target)
    else:
        target.mkdir()
    with pytest.raises(host.LabFailure):
        subject().cleanup(plan, manifest, execute=Docker(plan))
    assert plan.root.exists() and outside.read_text() == "public fixture"


def test_root_identity_mismatch_or_missing_receipt_preserves_root(owned):
    plan, manifest = owned
    manifest["root_identity"] = None
    with pytest.raises(host.LabFailure):
        subject().cleanup(plan, manifest, execute=Docker(plan))
    assert plan.root.exists()


def test_absent_uncreated_root_is_verified_without_deleting(owned):
    plan, manifest = owned
    plan.root.rmdir()
    manifest["root_identity"] = None
    assert subject().cleanup(plan, manifest, execute=Docker(plan))["root_removed"]


def test_known_public_fixture_inventory_removed_without_recursion(owned):
    plan, manifest = owned
    directory = plan.root / "credential"
    directory.mkdir(mode=0o700)
    info = directory.stat()
    manifest["directories"]["credential"] = {
        "dev": info.st_dev,
        "ino": info.st_ino,
        "uid": info.st_uid,
        "mode": stat.S_IMODE(info.st_mode),
    }
    path = directory / "scope.json"
    path.write_text("public fixture, not a credential")
    path.chmod(0o400)
    assert subject().cleanup(plan, manifest, execute=Docker(plan))["root_removed"]
    assert not plan.root.exists()


def test_changed_directory_inode_is_not_removed(owned):
    plan, manifest = owned
    directory = plan.root / "credential"
    directory.mkdir(mode=0o700)
    info = directory.stat()
    manifest["directories"]["credential"] = {
        "dev": info.st_dev,
        "ino": info.st_ino + 1,
        "uid": info.st_uid,
        "mode": stat.S_IMODE(info.st_mode),
    }
    with pytest.raises(host.LabFailure):
        subject().cleanup(plan, manifest, execute=Docker(plan))
    assert directory.exists()


def test_changed_root_inode_is_not_removed(owned):
    plan, manifest = owned
    manifest["root_identity"]["ino"] += 1
    with pytest.raises(host.LabFailure):
        subject().cleanup(plan, manifest, execute=Docker(plan))
    assert plan.root.exists()


def test_failed_remove_never_reports_absence_or_deletes_root(owned):
    plan, manifest = owned
    docker = Docker(plan, ("api",))

    def failing(args, **kwargs):
        if args[1] == "rm":
            raise RuntimeError("public-cleanup-canary")
        return docker(args, **kwargs)

    with pytest.raises(host.LabFailure) as error:
        subject().cleanup(plan, manifest, execute=failing)
    assert str(error.value) == "cleanup"
    assert plan.root.exists()


def test_rm_success_without_actual_absence_is_failure(owned):
    plan, manifest = owned
    docker = Docker(plan, ("api",))

    def lying(args, **kwargs):
        return "" if args[1] == "rm" else docker(args, **kwargs)

    with pytest.raises(host.LabFailure):
        subject().cleanup(plan, manifest, execute=lying)
    assert plan.root.exists()


def test_recorded_cid_renamed_to_unknown_name_is_not_removed(owned):
    plan, manifest = owned
    docker = Docker(plan, ("api",))
    cid, row = next(iter(docker.rows.items()))
    manifest["containers"]["api"] = cid
    row["Name"] = "/unrelated"
    with pytest.raises(host.LabFailure):
        subject().cleanup(plan, manifest, execute=docker)
    assert not any(call[1] == "rm" for call in docker.calls)


def test_root_symlink_never_follows_outside_directory(owned, tmp_path):
    plan, manifest = owned
    outside = tmp_path / "outside-directory"
    outside.mkdir()
    (outside / "keep").write_text("public fixture")
    plan.root.rmdir()
    plan.root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(host.LabFailure):
        subject().cleanup(plan, manifest, execute=Docker(plan))
    assert (outside / "keep").read_text() == "public fixture"
    assert plan.root.is_symlink()


def test_unrecorded_directory_is_not_adopted(owned):
    plan, manifest = owned
    (plan.root / "credential").mkdir(mode=0o700)
    with pytest.raises(host.LabFailure):
        subject().cleanup(plan, manifest, execute=Docker(plan))
    assert (plan.root / "credential").exists()


@pytest.mark.parametrize(
    "relative", ["pg-password", "api-private/pg-password", "api-private/run.json"]
)
def test_owned_partial_new_file_mode_is_disposable(owned, relative):
    plan, manifest = owned
    if "/" in relative:
        directory = plan.root / "api-private"
        directory.mkdir(mode=0o700)
        info = directory.stat()
        manifest["directories"]["api-private"] = {
            "dev": info.st_dev,
            "ino": info.st_ino,
            "uid": info.st_uid,
            "mode": stat.S_IMODE(info.st_mode),
        }
    path = plan.root / relative
    path.write_text("PUBLIC PARTIAL FILE FIXTURE, NOT A CREDENTIAL")
    path.chmod(0o600)
    assert subject().cleanup(plan, manifest, execute=Docker(plan))["root_removed"]


def test_actual_orchestrator_manifest_then_cleanup_with_fake_commands_only(tmp_path, monkeypatch):
    """Integration control flow only: no _private_inputs, sockets, OpenSSL or secrets."""
    runtime = importlib.import_module("scripts.ci.m2_lab_runtime")
    fixtures = importlib.import_module("tests.operations.test_m2_lab_runtime")
    monkeypatch.setattr(host, "ROOT", tmp_path)
    plan = host.RunPlan(
        "a" * 32,
        "b" * 40,
        "c" * 40,
        "sha256:" + "d" * 64,
        "sha256:" + "e" * 64,
        os.getuid(),
        os.getgid(),
    )
    manifest_path = tmp_path / "owned.json"
    executor = fixtures.FakeExecutor(plan, manifest_path, runtime)
    final_modes = {
        "pg-password": 0o444,
        "api-private/pg-password": 0o400,
        "api-private/run.json": 0o400,
        "ca/ca.key": 0o600,
        "ca/ca.crt": 0o644,
        "ca/api.csr": 0o644,
        "ca/san.cnf": 0o600,
        "tls/api.key": 0o400,
        "tls/api.crt": 0o400,
        "public/ca.crt": 0o444,
        "credential/credential": 0o400,
        "credential/scope.json": 0o400,
    }
    private_calls = []

    def public_material_only(actual_plan, _command):
        saved = json.loads(manifest_path.read_text())
        assert set(saved["directories"]) == set(runtime.DIRECTORIES)
        private_calls.append(1)
        for relative, mode in final_modes.items():
            path = actual_plan.root / relative
            path.write_text("PUBLIC NON-KEY NON-CREDENTIAL FIXTURE")
            path.chmod(mode)

    monkeypatch.setattr(runtime, "_private_inputs", public_material_only)
    runtime.run(plan, manifest_path, tmp_path / "evidence.json", execute=executor)
    assert private_calls == [1]
    assert not any(call[0] == "openssl" for call in executor.calls)
    docker = Docker(plan)
    docker.rows = executor.rows
    result = subject().cleanup(plan, json.loads(manifest_path.read_text()), execute=docker)
    assert result == {"containers_absent": True, "root_removed": True}
    assert not plan.root.exists() and not docker.rows


def test_cleanup_deadline_caps_each_command_without_sleep(owned, monkeypatch):
    module = subject()
    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    plan, manifest = owned
    docker = Docker(plan)
    timeouts = []

    def execute(args, *, timeout):
        timeouts.append(timeout)
        result = docker(args, timeout=timeout)
        clock[0] = 89.0
        return result

    assert module.cleanup(plan, manifest, execute=execute)["root_removed"]
    assert timeouts[0] == 5
    assert all(timeout == 1 for timeout in timeouts[1:])


def test_cleanup_expiry_stops_without_retry_or_root_removal(owned, monkeypatch):
    module = subject()
    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    plan, manifest = owned
    calls = []

    def execute(args, *, timeout):
        calls.append(args)
        clock[0] = 90.0
        return ""

    with pytest.raises(host.LabFailure) as error:
        module.cleanup(plan, manifest, execute=execute)
    assert error.value.reason == "deadline"
    assert len(calls) == 1 and plan.root.exists()


@pytest.mark.parametrize("stage", ["before_root", "after_root"])
def test_cleanup_deadline_checked_around_filesystem_phase(owned, monkeypatch, stage):
    module = subject()
    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    plan, manifest = owned
    if stage == "before_root":
        monkeypatch.setattr(module, "_remove_containers", lambda *args: clock.__setitem__(0, 90.0))
    else:
        remove_root = module._remove_root

        def expire_after_root(*args):
            remove_root(*args)
            clock[0] = 90.0

        monkeypatch.setattr(module, "_remove_root", expire_after_root)
    with pytest.raises(host.LabFailure) as error:
        module.cleanup(plan, manifest, execute=Docker(plan))
    assert error.value.reason == "deadline"
    assert plan.root.exists() is (stage == "before_root")
