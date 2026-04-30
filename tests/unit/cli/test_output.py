import pytest

from getarch.cli.output import GetarchConsole


def test_console_emits_to_capsys(capsys: pytest.CaptureFixture[str]) -> None:
    GetarchConsole(json_mode=False, no_color=True).log("hello")
    captured = capsys.readouterr()
    assert "hello" in captured.out


def test_console_json_mode_emits_jsonl(capsys: pytest.CaptureFixture[str]) -> None:
    GetarchConsole(json_mode=True, no_color=True).log({"event": "ok"})
    captured = capsys.readouterr()
    assert '"event"' in captured.out
