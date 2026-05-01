import json
from pathlib import Path

from typer.testing import CliRunner

from getarch.cli.app import app
from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.domain.disk import Disk, DiskPath
from getarch.execution.state import PipelineState, default_state_path
from getarch.planning.planner import Planner
from getarch.planning.rendering import render_json


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
    assert "---" in out
    assert "+++" in out
    # Encryption is unique to the btrfs config.
    lowered = out.lower()
    assert "encryption" in lowered or "luks" in lowered


def test_diff_against_installed_no_state(tmp_path: Path) -> None:
    a = _write(tmp_path, "minimal-ext4")
    result = CliRunner().invoke(
        app,
        ["--no-color", "diff", str(a), "--against-installed", "--mount-root", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "no previous install state" in result.output.lower()


def test_diff_against_installed_matches_when_blob_present(tmp_path: Path) -> None:
    a = _write(tmp_path, "minimal-ext4")
    cfg = Config.model_validate(EXAMPLES["minimal-ext4"])
    disk = Disk(path=DiskPath(Path(cfg.disk.path)), size_bytes=2**40)
    plan_blob = render_json(Planner().build(cfg=cfg, disk=disk, mount_root=tmp_path))
    state_path = default_state_path(tmp_path)
    PipelineState(plan_blob=plan_blob).write(state_path)

    result = CliRunner().invoke(
        app,
        ["--no-color", "diff", str(a), "--against-installed", "--mount-root", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "identical" in result.output.lower()
