# iFly-Skills Coze 服务

本目录提供可自行部署的 iFly-Skills 后端及 Coze 插件规范。由使用方或团队管理员部署服务、配置 HTTPS 域名和业务凭证，再在自己的 Coze 工作空间创建插件。智能体／工作流的调用者使用配置好的插件，无需各自部署服务。

一个部署实例为 11 项 Skill 提供共享后端，可选择启用国内站、国际站或两站。各部署使用自己的配置和数据目录；同一实例内按站点分别配置工作空间和访问密钥。项目提供源码、插件规范与部署说明，不提供统一运营的公共服务；服务器、域名／证书、存储维护及讯飞调用费用由部署方承担。

服务提供 11 个 Skill、24 个工具，地址为 `/v1/skills/<skill-id>/<action>`，并提供每 Skill 一份 OpenAPI 3.0.3 规范。使用前需配置相应业务凭证及运行环境；缺少依赖的工具返回 `DEPENDENCY_UNAVAILABLE`。插件通过官方控制台导入、调试和发布，完整流程见[插件接入与发布说明](./PUBLISHING.md)。

## 使用条件

- Python 3.13 或 3.14
- [uv](https://docs.astral.sh/uv/)
- 自行准备的服务运行环境，以及可从目标 Coze 站点访问的 HTTPS 域名和证书（本地调试可先使用 HTTP）
- 目标站点的 Coze 工作空间及 API 插件创建、调试和发布权限
- 在[讯飞控制台](https://console.xfyun.cn)注册并为启用能力开通服务、准备额度及相应凭证；注册账号不等于所有能力均已授权

## 配置

复制 [.env.example](./.env.example) 为同目录的 `.env`，再填写实际值。`.env` 只保存在部署环境，不要提交到代码仓库。

| 配置项 | 说明 |
| --- | --- |
| `COZE_ENABLED_SITES` | 填写 `cn`、`global` 或 `cn,global`，明确启用的站点 |
| `COZE_<SITE>_WORKSPACE_ID` | 对应站点的工作空间 ID |
| `COZE_<SITE>_BACKEND_API_KEY` | 插件访问本服务的独立密钥，长度 32～256 个无空格 ASCII 可打印字符 |
| `COZE_<SITE>_ALLOWED_SKILLS` | 允许该站点调用的 Skill ID，使用逗号分隔 |
| `COZE_<SITE>_API_BASE_URL` | 国内使用 `https://api.coze.cn`，国际使用 `https://api.coze.com` |
| `COZE_<SITE>_API_TOKEN` | 可选，仅用于本站工作空间只读检查；普通部署和控制台发布无需填写 |
| `COZE_<SITE>_BACKEND_BASE_URL` | 部署后供插件访问的 HTTPS 服务地址；本地运行时可留空 |
| `IFLY_APP_ID`／`IFLY_API_KEY`／`IFLY_API_SECRET` | 原子 Skill 的讯飞业务凭证，须分别开通所需服务 |
| `IFLY_CONTRACT_APP_ID`／`IFLY_CONTRACT_API_KEY`／`IFLY_CONTRACT_API_SECRET` | 合同流程独立配置的业务凭证；用于图片 OCR、图片理解、翻译和 Spark v3.5（`generalv3.5`）审核 |
| `COZE_DATA_DIR` | 私有持久化目录；留空时使用本目录下的 `output/runtime` |
| `COZE_ARTIFACT_BASE_URL` | 可访问产物的 HTTPS 服务地址，可含反向代理路径前缀；与实际 `/v1/artifacts/...` 路由对应 |
| `COZE_RENDER_IMAGE` | 完成隔离验收后的本地渲染镜像 ID（`sha256:...`）；留空关闭 GIF 渲染 |

其中 `<SITE>` 为 `CN` 或 `GLOBAL`。只需填写启用站点的运行配置；平台令牌仅在执行工作空间只读检查时提供，启动服务、导出规范和控制台发布均不需要平台令牌。当前每个部署实例在每站绑定一个工作空间。两个站点的账号、工作空间、平台令牌和服务密钥分别配置，服务密钥不能复用平台令牌。同一部署的后端域名可以共用，但必须能够从相应 Coze 站点访问。讯飞服务凭证只保存在服务端，不作为插件请求参数。

`BACKEND_BASE_URL` 和 `COZE_ARTIFACT_BASE_URL` 均填写 HTTPS 服务域名及可选的代理路径前缀。不要填写 Coze 平台 API 域名、IP、具体工具／产物路径，或含凭证、查询串的地址；服务会自行拼接相应路由。

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

在自己的部署环境中通过反向代理或托管网关提供 HTTPS，并设置请求超时、文件大小和日志保留策略。插件接入前确定稳定的域名和路径前缀；本地 HTTP 地址仅用于调试。请保留仓库中的 `skills/` 目录，适配器从固定位置加载原始脚本及资源。

正式部署请按[服务器与域名部署说明](./deploy/README.md)准备域名和证书、填写配置、启动并检查服务。Docker Compose 适用于除 GIF 外的工具；需要 GIF 时，使用说明中的 [Linux 直接运行方式](./deploy/README.md#启用-giflinux-直接运行)。

当前使用 SQLite 和本地产物存储，**每个数据目录只运行一个服务进程**，不要设置多个 Uvicorn worker。服务默认每个工作空间每分钟 60 次请求、最多 2 个同时执行的调用，实例最多 4 个。本地审核和渲染一次只处理一个任务，最多保留 32 个排队或运行中的任务；单任务执行最多 600 秒，含排队总计最多 900 秒。例如前一个任务耗时 600 秒，紧随其后的任务最多只剩约 300 秒执行时间；队列容量不代表能在期限内完成的任务数量。

普通同步调用预算 60 秒。视频任务创建／查询、音频转写任务创建、PDF 结果查询的整体预算为 600 秒，租约为 660 秒，以容纳下载、上传和产物保存；其中音视频输入及上游产物的每个文件下载预算为 180 秒，多个文件仍共享整体执行预算。文件大小上限不保证任意网速下均可完成。上述调用仍等待执行结果，部署网关与 Coze 节点的超时应覆盖实际耗时；超时后保留原 `request_id` 或 `job_id` 查询状态，避免重复提交。

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

部署后可运行 `scripts/check_deployment.py --site cn --all-tools` 或 `--site global --all-tools`，按本站配置检查 HTTPS、认证及全部启用工具的路由，包括无需上游调用的内置发音人列表。命令不调用收费上游，完整执行方式见[部署说明](./deploy/README.md#构建启动与检查)。检查通过不代表业务权限、真实结果或 Coze 调试已通过。

## Coze 接入

1. 部署并启动服务，验证 HTTPS 健康检查；填写目标站点的 `BACKEND_BASE_URL`。文件结果及上游取样还需配置 `COZE_ARTIFACT_BASE_URL`，确保对应的 `/v1/artifacts/...` 路由可从 Coze 和所用上游服务访问。
2. 按下节生成指向本次部署的 OpenAPI 文件，在自己的目标工作空间创建基于已有服务的 API 插件，每个 Skill 导入对应文件。
3. 为插件工具配置 `X-API-Key` 请求头，使用目标站点的服务密钥。
4. 按[接入与发布说明](./PUBLISHING.md)逐项调试工具，确认请求参数、响应字段和文件地址符合文档后发布，再从智能体／工作流验证调用。需要公共分发时，由该服务的部署方另行申请商店上架。只启用已具备运行条件并完成验证的能力。

每个部署方创建指向自己后端的插件实例。国内站和国际站分别使用各自的工作空间、插件记录和服务密钥；插件 ID、发布版本与部署地址应对应保存，不能复用其他部署或站点的记录。

国内站的[导入规则](https://docs.coze.cn/guides_import.md)和[国际站导入规则](https://docs.coze.com/guides/plugin_import)均规定插件 URL 导入后不可修改；更换域名或公共前缀时需重新创建插件并更新智能体／工作流引用。同一地址下的更新可沿用原插件，并按本站平台要求调试、发布及更新引用。

### 生成 OpenAPI 文件

[schemas/](./schemas/) 包含 11 份 JSON 插件文件，仓库版本使用 `https://backend.example.com` 示例域名。导入前，按下面的命令生成自己服务地址对应的文件。安装时保留默认依赖；导出命令会校验文件，不调用讯飞或 Coze 服务。

在仓库根目录执行，分别读取 `.env` 中的 `COZE_CN_BACKEND_BASE_URL` 与 `COZE_GLOBAL_BACKEND_BASE_URL`：

```sh
uv run --locked --project integrations/coze --python 3.13 python -B integrations/coze/scripts/export_openapi.py --site cn
uv run --locked --project integrations/coze --python 3.13 python -B integrations/coze/scripts/export_openapi.py --site global
```

文件分别生成到 `integrations/coze/output/schemas/cn/` 和 `global/`，文件名为 `<skill-id>.json`。文件使用所选站点的服务地址，保存在 Git 忽略目录中，不包含密钥或工作空间信息。配置另存时，添加 `--env-file <配置文件路径>` 并指定 `--site`；缺失地址会提示需要填写的配置项。

也可以显式指定后端地址而不读取配置文件：

```sh
uv run --locked --project integrations/coze --python 3.13 python -B integrations/coze/scripts/export_openapi.py --base-url https://your-backend.example.com/coze
```

此时默认输出到 `integrations/coze/output/schemas/custom/`，可用 `--output-dir` 指定专用目录。地址只能是 HTTPS 域名及可选的反向代理前缀，不能填写平台 API 域名、IP、密钥或具体工具路径。例如 `servers.url=https://your-backend.example.com/coze` 与路径 `/v1/skills/iflytek-translate/translate` 拼接成外部请求地址；代理需将 `/coze` 前缀移除后转发到后端。

不传地址参数时重新生成仓库示例规范；添加 `--check` 只检查文件与当前接口的一致性，不写文件：

```sh
uv run --locked --project integrations/coze --python 3.13 python -B integrations/coze/scripts/export_openapi.py --check
```

规范声明 Header API key 认证、GET 查询参数、POST JSON 请求及统一错误响应，不导出健康检查或产物下载为插件工具。异步操作返回 HTTP 200 表示任务快照，须继续检查 `status`。3.0.3 校验通过不等于 Coze 导入或发布成功；两站导入后仍须核对参数、可空结果、认证及真实调用。

## 工具与调用

下表中的查询操作及 `list_voices` 使用 GET，其余操作使用 POST JSON。GET 的 `job_id`／`text_id` 放在查询参数中。

| Skill | 工具 | 主要输入与结果 |
| --- | --- | --- |
| `iflytek-translate` | `translate` | `text`、`from_lang`、`to_lang` → 原文、译文及语言；文本最多 4096 UTF-8 字节 |
| `iflytek-text-proofread` | `check` | `text` → `checklist`；最多 220000 字符，不自动截断 |
| `iflytek-ocr-invoice` | `recognize` | `image_url` → 结构化票据字段 |
| `iflytek-hyper-tts` | `synthesize`、`list_voices` | 文本、发音人及韵律参数 → MP3；发音人列表无需业务凭证 |
| `iflytek-pdf-image-ocr` | `recognize_image`、`create_pdf_task`、`get_pdf_task` | 图片或 PDF URL → 识别内容／任务及产物；PDF 最多 100 页 |
| `iflytek-speed-transcription` | `create_task`、`get_task` | `audio_url`（MP3）→ 文本及分段；保留上游时间值，不转换单位 |
| `iflytek-image-understanding` | `analyze` | `image_url`、`question` → 完整回答及用量 |
| `iflytek-video-translate` | `create_task`、`get_task`、`confirm_transcript` | MP4 URL、源／目标语言 → 视频任务；成功后返回输出，待确认阶段仅返回状态；确认会直接接受上游字幕，不提供预览或编辑 |
| `iflytek-voiceclone-tts` | `get_training_text`、`create_training`、`upload_sample`、`submit_training`、`get_training`、`synthesize` | 获取训练文本，创建、上传、提交、查询，成功后用本工作空间的 `res_id` 合成 MP3 |
| `iflytek-contract-intelligence-review` | `review`、`get_review` | 合同 URL → 规则和模型审核结果、Markdown／JSON 报告 |
| `animated-sketch-diagram` | `render_html_to_gif`、`get_render` | 受限 `html`、尺寸、帧率和时长 → GIF |

例如，发送翻译请求：

```http
POST /v1/skills/iflytek-translate/translate
X-API-Key: <service-key>
Content-Type: application/json

{"text":"Hello world","from_lang":"en","to_lang":"cn"}
```

创建任务和训练／字幕的阶段操作必须提供 `request_id`。同一操作重试时复用原标识与原参数；相同标识配不同参数返回 `CONFLICT`。任务受理返回 HTTP 200 和 `job_id`、`status`，不代表业务完成。保存 `job_id`，至少间隔 5 秒查询，并在工作流中设置总时限与失败分支。

任务状态包括 `queued`、`running`、`waiting_input`、`succeeded`、`partially_succeeded`、`failed`、`submission_unknown`。`ANY_FAILED` 的 PDF 保留部分失败状态。提交超时或进程中断时不会自动重新提交；`submission_unknown` 需核实上游受理情况，有上游映射的任务可以继续查询。重启后保留未开始的本地队列与已受理的上游任务；正在执行的本地审核或渲染任务会标记为 `failed/TIMEOUT`，远程提交任务会保留为 `submission_unknown`，中断的调用不会自动重跑。

声音训练依次使用“创建 → 上传样本 → 提交训练 → 查询”；上传操作仅登记样本，不隐式提交训练。录音应由获授权的说话人按 `get_training_text` 返回的文本录制，上传时使用对应的 `text_id` 和 `seg_id`。当前工具不接收自定义训练文本，提供已有录音的转写不能替代所选服务端文本。合成只接受当前工作空间已成功训练的 `res_id`。

训练返回 `failure_reason=audio_text_mismatch` 时，需要按所选文本重新准备录音；格式合格或上传成功不代表训练成功。权限、额度不足等明确拒绝记录为失败；修复条件后重新发起请求时使用新的 `request_id`。

## 文件与能力限制

输入文件使用可下载的公网 HTTPS URL，不支持本地路径、内网地址或直接传入 Coze `file_id`。文件的实际格式需要符合要求，修改扩展名不能转换格式。图片只接收 PNG／JPEG，最多 4 MiB；PDF 最多 32 MiB；转写 MP3 和视频 MP4 最多 128 MiB。训练样本只接收单声道 WAV（16 bit）或 MP3，采样率至少 24 kHz、时长不超过 40 秒、最多 3 MiB，并须与所选训练文本一致。这些是后端接入上限，服务商限制仍需满足。

极速转写使用固定的 `language=zh_cn`、`accent=mandarin`、`domain=pro_ost_ed` 参数组合，服务自动识别中英文；英文录音也使用该组合。图片 OCR 的 `format` 可选 `json`、`markdown`、`json,markdown`，分别返回结构化 `json`、`markdown` 或两者。PDF 的已知服务商 HTTP 产物地址仅通过经验证的 HTTPS 对应地址下载，不回退到 HTTP。

音频、视频、GIF 和报告使用随机、限时 HTTPS URL，响应包含 `mime_type`、`size_bytes`、`expires_at`。**持有 URL 即可下载有效期内的产物**；应将地址作为私有数据保管。下载路由 `/v1/artifacts/...` 使用含 192 位随机熵的地址，不要求 `X-API-Key`，也不受工具调用的工作空间限流保护，便于 Coze 和上游服务拉取文件。服务记录请求追踪 ID、状态和耗时，不记录完整下载地址；没有按下载者身份审计或下载专用限流。需要限制下载流量时，可在反向代理设置连接数或速率限制，并确认不影响 Coze 和上游拉取。

输出默认保留 1 小时，供上游拉取的视频／训练样本保留 24 小时。保留期限独立于任务状态：即使任务提前失败，已转存的输入仍可通过原 URL 下载，直至过期；到期立即拒绝新下载请求，文件随后由后台自动清理。产物总容量上限 2 GiB、单文件上限 128 MiB。任务和报告记录包含业务内容，数据目录需限制访问、持久保存；任务标识的去重记录不自动删除。

合同支持 UTF-8 TXT／Markdown、DOCX（包含表格）、PDF、PNG／JPEG，不支持旧 `.doc`；最多 20 MiB、8 页 PDF，提取后最多 4000 字符，超限需先拆分。`quick`／`standard`／`deep` 沿用原 Skill 的规则范围并进行模型审核；`deep`、英文合同或 `need_translation=true` 会生成英文译文摘要，必要阶段失败即任务失败。结果区分规则检查和模型推断；模型风险的证据必须是原文连续引用，不匹配的条目移入 `model_review.uncertain_items` 并生成建议，标记需人工复核，其他有效结果和报告仍保留。未测量的置信度为空。`output_format` 可选 `markdown`、`json`、`both`。

训练适配器使用验证证书的 HTTPS，拒绝重定向；克隆合成使用验证证书的 WSS。部署前需按[声音复刻文档](https://www.xfyun.cn/doc/spark/voiceclone.html)准备录音，并核对实际账号的训练和合成权限。视频查询将 `waiting_transcript_confirmation`／`waiting_manual_intervention_segment` 映射为待字幕确认；`waiting_manual_intervention_refine` 为上游翻译审核阶段，须在服务商支持的审核入口处理后继续查询，不能用 `confirm_transcript` 代替。服务商取消的任务作为失败返回。视频最终产物及各服务的业务权限和媒体结果，需用实际账号完成联调后启用相应插件。

## GIF 隔离运行环境

GIF 只支持 HTML／SVG／CSS 绘图和 CSS 动画，不接收脚本、事件处理器、外部资源或本地文件引用。上限为 256 KiB HTML、2000 个元素、1600×1200、25 fps、5 秒、2 倍缩放，并受 1.2 亿像素帧预算约束。

GIF 需要 Linux 和本机 Docker。按[部署说明](./deploy/README.md#启用-giflinux-直接运行)构建渲染镜像，将得到的镜像 ID 填入 `COZE_RENDER_IMAGE`，完成一次生成、查询和下载检查后启用。渲染在独立容器中运行，限制资源并关闭网络，不传入讯飞凭证。

## 工作空间检查

需要确认平台令牌和工作空间范围时，可运行：

```sh
uv run --locked --project integrations/coze --python 3.13 python -B integrations/coze/scripts/check_config.py --site cn --online
uv run --locked --project integrations/coze --python 3.13 python -B integrations/coze/scripts/check_config.py --site global --online
```

检查只读查询对应站点的工作空间，不创建或发布资源；令牌需要具备 `listWorkspace` 权限。检查结果不会输出令牌、完整工作空间 ID 或工作空间名称。

## 当前服务边界

部署方维护服务、域名和证书，在 Coze 控制台完成导入、调试和工作空间发布，再按需申请商店上架。国内和国际站分别操作，详细步骤见[发布说明](./PUBLISHING.md)。商店插件固定调用部署时配置的地址；使用自有服务器时创建对应的插件。

服务认证由部署方在 Coze 中配置 `X-API-Key`，调用者无需填写讯飞凭证，费用统一归部署方的讯飞账号。同一插件调用者共享已授权能力和用量上限。上架前需确认服务权限、额度、真实工具结果和持续运行安排，并填写实际的数据处理说明；最终以平台审核为准。
