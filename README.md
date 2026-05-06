# getarch

[![License](https://img.shields.io/github/license/fabifont/getarch?color=blue)](LICENSE)
[![Latest release](https://img.shields.io/github/v/release/fabifont/getarch)](https://github.com/fabifont/getarch/releases)
![CI](https://github.com/fabifont/getarch/actions/workflows/ci.yml/badge.svg)

`getarch` is a declarative Arch Linux base-system installer that runs from
the live ISO. You describe the target system in a JSON config; getarch
validates it, builds an explicit install plan, asks before doing anything
destructive, and runs the plan through a single `subprocess` boundary that
never uses `shell=True`.

Postinstall userland — dotfiles, desktop environments, shell setup, app
installs — is **out of scope**. That belongs to the sibling project
[`setarch`](https://github.com/fabifont/setarch) (planned).

## Status

**Alpha.** The schema is versioned (`"version": 1`); breaking changes will
bump it. See [`docs/ROADMAP.md`](docs/ROADMAP.md) for what is missing.

## What it covers today

- UEFI + GPT, plus BIOS/MBR boot
- Filesystems: ext4, btrfs (with default + custom subvolumes)
- Encryption: none, LUKS2 on root
- Bootloader: systemd-boot
- Initramfs: mkinitcpio (drop-in `/etc/mkinitcpio.conf.d/10-hooks.conf`)
- Kernels: linux, linux-lts, linux-zen, linux-hardened
- Microcode: explicit Intel/AMD or auto-detect
- Swap: none / partition / swapfile
- Optional regular users with sudo + hashed/plain/secret-file/prompt root
  authentication
- Locale, keymap, timezone, hostname, hosts, services, timers, packages

## Quick start

```bash
# On the Arch live ISO:
pacman -Sy --noconfirm python uv
uv tool install --python 3.14 getarch
getarch examples minimal-ext4 > my.json
$EDITOR my.json
getarch validate my.json
getarch plan my.json
getarch install my.json --yes
```

## CLI

| Command | Purpose |
|---|---|
| `getarch validate CONFIG` | Syntactic + semantic validation. Exits `0` on success, `2` on failure. |
| `getarch plan CONFIG` | Render the full install plan. No subprocess execution. |
| `getarch install CONFIG` | Validate + plan + confirm + execute. Honors `--dry-run`, `--yes`, `--force`, `--mount-root`. |
| `getarch schema` | Emits the v1 JSON Schema. |
| `getarch examples [NAME]` | List or print a built-in example config. |
| `getarch discover` | Inspect the live ISO environment (disks, UEFI, locales, …). |
| `getarch version` | Print version. |

Global flags: `--log-level`, `--no-color`, `--json`, `--verbose`, `--debug`.

## Configuration

See [`docs/CONFIG.md`](docs/CONFIG.md) for the full schema reference and
[`examples/`](examples/) for runnable configs:

- `examples/minimal-ext4.json` — non-encrypted ext4 + systemd-boot.
- `examples/encrypted-btrfs.json` — LUKS2 + btrfs with subvolumes.
- `examples/full.json` — every optional section exercised.

`getarch schema` emits the same schema as a machine-readable JSON Schema
document, suitable for editor completion.

## Security model

See [`docs/SECURITY.md`](docs/SECURITY.md). Summary:

- `subprocess.run` is invoked with `shell=False` and a fixed argv list.
- Sensitive command argv and stdin are flagged and redacted in logs and
  plan rendering.
- Destructive steps (partitioning, encryption, filesystem creation) are
  marked in the plan and gated behind a confirmation prompt unless
  `--yes`/`--force`.
- Plain-text passwords in configs are accepted but discouraged. Prefer
  `prompt`, `hashed`, or `secret-file` modes.

## Development

```bash
git clone https://github.com/fabifont/getarch.git
cd getarch
uv sync --all-groups
uv run pytest --cov=getarch
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
uv run pre-commit install
```

The pre-commit hook runs ruff, basedpyright, and pytest. CI mirrors that on
GitHub Actions (`.github/workflows/ci.yml`). The QEMU smoke test
(`.github/workflows/qemu.yml`) is gated to manual dispatch until the
workflow is rewired against the new wheel-based distribution.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).

## Disclaimer

`getarch` performs destructive operations (partitioning, formatting,
chroot package install). Run only against disks you intend to wipe. The
authors take no responsibility for data loss.
