"""Sanity tests for the QEMU smoke matrix configs.

Catches missing packages, broken cross-section invariants, and any future
combination that the matrix workflow would otherwise silently boot before
failing in pacstrap or systemctl.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from getarch.config.schema.v1 import Config
from getarch.config.semantic import validate_semantics

_QEMU_CONFIGS_PATH = Path(__file__).resolve().parents[3] / "test_resources" / "qemu_configs.py"


def _load_qemu_configs_module() -> Any:
    spec = importlib.util.spec_from_file_location("qemu_configs", _QEMU_CONFIGS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {_QEMU_CONFIGS_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MATRIX = [
    (fs, bl) for fs in ("ext4", "btrfs", "xfs", "f2fs") for bl in ("systemd-boot", "grub", "uki")
]


@pytest.mark.parametrize(("fs", "bl"), _MATRIX)
def test_qemu_config_validates(fs: str, bl: str) -> None:
    module = _load_qemu_configs_module()
    raw = module.build(fs, bl)
    cfg = Config.model_validate(raw)
    validate_semantics(cfg)
    enabled = set(cfg.services.enable)
    pkgs = set(cfg.packages)
    # Every enabled service unit must come from a pacstrap-installed
    # package; otherwise `systemctl enable <svc>` will fail in chroot.
    assert "sshd" not in enabled or "openssh" in pkgs
    assert "NetworkManager" not in enabled or "networkmanager" in pkgs
