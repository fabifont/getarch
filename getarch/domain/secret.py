"""Secret value object - string-like wrapper that never leaks via str/repr/format."""

from __future__ import annotations

from typing import override


class Secret:
    """A wrapper around a sensitive string. ``str`` and ``repr`` never reveal it."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    @override
    def __repr__(self) -> str:
        return "Secret('***')"

    @override
    def __str__(self) -> str:
        return "***"

    @override
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Secret) and self._value == other._value

    @override
    def __hash__(self) -> int:
        return hash(self._value)
