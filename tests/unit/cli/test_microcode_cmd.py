import json
from pathlib import Path

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from getarch.cli.app import app
from getarch.config.examples import EXAMPLES


def _write(tmp: Path) -> Path:
    p = tmp / "c.json"
    p.write_text(json.dumps(EXAMPLES["minimal-ext4"]))
    return p


def test_microcode_resolves_intel(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "getarch.cli.commands.microcode.IsoEnvironment.cpu_vendor",
        return_value="GenuineIntel",
    )
    p = _write(tmp_path)
    result = CliRunner().invoke(app, ["--no-color", "microcode", str(p)])
    assert result.exit_code == 0
    assert "intel" in result.output.lower()
    assert "intel-ucode" in result.output


def test_microcode_resolves_none_for_unknown_vendor(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "getarch.cli.commands.microcode.IsoEnvironment.cpu_vendor",
        return_value="HygonGenuine",
    )
    p = _write(tmp_path)
    result = CliRunner().invoke(app, ["--no-color", "microcode", str(p)])
    assert result.exit_code == 0
    assert "resolved=none" in result.output
    assert "(none)" in result.output
