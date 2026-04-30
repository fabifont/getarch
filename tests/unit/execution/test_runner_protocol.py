from getarch.execution.command import Command
from getarch.execution.result import CommandResult
from getarch.execution.runner import CommandRunner


class _Stub:
    def __init__(self) -> None:
        self.seen: list[Command] = []

    def run(self, command: Command, *, chroot_path: str = "/mnt") -> CommandResult:
        del chroot_path
        self.seen.append(command)
        return CommandResult(command=command, returncode=0, stdout="", stderr="")


def test_runner_protocol_is_satisfied() -> None:
    stub: CommandRunner = _Stub()
    res = stub.run(Command(argv=("true",)))
    assert res.ok
