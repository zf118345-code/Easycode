# Android streaming runtime

EasyCode pins the official `scrcpy-server` device component for its optional
low-latency Android frame provider.

- Upstream: <https://github.com/Genymobile/scrcpy>
- Version: `4.1`
- Asset: `scrcpy-server-v4.1`
- SHA-256: `DEACB991ED2509715160FFDC7907E47B4160EB30D1566217E9047FD5B8850CAE`
- License: Apache License 2.0 (see the upstream repository)

The runtime verifies this hash before pushing the server to a device. A hash
mismatch disables the high-speed provider instead of executing an untrusted
binary. Standard ADB capture remains available as an explicitly labelled
compatibility tier.
