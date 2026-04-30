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


def test_plan_text_mode(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "getarch.cli.commands.plan._discover_disks",
        return_value=(Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),),
    )
    p = _write(tmp_path)
    result = CliRunner().invoke(app, ["--no-color", "plan", str(p)])
    assert result.exit_code == 0
    assert "Partition disk" in result.output


def test_plan_json_mode(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "getarch.cli.commands.plan._discover_disks",
        return_value=(Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),),
    )
    p = _write(tmp_path)
    result = CliRunner().invoke(app, ["--json", "plan", str(p)])
    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["version"] == "1"
    assert any(s["id"] == "partitioning" for s in payload["steps"])
