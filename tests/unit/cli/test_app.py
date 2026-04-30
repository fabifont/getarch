from typer.testing import CliRunner

from getarch import __version__
from getarch.cli.app import app


def test_version_command_prints_package_version() -> None:
    result = CliRunner().invoke(app, ["--no-color", "version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_main_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in (
        "validate",
        "plan",
        "install",
        "schema",
        "examples",
        "discover",
        "version",
    ):
        assert cmd in result.output
