# This file is part of getarch
#
# getarch is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# getarch is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with getarch.  If not, see <https://www.gnu.org/licenses/>.

import logging as logger

from .command import Command


class Disk:
    def __init__(self, name: str, size: int) -> None:
        self.__name = name
        self.__size = size

    def __str__(self) -> str:
        return f"{self.__name} {self.__size / (1 << 30):,.1f} GB"

    @property
    def name(self) -> str:
        return self.__name


class SystemData:
    def __init__(self) -> None:
        self.is_laptop = (
            "laptop" in Command.run("hostnamectl status | grep Chassis").stdout.lower()
        )
        self.disks = self.parse_disks()
        self.locales = Command.run("cat /usr/share/i18n/SUPPORTED").stdout.split("\n")
        self.langs = [locale.split(" ")[0] for locale in self.locales]
        self.keymaps = Command.run(
            r"find /usr/share/kbd/keymaps/ -type f -iname '*.map.gz' -exec basename -s .map.gz {} \; | sort"  # noqa: B950
        ).stdout.split("\n")
        self.timezones = Command.run("timedatectl list-timezones").stdout.split("\n")
        self.ucode = self.get_ucode()

    def parse_disks(self) -> list[Disk]:
        disks_list = Command.run("lsblk -b | grep disk | awk '{print $1, $4}'").stdout
        disks: list[Disk] = []
        for line in disks_list.split("\n"):
            name, size = line.split(" ")
            if any(check in name for check in ["rom", "loop", "airoot"]):
                continue
            disks.append(Disk(f"/dev/{name}", int(size)))
        return disks

    def get_ucode(self) -> str | None:
        cpu_vendor_id = Command.run(
            "cat /proc/cpuinfo | grep -m1 vendor_id | awk '{print $3}'"
        ).stdout
        if cpu_vendor_id == "GenuineIntel":
            return "intel-ucode"
        elif cpu_vendor_id == "AuthenticAMD":
            return "amd-ucode"
        return None


class UserData:
    disk: str
    clean_disk: bool
    filesystem: str
    root_password: str
    luks_password: str
    hostname: str
    lang: str
    locale: str
    timezone: str
    keymap: str
    packages: list[str]
    mkinitcpio_hooks: list[str]
    services: list[str]
    timers: list[str]

    def __init__(self, data: dict[str, list[str] | str | bool]):
        self.data = data
        self.disk = self.validate("disk", str)  # type: ignore
        self.clean_disk = self.validate("clean_disk", bool)  # type: ignore
        self.filesystem = self.validate("filesystem", str)  # type: ignore
        self.root_password = self.validate("root_password", str)  # type: ignore
        self.luks_password = self.validate("luks_password", str)  # type: ignore
        self.hostname = self.validate("hostname", str)  # type: ignore
        self.lang = self.validate("lang", str)  # type: ignore
        self.locale = self.validate("locale", str)  # type: ignore
        self.timezone = self.validate("timezone", str)  # type: ignore
        self.keymap = self.validate("keymap", str)  # type: ignore
        self.packages = self.validate("packages", list[str])  # type: ignore
        self.mkinitcpio_hooks = self.validate("mkinitcpio_hooks", list[str])  # type: ignore
        self.services = self.validate("services", list[str])  # type: ignore
        self.timers = self.validate("timers", list[str])  # type: ignore

    def validate(
        self, key: str, expected_type: type[list[str] | str | bool]
    ) -> list[str] | str | bool:
        try:
            parsed_type = type(self.data[key])
            if parsed_type == list and expected_type == list[str]:
                if not all(type(item) == str for item in self.data[key]):  # type: ignore
                    raise TypeError(
                        f"Expected {key} to be of type {expected_type}, but got {parsed_type}"
                    )
            elif parsed_type != expected_type:
                raise TypeError(
                    f"Expected {key} to be of type {expected_type}, but got {parsed_type}"
                )
            return self.data[key]
        except KeyError as e:
            logger.exception(e)
            raise e
        except TypeError as e:
            logger.exception(e)
            raise e
