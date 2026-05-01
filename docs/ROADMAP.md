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
* **Why:** `EncryptionConfig.header_path` is currently rejected at the
  schema layer because no bootloader/initramfs path in getarch can
  guarantee header availability at boot.
* **Plan:** support a small "header carrier" partition (FAT) with the
  header copied in, plus a mkinitcpio/dracut hook that mounts it
  read-only before `cryptsetup open`. Re-enable the schema field once
  one of {systemd-boot, grub, uki} can render the matching cmdline
  + initramfs glue.
* **Modules:** new
  `getarch/planning/strategies/encryption_header_carrier.py`,
  bootloader cmdline tweaks, schema unblock.
* **Tests:** golden snapshots for each (fs × bootloader) combo.

### Encrypted `/home` partition
* **Why:** `LUKS2 + efi-home-root` is currently rejected because the
  planner only encrypts root.
* **Plan:** second `cryptsetup luksFormat` for the home partition, an
  `EncryptionConfig.home_password` (or shared key + key-file derivation),
  and a `crypttab` entry so `systemd-cryptsetup@home` unlocks it on
  boot.
* **Risks:** unattended unlock UX (prompt twice, or one-key-unlocks-both
  via a key-file on the unlocked root).

### `home_size_mib = null` rest-of-disk
* **Why:** semantic validator currently requires `home_size_mib` for any
  layout containing `home` because sgdisk silently skipped the
  partition. Docs originally promised "omit to use rest of disk".
* **Plan:** reverse the sgdisk allocation when `home_size_mib is None` —
  give root a fixed slice (config-defined `root_size_mib`, default
  `32_768`) and `home` gets `0` (sgdisk-speak for "rest of disk").
* **Modules:** schema, `SgdiskStrategy`, semantic validator.

### TUI execution mode
* **Why:** `getarch tui` is read-only. Wiring the install pipeline behind
  the TUI lets users watch progress and respond to confirmations
  interactively.
* **Plan:** new Textual screen subscribed to a queue that
  `LoggingRunner` produces; render commands as they run; surface
  confirmation prompts via a modal.

### Resume safety: config fingerprint
* **Why:** `--resume` currently trusts step IDs. If the config changes
  between runs, the same IDs may correspond to different commands.
* **Plan:** persist a SHA-256 of the rendered plan JSON in
  `PipelineState`. `--resume` refuses to continue when the fingerprint
  mismatches; `--resume --force-fingerprint` overrides for users who
  understand the risk.

### Plan diff against installed system
* **Why:** `getarch diff CONFIG_A CONFIG_B` compares two configs.
  Comparing a proposed config against the *last applied* state would
  catch unintended drift before re-installing.
* **Plan:** read `<mount>/var/log/getarch.state.json` (or a hashed
  version of the original config persisted alongside) and diff the
  rendered plan IDs.

### Disk wipe before partition (`disk.wipe_before`)
* **Why:** the schema field exists today (`DiskConfig.wipe_before`) but
  the planner ignores it.
* **Plan:** new `DiskWipeStep` (between `disk-busy-guard` and
  `partitioning`) running `blkdiscard -f` for SSDs, `cryptsetup erase`
  for an existing LUKS header, or `wipefs -a` as a fallback. Off by
  default; opt-in.

### Mirror reachability preflight
* **Why:** the mirrors step touches `reflector` / a static mirrorlist
  but never validates that the chosen mirrors actually serve packages.
* **Plan:** new preflight check that fetches the first mirror's
  `core/os/x86_64/core.db` HEAD and times out after 10s; warns on slow
  mirrors, refuses on unreachable.

### `getarch verify CONFIG`
* **Why:** users sometimes want to re-run preflight against an existing
  config without building/printing the plan.
* **Plan:** new CLI subcommand that calls `preflight_environment` then
  prints the report (`text` and `json` modes).

### `getarch microcode CONFIG`
* **Why:** quick way to confirm what microcode the planner will resolve
  for the current host.
* **Plan:** small subcommand: load config, read `cpu_vendor`, print
  resolved `MicrocodeKind`.

### Snapper-aware destructive guard
* **Why:** when an existing system has snapper snapshots, the install
  blast radius extends to those snapshots if the user reinstalls onto
  the same disk.
* **Plan:** new preflight that lists snapshots discovered on
  `cfg.disk.path` and surfaces them in the destructive confirmation
  text.

### Locale: multi-locale support
* **Why:** schema only accepts one `locale.locale` line.
* **Plan:** widen `locale.locale` to `list[str]`; emit one line per
  entry into `/etc/locale.gen`.

## P5 — extended features

Larger items that meaningfully widen the supported install surface.
None are required for the base installer to be useful, but each one
matches a real hardware/use case.

### Custom partition table DSL on the target disk
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

### LVM-on-LUKS layout
* **Why:** classical Linux server layout (one LUKS volume, LVM inside,
  multiple LVs).
* **Plan:** new `LvmStrategy`; schema gains `lvm` block; encryption
  becomes a single LUKS container, mkfs runs against `/dev/<vg>/<lv>`.

### ZFS root (third-party module)
* **Why:** ZFS is the most common non-mainline filesystem request.
* **Plan:** opt-in via `archzfs` extra repo; `FilesystemKind.ZFS` +
  `ZfsStrategy`. Risk: ZFS module mismatch on kernel update.

### systemd-networkd extras: VLAN, bridge, bond
* **Why:** datacentre / homelab installs need link-aggregation or VLAN
  trunks on first boot.
* **Plan:** widen `SystemdNetworkdProfile` to render `*.netdev` and
  `*.link` files in addition to `*.network`.

### WPA2-Enterprise (802.1x)
* **Why:** corporate wifi.
* **Plan:** new `WifiBootstrap.kind = "iwctl-eap"` with `username` /
  `cert_path` / `private_key_path`. PSK-only path stays.

### WireGuard pre-install bootstrap
* **Why:** boxes inside corporate VPNs only reach mirrors via
  WireGuard.
* **Plan:** new bootstrap kind that writes `/etc/wireguard/wg0.conf`,
  enables `wg-quick@wg0` *before* the runtime preflight.

### nftables ruleset rendering
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

### Container / chroot install mode
* **Why:** install into a pre-mounted directory without touching disks
  (useful for image builds, OCI layers).
* **Plan:** `firmware: "container"` skips partitioning + bootloader +
  initramfs + cleanup steps; everything else runs into a user-supplied
  `--mount-root`.

### Reproducible builds
* **Why:** zipapp + wheel should be byte-identical for the same git
  commit.
* **Plan:** set `SOURCE_DATE_EPOCH` in the release workflow; pass
  `--build-id` to shiv; verify with `diffoscope` in CI.

### AUR PKGBUILD
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
