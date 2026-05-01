from pathlib import Path

import pytest

from getarch.errors import EnvironmentError as EnvErr
from getarch.execution.context import ExecutionContext
from getarch.execution.fake_runner import FakeRunner
from getarch.execution.result import StepStatus
from getarch.installers.preflight import RuntimeNetworkBootstrapStep


def _ctx(runner: FakeRunner) -> ExecutionContext:
    return ExecutionContext(runner=runner, mount_root=Path("/mnt"))


def test_iwctl_step_writes_psk_to_file_and_runs_connect() -> None:
    runner = FakeRunner()
    step = RuntimeNetworkBootstrapStep(
        backend="iwctl",
        device="wlan0",
        ssid="mywifi",
        psk="hunter2",
    )
    res = step.execute(_ctx(runner))
    assert res.status is StepStatus.SUCCEEDED
    psk_cmd = runner.recorded[0]
    # PSK is fed via stdin to install -Dm600 — never via argv.
    assert psk_cmd.argv[0] == "install"
    assert psk_cmd.argv[-1] == "/var/lib/iwd/mywifi.psk"
    assert psk_cmd.sensitive is True
    assert "hunter2" not in " ".join(psk_cmd.argv)
    assert psk_cmd.input is not None
    assert "hunter2" in psk_cmd.input

    connect_cmd = runner.recorded[1]
    assert connect_cmd.argv[0] == "iwctl"
    assert "connect" in connect_cmd.argv
    assert "mywifi" in connect_cmd.argv
    # No PSK argv on the connect command.
    assert "hunter2" not in " ".join(connect_cmd.argv)


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


def test_iwctl_eap_peap_writes_8021x_profile_and_connects() -> None:
    runner = FakeRunner()
    step = RuntimeNetworkBootstrapStep(
        backend="iwctl-eap",
        device="wlan0",
        ssid="corp",
        username="alice",
        password="s3cret",
        eap_method="PEAP",
    )
    res = step.execute(_ctx(runner))
    assert res.status is StepStatus.SUCCEEDED
    profile_cmd = runner.recorded[0]
    assert profile_cmd.argv[0] == "install"
    assert profile_cmd.argv[-1] == "/var/lib/iwd/corp.8021x"
    assert profile_cmd.sensitive is True
    assert profile_cmd.input is not None
    assert "EAP-Method=PEAP" in profile_cmd.input
    assert "EAP-PEAP-Phase2-Method=MSCHAPV2" in profile_cmd.input
    assert "EAP-PEAP-Phase2-Identity=alice" in profile_cmd.input
    assert "EAP-PEAP-Phase2-Password=s3cret" in profile_cmd.input
    # Password never on argv.
    assert "s3cret" not in " ".join(profile_cmd.argv)

    connect_cmd = runner.recorded[1]
    assert connect_cmd.argv == ("iwctl", "station", "wlan0", "connect", "corp")


def test_iwctl_eap_tls_writes_cert_paths() -> None:
    runner = FakeRunner()
    step = RuntimeNetworkBootstrapStep(
        backend="iwctl-eap",
        device="wlan0",
        ssid="corp",
        username="alice@example.com",
        cert_path="/etc/iwd/client.pem",
        private_key_path="/etc/iwd/client.key",
        eap_method="TLS",
    )
    res = step.execute(_ctx(runner))
    assert res.status is StepStatus.SUCCEEDED
    profile = runner.recorded[0].input or ""
    assert "EAP-Method=TLS" in profile
    assert "EAP-Identity=alice@example.com" in profile
    assert "EAP-TLS-ClientCert=/etc/iwd/client.pem" in profile
    assert "EAP-TLS-ClientKey=/etc/iwd/client.key" in profile


def test_iwctl_eap_ttls_phase2_token_pap() -> None:
    runner = FakeRunner()
    step = RuntimeNetworkBootstrapStep(
        backend="iwctl-eap",
        device="wlan0",
        ssid="corp",
        username="bob",
        password="pw",
        eap_method="TTLS",
    )
    res = step.execute(_ctx(runner))
    assert res.status is StepStatus.SUCCEEDED
    profile = runner.recorded[0].input or ""
    assert "EAP-Method=TTLS" in profile
    assert "EAP-TTLS-Phase2-Method=Token-PAP" in profile
    assert "EAP-TTLS-Phase2-Identity=bob" in profile


def test_iwctl_eap_tls_requires_cert_and_key() -> None:
    step = RuntimeNetworkBootstrapStep(
        backend="iwctl-eap",
        device="wlan0",
        ssid="corp",
        username="alice",
        eap_method="TLS",
    )
    with pytest.raises(EnvErr, match="cert_path"):
        step.execute(_ctx(FakeRunner()))


def test_iwctl_eap_peap_requires_password() -> None:
    step = RuntimeNetworkBootstrapStep(
        backend="iwctl-eap",
        device="wlan0",
        ssid="corp",
        username="alice",
        eap_method="PEAP",
    )
    with pytest.raises(EnvErr, match="PEAP requires password"):
        step.execute(_ctx(FakeRunner()))


def test_iwctl_eap_unsupported_method_raises() -> None:
    step = RuntimeNetworkBootstrapStep(
        backend="iwctl-eap",
        device="wlan0",
        ssid="corp",
        username="alice",
        eap_method="LEAP",
    )
    with pytest.raises(EnvErr, match="unsupported EAP method"):
        step.execute(_ctx(FakeRunner()))


def test_wireguard_step_runs_wg_quick_up() -> None:
    runner = FakeRunner()
    step = RuntimeNetworkBootstrapStep(
        backend="wireguard",
        device="wg0",
        config_path="/etc/wireguard/wg0.conf",
    )
    res = step.execute(_ctx(runner))
    assert res.status is StepStatus.SUCCEEDED
    assert runner.recorded[0].argv == (
        "wg-quick",
        "up",
        "/etc/wireguard/wg0.conf",
    )


def test_wireguard_requires_config_path() -> None:
    step = RuntimeNetworkBootstrapStep(backend="wireguard", device="wg0")
    with pytest.raises(EnvErr, match="config_path"):
        step.execute(_ctx(FakeRunner()))


def test_iwctl_eap_peap_includes_ca_cert_when_provided() -> None:
    runner = FakeRunner()
    step = RuntimeNetworkBootstrapStep(
        backend="iwctl-eap",
        device="wlan0",
        ssid="corp",
        username="alice",
        password="pw",
        ca_cert_path="/etc/ssl/corp-ca.pem",
        eap_method="PEAP",
    )
    res = step.execute(_ctx(runner))
    assert res.status is StepStatus.SUCCEEDED
    profile = runner.recorded[0].input or ""
    assert "EAP-PEAP-CACert=/etc/ssl/corp-ca.pem" in profile


def test_iwctl_eap_tls_includes_ca_cert_when_provided() -> None:
    runner = FakeRunner()
    step = RuntimeNetworkBootstrapStep(
        backend="iwctl-eap",
        device="wlan0",
        ssid="corp",
        username="alice@corp",
        cert_path="/etc/iwd/c.pem",
        private_key_path="/etc/iwd/c.key",
        ca_cert_path="/etc/ssl/corp-ca.pem",
        eap_method="TLS",
    )
    res = step.execute(_ctx(runner))
    assert res.status is StepStatus.SUCCEEDED
    profile = runner.recorded[0].input or ""
    assert "EAP-TLS-CACert=/etc/ssl/corp-ca.pem" in profile
