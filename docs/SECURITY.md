# getarch security model

## Command execution

* `getarch.execution.real_runner.RealRunner` is the only place that calls
  `subprocess.run`. It is invoked with `shell=False` and `argv` is always a
  list of explicit tokens. **No part of the codebase uses `shell=True`.**
* Commands needing shell-like features (heredocs for the bootloader entry,
  fstab append) are rendered as `("bash", "-c", <fixed-script>)` or
  `("sh", "-c", <fixed-script>)`. The script content is constructed at plan
  time from validated config values, never from external input.
* Every executor receives a `CommandRunner` protocol, so unit tests use a
  `FakeRunner` and never touch the host.

## Secrets

* The `getarch.domain.secret.Secret` value object's `__str__` and `__repr__`
  return `***`. Sensitive command argv and stdin (LUKS passwords, root and
  user passwords) are flagged `sensitive=True`; the runner redacts them in
  logs.
* `getarch.planning.rendering.render_json` redacts the `input` of any
  sensitive command (replaces with `***`).
* The plan rendered to text never shows secrets either — `Command.describe()`
  prints `<argv0> <redacted>` for sensitive commands.
* `RealRunner` redacts plan-input secrets out of `CommandFailedError.stderr`
  before raising.

## Destructive actions

* The planner explicitly tags `partitioning`, `encryption`, and
  `filesystems` as `destructive=True`.
* `getarch.installers.confirmation.require_destructive_confirmation` is
  invoked by the install command. It prompts via `rich.prompt.Confirm` unless
  the user passes `--yes` or `--force`. JSON mode never prompts.
* `--force` is for unattended CI runs only. It bypasses confirmation but
  never bypasses validation (syntactic, semantic, or environment).

## Configuration safety

* Pydantic schemas use `extra="forbid"` and `frozen=True`. Unknown fields
  fail validation; models are immutable after construction.
* Layered validation: syntactic (Pydantic) → semantic (cross-section rules
  in `getarch/config/semantic.py`) → environment (preflight in
  `getarch/system/preflight.py`).
* Plain-text passwords in configs are accepted but discouraged; the schema
  documents `hashed`, `secret-file`, and `prompt` modes for safer storage.

## Privileges and surface area

* getarch must run as root on the live ISO. It does not attempt to drop
  privileges or sandbox itself; the install pipeline writes to block
  devices, so root is required.
* No network calls outside of `pacman` / `pacstrap` invocations. No
  telemetry, no auto-update, no remote config fetching.
