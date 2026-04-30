# getarch configuration reference

`getarch` reads a single JSON file describing the install. The schema is
versioned (`"version": 1`) and validated by Pydantic v2. Run `uv run getarch
schema` to dump the machine-readable JSON Schema.

This document describes every field in v1.

## Top level

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `version` | int | yes | — | Must be `1`. |
| `disk` | object | yes | — | Target disk. |
| `partitioning` | object | yes | — | GPT layout. |
| `filesystem` | object | yes | — | Root filesystem. |
| `encryption` | object | yes | — | None or LUKS2. |
| `swap` | object | yes | — | None / partition / swapfile. |
| `kernel` | object | yes | — | Kernel package selection. |
| `microcode` | object | yes | — | Auto / intel / amd / none. |
| `bootloader` | object | yes | — | Currently `systemd-boot`. |
| `initramfs` | object | yes | — | Currently `mkinitcpio`. |
| `locale` | object | yes | — | lang/locale/keymap/timezone. |
| `network` | object | yes | — | Hostname + network backend. |
| `packages` | list[str] | yes | — | Pacstrap package list (must contain the kernel package). |
| `services` | object | yes | — | systemd units to enable. |
| `mirrors` | object | yes | — | Mirror strategy. |
| `users` | object | yes | — | Root authentication + optional regular users. |
| `reboot` | bool | no | `false` | Reboot after the install? |

## `disk`

```json
{ "path": "/dev/sda", "wipe_before": false }
```

* `path` must match `/dev/...` and must point to a *whole* disk (not a partition).
* `wipe_before`: reserved; the partitioning step always zaps the GPT.

## `partitioning`

```json
{
  "layout": "efi-swap-home-root",
  "efi_size_mib": 1024,
  "swap_size_mib": 4096,
  "home_size_mib": 8192
}
```

`layout` is one of `efi-root`, `efi-swap-root`, `efi-home-root`,
`efi-swap-home-root`. `swap_size_mib` is required when the layout includes
swap. `home_size_mib` may be omitted to let `/home` use the rest of the disk
(root takes a slice).

## `filesystem`

ext4:

```json
{ "kind": "ext4", "label": "system" }
```

btrfs:

```json
{
  "kind": "btrfs",
  "label": "system",
  "mount_options": ["compress=zstd", "noatime"],
  "subvolumes": [
    {"name": "@", "mountpoint": "/"},
    {"name": "@home", "mountpoint": "/home"},
    {"name": "@snapshots", "mountpoint": "/.snapshots"}
  ]
}
```

If `subvolumes` is omitted for btrfs, the defaults shown above are used.
ext4 must not declare subvolumes.

## `encryption`

```json
{ "kind": "none" }
```

```json
{ "kind": "luks2", "password": "CHANGE_ME", "mapper_name": "system" }
```

When `kind` is `luks2`, `password` is required. The initramfs hooks **must**
include either `encrypt` (busybox) or `sd-encrypt` (systemd) — semantic
validation enforces this. The mapper name defaults to `system`.

> Storing a plaintext password in the JSON is unsafe. The roadmap covers
> prompt-only and secret-file modes that avoid this.

## `swap`

* `{"kind": "none"}` — no swap.
* `{"kind": "partition", "size_mib": 4096}` — needs a layout that includes swap.
* `{"kind": "swapfile", "size_mib": 4096}` — created during install.

## `kernel`

`{"kind": "linux"}` (default), `linux-lts`, `linux-zen`, `linux-hardened`.
The chosen kernel package **must** appear in `packages`.

## `microcode`

`auto` (default — runtime detection), `intel`, `amd`, `none`. Explicit
selection appends `intel-ucode` or `amd-ucode` to the pacstrap list and
references the matching `*.img` from the bootloader entry.

## `bootloader`

```json
{
  "kind": "systemd-boot",
  "entry_id": "arch",
  "timeout_seconds": 3,
  "extra_kernel_params": ["quiet"]
}
```

`bootctl install` runs from the live ISO with `--esp-path=<mount_root>/boot`
because `arch-chroot` runs in a pid namespace and refuses to write UEFI
variables.

## `initramfs`

```json
{
  "generator": "mkinitcpio",
  "hooks": ["base", "udev", "autodetect", "modconf", "block", "filesystems", "fsck"]
}
```

The hooks list is written to `/etc/mkinitcpio.conf.d/10-hooks.conf` (the
Arch-recommended drop-in location); `mkinitcpio -p <kernel>` runs in chroot.

## `locale`

```json
{
  "lang": "en_US.UTF-8",
  "locale": "en_US.UTF-8 UTF-8",
  "keymap": "us",
  "timezone": "Europe/Rome"
}
```

`lang` must be a prefix of `locale`. The locale and keymap must exist on the
ISO (validated against `/usr/share/i18n/SUPPORTED` and `localectl
list-keymaps`). Timezone is validated against `timedatectl list-timezones`.

## `network`

```json
{ "hostname": "workstation", "backend": "networkmanager", "extra_packages": [] }
```

Backends: `networkmanager` (default — the planner appends `networkmanager` to
packages automatically), `systemd-networkd`, `iwd`.

## `packages`

A non-empty list of pacstrap package names. Must include the chosen kernel
package (`linux`, `linux-lts`, etc.) and may include any other Arch repo
package.

## `services`

```json
{ "enable": ["NetworkManager", "sshd"], "timers": ["fstrim.timer"] }
```

Both lists are passed to `systemctl enable` in chroot.

## `mirrors`

* `{"strategy": "keep"}` (default) — leave the live ISO mirrorlist alone.
* `{"strategy": "reflector", "reflector_args": ["--country", "Italy"]}` —
  run reflector. *(Plumbing in roadmap.)*
* `{"strategy": "static", "static_path": "/path/to/mirrorlist"}` —
  copy a static mirrorlist into the target. *(Plumbing in roadmap.)*

## `users`

```json
{
  "root": {"kind": "prompt"},
  "regular": [
    {"username": "alice", "password": "CHANGE_ME", "groups": ["wheel"], "sudo": true}
  ]
}
```

Root authentication kinds:

* `prompt` — getarch prompts for the password during install (default).
* `plain` — `password` field; **do not commit configs with plaintext passwords**.
* `hashed` — `hashed` field with the output of `openssl passwd -6`.
* `secret-file` — `secret_file` path to a file containing the password.

Regular users may declare `password` (plain), `hashed_password` (preferred),
`groups`, `shell`, `sudo`, `create_home`.

## `reboot`

`true` adds a final `reboot` step. Default `false`.

## Install command flags

* `--dry-run` — render plan and execute via `DryRunner` (no IO).
* `--yes` / `-y` — skip the destructive-confirmation prompt.
* `--force` — skip the destructive-confirmation prompt (alias of `--yes` for
  scripted automation; the user has explicitly opted out of the gate).
* `--mount-root <path>` — override the install target mount root (default
  `/mnt`).
* `--skip-runtime-preflight` — skip the in-pipeline runtime preflight step
  (NTP sync, keyring populate). Default off.
* `--skip-environment-preflight` — skip the *environment* preflight that
  asserts root, Arch ISO, UEFI, internet, pacman keyring, locale support,
  and pacman package availability. Default off. Useful on minimal images
  where one of these checks produces a false positive.

  Important: a separate **disk-busy guard** runs unconditionally before the
  first destructive step (when `--dry-run` is not set). It refuses to proceed
  if the target disk has any mounted partitions. This guard cannot be
  bypassed by `--skip-environment-preflight`, `--yes`, or `--force` — the
  whole point is to refresh the mount-state check immediately before
  destructive commands run.
