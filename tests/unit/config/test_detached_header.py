from copy import deepcopy

import pytest

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.config.semantic import validate_semantics
from getarch.errors import SemanticConfigError

_LUKSHEADER_DEVICE = "/dev/disk/by-partlabel/cryptheader"


def _luks_btrfs(layout: str) -> dict[str, object]:
    payload = deepcopy(EXAMPLES["encrypted-btrfs"])
    payload["partitioning"] = {"layout": layout, "efi_size_mib": 512}
    return payload


def test_luksheader_layout_with_header_path_validates() -> None:
    payload = _luks_btrfs("efi-luksheader-root")
    payload["encryption"] = {
        "kind": "luks2",
        "password": "x",
        "header_path": _LUKSHEADER_DEVICE,
    }
    cfg = Config.model_validate(payload)
    validate_semantics(cfg)
    assert cfg.encryption.header_path == _LUKSHEADER_DEVICE


def test_luksheader_layout_without_header_path_rejected() -> None:
    payload = _luks_btrfs("efi-luksheader-root")
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="header_path"):
        validate_semantics(cfg)


def test_header_path_without_luksheader_layout_rejected() -> None:
    payload = _luks_btrfs("efi-root")
    payload["encryption"] = {
        "kind": "luks2",
        "password": "x",
        "header_path": _LUKSHEADER_DEVICE,
    }
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="luksheader"):
        validate_semantics(cfg)
