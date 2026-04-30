from pathlib import Path

import pytest

from getarch.config.loader import load_config
from getarch.config.semantic import validate_semantics

_EXAMPLES_DIR = Path(__file__).resolve().parents[3] / "examples"


@pytest.mark.parametrize("name", ["minimal-ext4.json", "encrypted-btrfs.json", "full.json"])
def test_example_file_validates(name: str) -> None:
    cfg = load_config(_EXAMPLES_DIR / name)
    validate_semantics(cfg)
