# iFly-Skills Coze 服务

本目录提供一个面向 Coze 国内站和国际站的共享 HTTPS 服务，用于承载 iFly-Skills 能力。服务按站点分别配置工作空间和访问密钥；同一个后端实例可以同时服务两个站点。

当前发布版本提供服务配置、健康检查、访问认证和统一错误边界，尚未发布业务工具。业务工具在相应版本发布后，通过稳定的 `/v1/skills/<skill-id>/<action>` 地址提供；每个工具的请求和响应字段以该版本随附的 OpenAPI 文档为准。

## 使用条件

- Python 3.13 或 3.14
- [uv](https://docs.astral.sh/uv/)
- 可从 Coze 访问的 HTTPS 域名（本地调试可先使用 HTTP）
- 启用能力所需的讯飞服务凭证

## 配置

复制 [.env.example](./.env.example) 为同目录的 `.env`，再填写实际值。`.env` 只保存在部署环境，不要提交到代码仓库。

| 配置项 | 说明 |
| --- | --- |
| `COZE_ENABLED_SITES` | 填写 `cn`、`global` 或 `cn,global`，明确启用的站点 |
| `COZE_<SITE>_WORKSPACE_ID` | 对应站点的工作空间 ID |
| `COZE_<SITE>_BACKEND_API_KEY` | 插件访问本服务的独立密钥，长度 32～256 个无空格 ASCII 可打印字符 |
| `COZE_<SITE>_ALLOWED_SKILLS` | 允许该站点调用的 Skill ID，使用逗号分隔 |
| `COZE_<SITE>_API_BASE_URL` | 国内使用 `https://api.coze.cn`，国际使用 `https://api.coze.com` |
| `COZE_<SITE>_API_TOKEN` | 对应站点的平台令牌，仅用于工作空间或平台管理检查 |
| `COZE_<SITE>_BACKEND_BASE_URL` | 部署后供插件访问的 HTTPS 服务地址；本地运行时可留空 |

其中 `<SITE>` 为 `CN` 或 `GLOBAL`。两个站点的账号、工作空间、平台令牌和服务密钥分别配置，服务密钥不能复用平台令牌。后端域名可以共用，但必须能够从相应 Coze 站点访问。讯飞服务凭证只保存在服务端，不作为插件请求参数。

服务通过 `COZE_ENV_FILE` 指定配置文件，或完全使用进程环境变量；进程环境变量优先，配置变更后需要重启服务。

## 安装与启动

在仓库根目录执行：

```powershell
uv sync --locked --project integrations/coze --python 3.13
$env:COZE_ENV_FILE = (Resolve-Path integrations/coze/.env).Path
uv run --locked --project integrations/coze --python 3.13 uvicorn app.main:create_app --factory --app-dir integrations/coze --host 127.0.0.1 --port 8000 --no-access-log
```

Linux 或 macOS：

```sh
uv sync --locked --project integrations/coze --python 3.13
COZE_ENV_FILE=integrations/coze/.env uv run --locked --project integrations/coze --python 3.13 uvicorn app.main:create_app --factory --app-dir integrations/coze --host 127.0.0.1 --port 8000 --no-access-log
```

生产环境应在反向代理或托管网关后提供 HTTPS，并设置请求超时、并发、文件大小和日志保留策略。不要把本地 HTTP 地址填入 Coze 插件配置。

## 健康检查

访问：

```text
GET /healthz
```

正常响应为：

```json
{"status":"ok"}
```

健康检查不需要服务密钥。业务工具请求使用 `X-API-Key` 请求头：

```http
X-API-Key: <对应站点的 COZE_<SITE>_BACKEND_API_KEY>
```

服务端根据密钥绑定的站点、工作空间和允许能力进行授权，请求参数不能切换站点或工作空间。错误响应统一包含 `error.code`、`error.message`、`error.retryable` 和 `trace_id`；响应头同时返回 `X-Trace-Id`，可用于排查问题。

## Coze 接入

1. 为目标站点准备可访问的 HTTPS 服务地址，并在配置中填写对应的 `BACKEND_BASE_URL`。
2. 在 Coze 中创建基于已有服务的 API 插件，导入与服务版本对应的 OpenAPI 文档。
3. 为插件工具配置 `X-API-Key` 请求头，使用目标站点的服务密钥。
4. 逐项调试工具，确认请求参数、响应字段和文件地址符合文档后再发布插件。

国内站和国际站分别使用各自的工作空间、插件记录和服务密钥。一个站点的令牌、插件 ID 或权限不能替代另一个站点的配置。

## 工作空间检查

需要确认平台令牌和工作空间范围时，可运行：

```sh
uv run --locked --project integrations/coze --python 3.13 python -B integrations/coze/scripts/check_config.py --site cn --online
uv run --locked --project integrations/coze --python 3.13 python -B integrations/coze/scripts/check_config.py --site global --online
```

检查只读查询对应站点的工作空间，不创建或发布资源；令牌需要具备 `listWorkspace` 权限。检查结果不会输出令牌、完整工作空间 ID 或工作空间名称。

## 当前服务边界

业务工具、文件处理、长任务、产物存储、OpenAPI 文档导出和插件管理操作均以实际发布版本的文档为准。未在文档中列出的路径、参数或管理接口不能直接调用。平台令牌只用于平台管理检查，普通插件调用不需要将平台令牌传给本服务。

变更记录见 [CHANGELOG.md](./CHANGELOG.md)。

