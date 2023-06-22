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

import logging

from .installer import Installer
from .parser import Parser
from .validator import Validator

__version__ = "1.0.1"
__all__ = ["Installer", "Parser", "Validator"]

logging.basicConfig(level=logging.DEBUG)
