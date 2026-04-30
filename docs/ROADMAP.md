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
* **Status:** partial — explicit `intel`/`amd` works. `auto` falls through
  to "no microcode".
* **Plan:** in `Planner._microcode`, inspect `IsoEnvironment.cpu_vendor()`
  when `cfg.microcode.kind == "auto"` and append the right `*-ucode`
  package + bootloader initrd.
* **Modules:** `getarch/planning/planner.py`, `getarch/system/environment.py`.
* **Tests:** fixture cpuinfo files (Intel, AMD, none).
* **Risks:** missing ucode silently leaves the system without microcode patches.

### Mirror configuration plumbing
* **Status:** schema only. `reflector` and `static` strategies are accepted
  but produce no commands.
* **Plan:** new `mirrors` step in the planner that runs `reflector` (with
  validated args) or `cp` of a static mirrorlist into `<mount>/etc/pacman.d/
  mirrorlist` *before* pacstrap.
* **Modules:** `getarch/planning/planner.py`, possibly
  `getarch/installers/mirrors.py`.
* **Tests:** golden snapshot for each strategy.

### Swapfile creation
* **Status:** schema only.
* **Plan:** new step (after `mounting`, before `packages`) that runs
  `dd`/`fallocate`, `chmod 600`, `mkswap`, `swapon`, then appends an fstab
  entry. For btrfs, set `chattr +C` on the directory holding the swapfile.
* **Modules:** `getarch/planning/planner.py`.
* **Tests:** golden snapshot for swapfile vs swap partition.

### Separate `/home` partition
* **Status:** schema layouts include `efi-home-root` and
  `efi-swap-home-root`. `SgdiskStrategy` already emits the partition.
  Filesystem creation and mount need to wire the second partition into
  `Ext4Strategy` / `BtrfsStrategy`.
* **Modules:** `getarch/planning/strategies/filesystem.py`,
  `getarch/planning/planner.py`.
* **Tests:** layout matrix in planner tests.

### Regular user creation with sudo + hashed passwords
* **Status:** done.

### Hostname/hosts/locale/timezone validation against discovery
* **Status:** done — `system/preflight.py` checks every value.

## P2 — quality and flexibility improvements

### YAML / TOML config support
* **Plan:** branch in `config/loader.py` on the file extension; reuse the
  same Pydantic model.
* **Modules:** `getarch/config/loader.py`.
* **Tests:** round-trip from each format.

### Additional bootloaders (GRUB, UKI/systemd-stub)
* **Plan:** new strategy classes per kind; `Planner._bootloader_step`
  factory dispatches on `cfg.bootloader.kind`. Schema enum widens.
* **Modules:** `getarch/planning/strategies/bootloader.py`, schema.
* **Risks:** GRUB requires a different ESP layout (`grub-install
  --bootloader-id`) and BIOS dual-boot considerations.

### Additional filesystems (xfs, f2fs)
* **Plan:** new strategy modules; schema enum widening.
* **Risks:** f2fs needs specific mkinitcpio modules.

### dracut initramfs
* **Plan:** new initramfs strategy; schema enum.
* **Risks:** dracut uses different LUKS hooks and a different config
  location (`/etc/dracut.conf.d/`).

### TPM2 / FIDO2 LUKS unlock
* **Plan:** new encryption strategy that runs `systemd-cryptenroll
  --tpm2-device=auto` or `--fido2-device=auto` after LUKS open.
* **Risks:** hardware-dependent; hard to QEMU-test reliably.

### Detached LUKS header
* **Plan:** schema field for header path; planner emits `cryptsetup
  luksFormat --header=...` and `rd.luks.options=header=...`.
* **Risks:** complicates recovery.

### `zram` swap
* **Plan:** new step that installs `zram-generator` and writes
  `/etc/systemd/zram-generator.conf`.

### Custom mountpoints
* **Plan:** schema field for arbitrary `(partition, mountpoint)` pairs;
  planner expands mount commands.

### Network: full systemd-networkd / iwd stacks
* **Plan:** planner writes `*.network` and `*.link` files for
  systemd-networkd; copies `/var/lib/iwd/<ssid>.psk` for iwd.

### Audit log
* **Plan:** wrap the runner with a `LoggingRunner` that appends every
  rendered command to `<mount>/var/log/getarch.log` after install.

### Robust unmount / cleanup retries
* **Plan:** `umount -R` falls back to `umount -l` on failure with a clear
  warning.

### PyPI publishing
* **Plan:** add `pypa/gh-action-pypi-publish` to `release.yml` gated on a
  trusted publisher.

### Single-file zipapp distribution
* **Plan:** `uv build` + `shiv` or `zipapp` + bundled venv for a portable
  binary. Replaces what PyInstaller did historically.

## P3 — advanced / future

### Interactive TUI mode
* Different command (`getarch tui`), shares the domain core. Probably
  Textual.

### Plan diffs
* Compare two plans (e.g. proposed vs previous run) for review.

### Step-by-step resume after failure
* Persist execution state to a file; resume the pipeline after the failed
  step.
* **Risks:** state recovery is hard for partial mounts/encryption.

### BIOS/MBR boot
* New partitioning + bootloader branches. Significant rework of EFI
  assumptions.
* **Depends on:** P2 bootloader factory.

### Non-x86_64 architectures
* aarch64 / RISC-V. Requires hardware testing.

### Btrfs snapshot integration with snapper
* Configure snapper after install for automatic root snapshots.

### `multilib` / extra repo enablement
* Schema field; planner uncomments lines in `pacman.conf`.

### Headless network bootstrap
* `iwctl`/`nmcli` declarative pre-install network setup so the live ISO
  can come up unattended.

### Hypothesis-driven planner property tests
* Generate random valid configs and assert planner invariants
  (no duplicate steps, destructive set is exactly `{partitioning,
  encryption, filesystems}`, etc.).
