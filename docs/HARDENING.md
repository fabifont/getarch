# Hardening — what to do after the first boot

`getarch` lays down a working Arch install. It deliberately does
*not* configure SSH, firewall rules, sudoers, or automatic updates —
those are operational decisions. This guide covers the changes I
recommend on every fresh install. Pick what applies; nothing here is
mandatory.

## 1. SSH — disable password login, restrict ciphers

Edit `/etc/ssh/sshd_config.d/10-hardening.conf`:

```ini
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
UsePAM yes
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding no
PermitTunnel no
GatewayPorts no
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2

# Modern crypto only.
KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org,sntrup761x25519-sha512@openssh.com
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com
HostKeyAlgorithms ssh-ed25519,sk-ssh-ed25519@openssh.com,rsa-sha2-512,rsa-sha2-256
PubkeyAcceptedAlgorithms ssh-ed25519,sk-ssh-ed25519@openssh.com,rsa-sha2-512,rsa-sha2-256

AllowUsers your-username
```

Reload:

```bash
sudo sshd -t && sudo systemctl reload sshd
```

Drop your SSH key into `~/.ssh/authorized_keys` first; otherwise
disabling password auth locks you out.

## 2. Firewall — nftables baseline

If you set `network.firewall_nftables_rules` in your getarch config,
the installer already wrote `/etc/nftables.conf`. The minimum
restrictive baseline (drop everything inbound, allow established + ssh):

```text
chain input {
  type filter hook input priority 0; policy drop;
  ct state established,related accept
  iif lo accept
  icmp type echo-request limit rate 5/second accept
  ip6 nexthdr icmpv6 icmpv6 type { echo-request, nd-router-solicit } accept
  tcp dport 22 accept
}

chain forward { type filter hook forward priority 0; policy drop; }
chain output  { type filter hook output  priority 0; policy accept; }
```

Reload:

```bash
sudo systemctl restart nftables
```

## 3. sudo — wheel only, NOPASSWD off

`/etc/sudoers.d/10-wheel`:

```text
%wheel ALL=(ALL:ALL) ALL
Defaults timestamp_timeout=5
Defaults passwd_tries=3
Defaults env_reset
Defaults secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
```

`visudo -c -f /etc/sudoers.d/10-wheel` to validate. If you
intentionally want passwordless sudo for a CI box, scope it to the
specific binary path (`%wheel ALL=(ALL) NOPASSWD: /usr/bin/foo`) — never
the whole user.

## 4. Pacman — automatic security updates

`/etc/systemd/system/pacman-update.service`:

```ini
[Unit]
Description=Pacman -Syu (security updates)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/pacman -Syu --noconfirm
```

`/etc/systemd/system/pacman-update.timer`:

```ini
[Unit]
Description=Daily pacman -Syu

[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=2h

[Install]
WantedBy=timers.target
```

Enable:

```bash
sudo systemctl enable --now pacman-update.timer
```

Pair with `arch-audit` (from `community/`) to surface published CVEs:

```bash
sudo pacman -S --needed arch-audit
arch-audit
```

## 5. Audit log retention

The install pipeline ships its own audit log at
`/var/log/getarch.log` (schema documented in
`docs/audit-schema.md`). Logrotate it so it doesn't fill the disk:

`/etc/logrotate.d/getarch`:

```text
/var/log/getarch.log {
  weekly
  rotate 8
  compress
  delaycompress
  missingok
  notifempty
  copytruncate
}
```

## 6. Post-install kernel module hygiene

```bash
# Block the typewriter / FireWire / floppy / parport modules nobody on
# a modern laptop needs. Reduces kernel attack surface.
cat <<'EOF' | sudo tee /etc/modprobe.d/blocklist.conf
install dccp /bin/true
install sctp /bin/true
install rds /bin/true
install tipc /bin/true
install n-hdlc /bin/true
install ax25 /bin/true
install netrom /bin/true
install x25 /bin/true
install rose /bin/true
install decnet /bin/true
install econet /bin/true
install af_802154 /bin/true
install ipx /bin/true
install appletalk /bin/true
install psnap /bin/true
install p8023 /bin/true
install p8022 /bin/true
install can /bin/true
install atm /bin/true
install firewire-core /bin/true
install thunderbolt /bin/true
EOF
```

(Remove `thunderbolt` if you actually use it.)

## 7. Backups

Out of scope for `getarch`, but worth saying explicitly: a system
without backups is a system you don't run. Pick one:

* `restic` to S3 / B2 / local USB.
* `borgbackup` over SSH to a separate host.
* `snapper` (if you enabled it in your config) for in-place snapshots
  + something off-host for disaster recovery.

## What's intentionally not here

* Choosing a desktop environment / window manager.
* Migrating dotfiles.
* Monitoring stack (Prometheus, Loki, …).

Those belong outside `getarch`'s scope; see the project's
`out of scope` section of the roadmap.
