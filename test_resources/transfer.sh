#!/bin/bash

# Get the directory of the current script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Get the parent directory of the current script
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

ssh-keygen -f "/home/${USER}/.ssh/known_hosts" -R "[localhost]:2222" || true
sshpass -p "a" scp -P 2222 -o StrictHostKeyChecking=no -r ./dist/getarch root@localhost:~
sshpass -p "a" scp -P 2222 -o StrictHostKeyChecking=no -r ./examples/config.json root@localhost:~
