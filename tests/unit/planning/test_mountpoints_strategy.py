from pathlib import Path

from getarch.planning.strategies.mountpoints import (
    MountpointPlan,
    MountpointsStrategy,
)


def test_emits_mkdir_and_mount_per_plan() -> None:
    plans = (
        MountpointPlan(
            partition_label="data",
            mountpoint="/srv",
            mount_options=("noatime",),
        ),
        MountpointPlan(
            partition_label="logs",
            mountpoint="/var/log",
            mount_options=(),
        ),
    )
    cmds = MountpointsStrategy(plans=plans, mount_root=Path("/mnt")).commands()
    argvs = [c.argv for c in cmds]
    # No mkfs commands: the strategy must not format pre-existing partitions.
    assert all(not a[0].startswith("mkfs") for a in argvs)
    assert ("mkdir", "-p", "/mnt/srv") in argvs
    assert ("mount", "-o", "noatime", "/dev/disk/by-partlabel/data", "/mnt/srv") in argvs
    assert ("mkdir", "-p", "/mnt/var/log") in argvs
    assert ("mount", "/dev/disk/by-partlabel/logs", "/mnt/var/log") in argvs
