from copy import deepcopy

import pytest
from pydantic import ValidationError

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.config.semantic import validate_semantics
from getarch.errors import SemanticConfigError


def test_string_locale_back_compat() -> None:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["locale"] = {
        "lang": "en_US.UTF-8",
        "locale": "en_US.UTF-8 UTF-8",
        "keymap": "us",
        "timezone": "UTC",
    }
    cfg = Config.model_validate(payload)
    assert cfg.locale.locale == ["en_US.UTF-8 UTF-8"]
    validate_semantics(cfg)


def test_multi_locale_list_accepted() -> None:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["locale"] = {
        "lang": "en_US.UTF-8",
        "locale": ["en_US.UTF-8 UTF-8", "it_IT.UTF-8 UTF-8"],
        "keymap": "us",
        "timezone": "Europe/Rome",
    }
    cfg = Config.model_validate(payload)
    assert cfg.locale.locale == ["en_US.UTF-8 UTF-8", "it_IT.UTF-8 UTF-8"]
    validate_semantics(cfg)


def test_lang_must_match_one_locale() -> None:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["locale"] = {
        "lang": "fr_FR.UTF-8",
        "locale": ["en_US.UTF-8 UTF-8", "it_IT.UTF-8 UTF-8"],
        "keymap": "us",
        "timezone": "UTC",
    }
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="prefix"):
        validate_semantics(cfg)


def test_empty_locale_list_rejected() -> None:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["locale"] = {
        "lang": "en_US.UTF-8",
        "locale": [],
        "keymap": "us",
        "timezone": "UTC",
    }
    with pytest.raises(ValidationError):
        Config.model_validate(payload)
