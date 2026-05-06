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
| `partitioning` | object | yes | — | GPT layout (predefined, `lvm`, or `custom`). |
| `filesystem` | object | yes | — | Root filesystem. |
| `encryption` | object | yes | — | None or LUKS2 (with optional TPM2/FIDO2/header/`/home`/swap). |
| `swap` | object | yes | — | None / partition / swapfile / zram. |
| `kernel` | object | yes | — | Kernel package selection. |
| `microcode` | object | yes | — | Auto / intel / amd / none. |
| `bootloader` | object | yes | — | `systemd-boot`, `grub`, or `uki`. |
| `initramfs` | object | yes | — | `mkinitcpio` or `dracut`. |
| `locale` | object | yes | — | lang/locale/keymap/timezone. |
| `network` | object | yes | — | Hostname + network backend (incl. networkd VLAN/bridge/bond, iwd PSK, WPA2-Enterprise, WireGuard, headless bootstrap, nftables). |
| `packages` | list[str] | yes | — | Pacstrap package list (must contain the kernel package). |
| `services` | object | yes | — | systemd units to enable. |
| `mirrors` | object | yes | — | Mirror strategy. |
| `users` | object | yes | — | Root authentication + optional regular users. |
| `mountpoints` | list | no | `[]` | Extra partlabel→mountpoint pairs (read-only attach on disks other than the install target). |
| `repositories` | object | no | `{}` | multilib + extra pacman repos. |
| `firmware` | string | no | `"uefi"` | `"uefi"`, `"bios"`, or `"container"`. |
| `kdump` | object | no | `{enable: false}` | Kernel crash-dump (kexec + crashkernel cmdline). |
| `quirks` | object | no | `{enable: []}` | Hardware quirks the user opts into. |
| `reboot` | bool | no | `false` | Reboot after the install? |

## `disk`

```json
{ "path": "/dev/sda", "wipe_before": false }
```

* `path` must match `/dev/...` and must point to a *whole* disk (not a partition).
* `wipe_before` (default `false`): when `true`, a `disk-wipe` step runs
  `wipefs -a -f` and best-effort `blkdiscard -f` on the disk *after*
  every non-destructive prerequisite has succeeded and *before* the
  partitioning step. Useful when the disk has lingering signatures from
  prior installs that confuse `sgdisk`.

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
`efi-swap-home-root`, `efi-luksheader-root`, or `efi-swap-luksheader-root`
(the last two emit a 16 MiB `cryptheader` GPT carrier partition for a
detached LUKS header).

`swap_size_mib` is required when the layout includes swap.
`home_size_mib` may be omitted to let `/home` use the rest of the disk
(root takes a slice). To pin root and let home grow, set
`root_size_mib` instead — the two are mutually exclusive.

For non-trivial layouts, `partitioning` accepts two alternative payloads
(both validated at semantic time):

* `lvm: {vg_name, volumes: [...]}` — LVM-on-LUKS. The whole partition
  becomes one LUKS container; LVM volumes inside hold per-mountpoint
  filesystems. Planner auto-adds `lvm2` to packages.
* `custom: list[PartitionSpec]` — fully arbitrary GPT layout on the
  install target. Each entry has `label`, `size_mib` (or `null` for
  rest-of-disk), `typecode`, optional `role` ("efi"/"swap"/"root"/"home"),
  optional `filesystem`, optional `mountpoint`, optional `mount_options`.
  Planner builds the sgdisk script and wires the per-role strategies.

### Separate `/home`

When `layout` is `efi-home-root` or `efi-swap-home-root`, the planner
creates a second filesystem of the same kind as root on the home partition
and mounts it at `/home`. For btrfs roots, the default `@home` subvolume is
omitted because `/home` lives on the standalone filesystem.

## `filesystem`

Supported kinds: `ext4`, `btrfs`, `xfs`, `f2fs`. ext4/xfs/f2fs share a
single command graph (`mkfs`, mount, optional `/home` mount). Only `btrfs`
declares subvolumes.

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

Optional unattended-unlock fields (LUKS2 only):

* `tpm2_unlock: true` — runs `systemd-cryptenroll --tpm2-device=auto` so
  the system unlocks at boot when the TPM2 measurement matches.
* `fido2_unlock: true` — runs `systemd-cryptenroll --fido2-device=auto` so
  a connected FIDO2 token can unlock the volume.
* `header_path: "/dev/disk/by-partlabel/cryptheader"` — detached LUKS
  header. Requires a partitioning layout that includes a `cryptheader`
  carrier (e.g. `efi-luksheader-root`); semantic validation enforces
  this. Every `cryptsetup` invocation gets `--header=<header_path>`
  and the bootloader cmdline gains `rd.luks.options=header=...`.

Encrypted `/home` (when the layout includes a separate home partition):

* `home_kind: "shared-key"` — formats `/home` as a second LUKS2
  container reusing the root password.
* `home_kind: "separate-key"` — formats `/home` as an independent LUKS2
  container; requires `home_password`.
* `home_keyfile: true` — opt-in auto-unlock: an additional 4 KiB random
  key under `/etc/cryptkey/home.key` (mode 0600, written *inside* the
  unlocked root) is enrolled into the home LUKS volume; the crypttab
  entry points at it so `/home` unlocks automatically at boot without a
  second passphrase prompt. Requires `home_kind != "none"`.

Encrypted swap (LUKS2 root + a `swap` partition would otherwise leave
swap plaintext, leaking anything paged out of RAM):

* `swap.encrypt: true` (when `swap.kind="partition"`) — emits a
  `crypttab` entry that opens `/dev/<swap>` as a random-key plain
  dm-crypt mapper at boot; `mkswap`/`swapon` target the mapper, so the
  partition is re-keyed on every boot and never holds usable plaintext.
  `systemd-cryptsetup@swapcrypt.service` reads from crypttab on each
  boot.

> Storing a plaintext password in the JSON is unsafe. The roadmap covers
> prompt-only and secret-file modes that avoid this.

## `swap`

* `{"kind": "none"}` — no swap.
* `{"kind": "partition", "size_mib": 4096}` — needs a layout that includes
  swap.
* `{"kind": "swapfile", "size_mib": 4096}` — created during install at
  `/swap/swapfile`. On btrfs, CoW is disabled on `/swap` before the file is
  allocated. `genfstab` picks up the swapon entry from `/proc/swaps`.
* `{"kind": "zram", "zram_size_mib": 4096}` — installs `zram-generator`
  and writes `/etc/systemd/zram-generator.conf` so `/dev/zram0` mounts on
  first boot. Omit `zram_size_mib` for `min(ram, 8192)`.

## `kernel`

`{"kind": "linux"}` (default), `linux-lts`, `linux-zen`, `linux-hardened`.
The chosen kernel package **must** appear in `packages`.

## `microcode`

`auto` (default), `intel`, `amd`, `none`. Under `auto`, the planner reads
`cpu_vendor` from the environment preflight (`/proc/cpuinfo`) and appends
`intel-ucode` or `amd-ucode` accordingly; unknown vendors fall back to
`none`. Explicit `intel`/`amd` overrides the discovered vendor and
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

Supported kinds: `systemd-boot` (default), `grub`, `uki`.

* **systemd-boot** — `bootctl install` runs from the live ISO with
  `--esp-path=<mount_root>/boot` because `arch-chroot` runs in a pid
  namespace and refuses to write UEFI variables.
* **grub** — runs `grub-install --target=x86_64-efi
  --efi-directory=/boot --bootloader-id=<entry_id>` and renders
  `/etc/default/grub` then `grub-mkconfig`. Enables `cryptodisk` when
  encryption is on.
* **uki** — writes a mkinitcpio preset that emits a Unified Kernel Image
  to `/boot/EFI/Linux/<entry_id>-<kernel>.efi` and chains it through
  `bootctl install` (systemd-boot picks UKIs up automatically).

## `initramfs`

```json
{
  "generator": "mkinitcpio",
  "hooks": ["base", "udev", "autodetect", "modconf", "block", "filesystems", "fsck"]
}
```

Generators:

* **mkinitcpio** (default) — the hooks list is written to
  `/etc/mkinitcpio.conf.d/10-hooks.conf` (the Arch-recommended drop-in
  location); `mkinitcpio -p <kernel>` runs in chroot.
* **dracut** — writes `/etc/dracut.conf.d/10-getarch.conf` (with
  `crypt` added when LUKS is on) and runs `dracut --regenerate-all
  --force` in chroot. `hooks` is ignored.

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

Optional declarative configuration for non-NetworkManager backends:

```json
{
  "hostname": "workstation",
  "backend": "systemd-networkd",
  "systemd_networkd": [
    {
      "name": "20-wired",
      "match": {"Name": "en*"},
      "network": {"DHCP": "yes", "DNS": ["1.1.1.1", "8.8.8.8"]}
    }
  ]
}
```

```json
{
  "hostname": "laptop",
  "backend": "iwd",
  "iwd_networks": [
    {"ssid": "MyWifi", "psk": "secret"}
  ]
}
```

For `systemd-networkd`, each profile is rendered to
`/etc/systemd/network/<name>.network`. For `iwd`, each network is written
to `/var/lib/iwd/<ssid>.psk` (mode 0600, content `[Security]\nPassphrase
= <psk>`).

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
* `{"strategy": "reflector", "reflector_args": ["--country", "Italy",
  "--protocol", "https", "--sort", "rate"]}` — runs `reflector --save
  /etc/pacman.d/mirrorlist <args>` before pacstrap. `reflector_args` must
  not be empty (semantic validator refuses empty lists).
* `{"strategy": "static", "static_path": "/path/to/mirrorlist"}` — copies
  the file into `/etc/pacman.d/mirrorlist` on the live ISO before
  pacstrap. The file must exist on the live ISO (preflight refuses if
  missing).

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

## `repositories`

```json
{
  "repositories": {
    "multilib": true,
    "extra": [
      {"name": "archzfs", "include": "/etc/pacman.d/archzfs-mirrorlist"}
    ]
  }
}
```

`multilib=true` uncomments the `[multilib]` block in
`/etc/pacman.conf` on the live ISO before pacstrap. Each entry in
`extra` appends a `[name]\nInclude = include\n` block. After every
mutation the strategy runs `pacman -Sy --noconfirm` so pacstrap sees
the new repos.

## `firmware`

`"uefi"` (default), `"bios"`, or `"container"`.

* **uefi** — default Arch installation flow on UEFI hardware.
* **bios** — switches the partitioning strategy to a GPT layout with a
  1MiB BIOS-boot partition (no ESP) and the bootloader strategy to GRUB
  (`grub-install --target=i386-pc <disk>`). `bootloader.kind` must be
  `"grub"` for BIOS — the semantic validator refuses any other choice.
* **container** — install into a pre-mounted directory passed via
  `--mount-root` (no disks touched). The pipeline skips disk-busy
  guard, runtime network bootstrap, runtime preflight, partitioning,
  bootloader install, initramfs regeneration, and cleanup; everything
  else (pacstrap, system config, users, services) still runs into the
  chroot. The chroot caller is responsible for the keyring and network.

## Filesystem snapshots (snapper)

```json
{
  "filesystem": {"kind": "btrfs", "label": "system", "snapper": true}
}
```

Adds the `snapper` package, runs `snapper -c root create-config /` in
the chroot, and enables `snapper-timeline.timer` +
`snapper-cleanup.timer`. Only valid on `kind="btrfs"` (rejected
otherwise).

## Headless network bootstrap (`network.bootstrap`)

Pre-pacstrap network setup so the runtime preflight can reach the
internet on a freshly booted ISO without manual `iwctl` / `dhcpcd`
typing. Two payload shapes:

```json
{
  "network": {
    "bootstrap": {
      "kind": "iwctl",
      "device": "wlan0",
      "ssid": "MyWifi",
      "psk": "hunter2"
    }
  }
}
```

```json
{
  "network": {
    "bootstrap": {"kind": "dhcp", "device": "enp0s3"}
  }
}
```

The PSK is marked sensitive so the audit log redacts it.

## `mountpoints`

Mount existing partitions by partlabel under the new system. The
planner does **not** format these — pre-create the filesystem yourself
before running getarch.

```json
{
  "mountpoints": [
    {
      "partition_label": "data",
      "mountpoint": "/srv",
      "mount_options": ["noatime"]
    }
  ]
}
```

* `partition_label` must match `^[a-zA-Z0-9_.-]+$` and must resolve
  (via `/dev/disk/by-partlabel/<label>`) to a partition on a disk
  *other than* `disk.path`. Preflight refuses same-disk partlabels
  because the partitioning step zaps the target disk's GPT, leaving
  any reference unsafe to attach.
* `mountpoint` must start with `/`. Reserved mountpoints (`/`,
  `/boot`, `/home`) and reserved partition labels (`EFI`, `system`,
  `cryptsystem`, `swap`, `home`, `cryptheader`) are rejected by the
  semantic validator.
* `mount_options` — optional list passed straight through to `mount -o`.

For partitions on the install target itself, declare them in
`partitioning.custom` (which formats and mounts in one go).

## `kdump`

Kernel crash-dump (kdump) configuration. When enabled, the planner
adds `crashkernel=<value>` to the bootloader cmdline and enables
`kdump.service` so kexec captures a vmcore on panic.

```json
{ "kdump": { "enable": true, "crashkernel": "256M,high" } }
```

* `enable` (default `false`) — opt-in toggle.
* `crashkernel` (default `"256M,high"`) — must match
  `^[0-9]+[KkMmGg](,[a-z]+)?$`. Passed verbatim to the bootloader
  cmdline.

Requires a bootloader strategy that lets us mutate the cmdline
(`systemd-boot` or `grub`); UKI is rejected because the cmdline is
baked into the EFI image.

## `quirks`

Hardware quirks the user opts into. The planner walks
`getarch/quirks/*.yaml` and applies any quirk whose `id` is listed
here: contributed kernel modules land in the mkinitcpio `MODULES=()`
line (or dracut `force_drivers+=`); contributed cmdline params get
appended to the bootloader cmdline. Preflight surfaces detected
quirks that are *not* enabled as a warning so users learn about
applicable fixes.

```json
{ "quirks": { "enable": ["thinkpad-x1c11", "intel-iwlwifi-be"] } }
```

Unknown quirk IDs are rejected fail-closed by the planner.

## `reboot`

`true` adds a final `reboot` step. Default `false`.

## Other commands

* `getarch validate CONFIG` — schema + semantic validation only.
* `getarch plan CONFIG` — render the plan (text or `--json`) without
  executing it.
* `getarch schema` — emit the Pydantic-generated JSON Schema for the
  current config version.
* `getarch examples [NAME]` — list example names or print a bundled
  example (e.g. `minimal-ext4`, `encrypted-btrfs`, `full`).
* `getarch discover` — summarise the current ISO environment (disks,
  UEFI, vendor, counts).
* `getarch verify CONFIG` — re-run preflight checks against the host
  without building or executing the plan.
* `getarch microcode CONFIG` — print the resolved `MicrocodeKind` for
  this host given the config (helps debug `microcode.kind="auto"`).
* `getarch migrate CONFIG` — rewrite a v1 config under the v2 schema
  routing.
* `getarch help error <code>` — open the per-error help page for a
  stable error code (e.g. `E101`).
* `getarch diff CONFIG_A CONFIG_B` — unified plan diff between two
  configs.
* `getarch diff CONFIG --against-installed` — diff the new plan
  against the plan persisted at `<mount>/var/log/getarch.state.json`
  from the previous install.
* `getarch tui CONFIG` — Textual TUI for browsing a config + plan
  read-only. Requires `getarch[tui]` (installs `textual`).
* `getarch tui CONFIG --execute` — live install screen with modal
  destructive confirmations and password prompt callbacks. Shares the
  install pipeline assembly with `getarch install` so safety guarantees
  cannot drift between surfaces.

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
* `--resume` — pick up after a previous failed install by skipping every
  step recorded in `<mount>/var/log/getarch.state.json`. Without
  `--resume`, an existing state file aborts the install (so a stale state
  file doesn't silently change behaviour). Caveat: resume works for steps
  that were idempotent or fully completed; partial filesystem state from
  a half-finished partitioning step is your problem to clean up.
* `--force-fingerprint` — allow `--resume` to continue when the
  persisted plan fingerprint differs from the current plan. Off by
  default; without it, fingerprint mismatch refuses to resume so a
  changed config never silently splices into an old run.
* `--audit-hmac-key <env-var-or-path>` — sign the audit log with an
  HMAC-SHA256 trailer. Accepts an env-var name (read from process
  env) or a path to a key file.
* `--log-sink <syslog://host:port|journald>` — fan logs out to a
  remote sink. Default is the stdlib `logging` console handler.
* `--log-format {text,json}` — switch the in-process log records to
  JSON Lines (helpful when piping into a log shipper).
* `--json` — switch the CLI's user-facing output to JSON Lines (plan
  output, validation results, etc.). Independent of `--log-format`.
* `--no-color` — disable rich terminal colors.
* `--log-level {DEBUG,INFO,WARNING,ERROR}` — root log level.
* `--verbose` / `--debug` — convenience shortcuts for `INFO`/`DEBUG`.
