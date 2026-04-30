import pytest

from getarch.domain.locale import Hostname, Keymap, Locale, Timezone


def test_hostname_valid() -> None:
    Hostname("arch")
    Hostname("my-host-1")


def test_hostname_invalid() -> None:
    with pytest.raises(ValueError):
        Hostname("")
    with pytest.raises(ValueError):
        Hostname("Invalid Host")
    with pytest.raises(ValueError):
        Hostname("a" * 254)


def test_locale_includes_charset() -> None:
    Locale("en_US.UTF-8 UTF-8")


def test_locale_lang_property() -> None:
    assert Locale("en_US.UTF-8 UTF-8").lang == "en_US.UTF-8"


def test_keymap_non_empty() -> None:
    with pytest.raises(ValueError):
        Keymap("")
    Keymap("us")


def test_timezone_must_match_pattern() -> None:
    Timezone("Europe/Rome")
    Timezone("UTC")
    with pytest.raises(ValueError):
        Timezone("notatimezone with spaces")
