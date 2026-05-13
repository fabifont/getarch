#!/usr/bin/env bash
# Local-dev helper: boot QEMU with the project tree shared in via virtfs
# so you can hand-test `getarch install` against a fresh Arch ISO without
# going through the full CI smoke matrix.
#
# Defaults match the qemu-smoke workflow's firmware (UEFI/OVMF) so the
# guest sees the same boot path the CI matrix validates. Pass
# `--firmware bios` for the legacy SeaBIOS path.
#
# Usage:
#   test_resources/run_vm.sh [options]
#
# Options:
#   --iso PATH        Arch ISO to boot from
#                     (default: ~/.cache/getarch-qemu/archlinux.iso)
#   --disk PATH       qcow2 disk image; auto-created if missing
#                     (default: test_resources/arch.qcow2)
#   --size SIZE       disk size when auto-creating (default: 32G)
#   --firmware NAME   uefi | bios (default: uefi)
#   --ssh-port PORT   localhost SSH forward (default: 2222; 0 disables)
#   --memory SIZE     -m flag (default: 4G)
#   --cores N         -smp flag (default: 4)
#   --no-share        don't expose the project tree via virtfs
#   -h, --help        show this and exit
#
# Once the guest boots, the project tree is reachable at /shared via
# virtfs:
#
#   mount -t 9p -o trans=virtio,version=9p2000.L shared /shared
#
# which matches the mount tag the CI bootstrap (`run_install.sh`) uses,
# so you can drive a config + zipapp the same way the matrix does.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

ISO="${HOME}/.cache/getarch-qemu/archlinux.iso"
DISK="${SCRIPT_DIR}/arch.qcow2"
SIZE="32G"
FIRMWARE="uefi"
SSH_PORT="2222"
MEMORY="4G"
CORES="4"
SHARE="yes"

OVMF_CODE="/usr/share/edk2/x64/OVMF_CODE.4m.fd"
OVMF_VARS_TEMPLATE="/usr/share/edk2/x64/OVMF_VARS.4m.fd"

show_help() {
    sed -n '2,32p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --iso)        ISO="$2"; shift 2 ;;
        --disk)       DISK="$2"; shift 2 ;;
        --size)       SIZE="$2"; shift 2 ;;
        --firmware)   FIRMWARE="$2"; shift 2 ;;
        --ssh-port)   SSH_PORT="$2"; shift 2 ;;
        --memory)     MEMORY="$2"; shift 2 ;;
        --cores)      CORES="$2"; shift 2 ;;
        --no-share)   SHARE="no"; shift ;;
        -h|--help)    show_help; exit 0 ;;
        *)
            echo "Unknown option: $1" >&2
            show_help >&2
            exit 2
            ;;
    esac
done

if [[ ! -f "$ISO" ]]; then
    echo "ISO not found: $ISO" >&2
    echo "Drop an Arch ISO there or pass --iso PATH." >&2
    exit 1
fi

if [[ ! -f "$DISK" ]]; then
    echo "[run_vm] creating fresh $SIZE qcow2 at $DISK"
    qemu-img create -f qcow2 "$DISK" "$SIZE" >/dev/null
fi

QEMU_ARGS=(
    -enable-kvm
    -cpu host
    -smp "$CORES"
    -m "$MEMORY"
    -cdrom "$ISO"
    -boot order=d
    -drive "file=$DISK,format=qcow2,if=virtio"
    -monitor unix:/tmp/getarch-qemu-monitor.sock,server,nowait
)

case "$FIRMWARE" in
    uefi)
        if [[ ! -f "$OVMF_CODE" || ! -f "$OVMF_VARS_TEMPLATE" ]]; then
            echo "OVMF not found at $OVMF_CODE / $OVMF_VARS_TEMPLATE" >&2
            echo "Install edk2-ovmf or use --firmware bios." >&2
            exit 1
        fi
        OVMF_VARS="${SCRIPT_DIR}/OVMF_VARS.fd"
        if [[ ! -f "$OVMF_VARS" ]]; then
            cp "$OVMF_VARS_TEMPLATE" "$OVMF_VARS"
        fi
        QEMU_ARGS+=(
            -drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE"
            -drive "if=pflash,format=raw,file=$OVMF_VARS"
        )
        ;;
    bios)
        : # default SeaBIOS, no extra flags
        ;;
    *)
        echo "Unknown --firmware: $FIRMWARE (use 'uefi' or 'bios')" >&2
        exit 2
        ;;
esac

if [[ "$SSH_PORT" != "0" ]]; then
    QEMU_ARGS+=(-net "user,hostfwd=tcp::${SSH_PORT}-:22" -net nic)
fi

if [[ "$SHARE" == "yes" ]]; then
    QEMU_ARGS+=(
        -virtfs "local,path=${PARENT_DIR},mount_tag=shared,security_model=mapped,id=shared"
    )
fi

exec qemu-system-x86_64 "${QEMU_ARGS[@]}"
