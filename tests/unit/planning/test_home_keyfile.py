from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.config.semantic import validate_semantics
from getarch.domain.disk import Disk, DiskPath
from getarch.planning.planner import Planner


def _disk() -> Disk:
    return Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40)


def _luks_home_with_keyfile() -> dict[str, object]:
    payload = deepcopy(EXAMPLES["encrypted-btrfs"])
    payload["partitioning"] = {
        "layout": "efi-home-root",
        "efi_size_mib": 512,
        "home_size_mib": 8192,
    }
    payload["encryption"] = {
        "kind": "luks2",
        "password": "x",
        "home_kind": "shared-key",
        "home_keyfile": True,
    }
    return payload


def test_keyfile_step_emitted_with_dd_and_luks_add_key() -> None:
    cfg = Config.model_validate(_luks_home_with_keyfile())
    validate_semantics(cfg)
    plan = Planner().build(cfg=cfg, disk=_disk(), mount_root=Path("/mnt"))
    step = next(s for s in plan.steps if s.id == "encryption-home-keyfile")
    script = step.commands[0].argv[2]
    assert "/etc/cryptkey/home.key" in script
    assert "dd if=/dev/urandom" in script
    assert "luksAddKey" in script
    assert step.commands[0].sensitive is True


def test_crypttab_uses_keyfile_when_keyfile_set() -> None:
    cfg = Config.model_validate(_luks_home_with_keyfile())
    plan = Planner().build(cfg=cfg, disk=_disk(), mount_root=Path("/mnt"))
    crypttab = next(s for s in plan.steps if s.id == "crypttab")
    script = crypttab.commands[0].argv[2]
    assert "/etc/cryptkey/home.key" in script
    assert "homecrypt UUID=${HOME_UUID} /etc/cryptkey/home.key luks" in script


def test_crypttab_falls_back_to_none_without_keyfile() -> None:
    payload = _luks_home_with_keyfile()
    payload["encryption"]["home_keyfile"] = False  # type: ignore[index]
    cfg = Config.model_validate(payload)
    plan = Planner().build(cfg=cfg, disk=_disk(), mount_root=Path("/mnt"))
    crypttab = next(s for s in plan.steps if s.id == "crypttab")
    script = crypttab.commands[0].argv[2]
    assert "homecrypt UUID=${HOME_UUID} none luks" in script
    assert "/etc/cryptkey/home.key" not in script


def test_keyfile_requires_home_encryption() -> None:
    payload = deepcopy(EXAMPLES["encrypted-btrfs"])
    payload["encryption"] = {
        "kind": "luks2",
        "password": "x",
        "home_kind": "none",
        "home_keyfile": True,
    }
    with pytest.raises(ValidationError, match="home_keyfile"):
        Config.model_validate(payload)
