#!/bin/bash
# GitHub Actions self-hosted runner entrypoint for the qemu-smoke matrix.
# Reconciles the host's /dev/kvm GID into the container so the runner user
# can use KVM, then registers + starts the runner.
set -euo pipefail

: "${REPO_URL:?REPO_URL is required (e.g. https://github.com/<org>/<repo>)}"
: "${RUNNER_TOKEN:?RUNNER_TOKEN is required (registration token from repo settings)}"

RUNNER_NAME="${RUNNER_NAME:-getarch-kvm-$(hostname)}"
RUNNER_LABELS="${RUNNER_LABELS:-self-hosted,Linux,X64,kvm}"
RUNNER_WORK_DIR="${RUNNER_WORK_DIR:-_work}"

# Match the host's kvm group GID inside the container so /dev/kvm is readable.
if [[ -e /dev/kvm ]]; then
    HOST_KVM_GID="$(stat -c '%g' /dev/kvm)"
    if ! getent group "$HOST_KVM_GID" >/dev/null; then
        sudo groupadd -g "$HOST_KVM_GID" hostkvm
    fi
    if ! id -nG | tr ' ' '\n' | grep -qx "$(getent group "$HOST_KVM_GID" | cut -d: -f1)"; then
        sudo usermod -aG "$HOST_KVM_GID" "$(id -un)"
        # usermod's group change takes effect on the next login; re-exec under
        # the right groups so the rest of this script (and the runner) sees them.
        exec sudo -E --preserve-env=REPO_URL,RUNNER_TOKEN,RUNNER_NAME,RUNNER_LABELS,RUNNER_WORK_DIR \
            -u "$(id -un)" "$0" "$@"
    fi
fi

cleanup() {
    echo "[entrypoint] removing runner registration..."
    ./config.sh remove --token "$RUNNER_TOKEN" || true
}
trap cleanup EXIT INT TERM

./config.sh \
    --url "$REPO_URL" \
    --token "$RUNNER_TOKEN" \
    --name "$RUNNER_NAME" \
    --labels "$RUNNER_LABELS" \
    --work "$RUNNER_WORK_DIR" \
    --unattended \
    --replace

exec ./run.sh
