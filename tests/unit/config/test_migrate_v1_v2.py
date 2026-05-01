"""Schema v2 routing + migrate_v1_to_v2 tests."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from typer.testing import CliRunner

from getarch.cli.app import app
from getarch.config.examples import EXAMPLES
from getarch.config.loader import load_config
from getarch.config.migrations import migrate, migrate_v1_to_v2
from getarch.config.schema.v1 import Config as ConfigV1
from getarch.config.schema.v2 import Config as ConfigV2
from getarch.errors import SyntacticConfigError


def _v1_payload() -> dict[str, object]:
    return deepcopy(EXAMPLES["minimal-ext4"])


def test_migrate_v1_to_v2_bumps_version_and_keeps_fields() -> None:
    payload = _v1_payload()
    out = migrate_v1_to_v2(payload)
    assert out["version"] == 2
    # Every other key is preserved.
    for key, value in payload.items():
        if key == "version":
            continue
        assert out[key] == value


def test_migrate_v1_to_v2_does_not_mutate_input() -> None:
    payload = _v1_payload()
    snapshot = deepcopy(payload)
    migrate_v1_to_v2(payload)
    assert payload == snapshot


def test_migrate_v1_to_v2_rejects_non_v1_input() -> None:
    payload = _v1_payload()
    payload["version"] = 2
    with pytest.raises(SyntacticConfigError, match="want 1"):
        migrate_v1_to_v2(payload)


def test_migrate_top_level_handles_same_version_no_op() -> None:
    payload = _v1_payload()
    out = migrate(payload, to_version=1)
    assert out == payload
    # And it returns a copy, not the original.
    assert out is not payload


def test_migrate_top_level_routes_v1_to_v2() -> None:
    payload = _v1_payload()
    out = migrate(payload, to_version=2)
    assert out["version"] == 2


def test_migrate_top_level_refuses_downgrade() -> None:
    payload = _v1_payload()
    payload["version"] = 2
    with pytest.raises(SyntacticConfigError, match="downgrade"):
        migrate(payload, to_version=1)


def test_migrate_top_level_refuses_unknown_path() -> None:
    payload = _v1_payload()
    with pytest.raises(SyntacticConfigError, match="no path"):
        migrate(payload, to_version=99)


def test_loader_accepts_v1_payload(tmp_path: Path) -> None:
    p = tmp_path / "c.json"
    p.write_text(json.dumps(_v1_payload()), encoding="utf-8")
    cfg = load_config(p)
    assert isinstance(cfg, ConfigV1)
    assert cfg.version == 1


def test_loader_accepts_v2_payload_after_migration(tmp_path: Path) -> None:
    payload = migrate_v1_to_v2(_v1_payload())
    p = tmp_path / "c.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    cfg = load_config(p)
    assert isinstance(cfg, ConfigV2)
    assert cfg.version == 2
    # v2 has all the v1 fields.
    assert cfg.disk.path == "/dev/sda"


def test_loader_rejects_unknown_version(tmp_path: Path) -> None:
    payload = _v1_payload()
    payload["version"] = 99
    p = tmp_path / "c.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SyntacticConfigError, match="unsupported config version"):
        load_config(p)


def test_cli_migrate_writes_to_stdout(tmp_path: Path) -> None:
    src = tmp_path / "c.json"
    src.write_text(json.dumps(_v1_payload()), encoding="utf-8")
    result = CliRunner().invoke(
        app, ["migrate", str(src), "--to", "2"],
    )
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["version"] == 2


def test_cli_migrate_writes_to_output_file(tmp_path: Path) -> None:
    src = tmp_path / "c.json"
    out = tmp_path / "out.json"
    src.write_text(json.dumps(_v1_payload()), encoding="utf-8")
    result = CliRunner().invoke(
        app, ["migrate", str(src), "--to", "2", "--output", str(out)],
    )
    assert result.exit_code == 0
    assert out.is_file()
    assert json.loads(out.read_text(encoding="utf-8"))["version"] == 2
