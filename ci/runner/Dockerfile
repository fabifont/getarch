FROM archlinux:latest

# System deps for the qemu-smoke workflow:
# - qemu-base       → qemu-system-x86_64, qemu-img
# - edk2-ovmf       → /usr/share/edk2/x64/OVMF_CODE.4m.fd, OVMF_VARS.4m.fd
# - python, uv      → workflow uses uv to install Python 3.14 + sync deps
# - util-linux etc. → support utilities the install scripts call
RUN pacman -Syu --noconfirm \
        base-devel git curl ca-certificates \
        qemu-base edk2-ovmf \
        python uv \
        sudo procps-ng util-linux iproute2 \
        jq \
    && pacman -Scc --noconfirm

ARG RUNNER_VERSION=2.319.1
ARG RUNNER_ARCH=x64
ARG RUNNER_USER=runner
ARG RUNNER_UID=1000
ARG RUNNER_GID=1000

RUN groupadd -g ${RUNNER_GID} ${RUNNER_USER} \
    && useradd -m -u ${RUNNER_UID} -g ${RUNNER_GID} -G wheel ${RUNNER_USER} \
    && printf "%%wheel ALL=(ALL) NOPASSWD: ALL\n" > /etc/sudoers.d/wheel-nopasswd

USER ${RUNNER_USER}
WORKDIR /home/${RUNNER_USER}

# Fetch the GitHub Actions self-hosted runner release.
RUN curl -fsSL "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz" \
        -o runner.tar.gz \
    && tar xzf runner.tar.gz \
    && rm runner.tar.gz

# Pre-warm Python 3.14 so the first job's `uv python install 3.14` is a no-op.
RUN uv python install 3.14

COPY --chmod=755 entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
