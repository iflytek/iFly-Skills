# iFly-Skills MCP Server

Local stdio or authenticated SSE MCP server for the executable, single-step AI skills in this repository.
The server uses the official MCP Python SDK v2 and runs the existing skill scripts
without modifying them.

## Exposed tools

| Tool | Checked-in implementation |
|---|---|
| `translate` | `skills/iflytek-translate/scripts/translate.py` |
| `proofread` | `skills/iflytek-text-proofread/scripts/text_proofread.py` |
| `hyper_tts` | `skills/iflytek-hyper-tts/scripts/xfei_hyper_tts.py` |
| `image_understanding` | `skills/iflytek-image-understanding/scripts/image_understanding.py` |
| `ocr_invoice` | `skills/iflytek-ocr-invoice/scripts/invoice.py` |
| `image_ocr` / `pdf_ocr` | `skills/iflytek-pdf-image-ocr/scripts/*.py` |
| `transcribe` | `skills/iflytek-speed-transcription/scripts/transcribe.py` |

Stateful voice-cloning/video workflows, the multi-service contract-review workflow,
and the non-Python diagram skill are intentionally not exposed. They need dedicated
task-state, endpoint, or runtime contracts rather than a misleading one-shot wrapper.

## Credentials

Create an application in the [iFLYTEK Open Platform console](https://console.xfyun.cn/),
enable every capability you plan to call, and provide the matching values:

```text
IFLYTEK_APP_ID
IFLYTEK_API_KEY
IFLYTEK_API_SECRET
```

MCPB installers collect all three as declared sensitive user configuration. For local
and Docker runs, set them in the process environment. See
[`CREDENTIALS.md`](./CREDENTIALS.md) for the mapping and security boundary.

## Local development

From the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install './mcp-server[dev]'
python -m iflyskills_mcp.introspect
pytest -q mcp-server/tests
iflyskills-mcp
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

Example client entry, replacing both absolute paths:

```json
{
  "mcpServers": {
    "iflytek-skills": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/absolute/path/to/iFly-Skills/mcp-server",
        "iflyskills-mcp"
      ],
      "env": {
        "IFLY_SKILLS_ROOT": "/absolute/path/to/iFly-Skills",
        "IFLYSKILLS_ALLOWED_DIR": "/absolute/path/to/approved-inputs",
        "IFLYTEK_APP_ID": "<app-id>",
        "IFLYTEK_API_KEY": "<api-key>",
        "IFLYTEK_API_SECRET": "<api-secret>"
      }
    }
  }
}
```

## SSE transport

Stdio remains the default. To expose the same tools over the MCP SSE transport on the
loopback interface:

```bash
iflyskills-mcp --transport sse --host 127.0.0.1 --port 8000
```

Clients connect to `http://127.0.0.1:8000/sse`; the server advertises the paired
`/messages/` endpoint for that session. DNS-rebinding protection accepts loopback Host
and Origin values by default.

Any non-loopback bind, including `0.0.0.0`, requires a bearer token supplied through the
environment rather than a command-line argument:

```bash
export IFLYSKILLS_MCP_BEARER_TOKEN="$(openssl rand -hex 32)"
iflyskills-mcp --transport sse --host 0.0.0.0 --port 8000
```

Send `Authorization: Bearer <token>` on both the SSE connection and its message POSTs.
For a reverse proxy, explicitly add the public Host and browser Origin as needed:

```bash
iflyskills-mcp --transport sse --host 0.0.0.0 \
  --allow-host mcp.example.com \
  --allow-origin https://mcp.example.com
```

TLS termination, rate limiting, and multi-user identity belong at the reverse proxy or
gateway. The server token is never forwarded to child skill processes.

## Docker

```bash
docker build -f mcp-server/Dockerfile -t iflyskills-mcp .
docker run --rm -i \
  -v "$PWD/approved-inputs:/data:ro" \
  -e IFLYSKILLS_ALLOWED_DIR=/data \
  -e IFLYTEK_APP_ID \
  -e IFLYTEK_API_KEY \
  -e IFLYTEK_API_SECRET \
  iflyskills-mcp
```

For authenticated SSE in Docker, publish the port only on the intended interface and pass
the token through the environment:

```bash
docker run --rm \
  -p 127.0.0.1:8000:8000 \
  -v "$PWD/approved-inputs:/data:ro" \
  -e IFLYSKILLS_ALLOWED_DIR=/data \
  -e IFLYSKILLS_MCP_BEARER_TOKEN \
  -e IFLYTEK_APP_ID \
  -e IFLYTEK_API_KEY \
  -e IFLYTEK_API_SECRET \
  iflyskills-mcp --transport sse --host 0.0.0.0 --port 8000
```

The image runs as an unprivileged user. Image, PDF, invoice, and audio inputs must resolve
inside `IFLYSKILLS_ALLOWED_DIR`; the example mounts that directory read-only. The three
canonical credentials are removed from each child process and replaced only with the
prefix its selected skill expects. Tool arguments are passed as an argument vector, never
through a shell. Generated artifacts are read with a 20 MiB default limit, returned
without a local path, and the temporary file is deleted.

## MCPB, Smithery, and Glama

[`manifest.json`](./manifest.json) follows MCPB 0.4, requires an allowed input directory,
and declares App ID, API Key, and API Secret as sensitive installer fields. Build a
bundle from a clean output path:

```bash
python mcp-server/scripts/stage_mcpb.py mcp-server/dist/iflytek-skills
npx -y @anthropic-ai/mcpb@2.1.2 validate mcp-server/dist/iflytek-skills
npx -y @anthropic-ai/mcpb@2.1.2 pack \
  mcp-server/dist/iflytek-skills \
  mcp-server/dist/iflytek-skills.mcpb
```

- **Smithery:** [`smithery.yaml`](./smithery.yaml) uses the current local-target
  project format. Authenticate with `smithery auth login`, then publish the validated
  bundle with `smithery mcp publish <bundle.mcpb> -n <namespace>/iflytek-skills`.
- **Glama:** [`glama.json`](./glama.json) declares the GitHub maintainer using Glama's
  current schema. Repository listing remains a registry-side action.

Marketplace account authentication is deliberately not stored in this repository.
It is distinct from each user's iFLYTEK App ID/API Key/API Secret, which are collected
by the MCPB manifest and injected only at runtime.

## Validation

`.github/workflows/mcp-server.yml` runs Python 3.10 and 3.13 tests, static manifest-to-
argparse validation, Ruff, official MCPB 2.1.2 validation/packing, and a Docker build.

Primary specifications:

- [MCP Python SDK v2](https://github.com/modelcontextprotocol/python-sdk)
- [MCPB manifest and CLI](https://github.com/modelcontextprotocol/mcpb)
- [Smithery CLI publishing](https://github.com/arcadeai-labs/smithery-cli)
