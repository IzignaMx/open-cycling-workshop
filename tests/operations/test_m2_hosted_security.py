"""Independent adversarial inspection tests; no runtime commands or credentials."""

from copy import deepcopy

import pytest

from scripts.ci import m2_lab_hosted as controller


def inspected_connector():
    plan = controller.RunPlan(
        "a" * 32,
        "b" * 40,
        "c" * 40,
        "sha256:" + "d" * 64,
        "sha256:" + "e" * 64,
        1001,
        1001,
    )
    row = {
        "Id": "f" * 64,
        "Name": "/" + plan.name("connector"),
        "Image": plan.image,
        "Config": {"Labels": plan.labels("connector"), "User": "1001:1001"},
        "HostConfig": {
            "NetworkMode": "none",
            "ReadonlyRootfs": True,
            "Privileged": False,
            "CapAdd": [],
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"],
            "LogConfig": {"Type": "none"},
            "Memory": 128 * 1024**2,
            "MemorySwap": 128 * 1024**2,
            "NanoCpus": 500_000_000,
            "PidsLimit": 32,
            "PortBindings": {},
            "Devices": [],
            "PidMode": "",
            "IpcMode": "private",
            "CgroupnsMode": "private",
            "Tmpfs": {
                "/tmp": "rw,noexec,nosuid,nodev,size=64m,mode=1777",
                "/run/m2-store": "rw,noexec,nosuid,nodev,size=16m,mode=0700,uid=1001,gid=1001",
            },
        },
        "Mounts": [
            {"Type": "bind", "Source": source, "Destination": target, "RW": not readonly}
            for source, target, readonly in controller.mount_specs(plan, "connector")
        ],
    }
    return plan, row


def test_expected_connector_inspection_is_accepted():
    plan, row = inspected_connector()
    controller.verify_containment(plan, "connector", row)


@pytest.mark.parametrize(
    "mutation",
    ["host_cgroup", "unconfined_seccomp", "unbounded_store", "extra_tmpfs", "duplicate_bind"],
)
def test_inspection_refuses_weakened_or_extra_containment(mutation):
    plan, original = inspected_connector()
    row = deepcopy(original)
    if mutation == "host_cgroup":
        row["HostConfig"]["CgroupnsMode"] = "host"
    elif mutation == "unconfined_seccomp":
        row["HostConfig"]["SecurityOpt"].append("seccomp:unconfined")
    elif mutation == "unbounded_store":
        row["HostConfig"]["Tmpfs"]["/run/m2-store"] = "rw,mode=0700"
    elif mutation == "extra_tmpfs":
        row["HostConfig"]["Tmpfs"]["/extra"] = "rw,size=1g"
        row["Mounts"].append({"Type": "tmpfs", "Destination": "/extra", "RW": True})
    else:
        row["Mounts"].append(deepcopy(row["Mounts"][0]))
    with pytest.raises(controller.LabFailure):
        controller.verify_containment(plan, "connector", row)
