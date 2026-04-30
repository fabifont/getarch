import json
from pathlib import Path

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.domain.disk import Disk, DiskPath
from getarch.domain.plan import InstallPlan
from getarch.planning.planner import Planner
from getarch.planning.rendering import render_json, render_text


def _plan() -> InstallPlan:
    cfg = Config.model_validate(EXAMPLES["minimal-ext4"])
    return Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),
        mount_root=Path("/mnt"),
    )


def test_render_text_lists_steps_in_order() -> None:
    text = render_text(_plan())
    assert "Partition disk" in text
    assert "Mount filesystems" in text
    assert text.index("Partition disk") < text.index("Mount filesystems")


def test_render_text_marks_destructive() -> None:
    text = render_text(_plan())
    assert "DESTRUCTIVE" in text


def test_render_json_round_trips() -> None:
    obj = json.loads(render_json(_plan()))
    assert obj["version"] == "1"
    assert any(s["id"] == "partitioning" for s in obj["steps"])
    assert all("commands" in s for s in obj["steps"])


def test_render_json_redacts_sensitive_input() -> None:
    cfg = Config.model_validate(EXAMPLES["encrypted-btrfs"])
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),
        mount_root=Path("/mnt"),
    )
    blob = render_json(plan)
    assert "CHANGE_ME" not in blob
    assert "***" in blob
