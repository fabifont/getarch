# Self-hosted runner (Docker Compose)

This stack runs the GitHub Actions runner that backs the
`runs-on: [self-hosted, kvm]` jobs in
[`.github/workflows/qemu.yml`](../../.github/workflows/qemu.yml).

It bundles `qemu-system-x86_64`, `qemu-img`, OVMF firmware, Python 3.14
and `uv`, and the GitHub Actions runner agent into a single container
image based on `archlinux:latest` — same distro the smoke matrix is
validating against, so OVMF paths line up with the workflow's hardcoded
`/usr/share/edk2/x64/OVMF_*.4m.fd`.

## Host requirements

* Linux host with `/dev/kvm` accessible to the user that runs Docker
  (i.e. the host's `kvm` group is populated and the host kernel exposes
  the virtualization extensions).
* Docker Engine 25+ with the Compose plugin (`docker compose ...`).
* Outbound HTTPS to `github.com` and `geo.mirror.pkgbuild.com`.

## Setup

1. Copy the example environment and edit it:

   ```sh
   cp .env.example .env
   $EDITOR .env
   ```

   `RUNNER_TOKEN` is a short-lived registration token. Get one from
   *Settings → Actions → Runners → "New self-hosted runner"* on the
   GitHub repo. The token only needs to be valid at first registration;
   the runner stores its long-lived credential in the volume.

2. Build the image and start the runner:

   ```sh
   docker compose --env-file .env up -d --build
   ```

3. Confirm it's online:

   ```sh
   docker compose logs -f runner
   ```

   The runner should print `Listening for Jobs` once registered. Look
   for it under *Settings → Actions → Runners* on the GitHub repo.

## Updating

* GitHub publishes runner releases at
  <https://github.com/actions/runner/releases>. Bump `RUNNER_VERSION` in
  `.env`, then rebuild:

  ```sh
  docker compose --env-file .env build --no-cache
  docker compose --env-file .env up -d
  ```

* Arch packages (qemu, edk2-ovmf, python, uv) refresh on every image
  rebuild because the Dockerfile runs `pacman -Syu` from the latest
  base layer.

## Stopping / removing

* Stop: `docker compose down` (preserves `runner-work` and
  `runner-cache` volumes).
* Stop and reset: `docker compose down -v` (also drops the volumes —
  the runner will need to re-register on next start).

## How KVM passthrough works

The container declares `devices: /dev/kvm:/dev/kvm`. On startup,
[`entrypoint.sh`](entrypoint.sh) reads the host GID of `/dev/kvm`,
creates a matching group inside the container if one isn't already
there, adds the runner user to it, and re-execs so the new group
membership takes effect for the runner process.

## How the smoke matrix uses it

The `qemu-smoke` workflow's `smoke` job picks this runner via
`runs-on: [self-hosted, kvm]`. Each matrix cell:

1. Stages a fresh OVMF NVRAM copy and a per-cell config in
   `$RUNNER_TEMP/qemu-<fs>-<bootloader>/`.
2. Runs `test_resources/qemu_smoke.py` to drive the install via the
   QEMU monitor + virtfs share.
3. Restarts QEMU disk-only and asserts the installed system reaches a
   serial getty.

Logs and artefacts are uploaded back to the workflow run on completion.
