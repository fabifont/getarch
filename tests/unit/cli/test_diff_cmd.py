import json
from pathlib import Path

from typer.testing import CliRunner

from getarch.cli.app import app
from getarch.config.examples import EXAMPLES


def _write(tmp: Path, key: str) -> Path:
    p = tmp / f"{key}.json"
    p.write_text(json.dumps(EXAMPLES[key]))
    return p


def test_diff_identical_configs_reports_match(tmp_path: Path) -> None:
    a = _write(tmp_path, "minimal-ext4")
    b = _write(tmp_path, "minimal-ext4")
    result = CliRunner().invoke(app, ["--no-color", "diff", str(a), str(b)])
    assert result.exit_code == 0
    assert "identical" in result.output.lower()


def test_diff_different_configs_emits_unified_diff(tmp_path: Path) -> None:
    a = _write(tmp_path, "minimal-ext4")
    b = _write(tmp_path, "encrypted-btrfs")
    result = CliRunner().invoke(app, ["--no-color", "diff", str(a), str(b)])
    assert result.exit_code == 0
    out = result.output
    assert "---" in out and "+++" in out
    # Encryption is unique to the btrfs config.
    assert "encryption" in out.lower() or "luks" in out.lower()
