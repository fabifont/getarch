# getarch roadmap

`getarch` is an opinionated Arch Linux base-system installer. This document
captures what is implemented today, what is deferred, and what is out of
scope. For the per-field config reference see
[`docs/CONFIG.md`](CONFIG.md).

Anything userland (dotfiles, DEs, app installs) belongs to `setarch`, not
`getarch`.

## Implemented

### Safety and integrity
* Strict environment preflight: identity (root), Arch ISO check, network
  reachability, pacman keyring initialization, mount-busy detection,
  static-mirrorlist presence and reachability. Bypass via
  `--skip-environment-preflight`.
* Destructive confirmation gate (`require_destructive_confirmation`):
  surfaces target disk, layout summary, existing partition filesystems,
  active mountpoints. Honours `--yes` / `--force`.
* Always-on `DiskBusyGuardStep` re-checks mount state immediately before
  the first destructive step; cannot be bypassed by
  `--skip-environment-preflight`, `--yes`, or `--force`.
* `DiskWipeStep` runs `wipefs -a -f` + `blkdiscard -f` before
  partitioning when `disk.wipe_before=true`.
* Snapper-aware destructive guard enumerates `(partition, fstype)` pairs
  on the target disk and warns explicitly when btrfs is detected.
* Audit log: every command recorded by `LoggingRunner` with sensitive
  redaction; written to `<mount>/var/log/getarch.log` before cleanup.
  Stable JSON Lines schema (`schema_version=1`) + optional HMAC-SHA256
  trailer (`--audit-hmac-key`).
* Dry-run pipeline (`--dry-run`) and plan rendering with secret
  redaction in JSON output.
* Pipeline state + `--resume` after failure: writes
  `<mount>/var/log/getarch.state.json` after every successful step,
  filters non-resumable runtime guards on resume, and refuses fingerprint
  mismatch unless `--force-fingerprint`.
* `getarch diff CONFIG --against-installed` reads the persisted plan
  from a previous install and renders a unified diff against the new
  plan.

### Filesystems
* ext4, btrfs (default + custom subvolumes), xfs, f2fs.
* btrfs snapper integration (`snapper-timeline.timer`,
  `snapper-cleanup.timer`); planner drops `@snapshots` so snapper owns
  `/.snapshots` itself.
* Swap: `none`, partition, `swapfile` (btrfs-aware: `chattr +C`), `zram`.
* Custom mountpoints (`mountpoints` schema): read-only attach for
  pre-formatted partitions on disks *other than* the install target;
  preflight rejects same-disk partlabels.

### Encryption
* LUKS2 on root with passphrase, TPM2 unlock, or FIDO2 unlock
  (`systemd-cryptenroll --tpm2-device=auto` / `--fido2-device=auto`).
* Detached LUKS header on a carrier partition (`efi-luksheader-root` /
  `efi-swap-luksheader-root` layouts emit a 16 MiB `cryptheader` GPT
  partition; `header_path` threads through `cryptsetup --header` and
  the bootloader cmdline (`rd.luks.options=header=…`)).
* Encrypted `/home`: `home_kind="shared-key"` (reuse root password) or
  `"separate-key"` (require `home_password`); auto-unlock via
  `/etc/cryptkey/home.key` written inside the unlocked root.
* Encrypted swap: random-key dm-crypt swap with crypttab entry,
  unlocked by `systemd-cryptsetup@swapcrypt.service` on boot.

### Bootloaders, initramfs, kernel
* systemd-boot, GRUB, UKI/systemd-stub on UEFI; GRUB on BIOS/MBR
  (`firmware: "bios"` switches partitioning to `SgdiskBiosStrategy` and
  the bootloader to `GrubBiosStrategy`).
* mkinitcpio (drop-in `/etc/mkinitcpio.conf.d/10-hooks.conf`) and
  dracut (`/etc/dracut.conf.d/10-getarch.conf`).
* Microcode: explicit `intel`/`amd` or `auto` (auto reads
  `/proc/cpuinfo` via `IsoEnvironment`; planner injects the package and
  the bootloader initrd entry).
* Kernels: `linux`, `linux-lts`, `linux-zen`, `linux-hardened`.
* Optional kdump (`kdump.enable`): planner installs `kexec-tools` and
  sets `crashkernel=` on the bootloader cmdline.
* Hardware quirks DB (`getarch/quirks/`) keyed by PCI/USB IDs;
  preflight surfaces matches; planner appends modules + kernel cmdline
  opts to both initramfs generators (mkinitcpio uses `MODULES=()`,
  dracut uses `force_drivers+=`). Unknown quirk IDs fail closed.

### Disk layouts
* Predefined layouts: `efi-root`, `efi-swap-root`, `efi-root-home`,
  `efi-swap-root-home`, plus the encrypted-header carrier variants
  (`efi-luksheader-root`, `efi-swap-luksheader-root`).
* `partitioning.root_size_mib` lets `/home` take rest-of-disk
  (mutually exclusive with `home_size_mib`).
* `partitioning.custom: list[PartitionSpec]` payload for arbitrary
  partition tables on the target disk with role mapping.
* LVM-on-LUKS: one LUKS container with VG inside; per-LV mkfs/mount;
  planner auto-adds `lvm2` to packages.
* Container/chroot install mode (`firmware: "container"`) skips
  partitioning + bootloader + initramfs + cleanup; everything else runs
  into a user-supplied `--mount-root`.

### Networking
* `systemd_networkd` profiles render `*.network`, `*.netdev`, `*.link`
  files (covers VLAN, bridge, bond).
* `iwd_networks` writes `/var/lib/iwd/<ssid>.psk` (mode 0600).
* WPA2-Enterprise (`WifiBootstrap.kind="iwctl-eap"`) with `username`,
  `cert_path`, `private_key_path`, optional `ca_cert_path`.
* WireGuard pre-install bootstrap writes `/etc/wireguard/wg0.conf` and
  enables `wg-quick@wg0` *before* the runtime preflight.
* `network.bootstrap` (iwctl/dhcp) brings interfaces up before the
  keyring populate; PSKs land on stdin, never argv.
* `nftables` ruleset rendering to `/etc/nftables.conf` + service enable.

### Repositories and packages
* `repositories.multilib=true` uncomments `[multilib]` in
  `/etc/pacman.conf` on the live ISO before pacstrap.
* `repositories.extra` appends arbitrary repo blocks; the strategy
  follows up with `pacman -Sy --noconfirm`.
* Multi-locale support (`locale.locale: list[str]` or single string);
  validator requires `locale.lang` to be a prefix of at least one entry.

### CLI
* Subcommands: `validate`, `plan`, `install`, `schema`, `examples`,
  `discover`, `version`, `diff`, `verify`, `microcode`, `migrate`,
  `help error`, `tui`.
* Flags: `--dry-run`, `--yes`, `--force`, `--resume`,
  `--force-fingerprint`, `--skip-environment-preflight`,
  `--skip-runtime-preflight`, `--mount-root`, `--json`,
  `--log-sink {syslog://…,journald}`, `--log-format {text,json}`,
  `--audit-hmac-key`.
* Stable error codes (`getarch help error <code>`) backed by per-code
  Markdown docs under `docs/errors/`.
* Schema v2 migration: `getarch migrate` rewrites v1 configs;
  `config/loader.py` routes by `version`.

### TUI
* `getarch tui CONFIG` — Textual-based read-only viewer of config +
  rendered plan (optional dependency: `pip install 'getarch[tui]'`).
* `getarch tui --execute` — runs the install pipeline behind a worker
  thread, tails the audit buffer into a scrollable log view, with modal
  destructive confirmations and password prompt callbacks. Shares
  `build_install_pipeline_steps` with the CLI install command so
  surfaces cannot drift on safety guarantees.

### Distribution
* PyPI publishing via Trusted Publisher (`release.yml`).
* Single-file zipapp (`shiv` → `dist/getarch.pyz`) attached to releases.
* AUR PKGBUILD (thin wrapper).
* Reproducible builds via `SOURCE_DATE_EPOCH`.

### Observability
* Structured logging: stdlib `logging` with optional `--log-sink syslog`
  / `journald` and `--log-format text|json`.
* Discovery cache at `~/.cache/getarch/discovery.json` (60 s TTL).
* Audit log schema documented in [`docs/audit-schema.md`](audit-schema.md).

### Testing
* Unit suite (494 tests at last count) with coverage reporting;
  basedpyright, `ruff check`, `ruff format --check` in CI.
* Hypothesis property tests
  (`tests/property/test_planner_invariants.py`) over fs / encryption /
  swap / bootloader / initramfs combos.
* QEMU smoke matrix on a self-hosted KVM runner: 4 filesystems
  (ext4/btrfs/xfs/f2fs) × 3 bootloaders (systemd-boot/grub/uki) with a
  post-install reboot check. Fork-PR isolation gate prevents untrusted
  code from reaching the runner.

### Docs
* [`docs/TUTORIAL.md`](TUTORIAL.md) — first-install walkthrough.
* [`docs/HARDENING.md`](HARDENING.md) — post-boot lockdown guide.
* [`docs/CONFIG.md`](CONFIG.md) — per-field schema reference.
* [`docs/SECURITY.md`](SECURITY.md) — security model and guarantees.
* [`docs/RELEASING.md`](RELEASING.md) — release process.
* [`docs/audit-schema.md`](audit-schema.md) — audit log schema.
* [`docs/errors/`](errors/) — per-error help pages.

## Pending

These are deliberately deferred or need hardware / effort that has not
materialised yet.

* **Non-x86_64 architectures.** Schema would grow an `arch` field;
  needs aarch64 / RISC-V hardware to validate.
* **Multi-disk btrfs raid (raid1 / raid10).** `disks: list[DiskConfig]`
  payload (deprecate `disk`), btrfs strategy spans them
  (`mkfs.btrfs -m raid1 -d raid1 dev1 dev2`); bootloader install needs
  per-disk ESP handling.
* **ZFS root.** Opt-in via the `archzfs` extra repo;
  `FilesystemKind.ZFS` + `ZfsStrategy`. Risk: ZFS module mismatch on
  kernel update.
* **Btrfs snapshot before destructive ops.** When reinstalling onto a
  btrfs disk that already has a pre-getarch root subvolume, snapshot it
  before partitioning so the install can be rolled back.
* **systemd-homed for regular users.** Schema toggle
  `users.regular[].kind="homed"`; planner runs `homectl create` instead
  of `useradd`.

## Out of scope

These belong to `setarch` (userland orchestration), to other tools, or
to a future product entirely.

* Dotfiles, desktop environments, app installs.
* Internationalised CLI messages.
* GUI installer.
* Full AUR helper bootstrap (the `repositories.multilib` /
  `repositories.extra` plumbing is the limit).
* Backup orchestration / restore from backup.
* Cloud provider bootstrappers (AWS / GCP / Azure user-data).
