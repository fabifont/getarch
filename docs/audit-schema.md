# Audit log schema (v1)

Each install writes a line-delimited JSON file to
`<mount>/var/log/getarch.log`. Every line is one record; consumers can
process the file with `jq`, `vector`, `journald-export`, etc.

## Record types

### `command` records

Emitted once per executed command. Stable v1 keys:

| key | type | meaning |
|-----|------|---------|
| `schema_version` | int | always `1` for the v1 schema |
| `type` | string | always `"command"` |
| `ts` | string | ISO 8601 UTC timestamp, second precision |
| `argv` | array&lt;string&gt; | full argv. Sensitive commands are reduced to `[binary, "<redacted>"]` |
| `chroot` | string \| null | mount root passed to `arch-chroot`, or null if the command ran outside |
| `exit` | int | subprocess return code |
| `stderr_tail` | string | last 512 bytes of stderr |
| `input` | string \| null | `"***"` when the command had stdin AND was sensitive; else null |

Example:

```json
{"argv":["pacstrap","-K","/mnt","base"],"chroot":null,"exit":0,"input":null,"schema_version":1,"stderr_tail":"","ts":"2026-05-02T12:34:56+00:00","type":"command"}
```

### `hmac` trailer (optional)

When `--audit-hmac-key PATH` is set on `getarch install` or
`getarch tui --execute`, `LoggingRunner.render()` appends a single
trailer:

```json
{"alg":"HMAC-SHA256","schema_version":1,"type":"hmac","value":"<hex>"}
```

`value` is `HMAC-SHA256(key, body)` where `body` is the byte string of
all prior `command` records, each terminated by `\n`. The trailer
itself is excluded from the HMAC input.

## Verification

```bash
# Strip the HMAC trailer, then re-compute and compare.
KEY="$(cat /path/to/audit.key)"
BODY="$(head -n -1 /mnt/var/log/getarch.log)"
EXPECTED="$(jq -r '.value' /mnt/var/log/getarch.log | tail -n 1)"
ACTUAL="$(printf '%s\n' "$BODY" | openssl dgst -sha256 -hmac "$KEY" | awk '{print $2}')"
test "$EXPECTED" = "$ACTUAL" && echo OK
```

## Sensitivity

* Passwords, LUKS unlock material, WPA2-Enterprise credentials, etc.
  are flagged `sensitive=True` on the `Command` itself. The audit log
  redacts both `argv` (down to the binary name) and `input` for those
  records.
* Stderr is captured **as-is**: if a tool you invoked echoes a secret
  to stderr, the tail will land in the log. Avoid `--debug` flags on
  third-party tools that might leak material.
* The HMAC covers integrity, not confidentiality; the file is still
  plaintext JSON. Combine with `chmod 0600` and a transport that
  encrypts in flight if you ship the log off-host.

## Compatibility

The schema is versioned via `schema_version`. A bump (`schema_version`
\>= 2) is allowed to add or rename fields; consumers should reject
unknown `schema_version` values rather than silently accept them.
