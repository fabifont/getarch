import pytest

from getarch.domain.secret import Secret
from getarch.domain.users import RootAuth, RootAuthKind, Username, UserSpec


def test_username_valid() -> None:
    Username("alice")
    Username("alice_1")


def test_username_invalid() -> None:
    with pytest.raises(ValueError):
        Username("")
    with pytest.raises(ValueError):
        Username("Alice")
    with pytest.raises(ValueError):
        Username("1alice")


def test_user_spec_with_groups() -> None:
    u = UserSpec(  # noqa: S604 — ``shell`` is a UserSpec field, not subprocess
        username=Username("alice"),
        password=Secret("pw"),
        groups=("wheel", "audio"),
        shell="/bin/zsh",
    )
    assert u.groups == ("wheel", "audio")


def test_root_auth_prompt_kind_no_secret() -> None:
    RootAuth(kind=RootAuthKind.PROMPT)


def test_root_auth_plain_requires_secret() -> None:
    with pytest.raises(ValueError):
        RootAuth(kind=RootAuthKind.PLAIN)


def test_root_auth_hashed_requires_value() -> None:
    with pytest.raises(ValueError):
        RootAuth(kind=RootAuthKind.HASHED)
