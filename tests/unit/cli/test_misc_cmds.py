import json
from typing import Any

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from getarch.cli.app import app


def test_schema_command_emits_json_schema() -> None:
    result = CliRunner().invoke(app, ["schema"])
    assert result.exit_code == 0
    obj = json.loads(result.output)
    assert obj["title"] == "Config"
    assert "properties" in obj


def test_examples_lists_names() -> None:
    result = CliRunner().invoke(app, ["examples"])
    assert result.exit_code == 0
    assert "minimal-ext4" in result.output
    assert "encrypted-btrfs" in result.output


def test_examples_print_named() -> None:
    result = CliRunner().invoke(app, ["examples", "minimal-ext4"])
    assert result.exit_code == 0
    obj = json.loads(result.output)
    assert obj["version"] == 1


def test_discover_command(mocker: MockerFixture) -> None:
    info: dict[str, Any] = {
        "disks": [{"path": "/dev/sda", "size_bytes": 100, "model": "x"}],
        "uefi": True,
        "cpu_vendor": "GenuineIntel",
        "locales_count": 0,
        "keymaps_count": 0,
        "timezones_count": 0,
    }
    mocker.patch("getarch.cli.commands.discover._discover", return_value=info)
    result = CliRunner().invoke(app, ["--json", "discover"])
    assert result.exit_code == 0
    obj = json.loads(result.output)
    assert obj["uefi"] is True
