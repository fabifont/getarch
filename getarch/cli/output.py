"""Rich-backed console with JSON and no-color toggles."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass

from rich.console import Console
from rich.prompt import Confirm

from getarch.errors import GetarchError


@dataclass(slots=True)
class GetarchConsole:
    json_mode: bool = False
    no_color: bool = False
    _console: Console = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._console = Console(no_color=self.no_color, force_terminal=not self.no_color)

    def log(self, payload: object) -> None:
        if self.json_mode:
            sys.stdout.write(json.dumps(payload, default=str) + "\n")
            sys.stdout.flush()
            return
        self._console.print(payload)

    def error(self, message: str) -> None:
        if self.json_mode:
            sys.stdout.write(json.dumps({"level": "error", "message": message}) + "\n")
        else:
            self._console.print(f"[bold red]error:[/bold red] {message}")

    def render_exception(self, exc: GetarchError) -> None:
        """Render a getarch exception with its stable code + help link."""
        code = exc.code
        message = str(exc)
        if self.json_mode:
            payload: dict[str, object] = {
                "level": "error",
                "code": code,
                "message": message,
            }
            if exc.hint:
                payload["hint"] = exc.hint
            sys.stdout.write(json.dumps(payload) + "\n")
            return
        self._console.print(
            f"[bold red]error\\[{code}]:[/bold red] {message}",
        )
        if exc.hint:
            self._console.print(f"  [yellow]hint:[/yellow] {exc.hint}")
        self._console.print(
            f"  [dim]see:[/dim] getarch help error {code}",
        )

    def confirm(self, message: str) -> bool:
        if self.json_mode:
            return False
        return Confirm.ask(message, default=False, console=self._console)
