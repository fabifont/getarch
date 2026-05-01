"""Live install screen.

Runs the install pipeline in a worker thread; tails the LoggingRunner
buffer into a scrollable log view. Destructive plans are gated by a
modal confirmation dialog (see :mod:`getarch.tui.screens.confirm`).
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

    from getarch.execution.runner import CommandRunner

from getarch.config.loader import load_config
from getarch.config.semantic import validate_semantics
from getarch.constants import DEFAULT_MOUNT_ROOT
from getarch.domain.disk import Disk, DiskPath
from getarch.execution.context import ExecutionContext
from getarch.execution.dry_runner import DryRunner
from getarch.execution.logging_runner import LoggingRunner
from getarch.execution.pipeline import Pipeline
from getarch.execution.real_runner import RealRunner
from getarch.execution.state import PipelineState
from getarch.installers.base import PlannedStepExecutor
from getarch.installers.confirmation import require_destructive_confirmation
from getarch.planning.planner import Planner
from getarch.tui.screens.confirm import ConfirmModal

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

    Two modes:

    * **dry-run** (default): wraps :class:`DryRunner`; no destructive
      operations actually fire. The confirmation modal is skipped.
    * **real** (``dry_run=False``): wraps :class:`RealRunner`. The
      worker thread blocks on a :class:`ConfirmModal` whose answer
      determines whether the install pipeline runs.

    The optional ``runner_factory`` parameter exists so tests can
    inject a :class:`FakeRunner` instead of touching the system.
    """

    CSS = """
    Screen { layout: vertical; }
    #log { padding: 1 2; height: 1fr; }
    #status { padding: 0 2; height: 1; }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        config_path: Path,
        mount_root: Path,
        *,
        dry_run: bool = True,
        assume_yes: bool = False,
        runner_factory: type[CommandRunner] | None = None,
    ) -> None:
        super().__init__()
        self._config_path = config_path
        self._mount_root = mount_root
        self._dry_run = dry_run
        self._assume_yes = assume_yes
        if runner_factory is not None:
            inner: CommandRunner = runner_factory()
        else:
            inner = DryRunner() if dry_run else RealRunner()
        self._runner = LoggingRunner(inner=inner)
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

    def ask_confirmation(self, message: str) -> bool:
        """Block until the user answers the modal in the UI thread.

        Called from the worker thread. Uses a :class:`threading.Event`
        to bridge the async UI callback into the synchronous worker.
        """
        if self._dry_run or self._assume_yes:
            return True
        done = threading.Event()
        result: list[bool] = [False]
        modal = ConfirmModal(message=message, done=done, result=result)
        self.call_from_thread(self.push_screen, modal)
        done.wait()
        return result[0]

    @property
    def runner(self) -> LoggingRunner:
        return self._runner

    def _run_pipeline(self) -> None:
        try:
            cfg = load_config(self._config_path)
            validate_semantics(cfg)
            disk = Disk(path=DiskPath(Path(cfg.disk.path)), size_bytes=2**40)
            plan = Planner().build(
                cfg=cfg, disk=disk, mount_root=self._mount_root,
            )
            require_destructive_confirmation(
                plan,
                assume_yes=self._dry_run or self._assume_yes,
                force=False,
                prompt=self.ask_confirmation,
            )
            steps = tuple(PlannedStepExecutor(planned=s) for s in plan.steps)
            ctx = ExecutionContext(
                runner=self._runner, mount_root=self._mount_root,
            )
            Pipeline(
                steps=steps,  # type: ignore[arg-type]
                initial_state=PipelineState(),
            ).run(ctx)
            done_msg = (
                "[green]dry-run complete[/green] — press q"
                if self._dry_run
                else "[green]install complete[/green] — press q"
            )
            self.call_from_thread(self._status.update, done_msg)
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


def run(
    config_path: Path,
    mount_root: Path = DEFAULT_MOUNT_ROOT,
    *,
    dry_run: bool = True,
    assume_yes: bool = False,
) -> int:
    return TuiExecuteApp(
        config_path=config_path,
        mount_root=mount_root,
        dry_run=dry_run,
        assume_yes=assume_yes,
    ).run() or 0
