from getarch.config.examples import EXAMPLES, render_example
from getarch.config.schema.v1 import Config


def test_examples_contains_minimal_and_encrypted() -> None:
    assert "minimal-ext4" in EXAMPLES
    assert "encrypted-btrfs" in EXAMPLES


def test_each_example_validates_as_config() -> None:
    for payload in EXAMPLES.values():
        Config.model_validate(payload)


def test_render_example_returns_pretty_json() -> None:
    text = render_example("minimal-ext4")
    assert text.startswith("{")
    assert "\n" in text
