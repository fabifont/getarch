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


def test_v1_state_file_still_loadable(tmp_path: Path) -> None:
    """Backwards compat: a v1 state file (no plan_fingerprint) still loads."""
    p = tmp_path / "state.json"
    p.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "completed": ["partitioning"],
                "last_error": None,
            },
        ),
    )
    state = PipelineState.read(p)
    assert state.completed == ["partitioning"]
    assert state.plan_fingerprint is None
    assert state.plan_blob is None
    assert state.schema_version == 2  # promoted on read


def test_fingerprint_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    state = PipelineState(
        completed=["partitioning"],
        plan_fingerprint="abc123",
        plan_blob='{"version": "1"}',
    )
    state.write(p)
    loaded = PipelineState.read(p)
    assert loaded.plan_fingerprint == "abc123"
    assert loaded.plan_blob == '{"version": "1"}'


def test_default_state_path_under_mount(tmp_path: Path) -> None:
    assert default_state_path(tmp_path) == tmp_path / "var/log/getarch.state.json"
