import json
from pathlib import Path

import pytest

from getarch.execution.state import PipelineState, default_state_path


def test_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    state = PipelineState(completed=["partitioning", "encryption"], last_error=None)
    state.write(p)
    loaded = PipelineState.read(p)
    assert loaded.completed == ["partitioning", "encryption"]
    assert loaded.last_error is None


def test_last_error_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    state = PipelineState(completed=["partitioning"], last_error="boom")
    state.write(p)
    loaded = PipelineState.read(p)
    assert loaded.last_error == "boom"


def test_unsupported_schema_version_rejected(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"schema_version": 99, "completed": []}))
    with pytest.raises(ValueError, match="schema_version"):
        PipelineState.read(p)


def test_default_state_path_under_mount(tmp_path: Path) -> None:
    assert default_state_path(tmp_path) == tmp_path / "var/log/getarch.state.json"
