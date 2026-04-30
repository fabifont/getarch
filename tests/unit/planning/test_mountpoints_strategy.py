from pathlib import Path

import pytest

from getarch.planning.strategies.mountpoints import (
    MountpointPlan,
    MountpointsStrategy,
)


def test_emits_mkfs_mkdir_mount_per_plan() -> None:
    plans = (
        MountpointPlan(
            partition_label="data",
            mountpoint="/srv",
            filesystem="ext4",
            mount_options=("noatime",),
            create=True,
        ),
        MountpointPlan(
            partition_label="logs",
            mountpoint="/var/log",
            filesystem="xfs",
            mount_options=(),
            create=False,
        ),
    )
    cmds = MountpointsStrategy(plans=plans, mount_root=Path("/mnt")).commands()
    argvs = [c.argv for c in cmds]
    assert ("mkfs.ext4", "-F", "-L", "data", "/dev/disk/by-partlabel/data") in argvs
    assert ("mkdir", "-p", "/mnt/srv") in argvs
    assert ("mount", "-o", "noatime", "/dev/disk/by-partlabel/data", "/mnt/srv") in argvs
    # logs is create=False, no mkfs
    assert all(
        not (a[0].startswith("mkfs") and "logs" in a[3] if len(a) > 3 else False)
        for a in argvs
    )
    assert ("mkdir", "-p", "/mnt/var/log") in argvs
    assert ("mount", "/dev/disk/by-partlabel/logs", "/mnt/var/log") in argvs


def test_unsupported_filesystem_raises() -> None:
    plans = (
        MountpointPlan(
            partition_label="x",
            mountpoint="/x",
            filesystem="bogus",
            mount_options=(),
            create=True,
        ),
    )
    with pytest.raises(ValueError, match="unsupported filesystem"):
        MountpointsStrategy(plans=plans, mount_root=Path("/mnt")).commands()
