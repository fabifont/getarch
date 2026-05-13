# test_resources

Scripts and helpers for end-to-end testing of `getarch` against real
QEMU/KVM guests.

## CI smoke matrix

These three files are the inputs to the `qemu-smoke` workflow
([`.github/workflows/qemu.yml`](../.github/workflows/qemu.yml)).

| File | Role |
|---|---|
| [`qemu_smoke.py`](qemu_smoke.py) | Host-side driver. Boots the Arch ISO under QEMU/KVM, drives the install via the QEMU monitor + virtfs share, then restarts disk-only and asserts the installed system reaches a serial getty. |
| [`qemu_configs.py`](qemu_configs.py) | Generates the matrix-specific config (4 filesystems × 3 bootloaders). Run as `python qemu_configs.py <fs> <bootloader>`. |
| [`run_install.sh`](run_install.sh) | In-guest bootstrap. Mounted via virtfs at `/shared` and run by the orchestrator after the live ISO autologs into root. |

## Local-dev helper

[`run_vm.sh`](run_vm.sh) — boot a QEMU VM with the project tree shared
in via virtfs so you can hand-test `getarch install` without going
through the full smoke matrix. UEFI/OVMF by default to match CI; pass
`--firmware bios` for the legacy path.

```sh
# First time (assumes the ISO is cached in the same place the CI uses):
test_resources/run_vm.sh

# Custom ISO + BIOS guest:
test_resources/run_vm.sh --firmware bios --iso /tmp/arch.iso

# See all options:
test_resources/run_vm.sh --help
```

Inside the guest, mount the project tree once you're at the live-ISO
shell:

```sh
mkdir -p /shared
mount -t 9p -o trans=virtio,version=9p2000.L shared /shared
cd /shared
```

From there you can run the zipapp directly:

```sh
python dist/getarch.pyz install path/to/your.json --yes --force \
    --skip-environment-preflight --skip-runtime-preflight
```

(`run_install.sh` does exactly this for the CI matrix; reading it is a
good template for one-liner manual runs.)

## Local artefacts (gitignored)

- `*.iso`, `*.qcow2`, `*.fd` — boot ISOs, disk images, OVMF NVRAM
  scratch copies. The `run_vm.sh` script writes `arch.qcow2` and
  `OVMF_VARS.fd` here on first run.
