import json
from pathlib import Path

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from getarch.cli.app import app
from getarch.config.examples import EXAMPLES
from getarch.errors import EnvironmentError as EnvErr
from getarch.system.preflight import EnvironmentReport


def _write(tmp: Path) -> Path:
    p = tmp / "c.json"
    p.write_text(json.dumps(EXAMPLES["minimal-ext4"]))
    return p


def _ok_report() -> EnvironmentReport:
    return EnvironmentReport(
        disks_found={"/dev/sda": 1},
        cpu_vendor="GenuineIntel",
        is_uefi=True,
        is_root=True,
        is_arch_iso=True,
        internet_reachable=True,
        keyring_initialized=True,
        mountpoints_seen=(),
    )


def test_verify_prints_ok_when_preflight_passes(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    mocker.patch(
        "getarch.cli.commands.verify.preflight_environment",
        return_value=_ok_report(),
    )
    p = _write(tmp_path)
    result = CliRunner().invoke(app, ["--no-color", "verify", str(p)])
    assert result.exit_code == 0
    assert "preflight ok" in result.output.lower()
    assert "GenuineIntel" in result.output


def test_verify_propagates_preflight_failure(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    mocker.patch(
        "getarch.cli.commands.verify.preflight_environment",
        side_effect=EnvErr("no internet"),
    )
    p = _write(tmp_path)
    result = CliRunner().invoke(app, ["--no-color", "verify", str(p)])
    assert result.exit_code == 2
    assert "no internet" in result.output.lower()
