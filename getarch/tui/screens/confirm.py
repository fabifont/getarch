"""Modal confirmation screen for destructive plan execution.

Used by :class:`getarch.tui.screens.execute.TuiExecuteApp` to gate the
real-runner pipeline behind a yes/no prompt that wraps
:func:`getarch.installers.confirmation.require_destructive_confirmation`.

The worker thread fires the modal via ``app.call_from_thread``, then
blocks on a :class:`threading.Event` while the user presses ``y`` or
``n``; the result is written into a single-element list (``[bool]``)
that the worker reads after the event flips.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, ClassVar, override

from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult


class ConfirmModal(ModalScreen[bool]):
    """Yes/no modal for the install pipeline.

    Pushes a vertical box with the prompt text and two buttons. ``y``
    accepts, ``n``/``escape`` declines. The ``done`` event is set after
    either button is pressed (or a hotkey fires) so the worker thread
    can resume.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y,Y,enter", "accept", "Yes"),
        Binding("n,N,escape", "decline", "No"),
    ]

    CSS = """
    ConfirmModal {
        align: center middle;
    }
    #confirm-box {
        width: 70%;
        max-width: 100;
        background: $panel;
        padding: 1 2;
        border: round $accent;
    }
    #confirm-message {
        padding-bottom: 1;
    }
    #confirm-buttons {
        height: 3;
    }
    """

    def __init__(
        self,
        *,
        message: str,
        done: threading.Event,
        result: list[bool],
    ) -> None:
        super().__init__()
        self._message = message
        self._done = done
        self._result = result

    @override
    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self._message, id="confirm-message"),
            Vertical(
                Button("Yes (y)", id="confirm-yes", variant="error"),
                Button("No (n)", id="confirm-no", variant="default"),
                id="confirm-buttons",
            ),
            id="confirm-box",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        answer = event.button.id == "confirm-yes"
        self.record_answer(answer=answer)
        self.dismiss(answer)

    def action_accept(self) -> None:
        self.record_answer(answer=True)
        self.dismiss(True)

    def action_decline(self) -> None:
        self.record_answer(answer=False)
        self.dismiss(False)

    def record_answer(self, *, answer: bool) -> None:
        """Pure state mutation: write the answer + flip the event.

        Split out so tests can verify the worker-thread bridge without
        spinning up a Textual app context for ``dismiss``.
        """
        self._result[0] = answer
        self._done.set()
