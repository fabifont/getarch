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
from .data import SystemData, UserData


class Validator:
    def __init__(self, system_data: SystemData, user_data: UserData) -> None:
        self.system_data = system_data
        self.user_data = user_data
        self.supported_filesystems = ["btrfs", "ext4"]

    def validate(self) -> UserData:
        try:
            self.validate_strings()
            self.validate_filesystem()
            self.validate_disk()
            self.validate_packages()
            return self.user_data
        except ValueError as e:
            logger.exception(e)
            raise e

    def validate_strings(self) -> None:
        str_variables = {
            "disk": self.user_data.disk,
            "filesystem": self.user_data.filesystem,
            "root_password": self.user_data.root_password,
            "luks_password": self.user_data.luks_password,
            "hostname": self.user_data.hostname,
            "lang": self.user_data.lang,
            "locale": self.user_data.locale,
            "timezone": self.user_data.timezone,
            "keymap": self.user_data.keymap,
        }

        for name, value in str_variables.items():
            if not value:
                raise ValueError(f"{name} cannot be empty")
        if self.user_data.lang not in self.system_data.langs:
            raise ValueError(f"{self.user_data.lang} is not a valid lang")
        if self.user_data.locale not in self.system_data.locales:
            raise ValueError(f"{self.user_data.locale} is not a valid locale")
        if self.user_data.lang not in self.user_data.locale:
            raise ValueError(f"{self.user_data.lang} is not in {self.user_data.locale}")
        if self.user_data.timezone not in self.system_data.timezones:
            raise ValueError(f"{self.user_data.timezone} is not a valid timezone")
        if self.user_data.keymap not in self.system_data.keymaps:
            raise ValueError(f"{self.user_data.keymap} is not a valid keymap")

    def validate_filesystem(self) -> None:
        if self.user_data.filesystem not in self.supported_filesystems:
            raise ValueError(
                f"{self.user_data.filesystem} is not a supported filesystem"
            )

    def validate_disk(self) -> None:
        if self.user_data.disk not in [disk.name for disk in self.system_data.disks]:
            raise ValueError(f"{self.user_data.disk} is not a valid or supported disk")

    def validate_packages(self) -> None:
        for package in self.user_data.packages:
            result = Command.run(f"pacman -Ss ^{package}$")
            if result.returncode != 0:
                raise ValueError(f"{package} is not a valid package")
