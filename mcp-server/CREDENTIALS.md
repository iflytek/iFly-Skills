# iFLYTEK MCP credentials

## Obtain the values

1. Sign in to the [iFLYTEK Open Platform console](https://console.xfyun.cn/).
2. Create or select an application.
3. Copy its `APPID`, `APIKey`, and `APISecret` from the application page.
4. Enable each API capability used by the tools you plan to call. A valid credential
   set does not grant an ability that has not been enabled for that application.

The MCP server accepts one canonical set:

| MCP setting | iFLYTEK console value |
|---|---|
| `IFLYTEK_APP_ID` | `APPID` |
| `IFLYTEK_API_KEY` | `APIKey` |
| `IFLYTEK_API_SECRET` | `APISecret` |

## Runtime mapping

The checked-in scripts historically use different prefixes. The server maps the
canonical set immediately before launching the selected process:

| Skills | Child-process variables |
|---|---|
| Hyper TTS, transcription | `XFEI_APP_ID`, `XFEI_API_KEY`, `XFEI_API_SECRET` |
| Translation, invoice OCR | `XFYUN_APP_ID`, `XFYUN_API_KEY`, `XFYUN_API_SECRET` |
| Proofreading, image understanding, image/PDF OCR | `IFLY_APP_ID`, `IFLY_API_KEY`, `IFLY_API_SECRET` |

The canonical variables are removed from the child environment. Credential values are
redacted from MCP text responses and are never included in missing-credential errors.

File-based tools also require `IFLYSKILLS_ALLOWED_DIR`. Input paths are resolved before
execution and must be existing files beneath that directory. For Docker, mount the same
directory read-only. Text-only tools do not read it.

## Marketplace installation

`manifest.json` declares an allowed-directory picker plus all three credential values in
MCPB `user_config`; the credentials are required and marked `sensitive: true`. A compatible
installer, including Smithery's local MCPB path, collects them and substitutes them into
the server environment. `smithery.yaml` itself contains only the public server name and
local target.

Smithery/Glama publisher authentication is a registry-account concern, not an iFLYTEK
application credential. Do not add marketplace tokens, an App ID, API Key, or API Secret
to Git, workflow YAML, an MCP client argument list, logs, screenshots, or issue comments.

Rotate exposed values in the iFLYTEK console. The upstream service's privacy terms are
available at <https://www.xfyun.cn/doc/policy/privacy.html> and are also declared in the
MCPB manifest.
