"""Regression: failed commands MUST appear in the signed audit log.

``LoggingRunner.run`` previously only appended to the audit buffer
after the inner runner returned. With ``check=True`` (the default)
``RealRunner`` raises ``CommandFailedError`` on non-zero exits; the
failed command never made it into the buffer, so the HMAC trailer
signed an audit log that silently omitted the operationally most
important event.
"""

from __future__ import annotations

import json

import pytest

from getarch.errors import CommandFailedError
from getarch.execution.command import Command
from getarch.execution.fake_runner import FakeResponse, FakeRunner
from getarch.execution.logging_runner import LoggingRunner


def test_failed_checked_command_is_recorded_before_reraise() -> None:
    inner = FakeRunner(
        responses={
            ("pacstrap", "/mnt"): FakeResponse(returncode=1, stderr="boom"),
        },
    )
    runner = LoggingRunner(inner=inner)
    with pytest.raises(CommandFailedError):
        runner.run(Command(argv=("pacstrap", "/mnt")))
    assert len(runner.lines) == 1
    record = json.loads(runner.lines[0])
    assert record["argv"] == ["pacstrap", "/mnt"]
    assert record["exit"] == 1
    assert record["stderr_tail"] == "boom"


def test_hmac_trailer_covers_failed_record() -> None:
    inner = FakeRunner(
        responses={
            ("pacstrap", "/mnt"): FakeResponse(returncode=1, stderr="boom"),
        },
    )
    runner = LoggingRunner(inner=inner, hmac_key=b"k")
    with pytest.raises(CommandFailedError):
        runner.run(Command(argv=("pacstrap", "/mnt")))
    text = runner.render()
    lines = text.rstrip("\n").splitlines()
    # First line is the failed record; second is the HMAC trailer.
    assert json.loads(lines[0])["exit"] == 1
    assert json.loads(lines[1])["type"] == "hmac"
