# Tutorial — first install with getarch

This walkthrough takes you from "downloaded the Arch ISO" to "boot
into a freshly-installed Arch system" in about ten minutes. It targets
a UEFI laptop with one disk to wipe.

## Before you start

* USB stick (1 GiB+) for the ISO.
* The disk you intend to install on (e.g. `/dev/nvme0n1`,
  `/dev/sda`). **It will be wiped.** Back up first.
* A second machine (or your phone) with this page open.

## 1. Download + boot the Arch ISO

Grab the latest ISO from <https://archlinux.org/download/> and verify
its signature. Flash it onto a USB stick:

```bash
sudo dd if=archlinux-2026.05.01-x86_64.iso of=/dev/sdX bs=4M conv=fsync status=progress
```

Boot from the USB. You'll land at a Zsh prompt as `root`.

## 2. Get online

If you're on Ethernet, DHCP runs automatically. For wifi:

```bash
iwctl
[iwd]# station wlan0 connect "MyWifi"
[iwd]# quit
ping -c 1 archlinux.org
```

For WPA2-Enterprise (`iwctl-eap`) or WireGuard, set up a getarch
config bootstrap (see `docs/CONFIG.md`).

## 3. Install getarch

Either pull the zipapp from a GitHub Release:

```bash
curl -fsSLo /usr/local/bin/getarch.pyz \
  https://github.com/fabifont/getarch/releases/latest/download/getarch.pyz
chmod +x /usr/local/bin/getarch.pyz
ln -s /usr/local/bin/getarch.pyz /usr/local/bin/getarch
```

…or install from PyPI (Python 3.14+):

```bash
pacman -Sy --noconfirm python python-pip
pip install --break-system-packages getarch
```

## 4. Pick an example to start from

```bash
getarch examples encrypted-btrfs > /tmp/cfg.json
```

Open `/tmp/cfg.json` in `vim` and edit:

* `disk.path` → the disk you want to wipe (`/dev/nvme0n1`, etc.).
* `network.hostname` → your machine name.
* `users.regular[0].username` / `password`.
* `encryption.password` → your LUKS passphrase. **Use a long
  passphrase you can type at every boot.**
* `locale` → match your keyboard + region.

Validate before doing anything destructive:

```bash
getarch validate /tmp/cfg.json
```

Render the plan to see exactly what will run:

```bash
getarch plan /tmp/cfg.json
```

You can re-render with `--json` to feed the steps into a diff tool.

## 5. Run the install

```bash
getarch install /tmp/cfg.json
```

You'll get one confirmation prompt before any destructive operation
fires. Type `y` only after re-checking the disk path.

The pipeline runs in phases:

1. **Pre-disk** — mirror selection, repository config, runtime
   preflight (timedatectl, pacman keyring).
2. **Disk** — partition, LUKS format + open, filesystem creation,
   mount under `/mnt`.
3. **System** — pacstrap, fstab, crypttab, network config, nftables,
   initramfs, bootloader.
4. **Finalisation** — services, users, snapper (if enabled), cleanup.

A failure at any step leaves the disk in a recoverable state. The
audit log lands at `/mnt/var/log/getarch.log`; resume with:

```bash
getarch install /tmp/cfg.json --resume
```

## 6. Reboot

```bash
umount -R /mnt
reboot
```

Remove the USB. The system boots into the LUKS passphrase prompt;
enter it, and you land at the `tty1` login.

## 7. First-boot tasks

```bash
# Update the system (the install pulled the keyring at install time;
# a fresh sync is still good hygiene).
sudo pacman -Syu

# Now follow docs/HARDENING.md to lock down sshd, firewall, sudoers,
# and automatic updates.
```

## What just happened

You went from a blank disk to a bootable, fully-encrypted Arch
install with one config file. Every command the installer ran was
recorded in `/var/log/getarch.log`; pair the file with
`docs/audit-schema.md` to verify the run end-to-end.
