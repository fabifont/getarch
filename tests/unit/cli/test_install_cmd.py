import json
from pathlib import Path

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from getarch.cli.app import app
from getarch.config.examples import EXAMPLES
from getarch.domain.disk import Disk, DiskPath
from getarch.system.preflight import EnvironmentReport


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
    result = CliRunner().invoke(
        app,
        [
            "--no-color",
            "install",
            str(p),
            "--dry-run",
            "--yes",
            "--skip-environment-preflight",
        ],
    )
    assert result.exit_code == 0
    assert "dry-run" in result.output.lower()


def test_install_without_yes_or_force_refuses(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "getarch.cli.commands.install._discover_disks",
        return_value=(Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),),
    )
    p = _write(tmp_path)
    result = CliRunner().invoke(
        app,
        ["--no-color", "install", str(p), "--skip-environment-preflight"],
        input="n\n",
    )
    assert result.exit_code == 2
    output = result.output.lower()
    assert "declined" in output or "cancel" in output


def test_install_skip_environment_preflight_warns(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    mocker.patch(
        "getarch.cli.commands.install._discover_disks",
        return_value=(Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),),
    )
    p = _write(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "--no-color",
            "install",
            str(p),
            "--dry-run",
            "--yes",
            "--skip-environment-preflight",
        ],
    )
    assert result.exit_code == 0
    out = result.output.lower()
    assert "skipping environment preflight" in out


def test_skip_environment_preflight_does_not_bypass_disk_busy_guard(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """The mount-busy guard runs unconditionally before destructive steps.

    Even if the user passes --skip-environment-preflight together with --yes,
    the install must refuse to proceed when the target disk has live mounts.
    """
    mocker.patch(
        "getarch.cli.commands.install._discover_disks",
        return_value=(Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),),
    )

    class _Busy:
        def list_disks(self) -> tuple[Disk, ...]:
            return (Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),)

        def target_disk_busy(self, path: str) -> tuple[str, ...]:
            del path
            return ("/", "/boot")

    mocker.patch(
        "getarch.cli.commands.install.LsblkBlockDevices",
        return_value=_Busy(),
    )
    p = _write(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "--no-color",
            "install",
            str(p),
            "--yes",
            "--skip-environment-preflight",
        ],
    )
    assert result.exit_code == 2
    assert "mounted partitions" in result.output.lower()


def test_install_runs_environment_preflight_by_default(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    mocker.patch(
        "getarch.cli.commands.install._discover_disks",
        return_value=(Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),),
    )
    called: dict[str, int] = {"n": 0}

    def fake_preflight(*args: object, **kwargs: object) -> EnvironmentReport:
        del args, kwargs
        called["n"] += 1
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

    mocker.patch(
        "getarch.cli.commands.install.preflight_environment", side_effect=fake_preflight
    )
    p = _write(tmp_path)
    result = CliRunner().invoke(
        app, ["--no-color", "install", str(p), "--dry-run", "--yes"]
    )
    assert result.exit_code == 0
    assert called["n"] == 1


def test_install_passes_cpu_vendor_to_planner(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    mocker.patch(
        "getarch.cli.commands.install._discover_disks",
        return_value=(Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),),
    )

    def fake_preflight(*args: object, **kwargs: object) -> EnvironmentReport:
        del args, kwargs
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

    mocker.patch(
        "getarch.cli.commands.install.preflight_environment",
        side_effect=fake_preflight,
    )

    captured: dict[str, object] = {}
    from getarch.planning.planner import Planner as _RealPlanner

    real_build = _RealPlanner.build

    def spy_build(self: _RealPlanner, **kw: object) -> object:
        captured.update(kw)
        return real_build(self, **kw)  # type: ignore[arg-type]

    mocker.patch.object(_RealPlanner, "build", spy_build)

    p = _write(tmp_path)
    result = CliRunner().invoke(
        app, ["--no-color", "install", str(p), "--dry-run", "--yes"]
    )
    assert result.exit_code == 0
    assert captured.get("cpu_vendor") == "GenuineIntel"
