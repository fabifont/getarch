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

import json
import logging as logger
import pathlib

from .data import UserData


class Parser:
    def __init__(self, filepath: str):
        self.filepath = pathlib.Path(filepath)

    def parse(self) -> UserData:
        try:
            with open(pathlib.Path(self.filepath), "r") as file:
                data = json.load(file)
            return UserData(data)
        except FileNotFoundError as e:
            logger.exception(e)
            raise e
        except json.JSONDecodeError as e:
            logger.exception(e)
            raise e
