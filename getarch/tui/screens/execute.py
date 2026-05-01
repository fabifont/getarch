"""Live install screen.

Runs the install pipeline in a worker thread; tails the LoggingRunner
buffer into a scrollable log view. Confirmations are not yet wired into
modals — the user is expected to pass ``--yes``/``--force`` for now.
This screen is intentionally minimal so the bug surface is small.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Footer, Header, Static

if TYPE_CHECKING:
    from textual.timer import Timer

from getarch.config.loader import load_config
from getarch.config.semantic import validate_semantics
from getarch.constants import DEFAULT_MOUNT_ROOT
from getarch.domain.disk import Disk, DiskPath
from getarch.execution.context import ExecutionContext
from getarch.execution.dry_runner import DryRunner
from getarch.execution.logging_runner import LoggingRunner
from getarch.execution.pipeline import Pipeline
from getarch.execution.state import PipelineState
from getarch.installers.base import PlannedStepExecutor
from getarch.planning.planner import Planner

_REFRESH_INTERVAL_SECONDS = 0.5


class _LiveLog(Static):
    """Scrollable Static that's refreshed periodically from a runner buffer."""

    def __init__(self, runner: LoggingRunner) -> None:
        super().__init__("(no commands yet)")
        self._runner = runner

    def refresh_buffer(self) -> None:
        text = self._runner.render() or "(no commands yet)"
        self.update(text)


class TuiExecuteApp(App[int]):
    """Live install runner inside a Textual app.

    Currently dry-run only. Real-runner support requires modal
    confirmations; tracked in the roadmap.
    """

    CSS = """
    Screen { layout: vertical; }
    #log { padding: 1 2; height: 1fr; }
    #status { padding: 0 2; height: 1; }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, config_path: Path, mount_root: Path) -> None:
        super().__init__()
        self._config_path = config_path
        self._mount_root = mount_root
        self._runner = LoggingRunner(inner=DryRunner())
        self._log_widget = _LiveLog(self._runner)
        self._status = Static("starting…", id="status")
        self._timer: Timer | None = None
        self._worker: threading.Thread | None = None
        self._exit_code: int = 0

    @override
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield self._status
        yield Vertical(VerticalScroll(self._log_widget, id="log"))
        yield Footer()

    def on_mount(self) -> None:
        self._timer = self.set_interval(
            _REFRESH_INTERVAL_SECONDS, self._log_widget.refresh_buffer,
        )
        self._worker = threading.Thread(target=self._run_pipeline, daemon=True)
        self._worker.start()

    def _run_pipeline(self) -> None:
        try:
            cfg = load_config(self._config_path)
            validate_semantics(cfg)
            disk = Disk(path=DiskPath(Path(cfg.disk.path)), size_bytes=2**40)
            plan = Planner().build(
                cfg=cfg, disk=disk, mount_root=self._mount_root,
            )
            steps = tuple(PlannedStepExecutor(planned=s) for s in plan.steps)
            ctx = ExecutionContext(
                runner=self._runner, mount_root=self._mount_root,
            )
            Pipeline(
                steps=steps,  # type: ignore[arg-type]
                initial_state=PipelineState(),
            ).run(ctx)
            self.call_from_thread(
                self._status.update, "[green]dry-run complete[/green] — press q",
            )
        except Exception as exc:  # noqa: BLE001
            self._exit_code = 1
            self.call_from_thread(
                self._status.update, f"[red]error:[/red] {exc} — press q",
            )

    @override
    async def action_quit(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        await super().action_quit()
        self.exit(self._exit_code)


def run(config_path: Path, mount_root: Path = DEFAULT_MOUNT_ROOT) -> int:
    return TuiExecuteApp(
        config_path=config_path, mount_root=mount_root,
    ).run() or 0
