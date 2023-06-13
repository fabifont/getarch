#!/bin/bash

# Get the directory of the current script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Remove existing qcow2 images
rm -f "${SCRIPT_DIR}"/*.qcow2

# Create new qcow2 image
qemu-img create -f qcow2 "${SCRIPT_DIR}/arch.qcow2" 8G
