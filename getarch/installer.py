# This file is part of getarch
#
# getarch is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# getarch is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with getarch.  If not, see <https://www.gnu.org/licenses/>.

import logging as logger
import subprocess  # nosec

from .command import Command
from .data import SystemData, UserData


class Installer:
    def __init__(self, test: bool = False) -> None:
        self.system_data = SystemData()
        self.test = test

    def install(self, user_data: UserData) -> None:
        self.user_data = user_data
        if self.user_data.clean_disk:
            self.clean_disk()
        self.format_disk()
        self.setup_luks()
        self.setup_btrfs()
        self.setup_boot()
        self.install_base_system()
        self.setup_system()
        self.setup_initramfs()
        self.enable_services()
        self.enable_timers()
        self.setup_bootloader()
        self.setup_root_password()
        if self.test:
            return
        self.umount_and_reboot()

    def init(self) -> None:
        self.check_efi()
        self.sync_time()
        self.update_repos()
        self.setup_keyring()

    def check_efi(self) -> None:
        try:
            Command.run("ls /sys/firmware/efi/efivars")
        except subprocess.CalledProcessError as e:
            logger.exception("Not booted in EFI mode")
            raise e

    def sync_time(self) -> None:
        Command.run("timedatectl set-ntp true")

    def update_repos(self) -> None:
        Command.run("pacman -Sy")

    def setup_keyring(self) -> None:
        Command.run("pacman -S --noconfirm archlinux-keyring")
        Command.run("yes Y | pacman-key --init")
        Command.run("yes Y | pacman-key --populate")

    def clean_disk(self) -> None:
        Command.run(
            f"cryptsetup open --type plain {self.user_data.disk} disk_to_wipe --key-file /dev/urandom",  # noqa: B950
            cmd_input="YES\n",
        )

        try:
            Command.run("lsblk | grep disk_to_wipe || false")
        except subprocess.CalledProcessError as e:
            logger.error("A problem occurred while mounting the disk to wipe")
            logger.exception(e)
            raise e

        Command.run("dd if=/dev/zero of=/dev/mapper/disk_to_wipe bs=1M", check=False)
        Command.run("cryptsetup close disk_to_wipe")

    def format_disk(self) -> None:
        Command.run(f"sgdisk --zap-all {self.user_data.disk}")
        Command.run(
            (
                "sgdisk --clear"
                " --new=1:0:+512MiB --typecode=1:ef00 --change-name=1:EFI"
                " --new=2:0:0 --typecode=2:8300 --change-name=2:cryptsystem"
                f" {self.user_data.disk}"
            )
        )
        Command.run("mkfs.fat -F32 -n EFI /dev/disk/by-partlabel/EFI", check=False)

    def setup_luks(self) -> None:
        Command.run(
            "cryptsetup luksFormat --batch-mode /dev/disk/by-partlabel/cryptsystem",
            cmd_input=f"{self.user_data.luks_password}\n",
        )
        Command.run(
            "cryptsetup open /dev/disk/by-partlabel/cryptsystem system",
            cmd_input=f"{self.user_data.luks_password}\n",
        )

    def setup_btrfs(self) -> None:
        subvol_mountpoint_mapper = {
            "@": "",
            "@home": "/home",
            "@snapshots": "/.snapshots",
        }

        Command.run("mkfs.btrfs --label system /dev/mapper/system")
        Command.run("mount -t btrfs LABEL=system /mnt")

        for sv in subvol_mountpoint_mapper.keys():
            Command.run(f"btrfs sub create /mnt/{sv}")

        Command.run("umount -R /mnt")

        options = (
            "defaults,x-mount.mkdir,noatime,nodiratime,compress=zstd,space_cache=v2,ssd"
        )
        for sv, mp in subvol_mountpoint_mapper.items():
            Command.run(
                f"mount -t btrfs -o {options},subvol={sv} LABEL=system /mnt{mp}"
            )

    def setup_boot(self) -> None:
        Command.run("mkdir /mnt/boot")
        Command.run("mount LABEL=EFI /mnt/boot")

    def install_base_system(self) -> None:
        if self.system_data.ucode:
            self.user_data.packages.append(self.system_data.ucode)
        Command.run(f"pacstrap /mnt {' '.join(self.user_data.packages)}")
        Command.run("genfstab -L -p /mnt >> /mnt/etc/fstab")

    def setup_system(self) -> None:
        with open("/mnt/etc/locale.gen", "w") as f:
            f.write(f"{self.user_data.locale}\n")

        with open("/mnt/etc/locale.conf", "w") as f:
            f.write(f"LANG={self.user_data.lang}\n")

        with open("/mnt/etc/hostname", "w") as f:
            f.write(f"{self.user_data.hostname}\n")

        with open("/mnt/etc/vconsole.conf", "w") as f:
            f.write(f"KEYMAP={self.user_data.keymap}")

        with open("/mnt/etc/hosts", "w") as f:
            f.write(
                "127.0.0.1 localhost.localdomain localhost\n"
                "::1 localhost.localdomain localhost\n"
                f"127.0.0.1 {self.user_data.hostname}.localdomain {self.user_data.hostname}\n"
            )

        Command.run("locale-gen", chroot=True)
        Command.run(
            f"ln -sf /usr/share/zoneinfo/{self.user_data.timezone} /etc/localtime",
            chroot=True,
        )
        Command.run("hwclock --systohc", chroot=True)

    def setup_initramfs(self) -> None:
        hooks = f"HOOKS=({' '.join(self.user_data.mkinitcpio_hooks)})\n"

        with open("/mnt/etc/mkinitcpio.conf", "w") as f:
            f.write(f"{hooks}\n")

        Command.run("mkinitcpio -p linux", chroot=True)

    def enable_services(self) -> None:
        for service in self.user_data.services:
            try:
                Command.run(f"systemctl enable {service}", chroot=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to enable {service}")
                logger.exception(e)

    def enable_timers(self) -> None:
        for timer in self.user_data.timers:
            try:
                Command.run(f"systemctl enable {timer}", chroot=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to enable {timer}")
                logger.exception(e)

    def setup_bootloader(self) -> None:
        Command.run("bootctl --path /boot install", chroot=True)

        with open("/mnt/boot/loader/loader.conf", "w") as f:
            f.write("default arch.conf")

        load_microcode = (
            ""
            if not self.system_data.ucode
            else f"initrd /{self.system_data.ucode}.img\n"
        )
        uuid = Command.run(
            "blkid /dev/disk/by-partlabel/cryptsystem -s UUID -o value"
        ).stdout

        arch_entry = (
            "title Arch Linux\n"
            "linux /vmlinuz-linux\n"
            f"{load_microcode}"
            "initrd /initramfs-linux.img\n"
            f"options rd.luks.name={uuid}=system rd.luks.allow-discards root=/dev/mapper/system rootflags=subvol=@ rd.luks.options=discard rw"  # noqa: B950
        )

        with open("/mnt/boot/loader/entries/arch.conf", "w") as f:
            f.write(arch_entry)

    def setup_root_password(self) -> None:
        Command.run(
            "passwd",
            chroot=True,
            cmd_input=f"{self.user_data.root_password}\n{self.user_data.root_password}\n",
        )

    def umount_and_reboot(self) -> None:
        Command.run("umount -R /mnt")
        input("Installation complete. Press any key to reboot.")
        Command.run("reboot")
