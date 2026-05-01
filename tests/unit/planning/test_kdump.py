"""kdump planner integration tests."""

from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.config.semantic import validate_semantics
from getarch.domain.disk import Disk, DiskPath
from getarch.errors import SemanticConfigError
from getarch.planning.planner import Planner


def _payload_with_kdump(extra: dict[str, object] | None = None) -> dict[str, object]:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["kdump"] = {"enable": True, "crashkernel": "256M,high", **(extra or {})}
    return payload


def test_kdump_appends_crashkernel_to_bootloader_cmdline() -> None:
    cfg = Config.model_validate(_payload_with_kdump())
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    boot = next(s for s in plan.steps if s.id == "bootloader")
    flat = " ".join(arg for c in boot.commands for arg in c.argv) + " " + " ".join(
        c.input or "" for c in boot.commands
    )
    assert "crashkernel=256M,high" in flat


def test_kdump_user_supplied_crashkernel_wins() -> None:
    payload = _payload_with_kdump()
    payload["bootloader"] = {
        "kind": "systemd-boot",
        "extra_kernel_params": ["crashkernel=512M,low"],
    }
    cfg = Config.model_validate(payload)
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    boot = next(s for s in plan.steps if s.id == "bootloader")
    flat = " ".join(arg for c in boot.commands for arg in c.argv) + " " + " ".join(
        c.input or "" for c in boot.commands
    )
    assert "crashkernel=512M,low" in flat
    # The default 256M,high must NOT be appended on top of the user's
    # explicit override.
    assert "crashkernel=256M,high" not in flat


def test_kdump_auto_adds_kexec_tools_package() -> None:
    payload = _payload_with_kdump()
    pkgs = cast("list[str]", payload["packages"])
    payload["packages"] = [p for p in pkgs if p != "kexec-tools"]
    cfg = Config.model_validate(payload)
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    pkgs_step = next(s for s in plan.steps if s.id == "packages")
    assert "kexec-tools" in pkgs_step.commands[0].argv


def test_kdump_enables_kdump_service() -> None:
    cfg = Config.model_validate(_payload_with_kdump())
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    services = next(s for s in plan.steps if s.id == "services")
    flat = " ".join(arg for c in services.commands for arg in c.argv)
    assert "kdump.service" in flat


def test_kdump_disabled_does_not_touch_cmdline_or_packages() -> None:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    cfg = Config.model_validate(payload)
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    boot = next(s for s in plan.steps if s.id == "bootloader")
    flat = " ".join(arg for c in boot.commands for arg in c.argv) + " " + " ".join(
        c.input or "" for c in boot.commands
    )
    assert "crashkernel" not in flat
    pkgs_step = next(s for s in plan.steps if s.id == "packages")
    assert "kexec-tools" not in pkgs_step.commands[0].argv


def test_semantic_kdump_rejects_uki() -> None:
    payload = _payload_with_kdump()
    payload["bootloader"] = {"kind": "uki", "entry_id": "arch"}
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="uki"):
        validate_semantics(cfg)


def test_semantic_kdump_rejects_container() -> None:
    payload = _payload_with_kdump()
    payload["firmware"] = "container"
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="container"):
        validate_semantics(cfg)


def test_schema_kdump_rejects_invalid_crashkernel() -> None:
    payload = _payload_with_kdump({"crashkernel": "garbage"})
    with pytest.raises(ValueError, match="crashkernel"):
        Config.model_validate(payload)
