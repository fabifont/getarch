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

import argparse
import logging as logger
import sys

import getarch


def main():
    arg_parser = argparse.ArgumentParser(
        description="a simple tool to install archlinux", prog="getarch"
    )
    arg_parser.add_argument(
        "-v", "--version", action="version", version=f"getarch {getarch.__version__}"
    )
    arg_parser.add_argument(
        "-c", "--config", type=str, help="path to the configuration file"
    )
    arg_parser.add_argument(
        "-pv",
        "--possible-values",
        type=str,
        help="possible values for the configuration file are: disks, locales, langs, keymaps, timezones",  # noqa: B950
    )
    arg_parser.add_argument(
        "-t",
        "--test",
        action="store_true",
        help="exit before rebooting to perform tests",
    )

    if len(sys.argv) == 1:
        arg_parser.print_help(sys.stderr)
        sys.exit(1)

    args = arg_parser.parse_args()
    installer = getarch.Installer(test=args.test)

    if args.possible_values:
        if args.possible_values in vars(installer.system_data):
            if args.possible_values == "disks":
                print(
                    "\n".join(
                        [
                            str(disk)
                            for disk in getattr(
                                installer.system_data, args.possible_values
                            )
                        ]
                    )
                )
            else:
                print("\n".join(getattr(installer.system_data, args.possible_values)))
        else:
            print(f"invalid value: {args.possible_values}", file=sys.stderr)
            sys.exit(1)
    else:
        parser = getarch.Parser(args.config)
        installer.init()
        validator = getarch.Validator(installer.system_data, parser.parse())
        installer.install(validator.validate())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: B902
        logger.exception(e)
        sys.exit(1)
