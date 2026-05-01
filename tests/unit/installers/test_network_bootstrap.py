from pathlib import Path

import pytest

from getarch.errors import EnvironmentError as EnvErr
from getarch.execution.context import ExecutionContext
from getarch.execution.fake_runner import FakeRunner
from getarch.execution.result import StepStatus
from getarch.installers.preflight import RuntimeNetworkBootstrapStep


def _ctx(runner: FakeRunner) -> ExecutionContext:
    return ExecutionContext(runner=runner, mount_root=Path("/mnt"))


def test_iwctl_step_redacts_psk_and_runs_connect() -> None:
    runner = FakeRunner()
    step = RuntimeNetworkBootstrapStep(
        backend="iwctl",
        device="wlan0",
        ssid="mywifi",
        psk="hunter2",
    )
    res = step.execute(_ctx(runner))
    assert res.status is StepStatus.SUCCEEDED
    cmd = runner.recorded[0]
    assert cmd.argv[0] == "iwctl"
    assert "connect" in cmd.argv
    assert "mywifi" in cmd.argv
    assert cmd.sensitive is True


def test_dhcp_step_runs_dhcpcd() -> None:
    runner = FakeRunner()
    step = RuntimeNetworkBootstrapStep(backend="dhcp", device="enp0s3")
    res = step.execute(_ctx(runner))
    assert res.status is StepStatus.SUCCEEDED
    assert runner.recorded[0].argv == ("dhcpcd", "enp0s3")


def test_iwctl_requires_ssid_and_psk() -> None:
    step = RuntimeNetworkBootstrapStep(backend="iwctl", device="wlan0")
    with pytest.raises(EnvErr, match="ssid"):
        step.execute(_ctx(FakeRunner()))


def test_unknown_backend_raises() -> None:
    step = RuntimeNetworkBootstrapStep(backend="bogus", device="wlan0")
    with pytest.raises(EnvErr, match="bogus"):
        step.execute(_ctx(FakeRunner()))
