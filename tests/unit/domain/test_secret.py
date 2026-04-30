from getarch.domain.secret import Secret


def test_secret_repr_redacts() -> None:
    s = Secret("hunter2")
    assert "hunter2" not in repr(s)
    assert "***" in repr(s)


def test_secret_str_redacts() -> None:
    s = Secret("hunter2")
    assert "hunter2" not in str(s)


def test_secret_reveal_returns_value() -> None:
    s = Secret("hunter2")
    assert s.reveal() == "hunter2"


def test_secret_equality_value_based() -> None:
    assert Secret("a") == Secret("a")
    assert Secret("a") != Secret("b")
