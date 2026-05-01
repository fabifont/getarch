"""Audit log schema v1 + HMAC trailer behaviour."""

from __future__ import annotations

import hmac
import json
from hashlib import sha256

from getarch.execution.command import Command
from getarch.execution.fake_runner import FakeRunner
from getarch.execution.logging_runner import AUDIT_SCHEMA_VERSION, LoggingRunner


def test_every_record_starts_with_schema_version_and_type() -> None:
    runner = LoggingRunner(inner=FakeRunner())
    runner.run(Command(argv=("echo", "a")))
    runner.run(Command(argv=("chpasswd",), input="x", sensitive=True))
    for raw in runner.lines:
        rec = json.loads(raw)
        assert rec["schema_version"] == AUDIT_SCHEMA_VERSION
        assert rec["type"] == "command"


def test_render_without_hmac_key_omits_trailer() -> None:
    runner = LoggingRunner(inner=FakeRunner())
    runner.run(Command(argv=("echo", "a")))
    text = runner.render()
    last = text.rstrip("\n").splitlines()[-1]
    rec = json.loads(last)
    assert rec["type"] == "command"


def test_render_with_hmac_key_appends_trailer() -> None:
    runner = LoggingRunner(inner=FakeRunner(), hmac_key=b"shhh")
    runner.run(Command(argv=("echo", "a")))
    runner.run(Command(argv=("echo", "b")))
    text = runner.render()
    lines = text.rstrip("\n").splitlines()
    body = "\n".join(lines[:-1]) + "\n"
    trailer = json.loads(lines[-1])
    assert trailer["type"] == "hmac"
    assert trailer["alg"] == "HMAC-SHA256"
    assert trailer["schema_version"] == AUDIT_SCHEMA_VERSION
    expected = hmac.new(b"shhh", body.encode("utf-8"), sha256).hexdigest()
    assert trailer["value"] == expected


def test_hmac_trailer_changes_when_key_changes() -> None:
    runner1 = LoggingRunner(inner=FakeRunner(), hmac_key=b"k1")
    runner2 = LoggingRunner(inner=FakeRunner(), hmac_key=b"k2")
    for r in (runner1, runner2):
        r.run(Command(argv=("echo", "x")))
    t1 = json.loads(runner1.render().splitlines()[-1])["value"]
    t2 = json.loads(runner2.render().splitlines()[-1])["value"]
    assert t1 != t2


def test_hmac_trailer_changes_when_body_changes() -> None:
    a = LoggingRunner(inner=FakeRunner(), hmac_key=b"k")
    b = LoggingRunner(inner=FakeRunner(), hmac_key=b"k")
    a.run(Command(argv=("echo", "first")))
    b.run(Command(argv=("echo", "second")))
    ta = json.loads(a.render().splitlines()[-1])["value"]
    tb = json.loads(b.render().splitlines()[-1])["value"]
    assert ta != tb


def test_hmac_can_be_verified_independently() -> None:
    """Pin the verification recipe documented in docs/audit-schema.md."""

    runner = LoggingRunner(inner=FakeRunner(), hmac_key=b"unit-test-key")
    runner.run(Command(argv=("echo", "alpha")))
    runner.run(Command(argv=("echo", "beta")))
    text = runner.render()
    lines = text.rstrip("\n").splitlines()
    body_lines = lines[:-1]
    trailer_line = lines[-1]
    body = "\n".join(body_lines) + "\n"
    actual = hmac.new(b"unit-test-key", body.encode("utf-8"), sha256).hexdigest()
    expected = json.loads(trailer_line)["value"]
    assert actual == expected
