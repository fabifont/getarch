from pathlib import Path

from getarch.execution.fake_runner import FakeResponse, FakeRunner
from getarch.system.environment import IsoEnvironment


def test_cpu_vendor_intel(tmp_path: Path) -> None:
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text("processor : 0\nvendor_id : GenuineIntel\n")
    runner = FakeRunner()
    env = IsoEnvironment(runner=runner, cpuinfo_path=cpuinfo, locales_path=tmp_path / "x")
    assert env.cpu_vendor() == "GenuineIntel"


def test_cpu_vendor_missing(tmp_path: Path) -> None:
    runner = FakeRunner()
    env = IsoEnvironment(runner=runner, cpuinfo_path=tmp_path / "no", locales_path=tmp_path / "x")
    assert env.cpu_vendor() is None


def test_supported_locales_strips_comments(tmp_path: Path) -> None:
    locales = tmp_path / "SUPPORTED"
    locales.write_text("# comment\nen_US.UTF-8 UTF-8\nfr_FR.UTF-8 UTF-8\n\n")
    runner = FakeRunner()
    env = IsoEnvironment(runner=runner, cpuinfo_path=tmp_path / "no", locales_path=locales)
    assert env.supported_locales() == ("en_US.UTF-8 UTF-8", "fr_FR.UTF-8 UTF-8")


def test_keymaps_via_localectl() -> None:
    runner = FakeRunner(
        responses={("localectl", "list-keymaps"): FakeResponse(stdout="us\nde\nfr\n")},
    )
    env = IsoEnvironment(runner=runner, cpuinfo_path=Path("/no"), locales_path=Path("/no"))
    assert env.keymaps() == ("us", "de", "fr")


def test_timezones_via_timedatectl() -> None:
    runner = FakeRunner(
        responses={
            ("timedatectl", "list-timezones"): FakeResponse(stdout="UTC\nEurope/Rome\n"),
        },
    )
    env = IsoEnvironment(runner=runner, cpuinfo_path=Path("/no"), locales_path=Path("/no"))
    assert env.timezones() == ("UTC", "Europe/Rome")
