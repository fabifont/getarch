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


def _swap_partition_cfg(*, encrypt: bool) -> dict[str, object]:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["partitioning"] = {
        "layout": "efi-swap-root",
        "efi_size_mib": 512,
        "swap_size_mib": 2048,
    }
    payload["swap"] = {"kind": "partition", "encrypt": encrypt}
    return payload


def test_swap_partition_unencrypted_runs_mkswap_swapon() -> None:
    cfg = Config.model_validate(_swap_partition_cfg(encrypt=False))
    validate_semantics(cfg)
    plan = Planner().build(cfg=cfg, disk=_disk(), mount_root=Path("/mnt"))
    swap_step = next(s for s in plan.steps if s.id == "swap")
    argvs = [c.argv for c in swap_step.commands]
    assert ("mkswap", "/dev/disk/by-partlabel/swap") in argvs
    assert ("swapon", "/dev/disk/by-partlabel/swap") in argvs
    # No cryptsetup invocation when encrypt=False.
    assert all(a[0] != "cryptsetup" for a in argvs)


def test_swap_partition_encrypted_opens_random_key_mapper() -> None:
    cfg = Config.model_validate(_swap_partition_cfg(encrypt=True))
    validate_semantics(cfg)
    plan = Planner().build(cfg=cfg, disk=_disk(), mount_root=Path("/mnt"))
    swap_step = next(s for s in plan.steps if s.id == "swap")
    argvs = [c.argv for c in swap_step.commands]
    open_cmd = next(a for a in argvs if a[0] == "cryptsetup")
    assert "--type" in open_cmd
    assert "plain" in open_cmd
    assert "/dev/urandom" in open_cmd
    assert "swapcrypt" in open_cmd
    assert ("mkswap", "/dev/mapper/swapcrypt") in argvs
    assert ("swapon", "/dev/mapper/swapcrypt") in argvs


def test_swap_encrypt_writes_crypttab_swapcrypt_entry() -> None:
    cfg = Config.model_validate(_swap_partition_cfg(encrypt=True))
    validate_semantics(cfg)
    plan = Planner().build(cfg=cfg, disk=_disk(), mount_root=Path("/mnt"))
    crypttab = next(s for s in plan.steps if s.id == "crypttab")
    script = crypttab.commands[0].argv[2]
    assert "swapcrypt /dev/disk/by-partlabel/swap /dev/urandom swap,plain" in script


def test_swap_encrypt_requires_partition_kind() -> None:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["swap"] = {"kind": "swapfile", "size_mib": 1024, "encrypt": True}
    with pytest.raises(ValidationError, match="encrypt"):
        Config.model_validate(payload)
