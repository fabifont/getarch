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

import subprocess  # nosec


class Command:
    @staticmethod
    def run(
        command: str,
        check: bool = True,
        cmd_input: str | None = None,
        chroot: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        print(f"Running: {command}")
        if chroot:
            command = f"arch-chroot /mnt {command}"
        result = subprocess.run(
            command,
            shell=True,  # nosec
            capture_output=True,
            check=check,
            text=True,
            input=cmd_input,
        )
        result.stdout = result.stdout.strip()
        return result
