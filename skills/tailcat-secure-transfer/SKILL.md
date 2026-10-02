---
name: tailcat-secure-transfer
description: Transfer text or files, or temporarily reach one explicitly selected local TCP service between two machines with Tailcat. Use for an approved one-off peer transfer or development tunnel. Do not use for public hosting, long-lived VPNs, exit-node routing, unrestricted port exposure, or unauthenticated SSH.
metadata: {
  "homepage": "https://github.com/tailscale/tailcat",
  "openclaw": '{"emoji":"🐈","dimensions":["secure peer transfer","temporary TCP tunnel"],"user_instructions":["Send this file securely to another machine with Tailcat","Receive a one-off file over Tailcat","Temporarily reach my local development port through Tailcat"],"requires":{"bins":["tailcat"]}}'
}
---

# Tailcat Secure Transfer

Use Tailcat for a bounded transfer between two machines. One machine is the
**receiver/server**: it starts a listener and prints a `tc...` connection token.
The other is the **sender/client**: it receives that token out of band and connects.

Tailcat uses WireGuard encryption end to end. It attempts a direct UDP path and
falls back to a DERP relay when NAT traversal fails. Public relays are
rate-limited and best-effort, so do not promise a direct path, throughput, or uptime.

## Safety contract

Before executing anything, confirm:

- which machine receives/listens and which sends/connects;
- the exact text, source file, destination path, or localhost port in scope;
- that the user approves starting a network listener and transferring the data;
- how the token will be shared with the intended peer.

Treat a `tc...` token as a capability address: anyone who has it can try to reach
that listener unless client allowlisting is configured. Do not publish it, put it
in issue or PR text, persist it in notes, or echo it into unrelated logs. Tailcat
requires the token as a client argument, so keep command output and process details
scoped to the task.

For one-off work, pass `--key=new` on the receiving server. Do this even though a
fresh key is the normal default: Tailcat silently uses a saved key named `default`
when one exists, and that would turn a one-off address into a reusable address.

Do not install Tailcat, create a saved key, send local data, expose a port, or
start a listener without explicit approval. Never broaden a requested port into
`--serve=all`.

## Prepare both machines

1. Check for `tailcat` without changing the machine:
   - POSIX shell: `command -v tailcat`
   - PowerShell: `Get-Command tailcat -ErrorAction SilentlyContinue`
2. If it is missing, present the official
   [release](https://github.com/tailscale/tailcat/releases) and
   `go install github.com/tailscale/tailcat/cmd/tailcat@latest` options. Let the
   user choose a version and approve installation; do not silently download or
   upgrade it.
3. Inspect `tailcat --help` before use. Tailcat does not promise CLI or wire-format
   stability. These instructions were reviewed against upstream commit
   `a34089b378fea36d49ea2276d83b9237a32bb338`.

## One-off text transfer

On the receiving machine, start an ephemeral server:

```sh
tailcat --key=new
```

Tailcat prints the connection token to stderr and writes received bytes to stdout.
Share only the token with the intended sender. On the sending machine, connect with:

```sh
tailcat tc...
```

Provide the text through the process's stdin and then close stdin. When executing
for a user, pass stdin through the process or tool API or an approved file; do not
interpolate untrusted text into a shell command. The receiver exits after the pipe
finishes.

## One-off file transfer

Preserve bytes exactly. Do not use text-oriented pipelines such as PowerShell
`Get-Content | tailcat` or `tailcat | Set-Content` for binary files.

On the receiving machine:

1. Resolve the user-approved destination path.
2. Refuse to continue if either the final path or its `.part` path already exists.
3. Redirect Tailcat's stdout to the `.part` path while forcing an ephemeral key.
4. Rename the partial file to the final path only after Tailcat exits successfully.

POSIX example after both paths have been checked:

```sh
tailcat --key=new > received.bin.part &&
  mv -- received.bin.part received.bin
```

On Windows, use a native process API or `cmd.exe` redirection so stdin and stdout
remain byte streams. Quote paths according to that API. Do not route binary data
through PowerShell text cmdlets.

On the sending machine, stream the approved source file to the supplied token:

```sh
tailcat tc... < source.bin
```

Use process APIs rather than constructing a shell string when paths or tokens come
from untrusted input. If a transfer fails, report the `.part` file and ask before
deleting or replacing it.

For important files, calculate SHA-256 locally on both machines and compare the
digests through the approved coordination channel. Do not publish a digest when the
file itself or its fingerprint is sensitive.

## Temporary access to one local TCP service

Confirm the exact localhost port, intended peer, and stop condition. On the machine
hosting the service, expose only that port and keep the Tailcat process visible and
cancellable:

```sh
tailcat --key=new --serve=3000
```

For a raw TCP session, the client can connect to that same port:

```sh
tailcat tc... 3000
```

For an HTTP-aware command, run it through Tailcat's scoped SOCKS proxy and the
special `server.tailcat` hostname:

```sh
tailcat socks tc... curl --fail --show-error http://server.tailcat:3000/
```

Stop the server when the requested access is complete. Do not daemonize it or keep
the token for later unless the user explicitly requests a persistent setup.

## Explicit-only advanced setups

Do not propose these as shortcuts:

- `--serve=exit-node` exposes routes beyond the selected local service.
- `--serve=all` accepts connections for every port.
- `--serve=no-auth-ssh` starts an authentication-free SSH service.
- `tailcat genkey` creates a persistent identity and reusable address.

If the user explicitly requests persistent access, explain that anyone who retained
the stable server token can connect in future sessions. Prefer generating a client
identity and restricting the server with `--allow=<client-public-key>`. Key creation,
storage, DNS publication, and service persistence are separate external changes and
each needs approval.

## Finish

Report whether the transfer or connection completed, whether traffic was direct or
relayed if Tailcat reported it, and any partial files or still-running listeners.
Never claim success from process startup alone.

## Gotchas

The common failure modes are omitting `--key=new` when a saved default key exists,
using text pipelines for binary data, assuming DERP fallback is a direct path, and
treating listener startup as proof that the requested transfer completed.
