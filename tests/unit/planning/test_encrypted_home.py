from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.config.semantic import validate_semantics
from getarch.domain.disk import Disk, DiskPath
from getarch.errors import SemanticConfigError
from getarch.planning.planner import Planner


def _disk() -> Disk:
    return Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40)


def _luks_home_btrfs() -> dict[str, object]:
    payload = deepcopy(EXAMPLES["encrypted-btrfs"])
    payload["partitioning"] = {
        "layout": "efi-home-root",
        "efi_size_mib": 512,
        "home_size_mib": 8192,
    }
    return payload


def test_luks_with_home_layout_without_home_kind_rejected() -> None:
    cfg = Config.model_validate(_luks_home_btrfs())
    with pytest.raises(SemanticConfigError, match="home_kind"):
        validate_semantics(cfg)


def test_separate_key_requires_home_password() -> None:
    payload = _luks_home_btrfs()
    payload["encryption"] = {
        "kind": "luks2",
        "password": "x",
        "home_kind": "separate-key",
    }
    with pytest.raises(ValidationError, match="home_password"):
        Config.model_validate(payload)


def test_shared_key_path_emits_encryption_home_step_and_uses_mapper() -> None:
    payload = _luks_home_btrfs()
    payload["encryption"] = {
        "kind": "luks2",
        "password": "x",
        "home_kind": "shared-key",
    }
    cfg = Config.model_validate(payload)
    validate_semantics(cfg)
    plan = Planner().build(cfg=cfg, disk=_disk(), mount_root=Path("/mnt"))
    ids = [s.id for s in plan.steps]
    assert "encryption-home" in ids
    fs_step = next(s for s in plan.steps if s.id == "filesystems")
    flat = " ".join(arg for c in fs_step.commands for arg in c.argv)
    assert "/dev/mapper/homecrypt" in flat
    assert "by-partlabel/home" not in flat
    crypttab = next(s for s in plan.steps if s.id == "crypttab")
    bash = crypttab.commands[0]
    assert "blkid" in bash.argv[2]
    assert "homecrypt" in bash.argv[2]


def test_separate_key_uses_home_password_in_format() -> None:
    payload = _luks_home_btrfs()
    payload["encryption"] = {
        "kind": "luks2",
        "password": "rootpw",
        "home_kind": "separate-key",
        "home_password": "homepw",
    }
    cfg = Config.model_validate(payload)
    validate_semantics(cfg)
    plan = Planner().build(cfg=cfg, disk=_disk(), mount_root=Path("/mnt"))
    enc_home = next(s for s in plan.steps if s.id == "encryption-home")
    fmt = enc_home.commands[0]
    assert fmt.input is not None
    assert fmt.input.startswith("homepw")
