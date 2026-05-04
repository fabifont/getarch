#!/bin/bash
# In-guest bootstrap. Mounted via virtfs share at /shared and run by the
# orchestrator after the live ISO autologs into root.
#
# Steps:
#   1. Mount the host-shared workspace.
#   2. Install Python and getarch (zipapp wins over pacstrapping pip stack).
#   3. Run getarch install with the matrix-supplied config.
#   4. Drop a sentinel file the host orchestrator polls for.

set -euo pipefail

if ! mountpoint -q /shared; then
  mkdir -p /shared
  mount -t 9p -o trans=virtio,version=9p2000.L shared /shared
fi

cd /shared

# Use the matrix-supplied config + zipapp.
CONFIG="${CONFIG:-/shared/config.json}"
ZIPAPP="${ZIPAPP:-/shared/getarch.pyz}"
LOG="/shared/install.log"
SENTINEL="/shared/install.exit"

# Skip preflights: QEMU+ISO already guarantees root, Arch ISO, UEFI; pacman
# keyring is initialised by the live ISO; internet handled by the workflow.
ARGS=(
  install
  "$CONFIG"
  --yes
  --force
  --skip-environment-preflight
  --skip-runtime-preflight
)

# Mirror install output to /dev/tty1 (the framebuffer that the QEMU GUI
# window shows). The install bootstrap runs on ttyS0 because that's the
# only tty the host orchestrator can drive bidirectionally; without this
# tee, the GUI window would just sit at an idle login shell while the
# real action happens off-screen on serial.
TTY1_TEE=()
if [ -w /dev/tty1 ]; then
  TTY1_TEE=(/dev/tty1)
fi

set +e
python "$ZIPAPP" "${ARGS[@]}" 2>&1 | tee "$LOG" "${TTY1_TEE[@]}"
echo "${PIPESTATUS[0]}" > "$SENTINEL"
set -e
sync
