import json
from pathlib import Path

from typer.testing import CliRunner

from getarch.cli.app import app
from getarch.config.examples import EXAMPLES


def _write(tmp: Path, payload: object) -> Path:
    p = tmp / "c.json"
    p.write_text(json.dumps(payload))
    return p


def test_validate_ok(tmp_path: Path) -> None:
    p = _write(tmp_path, EXAMPLES["minimal-ext4"])
    result = CliRunner().invoke(app, ["--no-color", "validate", str(p)])
    assert result.exit_code == 0
    assert "valid" in result.output.lower()


def test_validate_fails_on_missing_field(tmp_path: Path) -> None:
    bad = dict(EXAMPLES["minimal-ext4"])
    del bad["packages"]
    p = _write(tmp_path, bad)
    result = CliRunner().invoke(app, ["--no-color", "validate", str(p)])
    assert result.exit_code != 0
    assert "packages" in result.output


def test_validate_json_mode(tmp_path: Path) -> None:
    p = _write(tmp_path, EXAMPLES["minimal-ext4"])
    result = CliRunner().invoke(app, ["--json", "validate", str(p)])
    assert result.exit_code == 0
    payload = json.loads(result.output.strip().splitlines()[0])
    assert payload["status"] == "ok"
