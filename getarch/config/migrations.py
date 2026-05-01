"""Config migrations between schema versions.

For now ``migrate_v1_to_v2`` is identity-shaped: v2 mirrors v1 except
for the ``version`` field. As v2 grows real divergences, this is the
single place to express the upgrade rules so users can run
``getarch migrate config.json --to 2`` deterministically.
"""

from __future__ import annotations

from copy import deepcopy

from getarch.errors import SyntacticConfigError


def migrate_v1_to_v2(payload: dict[str, object]) -> dict[str, object]:
    """Return a v2-shaped dict given a v1 payload.

    Raises :class:`SyntacticConfigError` if ``payload`` is not v1.
    """
    version = payload.get("version")
    if version not in (1, "1"):
        raise SyntacticConfigError(
            f"migrate_v1_to_v2: input has version {version!r}, want 1",
        )
    out: dict[str, object] = deepcopy(payload)
    out["version"] = 2
    return out


# Map of (from_version, to_version) → migrator. Adding a new bump
# means registering a new pair (and rerouting through intermediates if
# the user wants to skip multiple major versions).
MIGRATORS = {
    (1, 2): migrate_v1_to_v2,
}


def migrate(payload: dict[str, object], *, to_version: int) -> dict[str, object]:
    """Run the registered migrators in sequence to reach ``to_version``."""
    current_raw = payload.get("version")
    if not isinstance(current_raw, (int, str)):
        raise SyntacticConfigError(
            f"migrate: payload has invalid version {current_raw!r}",
        )
    try:
        current = int(current_raw)
    except (TypeError, ValueError) as exc:
        raise SyntacticConfigError(
            f"migrate: payload has non-numeric version {current_raw!r}",
        ) from exc
    if current == to_version:
        return deepcopy(payload)
    if current > to_version:
        raise SyntacticConfigError(
            f"migrate: cannot downgrade from {current} to {to_version}",
        )
    out = payload
    while current < to_version:
        try:
            step = MIGRATORS[(current, current + 1)]
        except KeyError as exc:
            raise SyntacticConfigError(
                f"migrate: no path from v{current} to v{current + 1}",
            ) from exc
        out = step(out)
        current += 1
    return out
