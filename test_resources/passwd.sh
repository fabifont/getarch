#!/bin/bash

commands=(
    "sendkey e"
    "sendkey c"
    "sendkey h"
    "sendkey o"
    "sendkey spc"
    "sendkey apostrophe"
    "sendkey a"
    "sendkey backslash"
    "sendkey n"
    "sendkey a"
    "sendkey backslash"
    "sendkey n"
    "sendkey apostrophe"
    "sendkey spc"
    "sendkey shift-backslash"
    "sendkey spc"
    "sendkey p"
    "sendkey a"
    "sendkey s"
    "sendkey s"
    "sendkey w"
    "sendkey d"
    "sendkey ret"
)

# Iterate over the commands and send them with a delay
for cmd in "${commands[@]}"; do
  echo "$cmd" | socat - UNIX-CONNECT:/tmp/qemu-monitor.sock
  sleep 0.5
done
