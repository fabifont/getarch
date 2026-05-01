"""LVM-on-LUKS volume group + logical volume creation.

The strategy assumes the root LUKS mapper is already open at
``/dev/mapper/<encryption.mapper_name>`` (the planner inserts this step
right after the ``encryption`` step). One PV is created on the mapper,
one VG named after :attr:`LvmConfig.vg_name`, then one LV per
:class:`LvmVolume`. The unsized LV (if any) consumes ``-l 100%FREE``.
"""

from __future__ import annotations

from dataclasses import dataclass

from getarch.execution.command import Command


@dataclass(frozen=True, slots=True)
class LvmVolumePlan:
    name: str
    size_mib: int | None
    mountpoint: str
    filesystem: str


@dataclass(frozen=True, slots=True)
class LvmStrategy:
    pv_device: str
    vg_name: str
    volumes: tuple[LvmVolumePlan, ...]

    def commands(self) -> tuple[Command, ...]:
        cmds: list[Command] = [
            Command(
                argv=("pvcreate", "-ff", "--yes", self.pv_device),
                description=f"create LVM PV on {self.pv_device}",
            ),
            Command(
                argv=("vgcreate", "-ff", "--yes", self.vg_name, self.pv_device),
                description=f"create VG {self.vg_name} on {self.pv_device}",
            ),
        ]
        for vol in self.volumes:
            if vol.size_mib is None:
                argv = (
                    "lvcreate",
                    "-y",
                    "-l",
                    "100%FREE",
                    "-n",
                    vol.name,
                    self.vg_name,
                )
                desc = f"create LV {vol.name} (rest of {self.vg_name})"
            else:
                argv = (
                    "lvcreate",
                    "-y",
                    "-L",
                    f"{vol.size_mib}M",
                    "-n",
                    vol.name,
                    self.vg_name,
                )
                desc = f"create LV {vol.name} ({vol.size_mib} MiB)"
            cmds.append(Command(argv=argv, description=desc))
        return tuple(cmds)


def lv_device_path(vg_name: str, lv_name: str) -> str:
    """Return the canonical LV device path used at install time."""
    return f"/dev/{vg_name}/{lv_name}"
