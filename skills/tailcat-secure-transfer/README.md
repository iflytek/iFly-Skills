# Tailcat Secure Transfer

`tailcat-secure-transfer` turns the
[Tailcat](https://github.com/tailscale/tailcat) CLI into a bounded agent workflow
for one-off text transfer, binary-safe file transfer, and temporary access to one
explicitly selected localhost TCP port.

Tailcat combines Tailscale's open-source data-plane components into a userspace
tool. It establishes WireGuard-encrypted connections without a Tailscale account
or elevated privileges, attempts direct NAT traversal, and falls back to a DERP
relay when needed.

## Prerequisite

Install `tailcat` on both machines from an official
[release](https://github.com/tailscale/tailcat/releases), or with Go:

```sh
go install github.com/tailscale/tailcat/cmd/tailcat@latest
```

Installation downloads software and changes the machine; an agent using this skill
must obtain confirmation first. Tailcat currently makes no CLI, API, or wire-format
stability promise, so check `tailcat --help` when using a different revision.

## Ask an agent

Examples that should activate the skill:

- Send this build artifact to my other machine with Tailcat.
- Receive a one-off file without overwriting anything.
- Let my teammate reach localhost port 3000 through Tailcat for this test.

The agent will identify the receiving and sending machines, confirm the exact data
or port, force an ephemeral server key for one-off sessions, and keep the connection
token out of unrelated logs.

## Security model

- Traffic is WireGuard-encrypted end to end, including over a DERP relay.
- A `tc...` token is a capability address. Share it only with the intended peer.
- Public Tailcat DERP relays are rate-limited and best-effort.
- File receives use a collision-checked partial path and rename only after success.
- The normal workflow does not use exit-node routing, all-port exposure,
  authentication-free SSH, or persistent server keys.
- Persistent setups should use a saved client identity and server-side allowlisting.

See [`SKILL.md`](./SKILL.md) for the complete workflow and safety boundaries.

## Upstream and license

The initial integration was reviewed against Tailcat commit
[`a34089b378fea36d49ea2276d83b9237a32bb338`](https://github.com/tailscale/tailcat/commit/a34089b378fea36d49ea2276d83b9237a32bb338).
Tailcat is distributed under the BSD 3-Clause License. This skill contains original
integration guidance and does not vendor Tailcat source code or binaries. Tailcat
and its contributors do not endorse this skill.
