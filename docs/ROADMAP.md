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
* **Status:** plumbing in domain layer; refused at schema time. The
  `LuksStrategy` honours `header_path` for `cryptsetup` invocations, but
  the schema currently rejects `EncryptionConfig.header_path` because
  systemd-boot/UKI cannot reach a header that lives off-disk at boot.
  Tracked in P4 (boot-time header access).

### `zram` swap
* **Status:** done. `ZramStrategy` writes
  `/etc/systemd/zram-generator.conf` and the planner installs
  `zram-generator` automatically.

### Custom mountpoints
* **Status:** done (read-only attach). `mountpoints` accepts
  `{partition_label, mountpoint, mount_options}` and the
  `custom-mountpoints` planner step `mkdir`s + mounts each entry.
  **Does not format** — the partition must already exist with a
  filesystem on a disk *other than* `cfg.disk.path`; preflight refuses
  same-disk partlabels. Format-and-mount on the target disk is tracked
  in P5 (custom partition layout DSL).

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

## P4 — finish what P0–P3 left partial

These are concrete follow-ups surfaced by the P0–P3 implementation and
adversarial reviews. Each one has a clear contract; none requires new
hardware.

### Boot-time access to detached LUKS header
* **Status:** done (carrier partition). New `efi-luksheader-root` /
  `efi-swap-luksheader-root` layouts emit a 16 MiB `cryptheader` GPT
  partition. `EncryptionConfig.header_path` (typically
  `/dev/disk/by-partlabel/cryptheader`) threads through `cryptsetup
  --header` calls and the bootloader cmdline (`rd.luks.options=header=…`).
  Semantic validator binds the field to the carrier layout.

### Encrypted `/home` partition
* **Status:** done. `EncryptionConfig.home_kind` accepts `"shared-key"`
  (reuse root password) or `"separate-key"` (require
  `home_password`). The planner emits a new `encryption-home` step that
  formats and opens `/dev/mapper/homecrypt`; the filesystem strategy
  uses the mapper device for home; a `crypttab-home` step writes the
  entry into `/etc/crypttab` with the UUID resolved at execution time.

### `home_size_mib = null` rest-of-disk
* **Status:** done. New `partitioning.root_size_mib` lets the user fix
  the root slice; `home` then takes the rest of the disk (sgdisk's `0`
  end token). Semantic validator rejects setting both at once.

### TUI execution mode
* **Status:** done (MVP). `getarch tui --execute` opens a new Textual
  screen that runs the install pipeline behind a worker thread and
  tails the `LoggingRunner` buffer into a scrollable log view. Real
  execution is gated on dry-run for now; modal confirmations land
  later (see P5/P6 for follow-ups).

### Resume safety: config fingerprint
* **Status:** done. `PipelineState.plan_fingerprint` (SHA-256 of the
  rendered plan JSON) persists alongside the completed step list.
  `--resume` refuses to continue when the fingerprint differs from the
  current plan unless `--force-fingerprint` is also passed.
  `PipelineState.schema_version` bumps to 2; v1 state files are still
  readable.

### Plan diff against installed system
* **Status:** done. `getarch diff CONFIG --against-installed` reads the
  plan JSON persisted in `PipelineState.plan_blob` from the previous
  install and renders a unified diff against the new plan.

### Disk wipe before partition (`disk.wipe_before`)
* **Status:** done. New `DiskWipeStep` is inserted between
  `disk-busy-guard` and the runtime preflight when
  `disk.wipe_before=true`. Runs `wipefs -a -f` (fails the step on
  failure) and `blkdiscard -f` (best-effort, HDDs return non-zero).

### Mirror reachability preflight
* **Status:** done. When `mirrors.strategy="static"` and the file
  exists, preflight fetches `core/os/x86_64/core.db` against the first
  uncommented mirror with a 10s HEAD timeout. Refuses on URL errors,
  socket errors, timeouts, or HTTP 4xx/5xx.

### `getarch verify CONFIG`
* **Status:** done. New CLI subcommand re-runs `preflight_environment`
  and prints the report. JSON mode (`--json`) emits the full
  dataclass; default text mode prints a compact summary.

### `getarch microcode CONFIG`
* **Status:** done. Loads the config, reads `cpu_vendor` via
  `IsoEnvironment`, prints the resolved `MicrocodeKind` and the
  package it would add.

### Snapper-aware destructive guard
* **Status:** done. `BlockDeviceProvider.target_disk_filesystems`
  enumerates all `(partition, fstype)` pairs on the target disk via
  `lsblk -J -o NAME,FSTYPE`. The destructive confirmation prompt
  surfaces them and explicitly warns when btrfs is detected (snapshots
  / subvolumes will be wiped).

### Locale: multi-locale support
* **Status:** done. `locale.locale` accepts `list[str]` (or a single
  string for back-compat). Each entry produces one `/etc/locale.gen`
  line. Semantic validator requires `locale.lang` to be a prefix of at
  least one entry.

## P5 — extended features

Larger items that meaningfully widen the supported install surface.
None are required for the base installer to be useful, but each one
matches a real hardware/use case.

**Status:** 12/16 implemented and adversarially reviewed (commit b5c8d42).
The four deferred items remain open: multi-disk btrfs raid, ZFS root,
btrfs pre-snapshot, systemd-homed.

### Custom partition table DSL on the target disk *(done — a46bb9d)*
* **Why:** the current `partitioning.layout` enum only covers four
  predefined layouts. Power users want arbitrary partitions on the
  install target (e.g., separate `/var`, `/srv`, ZFS data partition).
* **Plan:** new `partitioning.custom: list[PartitionSpec]` payload —
  each entry has `label`, `size_mib`, `typecode`. Mutually exclusive
  with `layout`. Planner builds the sgdisk script.

### Multi-disk: btrfs `raid1` / `raid10`
* **Why:** btrfs supports built-in RAID; getarch only handles one disk.
* **Plan:** `disks: list[DiskConfig]` (deprecate `disk`), btrfs strategy
  spans them via `mkfs.btrfs -m raid1 -d raid1 dev1 dev2`. Bootloader
  install needs to write to the EFI partition on each disk.

### LVM-on-LUKS layout *(done — 09e0409)*
* **Why:** classical Linux server layout (one LUKS volume, LVM inside,
  multiple LVs).
* **Plan:** new `LvmStrategy`; schema gains `lvm` block; encryption
  becomes a single LUKS container, mkfs runs against `/dev/<vg>/<lv>`.

### ZFS root (third-party module)
* **Why:** ZFS is the most common non-mainline filesystem request.
* **Plan:** opt-in via `archzfs` extra repo; `FilesystemKind.ZFS` +
  `ZfsStrategy`. Risk: ZFS module mismatch on kernel update.

### systemd-networkd extras: VLAN, bridge, bond *(done — d0a6c7f)*
* **Why:** datacentre / homelab installs need link-aggregation or VLAN
  trunks on first boot.
* **Plan:** widen `SystemdNetworkdProfile` to render `*.netdev` and
  `*.link` files in addition to `*.network`.

### WPA2-Enterprise (802.1x) *(done — c9e6037, ca_cert_path b5c8d42)*
* **Why:** corporate wifi.
* **Plan:** new `WifiBootstrap.kind = "iwctl-eap"` with `username` /
  `cert_path` / `private_key_path` / `ca_cert_path`. PSK-only path stays.

### WireGuard pre-install bootstrap *(done — c9e6037)*
* **Why:** boxes inside corporate VPNs only reach mirrors via
  WireGuard.
* **Plan:** new bootstrap kind that writes `/etc/wireguard/wg0.conf`,
  enables `wg-quick@wg0` *before* the runtime preflight.

### Encrypted swap *(done — 3668b01)*
* **Why:** `LUKS2` root + a `swap` partition leaves the swap partition
  plaintext, so anything paged out of RAM (passwords, keys) can leak.
* **Plan:** new `encryption-swap` planner step that runs
  `cryptsetup open --type plain --key-file /dev/urandom <swap>
  swapcrypt`, with a corresponding `crypttab` entry. mkswap/swapon
  target the mapper. Survives reboot via systemd's
  `systemd-cryptsetup@swapcrypt.service` reading from crypttab.

### Auto-unlock for encrypted /home *(done — 375de93)*
* **Why:** `home_kind="shared-key"` currently prompts the user for the
  passphrase twice (root + home) because crypttab uses `none` for the
  key source.
* **Plan:** generate a 4 KiB random key under `/etc/cryptkey/home.key`
  with mode `0600` *inside the unlocked root*; rewrite the crypttab
  entry to point at it. systemd unlocks `/home` automatically after
  pivot.

### TUI execution: confirmation modals + real runner *(done — 64332b8)*
* **Why:** `getarch tui --execute` runs the dry-run pipeline. Live
  install needs interactive confirmations and password prompts.
* **Plan:** Textual modal screen wrapping the destructive confirmation
  prompt; password prompts piped to the runner via a thread-safe
  callback.

### nftables ruleset rendering *(done — 37eac66)*
* **Why:** users want a baseline firewall on first boot.
* **Plan:** schema field for a list of rules; planner writes
  `/etc/nftables.conf` and enables `nftables.service`.

### Btrfs snapshot before destructive ops
* **Why:** existing systems with snapshots could be rolled back if the
  install fails; we don't take one.
* **Plan:** when reinstalling onto a btrfs disk that has an existing
  pre-getarch root subvolume, snapshot it before partitioning. Hard
  case; optional.

### systemd-homed for regular users
* **Why:** modern user account management with portable home dirs.
* **Plan:** schema toggle `users.regular[].kind = "homed"`; planner
  runs `homectl create` instead of `useradd`.

### Container / chroot install mode *(done — d226faf, b5c8d42)*
* **Why:** install into a pre-mounted directory without touching disks
  (useful for image builds, OCI layers).
* **Plan:** `firmware: "container"` skips partitioning + bootloader +
  initramfs + cleanup steps; everything else runs into a user-supplied
  `--mount-root`.

### Reproducible builds *(done — ed08c96)*
* **Why:** zipapp + wheel should be byte-identical for the same git
  commit.
* **Plan:** set `SOURCE_DATE_EPOCH` in the release workflow; pass
  `--build-id` to shiv; verify by re-build + `cmp` in CI.

### AUR PKGBUILD *(done — ed08c96)*
* **Why:** make `getarch` installable from the AUR for Arch users who
  don't want to pull from PyPI.
* **Plan:** publish a thin PKGBUILD that wraps `pip install getarch`
  inside a `python` package, or builds the zipapp.

## P6 — observability, tooling, docs

Cross-cutting work that doesn't add features but makes the installer
easier to operate, debug, and extend.

### Structured audit log: stable JSON Lines schema + signature
* **Why:** the current audit log is ad-hoc JSON Lines. Downstream
  consumers (compliance, SIEM) want a versioned schema and an HMAC.
* **Plan:** publish `docs/audit-schema.md`; `LoggingRunner` includes
  a `schema_version` field; optional `--audit-hmac-key` CLI flag
  appends an HMAC-SHA256 line per record.

### Structured logging with optional remote sink
* **Why:** for CI/lab installs, having per-step logs streamed to
  syslog/journald-export simplifies debugging.
* **Plan:** swap stdlib `logging` for `structlog`; add
  `--log-sink syslog://...` / `--log-sink journald` option.

### Discovery cache
* **Why:** `getarch discover` re-runs lsblk/localectl/timedatectl on
  every call. A short-lived cache would speed up `validate` + `plan` +
  `install` invocations on the same ISO boot.
* **Plan:** `~/.cache/getarch/discovery.json` with a TTL (60s default).

### Hardware quirks database
* **Why:** specific NIC/SATA/CPU combos need extra mkinitcpio modules
  or kernel parameters that getarch could opt-in automatically.
* **Plan:** small YAML at `getarch/quirks/` keyed by PCI/USB IDs;
  preflight surfaces matches to the user; planner appends the
  corresponding modules/cmdline.

### Crash dump / kdump
* **Why:** kernel panics during install or first-boot are otherwise
  lost.
* **Plan:** opt-in `kdump.enable` schema flag; planner installs
  `kdump-tools`-equivalent and sets `crashkernel=` on the bootloader
  cmdline.

### Better error messages with suggested fixes
* **Why:** `EnvironmentError` strings are useful but rarely actionable.
* **Plan:** introduce `code: str` on `GetarchError` subclasses; CLI
  renders a one-liner + a `getarch help error <code>` link to docs.

### Schema v2 migration path
* **Why:** v1 already accumulates deprecated combinations. A v2 cycle
  would let us tighten defaults without breaking existing configs.
* **Plan:** stub `getarch/config/schema/v2.py`; `config/loader.py`
  detects `version: 2` and routes accordingly; an in-tree
  `migrate_v1_to_v2` helper rewrites old configs.

### Tutorial + post-install hardening guide
* **Why:** the existing docs cover schema fields but not the
  end-to-end "first install" path or what to do once the system boots.
* **Plan:** `docs/TUTORIAL.md` (full walkthrough) and
  `docs/HARDENING.md` (sshd, firewall, sudoers, automatic updates).

## Out of scope

These are deliberately outside `getarch`. They belong to `setarch`
(userland orchestration), to other tools, or to a future product
entirely.

* Dotfiles, desktop environments, app installs.
* Internationalised CLI messages.
* GUI installer.
* Full AUR helper bootstrap (the multilib/extra-repos plumbing in P3
  is the limit).
* Backup orchestration / restore from backup.
* Cloud provider bootstrappers (AWS/GCP/Azure user-data).
