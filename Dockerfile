FROM myoung34/github-runner:latest

# Update packages and install qemu-kvm and dependencies
RUN apt-get update -y && \
    apt-get upgrade -y && \
    apt-get install -y qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
