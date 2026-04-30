"""Rich-backed console with JSON and no-color toggles."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass

from rich.console import Console
from rich.prompt import Confirm


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

    def confirm(self, message: str) -> bool:
        if self.json_mode:
            return False
        return Confirm.ask(message, default=False, console=self._console)
