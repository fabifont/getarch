from getarch.execution.fake_runner import FakeResponse, FakeRunner
from getarch.system.block_devices import LsblkBlockDevices

_LSBLK_JSON = """
{
   "blockdevices": [
      {"name":"sda", "size":"8589934592", "type":"disk", "model":"VBOX HARDDISK"},
      {"name":"sr0", "size":"1073741824", "type":"rom"},
      {"name":"loop0", "size":"0", "type":"loop"},
      {"name":"nvme0n1", "size":"512110190592", "type":"disk", "model":"Samsung SSD"}
   ]
}
"""


def test_list_disks_filters_rom_and_loop() -> None:
    runner = FakeRunner(
        responses={
            ("lsblk", "-J", "-b", "-o", "NAME,SIZE,TYPE,MODEL"): FakeResponse(
                stdout=_LSBLK_JSON,
            ),
        },
    )
    disks = LsblkBlockDevices(runner=runner).list_disks()
    paths = [d.path.as_posix() for d in disks]
    assert paths == ["/dev/sda", "/dev/nvme0n1"]
    assert disks[0].size_bytes == 8589934592
    assert disks[0].model == "VBOX HARDDISK"


def test_list_disks_handles_missing_model() -> None:
    runner = FakeRunner(
        responses={
            ("lsblk", "-J", "-b", "-o", "NAME,SIZE,TYPE,MODEL"): FakeResponse(
                stdout='{"blockdevices":[{"name":"sda","size":"100","type":"disk"}]}',
            ),
        },
    )
    disks = LsblkBlockDevices(runner=runner).list_disks()
    assert disks[0].model is None


_LSBLK_BUSY_JSON = """
{
   "blockdevices": [
      {"name":"sda","mountpoints":[null],
       "children":[
          {"name":"sda1","mountpoints":["/boot"]},
          {"name":"sda2","mountpoints":["/"]}
       ]
      }
   ]
}
"""

_LSBLK_CLEAN_JSON = """
{
   "blockdevices": [
      {"name":"sdb","mountpoints":[null],
       "children":[{"name":"sdb1","mountpoints":[null]}]
      }
   ]
}
"""


def test_target_disk_busy_returns_mountpoints() -> None:
    runner = FakeRunner(
        responses={
            ("lsblk", "-J", "-o", "NAME,MOUNTPOINTS", "/dev/sda"): FakeResponse(
                stdout=_LSBLK_BUSY_JSON,
            ),
        },
    )
    mounts = LsblkBlockDevices(runner=runner).target_disk_busy("/dev/sda")
    assert mounts == ("/boot", "/")


def test_target_disk_busy_clean() -> None:
    runner = FakeRunner(
        responses={
            ("lsblk", "-J", "-o", "NAME,MOUNTPOINTS", "/dev/sdb"): FakeResponse(
                stdout=_LSBLK_CLEAN_JSON,
            ),
        },
    )
    assert LsblkBlockDevices(runner=runner).target_disk_busy("/dev/sdb") == ()
