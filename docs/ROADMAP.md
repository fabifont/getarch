# getarch roadmap

The MVP that ships with v2.0.0a0 covers UEFI + GPT, ext4/btrfs, systemd-boot,
mkinitcpio, optional LUKS2, optional swap, optional regular users, and the
common locale/timezone/hostname/services/microcode/kernel choices.

This roadmap captures everything else needed for a complete, opinionated
Arch Linux base-system installer. Items are grouped by priority. Anything
related to userland (dotfiles, DEs, app installs) is **out of scope** —
that is `setarch`'s job.

## P0 — required for a safe MVP

These exist or are stubbed today; they must work end-to-end before tagging
v2.0.0.

### Strict environment preflight
* **Status:** done. `IdentityProvider`, `IsoProvider`, `NetworkProvider` and
  the extended `BlockDeviceProvider`/`PacmanProvider` are wired into
  `preflight_environment`; `--skip-environment-preflight` covers the
  minimal-image false-positive risk.

### Destructive confirmation
* **Status:** done. `getarch/installers/confirmation.py` honours `--yes`/
  `--force` and falls back to `rich.prompt.Confirm`.

### Dry-run pipeline
* **Status:** done. `DryRunner` records intent without IO; `--dry-run`
  exercises the full pipeline.

### Plan rendering JSON output redacts secrets
* **Status:** done. `render_json` substitutes `***` for sensitive command
  inputs.

### Disk safety
* **Status:** done. `LsblkBlockDevices.target_disk_busy` walks the lsblk tree
  for live mountpoints. `preflight_environment` refuses mounted target
  disks during the static check; `require_destructive_confirmation` prints
  the mountpoints in the confirmation summary when present;
  `DiskBusyGuardStep` repeats the lsblk-fresh check immediately before the
  first destructive step and cannot be bypassed by
  `--skip-environment-preflight`, `--yes`, or `--force`.

## P1 — required for a complete base installer

### Microcode auto-detect → planner injection
* **Status:** done. `MicrocodeKind.from_cpu_vendor` resolves `auto` against
  `EnvironmentReport.cpu_vendor`; planner injects the package and
  bootloader initrd line.

### Mirror configuration plumbing
* **Status:** done. `ReflectorStrategy` and `StaticMirrorlistStrategy` emit
  a single `mirrors` step before pacstrap; preflight refuses a missing
  static mirrorlist; semantic validator rejects empty `reflector_args`.

### Swapfile creation
* **Status:** done. `SwapfileStrategy` runs `mkdir`, optional `chattr +C`
  for btrfs, `fallocate`, `chmod 600`, `mkswap`, `swapon`. `genfstab`
  records the entry from `/proc/swaps`.

### Separate `/home` partition
* **Status:** done. `Ext4Strategy` and `BtrfsStrategy` create and mount a
  separate `/home` filesystem when the layout includes `home`; the btrfs
  `@home` subvolume is dropped in that case so `/home` lives on the
  standalone filesystem.

### Regular user creation with sudo + hashed passwords
* **Status:** done.

### Hostname/hosts/locale/timezone validation against discovery
* **Status:** done — `system/preflight.py` checks every value.

## P2 — quality and flexibility improvements

### YAML / TOML config support
* **Status:** done. `config/loader.py` branches on file extension and uses
  `yaml.safe_load`/`tomllib.loads`/`json.loads`.

### Additional bootloaders (GRUB, UKI/systemd-stub)
* **Status:** done. `GrubStrategy` and `UkiStrategy` plus
  `build_bootloader_strategy` dispatch on `cfg.bootloader.kind`.

### Additional filesystems (xfs, f2fs)
* **Status:** done. `_SimpleMkfsStrategy` covers xfs/f2fs alongside ext4
  inside the existing factory.

### dracut initramfs
* **Status:** done. `DracutStrategy` writes
  `/etc/dracut.conf.d/10-getarch.conf` and runs
  `dracut --regenerate-all --force`. `build_initramfs_strategy` dispatches.

### TPM2 / FIDO2 LUKS unlock
* **Status:** done. `LuksStrategy` honours
  `EncryptionConfig.tpm2_unlock`/`fido2_unlock` and emits
  `systemd-cryptenroll --tpm2-device=auto`/`--fido2-device=auto` after
  open.

### Detached LUKS header
* **Status:** done. `EncryptionConfig.header_path` propagates to
  `cryptsetup` calls and bootloader cmdlines; preflight refuses missing
  headers.

### `zram` swap
* **Status:** done. `ZramStrategy` writes
  `/etc/systemd/zram-generator.conf` and the planner installs
  `zram-generator` automatically.

### Custom mountpoints
* **Status:** done. `mountpoints` accepts
  `{partition_label, mountpoint, filesystem, mount_options, create}` and
  the new `custom-mountpoints` planner step formats and mounts each
  entry. Reserved labels and managed mountpoints are rejected.

### Network: full systemd-networkd / iwd stacks
* **Status:** done. `systemd_networkd` profiles are rendered to
  `/etc/systemd/network/*.network` and `iwd_networks` PSKs are written to
  `/var/lib/iwd/*.psk` (mode 0600, sensitive logging).

### Audit log
* **Status:** done. `LoggingRunner` records every command (with sensitive
  redaction) and the install command writes the JSON log to
  `<mount>/var/log/getarch.log` before cleanup.

### Robust unmount / cleanup retries
* **Status:** done. Cleanup runs `umount -R || umount -lR` so a busy
  target falls back to lazy unmount.

### PyPI publishing
* **Status:** done. `release.yml` builds with `uv build` and publishes to
  PyPI through a Trusted Publisher; setup is documented in
  `docs/RELEASING.md`.

### Single-file zipapp distribution
* **Status:** done. The release workflow builds `dist/getarch.pyz` via
  `shiv` and attaches it to the GitHub Release.

### QEMU smoke test
* **Status:** done. `.github/workflows/qemu.yml` boots the upstream Arch
  ISO under QEMU/KVM on a self-hosted runner for every push to
  `main`/`dev` and same-repo PR (fork PRs are skipped via a `should-run`
  gate so untrusted code never reaches the self-hosted runner). The
  matrix covers ext4/btrfs/xfs/f2fs × systemd-boot/grub/uki (12 cells,
  `fail-fast: false`). `test_resources/qemu_smoke.py` drives the install
  via the QEMU monitor + virtfs share, then restarts QEMU disk-only
  (no ISO, no virtfs) and asserts the installed system reaches a getty
  on serial.
* **Runner requirements:** label `kvm`, KVM access, `qemu-system-x86_64`,
  `qemu-img`, `OVMF` firmware (`/usr/share/edk2/x64/OVMF_*.4m.fd`),
  Python 3.14, and `uv`.

## P3 — advanced / future

### Interactive TUI mode
* **Status:** done (MVP). `getarch tui CONFIG` opens a Textual-based
  read-only viewer of the config + rendered plan. Optional dependency:
  `pip install 'getarch[tui]'`. Execution-from-TUI is intentionally not
  wired yet.

### Plan diffs
* **Status:** done. `getarch diff CONFIG_A CONFIG_B` emits a unified
  diff of the plans built from each config (step IDs + per-step argv).

### Step-by-step resume after failure
* **Status:** done. `Pipeline` writes
  `<mount>/var/log/getarch.state.json` after every successful step (and
  on failure with `last_error`). `getarch install --resume` skips
  already-completed step IDs. Caveat: resume cannot unwind partial
  filesystem state from a half-finished destructive step — the user is
  responsible for cleanup before resuming.

### BIOS/MBR boot
* **Status:** done. `firmware: "bios"` switches partitioning to
  `SgdiskBiosStrategy` (1MiB BIOS-boot partition, no ESP) and the
  bootloader to `GrubBiosStrategy` (`grub-install --target=i386-pc`).
  Semantic validator refuses any non-grub bootloader on BIOS.

### Non-x86_64 architectures
* **Status:** deferred indefinitely — needs aarch64/RISC-V hardware to
  validate. Schema would grow `arch` field when there is a real test
  surface.

### Btrfs snapshot integration with snapper
* **Status:** done. `filesystem.snapper=true` (btrfs only) installs the
  `snapper` package, creates the `root` config in chroot, and enables
  `snapper-timeline.timer` + `snapper-cleanup.timer`.

### `multilib` / extra repo enablement
* **Status:** done. `repositories.multilib=true` uncomments the
  `[multilib]` block in `/etc/pacman.conf` on the live ISO before
  pacstrap; `repositories.extra` appends arbitrary repo blocks. The
  strategy follows up with `pacman -Sy --noconfirm` so pacstrap sees
  the new repos.

### Headless network bootstrap
* **Status:** done. `network.bootstrap` accepts an `iwctl` or `dhcp`
  payload that fires before the runtime preflight so the ISO has
  internet for the keyring populate.

### Hypothesis-driven planner property tests
* **Status:** done. `tests/property/test_planner_invariants.py`
  generates random valid combos across fs / encryption / swap /
  bootloader / initramfs / timeout and asserts: unique step IDs,
  destructive-phase invariants, non-empty argv for every command, and
  monotonic phase order.
