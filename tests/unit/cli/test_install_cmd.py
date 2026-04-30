import json
from pathlib import Path

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from getarch.cli.app import app
from getarch.config.examples import EXAMPLES
from getarch.domain.disk import Disk, DiskPath


def _write(tmp: Path) -> Path:
    p = tmp / "c.json"
    p.write_text(json.dumps(EXAMPLES["minimal-ext4"]))
    return p


def test_install_dry_run_records_no_subprocess(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "getarch.cli.commands.install._discover_disks",
        return_value=(Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),),
    )
    p = _write(tmp_path)
    result = CliRunner().invoke(app, ["--no-color", "install", str(p), "--dry-run", "--yes"])
    assert result.exit_code == 0
    assert "dry-run" in result.output.lower()


def test_install_without_yes_or_force_refuses(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "getarch.cli.commands.install._discover_disks",
        return_value=(Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),),
    )
    p = _write(tmp_path)
    result = CliRunner().invoke(app, ["--no-color", "install", str(p)], input="n\n")
    assert result.exit_code == 2
    output = result.output.lower()
    assert "declined" in output or "cancel" in output
