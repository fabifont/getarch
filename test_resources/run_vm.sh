#!/bin/bash

# Get the directory of the current script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Get the parent directory of the current script
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Launch qemu
qemu-system-x86_64 -smp 6 -m 4G -enable-kvm -cdrom "${SCRIPT_DIR}/arch.iso" -boot order=d -net user,hostfwd=tcp::2222-:22 -net nic -bios /usr/share/ovmf/x64/OVMF_CODE.fd -virtfs local,path="${PARENT_DIR}",mount_tag=shared_folder,security_model=mapped,id=shared_folder -monitor unix:/tmp/qemu-monitor.sock,server,nowait "${SCRIPT_DIR}/arch.qcow2"
