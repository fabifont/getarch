from getarch.planning.strategies.repositories import (
    RepositoriesStrategy,
    RepositoryEntry,
)


def test_multilib_uncomments_pacman_conf() -> None:
    cmds = RepositoriesStrategy(multilib=True, extras=()).commands()
    argvs = [c.argv for c in cmds]
    assert any(a[0] == "sed" and "multilib" in a[2] for a in argvs)
    assert ("pacman", "-Sy", "--noconfirm") in argvs


def test_extras_appended_to_pacman_conf() -> None:
    cmds = RepositoriesStrategy(
        multilib=False,
        extras=(
            RepositoryEntry(name="archzfs", include="/etc/pacman.d/archzfs"),
        ),
    ).commands()
    flat = " ".join(arg for c in cmds for arg in c.argv)
    assert "archzfs" in flat
    assert "/etc/pacman.d/archzfs" in flat
    assert "pacman" in flat


def test_no_repos_emits_zero_commands() -> None:
    assert RepositoriesStrategy(multilib=False, extras=()).commands() == ()
