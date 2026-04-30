import pytest

from getarch.errors import (
    CommandFailedError,
    ConfigError,
    DiscoveryError,
    EnvironmentError,
    GetarchError,
    PlanError,
    SemanticConfigError,
    SyntacticConfigError,
)


def test_hierarchy() -> None:
    assert issubclass(ConfigError, GetarchError)
    assert issubclass(SyntacticConfigError, ConfigError)
    assert issubclass(SemanticConfigError, ConfigError)
    assert issubclass(EnvironmentError, GetarchError)
    assert issubclass(DiscoveryError, GetarchError)
    assert issubclass(PlanError, GetarchError)
    assert issubclass(CommandFailedError, GetarchError)


def test_command_failed_carries_context() -> None:
    err = CommandFailedError(argv=("ls", "/nope"), returncode=2, stderr="not found")
    assert err.argv == ("ls", "/nope")
    assert err.returncode == 2
    assert "not found" in str(err)


def test_getarch_error_is_runtime_error() -> None:
    with pytest.raises(GetarchError):
        raise GetarchError("boom")
